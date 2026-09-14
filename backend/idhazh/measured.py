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

**A count of tokens also says which weights counted them.** A second and a
resident set belong to the box that took them, so a timing record names hardware
and nothing else. A token count belongs to the tokenizer, the tokenizer ships
inside the weights, and a swap therefore invalidates every such reading at one
stroke while leaving each one looking fine. So a tokenizer reading is a
`TokenizerMeasured` and carries the weights digest as `subject`, and
`refuse_a_reading_taken_against_other_weights` is what says so out loud.

**Three constants shaped by a vocabulary cannot be moved in here, and their
readings are here anyway.** Two sit in `contracts/`, which may import no other
subpackage (`CLAUDE.md` section 4), and the third is read by an import-time
assertion, so none of the three can read a record back at the moment it is
declared. `SIZED_BY_A_READING_HERE` pairs each site with the reading that sized
it, so the `subject` is visible to a gate even where the constant is not.
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


@dataclass(frozen=True, kw_only=True)
class TokenizerMeasured(Measured):
    """A reading taken through a model's tokenizer, pinned to the weights that gave it.

    `subject` has no default on purpose. A tokenizer reading that omits it fails
    `mypy backend`, and a pin on a timing record cannot be written at all, so
    neither bad state needs a refusal test - the type refuses both. `kw_only` is
    on this class alone, so `Measured` and every call site of it are untouched.

    Only the pattern is not checked here. `Sha256` is a pydantic alias and does
    nothing in a plain dataclass, and the gate below already refuses a digest
    that is not the configured one, which a malformed digest never is.
    """

    subject: Sha256


#: The weights every tokenizer reading below was taken against, named for the file
#: rather than for the configuration slot it currently fills. A swap does not edit
#: this line - it adds the new weights beside it and retakes the readings that move.
#: `config/idhazh.json` is where the value in force lives; this is a historical
#: fact about a reading and is a literal for that reason (Guardrail #6).
QWEN35_9B_Q4_K_M: Final[Sha256] = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"


# --- Three constants that cannot read a record, and the readings that sized them --


#: Every definition sentence, which is what `VocabularyEntry.definition` bounds.
DEFINITION_SENTENCE_TOKENS: Final = TokenizerMeasured(
    value=658,
    measures="every taxonomy definition sentence together, in tokens",
    taken_on=date(2026, 9, 14),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "joined the `definition` of every entry in config/taxonomy.json and tokenized "
        "the join through the running server's /tokenize. 658 over 23 sentences is "
        "28.6 each. They ride in every labelling prompt, so the total is the quantity "
        "and the per-sentence figure is the total divided by the count. **Two things "
        "moved between this reading and the one before it** - the weights, and the "
        "vocabulary itself, which went from 30 definitions to 23. The total fell from "
        "805 because there are fewer sentences; per sentence it rose from 26.8, which "
        "is the only half of the change the tokenizer is responsible for."
    ),
    when_it_fires=(
        "the weights moved, or a definition was rewritten, or an entry was added or "
        "retired. Re-tokenize the joined definitions and re-derive `DefinitionText`'s "
        "character bound from the new per-sentence figure - it is about twice it, "
        "which is room to sharpen a sentence rather than room for a paragraph."
    ),
    why_a_number=(
        "the bound it sizes is a character count on a persisted contract, and a "
        "character count has to come from somewhere. The property behind it - the "
        "definitions fit the labelling prompt - is what `classify` already checks "
        "per run; this is what says the bound was not picked."
    ),
)

#: The cost of requiring every encoding role, which is what makes the widest
#: decoded plan reply the same shape as an ordinary one.
EMPTY_ROLE_TOKENS: Final = TokenizerMeasured(
    value=30,
    measures="the nine empty encoding roles on a visual plan that declines, in tokens",
    taken_on=date(2026, 9, 14),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "tokenized the committed plan fixtures through the running server's "
        "/tokenize. An empty role is `\"<name>\":[]` and a comma, so the nine cost "
        "115 characters on the plan that declines - 30 tokens, about 3.3 tokens an "
        "empty role. It was 28 on the retired 8B, so the denser vocabulary costs two "
        "tokens more for the same bytes."
    ),
    when_it_fires=(
        "the weights moved, or a role was added to or removed from the plan shape. "
        "Re-tokenize both committed fixtures and divide by the empty roles in each."
    ),
    why_a_number=(
        "it is what bought the decision to require every role, and a price nobody "
        "wrote down is a decision that gets re-argued. It does not set "
        "`WORST_CASE_REPLY_CHARACTERS`, which is arithmetic over the schema's own "
        "bounds - it is what says that arithmetic is worth paying."
    ),
)

