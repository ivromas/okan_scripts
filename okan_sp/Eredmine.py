# !/usr/bin/env python3
# -*- coding: UTF-8 -*-


import requests
import xmltodict
import time
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import datetime
import sys
import config


# class with method of progress bar only :)
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


# class returns googlesheet object with initial parameters(general gs url, local gs token *.json object, key of gs)
class GSWorksheet(ProgressBar):
    def recursion_auth(self):
        credentials = self.credentials
        try:
            gs = gspread.authorize(credentials)
            return gs
        except TimeoutError:
            time.sleep(1)
            gs = self.recursion_auth()
            return gs
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            gs = self.recursion_auth()
            return gs

    def recursion_open_by_key(self):
        gs = self.gs
        try:
            gsh_ok_sp = gs.open_by_key(self.gs_key)
            return gsh_ok_sp
        except requests.exceptions.SSLError:
            time.sleep(5)
            gsh_ok_sp = self.recursion_open_by_key()
            return gsh_ok_sp

    # update sp_gs
    def update_sp_gs(self, redmine_object, sp_list):
        self.print_progress(0, len(sp_list), prefix='Updating GS:', suffix='Complete', bar_length=50)
        for i in range(0, len(sp_list)):
            j = str(i + 2)
            cell_list = \
                self.worksheet_sp.range(config.UPDATE_GS_START_POSITION + j + config.UPDATE_GS_STOP_POSITION + j)
            k = redmine_object.updated_types_sequence['Отгрузка в РФ']
            self.print_progress(i, len(sp_list), prefix='Updating GS:', suffix='Complete', bar_length=50)
            for cell in cell_list:
                cell.value = sp_list[i][k]
                k += 1
            self.worksheet_sp.update_cells(cell_list)
        self.print_progress(len(sp_list), len(sp_list), prefix='Updating GS:', suffix='Completed', bar_length=50)

    def __init__(self, scope, credentials_path, gs_key):
        self.gs_key = gs_key
        self.scope = scope
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path,
                                                                            self.scope)
        self.gs = self.recursion_auth()
        self.gsh_ok_sp = self.recursion_open_by_key()
        self.worksheet_sp = self.gsh_ok_sp.worksheet('SP')


