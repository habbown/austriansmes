# put file logindata.py in same folder having form:
# username = 'COMPASS USERNAME''
# password = 'COMPASS PASSWORD'
#
# sql_config = {'user':'USERNAME',
#               'host':'HOST ADDRESS',
#               'database':'DATABASE NAME',
#               'password': 'PASSWORD',
#               'port':'PORT'}
#
# replace words in capitals
import time
import crawler
import requests
from bs4 import BeautifulSoup
import csv

import locale
import statistics
import re

from sqlalchemy import create_engine

locale.setlocale(locale.LC_ALL, '')
import pprint
import logindata
import pandas as pd
import pymysql  # keep, is needed for SQL engine

'''
import mysql.connector
from mysql.connector import errorcode


def create_database(cursor):
    try:
        cursor.execute(
            "CREATE DATABASE {} DEFAULT CHARACTER SET 'utf8'".format(DB_NAME))
    except mysql.connector.Error as err:
        print("Failed creating database: {}".format(err))
        exit(1)


try:
    cnx = mysql.connector.connect(**logindata.sql_config)
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Something is wrong with your user name or password")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Database does not exist")
    else:
        print(err)
else:
    cnx.close()

cursor = cnx.cursor()

try:
    cnx.database = DB_NAME
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_BAD_DB_ERROR:
        create_database(cursor)
        cnx.database = DB_NAME
    else:
        print(err)
        exit(1)

for name, ddl in TABLES.iteritems():
    try:
        print("Creating table {}: ".format(name), end='')
        cursor.execute(ddl)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
            print("already exists.")
        else:
            print(err.msg)
    else:
        print("OK")

add_basicdata = ("""INSERT INTO basic_data""")
# cursor.close()
# cnx.close()


for table_info in crsr.tables(tableType='TABLE'):
    print(table_info.table_name)
'''
company_list = []

time_requests = []
time_scraping_profile = []
time_scraping_bilanz = []

''' ['Gewerbedaten','Ediktsdatei', 'weitere.Informationen', 'Boersennotiert',
                   'Bankleitzahl', 'Taetigkeit']
'''
names_basicdata = ['FN', 'Firmenname', 'Compass-ID(ONR)', 'Firmenwortlaut', 'Adresse', 'DVR-Nummer', 'Gruendungsjahr',
                   'Ersteintragung', 'Fax', 'Geschaeftszweig.lt..Firmenbuch',
                   'Gericht', 'Gruendungsjahr', 'Korrespondenz',
                   'Letzte.Eintragung', 'OeNB.Identnummer', 'Rechtsform', 'Sitz.in',
                   'Taetigkeit.lt..Recherche',
                   'Telefon', 'UID',
                   ]

names_searchdata = ['Suchbegriff(e)', 'OENACE.2008']

names_numericdata = ['Beschaeftigte', 'EGT', 'Umsatz', 'Kapital', 'Cashflow']

names_administrativedata = ['Eigentuemer', 'Management', 'Beteiligungen', 'Wirtschaftlicher.Eigentuemer']

names_contactdata = ['Bankverbindung', 'Internet-Adressen', 'E-Mail']

time_start = time.time()
with open('hoovers2to2.3_subset.csv', newline='', encoding='utf-8') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        company_list.append({'name': row["Company Name"], 'address': row["Address Line 1"]})

start_index = 0
end_index = 10

company_list = company_list[start_index:end_index]

pprint.pprint(company_list)

time_after_reading_data = time.time()

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

time_requests.append(time.time())
result = session_requests.post(url_login, data=login, headers=dict(referer=url_login))
time_requests[-1] = time.time() - time_requests[-1]

time_requests.append(time.time())
result = session_requests.get(url, headers=dict(referer=url))
time_requests[-1] = time.time() - time_requests[-1]

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
    "id": "",  # extract from company profile, unique bilanz identifier
    "format": "htmltable",
    "erstellen": "Anzeigen"
}

time_before_loop = time.time()

index = start_index

list_basicdata = []
list_numericdata = []
list_administrativedata = []
list_bilanzdata = []
list_contactdata = []
list_searchdata = []

