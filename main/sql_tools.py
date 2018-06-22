from sqlalchemy import create_engine
from .settings import SQL_CONNECTION_STR, ENGINE_ADRESS, OUTPUT_DIR
import pyodbc
import pandas as pd
import numpy as np
from .tools import timer
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

    @timer
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

    def sample(self, table_name: str, n_companies: int, sort_by: str, multi_index: list = None,
               n: int = 500):
        """Samples from a given table_name and returns a formatted DataFrame"""
        df = self.get_table(table_name=table_name)
        sampled_companies = np.random.choice(df.FN.unique(), n_companies)
        df_sampled_sorted = df[df.isin(sampled_companies)].sample(n=n).sort_values(sort_by)

        return df_sampled_sorted.set_index(multi_index) if multi_index else df_sampled_sorted
