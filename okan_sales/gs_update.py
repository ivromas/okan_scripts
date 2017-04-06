# !/usr/bin/env python3
# -*- coding: UTF-8 -*-
from __future__ import with_statement
import gspread
from bs4 import BeautifulSoup
import requests
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import pandas as pd
import os
import re
import config


class GSWorksheet:
    def recursion_auth(self):
        credentials = self.credentials
        try:
            gs = gspread.authorize(credentials)
            return gs
        except TimeoutError:
            time.sleep(5)
            gs = self.recursion_auth()
            return gs

    def recursion_open_by_key(self):
        gs = self.gs
        try:
            gsh_ok_sales = gs.open_by_key(config.SPREADSHEET_KEY)
            return gsh_ok_sales
        except requests.exceptions.SSLError:
            time.sleep(5)
            gsh_ok_sales = self.recursion_open_by_key()
            return gsh_ok_sales

    def __init__(self, scope, credentials_path):
        self.scope = scope
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path,
                                                                   self.scope)
        self.gs = self.recursion_auth()
        self.gsh_ok_sales = self.recursion_open_by_key()
        self.worksheet = self.gsh_ok_sales.get_worksheet(0)


def recursion_request(url):
    try:
        page = requests.get(url)
        return page
    except requests.exceptions.ConnectionError:
        time.sleep(5)
        page = recursion_request(url)
        return page
    except requests.packages.urllib3.exceptions.ProtocolError:
        time.sleep(5)
        page = recursion_request(url)
        return page
    except TimeoutError:
        time.sleep(5)
        page = recursion_request(url)
        return page


def recursion_request_head(url):
    try:
        page = requests.head(url).headers['content-disposition']
        return page
    except requests.exceptions.ConnectionError:
        time.sleep(5)
        page = requests.head(url).headers['content-disposition']
        return page
    except requests.packages.urllib3.exceptions.ProtocolError:
        time.sleep(5)
        page = requests.head(url).headers['content-disposition']
        return page
    except TimeoutError:
        time.sleep(5)
        page = requests.head(url).headers['content-disposition']
        return page


def get_number_of_lot(okan_id):
    okan_id_for_fabrikant_multilot = {
        1: [1, 2],
        2: [3, 4],
        3: [5, 6],
        4: [7, 8]
    }
    for i in range(1, 5):
        assert(okan_id[-2].isdigit() is True)
        if i == int(okan_id[-2]):
            return okan_id_for_fabrikant_multilot[i]


def get_lot_table_with_urls(order_url, okan_id):
    # get url with a lot table
    print(order_url)
    page = recursion_request(order_url)
    # assert(page.status_code == 200)
    # assert(page.status_code == 404)
    page.raise_for_status()
    soup = BeautifulSoup(page.content, 'lxml')
    if "fabrikant" in order_url:
        number_of_lot = get_number_of_lot(okan_id)
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
        return lot_table_list
    elif 'rosatom' in order_url:
        url = 'http://zakupki.rosatom.ru'
        lot_div = soup.find("div", {"class": "table-lots-list",
                                       "id": "table_07"})
        try:
            lot_dates_url = url + [td.find('a') for td in lot_div][1].attrs['href']
        except NoneType:
            return False, False
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
        # local_now_time = datetime.datetime.strptime('2017-03-20', "%Y-%m-%d")
        local_now_time = datetime.datetime.now()
        new_file = ''
        new_href = []
        for sublist in files_table_list:
            x = datetime.datetime.strptime(sublist[2], "%d.%m.%Y")
            if x.date() == local_now_time.date():
                href = sublist[0]
                new_filename = download_file(href, okan_id)
                new_file = new_filename + ' от ' + str(local_now_time.date())
                new_href.append(href)
        return lot_dates_url, lot_table_list, new_file


def download_file(url, okan_id):
    rq = recursion_request(url)
    rq_head = recursion_request_head(url)
    fname = re.findall("FileName=(.+)", rq_head)
    local_filename_return = okan_id + '_' + fname[0].encode('latin_1', 'ignore').decode('utf-8').strip('"')
    local_filename = local_filename_return
    # local_filename = "//server1/1- script.files" + local_filename_return
    with open(local_filename, 'wb') as f:
        for chunk in rq.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                # f.flush() commented by recommendation from J.F.Sebastian
    return local_filename_return


