# add username and password in relevant lines
import time
import crawler
import requests
from bs4 import BeautifulSoup
import csv
# import pandas
import locale
import statistics
import re

locale.setlocale(locale.LC_ALL, '')
import pprint
import logindata

company_list = []

time_requests = []
time_scraping_profile = []
time_scraping_bilanz = []

time_start = time.time()
with open('hoovers2to2.3_subset.csv', newline='', encoding='utf-8') as csvfile:
    csvreader = csv.DictReader(csvfile)
    for row in csvreader:
        company_list.append({'name': row["Company Name"], 'address': row["Address Line 1"]})


start_index = 0
end_index = 2

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
    "id": "",  # extract from company profile, unique bilanz identifier
    "format": "htmltable",
    "erstellen": "Anzeigen"
}


time_before_loop = time.time()

index = start_index

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
    values = crawler.extract_values_from_profile(soup)
    time_scraping_profile[-1] = time.time() - time_scraping_profile[-1]

    # read in Bilanzdata, and extract id's
    form_list = soup.find_all('form', attrs={'method': 'post', 'action': 'Bilanz', 'target': '_bank'})
    values['Jahresabschluss'] = {}
    counter = 0
    for form in form_list:
        values['Jahresabschluss'][str(counter)] = {}
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
        form_text = form.find('span', attrs={'class': 'spacing'})
        if form_text:
            values['Jahresabschluss'][str(counter)]['text'] = form_text.string
        form_comment = form.find('span', attrs={'class': 'badge'})
        if form_comment:
            values['Jahresabschluss'][str(counter)]['comment'] = list(form_comment.stripped_strings)[0]
        counter += 1
    print('#################')
    print('extracted:')
    pprint.pprint(values)

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


'''
# pandas.DataFrame(values).to_csv('index.csv',index=True) #doesn't work, why?
# open a csv file with append, so old data will not be erased
with open('index.csv', 'w', newline='') as csv_file:
    writer = csv.DictWriter(csv_file, values.keys())
    writer.writeheader()
    writer.writerow(halloasia)
'''
