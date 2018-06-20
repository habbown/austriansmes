from sqlalchemy import create_engine
from .settings import login_data, SQL_CONNECTION_STR, ENGINE_ADRESS, OUTPUT_DIR
import pyodbc
import pandas as pd
import os


class Tables:
    def __init__(self):
        self.connection = create_engine(ENGINE_ADRESS, encoding='utf-8').connect()
        self.sql_connection = pyodbc.connect(SQL_CONNECTION_STR)
        self.db_cursor = self.sql_connection.cursor()

    def get_table(self, table_name: str):
        return pd.read_sql(table_name,
                           self.connection,
                           index_col='index')

    def commit_to_table(self, table_name: str, data: pd.DataFrame,
                        how: str = 'append',
                        filename: str = None):
        data.to_sql(name=table_name,
                    con=self.sql_connection,
                    if_exists=how,
                    chunksize=10000)

        if filename:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            data.to_csv(path_or_buf=os.path.join(OUTPUT_DIR, filename),
                        encoding='utf-8')