def get_data_table(lot_dates_url):
    # patsing data lot table
    page_data = recursion_request(lot_dates_url)
    data_soup = BeautifulSoup(page_data.content, 'lxml')
    data_div_table = data_soup.find("table", {"id" : "table_03"})
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


def get_info_of_current_transaction(order_url, okan_id, local_now_time):

    if 'fabrikant' in order_url:
        lot_table_list = get_lot_table_with_urls(order_url, okan_id)
        if '(2)' in okan_id:
            events_of_current_transaction = {
                'Текущая дата': local_now_time,
                'Подача заявок': lot_table_list[16][1],
                'Отборочная стадия': lot_table_list[17][1],
                'Оценочная стадия': lot_table_list[18][1],
                'Закрыт': '',
                'Текущее событие': '',
                'Дата текущего события': '23:59',
                'Время текущего события': '',
                'Наименование': lot_table_list[2][1],
                'НМЦ': lot_table_list[6][1],
                'Новые файлы': ''
            }
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]
        elif '*(1)' in okan_id:
            events_of_current_transaction = {
                'Текущая дата': local_now_time,
                'Подача заявок': lot_table_list[15][1],
                'Отборочная стадия': lot_table_list[16][1],
                'Оценочная стадия': lot_table_list[17][1],
                'Закрыт': '',
                'Текущее событие': '',
                'Дата текущего события': '23:59',
                'Время текущего события': '',
                'Наименование': lot_table_list[2][1],
                'НМЦ': lot_table_list[6][1],
                'Новые файлы': ''
            }
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]
        elif '(1)' in okan_id:
            events_of_current_transaction = {
                'Текущая дата': local_now_time,
                'Подача заявок': lot_table_list[16][1],
                'Отборочная стадия': lot_table_list[17][1],
                'Оценочная стадия': lot_table_list[18][1],
                'Закрыт': '',
                'Текущее событие': '',
                'Дата текущего события': '23:59',
                'Время текущего события': '',
                'Наименование': lot_table_list[2][1],
                'НМЦ': lot_table_list[6][1],
                'Новые файлы': ''
            }
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]
        elif '(3)' in okan_id:
            events_of_current_transaction = {
                'Текущая дата': local_now_time,
                'Подача заявок': lot_table_list[16][1],
                'Отборочная стадия': lot_table_list[17][1],
                'Оценочная стадия': lot_table_list[18][1],
                'Закрыт': '',
                'Текущее событие': '',
                'Дата текущего события': '23:59',
                'Время текущего события': '',
                'Наименование': lot_table_list[2][1],
                'НМЦ': lot_table_list[6][1],
                'Новые файлы': ''
            }
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]
        else:
            events_of_current_transaction = {
                'Текущая дата': local_now_time,
                'Подача заявок': lot_table_list[16][1],
                'Отборочная стадия': lot_table_list[17][1],
                'Оценочная стадия': lot_table_list[18][1],
                'Закрыт': '',
                'Текущее событие': '',
                'Дата текущего события': '23:59',
                'Время текущего события': '',
                'Наименование': lot_table_list[2][1],
                'НМЦ': lot_table_list[6][1],
                'Новые файлы': ''
            }
            actual_status = lot_table_list[0][0].split("(")
            actual_status = actual_status[1][:-1]

        match = re.search(r'\d{2}.\d{2}.\d{4} \d{2}:\d{2}', events_of_current_transaction['Отборочная стадия'])
        events_of_current_transaction['Отборочная стадия'] = datetime.datetime.strptime(match.group(), "%d.%m.%Y %H:%M")
        match = re.search(r'\d{2}.\d{2}.\d{4} \d{2}:\d{2}', events_of_current_transaction['Подача заявок'])
        events_of_current_transaction['Подача заявок'] = datetime.datetime.strptime(match.group(), "%d.%m.%Y %H:%M")
        events_of_current_transaction['Оценочная стадия'] = datetime.datetime.strptime(
            events_of_current_transaction['Оценочная стадия'], "%d.%m.%Y %H:%M")

        local_now_time = datetime.datetime.strptime(
            local_now_time, "%d.%m.%Y %H:%M")

        if local_now_time < events_of_current_transaction['Подача заявок']:

            events_of_current_transaction['Текущее событие'] = 'Подача заявок'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Подача заявок']

        elif local_now_time < events_of_current_transaction['Отборочная стадия']:

            events_of_current_transaction['Текущее событие'] = 'Отборочная стадия'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Отборочная стадия']

        elif events_of_current_transaction['Закрыт'] == '(ЗАКРЫТ)':

            events_of_current_transaction['Текущее событие'] = 'Оценочная стадия(ЗАКРЫТ)'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Оценочная стадия']

        else:
            events_of_current_transaction['Текущее событие'] = 'Оценочная стадия'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Оценочная стадия']
    # TODO удалить эту ересь, когда гениальные авторы фабриканта поставят актуальную дату
    #     if 'id=21642' in order_url:
    #         events_of_current_transaction['Текущее событие'] = 'Подача заявок'
    #         events_of_current_transaction['Дата текущего события'] = \
    #             datetime.datetime.now().replace(microsecond=0) + datetime.timedelta(days=1)
        if 'Идёт приём заявок' not in actual_status:
            events_of_current_transaction['Текущее событие'] = events_of_current_transaction[
                                                                   'Текущее событие'] + '(' + actual_status + ')'

        events_of_current_transaction['Подача заявок'] = str(events_of_current_transaction['Подача заявок'])
        events_of_current_transaction['Отборочная стадия'] = str(events_of_current_transaction['Отборочная стадия'])
        events_of_current_transaction['Оценочная стадия'] = str(events_of_current_transaction['Оценочная стадия'])
        events_of_current_transaction['Дата текущего события'] = str(events_of_current_transaction['Дата текущего события'])
        return events_of_current_transaction
    elif 'rosatom' in order_url:
        lot_dates_url, lot_table_list, file_urls_list = get_lot_table_with_urls(order_url, okan_id)
        events_of_current_transaction = {
            'Текущая дата': local_now_time,
            'Подача заявок': local_now_time,
            'Отборочная стадия': local_now_time,
            'Оценочная стадия': local_now_time,
            'Закрыт': '',
            'Текущее событие': '',
            'Дата текущего события': '23:59',
            'Время текущего события': '',
            'Наименование': lot_table_list[1][1],
            'НМЦ': lot_table_list[1][2],
            'Новые файлы': file_urls_list
        }

        if type(lot_dates_url) == bool:
            events_of_current_transaction['Текущее событие'] = 'Некорректо указан url'
            return events_of_current_transaction

        data_list = get_data_table(lot_dates_url)
        # =================================================================================================================#
        # Право заключения договора на
        # #
        # Право заключения договора на
        # ---------------------------------------------------------------------------------------------------------------
        # 1. Подача заявок
        # Дата и время окончания подачи предложений OR
        # Дата и время продления срока подачи предложений
        # ---------------------------------------------------------------------------------------------------------------
        # 2. Отборочная стадия
        # Дата рассмотрения предложений
        # Измененная дата рассмотрения предложений
        # ---------------------------------------------------------------------------------------------------------------
        # 3. Оценочная стадия
        # Дата подведения итогов
        # Измененная дата подведения итогов
        # ---------------------------------------------------------------------------------------------------------------
        # 4.Закрыт (добавлять "ДА" в текущее событе в скобках, если закрыт)
        # Да
        # Нет
        # ---------------------------------------------------------------------------------------------------------------
        # =================================================================================================================#
        for sublist in data_list:
            sublist[1] = sublist[1].replace(u'\xa0', u'')

            if len(sublist[1]) < 11:
                sublist[1] = sublist[1] + ' 23:59'

            if 'Дата и время продления срока подачи' in sublist[0]:
                events_of_current_transaction['Подача заявок'] = sublist[1]
            elif 'Дата и время окончания подачи' in sublist[0]:
                events_of_current_transaction['Подача заявок'] = sublist[1]

            if 'Измененная дата рассмотрения' in sublist[0]:
                events_of_current_transaction['Отборочная стадия'] = sublist[1]
            elif 'Дата рассмотрения' in sublist[0]:
                events_of_current_transaction['Отборочная стадия'] = sublist[1]

            if 'Измененная дата подведения итогов' in sublist[0]:
                events_of_current_transaction['Оценочная стадия'] = sublist[1]
            elif 'Дата подведения итогов' in sublist[0]:
                events_of_current_transaction['Оценочная стадия'] = sublist[1]

            if 'Закрыт' in sublist[0] and 'Да' == sublist[1]:
                events_of_current_transaction['Закрыт'] = '(ЗАКРЫТ)'

        events_of_current_transaction['Подача заявок'] = datetime.datetime.strptime(str(
            events_of_current_transaction['Подача заявок']), "%d.%m.%Y %H:%M")
        events_of_current_transaction['Отборочная стадия'] = datetime.datetime.strptime(
            events_of_current_transaction['Отборочная стадия'], "%d.%m.%Y %H:%M")
        events_of_current_transaction['Оценочная стадия'] = datetime.datetime.strptime(
            events_of_current_transaction['Оценочная стадия'], "%d.%m.%Y %H:%M")
        local_now_time = datetime.datetime.strptime(
            local_now_time, "%d.%m.%Y %H:%M")

        if local_now_time < events_of_current_transaction['Подача заявок']:

            events_of_current_transaction['Текущее событие'] = 'Подача заявок'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Подача заявок']

        elif local_now_time < events_of_current_transaction['Отборочная стадия']:

            events_of_current_transaction['Текущее событие'] = 'Отборочная стадия'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Отборочная стадия']

        elif events_of_current_transaction['Закрыт'] == '(ЗАКРЫТ)':

            events_of_current_transaction['Текущее событие'] = 'Оценочная стадия(ЗАКРЫТ)'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Оценочная стадия']

        else:
            events_of_current_transaction['Текущее событие'] = 'Оценочная стадия'
            events_of_current_transaction['Дата текущего события'] = events_of_current_transaction['Оценочная стадия']

        if 'Приостановлен' in lot_table_list[1][3]:
            events_of_current_transaction['Текущее событие'] = events_of_current_transaction[
                                                                   'Текущее событие'] + '(Приостановлен)'

        events_of_current_transaction['Подача заявок'] = str(events_of_current_transaction['Подача заявок'])
        events_of_current_transaction['Отборочная стадия'] = str(events_of_current_transaction['Отборочная стадия'])
        events_of_current_transaction['Оценочная стадия'] = str(events_of_current_transaction['Оценочная стадия'])
        events_of_current_transaction['Дата текущего события'] = str(
            events_of_current_transaction['Дата текущего события'])
        return events_of_current_transaction


