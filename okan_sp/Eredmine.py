# !/usr/bin/env python3
# -*- coding: UTF-8 -*-


import requests
import xmltodict
import time
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import datetime
import config


# class returns googlesheet object with initial parameters(general gs url, local gs token *.json object, key of gs)
class GSWorksheet:
    def recursion_auth(self):
        credentials = self.credentials
        try:
            gs = gspread.authorize(credentials)
            return gs
        except TimeoutError:
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

    def __init__(self, scope, credentials_path, gs_key):
        self.gs_key = gs_key
        self.scope = scope
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_path,
                                                                            self.scope)
        self.gs = self.recursion_auth()
        self.gsh_ok_sp = self.recursion_open_by_key()


# class that returns different parameters of issues
class RedmineManager:
    def recursion_req(self, url):
        try:
            response_ = requests.get(url, auth=(self.LOGIN, self.KEY)).content.decode('utf-8')
            return response_
        except TimeoutError:
            time.sleep(1)
            print('Oops, self.recursion_req()')
            response_ = self.recursion_req(url)
            return response_
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            print('Oops, self.recursion_req()')
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
        print(return_dict['tracker'])
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

    def get_contacts(self):
        url = 'http://easy.okan.su/easy_contacts.xml?offset=0&limit=100'
        response_ = self.recursion_req(url)
        response_dict_ = xmltodict.parse(response_)
        return response_dict_

    def __init__(self, login, key):
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
        self.trackers_id = self.get_trackers_list()
        self.projects_id = self.get_project_list()
        self.contacts = self.get_contacts()
        # print(1)


# update sp_gs
def update_sp_gs(redmine_object, sp_list, worksheet_sp):
    for i in range(0, len(sp_list)):
        j = str(i + 2)
        cell_list = worksheet_sp.range(config.UPDATE_GS_START_POSITION + j + config.UPDATE_GS_STOP_POSITION + j)
        k = redmine_object.updated_types_sequence['Отгрузка в РФ']
        for cell in cell_list:
            cell.value = sp_list[i][k]
            k += 1
        worksheet_sp.update_cells(cell_list)


# method updates sp list with current issue info
def update_issue_info(redmine_object, list_of_dicts, list_of_lists):
    def to_date_(x):
        try:
            x['date'] = datetime.datetime.strptime(x['date'], "%Y-%m-%d").date()
        except TypeError:
            pass
    [to_date_(x) for x in list_of_dicts]
    for dict in list_of_dicts:
        date_position = redmine_object.updated_types_sequence[dict['tracker']]
        for i in range(0, list_of_lists.__len__()):
            list_of_lists[i][14] = \
                get_products_status(list_of_lists[i][redmine_object.updated_types_sequence['Код KKS']], list_of_dicts)
            if any(list_of_lists[i][redmine_object.updated_types_sequence['Код KKS']] in x for x in dict['products']):
                list_of_lists[i][date_position] = dict['date']


def get_products_status(item, list_of_dicts):
    one_dict = {
        'name': item,
        'date': '',
        'status': ''
    }
    for j in range(0, list_of_dicts.__len__()):
        if any(one_dict['name'] in x for x in list_of_dicts[j]['products']):
            if len(one_dict['status']) == 0:
                one_dict['date'] = list_of_dicts[j]['date']
                one_dict['status'] = list_of_dicts[j]['name']
            elif one_dict['date'] > list_of_dicts[j]['date']:
                one_dict['date'] = list_of_dicts[j]['date']
                one_dict['status'] = list_of_dicts[j]['name']
    return one_dict['status']


def main():
    gs_worksheet = GSWorksheet(config.SPREADSHEET_URL, config.GOOGLE_ENGINE_TOKEN_WAY, config.SPREADSHEET_KEY)
    worksheet_sp = gs_worksheet.gsh_ok_sp.worksheet('SP')
    sp_list = worksheet_sp.get_all_values()
    sp_list = sp_list[1:]
    unique_projects_list = list(set([sublist[0] for sublist in sp_list]))
    redmine_object = RedmineManager(config.LOGIN, config.KEY)
    some_list = []
    for i in range(0, unique_projects_list.__len__()):
        project_id = redmine_object.projects_id[unique_projects_list[i]]
        print(project_id)
        some_list.append(redmine_object.get_issues_list(project_id))
        list_of_dicts = [val for sublist in some_list for val in sublist]
    update_issue_info(redmine_object, list_of_dicts, sp_list)
    update_sp_gs(redmine_object, sp_list, worksheet_sp)
    print('jo')


# TODO make some processing indicators
if __name__ == '__main__':
    main()