#: The ratio every truncation point in the pipeline is placed with.
TOKENS_A_WORD_AT_THE_CUT: Final = TokenizerMeasured(
    value=1.3628,
    measures="tokens a word, used to spend a token cap as a word count at the cut",
    taken_on=date(2026, 9, 14),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "tokenized the article bodies of the first 200 corpus rows through the running "
        "server's /tokenize and divided total tokens by total words. **It was a "
        "judgement until this reading** - 1.3 was the received figure for English in a "
        "BPE vocabulary, written on the day `truncate_to_tokens` landed and never "
        "counted. It is a measurement now, and it moved 4.8 percent, so every "
        "truncation point cuts slightly earlier than it did."
    ),
    when_it_fires=(
        "the weights moved, or an article was cut shorter than its cap allowed. "
        "Re-tokenize a bounded sample of corpus article bodies and divide total tokens "
        "by total words - `backend/utilities/measure_budgets.py read` is that probe."
    ),
    why_a_number=(
        "a ratio has to be a number to convert a token cap into a word count. "
        "`WORST_TOKENS_A_WORD` at 1.585 is the same quantity on the single worst "
        "article rather than over a sample, and the gap between the two is the "
        "headroom a cap has to carry."
    ),
)


@dataclass(frozen=True)
class Unreached:
    """A constant that lives outside this module, beside the reading that sized it.

    All three sit where a loaded config cannot reach them. Two are in
    `contracts/`, which is the bottom of the dependency graph and may import no
    other subpackage (`CLAUDE.md` section 4), and the third is read by an
    import-time assertion in `classify/calls.py`, so a config edit that made it
    move could stop an import rather than change a behaviour. So the constant
    stays a literal at its site and the reading behind it lives here, where the
    gate can read its `subject`.
    """

    module: str
    constant: str
    reading: TokenizerMeasured
    #: What the reading is called in this module. The reader prints it as the
    #: heading of a paste block, so a rename that missed this line would hand
    #: somebody three lines to paste under a name that no longer exists.
    reading_name: str
    #: How the constant is derived from the reading, for whoever retakes it.
    derivation: str


#: Three constants shaped by a vocabulary, each beside the reading that sized it.
#: The 8B-to-9B move on 2026-08-27 left all three behind, so every `subject` below
#: names weights the configuration no longer runs. That is a correction waiting to
#: be made rather than a precaution, and `readings_awaiting_a_retake` is what says
#: so out loud.
#:
#: **Removal condition:** row #13b of `TODO/20260913-28-model-swap-plan.md` retakes
#: all three against the configured weights. A reading whose retake moves it gets
#: the old one deleted rather than kept beside the new one (Guardrail #10). A
#: reading that stops being tokenizer-shaped leaves this tuple for `EVERY_MEASURED`.
SIZED_BY_A_READING_HERE: Final = (
    Unreached(
        module="backend/idhazh/contracts/taxonomy.py",
        constant="DefinitionText",
        reading=DEFINITION_SENTENCE_TOKENS,
        reading_name="DEFINITION_SENTENCE_TOKENS",
        derivation=(
            "bounded at 240 characters, about twice the 27 tokens a definition "
            "sentence costs. Raise or lower the bound with the per-sentence figure"
        ),
    ),
    Unreached(
        module="backend/idhazh/contracts/visual.py",
        constant="WORST_CASE_REPLY_CHARACTERS",
        reading=EMPTY_ROLE_TOKENS,
        reading_name="EMPTY_ROLE_TOKENS",
        derivation=(
            "3,767, arithmetic over the schema's own bounds and recomputed at import, "
            "so the retake does not move it. What the retake settles is whether "
            "requiring all nine roles is still worth about 3 tokens each"
        ),
    ),
    Unreached(
        module="backend/idhazh/extract.py",
        constant="TOKENS_PER_WORD",
        reading=TOKENS_A_WORD_AT_THE_CUT,
        reading_name="TOKENS_A_WORD_AT_THE_CUT",
        derivation=(
            "the reading itself, read straight off `TOKENS_A_WORD_AT_THE_CUT.value`. "
            "This one moves the instant the reading does"
        ),
    ),
)


