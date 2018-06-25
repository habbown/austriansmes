from main import logindata
import os

OUTPUT_DIR: str = os.path.join(os.path.dirname(os.getcwd()), 'output')

DATA_HOOVERS_REVENUE_AT_LEAST_70M = os.path.join(os.getcwd(),
                                                 'data',
                                                 'dnbhoovers_revenueatleast70m.csv')
TERMS_DICT = {
    'BasicData': ['FN', 'Firmenname', 'Compass-ID(ONR)', 'Firmenwortlaut', 'Adresse', 'DVR-Nummer', 'Gruendungsjahr',
                  'Ersteintragung', 'Fax', 'Geschaeftszweig.lt..Firmenbuch', 'Gericht', 'Gruendungsjahr',
                  'Korrespondenz', 'Letzte.Eintragung', 'OeNB.Identnummer', 'Rechtsform', 'Sitz.in',
                  'Taetigkeit.lt..Recherche', 'Telefon', 'UID', 'Korrespondenz', 'Produkte',
                  'Import', 'Export', 'Markennamen', 'geloescht', 'Gruendungsprivilegierung', 'Ringbeteiligung',
                  'Boersennotiert', 'Firmenwortlaut', 'Zusaetzliche.Angaben',
                  'Bankleitzahl(en)'],
    'GuVData': ['Jahresabschluss', 'Konzernabschluss'],
    'SearchData': ['Suchbegriff(e)', 'OENACE.2008', 'Historische.Adressen', 'Historische.Firmenwortlaute'],
    'NumericData': ['Beschaeftigte', 'EGT', 'Umsatz', 'Kapital', 'Cashflow'],
    'AdministrativeData': ['Eigentuemer', 'Management', 'Beteiligungen', 'Wirtschaftlicher.Eigentuemer',
                           'Kontrollorgane'],
    'ContactData': ['Bankverbindung', 'Internet-Adressen', 'E-Mail', 'Gewerbedaten', 'Ediktsdatei'],
    'Niederlassungen': ['Niederlassungen'],
    'Rechtstatsachen': ['Rechtstatsachen'],
    'BilanzData': ['Bilanz'],
    'EU_Agrarfoerderungen': ['EU-Agrarfoerderungen']
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

DB_NAME = "compassdata"
ENGINE_ADDRESS = ("mysql+pymysql://"
                  + logindata.sql_config['user']
                  + ":"
                  + logindata.sql_config['password']
                  + "@"
                  + logindata.sql_config['host']
                  + "/"
                  + DB_NAME
                  + "?charset=utf8")
SQL_CONNECTION_STR = (
        r'user=' + logindata.sql_config['user'] + r';' +
        r'password=' + logindata.sql_config['password'] + r';' +
        r'server=' + logindata.sql_config['host'] + r';' +
        r'port=' + logindata.sql_config['port'] + r';' +
        r'database=' + logindata.sql_config['database'] + ';' +
        r'driver={Devart ODBC Driver for MySQL};'
)
