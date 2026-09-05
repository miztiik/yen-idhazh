"""Whether an item gets a chart or nothing.

"Nothing" is a real, frequent and correct answer. The failure mode being
designed against is decoration: a generated picture of a chart with invented
axis labels looks like evidence, and a reader who once notices an invented
number stops trusting every summary on the page.

A render failure degrades the item to no visual. It never fails the item and it
never fails the run.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, RelPath, Slug, Timestamp, UrlKey

#: What one item's decision is filed as, under `backend/var/run/<date>/items/`.
#: The writer, the reader and the workflow's upload glob all spell it, and a run
#: where they disagree uploads an empty artifact and publishes with no pictures.
PAYLOAD_SUFFIX: Final = ".visual.json"


class VisualKind(StrEnum):
    CHART = "chart"
    NONE = "none"


class VisualState(StrEnum):
    """What became of the visual. "Could not make it" and "made it then threw it
    away" are different facts, so they never share a member."""

    ABSENT = "absent"
    RENDERED = "rendered"
    RENDER_FAILED = "render_failed"


class VisualDecision(Contract):
    """The visual planner's decision plus the Render stage's outcome, one per item."""

    __schema_stem__: ClassVar[str] = "visual-decision"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-05T18:00",
            change=(
                "Removed spec_format and the SpecFormat enum it was typed with. VisualKind "
                "lost diagram and image, so it holds chart and none. spec is unchanged and "
                "still carries the Vega-Lite JSON the renderer draws."
            ),
            why=(
                "spec_format was never read. It was a second name for a fact kind already "
                "carried, and a table in this module mapped one to the other - so the only "
                "thing it could do was disagree with kind, which is what the validator "
                "existed to stop. image had no producer and no renderer from the day it was "
                "written. diagram had both, and both were Mermaid: the planner wrote "
                "flowchart TD text and our own layout read it back. That round trip is gone "
                "(pseudo-plan row 63). It was written so anyone could re-render the picture "
                "with the real Mermaid toolchain, and nobody can: the payload lands under "
                "backend/var/, which is gitignored, travels as a one-day artifact, and the "
                "published DigestVisual carries no spec at all. It also lost data - the "
                "parser matched edges and threw them away, so two different graphs drew "
                "identically. No read-side migration: scanned 2026-09-05 over all 15 "
                "committed digest.json files, 6,425 items, 351 of them carrying a visual - "
                "every one is a chart, none carries diagram or image, and no committed "
                "visual carries a spec or a spec_format key."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T17:00",
            change=(
                "The file this payload is written to is now <item>.visual.json. It was "
                "<item>.route.json. No field changed."
            ),
            why=(
                "The filename is the last place the old word survived on the write path, "
                "and it is the one nothing else records - the payload lives under "
                "backend/var/, which is gitignored, so a reader of this repository has "
                "only this entry to learn the old name from. Python now spells the suffix "
                "once, as PAYLOAD_SUFFIX above, because the writer and the glob that "
                "reads it were two literals that had to agree. The workflow's upload glob "
                "is the second spelling and cannot read a Python name, so a test holds "
                "the two as one pair: move the suffix without the glob and the artifact "
                "uploads nothing, assemble receives no visuals, and the day publishes "
                "with no pictures on a green run."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T15:00",
            change=(
                "Renamed. The class was Route, the schema file was route.schema.json, and "
                "the two fields routed_at and route_ms are now decided_at and decision_ms. "
                "No field was added, removed or retyped, and no value changed."
            ),
            why=(
                "Route names a dispatch decision; this payload records a planning "
                "decision, so the old stem taught the wrong word to everything that read "
                "it. The old stem is written here because a schema file that changes name "
                "leaves no other trace of what it used to be called (CLAUDE.md section "
                "11). No read-side migration: this payload is written to <item>.route.json "
                "under backend/var/, which is gitignored and travels as a one-day "
                "artifact, so the run that writes it is the run that reads it and no "
                "committed payload carries the old field names."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "asset_path is now written as digest/<Y>/<M>/<D>/<item_id>.svg. It was "
                "digest/<Y>/<M>/<D>/<vertical>-<NN>.svg, where NN came from a counter "
                "seeded by reading the day's directory."
            ),
            why=(
                "A counter has to be seeded from somewhere a run can read, and two runs "
                "of one day read the same directory before either had pushed. Both wrote "
                "energy-03.svg for different items and run 32869125768 lost a finished "
                "day to CONFLICT (add/add). Naming the file after the item makes the "
                "path a function of the item, so no two runs and no two shards can pick "
                "one path for two stories, and sharding the route stage stops being "
                "blocked on it. No migration: the path is stored, not derived, so every "
                "payload written under the old shape still validates and still resolves "
                "to the file it names. Both shapes are live in committed data."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change="Added drafted_chart, defaulting to false and derived true for a chart.",
            why=(
                "A chart draft that the post-model checks reject is today indistinguishable "
                "from a draft the model never wrote, so nothing committed says why 8 of 17 "
                "drafts died on 2026-08-25. The run manifest sums this into charts_drafted. "
                "The read-side migration is a validator: a payload written before the field "
                "existed whose kind is chart was necessarily drafted as one, and a default "
                "of false there would report fewer drafts than published charts."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:10",
            change="Added asked_the_model, defaulting to true.",
            why=(
                "The router now decides an item without posting when no enabled visual "
                "kind could survive its checks. That decision must be a field, not a "
                "sentence a reader parses out of the rationale, because the run manifest "
                "counts it and a chart rate quoted against the wrong denominator is the "
                "first thing this gate would break. True on an older payload, which is "
                "correct: every item was asked before the gate existed."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added optional route_ms.",
            why=(
                "The route job sits between 51 and 60 minutes against a 60-minute bound and "
                "nothing recorded what it spent, so every argument about the budget was an "
                "estimate (Rule #10). Null on a payload written before the clock existed, "
                "which is what keeps the field additive."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change=(
                "Initial shape: the four-way visual-kind enum, the spec, and the render "
                "outcome."
            ),
            why=(
                "Contracts before logic - the planner and Render are written against a "
                "fixed payload."
            ),
        ),
    )

    item_id: ItemId
    url_key: UrlKey
    kind: VisualKind
    rationale: UntrustedLine | None = None
    spec: str | None = Field(
        default=None,
        description=(
            "The Vega-Lite JSON the renderer draws, built here from the article's own "
            "numbers. Null on an item decided to nothing."
        ),
    )
    asset_path: RelPath | None = Field(
        default=None,
        description=(
            "Relative POSIX path under frontend/public/, once rendered. Written as "
            "digest/<Y>/<M>/<D>/<item_id>.svg since 2026-08-27; payloads before that "
            "carry digest/<Y>/<M>/<D>/<vertical>-<NN>.svg and stay valid."
        ),
    )
    alt_text: UntrustedLine | None = None
    visual_state: VisualState = VisualState.ABSENT
    model_id: Slug
    decided_at: Timestamp
    decision_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall-clock for this item: the planner call plus the render. Null on a payload "
            "written before the clock existed."
        ),
    )
    asked_the_model: bool = Field(
        default=True,
        description=(
            "False when the planner decided this item on its own facts and never posted. "
            "True on a payload written before the gate existed, because every item was "
            "asked then."
        ),
    )
    drafted_chart: bool = Field(
        default=False,
        description=(
            "True when the model's reply asked for a chart, whatever this decision "
            "became. The gap between this and a kind of chart is what the post-model "
            "checks rejected."
        ),
    )
    failure_detail: UntrustedLine | None = None

    @model_validator(mode="after")
    def _a_published_chart_was_drafted_as_one(self) -> Self:
        """The read side for a payload written before `drafted_chart` existed."""
        if self.kind is VisualKind.CHART and not self.drafted_chart:
            self.drafted_chart = True
        return self

    @model_validator(mode="after")
    def _outcome_matches_the_decision(self) -> Self:
        if self.kind is VisualKind.NONE:
            if self.spec is not None:
                raise ValueError("an item decided to nothing carries no spec")
            if self.visual_state is not VisualState.ABSENT:
                raise ValueError("an item decided to nothing has no visual to be in a state about")
        elif not self.spec:
            raise ValueError("a planned visual must carry the spec it was planned as")

        if self.visual_state is VisualState.RENDERED:
            if self.asset_path is None:
                raise ValueError("a rendered visual must record where it landed")
        elif self.asset_path is not None:
            raise ValueError("only a rendered visual carries an asset_path")

        if (self.visual_state is VisualState.RENDER_FAILED) != (self.failure_detail is not None):
            raise ValueError("a failed render records why, and only a failed render does")
        return self
