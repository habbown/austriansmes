import bs4
from bs4 import BeautifulSoup
import locale
import pprint
import re
import unicodedata

locale.setlocale(locale.LC_ALL, '')


def extract_values_from_profile(soup):
    values = {}
    fn_box = soup.find('h2')
    fn = fn_box.text.strip()
    values['FN'] = fn

    div = soup.find('div', attrs={'class': 'content'})

    div_children = [x for x in div.children if not isinstance(x, bs4.NavigableString) and x.name == 'div']
    for child in div_children:
        variablename = child.find('div', attrs={'class': 'label'})
        variablevalue = child.find('div', attrs={'class': 'content'})
        variablename = ' '.join(list(variablename.stripped_strings))
        if variablename == 'OENACE 2008':
            if variablevalue.string:
                print(variablevalue.string)
            print(list(variablevalue.stripped_strings))
        if variablevalue.string:
            variablevalue = variablevalue.string
        elif variablename in {'Telefon', 'Fax'}:
            variablevalue = list(variablevalue.stripped_strings)[0]
        elif variablename in {'Adresse', 'Postanschrift', 'Historische Adressen', 'Historische Firmenwortlaute'}:
            variablevalues = variablevalue.find_all('p')
            if len(variablevalues) != 0:
                variablevalue = {}
                counter = 0
                for list_element in variablevalues:
                    list_element = '; '.join(list(list_element.stripped_strings))
                    variablevalue[str(counter)] = list_element
                    counter += 1
            else:
                variablevalue = '; '.join(list(variablevalue.stripped_strings))
        elif variablename in {'Wirtschaftlicher Eigentümer', 'Eigentümer', 'Management', 'Beteiligungen'}:
            variablevalue_children = [x for x in variablevalue.find_all('p') if not isinstance(x, bs4.NavigableString)]
            variablevalue = {}
            counter = 0
            type_of = None
            for child in variablevalue_children:
                if child.p:
                    continue
                elif child.b != None:
                    type_of = unicodedata.normalize('NFKD', child.b.text)
                elif child.a != None:
                    variablevalue[str(counter)] = {}
                    if type_of:
                        variablevalue[str(counter)]['type'] = unicodedata.normalize('NFKD', type_of)
                    link = child.a['href']
                    variablevalue[str(counter)]['link'] = link
                    name = child.a.string
                    variablevalue[str(counter)]['name'] = name
                    if 'geb.' in child.text:
                        birthdate_index = child.text.find('geb.')
                        start_index = birthdate_index + 5
                        end_index = birthdate_index + 15
                        birthdate = child.text[start_index:end_index]
                        variablevalue[str(counter)]['birthdate'] = birthdate
                    if 'Anteil' in child.text:
                        p = re.compile('Anteil: ([\w %,]*)[)]')
                        variablevalue[str(counter)]['anteil'] = p.search(str(child.text)).group(1)
                    if child.br != None and child.br.string != None:
                        comment1 = child.br.string
                        variablevalue[str(counter)]['comment1'] = comment1
                    if child.text.strip()[0:5] != name[0:5]:
                        comment2 = child.text.strip()
                        comment2 = re.sub(r'\s+', ' ', comment2).strip()
                        variablevalue[str(counter)]['comment2']= comment2
                    counter += 1
                elif child.stripped_strings != None and list(child.stripped_strings) != []:
                    variablevalue[str(counter)] = {}
                    variablevalue[str(counter)]['type'] = type_of
                    if '(' in list(child.stripped_strings)[0]:
                        parenthesis_open = list(child.stripped_strings)[0].find('(')
                        parenthesis_close = list(child.stripped_strings)[0].find(')')
                        comment = list(child.stripped_strings)[0][parenthesis_open + 1:parenthesis_close]
                        name = list(child.stripped_strings)[0][:parenthesis_open - 1]
                        variablevalue[str(counter)]['name'] = name
                        variablevalue[str(counter)]['comment'] = comment
                    else:
                        name = child.text
                        variablevalue[str(counter)]['name'] = name
                    counter += 1
                else:
                    continue
        elif variablename in {'Kapital'}:
            kapital = variablevalue.stripped_strings
            variablevalue = {}
            counter = 0
            for content in kapital:
                variablevalue[str(counter)] = {}
                currencysymbol = re.compile('[A-Z]{3}')
                currency_re = currencysymbol.search(content)
                currency = currency_re.group()
                variablevalue[str(counter)]['currency'] = currency
                content = content.replace(currency, '')
                value_pattern = re.compile('[0-9,.]+')
                value_re = value_pattern.search(content)
                value = locale.atof(value_re.group())
                variablevalue[str(counter)]['value'] = value
                content = content.replace(value_re.group(), '')
                content = content.strip()
                if content != '':
                    variablevalue[str(counter)]['comment'] = content
                counter += 1
        elif variablename in {'Gericht', 'UID'}:
            variablevalue = list(variablevalue.stripped_strings)[0]
            if ';' in variablevalue:
                index = variablevalue.find(';')
                variablevalue = variablevalue[:index]
        elif variablename in {'Bankverbindung', 'Internet-Adressen', 'E-Mail'}:
            output = {}
            counter = 1
            for grandchild in variablevalue.find_all('a'):
                link = grandchild['href']
                name = grandchild.string
                value = {'name': name, 'link': link}
                output[str(counter)] = value
            variablevalue = output
        elif variablename in {'Suchbegriff(e)'}:
            variablevalue = list(variablevalue.stripped_strings)
        elif variablename in {'Beschäftigte', 'Umsatz', 'EGT'}:
            variablevalues = variablevalue.stripped_strings
            variablevalue = {}
            counter = 0
            for content in variablevalues:
                variablevalue[str(counter)] = {}
                find_year = re.compile('[0-9/]*')
                year_re = find_year.match(content)
                if year_re:
                    year = year_re.group()
                    variablevalue[str(counter)]['year'] = year
                    content = content.replace(year, '')
                index_of_colon = content.find(':')
                if index_of_colon not in [-1, 0]:
                    comment1 = content[:index_of_colon]
                    variablevalue[str(counter)]['comment1'] = comment1
                content = content.replace(re.compile(':? *').match(content).group(), '')
                value_re = re.compile('-?[0-9,.]+').match(content)
                if value_re:
                    value = locale.atof(value_re.group())
                    variablevalue[str(counter)]['value'] = value
                    content = content.replace(value_re.group(), '')
                    content = content.lstrip()
                currencysymbol = re.compile('[A-Z]{3}')
                currency_re = currencysymbol.search(content)
                if currency_re:
                    currency = currency_re.group()
                    variablevalue[str(counter)]['currency'] = currency
                    variablevalue[str(counter)]['unit'] = content[:currency_re.start()]
                    if content[currency_re.end():].strip()[1:-1] != '':
                        variablevalue[str(counter)]['comment2'] = content[currency_re.end():].strip()[1:-1]
                counter += 1
        else:
            continue
        values[beautify(variablename)] = variablevalue
    return values  # want to flatten out dictionary first and improve some minor errors (type for Eigentümer and so on)


