"""Store measured values and judgements with their sources and remeasurement steps.

Token counts identify the model weights used to measure them. Helpers reject
readings for different weights and list external constants that need remeasurement.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from idhazh.contracts.base import Sha256

Kind = Literal["measurement", "judgement"]


@dataclass(frozen=True)
class Measured:
    """A value, its source, and instructions for remeasurement."""

    value: float
    measures: str
    taken_on: date
    method: str
    when_it_fires: str
    why_a_number: str
    kind: Kind = "measurement"

    def __post_init__(self) -> None:
        for field in ("measures", "method", "when_it_fires", "why_a_number"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty")


@dataclass(frozen=True, kw_only=True)
class TokenizerMeasured(Measured):
    """A tokenizer reading with the digest of the measured model weights."""

    subject: Sha256


# Fixed measurement identity, not the model currently selected in config.
QWEN35_9B_Q4_K_M: Final[Sha256] = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"


DEFINITION_SENTENCE_TOKENS: Final = TokenizerMeasured(
    value=658,
    measures="every taxonomy definition sentence together, in tokens",
    taken_on=date(2026, 9, 14),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "joined all 23 definitions in config/taxonomy.json and counted 658 tokens "
        "through the model server's /tokenize endpoint."
    ),
    when_it_fires=(
        "when weights or taxonomy definitions change, tokenize the joined definitions "
        "again and recalculate DefinitionText's character bound."
    ),
    why_a_number=(
        "provides evidence for the persisted definition-length bound."
    ),
)

TOKENS_A_WORD_AT_THE_CUT: Final = TokenizerMeasured(
    value=1.3628,
    measures="tokens a word, used to spend a token cap as a word count at the cut",
    taken_on=date(2026, 9, 14),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "tokenized article bodies from the first 200 corpus rows through /tokenize "
        "and divided total tokens by total words."
    ),
    when_it_fires=(
        "when weights change or truncation cuts too much, rerun "
        "backend/utilities/measure_budgets.py read on a bounded corpus sample."
    ),
    why_a_number=(
        "converts a token budget to the word count used for truncation."
    ),
)


@dataclass(frozen=True)
class Unreached:
    """An external constant and the reading used to size it."""

    module: str
    constant: str
    reading: TokenizerMeasured
    #: Record name used in printed replacement instructions.
    reading_name: str
    derivation: str


SIZED_BY_A_READING_HERE: Final = (
    Unreached(
        module="backend/idhazh/contracts/taxonomy.py",
        constant="DefinitionText",
        reading=DEFINITION_SENTENCE_TOKENS,
        reading_name="DEFINITION_SENTENCE_TOKENS",
        derivation=(
            "240-character bound; recalculate using mean tokens per definition."
        ),
    ),
    Unreached(
        module="backend/idhazh/extract.py",
        constant="TOKENS_PER_WORD",
        reading=TOKENS_A_WORD_AT_THE_CUT,
        reading_name="TOKENS_A_WORD_AT_THE_CUT",
        derivation="reads TOKENS_A_WORD_AT_THE_CUT.value directly.",
    ),
)


def readings_awaiting_a_retake(*, configured_sha256: str) -> tuple[Unreached, ...]:
    """Return external constants measured against different model weights."""
    return tuple(
        site for site in SIZED_BY_A_READING_HERE if site.reading.subject != configured_sha256
    )


def describe_a_retake(site: Unreached) -> str:
    """One constant, its reading and what to do about it, as printable lines."""
    return (
        f"  - {site.module} {site.constant}\n"
        f"    {site.derivation}\n"
        f"    sized on {site.reading_name} = {site.reading.value:g} - {site.reading.measures}\n"
        f"    taken {site.reading.taken_on.isoformat()} against {site.reading.subject}\n"
        f"    to retake it: {site.reading.when_it_fires}"
    )


def refuse_a_reading_taken_against_other_weights(
    *, configured_sha256: str, records: Iterable[Measured]
) -> None:
    """Reject mismatched tokenizer readings and report required remeasurements."""
    stale = [
        record
        for record in records
        if isinstance(record, TokenizerMeasured) and record.subject != configured_sha256
    ]
    if not stale:
        return
    readings = "\n".join(
        f"  - {record.measures}\n"
        f"    taken {record.taken_on.isoformat()} against {record.subject}\n"
        f"    to retake it: {record.when_it_fires}"
        for record in stale
    )
    elsewhere = readings_awaiting_a_retake(configured_sha256=configured_sha256)
    unreached = "\n".join(describe_a_retake(site) for site in elsewhere)
    raise ValueError(
        f"{len(stale)} tokenizer reading(s) name weights the configuration does not.\n"
        f"the configured weights are {configured_sha256}\n"
        f"{readings}\n"
        "Retake each reading against the configured weights and replace the record.\n"
        f"{len(elsewhere)} of {len(SIZED_BY_A_READING_HERE)} constants sized by a reading "
        "need review. Run `python backend/utilities/measure_budgets.py read`:\n"
        f"{unreached}"
    )


SITE_GROWTH_KB_A_DAY: Final = Measured(
    value=16_252,
    measures="the fastest growth of the published site, in binary KB a published day",
    taken_on=date(2026, 8, 27),
    method=(
        "summed frontend/build file sizes after npm run build over three mature "
        "committed days; 16,641,956 bytes per day, rounded up to binary KB."
    ),
    when_it_fires=(
        "remeasure the three newest mature days and replace this record; adjust "
        "retention.site_budget_mb to preserve the required warning period."
    ),
    why_a_number=(
        "converts remaining site capacity to days before the platform size limit."
    ),
)

WARNING_DAYS_REQUIRED: Final = Measured(
    value=14,
    measures="days of warning the site-size alarm has to buy before the platform cap",
    taken_on=date(2026, 8, 27),
    method=(
        "operator judgement of the time needed to notice an alarm, edit config "
        "and redeploy; not a measured response time."
    ),
    when_it_fires=(
        "lower retention.site_budget_mb or remeasure SITE_GROWTH_KB_A_DAY if growth "
        "changed; do not shorten the warning period to pass the check."
    ),
    why_a_number=(
        "sets the required operator response period before the site reaches its limit."
    ),
    kind="judgement",
)

PROMPT_OVERHEAD_TOKENS: Final = TokenizerMeasured(
    value=997,
    measures="what the summarize prompt costs before a word of the article reaches it",
    taken_on=date(2026, 9, 9),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "least-squares fit of input_tokens against source_words over 4,117 items "
        "in runner-written state/item-health/2026-09.csv."
    ),
    when_it_fires=(
        "when prompt text, fences or weights change, refit against the newest "
        "month shard and check the article cap against the context window."
    ),
    why_a_number=(
        "adds fixed prompt tokens to the context-window calculation."
    ),
)

WORST_TOKENS_A_WORD: Final = TokenizerMeasured(
    value=1.585,
    measures="the highest tokens a word any published item has reached",
    taken_on=date(2026, 9, 9),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "(7,093 input tokens - 997 prompt tokens) / 3,846 source words for the "
        "highest-ratio item in state/item-health/2026-09.csv."
    ),
    when_it_fires=(
        "when a higher ratio is observed or weights change, remeasure the maximum "
        "and check the article cap against the context window."
    ),
    why_a_number=(
        "converts the largest allowed word count to a worst-case body token count."
    ),
)

# The two readings below were taken with /tokenize on eight 7,692-word corpus builds:
# longest-first, densest-first, reverse-densest and five seeded shuffles. They were read
# on the longest prompt this project has sent, which carried instructions and sentence
# addresses the digest call's prompt does not, so each one is a ceiling on that prompt and
# not a reading of it.

DIGEST_PROMPT_SCAFFOLD_TOKENS: Final = TokenizerMeasured(
    value=2167,
    measures=(
        "a ceiling on what the digest call's prompt costs before a word of the article or a "
        "table row lands, read on the longer prompt of the first call it replaced"
    ),
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "rendered that first call's request with a seven-word article and empty candidate "
        "menu, then tokenized the whole prompt: 2,055 system tokens and 112 others."
    ),
    when_it_fires=(
        "when prompts, turn markers or weights change, render calls.build_summary_request for a "
        "seven-word article and no tables, tokenize the whole prompt, and "
        "replace this ceiling with the count."
    ),
    why_a_number=(
        "adds the fixed prompt tokens to the digest call's context-window calculation."
    ),
)

DIGEST_PROMPT_BODY_TOKENS_A_WORD: Final = TokenizerMeasured(
    value=2.2285,
    measures=(
        "a ceiling on the article's tokens per word of the cut article, read with the "
        "sentence addresses the digest call's prompt no longer carries"
    ),
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "(15,014 body tokens + 2,127 sentence-address tokens) / 7,692 words on the "
        "densest of eight cap-length builds."
    ),
    when_it_fires=(
        "when a higher ratio is observed or weights change, rebuild the cap-length inputs, "
        "tokenize the article as calls.summary_user_turn prints it, and remeasure the maximum."
    ),
    why_a_number=(
        "converts article words to a worst-case token count."
    ),
)

EVERY_MEASURED: Final = (
    SITE_GROWTH_KB_A_DAY,
    WARNING_DAYS_REQUIRED,
    PROMPT_OVERHEAD_TOKENS,
    WORST_TOKENS_A_WORD,
    DIGEST_PROMPT_SCAFFOLD_TOKENS,
    DIGEST_PROMPT_BODY_TOKENS_A_WORD,
)