for company in company_list:
    print('#####################')
    print('Firma Nummer: ' + str(index))
    print(company['name'])
    print(company['address'])
    index += 1
    values = {}

    #
    search_data["suchartid"] = "F"
    search_data["suchwort"] = company['name'][0:38]  # if company name length > ~41, then no search results are found
    time_requests.append(time.time())
    result_profil = session_requests.post(result.url, data=search_data)
    time_requests[-1] = time.time() - time_requests[-1]
    soup = BeautifulSoup(result_profil.text, 'html.parser')

    # check whether more than one company was found and try in a different way
    result_summary = soup.find('h2', attrs={'id': 'result_summary'})
    if not result_summary:  # if not more than one company was found, check whether no company was found
        result_summary = soup.find('span', attrs={'id': 'result_summary'})
        if not result_summary:  # another option is that too many companies were found: (e.g., Spar)
            result_summary = soup.find('div', attrs={'class': 'message warning'})
            if result_summary:
                result_summary = result_summary.div

    if result_summary:  # when search by company name doesn't succeed (when no company is found(/ > 1 company found)
        # search by address
        print('No unique company by name')
        search_data["suchartid"] = "A"
        search_data["suchwort"] = company['address'][0:38]
        time_requests.append(time.time())
        result_profil = session_requests.post(result.url, data=search_data)
        time_requests[-1] = time.time() - time_requests[-1]
        soup = BeautifulSoup(result_profil.text, 'html.parser')
        # if not unique, match by name (if no search result go back to looking by name?)
        if soup.find('h2', attrs={'id': 'result_summary'}):
            tag = soup.find('a', string=re.compile(str(company['name'][1:-1])))
            onr_re = re.compile('onr=(\d*)')
            onr = onr_re.search(str(tag)).group(1)
            values['Compass-ID(ONR)'] = onr
            result_profil = session_requests.post(result.url, {'p': 'betrieb', 'onr': onr, 'PageID': '916F8E'})
            soup = BeautifulSoup(result_profil.text, 'html.parser')

    # if we still don't have a company profile page in our soup, we'll continue
    result_summary = None
    result_summary = soup.find('h2', attrs={'id': 'result_summary'})

    if not result_summary:  # if not more than one company was found, check whether no company was found
        result_summary = soup.find('span', attrs={'id': 'result_summary'})

    if result_summary:
        continue

    # assume now that we have a company profile in our soup:
    time_scraping_profile.append(time.time())
    values.update(crawler.extract_values_from_profile(soup))
    time_scraping_profile[-1] = time.time() - time_scraping_profile[-1]

    # extract onr (Compass ID for companies)
    onr_pattern = re.compile('onr=(\d+)')
    onr_re = onr_pattern.search(result_profil.url)
    if onr_re:
        values['Compass-ID(ONR)'] = onr_re.group(1)

    # read in Bilanzdata, and extract id's
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
            time_requests.append(time.time())
            bilanz = session_requests.post(url_bilanz, data=bilanz_data)
            time_requests[-1] = time.time() - time_requests[-1]
            bilanz_soup = BeautifulSoup(bilanz.text, 'html.parser')
            time_scraping_bilanz.append(time.time())
            values.update(crawler.extract_values_from_bilanz(bilanz_soup))
            time_scraping_bilanz[-1] = time.time() - time_scraping_bilanz[-1]
    #  put collected values into a list of dictionaries, at end convert to dataframe
    # values_basicdata = {}
    # pprint.pprint(values)
    values_basicdata = {key: value for key, value in values.items() if key in names_basicdata}
    list_basicdata.append(values_basicdata)
    # print(list_basicdata)

    values_numericdata = [value for key, value in values.items() if key in names_numericdata]
    values_numericdata = [item for sublist in values_numericdata for item in sublist]
    list_numericdata.extend(values_numericdata)

    values_contactdata = {key: value for key, value in values.items() if key in names_contactdata}
    values_contactdata = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value in values_contactdata.items()
                          for info in value]
    list_contactdata.extend(values_contactdata)

    values_administrativedata = [value for key, value in values.items() if key in names_administrativedata]
    values_administrativedata = [item for sublist in values_administrativedata for item in sublist]
    list_administrativedata.extend(values_administrativedata)

    values_searchdata = {key:value for key, value in values.items() if key in names_searchdata}
    values_searchdata = [dict(info, **{'FN': values['FN'], 'type': key}) for key,value in values_searchdata.items()
                         for info in value]
    list_searchdata.extend(values_searchdata)


    values_bilanzdata = [{'FN': values['FN'], 'name': key, 'value': value}
                         for key, value in values.items() if key.startswith('Bilanz')]
    list_bilanzdata.extend(values_bilanzdata)