def beautify(
        string):  # takes in a string, replaces commas by ; (so we  can export to csv), spaces by '.' and replace umlaute and ß
    string = string.replace('\n', ' ')
    string = ' '.join(string.split())
    string = string.translate(
        {ord('ä'): 'ae', ord('Ä'): 'Ae', ord('ö'): 'oe', ord('Ö'): 'Oe', ord('ü'): 'ue', ord('Ü'): 'Ue', ord('ß'): 'ss',
         ord(' '): '.', ord(','): ';'})
    return string


def extract_values_from_table(table, prefix=[], values={}):
    tr_list = table.children
    # if table.tbody:
    #    tr_list = table.tbody.children
    tr_list = [x for x in tr_list if not isinstance(x, bs4.NavigableString) and x.name == 'tr']
    title = ''
    if tr_list == []:
        return
    for tr in tr_list:
        if ('class', ['title', 'main', 'indent']) in tr.attrs.items() or ('class', ['title']) in tr.attrs.items() or (
                'class', ['title', 'main']) in tr.attrs.items():
            if tr.find('td', attrs={'class': 'value'}).string == None:
                title = beautify(tr.find('td', attrs={'class': 'text'}).string)
            else:
                variablename = '_'.join(prefix) + '_' + (tr.find('td', attrs={'class': 'text'}).string)
                value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
                values[variablename] = value
        elif ('class', ['level-group']) in tr.attrs.items():
            table_list = tr.td.children
            table_list = [x for x in table_list if not isinstance(x, bs4.NavigableString) and x.name == 'table']
            for table_element in table_list:
                extract_values_from_table(table_element, prefix + [title], values)
        elif ('class', ['indent']) in tr.attrs.items():
            if tr.find('td', attrs={'class': 'text single'}) != None:
                variablename = '_'.join(prefix) + '_' + beautify(tr.find('td', attrs={'class': 'text single'}).string)
            elif tr.find('th', attrs={'class': 'text'}) != None:
                variablename = '_'.join(prefix) + '_' + beautify(tr.find('th', attrs={'class': 'text'}).string)
            if tr.find('td', attrs={'class': 'value'}) != None:
                value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
            elif tr.find('th', attrs={'class': 'value'}) != None:
                value = locale.atof(tr.find('th', attrs={'class': 'value'}).string)
            values[variablename] = value
        elif ('class', ['sum']) in tr.attrs.items():
            variablename = '_'.join(prefix) + '_' + title + '_' + beautify(
                tr.find('td', attrs={'class': 'text'}).string)
            value = locale.atof(tr.find('td', attrs={'class': 'value'}).string)
            values[variablename] = value
        elif len(tr.attrs.items()) == 0 or ('class',['']) in tr.attrs.items():
            if tr.find(attrs={'class': 'text'}).string:
                variablename = '_'.join(prefix) + '_' + beautify(tr.find(attrs={'class': 'text'}).string)
            elif tr.find(attrs={'class': 'textsingle'}).string:
                variablename = '_'.join(prefix) + '_' + beautify(tr.find(attrs={'class': 'text single'}).string)
            value = locale.atof(tr.find(attrs={'class': 'value'}).string)
            values[variablename] = value


