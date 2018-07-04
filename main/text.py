from difflib import SequenceMatcher
import pandas as pd
from nltk.stem.snowball import GermanStemmer
from tqdm import tqdm


class StringHandler:
    _STEMMER = GermanStemmer()

    def __init__(self, string_series: pd.Series):
        self.ds = string_series.str.lower()
        self.ds_origin = self.ds.copy()

    def optimize(self):
        self.remove_noise()
        self.split_text()
        self.build_sentence()
        self.stem_words()
        # self.correct_spelling()

    def recover(self):
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
        self.ds = None

    @classmethod
    def stem_sentence(cls, sentence: str, split_char: str = ' '):
        return ' '.join(cls._STEMMER.stem(word) for word in sentence.split(split_char))

    @property
    def get_unique_series(self):
        return pd.Series(self.ds.unique).sort_values().reset_index(drop=True)


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
