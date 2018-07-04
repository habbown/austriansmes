from difflib import SequenceMatcher
import pandas as pd
import nltk


class TextClean:
    @staticmethod
    def optimize_sentence(words: pd.Series):
        ds_cleaned = TextClean.remove_noise(series=words)
        ds_split = TextClean.split_text(series=ds_cleaned)
        ds_reconstructed = TextClean.reconstruct_sentence(series=ds_split)

        return TextClean.remove_stopwords(series=ds_reconstructed)

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
        return


class TextCluster:
    @staticmethod
    def match_word_to_iterable(ref: str, iterable):
        return list(TextCluster.get_similarity(ref, word) for word in iterable if ref != word)

    @staticmethod
    def get_similarity(w1: str, w2: str):
        return SequenceMatcher(None, w1, w2).ratio()
