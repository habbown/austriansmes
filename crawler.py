import bs4
from bs4 import BeautifulSoup
import locale
import pprint
import re
import unicodedata

# should we convert every string extracted from the page from navigable string to normal string?

locale.setlocale(locale.LC_ALL, '')


# takes in the source code of a profile page and extracts all values from the page
def extract_values_from_profile(soup):
    values = {}
    fn_box = soup.find('h2')
    fn = fn_box.text.strip()[3:]
    values['FN'] = fn
    if soup.find('h1', attrs={'class': 'geloescht'}):
        values['gelöscht'] = soup.find('h1', attrs={'class': 'geloescht'}).string

    div = soup.find('div', attrs={'class': 'content'})

    div_children = [x for x in div.children if not isinstance(x, bs4.NavigableString) and x.name == 'div']
    # go through all possible pairs of variablename and variablevalue, depending on variablename do something with the
    # field containing the variablevalues to convert it to reasonable output
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
                info['name'] = name
            variablevalue = [info]
        elif variablename in {'Ediktsdatei'}:
            for item in variablevalue.stripped_strings:
                if item.parent.name == 'a':
                    link = item.parent['href']
                    linktext = item
                else:
                    comment = item
            variablevalue = {'link': link, 'linktext': linktext, 'comment': comment}
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
        elif variablename in {'Wirtschaftlicher Eigentümer'}:
            variablevalue_children = [x for x in variablevalue.children if not isinstance(x, bs4.NavigableString)]
            variablevalue = []
            for child in variablevalue_children:
                info = {}
                info['FN'] = fn
                info['function'] = variablename
                # in case of div, there's two span tags inside of which the first contains the information and the second a link to a diagram
                if child.name == 'div' and child.span:
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
                variablevalue.append(info)
        elif variablename in {'Rechtstatsachen'}:
            variablevalue_children = variablevalue.find_all('p')
            variablevalue = {}
            for child in variablevalue_children:
                variablevalue[child.b.string] = list(child.stripped_strings)[1]
        elif variablename in {'Firmeninformationen'}:
            info = {}
            for item in variablevalue.find_all('li'):
                if item.a:
                    info['name'] = item.a.string
                    info['link'] = item.a['href']
            variablevalue = info
        elif variablename in {'Ringbeteiligung'}:
            if variablevalue.find('span', attrs={'class': 'checked'}):
                variablevalue = variablevalue.find('span', attrs={'class': 'checked'})
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
                info['FN'] = fn
                info['function'] = variablename
                if child.p:
                    continue
                else:
                    if child.b:
                        type_of = child.b.string
                        type_of.replace("\xc2\xa0", "")
                        type_of.replace("\xa0", "")
                        type_of = re.sub('\s+', ' ', type_of)
                        type_of.strip()
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
                            p = re.compile('Anteil: ([\w %,.€]*)[)]')
                            info['anteil'] = p.search(str(child.text)).group(1)
                        if child.br != None and child.br.string != None:
                            comment1 = child.br.string
                            info['comment1'] = comment1
                        if child.text.strip()[0:5] != name[0:5]:
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
        elif variablename in {'Bankverbindung', 'Internet-Adressen', 'E-Mail'}:
            children = variablevalue.find_all('a')
            variablevalue = []
            for child in children:
                link = child['href']
                name = child.string
                info = {'name': name, 'link': link}
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
        elif variablevalue.string:
            variablevalue = re.sub(r'\s+', ' ', variablevalue.string).strip()
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
         ord(' '): '.', ord(';'): ','})
    return string
    # what about commatas for CSV-export (or escape by putting in quotes and replacing quotes (") in text (do these exist)
    # by double quotes (#)


def extract_values_from_table(table, prefix=[], values={}):
    # takes in a table tag, a prefix (to prepend the variablenames with), and a dictionary it adds values to (is that good or
    # wouldn't it be better to just return a dictionary containing the values extracted from the table?)
    tr_list = table.children
    # if table.tbody:
    #    tr_list = table.tbody.children
    tr_list = [x for x in tr_list if not isinstance(x, bs4.NavigableString) and x.name == 'tr']
    title = ''
    if tr_list == []:
        return
    for tr in tr_list:
        # depending on the tr's (the lines of the table) attributes, do one of certain things; if it contains the title
        # of a subtable add it to the prefix, if it contains values, put them into the table, ...
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
        elif len(tr.attrs.items()) == 0 or ('class', ['']) in tr.attrs.items():
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
