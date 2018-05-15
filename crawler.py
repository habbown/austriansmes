import bs4
import locale

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
        variablename = beautify(' '.join(list(variablename.stripped_strings)))
        if variablevalue.string != None:
            variablevalue = variablevalue.string
        elif variablename in {'Adresse', 'Postanschrift', 'Historische Adressen', 'Historische Firmenwortlaute'}:
            variablevalues = variablevalue.find_all('p')
            if len(variablevalues) != 0:
                variablevalue = []
                for list_element in variablevalues:
                    list_element = '; '.join(list(list_element.stripped_strings))
                    variablevalue.append(list_element)
            else:
                variablevalue = '; '.join(list(variablevalue.stripped_strings))
        elif variablename in {'Wirtschaftlicher Eigentümer', 'Eigentümer', 'Management', 'Beteiligungen'}:
            variablevalue_children = [x for x in variablevalue.children if not isinstance(x, bs4.NavigableString)]
            variablevalue = {}
            counter = 0
            type = None
            value = {}
            for child in variablevalue_children:
                if child.b != None:
                    type = child.b.text
                    if '\\' in type:
                        index = type.find('\\')
                        type = type[:index]
                    value['type'] = type
                if child.a != None:
                    if child.a != None:
                        link = child.a['href']
                        value['link'] = link
                        name = child.a.string
                        value['name'] = name
                    if 'geb.' in child.text:
                        birthdate_index = child.text.find('geb.')
                        start_index = birthdate_index + 5
                        end_index = birthdate_index + 15
                        birthdate = child.text[start_index:end_index]
                        value['birthdate'] = birthdate
                    if 'Anteil' in child.text:
                        anteil_index = child.text.find('Anteil')
                        percent_index = child.text.find('%')
                        anteil = child.text[anteil_index + 7:percent_index]
                        value['anteil'] = anteil
                    if child.br != None:
                        comment = child.br.string
                        value['comment'] = comment
                    variablename1 = variablename + str(counter)
                    variablevalue[variablename1] = value
                    counter += 1
        elif variablename in {'Kapital'}:
            kapital = variablevalue.stripped_strings
            output = {}
            for content in kapital:
                content_split = content.split(" ")
                variablevalue = locale.atof(content_split[1])
                del content_split[1]
                variablename1 = ' '.join(content_split)
                variablename1 = variablename + '.' + variablename1
                output[variablename1] = variablevalue
            variablevalue = output
        elif variablename in {'Gericht', 'UID'}:
            variablevalue = list(variablevalue.stripped_strings)[0]
            if ';' in variablevalue:
                index = variablevalue.find(';')
                variablevalue = variablevalue[:index]
        elif variablename in {'Bankverbindung', 'Internet-Adressen'}:
            output = {}
            counter = 1
            for grandchild in variablevalue.find_all('a'):
                link = grandchild['href']
                name = grandchild.string
                value = {'name': name, 'link': link}
                output[variablename + str(counter)] = value
            variablevalue = output
        elif variablename in {'Beschäftigte', 'Umsatz', 'EGT'}:
            variablevalues = variablevalue.stripped_strings
            variablevalue = {}
            for content in variablevalues:
                content_split = content.split(":")
                if content_split[1] == '  keine':
                    content_split[1] = '0'
                variablevalue2 = content_split[1] # need to convert to number
                del content_split[1]
                variablekey = variablename + content_split[0]
                variablevalue[variablekey] = variablevalue2
        else:
            continue
        values[variablename] = variablevalue
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
    tr_list = table.tbody.children
    tr_list = [x for x in tr_list if not isinstance(x, bs4.NavigableString) and x.name == 'tr']
    title = ''
    if tr_list == []:
        return
    for tr in tr_list:
        if ('class', ['title', 'main', 'indent']) in tr.attrs.items() or ('class', ['title']) in tr.attrs.items():
            if tr.find('td', attrs={'class': 'value'}).string == None:
                title = beautify(tr.find('td', attrs={'class': 'text'}).string)
            else:
                variablename = '_'.join(prefix) + '_' + (tr.find('td', attrs={'class': 'text'}).string)
                value = tr.find('td', attrs={'class': 'value'}).string
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
        elif len(tr.attrs.items()) == 0:
            variablename = prefix[0] + '_' + beautify(tr.find('th', attrs={'class': 'text'}).string)
            value = locale.atof(tr.find('th', attrs={'class': 'value'}).string)
            values[variablename] = value


def extract_values_from_div(div, prefix=[], values={}):
    title = ''
    div_children = div.children
    div_children = [x for x in div_children if not isinstance(x, bs4.NavigableString)]
    for child in div_children:
        if child.name == 'h3':
            title = beautify(child.string)
        elif child.name == 'div':
            extract_values_from_div(child, prefix + [title], values)
        elif child.name == 'table':
            if ('class', ['header']) in child.attrs.items():
                continue
            elif ('class', ['bilanz-footer']) in child.attrs.items():
                extract_values_from_table(child, prefix + [title], values)
            elif child.attrs == {}:
                extract_values_from_table(child, prefix + [title], values)


def extract_values_from_bilanz(soup):
    values = {}
    firmenname = soup.find('h1')
    firmenname = firmenname.string
    values["Firmenname"] = firmenname

    fn = soup.find('h2')
    fn = fn.string[3:]
    values["FN"] = fn

    bilanzinfo = soup.find(attrs={'class': 'bilanz-info'})
    for child in bilanzinfo.find_all('div'):
        name = child.find(attrs={'class': 'title'}).string
        index = name.find(':')
        name = name[:index]
        name = beautify(name)
        values[name] = child.find(attrs={'class': 'content'}).string

    title = beautify(soup.h3.text)
    div = soup.find('div', attrs={'class': 'bilanz'})

    extract_values_from_div(div, prefix=[title], values=values)

    infotext = values['infotext'] = soup.find_all('div', attrs={'class', 'infotext'})
    if len(infotext) > 0:
        values['infotext'] = soup.find('div', attrs={'class', 'infotext'}).p.string
    return values
