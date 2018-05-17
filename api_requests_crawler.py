# add username and password in relevant lines

import crawler
import requests
from bs4 import BeautifulSoup
import csv
# import pandas
import locale

locale.setlocale(locale.LC_ALL, '')
import pprint
import logindata

company_list = []

with open('hoovers2to2.3_subset.csv', newline='', encoding='utf-8') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        company_list.append({'name': row["Company Name"], 'address': row["Address Line 1"]})

company_list = company_list[1:3]

url_login = "https://daten.compass.at/sso/login/process"
url = "https://daten.compass.at/FirmenCompass"
url_bilanz = "https://daten.compass.at/FirmenCompass/Bilanz"

session_requests = requests.Session()
login = {
    "targetUrl": "/compassDienste/startseite",
    "userDomain": "916F8E",
    "username": logindata.username,
    "password": logindata.password,
    "_saveLogin": "false",
    "loginSubmit": "Login"
}
result = session_requests.post(url_login, data=login, headers=dict(referer=url_login))

result = session_requests.get(url, headers=dict(referer=url))
# looking up by name is not ideal, we could use address from D&B Hoovers to look up by address and then do name check (or something along this line?)


search_data = {
    "PageID": "916F8E",
    "p": "suche",
    "suchwort": "",  # change by company
    "suchartid": "F",  # 'F' for name, 'A' for address
    "suchbldid": "Oe"
}

bilanz_data = {
    "PageID": "916F8E",
    "onr": "",  # extract from company profile
    "id": "20202351",  # extract from company profile, unique bilanz identifier
    "format": "htmltable",
    "erstellen": "Anzeigen"
}
# what to do if search results in a list of companies?



for company in company_list:
    values = {}
    search_data["suchartid"] = "F"
    search_data["suchwort"] = company['name']
    result = session_requests.post(result.url, data=search_data)
    soup = BeautifulSoup(result.text, 'html.parser')

    # check whether more than one company was found and try in a different way
    result_summary = soup.find('h2', attrs={'id': 'result_summary'})
    if not result_summary: #if not more than one company was found, check whether no company was found
        result_summary = soup.find('span', attrs={'id': 'result_summary'})

    if result_summary:
        search_data["suchartid"] = "A"
        search_data["suchwort"] = company['address']
        result = session_requests.post(result.url, data=search_data)
        soup = BeautifulSoup(result.text, 'html.parser')
        result_summary = soup.find('h2', attrs={'id': 'result_summary'})
        # if result_summary: #in case again no unique company is found, match (or read out all of them?)

    # assume now that we have a company profile in our soup:
    values = crawler.extract_values_from_profile(soup)

    # read in Bilanzdata, and extract id's
    form_list = soup.find_all('form', attrs={'method': 'post', 'action': 'Bilanz', 'target': '_bank'})
    values['Jahresabschluss'] = {}
    counter = 0
    for form in form_list:
        values['Jahresabschluss'][str(counter)] = {}
        onr_number = form.find('input', attrs={'name': 'onr', 'type': 'hidden'})['value']
        id_number = form.find('input', attrs={'name': 'id', 'type': 'hidden'})['value']
        if id_number and onr_number:
            bilanz_data['onr'] = onr_number
            bilanz_data['id'] = id_number
            bilanz = session_requests.post(url_bilanz, data=bilanz_data)
            bilanz_soup = soup = BeautifulSoup(bilanz.text, 'html.parser')
            values.update(crawler.extract_values_from_bilanz(bilanz_soup))
        form_text = form.find('span', attrs={'class': 'spacing'})
        if form_text:
            values['Jahresabschluss'][str(counter)]['text'] = form_text.string
        form_comment = form.find('span', attrs={'class': 'badge'})
        if form_comment:
            values['Jahresabschluss'][str(counter)]['comment'] = form_comment.string
    pprint.pprint(values)

'''
# pandas.DataFrame(values).to_csv('index.csv',index=True) #doesn't work, why?
# open a csv file with append, so old data will not be erased
with open('index.csv', 'w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, values.keys())
    writer.writeheader()
    writer.writerow(halloasia)
'''
