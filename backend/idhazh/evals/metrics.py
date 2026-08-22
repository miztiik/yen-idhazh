"""The counterweights, computed without a model.

Faithfulness alone rewards copying: a summary that quotes the source verbatim
scores nearly perfectly and has summarized nothing. These metrics are the other
half, and they are deliberately model-free - they are pure string and token
work, they run on every item forever, and they are what still measures the
pipeline if the faithfulness scorer turns out not to fit the runner.

Two of them see defects nothing else here can:

- `unsupported_numbers` catches a *wrong* number. Recall-style metrics see an
  omitted number and are structurally blind to an invented one, and a wrong
  figure is the most damaging thing a news summary can carry.
- `hedge_dropped` catches a rumour becoming a fact. A faithfulness scorer marks
  it generously, because the entity and the relation are both present - only the
  uncertainty went missing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Final

from idhazh.contracts.app_config import EvaluationConfig

#: Bumped whenever any definition below changes. Part of the derived
#: `scorer_version`, so a ledger row keeps meaning what it meant when written.
METRICS_VERSION: Final = "1"

LEAD_SENTENCES: Final = 3
_NGRAM: Final = 4

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")
# Only numbers a summary could plausibly get wrong. Single digits are usually
# spelled out or trivially present, and checking them manufactures false alarms.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CAPITALISED_RUN = re.compile(r"\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*)*")

# Words that start an English sentence far more often than they name anything,
# plus the calendar - a summary that dropped the day of the week dropped nothing.
_NOT_AN_ENTITY: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "but",
        "by",
        "for",
        "from",
        "he",
        "her",
        "his",
        "however",
        "in",
        "it",
        "its",
        "meanwhile",
        "of",
        "on",
        "one",
        "she",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "under",
        "we",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "with",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
)

#: Closed lexicon. A source that hedges and a summary that does not is a rumour
#: published as a fact. Multi-word entries are matched as phrases.
HEDGE_TERMS: Final[tuple[str, ...]] = (
    "according to",
    "alleged",
    "allegedly",
    "apparently",
    "claimed",
    "claims",
    "could",
    "expected to",
    "is said to",
    "may",
    "might",
    "plans to",
    "potential",
    "purportedly",
    "reportedly",
    "reported to",
    "rumored",
    "rumoured",
    "seemingly",
    "sources say",
    "unconfirmed",
    "would",
)
_HEDGE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in HEDGE_TERMS) + r")\b", re.IGNORECASE
)


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def lead(text: str, sentences: int = LEAD_SENTENCES) -> str:
    """Journalism puts the who, the what and the how-much in the first lines."""
    return " ".join(_SENTENCE_SPLIT.split(text.strip())[:sentences])


def compression(summary: str, source: str) -> float:
    """Summary length over source length. Recorded, never flagged.

    At a fixed output budget this measures the article's length rather than the
    summary's quality, so a band on it would flag every short article forever.
    """
    total = word_count(source)
    return word_count(summary) / total if total else 0.0


def _ngrams(tokens: Sequence[str], size: int = _NGRAM) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def _normalise(tokens: Iterable[str]) -> list[str]:
    return [token.lower().strip(".,") for token in tokens]


def extractiveness(summary: str, source: str) -> float:
    """Share of the summary's 4-grams that appear verbatim in the source.

    Not a longest-common-subsequence: subsequence matching permits arbitrary
    gaps, so function words match in order in almost any document, which puts a
    stopword floor under the score and moves it with length rather than with
    copying.
    """
    summary_tokens = _normalise(words(summary))
    if len(summary_tokens) < _NGRAM:
        return 0.0
    summary_grams = _ngrams(summary_tokens)
    source_grams = _ngrams(_normalise(words(source)))
    return len(summary_grams & source_grams) / len(summary_grams)


def verbatim_run(summary: str, source: str) -> float:
    """Longest unbroken copied stretch, as a share of the summary.

    This is the one that actually names copying. A summary can score low on
    4-gram precision while still lifting one whole paragraph.
    """
    summary_tokens = _normalise(words(summary))
    if not summary_tokens:
        return 0.0
    source_tokens = _normalise(words(source))
    source_index: dict[str, list[int]] = {}
    for position, token in enumerate(source_tokens):
        source_index.setdefault(token, []).append(position)

    longest = 0
    for start in range(len(summary_tokens)):
        if len(summary_tokens) - start <= longest:
            break
        for origin in source_index.get(summary_tokens[start], ()):
            length = 0
            while (
                start + length < len(summary_tokens)
                and origin + length < len(source_tokens)
                and summary_tokens[start + length] == source_tokens[origin + length]
            ):
                length += 1
            longest = max(longest, length)
    return longest / len(summary_tokens)


def _checkable_numbers(text: str) -> set[str]:
    """Normalised so 1,320 and 1320 and 1320.0 are the same number."""
    found: set[str] = set()
    for raw in _NUMBER.findall(text):
        cleaned = raw.replace(",", "")
        if "." in cleaned:
            cleaned = cleaned.rstrip("0").rstrip(".")
        if len(cleaned.replace(".", "")) >= 2:
            found.add(cleaned)
    return found


def unsupported_numbers(summary: str, source: str) -> int:
    """Numbers the summary asserts that appear nowhere in the full source.

    Checked against the full article, never the truncated text: a figure the
    model could not have seen is still a figure that is in the article.
    """
    return len(_checkable_numbers(summary) - _checkable_numbers(source))


def _entities(text: str) -> set[str]:
    """Capitalised runs, minus the ones English capitalises for grammar.

    A single capitalised word opening a sentence is not evidence of a name -
    every sentence has one. Requiring it to appear mid-sentence somewhere lets
    the document itself say whether the capital is structural or nominal.
    """
    named: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        stripped = sentence.strip()
        for match in _CAPITALISED_RUN.finditer(stripped):
            run = match.group().strip(" .,").lower()
            if not run or run in _NOT_AN_ENTITY:
                continue
            if match.start() == 0 and " " not in run:
                continue
            named.add(run)
    return named


def lead_coverage(summary: str, source: str, sentences: int = LEAD_SENTENCES) -> float:
    """Survival of the lead's names and figures into the summary.

    Recall over the WHOLE source would be a constant near 0.12 - a 3,500-word
    article carries far more entities than 150 words can hold, for a good
    summary and a bad one alike. Anchoring on the lead gives the metric dynamic
    range and points it at the defect that matters: a summary that dropped the
    story.

    Carriage is checked by presence in the summary, not by re-extracting from
    it: the question is whether the summary mentioned the thing, and an entity
    that happens to open the summary's second sentence still counts.
    """
    opening = lead(source, sentences)
    salient_names = _entities(opening)
    salient_numbers = _checkable_numbers(opening)
    total = len(salient_names) + len(salient_numbers)
    if not total:
        return 1.0
    haystack = summary.lower()
    kept = sum(1 for name in salient_names if name in haystack)
    kept += len(salient_numbers & _checkable_numbers(summary))
    return kept / total


def hedge_dropped(summary: str, source: str, sentences: int = LEAD_SENTENCES) -> bool:
    """The source hedged its lead and the summary asserted it flat."""
    return bool(_HEDGE.search(lead(source, sentences))) and not _HEDGE.search(summary)


def scorer_version(
    *, scorer_id: str, scorer_revision: str, weights_sha256: str, evaluation: EvaluationConfig
) -> str:
    """Derived, never hand-typed, and readable years later.

    A hand-bumped string is wrong within a quarter and every row after it
    becomes uninterpretable. A bare digest would be interpretable by nobody, so
    this spells its components instead of hashing them.
    """
    return ";".join(
        (
            f"{scorer_id}@{scorer_revision[:8]}",
            f"weights-{weights_sha256[:8]}",
            f"metrics-{METRICS_VERSION}",
            f"bands={evaluation.band_high_min:.2f}/{evaluation.band_medium_min:.2f}",
        )
    )
