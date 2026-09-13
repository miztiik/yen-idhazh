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
wrote any code, because a run appended more?** That is Guardrail #12's question with
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

#: Everything below is call 1's prompt, which the two-call path renders itself.
#: Four numbers rather than one, because they move for different reasons: the
#: scaffold moves when a prompt file is edited, the per-word rate when an article
#: tokenizes harder, the per-row rate when the menu's layout changes, and the
#: seam when call 2's trailing turn is reworded. One number would hide which.
#:
#: All four were taken together on 2026-09-13 against
#: `backend/models/Qwen3.5-9B-Q4_K_M.gguf` through `llama-server`'s own
#: `/tokenize`, on a laptop (i7-1265U, 32 GiB, four other agents live). A
#: tokenizer reading is not a timing, so the hardware bounds nothing here: the
#: same weights return the same token counts on a runner.
#:
#: **The cap-length article had to be built.** The committed corpus's longest
#: body is 3,846 words against a cut point of 7,692, so every reading below comes
#: from eight articles joined out of corpus prose and cut by `truncate_to_tokens`
#: itself - longest-first, densest-first, its reverse, and five seeded shuffles.
#: `CLAUDE.md` section 13 is the rule: where the awkward shape is the point, the
#: shape is built, because a built one carries the case the archive never produced.

CALL_ONE_SCAFFOLD_TOKENS: Final = Measured(
    value=2167,
    measures="what call 1's prompt costs before a word of the article or a menu row lands",
    taken_on=date(2026, 9, 13),
    method=(
        "rendered `build_call_one_request` over a seven-word article with an empty "
        "candidate menu and tokenized the whole prompt. The system turn alone is "
        "2,055 of it, measured separately, so the remaining 112 is the title line, "
        "the two section headers and the fences. It is bigger than the single call's "
        "997 because call 1's system turn carries both jobs since row #3e."
    ),
    when_it_fires=(
        "a prompt file under backend/idhazh/prompts/ changed, or a turn marker moved. "
        "Re-render the same seven-word article and tokenize it again."
    ),
    why_a_number=(
        "it is the constant term of the arithmetic that checks the two-call sequence "
        "against the window, so it has to be a number to be added to anything. It "
        "moves when a prompt is edited, never when a run publishes."
    ),
)

CALL_ONE_BODY_TOKENS_A_WORD: Final = Measured(
    value=2.2285,
    measures="the article and its sentence addresses, per word of the cut article",
    taken_on=date(2026, 9, 13),
    method=(
        "(15,014 + 2,127) / 7,692 on the densest of the eight cap-length builds. The "
        "body is 15,014 tokens and the `[sNN] ` addresses in front of each sentence "
        "are the other 2,127. The spread across the eight is 1.524 to 2.228, and the "
        "top of it is what a window has to hold."
    ),
    when_it_fires=(
        "prose tokenized harder than this, or `numbered_sentences` changed how it "
        "addresses a sentence. Rebuild the cap-length arms and re-take the worst."
    ),
    why_a_number=(
        "a ratio has to be a number to be multiplied by a word count. It moves when "
        "an article tokenizes harder than any built so far, which is a property of "
        "one article rather than of how many we published."
    ),
)

CALL_ONE_MENU_TOKENS_A_ROW: Final = Measured(
    value=34.115,
    measures="one row of call 1's candidate menu, in tokens",
    taken_on=date(2026, 9, 13),
    method=(
        "8,665 / 254 on the worst of the eight cap-length builds; the spread across "
        "them is 27.2 to 34.1. A row is `[element_id] excerpt = value unit (sentence "
        "sNN)`. It is multiplied by `elements.max_per_article` rather than by a "
        "density, because the cap is what a saturated menu costs and the census says "
        "a cap-length article reaches it: over the 1,444 committed corpus rows the "
        "95th-percentile density is 0.0659 elements a word, which is 507 elements at "
        "7,692 words against a cap of 256."
    ),
    when_it_fires=(
        "`candidate_menu` changed what a row prints, or `element_id` changed length. "
        "Re-tokenize the menu of the same builds and re-take the worst per row."
    ),
    why_a_number=(
        "it is the per-row term of the same arithmetic, and it is the one term that "
        "reads a config knob back: `elements.max_per_article` sets how many rows it "
        "is multiplied by. It moves when the menu's layout moves, never when a run "
        "publishes."
    ),
)

CALL_TWO_SEAM_TOKENS: Final = Measured(
    value=58,
    measures="what call 2 adds in front of its own reply, beyond call 1's prompt and reply",
    taken_on=date(2026, 9, 13),
    method=(
        "tokenized call 2's whole prompt and subtracted call 1's prompt and the reply "
        "between them, over both plan states and two reply strings. 53 with the plan "
        "asked for, 58 with it suppressed - the wider of the two, because the "
        "suppressed shape is the one that has to fit when the window is tightest."
    ),
    when_it_fires=(
        "`call_two_user_turn` was reworded or a turn marker moved. Re-tokenize both "
        "prompts on the same build and subtract again."
    ),
    why_a_number=(
        "it is the last term of the two-call sum. Small, and worth a record anyway: "
        "row #3e cut this turn from 692 tokens to 58 by moving its work into the "
        "system turn, and a number nobody wrote down is a saving that comes back."
    ),
)

#: Everything above, so a check can walk the set rather than naming each one.
EVERY_MEASURED: Final = (
    SITE_GROWTH_KB_A_DAY,
    WARNING_DAYS_REQUIRED,
    PROMPT_OVERHEAD_TOKENS,
    WORST_TOKENS_A_WORD,
    CALL_ONE_SCAFFOLD_TOKENS,
    CALL_ONE_BODY_TOKENS_A_WORD,
    CALL_ONE_MENU_TOKENS_A_ROW,
    CALL_TWO_SEAM_TOKENS,
)