def normilise_time(time):
    time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")

    if time.hour == 23 and time.minute == 59:
        time = time.strftime("%d.%m.%Y")
        time_exact = ''
    else:
        time_exact = time.strftime("%H:%M")
        time = time.strftime("%d.%m.%Y")
    return time, time_exact


def backup_():
    # creating csv 'backup' with actual data
    df_backup = pd.DataFrame(list_of_lists)
    backup_name = config.BACKUP_WAY + datetime.datetime.now().strftime("%d-%m-%Y-%H-%M") \
                  + '.csv'
    df_backup.to_csv(backup_name, index=False, header=False, sep=';', encoding='UTF-8') \
        # removing old data backup
    backup_list = os.listdir(config.BACKUP_WAY)
    data_backup = datetime.datetime.now() - datetime.timedelta(days=7)
    # data_backup = data_backup.strftime("%d-%m-%Y-%H-%M")
    for i in range(0, len(backup_list)):
        compare_string = backup_list[i].split("_")
        compare_date = compare_string[4].split('.')
        compare_date = datetime.datetime.strptime(compare_date[0], "%d-%m-%Y-%H-%M")
        if compare_date < data_backup:
            backup_remove_name = config.BACKUP_WAY + backup_list[i]
            os.remove(backup_remove_name)


