from sqlalchemy import create_engine
from .settings import login_data, SQL_CONNECTION_STR, ENGINE_ADRESS
import pyodbc
import pandas as pd


class Tables:
    def __init__(self):
        self.connection = create_engine(ENGINE_ADRESS, encoding='utf-8').connect()
        self.sql_connection = pyodbc.connect(SQL_CONNECTION_STR)
        self.db_cursor = self.sql_connection.cursor()

    def fetch_table(self, table_name: str):
        df = pd.read_sql(table_name,
                         self.connection,
                         index_col='index')

    def commit_to_table(self, table_name: str, data):
        pass
