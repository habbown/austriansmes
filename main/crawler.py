import locale
import os
import pyodbc
import re
import time
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import types

import bs4
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from tqdm import tqdm

from .settings import (ENGINE_ADDRESS, OUTPUT_DIR, SQL_CONNECTION_STR, TERMS_DICT,
                       URL_DICT, bilanz_data, login_data, search_data)

locale.setlocale(locale.LC_ALL, '')


def timer(func):
    def wrapper(*args, **kwargs):
        timer_start = time.clock()
        result = func(*args, **kwargs)
        timer_end = time.clock()
        print(f'{func.__name__} executed in {timer_end-timer_start}')
        return result

    return wrapper


class Crawler:
    session_requests = None
    collection_dict = None

    def __init__(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self.session_requests = requests.Session()
        self.session_requests.post(URL_DICT['login'],
                                   data=login_data,
                                   headers=dict(referer=URL_DICT['login']))
        self.collection_dict = dict()
        self.logging_df = pd.DataFrame(columns=['non_unique_name',
                                                'non_unique_address',
                                                'multiple_hits',
                                                'no_hits',
                                                'error'])

    def get_content(self, file: str, encoding: str = 'utf-8', rows: tuple = (0, 100)):
        index_start, index_end = rows

        if file.lower().endswith('csv'):
            try:
                df = pd.read_csv(filepath_or_buffer=file,
                                 encoding=encoding)
            except (ValueError, UnicodeEncodeError):
                return
        elif file.lower().endswith(('xls', 'xlsx')):
            df = pd.read_excel(io=file)
        else:
            raise TypeError('Filetype not supported')

        progress_df = tqdm(iterable=df[index_start:index_end].iterrows(),
                           total=abs(index_end - index_start),
                           desc='::: Scraping companies :::')

        for idx, row in progress_df:
            try:
                self.process_company(company=row)
            except ValueError:
                self.logging_df.at[row['Company Name'][0:38], 'no_hits'] = True
                continue
            except AttributeError:
                self.logging_df.at[row['Company Name'][0:38], 'error'] = True

        if not self.logging_df.empty:
            self.logging_df.to_csv(path_or_buf=os.path.join(OUTPUT_DIR,
                                                            time.strftime("log_%Y%m%d_%H%M%S.csv")),
                                   encoding='utf-8',
                                   sep=';')

        return self.collection_dict

    def process_company(self, company):
        http_return = self._get_company_content(company=company)

        if not http_return:
            raise ValueError('No data found')

        values = self._extract_company_values(soup=http_return)

        for table_name, group_terms in TERMS_DICT.items():
            if isinstance(group_terms, str):
                term_values = [{'FN': values['FN'], 'name': key, 'value': value}
                               for key, value in values.items() if key.startswith(group_terms)]
            elif table_name.lower().startswith('basic'):
                term_values = [{key: value for key, value in values.items() if key in group_terms}]
            else:
                term_values = {key: value for key, value in values.items() if key in group_terms}
                term_values = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value
                               in term_values.items() for info in value]

            if table_name in self.collection_dict and term_values:
                self.collection_dict[table_name].extend(term_values)
            elif term_values:
                self.collection_dict[table_name] = term_values

    def _get_company_content(self, company, byaddress: bool = False):
        if not byaddress:
            search_data["suchwort"] = company['Company Name'][0:38]
            search_data["suchartid"] = 'F'
        else:
            search_data["suchwort"] = company['Address Line 1'][0:38]
            search_data["suchartid"] = 'A'

        result_profil = self.session_requests.post(URL_DICT['search'], data=search_data)

        soup = BeautifulSoup(result_profil.text, 'html.parser')

        more_than_one_company = soup.find('h2', attrs={'id': 'result_summary'})
        no_company = soup.find('span', attrs={'id': 'result_summary'})
        too_many_companies = soup.find('div', attrs={'class': 'message warning'})

        if more_than_one_company or no_company or too_many_companies:
            if byaddress:
                self.logging_df.at[company['Company Name'][0:38], 'non_unique_address'] = True
            else:
                self.logging_df.at[company['Company Name'][0:38], 'non_unique_name'] = True

            if more_than_one_company:
                self.logging_df.at[company['Company Name'][0:38], 'multiple_hits'] = True
                tag = soup.find('a', string=re.compile(re.escape(company['Company Name'].lower()), re.I))
                if tag:
                    result_profil = self.session_requests.post(URL_DICT['compass'] + tag['href'])
                    soup = BeautifulSoup(result_profil.text, 'html.parser')
                    return soup

            if not byaddress:
                soup = self._get_company_content(company, byaddress=True)
            else:
                return False
        return soup

    def _extract_company_values(self, soup):
        values = self._extract_values_from_profile(soup)

        form_list = soup.find_all('form', attrs={'method': 'post', 'action': 'Bilanz', 'target': '_bank'})
        for form in form_list:
            id_number = None
            onr_number = None
            if form.find('input', attrs={'name': 'onr', 'type': 'hidden'}):
                onr_number = form.find('input', attrs={'name': 'onr', 'type': 'hidden'})['value']
            if form.find('input', attrs={'name': 'id', 'type': 'hidden'}):
                id_number = form.find('input', attrs={'name': 'id', 'type': 'hidden'})['value']
            if id_number and onr_number:
                bilanz_data['onr'] = onr_number
                bilanz_data['id'] = id_number
                bilanz = self.session_requests.post(URL_DICT['bilanz'], data=bilanz_data)
                bilanz_soup = BeautifulSoup(bilanz.text, 'html.parser')
                values.update(self._extract_values_from_bilanz(bilanz_soup))

        return values

    def _extract_values_from_profile(self, soup):
        values = {}
        fn_box = soup.find('h2')
        fn = fn_box.text.strip()[3:]
        values['FN'] = fn
        if soup.find('h1', attrs={'class': 'geloescht'}):
            values['geloescht'] = soup.find('h1', attrs={'class': 'geloescht'}).string

        div = soup.find('div', attrs={'class': 'content'})

        div_children = [x for x in div.children if not isinstance(x, bs4.NavigableString) and x.name == 'div']
        # go through all possible pairs of variablename and variablevalue, depending on variablename do something
        #  with the field containing the variablevalues to convert it to reasonable output
        for child in div_children:
            variablename = child.find('div', attrs={'class': 'label'})
            variablevalue = child.find('div', attrs={'class': 'content'})
            variablename = ' '.join(list(variablename.stripped_strings))
            if variablename == 'Gewerbedaten':
                info = {}
                if variablevalue.a:
                    link = variablevalue.a['href']
                    info['link'] = link
                if variablevalue.string:
                    name = variablevalue.string
                    info['linktext'] = name
                variablevalue = [info]
            elif variablename in {'Ediktsdatei'}:
                info = {}
                for item in variablevalue.contents:
                    if item.name == 'a':
                        info['link'] = item['href']
                        info['linktext'] = str(item.string).strip()
                    elif isinstance(item, bs4.NavigableString):
                        info['comment'] = str(item).strip()
                variablevalue = [info]
            elif variablename in {'EU-Agrarförderungen'}:
                value = []
                period = None
                for child in variablevalue.children:
                    if child.name == 'p':
                        if child.stripped_strings != []:
                            period = list(child.stripped_strings)[0]
                    elif child.name == 'div':
                        if child.table:
                            for row in child.table.children:
                                if row.name == 'thead':
                                    names = row.find_all('th')
                                    names = [name.string for name in names]
                                elif row.name == 'tr':
                                    info = {}
                                    if period:
                                        info['period'] = period
                                    contents = row.find_all('td')
                                    contents = [list(content.stripped_strings)[0] for content in contents]
                                    info.update(dict(zip(names, contents)))
                                    value.append(info)
                    elif isinstance(child, bs4.NavigableString):
                        continue
                variablevalue = value
            elif variablename == 'OENACE 2008':
                if variablevalue.string:
                    variablevalue = [{'value': variablevalue.string, 'main': True}]
                else:
                    value = list(variablevalue.stripped_strings)
                    if variablevalue.b:
                        bolded = list(variablevalue.b.stripped_strings)[0]
                        value = [item for item in value if item != bolded]
                        value = [{'value': item, 'main': False} for item in value]
                        value.append({'value': bolded, 'main': True})
                    else:
                        value = [{'value': item, 'main': False} for item in value]
                    variablevalue = value
            elif variablename in {'Telefon', 'Fax'}:
                variablevalue = ', '.join(list(variablevalue.stripped_strings))
            elif variablename in {'Niederlassungen'}:
                tables = variablevalue.find_all('table')
                headings = variablevalue.find_all('h4')
                variablevalue = []
                if headings != []:
                    for header in headings:
                        header = list(header.stripped_strings)[0]
                        variablevalue.append({'comment': header})
                # each table contains one Niederlassung, every table can have rows on address, phone number, ...
                if tables != []:
                    for table in tables:
                        info = {}
                        for row in table.find_all('tr'):
                            if row.td.string:
                                info[row.th.string] = row.td.string
                            else:
                                info[row.th.string] = ' '.join(list(row.td.stripped_strings))
                        variablevalue.append(info)
            elif variablename in {'Historische Adressen', 'Historische Firmenwortlaute'}:
                variablevalues = variablevalue.find_all('p')
                if len(variablevalues) != 0:
                    variablevalue = []
                    for list_element in variablevalues:
                        list_element = '; '.join(list(list_element.stripped_strings))
                        variablevalue.append({'value': list_element})
                else:
                    variablevalue = [{'value': '; '.join(list(variablevalue.stripped_strings))}]
            elif variablename in {'Adresse', 'Postanschrift'}:
                variablevalue = '; '.join(list(variablevalue.stripped_strings))
            elif variablename in {'Wirtschaftlicher Eigentümer'}:
                variablevalue_children = [x for x in variablevalue.children if not isinstance(x, bs4.NavigableString)]
                variablevalue = []
                for child in variablevalue_children:
                    info = {}
                    name = None
                    comment = None
                    info['FN'] = fn
                    info['function'] = variablename
                    # in case of div, there's two span tags inside of which the
                    #  first contains the information and the second a link to a diagram
                    if child.name == 'div' and child.span:
                        if child.span.a or 'geb.' in child.text:
                            if child.span.a:
                                link = child.span.a['href']
                                info['link'] = link
                                name = child.span.a.string
                                info['name'] = name
                            if 'geb.' in child.text:
                                birthdate_index = child.text.find('geb.')
                                start_index = birthdate_index + 5
                                end_index = birthdate_index + 15
                                birthdate = child.text[start_index:end_index]
                                info['birthdate'] = birthdate
                        else:
                            continue
                    elif child.name == 'p':  # in case of a p tag, there's either information about a person or extra text
                        comment = ' '.join(list(child.stripped_strings))
                        info['comment'] = re.sub(r'\s+', ' ', comment).strip()
                        if child.a:
                            link = child.a['href']
                            info['link'] = link
                            name = child.a.string
                            info['name'] = name
                    elif child.stripped_strings == []:
                        continue
                    if name or comment:
                        variablevalue.append(info)
            elif variablename in {'Rechtstatsachen'}:
                variablevalue_children = variablevalue.find_all('p')
                variablevalue = []
                for child in variablevalue_children:
                    variablevalue.append({'number': child.b.string, 'text': list(child.stripped_strings)[1]})
            elif variablename in {'Firmeninformationen'}:
                value = []
                for item in variablevalue.find_all('li'):
                    info = {}
                    if item.a:
                        info['name'] = item.a.string
                        info['link'] = item.a['href']
                    value.append(info)
                variablevalue = value
            elif variablename in {'Ringbeteiligung', 'Börsennotiert', 'Gründungsprivilegierung'}:
                if variablevalue.find('span', attrs={'class': 'checked'}):
                    variablevalue = variablevalue.find('span', attrs={'class': 'checked'}).string
            elif variablename in {'Eigentümer', 'Management', 'Beteiligungen', 'Kontrollorgane'}:
                # those fields are not completely the same (explaining why the code isn't as nice as it could be), one of
                # these has nested p tags (explaining why we don't just go to through the children but through all p tags,
                # ignoring those which themselves contain p tags)
                if variablevalue.p:
                    variablevalue_children = [x for x in variablevalue.find_all('p') if
                                              not isinstance(x, bs4.NavigableString)]
                variablevalue = []
                type_of = None
                for child in variablevalue_children:
                    info = {}
                    name = None
                    info['FN'] = fn
                    info['function'] = variablename
                    if child.p:
                        continue
                    else:
                        if child.b:
                            type_of = child.b.string
                            child.b.decompose()
                            type_of.replace("\xc2\xa0", "")
                            type_of.replace("\xa0", "")
                            type_of = re.sub('\s+', ' ', type_of)
                            type_of = re.sub('^ | $', '', type_of)
                        if child.a:
                            if type_of:
                                info['type'] = type_of
                            link = child.a['href']
                            info['link'] = link
                            name = child.a.string
                            info['name'] = name
                            if 'geb.' in child.text:
                                birthdate_index = child.text.find('geb.')
                                start_index = birthdate_index + 5
                                end_index = birthdate_index + 15
                                birthdate = child.text[start_index:end_index]
                                info['birthdate'] = birthdate
                            if 'Anteil' in child.text:
                                p = re.compile('Anteil: ([^)]*)[)]')
                                info['anteil'] = p.search(str(child.text)).group(1)
                            if (child.find('span', attrs={'class': 'smalltext'}) and
                                    child.find('span', attrs={'class': 'smalltext'}).string):
                                comment1 = child.find('span', attrs={'class': 'smalltext'}).string
                                info['comment1'] = comment1
                            if child.text.strip()[0:5] != name[0:5] and child.text.strip()[0:5] != type_of[0:5]:
                                comment2 = child.text.strip()
                                comment2 = re.sub(r'\s+', ' ', comment2).strip()
                                info['comment2'] = comment2
                            if '(' in child.text and '(Anteil' not in child.text:
                                comment3_pattern = re.compile('[(]([\w ,]+)[)]')
                                comment3_re = comment3_pattern.search(str(child.text))
                                if comment3_re:
                                    info['comment3'] = comment3_re.group(1)
                            variablevalue.append(info)
                        elif child.stripped_strings and list(child.stripped_strings) != []:
                            if type_of:
                                info['type'] = type_of
                                if type_of in list(child.stripped_strings)[0]:
                                    continue
                            if '(' in list(child.stripped_strings)[0]:
                                parenthesis_open = list(child.stripped_strings)[0].find('(')
                                parenthesis_close = list(child.stripped_strings)[0].find(')')
                                comment = list(child.stripped_strings)[0][parenthesis_open + 1:parenthesis_close]
                                name = list(child.stripped_strings)[0][:parenthesis_open - 1]
                                info['name'] = name
                                info['comment'] = comment
                            else:
                                name = child.text
                                info['name'] = name
                            if type_of and type_of in name:  # this is ugly but we want to prevent that the same
                                # string is extracted as both the name and the type of a person, a better way to
                                # prevent this would be to only look for the b-tag outside of the name
                                continue
                            variablevalue.append(info)
                        else:
                            continue
            elif variablename in {'Tätigkeit lt. Recherche'}:
                variablevalue = ' '.join(variablevalue.stripped_strings)
            elif variablename in {'Kapital'}:
                kapital = variablevalue.stripped_strings
                variablevalue = []
                for content in kapital:
                    info = {}
                    info['FN'] = fn
                    info['name'] = variablename
                    currencysymbol = re.compile('[A-Z]{3}')
                    currency_re = currencysymbol.search(content)
                    currency = currency_re.group()
                    info['currency'] = currency
                    content = content.replace(currency, '')
                    value_pattern = re.compile('[0-9,.]+')
                    value_re = value_pattern.search(content)
                    value = locale.atof(value_re.group())
                    info['value'] = value
                    content = content.replace(value_re.group(), '')
                    content = content.strip()
                    if content != '':
                        info['comment'] = content
                    variablevalue.append(info)
            elif variablename in {'Jahresabschluss', 'Konzernabschluss'}:
                children = soup.find_all('form', attrs={'method': 'post', 'action': 'Bilanz', 'target': '_bank'})
                variablevalue = []
                for form in children:
                    info = {}
                    form_text = form.find('span', attrs={'class': 'spacing'})
                    if form_text:
                        info['text'] = form_text.string
                    form_comment = form.find('span', attrs={'class': 'badge'})
                    if form_comment:
                        info['comment'] = list(form_comment.stripped_strings)[0]
                    variablevalue.append(info)
            elif variablename in {'Gericht', 'UID'}:
                variablevalue = list(variablevalue.stripped_strings)[0]
                if ';' in variablevalue:
                    index = variablevalue.find(';')
                    variablevalue = variablevalue[:index]
            elif variablename in {'Bankverbindung', 'Internet-Adressen', 'E-Mail', 'Weitere Informationen'}:
                children = variablevalue.find_all('a')
                variablevalue = []
                for child in children:
                    link = child['href']
                    linktext = child.string
                    info = {'linktext': linktext, 'link': link}
                    variablevalue.append(info)
            elif variablename in {'Suchbegriff(e)'}:
                variablevalue = list(variablevalue.stripped_strings)
                variablevalue = [{'value': value} for value in variablevalue]
            elif variablename in {'Beschäftigte', 'Umsatz', 'EGT', 'Cashflow'}:
                variablevalues = variablevalue.stripped_strings
                variablevalue = []
                for content in variablevalues:
                    info = {}
                    info['FN'] = fn
                    info['name'] = variablename
                    find_year = re.compile('^[0-9/]+')
                    year_re = find_year.match(content)
                    if year_re:
                        year = year_re.group()
                        info['year'] = year
                        content = content.replace(year, '')
                    index_of_colon = content.find(':')
                    if index_of_colon not in [-1, 0]:
                        comment1 = content[:index_of_colon]
                        info['comment1'] = comment1.strip('() ')
                        content = content[index_of_colon + 1:]
                    elif index_of_colon == 0:
                        content = content.strip(':')
                    content = content.replace(re.compile(':? *').match(content).group(), '')
                    value_re = re.compile('-?[\d,.]+|keine').match(content)
                    if value_re:
                        value = value_re.group()
                        if value == 'keine':
                            value = 0
                        else:
                            value = locale.atof(value)
                        info['value'] = value
                        content = content.replace(value_re.group(), '')
                        content = content.lstrip()
                    currencysymbol = re.compile('[A-Z]{3}')
                    currency_re = currencysymbol.search(content)
                    if currency_re:
                        currency = currency_re.group()
                        info['currency'] = currency
                        info['unit'] = content[:currency_re.start()].strip()
                        if content[currency_re.end():].strip()[1:-1] != '':
                            info['comment2'] = content[currency_re.end():].strip()[1:-1]
                    variablevalue.append(info)
            elif variablename in {'Bankleitzahlen'}:
                variablevalue = list(variablevalue.stripped_strings)
                variablevalue = [{'value': value} for value in variablevalue]
            elif variablevalue.string:
                variablevalue = re.sub(r'\s+', ' ', variablevalue.string).strip()
            else:
                continue
            values[self.beautify(variablename)] = variablevalue

        if (soup.find('ul', attrs={'class': 'links'})
            and soup.find('ul', attrs={'class': 'links'}).find('li', attrs={'class': 'last'})).a:
            onr_re = re.compile('onr=(\d*)')
            onr = onr_re.search(soup.find('ul', attrs={'class': 'links'}).find('li', attrs={'class': 'last'}).a['href'])
            if onr:
                onr = onr.group(1)
                values['Compass-ID(ONR)'] = onr
        return values  # want to flatten out dictionary first and improve some minor errors (type for Eigentümer and so on)

    def beautify(self, string: str):
        # takes in a string, replaces commas by ; (so we  can export to csv), spaces by '.' and replace umlaute and ß
        string = string.replace('\n', ' ')
        string = ' '.join(string.split())
        string = string.translate(
            {ord('ä'): 'ae', ord('Ä'): 'Ae', ord('ö'): 'oe', ord('Ö'): 'Oe', ord('ü'): 'ue', ord('Ü'): 'Ue',
             ord('ß'): 'ss',
             ord(' '): '.', ord(';'): ','})
        return string
        # what about commatas for CSV-export (or escape by putting in quotes and replacing quotes (") in text (do these exist)
        # by double quotes (#)

    def _extract_values_from_table(self, table, prefix=[]):
        # takes in a table tag, a prefix (to prepend the variablenames with),
        #  and a dictionary it adds values to (is that good or
        # wouldn't it be better to just return a dictionary containing the values extracted from the table?)
        tr_list = table.children
        values = {}
        # if table.tbody:
        #    tr_list = table.tbody.children
        tr_list = [x for x in tr_list if not isinstance(x, bs4.NavigableString) and x.name == 'tr']
        title = ''
        if tr_list == []:
            return
        for tr in tr_list:
            # depending on the tr's (the lines of the table) attributes, do one of certain things; if it contains the
            # title of a subtable add it to the prefix, if it contains values, put them into the table, ...
            if ('class', ['title', 'main', 'indent']) in tr.attrs.items() or (
                    'class', ['title']) in tr.attrs.items() or (
                    'class', ['title', 'main']) in tr.attrs.items():
                if not tr.find('td', attrs={'class': 'value'}).string:
                    title = self.beautify(tr.find('td', attrs={'class': 'text'}).string)
                else:
                    variablename = '_'.join(prefix) + '_' + (tr.find('td', attrs={'class': 'text'}).string)
                    value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
                    values[variablename] = value
            elif ('class', ['level-group']) in tr.attrs.items():
                table_list = tr.td.children
                table_list = [x for x in table_list if not isinstance(x, bs4.NavigableString) and x.name == 'table']
                for table_element in table_list:
                    values.update(self._extract_values_from_table(table_element, prefix + [title]))
            elif ('class', ['indent']) in tr.attrs.items():
                if tr.find('td', attrs={'class': 'text single'}) != None:
                    variablename = '_'.join(prefix) + '_' + self.beautify(
                        tr.find('td', attrs={'class': 'text single'}).string)
                elif tr.find('th', attrs={'class': 'text'}) != None:
                    variablename = '_'.join(prefix) + '_' + self.beautify(tr.find('th', attrs={'class': 'text'}).string)
                if tr.find('td', attrs={'class': 'value'}) != None:
                    value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
                elif tr.find('th', attrs={'class': 'value'}) != None:
                    value = locale.atof(tr.find('th', attrs={'class': 'value'}).string)
                values[variablename] = value
            elif ('class', ['sum']) in tr.attrs.items():
                variablename = '_'.join(prefix) + '_' + title + '_' + self.beautify(
                    tr.find('td', attrs={'class': 'text'}).string)
                value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
                values[variablename] = value
            elif len(tr.attrs.items()) == 0 or ('class', ['']) in tr.attrs.items():
                if tr.find(attrs={'class': 'text'}).string:
                    variablename = '_'.join(prefix) + '_' + self.beautify(tr.find(attrs={'class': 'text'}).string)
                elif tr.find(attrs={'class': 'textsingle'}).string:
                    variablename = '_'.join(prefix) + '_' + self.beautify(
                        tr.find(attrs={'class': 'text single'}).string)
                if tr.find(attrs={'class': 'value'}) and tr.find(attrs={'class': 'value'}).string:
                    value = locale.atof(tr.find(attrs={'class': 'value'}).string)
                    values[variablename] = value
        return values

    def _extract_values_from_div(self, div, prefix=[]):
        values = {}
        title = ''
        div_children = div.children
        div_children = [x for x in div_children if not isinstance(x, bs4.NavigableString)]
        for child in div_children:
            if child.name == 'h3':
                title = self.beautify(child.string)
            elif child.name == 'div':
                values.update(self._extract_values_from_div(child, prefix + [title]))
            elif child.name == 'table':
                if ('class', ['header']) in child.attrs.items():
                    continue
                elif ('class', ['bilanz-footer']) in child.attrs.items():
                    values.update(self._extract_values_from_table(child, prefix + [title]))
                elif child.attrs == {}:
                    values.update(self._extract_values_from_table(child, prefix + [title]))
        return values

    def _extract_values_from_bilanz(self, soup):
        values = {}
        firmenname = soup.find('h1')
        firmenname = firmenname.string
        values["Firmenname"] = firmenname

        fn = soup.find('h2')
        fn = fn.string[3:]
        values["FN"] = fn

        title = self.beautify(soup.h3.text)

        bilanzinfo = soup.find(attrs={'class': 'bilanz-info'})
        for child in bilanzinfo.find_all('div'):
            name = child.find(attrs={'class': 'title'}).string
            index = name.find(':')
            name = name[:index]
            name = self.beautify(name)
            values[title + '_' + name] = child.find(attrs={'class': 'content'}).string

        bilanz = soup.find('div', attrs={'class': 'bilanz'})
        if bilanz:
            values.update(self._extract_values_from_div(bilanz))

        guvrechnung = soup.find('div', attrs={'class': 'gewinn-verlust'})
        if guvrechnung:
            values.update(self._extract_values_from_div(guvrechnung))

        infotext = soup.find_all('div', attrs={'class', 'infotext'})
        if len(infotext) > 0:
            infotext = soup.find('div', attrs={'class', 'infotext'}).p.string
            infotext = re.sub(r'\s+', ' ', infotext).strip()
            values[title + '_' + 'infotext'] = infotext
        return values


