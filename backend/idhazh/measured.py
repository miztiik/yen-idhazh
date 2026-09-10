"""Every measured number a gate or a test reads, in one place, with its provenance.

A number like the site's growth rate is measured once and then read by code that
cannot see the measurement. Written as a constant with the derivation in a doc,
the two drift silently: deleting the prose leaves a live constant that nobody can
re-derive, and every test still passes, so nothing says so. That happened - the
sole written derivation of the site growth rate sat in a page section the page's
own retention rule said to delete.

So the provenance travels with the value, as fields rather than as a comment, and
this module is the only place either lives. **Docs cite this module; this module
cites no doc**, because a doc section can be renamed or removed and a link into
prose is the thing that rots.

Every record also says what to do when it fires. These are guardrails for riding
a boundary, not walls: a number that only ever stops work gets raised by whoever
finds it inconvenient, and a number that says how to re-derive it gets re-derived.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

Kind = Literal["measurement", "judgement"]


@dataclass(frozen=True)
class Measured:
    """One number, what it is of, where it came from, and what to do when it bites."""

    value: float
    measures: str
    taken_on: date
    method: str
    when_it_fires: str
    kind: Kind = "measurement"

    def __post_init__(self) -> None:
        for field in ("measures", "method", "when_it_fires"):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} is empty: a number with no {field} is an estimate")


SITE_GROWTH_KB_A_DAY: Final = Measured(
    value=16_252,
    measures="the fastest growth of the published site, in binary KB a published day",
    taken_on=date(2026, 8, 27),
    method=(
        "sum every file under frontend/build after npm run build, over the three "
        "mature committed days; 16,641,956 bytes a day rounded up to binary KB. It "
        "replaced 8,537, which was unmeasured arithmetic over a hypothetical image "
        "on every item and was taken over the committed payload tree rather than "
        "the built site - a different tree, eighteen times smaller."
    ),
    when_it_fires=(
        "re-measure the same way over the three newest mature days and replace this "
        "record. The alarm point moves with it rather than the other way round: the "
        "rate is the evidence and retention.site_budget_mb is the knob."
    ),
)

WARNING_DAYS_REQUIRED: Final = Measured(
    value=14,
    measures="days of warning the site-size alarm has to buy before the platform cap",
    taken_on=date(2026, 8, 27),
    method=(
        "a judgement, not a measurement. Nothing here measures how long one "
        "maintainer takes to read one issue. Two things around it are measured and "
        "bound the window rather than set it: the pipeline runs five times a day, so "
        "the site is measured every four hours, and the fix is a config edit and a "
        "redeploy at about 25 minutes of CI."
    ),
    when_it_fires=(
        "the alarm point is too high for the growth rate. Lower "
        "retention.site_budget_mb, or re-derive SITE_GROWTH_KB_A_DAY if the rate "
        "itself has moved. Do not lower this number to make the check pass."
    ),
    kind="judgement",
)

CONSOLE_CEILING_HEADROOM_BYTES: Final = Measured(
    value=370_000,
    measures="the bound every console page guardrail has to stay under, in gzipped bytes",
    taken_on=date(2026, 9, 10),
    method=(
        "the heaviest console document plus 313,300 - what a day payload cost when a "
        "layout last inlined one, which is the single regression this surface has "
        "actually had. A number above the sum cannot catch it. 57,488 measured at "
        "c40eda91, gzip -5, heaviest of five builds of the shipping tree, plus "
        "313,300, rounded down to the thousand. It held 369,000 from 2026-09-06 at a "
        "heaviest document of 56,664, 536,000 before that at 222,819, and 433,000 "
        "before that at 119,700 - and 222,819 is the measure of how far this stand-in "
        "drifts from the page, because the console then stopped inlining its telemetry "
        "and the document fell to a quarter of it."
    ),
    when_it_fires=(
        "the console genuinely carries more, so re-measure the heaviest document and "
        "re-derive this bound in the same commit. It is the ceiling on a guardrail "
        "rather than a guardrail itself, so it does not take the twice-the-page rule: "
        "a page-weight number above this sum cannot see the regression it exists for. "
        "No approved panel is cut to stay under a number (owner, 2026-08-31)."
    ),
)

PROMPT_OVERHEAD_TOKENS: Final = Measured(
    value=997,
    measures="what the summarize prompt costs before a word of the article reaches it",
    taken_on=date(2026, 9, 9),
    method=(
        "a least-squares fit of input_tokens against source_words over the 4,117 "
        "published items in state/item-health/2026-09.csv, written by stock "
        "ubuntu-latest runners. The shortest items on the shard - 3 words each - "
        "measured 980 to 985 tokens directly, so the constant reads off the data twice."
    ),
    when_it_fires=(
        "the system prompt, the fence or the instructions changed. Re-fit against the "
        "newest month shard; the window-fit check reads this value and the cap together."
    ),
)

WORST_TOKENS_A_WORD: Final = Measured(
    value=1.585,
    measures="the highest tokens a word any published item has reached",
    taken_on=date(2026, 9, 9),
    method=(
        "(7,093 - 997) / 3,846 over the same shard. extract.truncate_to_tokens spends "
        "the cap at 1.3 tokens a word, so a body tokenizing above that overruns the "
        "budget its own cap gave it. The spread is the point: the median item runs "
        "1.306, so a window sized on the median is sized on the article that never "
        "causes trouble."
    ),
    when_it_fires=(
        "an article tokenized harder than any before it. Raise this to what it "
        "measured and re-check the cap against the window - the two are one decision."
    ),
)

ITEMS_A_DAY_CEILING: Final = Measured(
    value=160,
    measures="the item ceiling a run plans to, run.safety_ceiling_per_run",
    taken_on=date(2026, 8, 26),
    method="read from config/idhazh.json; spelled out so the arithmetic reading it stays readable.",
    when_it_fires=(
        "the config moved and this copy did not. Read it from the config rather than "
        "raising it here."
    ),
    kind="judgement",
)

#: Everything above, so a check can walk the set rather than naming each one.
EVERY_MEASURED: Final = (
    SITE_GROWTH_KB_A_DAY,
    WARNING_DAYS_REQUIRED,
    CONSOLE_CEILING_HEADROOM_BYTES,
    PROMPT_OVERHEAD_TOKENS,
    WORST_TOKENS_A_WORD,
    ITEMS_A_DAY_CEILING,
)
