"""Which fixed safe observations identify retained legacy preparation fallbacks?"""

from typing import Literal

CoverageWarningCode = Literal[
    "SENTENCE_TOKENIZER_FALLBACK",
    "RETRIEVAL_FALLBACK",
    "EVIDENCE_SENTENCE_FALLBACK",
]
