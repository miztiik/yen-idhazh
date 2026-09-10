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

**And every record says why it is a number at all, because most of them should
not be.** A threshold is a proxy for a property nobody stated, and it fails in
two directions that are both green: too tight it fires on ordinary work and the
cheapest answer is to raise it, too loose it fires on nothing and nothing says
so. `page_weight.ceilings_bytes` did both - it fired on ordinary publishing four
times and was raised each time, while `/console/` sat at 7.2 times the page it
bounded for four days with the build green. Four of its six numbers were deleted
on 2026-09-10 and the property behind them is asserted directly, by
`frontend/tests/payload-weight.spec.ts`, which looks for a day payload in a
document that should not carry one and has no number in it at all.

**The test a number has to pass to live here: does it have to move when nobody
wrote any code, because a run appended more?** That is Rule #12's question with
one noun changed. Yes means it is the defect and the property behind it should be
asserted instead. No means it is a design statement and it is welcome. And where
a number must exist, prefer putting the direction it may not move into the type -
`retention.pages_hard_cap_mb` is bounded `le=PAGES_HARD_CAP_MB`, so the loose
failure is unrepresentable rather than merely unlikely.
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
    why_a_number: str
    kind: Kind = "measurement"

    def __post_init__(self) -> None:
        for field in ("measures", "method", "when_it_fires", "why_a_number"):
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
    why_a_number=(
        "the question is how many days of warning are left, and days are the rate "
        "divided into the headroom - there is no property that answers it. It passes "
        "the test: publishing more does not change how fast the site grows, so this "
        "number does not have to move when nobody wrote any code."
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
    why_a_number=(
        "it is how long a person needs, and a person is not a property this repository "
        "can assert. It moves when the pipeline's schedule or the fix's cost moves, "
        "never when a run publishes."
    ),
    kind="judgement",
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
    why_a_number=(
        "it is a term in an arithmetic check that the context window fits the worst "
        "article, so it has to be a number to be added to anything. It moves when the "
        "prompt is edited, never when a run publishes."
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
    why_a_number=(
        "the same arithmetic as PROMPT_OVERHEAD_TOKENS and the same answer: a ratio "
        "has to be a number to be multiplied by a word count. It moves when an "
        "article tokenizes harder than any before it, which is a property of one "
        "article rather than of how many we published."
    ),
)

#: Everything above, so a check can walk the set rather than naming each one.
EVERY_MEASURED: Final = (
    SITE_GROWTH_KB_A_DAY,
    WARNING_DAYS_REQUIRED,
    PROMPT_OVERHEAD_TOKENS,
    WORST_TOKENS_A_WORD,
)