def readings_awaiting_a_retake(*, configured_sha256: str) -> tuple[Unreached, ...]:
    """The constants above whose reading names weights the configuration does not.

    A tuple rather than a refusal, because all three are stale on every commit
    until row #13b retakes them, and a check that is red on a state nobody has
    fixed yet is a check people learn to scroll past (`CLAUDE.md` section 13).
    Two surfaces read it: the refusal below, which fires at the one moment a
    person is provably looking at weights, and `backend/utilities/measure_budgets.py
    check`, which a person runs and which exits non-zero on what this returns.
    """
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
    """Refuse any tokenizer reading pinned to weights the configuration no longer names.

    Both arguments are handed in rather than read here, for two reasons.
    `contracts/` is the bottom of the dependency graph and cannot import this
    module, so an `AppConfig` validator is not an available placement and this
    module opens no file. And a gate that reads its own inputs cannot be driven
    from a built record, which is what the arm proving it bites needs
    (`CLAUDE.md` section 13).

    The refusal carries `SIZED_BY_A_READING_HERE`. This gate has exactly one
    trigger - the configured digest no longer matching a pinned reading - and
    that same swap is what makes those three stale, so they are the rest of the
    same failure rather than noise on an unrelated one. The person swapping a
    model is reading `config/idhazh.json` and a failing gate, not this module.
    """
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
        "Retake each one against the configured weights and replace the record. A reading "
        "is a variable and not a log entry, so the old one goes (Guardrail #10).\n"
        f"{len(elsewhere)} of {len(SIZED_BY_A_READING_HERE)} constants sized by a reading "
        "here live in modules that cannot read one back, and are stale for the same "
        "reason. `python backend/utilities/measure_budgets.py read` retakes them:\n"
        f"{unreached}"
    )


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

PROMPT_OVERHEAD_TOKENS: Final = TokenizerMeasured(
    value=997,
    measures="what the summarize prompt costs before a word of the article reaches it",
    taken_on=date(2026, 9, 9),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "a least-squares fit of input_tokens against source_words over the 4,117 "
        "published items in state/item-health/2026-09.csv, written by stock "
        "ubuntu-latest runners. The shortest items on the shard - 3 words each - "
        "measured 980 to 985 tokens directly, so the constant reads off the data twice. "
        "Every row on that shard was served by the weights in `subject`, which have "
        "been the configured ones since 2026-08-27."
    ),
    when_it_fires=(
        "the system prompt, the fence or the instructions changed, or the weights moved. "
        "Re-fit against the newest month shard; the window-fit check reads this value "
        "and the cap together. A different vocabulary counts the same prompt "
        "differently, so a swap retires this reading whatever the prompt says."
    ),
    why_a_number=(
        "it is a term in an arithmetic check that the context window fits the worst "
        "article, so it has to be a number to be added to anything. It moves when the "
        "prompt is edited, never when a run publishes."
    ),
)

