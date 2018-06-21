import logindata
import pyodbc
from sqlalchemy import create_engine
import pandas as pd

DB_NAME = "compassdata"
engine_address = ("mysql+pymysql://" + logindata.sql_config['user'] + ":" + logindata.sql_config['password'] +
                  "@" + logindata.sql_config['host'] + "/" + DB_NAME + "?charset=utf8")
engine = create_engine(engine_address, encoding='utf-8')
con = engine.connect()

connStr = (
        r'user=' + logindata.sql_config['user'] + r';' +
        r'password=' + logindata.sql_config['password'] + r';' +
        r'server=' + logindata.sql_config['host'] + r';' +
        r'port=' + logindata.sql_config['port'] + r';' +
        r'database=' + logindata.sql_config['database'] + ';' +
        r'driver={Devart ODBC Driver for MySQL};'
)

cnxn = pyodbc.connect(connStr)
crsr = cnxn.cursor()

crsr.execute("SHOW TABLES")
table_list = [row[0] for row in crsr.fetchall()]

if 'BilanzDataFormatted' not in table_list:
    df = pd.read_sql_table('BilanzData', con, index_col='index')
    content_indices = df.name.str.contains('Aktiva|Passiva')
    df_bilanz_only_content = df[content_indices]
    # allocate new columns
    df_bilanz_only_content = df_bilanz_only_content.assign(date=None,
                                                           position=None)
    # show char position value counts through table
    print(df_bilanz_only_content.name.str.find('__').value_counts(normalize=True))
    # parse and assign substring 11:21 of column name to column date
    df_bilanz_only_content.date = df_bilanz_only_content.name.str[11:21]
    # strip underscores, date, and noise and update name column
    df_bilanz_only_content.name = df_bilanz_only_content.name.str[23:]
    # set values for position column
    aktiva_index = df_bilanz_only_content.name.str.contains('Aktiva')
    passiva_index = df_bilanz_only_content.name.str.contains('Passiva')
    df_bilanz_only_content.loc[aktiva_index, 'position'] = 'Aktiva'
    df_bilanz_only_content.loc[passiva_index, 'position'] = 'Passiva'
    # clean/reformat name column
    df_bilanz_only_content.loc[aktiva_index, 'name'] = df_bilanz_only_content.loc[aktiva_index, 'name'].str[7:]
    df_bilanz_only_content.loc[passiva_index, 'name'] = df_bilanz_only_content.loc[passiva_index, 'name'].str[8:]

    df_bilanz_only_content.to_sql(name="BilanzDataFormatted", con=con, chunksize=10000)

if 'GuVDataFormatted' not in table_list:
    df = pd.read_sql_table('GuVData', con, index_col='index')
    df = df.assign(year=None)
    df.year = df.name.str[52:56]
    # caution with stripping, some rows contain only single underscores..
    df.name = df.name.str[56:].str.lstrip('_')
    # fix upper/lowercase
    df.name = df.name.str.capitalize()

    df.to_sql(name="GuVDataFormatted", con=con, chunksize=10000)
