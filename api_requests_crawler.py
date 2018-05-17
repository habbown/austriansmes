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



with open('hoovers2to2.3_subset.csv', newline='', encoding='utf-8') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        suchwort_liste.append(row["Company Name"])

suchwort_liste = suchwort_liste[1:3]

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
    "suchwort": "hallo asia",
    "suchartid": "F",
    "suchbldid": "Oe"
}
# what to do if search results in a list of companies?

result = session_requests.post(result.url, data=search_data)
soup = BeautifulSoup(result.text, 'html.parser')


values = crawler.extract_values_from_profile(soup)

bilanz_data = {
    "PageID": "916F8E",
    "onr": "12818737",
    "id": "20202351",
    "format": "htmltable",
    "erstellen": "Anzeigen"
}

bilanz = session_requests.post(url_bilanz, data=bilanz_data)
soup = BeautifulSoup(bilanz.text, 'html.parser')






crawler.extract_values_from_bilanz(soup)

'''
# pandas.DataFrame(values).to_csv('index.csv',index=True) #doesn't work, why?
# open a csv file with append, so old data will not be erased
with open('index.csv', 'w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, values.keys())
    writer.writeheader()
    writer.writerow(halloasia)
'''