def sort_gs_table(list_of_lists):
    sequence_of_events = {
        'Подача заявок': 1,
        'Подача заявок(Ожидает решения организатора)': 1,
        'Подача заявок(Приостановлен)': 1,
        'Отборочная стадия': 2,
        'Отборочная стадия(Приостановлен)': 2,
        'Отборочная стадия(Ожидает решения организатора)': 2,
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

    del list_of_lists[0]

    # backup_()

    # sorty by 0 colmn
    s_list_of_lists = sorted(list_of_lists, key=lambda x: x[0])
    del list_of_lists
    sort_list_to_return = []
    list_of_lists = []
    s_point_start = s_list_of_lists[0][0]
    for j in range(0, len(s_list_of_lists)):
        # if s_point_start == 'А':
        if s_point_start == s_list_of_lists[j][0]:
            list_of_lists.append(s_list_of_lists[j])
        elif s_point_start == 'А':
            for i in range(0, len(list_of_lists)):
                progress = (1 - (len(list_of_lists) - i) / len(list_of_lists)) * 100
                progress = str(progress.__round__()) + '%'
                print(progress)
                del progress
                # parsing ulr, if exists
                if len(list_of_lists[i][16]) != 0:
                    okan_id = list_of_lists[i][1]
                    order_url = list_of_lists[i][16]
                    # order_url = 'http://zakupki.rosatomru/170113053603'
                    events_of_current_transaction = get_info_of_current_transaction(order_url, okan_id, local_now_time)
                    list_of_lists[i][3] = events_of_current_transaction['НМЦ']
                    list_of_lists[i][4] = events_of_current_transaction['Наименование']
                    list_of_lists[i][7] = events_of_current_transaction['Текущее событие']
                    list_of_lists[i][8] = events_of_current_transaction['Дата текущего события']
                    list_of_lists[i][9] = events_of_current_transaction['Время текущего события']
                    list_of_lists[i][10] = events_of_current_transaction['Подача заявок']
                    list_of_lists[i][11] = events_of_current_transaction['Отборочная стадия']
                    list_of_lists[i][12] = events_of_current_transaction['Оценочная стадия']
                    list_of_lists[i][6] = events_of_current_transaction['Новые файлы']
                # check all events
                list_of_lists[i][23] = int(sequence_of_events[list_of_lists[i][7]])
            # sort by number of event
            list_of_list_sort = sorted(list_of_lists, key=lambda x: x[23])
            list_of_lists = []
            sort_list = []
            sort_list_final = []
            point_start = list_of_list_sort[0][23]
            # sort by date for each event
            for i in range(0, len(list_of_list_sort)):
                if point_start == list_of_list_sort[i][23]:
                    sort_list.append(list_of_list_sort[i])
                else:
                    # даты есть только для 1.2.4 событий
                    if point_start < 3 or point_start is 4:
                        sort_list_final = sort_list_final + sorted(sort_list,
                                                                   key=lambda x: datetime.datetime.strptime(x[8],
                                                                                                            "%Y-%m-%d %H:%M:%S"))
                    else:
                        sort_list_final = sort_list_final + sort_list
                    del sort_list
                    sort_list = []
                    sort_list.append(list_of_list_sort[i])
                    point_start = list_of_list_sort[i][23]
            if point_start < 3 or point_start is 4:
                sort_list_final = sort_list_final + sorted(sort_list,
                                                           key=lambda x: datetime.datetime.strptime(x[8],
                                                                                                    "%Y-%m-%d %H:%M:%S"))
            else:
                sort_list_final = sort_list_final + sort_list
            del sort_list, point_start
            for i in range(0, len(sort_list_final)):
                if sort_list_final[i][23] < 3 or sort_list_final[i][23] is 4:
                    if len(sort_list_final[i][8]) > 10:
                        sort_list_final[i][8], sort_list_final[i][9] = normilise_time(sort_list_final[i][8])
                    if len(sort_list_final[i][10]) > 10:
                        sort_list_final[i][10], x = normilise_time(sort_list_final[i][10])
                    if len(sort_list_final[i][11]) > 10:
                        sort_list_final[i][11], x = normilise_time(sort_list_final[i][11])
                    if len(sort_list_final[i][12]) > 10:
                        sort_list_final[i][12], x = normilise_time(sort_list_final[i][12])
            sort_list_to_return = sort_list_final
            # del sort_list_final, sort_list
            # s_point_start = s_list_of_lists[j][0]
            break
            # sort_list_to_return = sort_list_to_return + list_of_lists
            # list_of_lists = []
            # s_point_start = s_list_of_lists[j][0]
    sort_list_to_return = sort_list_to_return + s_list_of_lists[j:]
    return sort_list_to_return
# =====================================================================================================================
#  working with goolge spreadsheets

if __name__ == '__main__':
    local_now_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    gs_worksheet = GSWorksheet(config.SPREADSHEET_URL, config.GOOGLE_ENGINE_TOKEN_WAY)
    worksheet = gs_worksheet.worksheet
    list_of_lists = worksheet.get_all_values()
    list_for_gs_update = sort_gs_table(list_of_lists)
    print('updating GS...')
    for i in range(0, len(list_for_gs_update)):
        j = str(i + 2)
        cell_list = worksheet.range('A' + j + ':V' + j)
        k = 0
        for cell in cell_list:
            cell.value = list_for_gs_update[i][k]
            k+=1
        worksheet.update_cells(cell_list)
    print('completed')
