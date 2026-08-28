"""One human faithfulness label (`state/labels.csv`).

The faithfulness thresholds are a promise to a reader and nothing has ever
measured their error rate. This is the instrument that would, and it is
deliberately the smallest one that can: a stratified draw over the committed
ledger, one binary answer, one tag.

Three things about this shape are load-bearing.

**A label is a fact about a (summary, article) pair, not about a score.**
`output_digest` pins the exact words that were judged. The scorer's number at
draw time is recorded so a later analysis can see what it would have concluded,
and hidden from the labeller so it cannot anchor them. When the scorer moves, the
label stays valid as a label and stops being evidence about that scorer's
numbers - so the read side re-joins on `output_digest` and takes the live score
from the ledger.

**There is nowhere to put a machine verdict.** `labeller` is a required non-empty
name checked against `evaluation.labellers` in config. No `model_id`, no nullable
author. LLM-as-judge is a project non-goal (`CLAUDE.md` section 0a), and a
non-goal that is only discouraged is not a control - putting a model in this
ledger needs a schema change, a changelog entry with a written reason, and a
Level 5 consultation.

**`seconds_spent` is the cheapest fatigue detector there is**, and together with
`labelled_at` it is what a contract test reads to refuse a machine-paced dump.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    Timestamp,
    Url,
    UrlKey,
)
from idhazh.contracts.eval_row import ConfidenceBand


class LabelVerdict(StrEnum):
    """The one question. Not a bool - a bool named `unsupported` inverts in
    somebody's head within a month."""

    #: Everything the summary asserts is supported by the article.
    SUPPORTED = "supported"
    #: The summary asserts something the article does not support.
    UNSUPPORTED = "unsupported"


class LabelTag(StrEnum):
    """Why, in one closed word.

    Every tag names a defect with a **different** fix. Two tags that lead to the
    same code change would be one tag. Three of these deliberately mirror a
    counterweight the pipeline already computes, which buys that counterweight's
    own precision and recall out of the same 60 labels.

    Absent on purpose: severity, which is a second axis with its own agreement
    problem; anything about style, which is not faithfulness; and `other`, which
    grows until the vocabulary means nothing. `note` carries the misses.
    """

    #: The verdict was `supported`. There is nothing to explain.
    NONE = "none"
    #: An entity, event or relation the article does not contain.
    INVENTED_FACT = "invented_fact"
    #: A figure, date or quantity the article contradicts or never gives.
    WRONG_NUMBER = "wrong_number"
    #: The article hedged or attributed; the summary asserted it flat.
    OVERSTATED = "overstated"
    #: Faithful sentences about the wrong thing - a sidebar, another company.
    WRONG_SUBJECT = "wrong_subject"
    #: The summary describes chrome: navigation, a paywall notice, a caption.
    NOT_THE_ARTICLE = "not_the_article"
    #: Source gone, wrong language, or too little text to judge. An exclusion.
    UNJUDGEABLE = "unjudgeable"


class LabelRow(Contract):
    """One labelled item, appended by a human."""

    __schema_stem__: ClassVar[str] = "label-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27",
            change="source_word_count is now source_seen_word_count.",
            why=(
                "The queue filled it from the eval ledger's source_word_count, which now "
                "means the whole article and is null when that length was never recorded. "
                "A labeller cannot check a number against text nobody kept. The premise "
                "they read is the truncated text, so the count beside it is the count of "
                "that text, and it is never missing. No row is migrated because no label "
                "has ever been written - state/labels.csv does not exist."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24",
            change="Initial shape: the draw's identity, the scorer at draw time, and the label.",
            why=(
                "The faithfulness cuts are a reader-facing promise with no measured error "
                "rate behind them. Nothing can move a threshold until labels exist, and "
                "labels cannot exist until the shape that holds them does (Rule #3). "
                "Contracts before logic, and this one lands before a single row."
            ),
        ),
    )

    # --- what was judged ---------------------------------------------------
    label_id: Slug = Field(
        description=(
            "Deterministic draw key, rebuilt from its value fields on read and never "
            "trusted from the file."
        )
    )
    draw_id: Slug = Field(
        description=(
            "Which draw this row belongs to. Distinguishes a second draw from a re-label "
            "of the first."
        )
    )
    url_key: UrlKey
    source_url: Url
    date: DateStamp
    run_id: RunId
    output_digest: Sha256 = Field(
        description=(
            "The exact summary that was judged. The load-bearing field: a mismatch means "
            "the label is about different words."
        )
    )
    pipeline_fingerprint: Sha256
    summary_word_count: int = Field(ge=0)
    source_seen_word_count: int = Field(
        ge=0,
        description=(
            "Words in the premise the labeller reads - the article after sanitizing and "
            "truncation, which is what the scorer read too. Not the whole article: that "
            "length is null on a ledger row that never recorded it, and a labeller cannot "
            "check a number against text nobody kept."
        ),
    )

    # --- what the scorer said at draw time: recorded, never shown ----------
    scorer_version: str = Field(
        min_length=1,
        description=(
            "The full string, band values included. Recorded so an analysis can refuse to "
            "mix instruments, hidden so it cannot anchor the labeller."
        ),
    )
    hhem_at_label: float = Field(ge=0.0, le=1.0)
    band_at_label: ConfidenceBand

    # --- the label ---------------------------------------------------------
    verdict: LabelVerdict
    tag: LabelTag
    labeller: Slug = Field(
        description=(
            "Who. Checked against evaluation.labellers. Two people disagreeing is signal; "
            "an anonymous ledger cannot see it."
        )
    )
    labelled_at: Timestamp
    seconds_spent: int = Field(
        ge=1,
        description=(
            "How long this row took. The cheapest fatigue detector there is, and half of "
            "what makes a machine-paced dump detectable."
        ),
    )
    note: UntrustedLine | None = Field(
        default=None,
        description="Capped and sanitized. If notes pile onto one tag, the vocabulary is wrong.",
    )

    @model_validator(mode="after")
    def _tag_agrees_with_the_verdict(self) -> Self:
        if self.verdict is LabelVerdict.SUPPORTED and self.tag is not LabelTag.NONE:
            raise ValueError("a supported summary has no defect to tag")
        if self.verdict is LabelVerdict.UNSUPPORTED and self.tag is LabelTag.NONE:
            raise ValueError("an unsupported summary must name which defect it is")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell, not the word None."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}