# print('#################')
# print('extracted:')
# pprint.pprint(values)

time_after_loop = time.time()

print(time_start)
print(time_after_reading_data)
print(time_before_loop)
print(time_after_loop)
print("Zeit pro Firma: " + str((time_after_loop - time_before_loop) / (end_index - start_index)))
print("Scraping der Bilanzen durchschnittlich: " + str(statistics.mean(time_scraping_bilanz)))
print("Durchführung der Requests durchschnittlich: " + str(statistics.mean(time_requests)))
print("Anzahl der Requests: " + str(len(time_requests)))
print("Scraping der Profile durchschnittlich: " + str(statistics.mean(time_scraping_profile)))
# print('Bilanzenscraping')
# pprint.pprint(time_scraping_bilanz)
# print('Profilscraping')
# pprint.pprint(time_scraping_profile)
# print('Requests')
# pprint.pprint(time_requests)

# for numeric data make table: first extract field names and then write out using dictwriter (or look into dictwriter documentation again)
# OR write out manually
# for non-numeric data make extra tables, with several rows per company, depending on number of managers, ...


# pandas.DataFrame(values).to_csv('index.csv',index=True) #doesn't work, why?
# open a csv file with append, so old data will not be erased

'''
Possible variable names:
Basic data, easy to handle:
Adresse, DVR-Nummer, E-Mail, Ersteintragung, FN, Fax, Firmenname, Firmenwortlaut, Gericht, Gruendungsjahr,
Korrespondenz, Letzte.Eintragung,  OeNBD.Identnummer, Rechtsform, Sitz.in, Taetigkeit.lt..Recherche, Telefon, UID, onr
Basic data, harder to handle:
Bankverbindung, E-Mail, Gewerbedaten, Historische.Adressen, Historische.Firmenwortlaute, Niederlassungen, Internet-Adressen, Jahresabschluss, Kapital, 
OENACE.2008, Suchbegriff(e),
numeric data:
Beschaeftigte, EGT, Umsatz, 
one table for:
Beteiligungen, Eigentuemer, Management, Wirtschaftlicher.Eigentuemer
and a table for:
the data from the Bilanzen
'''

time_for_pd = time.time()

basicdata = pd.DataFrame(list_basicdata)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
# print(basicdata)

numericdata = pd.DataFrame(list_numericdata)
administrativedata = pd.DataFrame(list_administrativedata)
bilanzdata = pd.DataFrame(list_bilanzdata)
searchdata = pd.DataFrame(list_searchdata)
# pprint.pprint(administrativedata)


contactdata = pd.DataFrame(list_contactdata)
time_for_pd = time.time() - time_for_pd
print("time_for_pd", time_for_pd)

time_for_sql = time.time()
DB_NAME = 'compassdata'

'''
try:
    cnx = mysql.connector.connect(**logindata.sql_config)
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("Something is wrong with your user name or password")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("Database does not exist")
    else:
        print(err)
# else:
#   cnx.close()

cursor = cnx.cursor()

try:
    cnx.database = DB_NAME
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_BAD_DB_ERROR:
        create_database(cursor)
        cnx.database = DB_NAME
    else:
        print(err)
        exit(1)
'''


engine_address = ("mysql+pymysql://" + logindata.sql_config['user'] + ":" + logindata.sql_config['password'] +
                  "@" + logindata.sql_config['host'] + "/" + DB_NAME + "?charset=utf8")
engine = create_engine(engine_address, encoding='utf-8')
con = engine.connect()
basicdata.to_sql(name="BasicData", con=con, if_exists='append')
numericdata.to_sql(name="NumericData", con=con, if_exists='append')
administrativedata.to_sql(name="AdministrativeData", con=con, if_exists='append')
bilanzdata.to_sql(name="BilanzData", con=con, if_exists='append')
contactdata.to_sql(name="ContactData", con=con, if_exists='append')
searchdata.to_sql(name="SearchData", con=con, if_exists='append')
con.close()
time_for_sql = time.time() - time_for_sql
print("time_for_sql", time_for_sql)
