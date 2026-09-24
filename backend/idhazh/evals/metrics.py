"""The counterweights, computed without a model.

Faithfulness alone rewards copying: a summary that quotes the source verbatim
scores nearly perfectly and has summarized nothing. These metrics are the other
half, and they are deliberately model-free - they are pure string and token
work, they run on every item forever, and they are what still measures the
pipeline if the faithfulness scorer turns out not to fit the runner.

Three of them see defects nothing else here can:

- `unsupported_numbers` catches a *wrong* number. Recall-style metrics see an
  omitted number and are structurally blind to an invented one, and a wrong
  figure is the most damaging thing a news summary can carry.
- `hedge_dropped` catches a rumour becoming a fact. A faithfulness scorer marks
  it generously, because the entity and the relation are both present - only the
  uncertainty went missing.
- `self_repetition` catches a summary that says the same thing twice. It is the
  only measure here that reads the summary against itself, and it is the only
  defect that scores BETTER on every other metric the worse it gets: a repeated
  sentence is still perfectly supported by the article.

The two densities are the odd pair here: they score the ARTICLE, not our summary
of it. Everything else asks whether we were faithful to the source. They ask what
the source was worth - whether it named who told it, or only said a thing may
happen. A perfectly faithful summary of an unsourced rumour is still an unsourced
rumour, and no faithfulness metric can say so, because faithfulness to a fragile
article is exactly what it measures.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Final

from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.evals.hhem import CHUNK_ANCHOR

#: Bumped whenever the set of definitions below changes what a ledger row means.
#: Part of the derived `scorer_version`, so a row keeps meaning what it meant
#: when written.
#:
#: It did not move for `self_repetition` on 2026-08-26, for the anchored
#: faithfulness window on 2026-08-28, or for `new_fact_rate`. Each of those
#: added a column nothing bands or derives from, so every row already written
#: still said exactly what it said, and moving the stamp would have restarted
#: the ten-run-day count `docs/concepts/evaluation.md` requires before any
#: threshold moves - to record a fact no threshold reads.
#:
#: It moves to `4` on 2026-09-24, because this time columns LEFT. `coverage` and
#: `new_fact_rate` are gone and `coherence` and `semantic_coverage` are new, so
#: a row cannot be read as if it came from the same set of instruments. The
#: count restarts anyway in the same change - `scorer_version` loses its `lead=`
#: component with the band input behind it - so the stamp is what names why.
#: Authority: Andre, Fowler.
METRICS_VERSION: Final = "4"

#: How many of the article's most-repeated content words `semantic_coverage`
#: asks the summary about. A constant rather than a `config/` knob, like
#: `_NGRAM` and `LEAD_SENTENCES` above and below it: moving it does not tune a
#: threshold, it changes what a committed cell MEANS, and the machinery for
#: that is `METRICS_VERSION` rather than a config edit two rows can straddle.
#: 20 was measured against 1,490 committed article-and-summary pairs on
#: 2026-09-24 - see `docs/architecture/publishing/autotune-summary-quality.md`.
SALIENT_TERMS: Final = 20

LEAD_SENTENCES: Final = 3
_NGRAM: Final = 4

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")
# Only numbers a summary could plausibly get wrong. Single digits are usually
# spelled out or trivially present, and checking them manufactures false alarms.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Words English uses for grammar rather than for naming anything, plus the
# calendar - a summary that dropped the day of the week dropped nothing.
# `semantic_coverage` subtracts these before it asks what the article kept
# returning to, because an article returns to "the" more than to any name in it.
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

# The two halves of what used to be one flat list of hedges. They read alike and
# they do opposite work, which is why splitting them is worth a metrics version.
#
# "Reportedly" and "may" are both hedges, and a summary that drops either has
# published a rumour as a fact - so `hedge_dropped` wants them in one bucket and
# still gets them in one bucket. But asked about the ARTICLE they say opposite
# things. "According to the ministry" is a claim you can go and check. "Could
# happen" is a claim nobody has made yet. Counting them together produces one
# number that rises for a well-sourced report and for pure speculation alike,
# which is a number that means nothing.

#: Reportative markers: the article is saying how it knows. These are the
#: evidence a claim rests on, not a weakness in it.
EVIDENTIAL_TERMS: Final[tuple[str, ...]] = (
    "according to",
    "alleged",
    "allegedly",
    "claimed",
    "claims",
    "is said to",
    "purportedly",
    "reported to",
    "reportedly",
    "sources say",
)

#: Epistemic markers: the claim itself is unresolved, future or merely possible.
#: Nobody is being cited - the article is telling you the thing may not be so.
#: "Rumored" and "unconfirmed" sit here and not above: they name the absence of a
#: source, which is the opposite of naming one.
SPECULATIVE_TERMS: Final[tuple[str, ...]] = (
    "apparently",
    "could",
    "expected to",
    "may",
    "might",
    "plans to",
    "potential",
    "rumored",
    "rumoured",
    "seemingly",
    "unconfirmed",
    "would",
)

#: Both halves, derived and never typed twice. A source that hedges and a summary
#: that does not is a rumour published as a fact, whichever kind of hedge went
#: missing. Multi-word entries are matched as phrases.
HEDGE_TERMS: Final[tuple[str, ...]] = tuple(sorted(EVIDENTIAL_TERMS + SPECULATIVE_TERMS))


def _lexicon(terms: Sequence[str]) -> re.Pattern[str]:
    """Whole words only, so "claims" does not fire inside "claimsmanship"."""
    return re.compile(
        r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")\b", re.IGNORECASE
    )


_HEDGE = _lexicon(HEDGE_TERMS)
_EVIDENTIAL = _lexicon(EVIDENTIAL_TERMS)
_SPECULATIVE = _lexicon(SPECULATIVE_TERMS)


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


def self_repetition(summary: str) -> float:
    """How much of the summary is a phrase the summary already used.

    Every other n-gram measure in this file reads our summary against the
    SOURCE. None of them can see a summary that repeats itself, because a
    repeated sentence is still perfectly supported by the article. This is the
    one defect that looks more faithful the worse it gets.

    A model in a loop is what makes it possible, and the temperature decides how
    a loop ends rather than whether one starts. At temperature 0 there is no
    sampling noise to break out of one, so the same clause repeats until the
    budget runs out; Qwen's own model card warns that greedy decoding "can lead
    to performance degradation and endless repetitions" in thinking mode, which
    is the same failure named from the other side. Above 0 a loop can still form
    and is likelier to end on its own, so this column stays exactly as useful.

    Zero is a summary in which every four-word window is different, which is
    what ordinary prose looks like. The number rises toward one as more of the
    text repeats a window it has already used. A four-word phrase said three
    times instead of once puts two windows on repeat, so a 100-word summary
    reads 0.02; a whole sentence said twice reads far higher, because every
    window inside it repeats. Recorded only - no band reads it
    (`docs/concepts/evaluation.md`).

    The same window size as `extractiveness`, deliberately. Two n-gram sizes in
    one file are two numbers a reader has to reconcile.
    """
    tokens = _normalise(words(summary))
    windows = len(tokens) - _NGRAM + 1
    if windows < 1:
        return 0.0
    return 1.0 - len(_ngrams(tokens)) / windows


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


def semantic_coverage(summary: str, source: str, terms: int = SALIENT_TERMS) -> float | None:
    """Share of the article's most-repeated content words the summary carried.

    **Lexical, despite the column's name.** It compares word forms, so a summary
    saying "the chipmaker" where the article said "Nvidia" is counted as a miss,
    and so is "cut rates" against "rate reduction".

    The reference is the `terms` content words the article used most, which is
    what gives the number any range. Recall against the whole article is the
    shape that does not work, and it was measured rather than argued: over 1,490
    committed pairs on 2026-09-24, whole-article 4-gram recall sat at a median of
    0.017 with half of all summaries between 0.008 and 0.036, and whole-article
    unigram recall correlated 0.93 with `compression`, which is a length column.
    A fixed reference of 20 reads 0.60 at the median with 0.35 to 0.85 covering
    the middle 90 percent, and its rank correlation with article length is -0.09.
    See `docs/architecture/publishing/autotune-summary-quality.md`.

    What it gives up for that: it cannot see a fact the article mentioned once
    and the summary dropped. It only asks whether the summary carried what the
    article kept returning to.

    Ties are broken alphabetically and not by whichever word the counter happened
    to meet first, or the word on the boundary would be chosen by dict insertion
    order and two runs over one article could disagree.

    The summary side is the raw token set: presence is the question, the same way
    `hedge_dropped` asks it, so a summary is not required to repeat a term to be
    counted as carrying it.

    None when the article yielded no content word at all. That is an article
    nobody could measure, which is a different fact from a summary that carried
    nothing.
    """
    counts = Counter(
        token for token in _normalise(words(source)) if token and token not in _NOT_AN_ENTITY
    )
    ranked = sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:terms]
    if not ranked:
        return None
    reference = {term for term, _ in ranked}
    return len(reference & set(_normalise(words(summary)))) / len(reference)


def hedge_dropped(summary: str, source: str, sentences: int = LEAD_SENTENCES) -> bool:
    """The source hedged its lead and the summary asserted it flat."""
    return bool(_HEDGE.search(lead(source, sentences))) and not _HEDGE.search(summary)


def _density(pattern: re.Pattern[str], text: str) -> float:
    """Markers as a share of the text's words.

    A share and not a count, because a count is mostly a measure of length: a
    3,000-word feature carries more of everything than a wire brief, and the
    question is how thick the marking is, not how long the article is.
    """
    total = word_count(text)
    if not total:
        return 0.0
    return len(pattern.findall(text)) / total


def evidential_density(source: str) -> float:
    """How often the article says where a claim came from.

    Over the whole article, and a rate rather than a recall - so the denominator
    can be the honest one. The lead is exactly where the style guide puts an
    attribution, so anchoring there would measure the convention instead of the
    reporting.

    Read it against `speculative_density`, never alone. High on both is normal
    for a court report. High on speculation and near zero on attribution is an
    article built out of what might happen, told by nobody.
    """
    return _density(_EVIDENTIAL, source)


def speculative_density(source: str) -> float:
    """How much of the article has not happened yet, or is not confirmed.

    Not a defect on its own. A forecast is a legitimate story, and a preview of
    a launch is honest work. It is a defect in company: see
    `evidential_density`.
    """
    return _density(_SPECULATIVE, source)


# --- the two that score the run rather than a summary ------------------------
#
# Everything above reads one summary or one article. These two read a day's own
# counts, and they belong here for the reason the two densities do: model-free
# arithmetic that says whether the pipeline is still doing its job. They are not
# scorers, no eval-ledger column carries them, and `METRICS_VERSION` does not
# move for them - the same reason it did not move for `self_repetition` or
# `compression`.
#
# Both return `None` on an empty denominator. A rate over nothing is not zero:
# zero is a day where every chartable article went undrawn, and a day with no
# chartable article on it is a different fact.


def extractable_but_unused_rate(
    *, chartable_published: int, chartable_charted: int
) -> float | None:
    """Of the published articles whose numbers could have made a chart, how many got none.

    The one number that separates a planner regression from an extractor that
    started missing numbers. Without it the two are the same fall in published
    charts, and they have different fixes: this rising means the planner is
    passing over material it was given, and `DayExtraction.chartable` falling
    instead means the pass stopped finding the material at all.

    Keyword-only because both arguments are counts of the same kind, and a
    positional call that swapped them would return a plausible rate.
    """
    if chartable_published <= 0:
        return None
    return (chartable_published - chartable_charted) / chartable_published


def span_integrity_rate(*, items: int, passed: int) -> float | None:
    """Of the articles the candidate pass ran on, how many re-sliced every span.

    The reporting half of the span-drift invariant
    (`docs/architecture/extraction/elements.md`). A span that stopped pointing
    where it did degrades that one item and never the build, so this is what
    makes the refusal visible: nothing else would show a run whose own
    arithmetic had broken on every article.
    """
    if items <= 0:
        return None
    return passed / items


def scorer_version(
    *, scorer_id: str, scorer_revision: str, weights_sha256: str, evaluation: EvaluationConfig
) -> str:
    """Derived, never hand-typed, and readable years later.

    A hand-bumped string is wrong within a quarter and every row after it
    becomes uninterpretable. A bare digest would be interpretable by nobody, so
    this spells its components instead of hashing them.

    Order is identity, then geometry, then the cuts. `window=` names the premise
    the number was measured over, which is part of the instrument and not part
    of the decision made from it.

    `bands=` used to carry a `lead=` component too, naming the lead-coverage
    floor a high band had to clear. That input is retired, so the string no
    longer names it - which moves every row's `scorer_version` once and restarts
    the run-day count in `evaluation.label_min_run_days`.
    """
    return ";".join(
        (
            f"{scorer_id}@{scorer_revision[:8]}",
            f"weights-{weights_sha256[:8]}",
            f"metrics-{METRICS_VERSION}",
            f"window={evaluation.chunk_words}/{evaluation.chunk_overlap_words}/{CHUNK_ANCHOR}",
            f"bands={evaluation.band_high_min:.2f}/{evaluation.band_medium_min:.2f}",
        )
    )
