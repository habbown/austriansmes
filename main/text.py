from difflib import SequenceMatcher
import pandas as pd
from nltk.stem.snowball import GermanStemmer
from tqdm import tqdm


class StringHandler:
    _STEMMER = GermanStemmer()
    _P_SIMILARITY_THRESHOLD: float = 0.9

    def __init__(self, string_series: pd.Series):
        self._ds = string_series.str.lower()
        self.ds_origin = string_series

    def optimize(self):
        self.remove_noise()
        self.split_text()
        self.build_sentence()
        self.stem_words()
        # self.correct_spelling()

    def reset(self):
        self.ds = self.ds_origin.copy()

    # string manipulation
    ##################################

    def stem_words(self):
        self.ds = self.ds.apply(StringHandler.stem_sentence)

    def split_text(self):
        self.ds = self.ds.str.split(' ')

    def remove_noise(self):
        self.ds = self.ds.str.replace(r'[^a-zA-Z0-9]', ' ')
        # remove leftover isolated substrings that are not words/digits

    def build_sentence(self):
        self.ds = self.ds.apply(lambda x: ' '.join(word.strip() for word in x if word))

    # nlp manipulation
    ##################################

    def correct_spelling(self):
        uniques = self.get_unique_series
        uniques.apply(lambda x: list(i for i in uniques if i != x and SequenceMatcher(None, x, i).ratio() > 0.9))

    @classmethod
    def stem_sentence(cls, sentence: str, split_char: str = ' '):
        return ' '.join(cls._STEMMER.stem(word) for word in sentence.split(split_char))

    # properties
    ##################################

    @property
    def get_unique_series(self):
        return pd.Series(self.ds.unique()).sort_values().reset_index(drop=True)

    @property
    def ds(self):
        return self._ds

    @ds.setter
    def ds(self, ds: pd.Series):
        if isinstance(ds, pd.Series) and not ds.empty:
            self._ds = ds
        else:
            raise TypeError('Wrong variable type or empty series')


class TextCluster(StringHandler):
    def __init__(self, words: pd.Series, optimize: bool = True):
        super().__init__(string_series=words)

        if optimize:
            self.optimize()

    def cluster(self, by_column: str):
        term_dict = dict()

        for term in tqdm(iterable=self.get_unique_series,
                         desc=f'Grouping series ::: '):
            term_dict[term] = set()

            for sub_term in self.get_unique_series:
                if sub_term != term:
                    term_dict[term].update(sub_term)

        return term_dict

    @staticmethod
    def match_word_to_iterable(ref: str, iterable):
        return list(TextCluster.get_similarity(ref, word) for word in iterable if ref != word)

    @staticmethod
    def get_similarity(w1: str, w2: str):
        return SequenceMatcher(None, w1, w2).ratio()


class DBFormat:
    def __init__(self, table_name: str, df: pd.DataFrame):
        self.table_name = table_name
        self.table = df

    def get_formatted_table(self):
        df = self.table

        if self.table_name.lower().startswith('bilanz'):
            df = df.assign(date=None,
                           position=None)
            df.date = df.name.str.extract('([\d]{2}.[\d]{2}.[\d]{4})')
            df.name = df.name.str.extract('[\d]{2}.[\d]{2}.[\d]{4}_(.*)')
            df.name = df.name.str.lstrip('_')
            # filter by aktiva/passiva indices
            aktiva_index = df.name.str.contains('Aktiva')
            passiva_index = df.name.str.contains('Passiva')
            # set new position column entries by loc filter
            df.loc[aktiva_index, 'position'] = 'Aktiva'
            df.loc[aktiva_index, 'name'] = df.name.str.lstrip('Aktiva')
            df.loc[passiva_index, 'position'] = 'Passiva'
            df.loc[passiva_index, 'name'] = df.name.str.lstrip('Passiva')
            df.name = df.name.str.lstrip('_')

            df.dropna(subset={'position'},
                      inplace=True)

        elif self.table_name.lower().startswith('guv'):
            df = df.assign(year=None,
                           is_revenue=False)
            df.year = df.name.str.extract('([\d{4}]+)')
            df.name = df.name.str.extract('\d{4}_(.*)')
            df.name = df.name.str.lstrip('_')
            df.name = df.name.str.capitalize()

            for k, group in df.groupby(by=['FN', 'year']):
                revenue_hits = group.name.str.lower().str.contains('umsatz')

                if revenue_hits.any():
                    revenue_index = group[revenue_hits].iloc[0].name
                else:
                    revenue_index = group.value.iloc[:25].idxmax()

                df.at[revenue_index, 'is_revenue'] = True

        elif self.table_name.lower().startswith('search'):
            df = df.assign(code=None)

            if df.type.str.contains('OENACE.2008').any():
                oenace_index = df.type == 'OENACE.2008'
                split_content = df.loc[oenace_index, 'value'].str.split('(')
                codes = split_content.apply(lambda x: x[-1]).str.rstrip(')')
                values = split_content.apply(lambda x: '('.join(part for part in x[:-1]))

                df.loc[oenace_index, 'code'] = codes
                df.loc[oenace_index, 'value'] = values

        return df