def extract_values_from_div(div, prefix=[], values={}):
    title = ''
    div_children = div.children
    div_children = [x for x in div_children if not isinstance(x, bs4.NavigableString)]
    for child in div_children:
        if child.name == 'h3':
            title = child.string
        elif child.name == 'div':
            extract_values_from_div(child, prefix + [title], values)
        elif child.name == 'table':
            if ('class', ['header']) in child.attrs.items():
                continue
            elif ('class', ['bilanz-footer']) in child.attrs.items():
                extract_values_from_table(child, prefix + [title], values=values)
            elif child.attrs == {}:
                extract_values_from_table(child, prefix + [title], values=values)


def extract_values_from_bilanz(soup):
    values = {}
    firmenname = soup.find('h1')
    firmenname = firmenname.string
    values["Firmenname"] = firmenname

    fn = soup.find('h2')
    fn = fn.string[3:]
    values["FN"] = fn

    title = beautify(soup.h3.text)

    bilanzinfo = soup.find(attrs={'class': 'bilanz-info'})
    for child in bilanzinfo.find_all('div'):
        name = child.find(attrs={'class': 'title'}).string
        index = name.find(':')
        name = name[:index]
        name = beautify(name)
        values[title + '_' + name] = child.find(attrs={'class': 'content'}).string

    div = soup.find('div', attrs={'class': 'table-container'})
    extract_values_from_div(div, prefix=[title], values=values)

    infotext = soup.find_all('div', attrs={'class', 'infotext'})
    if len(infotext) > 0:
        infotext = soup.find('div', attrs={'class', 'infotext'}).p.string
        infotext = re.sub(r'\s+', ' ', infotext).strip()
        values[title + '_' + 'infotext'] = infotext
    return values