class DBTable:
    _CHUNKSIZE = int(1e4)

    def __init__(self):
        self.connection = None
        self.sql_connection = None
        self.db_cursor = None
        self.open_connection()

    def push_from_source(self, source: dict, to_file: bool = False):
        print('Pushing data to server...\n')

        for table_key, data in source.items():
            data_formatted = self.get_formatted(table_name=table_key,
                                                data=data)
            self.update_database(table_name=table_key,
                                 df_new=data_formatted)

            if to_file:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                data.to_csv(path_or_buf=os.path.join(OUTPUT_DIR, table_key + '.csv'),
                            encoding='utf-8')

        if 'BilanzData' in source:
            self.update_relational_tables()

        print('...Done')

    def update_relational_tables(self):
        print('Updating relational tables...\n')
        df_guv_compact = self.get(table_name='GuVData')[['FN', 'year']].drop_duplicates()
        df_bilanz_compact = self.get(table_name='BilanzData')[['FN', 'date']].drop_duplicates()
        df_bilanz_compact['year'] = df_bilanz_compact.date.str[-4:]

        df_bilanz_info = df_bilanz_compact[['FN', 'year']].merge(df_guv_compact,
                                                                 how='outer',
                                                                 indicator=True)
        df_bilanz_info = df_bilanz_info.assign(shortened=False)
        df_bilanz_info.loc[df_bilanz_info._merge == 'left_only', 'shortened'] = True

        self.commit(table_name='BilanzInfo',
                    df=df_bilanz_info[['FN', 'year', 'shortened']])

    def update_database(self, table_name: str, df_new: pd.DataFrame):
        print(f'Processing table {table_name}...')

        try:
            original_table = self.get(table_name=table_name)
        except ProgrammingError:
            print(f'Table {table_name} is not yet present on server, pushing temp data directly...')
            self.commit(table_name=table_name, df=df_new)
            return

        concat_table = pd.concat(objs=[original_table, df_new],
                                 ignore_index=True,
                                 sort=False)
        concat_table.drop_duplicates(inplace=True)
        concat_table.reset_index(inplace=True,
                                 drop=True)

        self.commit(table_name=table_name,
                    df=concat_table,
                    how='replace')
        self.sql_connection.commit()

    def get(self, table_name: str):
        return pd.read_sql(table_name,
                           self.connection)

    def commit(self, table_name: str, df: pd.DataFrame,
               how: str = 'append'):
        dtype_mappings = DBTable.get_df_column_mappings(df=df)
        df.to_sql(name=table_name,
                  con=self.connection,
                  if_exists=how,
                  index=False,
                  dtype=dtype_mappings,
                  chunksize=self._CHUNKSIZE)

    @staticmethod
    def get_formatted(table_name: str, data: list):
        df = pd.DataFrame(data)

        if table_name.lower().startswith('bilanz'):
            df = df.assign(date=None,
                           position=None)
            df.date = df.name.str.extract('([\d]{2}.[\d]{2}.[\d]{4})')
            df.name = df.name.str.extract('[\d]{2}.[\d]{2}.[\d]{4}_(.*)')
            df.name = df.name.str.lstrip('_')
            # filter by aktiva/passiva indices
            aktiva_index = df.name.str.contains('Aktiva')
            passiva_index = df.name.str.contains('Passiva')
            # set new position column entries by loc filter
            df.loc[aktiva_index, 'position'] = 'Aktiva'
            df.loc[aktiva_index, 'name'] = df.name.str.lstrip('Aktiva')
            df.loc[passiva_index, 'position'] = 'Passiva'
            df.loc[passiva_index, 'name'] = df.name.str.lstrip('Passiva')
            df.name = df.name.str.lstrip('_')

            df.dropna(subset={'position'},
                      inplace=True)

        elif table_name.lower().startswith('guv'):
            df = df.assign(year=None,
                           is_revenue=False)
            df.year = df.name.str.extract('([\d{4}]+)')
            df.name = df.name.str.extract('\d{4}_(.*)')
            df.name = df.name.str.lstrip('_')
            df.name = df.name.str.capitalize()

            for k, group in df.groupby(by=['FN', 'year']):
                revenue_hits = group.name.str.lower().str.contains('umsatz')

                if revenue_hits.any():
                    revenue_index = group[revenue_hits].iloc[0].name
                else:
                    revenue_index = group.value.iloc[:25].idxmax()

                df.at[revenue_index, 'is_revenue'] = True

        elif table_name.lower().startswith('search'):
            df = df.assign(code=None)

            if df.type.str.contains('OENACE.2008').any():
                oenace_index = df.type == 'OENACE.2008'
                split_content = df.loc[oenace_index, 'value'].str.split('(')
                codes = split_content.apply(lambda x: x[-1]).str.rstrip(')')
                values = split_content.apply(lambda x: '('.join(part for part in x[:-1]))

                df.loc[oenace_index, 'code'] = codes
                df.loc[oenace_index, 'value'] = values

        return df

    def sample(self, table_name: str, n_companies: int, sort_by: str, multi_index: list = None,
               n: int = 500):
        """Samples from a given table_name and returns a formatted DataFrame"""
        df = self.get(table_name=table_name)
        sampled_companies = np.random.choice(df.FN.unique(), n_companies)
        df_sampled_sorted = df[df.isin(sampled_companies)].sample(n=n).sort_values(sort_by)

        return df_sampled_sorted.set_index(multi_index) if multi_index else df_sampled_sorted

    @staticmethod
    def get_df_column_mappings(df: pd.DataFrame):
        return {k: types.VARCHAR(df[k].str.len().max()) for k, v in df.dtypes.items() if v == 'object'}

    def close_connection(self):
        self.db_cursor.close()
        self.sql_connection.close()
        self.connection.close()

    def open_connection(self):
        self.connection = create_engine(ENGINE_ADDRESS, encoding='utf-8').connect()
        self.sql_connection = pyodbc.connect(SQL_CONNECTION_STR)
        self.db_cursor = self.sql_connection.cursor()

    @staticmethod
    def bulk_push_data(df: pd.DataFrame, model):
        model.objects.bulk_create(model(**values) for values in df.to_dict('records'))
