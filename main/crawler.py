import locale
import os
import pyodbc
import re
import time

import bs4
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from tqdm import tqdm

from main import logindata
from .settings import ENGINE_ADRESS, OUTPUT_DIR, SQL_CONNECTION_STR, TERMS_DICT, URL_DICT, bilanz_data, login_data, \
    search_data

locale.setlocale(locale.LC_ALL, '')


class Crawler:
    session_requests = None
    collection_dict = None

    def __init__(self):
        self.tables = Tables()
        self.session_requests = requests.Session()
        self.session_requests.post(URL_DICT['login'],
                                   data=login_data,
                                   headers=dict(referer=URL_DICT['login']))
        self.collection_dict = dict()

    def run_from_file(self, file: str, encoding: str = 'utf-8', rows: tuple = (0, 100)):
        index_start, index_end = rows

        try:
            df = pd.read_csv(filepath_or_buffer=file,
                             encoding=encoding)
        except (ValueError, UnicodeEncodeError):
            return

        progress_df = tqdm(iterable=df[index_start:index_end].iterrows(),
                           total=abs(index_end - index_start),
                           desc='::: Scraping companies :::')

        for idx, row in progress_df:
            self.process_company(company=row)

        if self.collection_dict:
            self.tables.upload_from_dict(collection_dict=self.collection_dict)
            self.tables.close_connection()

    def process_company(self, company):
        http_return = self._get_company_content(company=company)
        values = self._extract_company_values(soup=http_return)

        for term_name, group_dict in TERMS_DICT.items():
            if term_name.startswith('Basic'):
                term_values = [{key: value for key, value in values.items() if key in group_dict}]
            else:
                term_values = {key: value for key, value in values.items() if key in group_dict}
                term_values = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value
                               in term_values.items() for info in value]
            if term_name in self.collection_dict and term_values:
                self.collection_dict[term_name].extend(term_values)
            else:
                self.collection_dict[term_name] = term_values

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
            if not byaddress:
                print("No unique company by name")
                soup = self._get_company_content(company, byaddress=True)
            else:
                print("No unique company by address")
                if more_than_one_company:
                    print("More than one company")
                    tag = soup.find('a', string=re.compile(re.escape(company['Company Name'][0:39].lower()), re.I))
                    if tag:
                        result_profil = self.session_requests.post(URL_DICT['compass'] + tag['href'])
                        soup = BeautifulSoup(result_profil.text, 'html.parser')
                    else:
                        print("No company found")
                        return False
                else:
                    print("No company found")
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
                variablevalue = {}
                for child in variablevalue_children:
                    variablevalue[child.b.string] = list(child.stripped_strings)[1]
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
                    find_year = re.compile('[0-9/]*')
                    year_re = find_year.match(content)
                    if year_re:
                        year = year_re.group()
                        info['year'] = year
                        content = content.replace(year, '')
                    index_of_colon = content.find(':')
                    if index_of_colon not in [-1, 0]:
                        comment1 = content[:index_of_colon]
                        info['comment1'] = comment1
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
                        info['unit'] = content[:currency_re.start()]
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

    def update_tables(self):  # downloads all SQL-Tables, concatenates every temp table with the permanent one, and
        # deletes the
        DB_NAME = "compassdata"
        engine_address = ("mysql+pymysql://" + logindata.sql_config['user'] + ":" + logindata.sql_config['password'] +
                          "@" + logindata.sql_config['host'] + "/" + DB_NAME + "?charset=utf8")
        engine = create_engine(engine_address, encoding='utf-8')
        con = engine.connect()

        connStr = (
                r'user=' + logindata.sql_config['user'] + r';' +
                r'password=' + logindata.sql_config['password'] + r';' +
                r'server=' + logindata.sql_config['host'] + r';' +
                r'port=' + logindata.sql_config['port'] + r';' +
                r'database=' + logindata.sql_config['database'] + ';' +
                r'driver={Devart ODBC Driver for MySQL};'
        )

        cnxn = pyodbc.connect(connStr)  # set up a connection to the db
        crsr = cnxn.cursor()  # and construct a cursor

        crsr.execute("SHOW TABLES")
        names = [row[0] for row in crsr.fetchall()]
        temp_names = [name for name in names if name.endswith("Temp")]
        perm_names = [name for name in names if name not in temp_names]
        for table_name in perm_names:
            if table_name + "Temp" in temp_names:
                perm_table = pd.read_sql_table(table_name, con, index_col='index')
                temp_table = pd.read_sql_table(table_name + "Temp", con, index_col='index')
                new_table = pd.concat([perm_table, temp_table], ignore_index=True, sort=False)
                new_table = new_table.drop_duplicates().reset_index(drop=True)
                new_table.to_sql(name=table_name, con=con, if_exists='replace', chunksize=10000)
                temp_names.remove(table_name + 'Temp')
                crsr.execute("DROP TABLE " + table_name + "Temp")
                print("Appended " + table_name + "Temp to " + table_name)
        cnxn.commit()
        for table_name in temp_names:
            crsr.execute("RENAME TABLE " + table_name + " TO " + table_name[:-4])
            print("Renamed " + table_name + " to " + table_name[:-4])
        cnxn.commit()
        crsr.close()
        cnxn.close()
        con.close()


