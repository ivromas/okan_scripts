# !/usr/bin/env python3
# -*- coding: UTF-8 -*-
from __future__ import with_statement
import gspread
from bs4 import BeautifulSoup
import requests
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import re
import urllib.parse
import sys
import config


class ProgressBar:

    @staticmethod
    def print_progress(iteration, total, prefix='', suffix='', decimals=1, bar_length=100):
        """
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : positive number of decimals in percent complete (Int)
            bar_length  - Optional  : character length of bar (Int)
        """
        str_format = "{0:." + str(decimals) + "f}"
        percents = str_format.format(100 * (iteration / float(total)))
        filled_length = int(round(bar_length * iteration / float(total)))
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, bar, percents, '%', suffix)),
        if iteration == total:
            sys.stdout.write('\n')
        sys.stdout.flush()


class GSWorksheet(ProgressBar):
    def recursion_auth(self):
        credentials = self.credentials
        try:
            gs = gspread.authorize(credentials)
            return gs
        except TimeoutError:
            gs = self.recursion_auth()
            return gs
        except requests.exceptions.RequestException:
            gs = self.recursion_auth()
            return gs

    def recursion_open_by_key(self):
        gs = self.gs
        try:
            gsh_ok_sales = gs.open_by_key(config.SPREADSHEET_KEY)
            return gsh_ok_sales
        except requests.exceptions.RequestException:
            gsh_ok_sales = self.recursion_open_by_key()
            return gsh_ok_sales

    def recursion_update_gs(self, cell):
        try:
            self.worksheet.update_cells(cell)
        except gspread.exceptions.RequestError:
            self.recursion_update_gs(cell)

    def update_gs(self, value_list):
        self.print_progress(0, len(value_list), prefix='Updating GS:', suffix='Complete', bar_length=50)
        for i in range(0, len(value_list)):
            j = str(i + 2)
            cell_list = self.worksheet.range('A' + j + ':V' + j)
            k = 0
            self.print_progress(i, len(value_list), prefix='Updating GS:', suffix='Complete', bar_length=50)
            for cell in cell_list:
                cell.value = value_list[i][k]
                k += 1
            self.recursion_update_gs(cell_list)
        self.print_progress(len(value_list), len(value_list), prefix='Updating GS:', suffix='Completed', bar_length=50)

    def __init__(self, scope, credentials_path):
        self.scope = scope
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, self.scope)
        self.gs = self.recursion_auth()
        self.gsh_ok_sales = self.recursion_open_by_key()
        self.worksheet = self.gsh_ok_sales.get_worksheet(0)


