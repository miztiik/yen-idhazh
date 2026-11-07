"""Which source chunks and evidence sentence does the retained BM25 retrieval order select?"""

import re
from collections.abc import Callable

from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.contracts.service_settings import CoveragePreparation
from summary_evaluator.source_coverage.prepare_text import split_sentences

# These nonempty token sentinels and word pattern are the legacy BM25 input format.
WORD_PATTERN = r"\w+"
EMPTY_DOCUMENT_TOKEN = "document"
EMPTY_QUERY_TOKEN = "text"
EMPTY_SENTENCE_TOKEN = "sentence"


class EvidenceRetriever:
    def __init__(
        self,
        chunks: list[str],
        settings: CoveragePreparation,
        warning: Callable[[CoverageWarningCode], None] | None = None,
    ) -> None:
        self.chunks, self.settings, self.warning = chunks, settings, warning
        self.use_bm25 = False
        try:
            from rank_bm25 import BM25Okapi

            tokenized = [re.findall(WORD_PATTERN, chunk.lower()) for chunk in self.chunks]
            tokenized = [tokens if tokens else [EMPTY_DOCUMENT_TOKEN] for tokens in tokenized]
            self.bm25 = BM25Okapi(tokenized)
            self.use_bm25 = True
        except Exception:
            self._warn("RETRIEVAL_FALLBACK")

    def _warn(self, code: CoverageWarningCode) -> None:
        if self.warning is not None:
            self.warning(code)

    def retrieve_top_k(self, sentence: str) -> list[tuple[int, str]]:
        count = self.settings.top_chunks
        if len(self.chunks) <= count:
            return list(enumerate(self.chunks))
        tokens = re.findall(WORD_PATTERN, sentence.lower()) or [EMPTY_QUERY_TOKEN]
        if self.use_bm25:
            try:
                scores = self.bm25.get_scores(tokens)
                top_indices = sorted(
                    range(len(scores)), key=lambda index: scores[index], reverse=True
                )[:count]
            except Exception:
                self._warn("RETRIEVAL_FALLBACK")
                top_indices = list(range(min(count, len(self.chunks))))
        else:
            token_set = set(tokens)
            scores = [
                len(token_set.intersection(set(re.findall(WORD_PATTERN, chunk.lower()))))
                for chunk in self.chunks
            ]
            top_indices = sorted(
                range(len(scores)), key=lambda index: scores[index], reverse=True
            )[:count]
        return [(index, self.chunks[index]) for index in top_indices]

    def find_best_sentence(self, sentence: str, chunk_text: str) -> str:
        sentences = split_sentences(chunk_text, self.settings, self.warning)
        if not sentences:
            return chunk_text[: self.settings.evidence_fallback_chars]
        if len(sentences) == 1:
            return sentences[0]
        try:
            from rank_bm25 import BM25Okapi

            tokenized = [re.findall(WORD_PATTERN, item.lower()) for item in sentences]
            tokenized = [tokens if tokens else [EMPTY_SENTENCE_TOKEN] for tokens in tokenized]
            sent_bm25 = BM25Okapi(tokenized)
            query_tokens = re.findall(WORD_PATTERN, sentence.lower())
            scores = sent_bm25.get_scores(query_tokens)
            best_index = int(max(range(len(scores)), key=lambda index: scores[index]))
            if scores[best_index] > self.settings.evidence_min_score:
                return sentences[best_index]
        except Exception:
            self._warn("EVIDENCE_SENTENCE_FALLBACK")
        return sentences[0]