class Tables:
    def __init__(self):
        self.connection = create_engine(ENGINE_ADRESS, encoding='utf-8').connect()
        self.sql_connection = pyodbc.connect(SQL_CONNECTION_STR)
        self.db_cursor = self.sql_connection.cursor()

    @timer
    def upload_from_dict(self, collection_dict: dict, to_file: bool = False):
        for table_name, data in collection_dict.items():
            self.commit(table_name=table_name + 'temp',
                        data=pd.DataFrame(data),
                        filename=table_name + '.csv' if to_file else None)

        self.update_tables()

    def update_tables(self):
        # todo: update_tables() should be redundant, since we only need to append newly
        # todo: scraped data and keep the format consistent
        for table_name in filter(lambda content: 'temp' in content, self.table_names):
            original_table = self.get(table_name=table_name.strip('temp'))
            temporary_table = self.get(table_name=table_name)

            concat_tables = pd.concat([original_table, temporary_table],
                                      ignore_index=True,
                                      sort=False)
            concat_tables.drop_duplicates(inplace=True)

            self.commit(table_name=table_name.strip('temp'),
                        data=concat_tables.reset_index(drop=True),
                        how='replace')
            self.db_cursor.execute('DROP TABLE ' + table_name)
        self.sql_connection.commit()

    def get(self, table_name: str):
        return pd.read_sql(table_name,
                           self.connection,
                           index_col='index')

    def commit(self, table_name: str, data: pd.DataFrame,
               how: str = 'append',
               filename: str = None):
        data.to_sql(name=table_name,
                    con=self.sql_connection,
                    if_exists=how,
                    chunksize=10000)

        if filename:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            data.to_csv(path_or_buf=os.path.join(OUTPUT_DIR, filename),
                        encoding='utf-8')

    def sample(self, table_name: str, n_companies: int, sort_by: str, multi_index: list = None,
               n: int = 500):
        """Samples from a given table_name and returns a formatted DataFrame"""
        df = self.get(table_name=table_name)
        sampled_companies = np.random.choice(df.FN.unique(), n_companies)
        df_sampled_sorted = df[df.isin(sampled_companies)].sample(n=n).sort_values(sort_by)

        return df_sampled_sorted.set_index(multi_index) if multi_index else df_sampled_sorted

    def close_connection(self):
        self.db_cursor.close()
        self.sql_connection.close()
        self.connection.close()

    @property
    def table_names(self):
        self.db_cursor.execute('Show Tables')

        return list(row[0] for row in self.db_cursor.fetchall())


def timer(func):
    def wrapper(*args, **kwargs):
        timer_start = time.clock()
        result = func(*args, **kwargs)
        timer_end = time.clock()
        print(f'{func.__name__} executed in {timer_end-timer_start}')
        return result

    return wrapper