class TransactionsList(ProgressBar):

    @staticmethod
    def normilise_time(time):
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
        if time.hour == 23 and time.minute == 59:
            time = time.strftime("%d.%m.%Y")
            time_exact = ''
        else:
            time_exact = time.strftime("%H:%M")
            time = time.strftime("%d.%m.%Y")
        return time, time_exact

    def get_number_of_lots(self):
        list = self.list_of_lists
        counter = 0
        for col in list:
            if col[0] == 'А' and len(col[config.TABLE_URL_POS]) != 0:
                counter += 1
        return counter

    def sort_list(self):
        s_list_of_lists = sorted(self.list_of_lists, key=lambda x: x[0])
        sort_list_to_return = []
        s_point_start = s_list_of_lists[0][0]
        return_list = []
        for j in range(0, len(s_list_of_lists)):
            if s_point_start == s_list_of_lists[j][0]:
                return_list.append(s_list_of_lists[j])
            elif s_point_start == 'А':
                number_of_A = self.get_number_of_lots()
                # print('\n')
                self.print_progress(0, number_of_A, prefix='Parsing', suffix='', bar_length=25)
                for i in range(0, len(return_list)):
                    if len(return_list[i][config.TABLE_URL_POS]) != 0:
                        okan_id = return_list[i][1]
                        order_url = return_list[i][config.TABLE_URL_POS]
                        self.print_progress(i, number_of_A, prefix='Parsing', suffix=order_url, bar_length=25)
                        tr_object = SingleTransaction(order_url, okan_id, self.local_time_now)
                        events_of_current_transaction = tr_object.events_of_current_transaction
                        return_list[i][config.TABLE_NMC_POS] = events_of_current_transaction['НМЦ']
                        return_list[i][config.TABLE_NAME_POS] = events_of_current_transaction['Наименование']
                        return_list[i][config.TABLE_CURRENT_ACT_POS] = events_of_current_transaction['Текущее событие']
                        return_list[i][config.TABLE_DATE_CURRENT_ACT_POS] =\
                            events_of_current_transaction['Дата текущего события']
                        return_list[i][config.TABLE_TIME_CURRENT_ACT_POS] =\
                            events_of_current_transaction['Время текущего события']
                        return_list[i][config.TABLE_SUBMIT_APPLICATIONS_POS] =\
                            events_of_current_transaction['Подача заявок']
                        return_list[i][config.TABLE_QUALIFYING_STAGE_POS] =\
                            events_of_current_transaction['Отборочная стадия']
                        return_list[i][config.TABLE_EVALUATION_STAGE_POS] =\
                            events_of_current_transaction['Оценочная стадия']
                        return_list[i][config.TABLE_NEW_FILE_POS] = events_of_current_transaction['Новые файлы']
                    # check all events
                    return_list[i][config.TABLE_SORT_FACTOR_POS] = \
                        int(self.sequence_of_events[return_list[i][config.TABLE_CURRENT_ACT_POS]])
                # sort by number of event
                list_of_list_sort = sorted(return_list, key=lambda x: x[config.TABLE_SORT_FACTOR_POS])
                sort_list = []
                sort_list_final = []
                point_start = list_of_list_sort[0][config.TABLE_SORT_FACTOR_POS]
                # sort by date for each event
                for i in range(0, len(list_of_list_sort)):
                    if point_start == list_of_list_sort[i][config.TABLE_SORT_FACTOR_POS]:
                        sort_list.append(list_of_list_sort[i])
                    else:
                        # даты есть только для 1.2.4 событий
                        if point_start < 3 or point_start is 4:
                            sort_list_final = sort_list_final + \
                                              sorted(sort_list,
                                                     key=lambda x: datetime.datetime.strptime(x[config.TABLE_DATE_CURRENT_ACT_POS], "%Y-%m-%d %H:%M:%S")
                                                     )
                        else:
                            sort_list_final += sort_list
                        del sort_list
                        sort_list = [list_of_list_sort[i]]
                        point_start = list_of_list_sort[i][config.TABLE_SORT_FACTOR_POS]
                if point_start < 3 or point_start is 4:
                    sort_list_final = sort_list_final + sorted(sort_list,
                                                               key=lambda x: datetime.datetime.strptime(x[config.TABLE_DATE_CURRENT_ACT_POS],
                                                                                                        "%Y-%m-%d %H:%M:%S"))
                else:
                    sort_list_final += sort_list
                del sort_list, point_start
                for i in range(0, len(sort_list_final)):
                    if sort_list_final[i][config.TABLE_SORT_FACTOR_POS] < 3 or sort_list_final[i][config.TABLE_SORT_FACTOR_POS] is 4:
                        if len(sort_list_final[i][config.TABLE_DATE_CURRENT_ACT_POS]) > 10:
                            sort_list_final[i][config.TABLE_DATE_CURRENT_ACT_POS], sort_list_final[i][config.TABLE_TIME_CURRENT_ACT_POS] = self.normilise_time(sort_list_final[i][config.TABLE_DATE_CURRENT_ACT_POS])
                        if len(sort_list_final[i][config.TABLE_SUBMIT_APPLICATIONS_POS]) > 10:
                            sort_list_final[i][config.TABLE_SUBMIT_APPLICATIONS_POS], x = self.normilise_time(sort_list_final[i][config.TABLE_SUBMIT_APPLICATIONS_POS])
                        if len(sort_list_final[i][config.TABLE_QUALIFYING_STAGE_POS]) > 10:
                            sort_list_final[i][config.TABLE_QUALIFYING_STAGE_POS], x = self.normilise_time(sort_list_final[i][config.TABLE_QUALIFYING_STAGE_POS])
                        if len(sort_list_final[i][config.TABLE_EVALUATION_STAGE_POS]) > 10:
                            sort_list_final[i][config.TABLE_EVALUATION_STAGE_POS], x = self.normilise_time(sort_list_final[i][config.TABLE_EVALUATION_STAGE_POS])
                sort_list_to_return = sort_list_final
                break
        self.list_of_lists = []
        self.list_of_lists = sort_list_to_return

    def __init__(self, gs_list, time):
        self.local_time_now = time
        self.list_of_lists = gs_list[1:]
        self.sequence_of_events = {
            'Подача заявок': 1,
            'Подача заявок(Ожидает решения организатора)': 1,
            'Подача заявок(Приостановлен)': 1,
            'Подача заявок(Ожидает решение по определению участников)': 1,
            'Отборочная стадия': 2,
            'Отборочная стадия(Приостановлен)': 2,
            'Отборочная стадия(Ожидает решения организатора)': 2,
            'Отборочная стадия(Ожидает решение по определению участников)': 2,
            'Оценочная стадия': 4,
            'Оценочная стадия(Приостановлен)': 4,
            'Оценочная стадия(ЗАКРЫТ)': 4,
            'Оценочная стадия(Ожидает решения организатора)': 4,
            'Формирование КД': 6,
            'Формирование НМЦ': 7,
            'Запрос ТКП': 8,
            'Итоги': 5,
            'Лид': 9,
            'Переторжка': 3,
            '-': 10
        }
        self.sort_list()


