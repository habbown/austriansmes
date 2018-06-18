# put file logindata.py in same folder having form:
# username = 'COMPASS USERNAME'
# password = 'COMPASS PASSWORD'
#
# sql_config = {'user':'USERNAME',
#               'host':'HOST ADDRESS',
#               'database':'DATABASE NAME',
#               'password': 'PASSWORD',
#               'port':'PORT'}
#
# replace words in capitals
# test
import time  # to measure time it takes
import requests  # handling the HTTP requests
from bs4 import BeautifulSoup  # read HTML pages
import csv  # read company names from csv
import locale  # properly read in numbers written with , for comma and . as thousands separator
import statistics  # statistics.mean
import re  # regular expressions
from sqlalchemy import create_engine  # for the SQL database
import pprint  # nice printing

import pandas as pd  # write data to dataframe in order to write out to SQL db
import pymysql  # keep, is needed for SQL engine

import crawler  # functions to extract values
import logindata  # logindata to Compass and SQL db

locale.setlocale(locale.LC_ALL, '')  # set locale so that numbers are read correctly

# some timing
time_requests = []
time_scraping_profile = []
time_scraping_bilanz = []


# variablenames for the SQL tables
names_basicdata = ['FN', 'Firmenname', 'Compass-ID(ONR)', 'Firmenwortlaut', 'Adresse', 'DVR-Nummer', 'Gruendungsjahr',
                   'Ersteintragung', 'Fax', 'Geschaeftszweig.lt..Firmenbuch', 'Gericht', 'Gruendungsjahr',
                   'Korrespondenz', 'Letzte.Eintragung', 'OeNB.Identnummer', 'Rechtsform', 'Sitz.in',
                   'Taetigkeit.lt..Recherche', 'Telefon', 'UID', 'Korrespondenz', 'Produkte',
                   'Import', 'Export', 'Markennamen', 'geloescht', 'Gruendungsprivilegierung', 'Ringbeteiligung',
                   'Boersennotiert', 'Firmenwortlaut', 'Zusaetzliche.Angaben']
names_abschluss = ['Jahresabschluss', 'Konzernabschluss']
names_searchdata = ['Suchbegriff(e)', 'OENACE.2008', 'Historische.Adressen', 'Historische.Firmenwortlaute',
                    'Bankleitzahl(en)']
names_numericdata = ['Beschaeftigte', 'EGT', 'Umsatz', 'Kapital', 'Cashflow']
names_administrativedata = ['Eigentuemer', 'Management', 'Beteiligungen', 'Wirtschaftlicher.Eigentuemer',
                            'Kontrollorgane']
names_contactdata = ['Bankverbindung', 'Internet-Adressen', 'E-Mail', 'Gewerbedaten', 'Ediktsdatei']
names_niederlassungsdata = ['Niederlassungen']
names_rechtstatsachen = ['Rechtstatsachen']
names_agrarfoerderungen = ['EU-Agrarfoerderungen']

time_start = time.time()

# read in company data, from file with columns titled 'Company Name' and 'Address Line 1'
# Company Name should contain the name of the company name, Address Line 1 the street name and number
company_list = []
with open('hoovers2to2.3_subset.csv', newline='', encoding='utf-8') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        company_list.append({'name': row["Company Name"], 'address': row["Address Line 1"]})

# set start and end index for which company's to extract
start_index = 100
end_index = 200
company_list = company_list[start_index:end_index]

#pprint.pprint(company_list)

time_after_reading_data = time.time()

# start a requests session in order to save cookies etc.
session_requests = requests.Session()

time_requests.append(time.time())
result = session_requests.post(crawler.url_login, data=crawler.login, headers=dict(referer=crawler.url_login))
time_requests[-1] = time.time() - time_requests[-1]

'''
time_requests.append(time.time())
result = session_requests.get(crawler.url_search, headers=dict(referer=crawler.url_compass))
time_requests[-1] = time.time() - time_requests[-1]
'''

time_before_loop = time.time()

index = start_index

list_basicdata = []
list_numericdata = []
list_administrativedata = []
list_bilanzdata = []
list_contactdata = []
list_searchdata = []
list_abschlussdata = []
list_niederlassungsdata = []
list_rechtstatsachen = []
list_agrarfoerderungen = []