WORST_TOKENS_A_WORD: Final = TokenizerMeasured(
    value=1.585,
    measures="the highest tokens a word any published item has reached",
    taken_on=date(2026, 9, 9),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "(7,093 - 997) / 3,846 over the same shard. extract.truncate_to_tokens spends "
        "the cap at 1.3 tokens a word, so a body tokenizing above that overruns the "
        "budget its own cap gave it. The spread is the point: the median item runs "
        "1.306, so a window sized on the median is sized on the article that never "
        "causes trouble."
    ),
    when_it_fires=(
        "an article tokenized harder than any before it, or the weights moved. Raise "
        "this to what it measured and re-check the cap against the window - the two are "
        "one decision. A ratio of tokens to words is a property of the vocabulary as "
        "much as of the prose, so a swap retires this reading on its own."
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
#: All four were taken together on 2026-09-13 through `llama-server`'s own
#: `/tokenize`, on a laptop (i7-1265U, 32 GiB, four other agents live). A
#: tokenizer reading is not a timing, so the hardware bounds nothing here: the
#: same weights return the same token counts on a runner. Which weights is
#: `subject` on each record, and `QWEN35_9B_Q4_K_M` is what names the file.
#:
#: **The cap-length article had to be built.** The committed corpus's longest
#: body is 3,846 words against a cut point of 7,692, so every reading below comes
#: from eight articles joined out of corpus prose and cut by `truncate_to_tokens`
#: itself - longest-first, densest-first, its reverse, and five seeded shuffles.
#: `CLAUDE.md` section 13 is the rule: where the awkward shape is the point, the
#: shape is built, because a built one carries the case the archive never produced.

CALL_ONE_SCAFFOLD_TOKENS: Final = TokenizerMeasured(
    value=2167,
    measures="what call 1's prompt costs before a word of the article or a menu row lands",
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "rendered `build_call_one_request` over a seven-word article with an empty "
        "candidate menu and tokenized the whole prompt. The system turn alone is "
        "2,055 of it, measured separately, so the remaining 112 is the title line, "
        "the two section headers and the fences. It is bigger than the single call's "
        "997 because call 1's system turn carries both jobs since row #3e."
    ),
    when_it_fires=(
        "a prompt file under backend/idhazh/prompts/ changed, a turn marker moved, or "
        "the weights moved. Re-render the same seven-word article and tokenize it again."
    ),
    why_a_number=(
        "it is the constant term of the arithmetic that checks the two-call sequence "
        "against the window, so it has to be a number to be added to anything. It "
        "moves when a prompt is edited, never when a run publishes."
    ),
)

CALL_ONE_BODY_TOKENS_A_WORD: Final = TokenizerMeasured(
    value=2.2285,
    measures="the article and its sentence addresses, per word of the cut article",
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "(15,014 + 2,127) / 7,692 on the densest of the eight cap-length builds. The "
        "body is 15,014 tokens and the `[sNN] ` addresses in front of each sentence "
        "are the other 2,127. The spread across the eight is 1.524 to 2.228, and the "
        "top of it is what a window has to hold."
    ),
    when_it_fires=(
        "prose tokenized harder than this, `numbered_sentences` changed how it "
        "addresses a sentence, or the weights moved. Rebuild the cap-length arms and "
        "re-take the worst."
    ),
    why_a_number=(
        "a ratio has to be a number to be multiplied by a word count. It moves when "
        "an article tokenizes harder than any built so far, which is a property of "
        "one article rather than of how many we published."
    ),
)

CALL_ONE_MENU_TOKENS_A_ROW: Final = TokenizerMeasured(
    value=34.115,
    measures="one row of call 1's candidate menu, in tokens",
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
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
        "`candidate_menu` changed what a row prints, `element_id` changed length, or "
        "the weights moved. Re-tokenize the menu of the same builds and re-take the "
        "worst per row."
    ),
    why_a_number=(
        "it is the per-row term of the same arithmetic, and it is the one term that "
        "reads a config knob back: `elements.max_per_article` sets how many rows it "
        "is multiplied by. It moves when the menu's layout moves, never when a run "
        "publishes."
    ),
)

CALL_TWO_SEAM_TOKENS: Final = TokenizerMeasured(
    value=58,
    measures="what call 2 adds in front of its own reply, beyond call 1's prompt and reply",
    taken_on=date(2026, 9, 13),
    subject=QWEN35_9B_Q4_K_M,
    method=(
        "tokenized call 2's whole prompt and subtracted call 1's prompt and the reply "
        "between them, over both plan states and two reply strings. 53 with the plan "
        "asked for, 58 with it suppressed - the wider of the two, because the "
        "suppressed shape is the one that has to fit when the window is tightest."
    ),
    when_it_fires=(
        "`call_two_user_turn` was reworded, a turn marker moved, or the weights moved. "
        "Re-tokenize both prompts on the same build and subtract again."
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
