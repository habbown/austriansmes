from difflib import SequenceMatcher
import pandas as pd
from nltk.stem.snowball import GermanStemmer
from tqdm import tqdm


class TextClean:
    _STEMMER = GermanStemmer()

    def __init__(self, words: pd.Series, optimize: bool = True):
        self.words = words

        if optimize:
            self.words = self.optimize()

    def optimize(self):
        """Runs a series of cleaning, stemming, and optimizing processes"""
        ds_cleaned = TextClean.remove_noise(series=self.words)
        ds_split = TextClean.split_text(series=ds_cleaned)
        ds_reconstructed = TextClean.reconstruct_sentence(series=ds_split)

        return TextClean.remove_stopwords(series=ds_reconstructed)

    # nlp manipulation
    ##################################

    @staticmethod
    def spell_correction(series: pd.Series):
        return

    @classmethod
    def stem_text(cls, series: pd.Series):
        return series.apply(lambda x: ' '.join(cls._STEMMER.steam(i) for i in x.split(' ')))

    # string manipulation
    ##################################

    @staticmethod
    def split_text(series: pd.Series):
        return series.str.split(' ')

    @staticmethod
    def remove_noise(series: pd.Series):
        return series.str.replace(r'[^a-zA-Z0-9]', ' ')

    @staticmethod
    def reconstruct_sentence(series: pd.Series):
        return series.apply(lambda x: ' '.join(word.strip() for word in x if word))

    @staticmethod
    def remove_stopwords(series: pd.Series):
        return series


class TextCluster(TextClean):
    def group_words(self):
        unique_terms = self.words.str.lower().unique()
        term_dict = dict()

        for term in tqdm(iterable=unique_terms,
                         desc=f'Grouping series ::: '):
            term_dict[term] = set()

            for sub_term in unique_terms:
                if sub_term != term:
                    term_dict[term].update(sub_term)

        return term_dict

    @staticmethod
    def match_word_to_iterable(ref: str, iterable):
        return list(TextCluster.get_similarity(ref, word) for word in iterable if ref != word)

    @staticmethod
    def get_similarity(w1: str, w2: str):
        return SequenceMatcher(None, w1, w2).ratio()