class SingleTransaction:

    def recursion_request(self, url):
        try:
            page = requests.get(url)
            return page
        except requests.exceptions.RequestException:
            page = self.recursion_request(url)
            return page
        except TimeoutError:
            page = self.recursion_request(url)
            return page

    def recursion_request_head(self, url):
        try:
            page = requests.head(url).headers['content-disposition']
            return page
        except requests.exceptions.RequestException:
            page = self.recursion_request_head(url)
            return page
        except TimeoutError:
            page = self.recursion_request_head(url)
            return page

    def download_file(self, url):
        rq = self.recursion_request(url)
        rq_head = self.recursion_request_head(url)
        fname = re.findall("FileName=(.+)", rq_head)
        if fname.__len__() == 0:
            fname = re.findall("'\\'(.+)", rq_head)
            local_filename_return = self.okan_id[:6] + '_' + urllib.parse.unquote(fname[0]).replace('+', '_')
        else:
            local_filename_return = self.okan_id + '_' + fname[0].encode('latin_1', 'ignore').decode('utf-8').strip('"')
        local_filename = config.DOWNLOAD_FILE_PATH + local_filename_return
        with open(local_filename, 'wb') as f:
            for chunk in rq.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
        return local_filename_return

    def get_number_of_lot(self):
        okan_id_for_fabrikant_multilot = {
            1: [1, 2],
            2: [3, 4],
            3: [5, 6],
            4: [7, 8]
        }
        for i in range(1, 5):
            assert (self.okan_id[-2].isdigit() is True)
            if i == int(self.okan_id[-2]):
                return okan_id_for_fabrikant_multilot[i]

    def get_data_table(self, lot_dates_url):
        # patsing data lot table
        page_data = self.recursion_request(lot_dates_url)
        data_soup = BeautifulSoup(page_data.content, 'lxml')
        data_div_table = data_soup.find("table", {"id": "table_03"})
        data_div_table_all_rows = data_div_table.findAll('tr')
        data_list = []
        for row in data_div_table_all_rows:
            data_list_col = []
            allcols = row.findAll('td')
            for col in allcols:
                content = col.getText()
                data_list_col.append(content)
            data_list.append(data_list_col)
        return data_list

    def math(self, event_name):
        match = re.search(r'\d{2}.\d{2}.\d{4} \d{2}:\d{2}', self.events_of_current_transaction[event_name])
        self.events_of_current_transaction[event_name] = datetime.datetime.strptime(match.group(), "%d.%m.%Y %H:%M")

    def get_lot_table_with_urls(self):
        # get url with a lot table
        # print(self.order_url)
        page = self.recursion_request(self.order_url)
        # assert(page.status_code == 200)
        # assert(page.status_code == 404)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, 'lxml')
        new_file = ''
        if "fabrikant" in self.order_url:
            number_of_lot = self.get_number_of_lot()
            lot_div = soup.find_all("table", {'class': 'blank'})
            lot_table_list = []
            for i in range(number_of_lot[0], number_of_lot[1] + 1):
                lot_table_list_col = lot_div[i].findAll('tr')
                for row in lot_table_list_col:
                    lot_table_list_col = []
                    lot_table_list_col_allcols = row.findAll('td')
                    for col in lot_table_list_col_allcols:
                        content = col.getText().strip('\n\t')
                        lot_table_list_col.append(content)
                    lot_table_list.append(lot_table_list_col)
            file_url_table = soup.findAll("table", {'class': 'round_blocks'})
            links = file_url_table[0].findAll('a')
            url_table_with_docs = self.order_url.split('?')[0] + '?' + links[0]['href'].split('?')[1]
            page_docs = self.recursion_request(url_table_with_docs)
            soup_docs = BeautifulSoup(page_docs.content.decode('windows-1251'), 'lxml')
            rows = soup_docs.findAll("table", {'class': 'list document_list'})[0].find('tbody').find_all('tr')
            file_table = []
            k = 0
            for row in rows:
                cols = row.findAll('td')
                files_table_cols = []
                for col in cols:
                    content = col.getText().strip('\n\t')
                    if 'файл' in content:
                        href = col.contents[1]['href']
                        files_table_cols.append(href)
                    else:
                        files_table_cols.append(content)
                file_table.append(files_table_cols)
                x = datetime.datetime.strptime(file_table[k][3], "%d.%m.%Y %H:%M:%S")
                if x.date() == self.local_now_time.date():
                    new_filename = self.download_file(file_table[k][1])
                    new_file = new_filename + ' от ' + str(self.local_now_time.date())
                k += 1
            return lot_table_list, new_file
        elif 'rosatom' in self.order_url:
            url = 'http://zakupki.rosatom.ru'
            lot_div = soup.find("div", {"class": "table-lots-list",
                                        "id": "table_07"})
            lot_dates_url = url + [td.find('a') for td in lot_div][1].attrs['href']
            # get list with info from  lots table
            lot_div_table = lot_div.findAll('tr')
            lot_table_list = []
            for row in lot_div_table:
                lot_table_list_col = []
                lot_table_list_col_allcols = row.findAll('td')
                for col in lot_table_list_col_allcols:
                    content = col.getText()
                    lot_table_list_col.append(content)
                lot_table_list.append(lot_table_list_col)
            # status is in results[1][3]
            # href with dates table is in lot_dates_url
            files_div_table = soup.find("div", {"class": "table-lots-list",
                                                "id": "table_04"})
            files_table = files_div_table.findAll('tr')
            files_table_list = []
            for row in files_table:
                files_table_list_col = []
                files_table_list_allcols = row.findAll('td')
                # get urls of files
                files_table_dates_url = row.findAll('a', href=True)
                if files_table_dates_url:
                    href = url + files_table_dates_url[0].attrs['href']
                    files_table_list_col.append(href)
                for col in files_table_list_allcols:
                    content = col.getText().strip('\n\t')
                    files_table_list_col.append(content)
                files_table_list.append(files_table_list_col)
            files_table_list = files_table_list[1:]
            new_href = []
            for sublist in files_table_list:
                x = datetime.datetime.strptime(sublist[2], "%d.%m.%Y")
                if x.date() == self.local_now_time.date():
                    href = sublist[0]
                    new_filename = self.download_file(href)
                    new_file = new_filename + ' от ' + str(self.local_now_time.date())
                    new_href.append(href)
            return lot_dates_url, lot_table_list, new_file

    def get_info_of_current_transaction(self):
        if 'fabrikant' in self.order_url:
            lot_table_list, new_file = self.get_lot_table_with_urls()
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]
            if '*(1)' in self.okan_id:
                self.events_of_current_transaction['Подача заявок'] = lot_table_list[14][1]
                self.events_of_current_transaction['Отборочная стадия'] = lot_table_list[15][1]
                self.events_of_current_transaction['Оценочная стадия'] = lot_table_list[16][1]
                self.events_of_current_transaction['Наименование'] = lot_table_list[2][1]
                self.events_of_current_transaction['НМЦ'] = lot_table_list[5][1]
                self.events_of_current_transaction['Новые файлы'] = new_file
            else:
                self.events_of_current_transaction['Подача заявок'] = lot_table_list[15][1]
                self.events_of_current_transaction['Отборочная стадия'] = lot_table_list[16][1]
                self.events_of_current_transaction['Оценочная стадия'] = lot_table_list[17][1]
                self.events_of_current_transaction['Наименование'] = lot_table_list[2][1]
                self.events_of_current_transaction['НМЦ'] = lot_table_list[6][1]
                self.events_of_current_transaction['Новые файлы'] = new_file

            self.math('Подача заявок')
            self.math('Отборочная стадия')
            self.math('Оценочная стадия')

            if self.local_now_time < self.events_of_current_transaction['Подача заявок']:

                self.events_of_current_transaction['Текущее событие'] = 'Подача заявок'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Подача заявок']

            elif self.local_now_time < self.events_of_current_transaction['Отборочная стадия']:

                self.events_of_current_transaction['Текущее событие'] = 'Отборочная стадия'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Отборочная стадия']

            elif self.events_of_current_transaction['Закрыт'] == '(ЗАКРЫТ)':

                self.events_of_current_transaction['Текущее событие'] = 'Оценочная стадия(ЗАКРЫТ)'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Оценочная стадия']

            else:
                self.events_of_current_transaction['Текущее событие'] = 'Оценочная стадия'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Оценочная стадия']
            if 'Идёт приём заявок' not in actual_status:
                self.events_of_current_transaction['Текущее событие'] = \
                    self.events_of_current_transaction['Текущее событие'] + '(' + actual_status + ')'

            self.events_of_current_transaction['Подача заявок'] = \
                str(self.events_of_current_transaction['Подача заявок'])
            self.events_of_current_transaction['Отборочная стадия'] = \
                str(self.events_of_current_transaction['Отборочная стадия'])
            self.events_of_current_transaction['Оценочная стадия'] = \
                str(self.events_of_current_transaction['Оценочная стадия'])
            self.events_of_current_transaction['Дата текущего события'] = str(
                self.events_of_current_transaction['Дата текущего события'])

        elif 'rosatom' in self.order_url:
            lot_dates_url, lot_table_list, new_file = self.get_lot_table_with_urls()
            self.events_of_current_transaction['Наименование'] = lot_table_list[1][1]
            self.events_of_current_transaction['НМЦ'] = lot_table_list[1][2]
            self.events_of_current_transaction['Новые файлы'] = new_file
            if '(3)' in self.okan_id:
                lot_dates_url = \
                    'http://zakupki.rosatom.ru/Web.aspx?node=currentorders&action=siteview&oid=404202&mode=lot'
                self.events_of_current_transaction['НМЦ'] = lot_table_list[3][2]
                self.events_of_current_transaction['Наименование'] = lot_table_list[3][1]
            elif '(4)' in self.okan_id:
                lot_dates_url = \
                    'http://zakupki.rosatom.ru/Web.aspx?node=currentorders&action=siteview&oid=404203&mode=lot'
                self.events_of_current_transaction['НМЦ'] = lot_table_list[4][2]
                self.events_of_current_transaction['Наименование'] = lot_table_list[4][1]
            elif '(8)' in self.okan_id:
                lot_dates_url = \
                    'http://zakupki.rosatom.ru/Web.aspx?node=currentorders&action=siteview&oid=404207&mode=lot'
                self.events_of_current_transaction['НМЦ'] = lot_table_list[8][2]
                self.events_of_current_transaction['Наименование'] = lot_table_list[8][1]
            else:
                pass
            if type(lot_dates_url) == bool:
                self.events_of_current_transaction['Текущее событие'] = 'Некорректо указан url'
            data_list = self.get_data_table(lot_dates_url)
            for sublist in data_list:
                sublist[1] = sublist[1].replace(u'\xa0', u'')

                if len(sublist[1]) < 11:
                    sublist[1] += ' 23:59'

                if 'Дата и время продления срока подачи' in sublist[0]:
                    self.events_of_current_transaction['Подача заявок'] = sublist[1]
                elif 'Дата и время окончания подачи' in sublist[0]:
                    self.events_of_current_transaction['Подача заявок'] = sublist[1]
                if 'Измененная дата рассмотрения' in sublist[0]:
                    self.events_of_current_transaction['Отборочная стадия'] = sublist[1]
                elif 'Дата рассмотрения' in sublist[0]:
                    self.events_of_current_transaction['Отборочная стадия'] = sublist[1]
                if 'Измененная дата подведения итогов' in sublist[0]:
                    self.events_of_current_transaction['Оценочная стадия'] = sublist[1]
                elif 'Дата подведения итогов' in sublist[0]:
                    self.events_of_current_transaction['Оценочная стадия'] = sublist[1]

                if 'Закрыт' in sublist[0] and 'Да' == sublist[1]:
                    self.events_of_current_transaction['Закрыт'] = '(ЗАКРЫТ)'

            self.events_of_current_transaction['Подача заявок'] = datetime.datetime.strptime(str(
                self.events_of_current_transaction['Подача заявок']), "%d.%m.%Y %H:%M")
            self.events_of_current_transaction['Отборочная стадия'] = datetime.datetime.strptime(
                self.events_of_current_transaction['Отборочная стадия'], "%d.%m.%Y %H:%M")
            self.events_of_current_transaction['Оценочная стадия'] = datetime.datetime.strptime(
                self.events_of_current_transaction['Оценочная стадия'], "%d.%m.%Y %H:%M")

            if self.local_now_time < self.events_of_current_transaction['Подача заявок']:

                self.events_of_current_transaction['Текущее событие'] = 'Подача заявок'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Подача заявок']

            elif self.local_now_time < self.events_of_current_transaction['Отборочная стадия']:

                self.events_of_current_transaction['Текущее событие'] = 'Отборочная стадия'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Отборочная стадия']

            elif self.events_of_current_transaction['Закрыт'] == '(ЗАКРЫТ)':

                self.events_of_current_transaction['Текущее событие'] = 'Оценочная стадия(ЗАКРЫТ)'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Оценочная стадия']

            else:
                self.events_of_current_transaction['Текущее событие'] = 'Оценочная стадия'
                self.events_of_current_transaction['Дата текущего события'] = \
                    self.events_of_current_transaction['Оценочная стадия']

            if 'Приостановлен' in lot_table_list[1][3]:
                self.events_of_current_transaction['Текущее событие'] += '(Приостановлен)'

            self.events_of_current_transaction['Подача заявок'] = \
                str(self.events_of_current_transaction['Подача заявок'])
            self.events_of_current_transaction['Отборочная стадия'] = \
                str(self.events_of_current_transaction['Отборочная стадия'])
            self.events_of_current_transaction['Оценочная стадия'] = \
                str(self.events_of_current_transaction['Оценочная стадия'])
            self.events_of_current_transaction['Дата текущего события'] = str(
                self.events_of_current_transaction['Дата текущего события'])

    def __init__(self, order_url, okan_id, time):
        self.order_url = order_url
        self.okan_id = okan_id
        self.local_now_time = time
        self.events_of_current_transaction = {
                    'Текущая дата': self.local_now_time,
                    'Подача заявок': '',
                    'Отборочная стадия': '',
                    'Оценочная стадия': '',
                    'Закрыт': '',
                    'Текущее событие': '',
                    'Дата текущего события': '23:59',
                    'Время текущего события': '',
                    'Наименование': '',
                    'НМЦ': '',
                    'Новые файлы': '',
                }
        self.get_info_of_current_transaction()


def main():
    # get starting date
    local_now_time = datetime.datetime.now()
    # get data from GS
    gs_worksheet = GSWorksheet(config.SPREADSHEET_URL, config.GOOGLE_ENGINE_TOKEN_WAY)
    worksheet = gs_worksheet.worksheet
    list_of_lists = worksheet.get_all_values()
    # update data
    gs_update_data = TransactionsList(list_of_lists, local_now_time)
    list_for_gs_update = gs_update_data.list_of_lists
    # update GSz
    gs_worksheet.update_gs(list_for_gs_update)

if __name__ == '__main__':
    main()

