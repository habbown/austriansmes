import logindata

DATA_HOOVERS_REVENUE_AT_LEAST_70M = 'dnbhoovers_revenueatleast70m.csv'
TERMS_DICT = {
    'BASIC': ['FN', 'Firmenname', 'Compass-ID(ONR)', 'Firmenwortlaut', 'Adresse', 'DVR-Nummer', 'Gruendungsjahr',
              'Ersteintragung', 'Fax', 'Geschaeftszweig.lt..Firmenbuch', 'Gericht', 'Gruendungsjahr',
              'Korrespondenz', 'Letzte.Eintragung', 'OeNB.Identnummer', 'Rechtsform', 'Sitz.in',
              'Taetigkeit.lt..Recherche', 'Telefon', 'UID', 'Korrespondenz', 'Produkte',
              'Import', 'Export', 'Markennamen', 'geloescht', 'Gruendungsprivilegierung', 'Ringbeteiligung',
              'Boersennotiert', 'Firmenwortlaut', 'Zusaetzliche.Angaben',
              'Bankleitzahl(en)'],
    'ABSCHLUSS': ['Jahresabschluss', 'Konzernabschluss'],
    'SEARCH': ['Suchbegriff(e)', 'OENACE.2008', 'Historische.Adressen', 'Historische.Firmenwortlaute'],
    'NUMERIC': ['Beschaeftigte', 'EGT', 'Umsatz', 'Kapital', 'Cashflow'],
    'ADMINISTRATIVE': ['Eigentuemer', 'Management', 'Beteiligungen', 'Wirtschaftlicher.Eigentuemer',
                       'Kontrollorgane'],
    'CONTACT': ['Bankverbindung', 'Internet-Adressen', 'E-Mail', 'Gewerbedaten', 'Ediktsdatei'],
    'NIEDERLASSUNG': ['Niederlassungen'],
    'RECHTSSTAAT': ['Rechtstatsachen'],
    'AGRARFOERDERUNG': ['EU-Agrarfoerderungen']
}

URL_DICT = {
    'login': "https://daten.compass.at/sso/login/process",  # URL to login to Compass
    'search': "https://daten.compass.at/FirmenCompass",  # url to post requests for company search
    'bilanz': "https://daten.compass.at/FirmenCompass/Bilanz",  # url to post requests for financial statements
    'compass': "https://daten.compass.at",
}

login_data = {  # data needed to login to Compass
    "targetUrl": "/compassDienste/startseite",
    "userDomain": "916F8E",
    "username": logindata.username,
    "password": logindata.password,
    "_saveLogin": "false",
    "loginSubmit": "Login"
}

bilanz_data = {  # data needed to search for financial statements
    "PageID": "916F8E",
    "onr": "",  # extract from company profile
    "id": "",  # extract from company profile, unique bilanz identifier
    "format": "htmltable",
    "erstellen": "Anzeigen"
}

search_data = {  # data needed to search for company
    "PageID": "916F8E",
    "p": "suche",
    "suchwort": "",  # change by company
    "suchartid": "",  # 'F' for name, 'A' for address
    "suchbldid": "Oe"
}