# class that returns different parameters of issues
class RedmineManager(ProgressBar):

    def recursion_req(self, url):
        try:
            response_ = requests.get(url, auth=(self.LOGIN, self.KEY)).content.decode('utf-8')
            return response_
        except TimeoutError:
            time.sleep(1)
            response_ = self.recursion_req(url)
            return response_
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            response_ = self.recursion_req(url)
            return response_

    @staticmethod
    def get_issue_info(issue_dict):
        return_dict = {
            'date': issue_dict['due_date'],
            'name': issue_dict['subject'],
            'tracker': issue_dict['tracker']['@name'],
            'products': ''
        }
        assert return_dict['date'] is not None, 'Error in due date in issue %r ' % issue_dict['id']
        # print(return_dict['tracker'])
        # if return_dict['tracker'] == 'ВК' or return_dict['tracker'] == 'Инспекция':
        if issue_dict['custom_fields']['custom_field'].__len__() == 2:
                return_dict['products'] = issue_dict['custom_fields']['custom_field'][0]['value']['value']
        else:
            return_dict['products'] = issue_dict['custom_fields']['custom_field']['value']['value']
        if type(return_dict['products']) is str:
            x = return_dict['products']
            return_dict['products'] = []
            return_dict['products'].append(x)
        return return_dict

    # returns dict of projects name and projects id
    def get_project_list(self):
        url = 'http://easy.okan.su/projects.xml?&limit=100'
        response_ = self.recursion_req(url)
        response_dict_ = xmltodict.parse(response_)
        projects = response_dict_['projects']['project']
        projects_name = [data['name'] for data in projects]
        projects_id = [data['id'] for data in projects]
        project_main_info = dict(zip(projects_name, projects_id))
        return project_main_info

    # returns dict of trackers name and trackers id
    def get_trackers_list(self):
        url = 'http://easy.okan.su/trackers.xml?'
        response_ = self.recursion_req(url)
        response_dict_ = xmltodict.parse(response_)
        trackers = response_dict_['trackers']['tracker']
        trackers_name = [data['name'] for data in trackers]
        trackers_id = [data['id'] for data in trackers]
        trackers_main_info = dict(zip(trackers_name, trackers_id))
        return trackers_main_info

    # returns list of issues(full dict) of project, initialized by id
    def get_issues_list(self, project_id):
        url_general = 'http://easy.okan.su/issues.xml?project_id=' + project_id + \
                      '&offset=0&limit=100&tracker_id='
        necessary_trackers = self.updated_types
        list_of_issues = []
        for key in necessary_trackers:
            necessary_trackers[key] = self.trackers_id[key]
            url = url_general + necessary_trackers[key]
            response_ = self.recursion_req(url)
            response_dict_ = xmltodict.parse(response_)
            if int(response_dict_['issues']['@total_count']) is 0:
                pass
            elif int(response_dict_['issues']['@total_count']) is 1:
                list_of_issues.append(self.get_issue_info(response_dict_['issues']['issue']))
            else:
                for dict in response_dict_['issues']['issue']:
                    list_of_issues.append(self.get_issue_info(dict))
        return list_of_issues

    def get_issue_info_list(self):
        some_list = []
        self.print_progress(0, len(self.unique_projects_list),
                            prefix='Getting issue info:', suffix='Complete', bar_length=50)
        for i in range(0, self.unique_projects_list.__len__()):
            self.print_progress(i, len(self.unique_projects_list),
                                prefix='Getting issue info:', suffix='Complete', bar_length=50)
            project_id = self.projects_id[self.unique_projects_list[i]]
            some_list.append(self.get_issues_list(project_id))
            list_of_dicts = [val for sublist in some_list for val in sublist]
        self.print_progress(len(self.unique_projects_list), len(self.unique_projects_list),
                            prefix='Getting issue info:', suffix='Completed', bar_length=50)
        return list_of_dicts

    def update_issue_info(self):
        issue_info_list = self.get_issue_info_list()
        def to_date_(x):
            try:
                x['date'] = datetime.datetime.strptime(x['date'], "%Y-%m-%d").date()
            except TypeError:
                pass
        [to_date_(x) for x in issue_info_list]
        self.print_progress(0, len(issue_info_list), prefix='Updating GS info:', suffix='Complete', bar_length=50)
        j = 0
        for dict in issue_info_list:
            j += 1
            date_position = self.updated_types_sequence[dict['tracker']]
            self.print_progress(j, len(issue_info_list), prefix='Updating GS info:', suffix='Complete', bar_length=50)
            for i in range(0, self.sp_list.__len__()):
                self.get_products_status(self.sp_list[i][self.updated_types_sequence['Код KKS']], issue_info_list)
                self.sp_list[i][14] = self.one_dict['status']
                if any(self.sp_list[i][self.updated_types_sequence['Код KKS']] in x for x in
                       dict['products']):
                    self.sp_list[i][date_position] = dict['date']
        # self.print_progress(len(issue_info_list), len(issue_info_list),
        #                      prefix='Updating GS info:', suffix='Completed', bar_length=50)

    def get_products_status(self, item, list_of_dicts):
        self.one_dict['name'] = item
        for j in range(0, list_of_dicts.__len__()):
            if any(self.one_dict['name'] in x for x in list_of_dicts[j]['products']):
                if len(self.one_dict['status']) == 0:
                    self.one_dict['date'] = list_of_dicts[j]['date']
                    self.one_dict['status'] = list_of_dicts[j]['name']
                elif self.one_dict['date'] > list_of_dicts[j]['date']:
                    self.one_dict['date'] = list_of_dicts[j]['date']
                    self.one_dict['status'] = list_of_dicts[j]['name']

    def __init__(self, login, key, sp_list):
        self.KEY = key
        self.LOGIN = login
        self.updated_types = {
            'Отгрузка в РФ': '',
            'Отгрузка на АЭС': '',
            'Подписание ТОРГ-12': '',
            'ВК': '',
            'Платёж': '',
        }
        self.updated_types_sequence = {
            'Отгрузка в РФ': 9,
            'Отгрузка на АЭС': 10,
            'Подписание ТОРГ-12': 11,
            'ВК': 12,
            'Платёж': 13,
            'Код KKS': 3,
            'Текущий статус': 14
        }
        self.one_dict = {
            'name': '',
            'date': '',
            'status': ''
        }
        self.trackers_id = self.get_trackers_list()
        self.projects_id = self.get_project_list()
        self.sp_list = sp_list
        self.unique_projects_list = list(set([sublist[0] for sublist in sp_list]))


def main():

    gs_worksheet = GSWorksheet(config.SPREADSHEET_URL, config.GOOGLE_ENGINE_TOKEN_WAY, config.SPREADSHEET_KEY)
    sp_list = gs_worksheet.worksheet_sp.get_all_values()[1:]

    redmine_object = RedmineManager(config.LOGIN, config.KEY, sp_list)
    redmine_object.update_issue_info()

    gs_worksheet.update_sp_gs(redmine_object, sp_list)

    print('done')

if __name__ == '__main__':
    main()
