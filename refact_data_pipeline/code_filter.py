import re
from collections import Counter
from string import ascii_letters
from typing import Optional, List

from kshingle import shingleseqs_list
from refact_data_pipeline import DatasetOpts
from refact_data_pipeline.utils.text_extraction import get_nl_ratio


class TheStackFilter:
    def __init__(
            self,
            inner_filter,
            dataopts: DatasetOpts,
    ):
        self.inner_filter = inner_filter
        self.dataopts = dataopts
        self.word_splitter = re.compile(r'[\s,;!.\\/=:?\-><]+')
        self.excluded_languages = {'Text', 'Jupyter Notebook', 'TeX'}

    def _filter(self, text: str, language: str) -> Optional[str]:
        if language in self.excluded_languages:
            return "excluded_language"

        lower_text = text.lower()
        words = list(filter(lambda w: len(w) > 1 or w.isalnum(), self.word_splitter.split(lower_text)))

        # words count filter
        if len(words) < 5:
            return "too_short_text"

        # mean word length filter
        mean_word_length = sum(map(len, words)) / len(words)
        if mean_word_length > 25:
            return "long_mean_word_length"

        # alpha to num ration filter
        alpha_num_ratio = len([c for c in text if c.isdigit()]) / len(text)
        if alpha_num_ratio > 0.3:
            return "too_much_digits"

        # english text filter
        words_ascii = list(filter(str.isascii, words))
        if len(words_ascii) / len(words) < 0.5:
            return "too_much_non_ascii"

        # generated code filter
        if any(w in lower_text for w in ["generated code", "autogenerated", "auto-generated"]):
            return "generated_code"

        # ngrams frequency filter
        def _top_n_gram_frequency(words: List[str], n: int) -> float:
            shingles_counter = Counter(map(tuple, shingleseqs_list(words, klist=[n])[0]))
            if shingles_counter:
                return max(shingles_counter.values()) / len(words)
            return 0

        for n, freq in [(2, 0.2), (3, 0.18), (4, 0.16)]:
            if _top_n_gram_frequency(words, n) > freq:
                return f"frequent_{n}_grams"

        lines = [line for line in text.splitlines() if len(line) > 0]
        if max(map(len, lines)) > 1000:
            return "too_long_max_line_length"

        avg_line_length = sum(map(len, lines)) / len(lines)
        if avg_line_length > 150:
            return "too_long_avg_line_length"
        elif avg_line_length < 5:
            return "too_short_avg_line_length"

        if '<?xml version=' in text[:100]:
            return "xml_tag"

        # try:
        #     comments_ratio = get_nl_ratio(text, language.lower())
        #     if comments_ratio > 0.9:
        #         return "too_high_comments_ratio"
        # except Exception as e:
        #     print(e)

        return None

    def __iter__(self):
        internal_stats = dict(
            excluded_language=0,
            too_short_text=0,
            long_mean_word_length=0,
            too_much_digits=0,
            too_much_non_ascii=0,
            generated_code=0,
            frequent_2_grams=0,
            frequent_3_grams=0,
            frequent_4_grams=0,
            too_long_max_line_length=0,
            too_long_avg_line_length=0,
            too_short_avg_line_length=0,
            xml_tag=0,
            too_high_comments_ratio=0
        )
        for sample in self.inner_filter:
            filter_result = self._filter(sample['text'], sample.get('lang', ''))
            if filter_result is not None:
                internal_stats[filter_result] += 1
            else:
                stats = {**sample.pop('stats', dict()), **internal_stats}
                yield {**sample, 'stats': stats}