for company in company_list:
    print('#####################')
    print('Firma Nummer: ' + str(index))
    print(company['name'])
    print(company['address'])
    index += 1
    values = {}

    time_requests.append(time.time())
    soup = crawler.find_company(company, session_requests, False)
    time_requests[-1] = time.time() - time_requests[-1]

    # print(soup)
    if not soup:
        continue

    values = crawler.get_company_values(soup, session_requests)
    #pprint.pprint(values)


    #  put collected values into a list of dictionaries, at end convert to dataframe
    values_basicdata = {key: value for key, value in values.items() if key in names_basicdata}
    list_basicdata.append(values_basicdata)
    # print(list_basicdata)

    values_numericdata = [value for key, value in values.items() if key in names_numericdata]
    values_numericdata = [item for sublist in values_numericdata for item in sublist]
    list_numericdata.extend(values_numericdata)

    values_contactdata = {key: value for key, value in values.items() if key in names_contactdata}
    values_contactdata = [dict(info, **{'FN': values['FN'], 'field_name': key}) for key, value
                          in values_contactdata.items() for info in value]
    list_contactdata.extend(values_contactdata)

    values_administrativedata = [value for key, value in values.items() if key in names_administrativedata]
    values_administrativedata = [item for sublist in values_administrativedata for item in sublist]
    list_administrativedata.extend(values_administrativedata)

    values_searchdata = {key: value for key, value in values.items() if key in names_searchdata}
    values_searchdata = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value in values_searchdata.items()
                         for info in value]
    list_searchdata.extend(values_searchdata)

    values_bilanzdata = [{'FN': values['FN'], 'name': key, 'value': value}
                         for key, value in values.items() if key.startswith('Bilanz')]
    list_bilanzdata.extend(values_bilanzdata)

    values_abschlussdata = {key: value for key, value in values.items() if key in names_abschluss}
    values_abschlussdata = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value
                            in values_abschlussdata.items() for info in value]
    list_abschlussdata.extend(values_abschlussdata)

    values_niederlassungsdata = {key: value for key, value in values.items() if key in names_niederlassungsdata}
    values_niederlassungsdata = [dict(info, **{'FN': values['FN'], 'type': key}) for key, value
                                 in values_niederlassungsdata.items() for info in value]
    list_niederlassungsdata.extend(values_niederlassungsdata)

    values_rechtstatsachen = {key: value for key, value in values.items() if key in names_rechtstatsachen}
    values_rechtstatsachen = [{'FN': values['FN'], 'type': key, 'number': key1, 'text': value1} for key, value
                              in values_rechtstatsachen.items() for key1, value1 in value.items()]
    list_rechtstatsachen.extend(values_rechtstatsachen)

    values_agrarfoerderungen = {key: value for key, value in values.items() if key in names_agrarfoerderungen}
    values_agrarfoerderungen = [dict(info, **{'FN': values['FN'], 'field_name': key}) for key, value
                                in values_agrarfoerderungen.items() for info in value]
    list_agrarfoerderungen.extend(values_agrarfoerderungen)


# print('#################')
# print('extracted:')
# pprint.pprint(values)

time_after_loop = time.time()

print(time_start)
print(time_after_reading_data)
print(time_before_loop)
print(time_after_loop)
print("Zeit pro Firma: " + str((time_after_loop - time_before_loop) / (end_index - start_index)))
if time_scraping_bilanz != []:
    print("Scraping der Bilanzen durchschnittlich: " + str(statistics.mean(time_scraping_bilanz)))
if time_requests != []:
    print("Durchführung der Requests durchschnittlich: " + str(statistics.mean(time_requests)))
print("Anzahl der Requests: " + str(len(time_requests)))
if time_scraping_profile != []:
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
abschlussdata = pd.DataFrame(list_abschlussdata)
niederlassungsdata = pd.DataFrame(list_niederlassungsdata)
rechtstatsachendata = pd.DataFrame(list_rechtstatsachen)
agrarfoerderungendata = pd.DataFrame(list_agrarfoerderungen)
# pprint.pprint(administrativedata)

print(niederlassungsdata)

contactdata = pd.DataFrame(list_contactdata)
time_for_pd = time.time() - time_for_pd
print("time_for_pd", time_for_pd)

time_for_sql = time.time()
DB_NAME = 'compassdata'


engine_address = ("mysql+pymysql://" + logindata.sql_config['user'] + ":" + logindata.sql_config['password'] +
                  "@" + logindata.sql_config['host'] + "/" + DB_NAME + "?charset=utf8")
engine = create_engine(engine_address, encoding='utf-8')
con = engine.connect()
if not basicdata.empty:
   basicdata.to_sql(name="BasicDataTemp", con=con, if_exists='append')
if not numericdata.empty:
  numericdata.to_sql(name="NumericDataTemp", con=con, if_exists='append')
if not administrativedata.empty:
  administrativedata.to_sql(name="AdministrativeDataTemp", con=con, if_exists='append')
if not bilanzdata.empty:
  bilanzdata.to_sql(name="BilanzDataTemp", con=con, if_exists='append')
if not contactdata.empty:
  contactdata.to_sql(name="ContactDataTemp", con=con, if_exists='append')
if not searchdata.empty:
    searchdata.to_sql(name="SearchDataTemp", con=con, if_exists='append')
if not abschlussdata.empty:
    abschlussdata.to_sql(name="AbschlussTemp", con=con, if_exists='append')
if not niederlassungsdata.empty:
    niederlassungsdata.to_sql(name="NiederlassungenTemp", con=con, if_exists='append')
if not rechtstatsachendata.empty:
    rechtstatsachendata.to_sql(name="RechtstatsachenTemp", con=con, if_exists='append')
if not agrarfoerderungendata.empty:
    agrarfoerderungendata.to_sql(name="EU_AgrarfoerderungenTemp", con=con, if_exists='append')
con.close()
time_for_sql = time.time() - time_for_sql
print("time_for_sql", time_for_sql)

crawler.update_tables()