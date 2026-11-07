"""How does the legacy method prepare complete sentences, overlapping chunks and its macro view?"""

import re
from collections.abc import Callable

from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.contracts.service_settings import CoveragePreparation

# This punctuation pattern and omission marker are the retained legacy text format.
SENTENCE_FALLBACK_PATTERN = r"(?<=[.!?])\s+"
MACRO_OMISSION_MARKER = "[...]"


def split_sentences(
    text: str,
    settings: CoveragePreparation,
    warning: Callable[[CoverageWarningCode], None] | None = None,
) -> list[str]:
    try:
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(text)
    except Exception:
        if warning is not None:
            warning("SENTENCE_TOKENIZER_FALLBACK")
        sentences = re.split(SENTENCE_FALLBACK_PATTERN, text)
    valid = [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) > settings.summary_min_sentence_chars
    ]
    return valid if valid else ([text.strip()] if text.strip() else [settings.empty_sentence])


def chunk_document(text: str, settings: CoveragePreparation) -> list[str]:
    words = text.split()
    if len(words) <= settings.chunk_words:
        return [text] if text.strip() else [settings.empty_document]
    chunks = []
    index = 0
    while index < len(words):
        chunks.append(" ".join(words[index : index + settings.chunk_words]))
        if index + settings.chunk_words >= len(words):
            break
        index += settings.chunk_words - settings.stride_words
    return chunks if chunks else [settings.empty_document]


def extract_macro_skeleton(text: str, settings: CoveragePreparation) -> str:
    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if len(paragraph.strip()) > settings.macro_min_paragraph_chars
    ]
    if not paragraphs:
        return text[: settings.macro_no_paragraph_chars] if text else settings.empty_macro
    if len(paragraphs) <= settings.macro_complete_paragraphs:
        return "\n\n".join(paragraphs)[: settings.macro_few_paragraph_chars]
    combined = "\n\n".join(
        [
            *paragraphs[: settings.macro_lead_paragraphs],
            MACRO_OMISSION_MARKER,
            *paragraphs[-settings.macro_tail_paragraphs :],
        ]
    )
    words = combined.split()
    return (
        " ".join(words[: settings.macro_words])
        if len(words) > settings.macro_words
        else combined
    )
