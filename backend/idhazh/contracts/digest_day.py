"""The published day payload (`.../digest.json`) - what a reader actually gets.

One file per day carrying every item; a vertical route is a filter over this
same payload, never a second file. That is what keeps rendering any page at a
constant two requests however old the archive gets.

The order of `items` IS the published order: global, deterministic, and
identical for every reader. Read-state is a client-side mark that may change how
an item looks and may never change where it sits, whether it appears, or how it
ranks. An item introduced by a later run appends after the items already there,
which is why `introduced_by_run` may never decrease down the list.

`updated_at` and `updated_by_run` are reserved and nothing writes them. An
item's words are written once, by the run that introduced it. The two fields
hold the join to the run manifest that names the model, so that join stays true
if a run ever does rewrite an item's words.

`carried_by`, `watchlist_hit`, `on_front_page` and `rank_score` are the terms
the planning step scored the story on, and `time_source` is the clock behind
`published_at`. They are published so a page can say why a story is here and
whose time it is printing. All five are null on a day published before they
existed, and a null is unknown rather than a value.

`also_covered_by` and `same_story_as` are the day's own duplicate pass. It
groups the items on the vectors this payload already carries and keeps the
strongest of each group. Nothing is unpublished by it: a collapsed item keeps
its place in `items`, its anchor and its archive entry, and only what the
default view draws changes.

`leads` is the day's leading stories, chosen across the whole day rather than
off the head of `items`. It is a second order over the same list and never a
second list: a lead names a story `items` already holds, and an empty `leads`
is the ordinary state of a day with too few stories worth leading. It is
chosen after the duplicate pass has run, so the block reads the day the way
the reader will see it.

`considered`, `too_old` and `below_feed_floor` on a vertical are what the
planning step already knew and threw away. They are why a vertical is thin, so
a quiet vertical and a broken feed stop looking identical. All three are null on
a day published before they existed.

**`vertical` and `desk` are two different words and this file uses each for one
thing only.** A vertical is what the feed carrying the story declares about
itself, and it is what `item_id` is addressed from, so it never moves. A desk is
where the day publishes the story. They agree on every story nothing has
relabelled, and `desk` is null there - absent is unknown, and a reader falls
back to the vertical rather than reading a null as a desk.

`secondary_desk` is the one other desk a story has a claim to, and a story never
names more than these two. It is where the day sends the story when the desk it
is on is over its ceiling, and after such a move the two swap - so the story
keeps its claim on the desk it left rather than having a crowding rule erase
what the story is about. Null is unknown, never "no second desk".
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    RelPath,
    Slug,
    Timestamp,
    Url,
    without_retired_keys,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.visual_decision import VisualKind, VisualState


class DigestVisual(Model):
    """Where a story's chart data is, and never the chart data itself.

    One pointer and no chart data, ever. The day payload is the record that a
    day happened and is never deleted, so anything held inside it could not age
    out and `retention.image_months` would have nothing to act on - which is why
    the marks live in their own file and this says where (owner, 2026-09-13).

    **`path` retired on 2026-09-13 and the frozen days still carry it.** It
    named the committed drawing, the drawing is deleted, and the reader's browser
    draws from `data_path`. `Model` forbids a key it does not declare, so the 24
    days written before this are read through a named pop rather than by widening
    the model (`CLAUDE.md` section 11).
    """

    kind: VisualKind
    state: VisualState
    data_path: RelPath | None = Field(
        default=None,
        description=(
            "Where this visual's data landed, relative to frontend/public/, as "
            "digest/<Y>/<M>/<D>/<item_id>.json beside the day payload. Null on a day "
            "published before the file existed and on a visual whose data could not "
            "be written - absent reads as no data carried, never as an empty chart."
        ),
    )
    alt: UntrustedLine | None = None

    @model_validator(mode="before")
    @classmethod
    def _without_the_retired_drawing_path(cls, data: Any) -> Any:
        return without_retired_keys(data, "path")

    @model_validator(mode="after")
    def _a_data_path_means_the_marks_were_written(self) -> Self:
        """One-way, because the archive cannot satisfy the other direction.

        495 visuals across the 24 frozen days are `rendered` and carry no
        `data_path`: row #1a published the data going forward and rewrote no
        committed day, and no day will ever gain one - back-filling would mean
        re-fetching 495 source pages that have since moved. So a rule tying
        `rendered` to a present `data_path` would refuse the whole archive on
        first read.

        The direction that does hold catches the bug that can still happen: the
        write and the state are set in one step, so a path recorded without the
        state, or the reverse, is this project's own arithmetic being wrong.
        """
        if self.data_path is not None and self.state is not VisualState.RENDERED:
            raise ValueError("a data path is present only on a visual that rendered")
        return self


class DigestRunRef(Model):
    """A run of this date, as the page footer and the new-arrivals block need it."""

    n: int = Field(ge=1)
    at: Timestamp
    items_added: int = Field(ge=0)


class DigestVerticalRef(Model):
    """One topic of the day, and why it ran what it ran.

    **It carries two counts and they answer two questions.** `count` is every
    story whose carrying feed declares this vertical. `desk_count` is every
    story the day publishes under this name, which is what a reader sees. They
    are equal on every day nothing relabelled, and a page that wants the number
    on the screen reads `desk_count` and falls back to `count`.

    Both include a story the duplicate pass grouped behind another - nothing is
    unpublished by that pass, so the numbers are the payload's own and not what
    the default view happens to draw.

    The three shortfall fields are vertical facts, because collection is per
    feed and a feed declares a vertical. Each is the day's strongest reading:
    the largest any run of the day recorded. A later run has already taken what
    an earlier one published, so it sees a smaller pool of the same stories -
    summing the runs would count one back-catalogue story once per run.

    All three are null together on a day published before they existed, and a
    null is unknown rather than a zero, which would claim the feeds offered this
    vertical nothing.
    """

    id: Slug
    display_name: str = Field(min_length=1)
    count: int = Field(
        ge=0,
        description=(
            "Stories whose carrying feed declares this vertical. It is not what the "
            "page draws where a story was relabelled - `desk_count` is - and it keeps "
            "this meaning because 22 frozen published days already carry it."
        ),
    )
    desk_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Stories this day publishes under this name, which is the number a reader "
            "sees. Equal to `count` on a day nothing relabelled. Null on a day "
            "published before this field existed, where a page falls back to `count`."
        ),
    )
    considered: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Distinct addresses the feeds offered this vertical today, less what the "
            "day had already published or already failed on. It is not an upper bound "
            "on `count`: each run counts its own pool and the day's stories accumulate "
            "across runs."
        ),
    )
    too_old: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Of those, how many were past collect.max_age_hours. A vertical fed by a "
            "back catalogue thins for this reason and no other, and a thin topic that "
            "cannot say why reads as a broken run."
        ),
    )
    below_feed_floor: bool | None = Field(
        default=None,
        description=(
            "Some run today found fewer live feeds than this vertical's floor, so that "
            "run planned nothing for it. Published for the operator surfaces; the "
            "reading page never draws a sentence from it, because how many of our "
            "feeds answered is a fact about our pipeline rather than about a story."
        ),
    )

    @model_validator(mode="after")
    def _the_three_shortfall_fields_arrive_together(self) -> Self:
        absent = [
            self.considered is None,
            self.too_old is None,
            self.below_feed_floor is None,
        ]
        if any(absent) and not all(absent):
            raise ValueError("a topic carries every shortfall field or none of them")
        if self.considered is not None and self.too_old is not None:
            if self.too_old > self.considered:
                raise ValueError("a topic cannot drop more stories than it considered")
        return self


class DigestLead(Model):
    """One of the day's leading stories, and the one sentence saying why it leads.

    The story itself stays in `items` in the published order, so the block adds
    a way in and removes nothing. Nothing here carries a position: a number
    beside a story implies a score we would then owe the reader an explanation
    for.
    """

    item_id: ItemId
    reason: str = Field(
        min_length=1,
        description=(
            "One sentence a reader can check against the story, built from our own "
            "published title and our own closed registry and never from fetched text "
            "(Guardrail #11). A lead that cannot say something true is not a lead."
        ),
    )


class DigestItem(Model):
    """One item as a reader consumes it. The link is a first-class element, not a footnote."""

    item_id: ItemId
    vertical: Slug = Field(
        description=(
            "The vertical the carrying feed declares. `item_id` is addressed from it, "
            "so it is the story's address and never a reading of the story."
        )
    )
    desk: Slug | None = Field(
        default=None,
        description=(
            "Where the day publishes this story, which is the topic a reader finds it "
            "under. Null says nothing relabelled it and a page falls back to "
            "`vertical`; null is never read as a desk of its own."
        ),
    )
    secondary_desk: Slug | None = Field(
        default=None,
        description=(
            "The one other desk this story has a claim to, and the desk the day sends "
            "it to when the one it is on is over its ceiling. It never equals the desk "
            "the day filed the story under, so a story names at most two desks. Null "
            "says nothing has named a second one, and is never read as 'no second "
            "desk'. No page draws it yet: `count` and `desk_count` both still answer "
            "for the desk a story is filed under."
        ),
    )
    title: UntrustedLine
    source_url: Url
    source_id: Slug
    source_name: str = Field(min_length=1)
    source_kind: SourceKind = Field(
        default=SourceKind.REPORTING,
        description="Who is speaking. A vendor's own copy must not look like a reporter's.",
    )
    published_at: Timestamp | None = None
    time_source: TimeSource | None = Field(
        default=None,
        description=(
            "Which clock published_at came from - the feed's, or our first sight of "
            "the address. Null on a day published before this existed, and that reads "
            "as unknown rather than as a claim about either clock."
        ),
    )

    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    lenses: list[Slug] = Field(default_factory=list)
    events: list[Slug] = Field(default_factory=list)
    entities: list[Slug] = Field(default_factory=list)

    band: ConfidenceBand
    band_reason: BandReason | None = Field(
        default=None,
        description=(
            "Why the item is not in the top band. An identifier the site turns into a "
            "sentence; null on a `high` item and on a day published before this existed."
        ),
    )
    source_form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description="Declared feed form, so a reader can see when an item is an abstract.",
    )
    reader_note: str | None = Field(
        default=None,
        description="Our sentence explaining a source limitation, never a badge.",
    )
    truncated: bool = Field(
        default=False, description="The reader is told before they find out by clicking through."
    )
    visual: DigestVisual | None = None
    carried_by: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many feeds carried this one address today. Syndication of a single "
            "story, never 'also covered by N sources' - two outlets writing their own "
            "piece produce two addresses and both read 1. Null where the run did not "
            "record it, which is not the same as 1."
        ),
    )
    watchlist_hit: bool | None = Field(
        default=None,
        description="The story names a watchlist entity. Null where the run did not record it.",
    )
    on_front_page: bool | None = Field(
        default=None,
        description=(
            "A salience feed voted for it. A vote, never a discovery. Null where the "
            "run did not record it, which is not the same as false."
        ),
    )
    rank_score: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "What the planning step scored this story at, against the other stories of "
            "its own vertical. Comparable across the day because every vertical uses "
            "one scale. Null where the run did not record it, which is not the same "
            "as 0."
        ),
    )
    also_covered_by: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many OTHER sources carried the same story today, counted over the "
            "day's own items. Not `carried_by`, which counts syndication of one "
            "address and reads 1 when two outlets write their own piece. 0 says only "
            "one of our sources carried it. Null says the pass could not tell - the "
            "day carries no vectors, or this item has none - and is never read as 0."
        ),
    )
    same_story_as: ItemId | None = Field(
        default=None,
        description=(
            "The item the default view keeps for this story. Null on the item that is "
            "kept and on an item nothing grouped with. Nothing is unpublished: a "
            "collapsed item keeps its place in this list, its anchor and its archive "
            "entry."
        ),
    )
    introduced_by_run: int = Field(
        ge=1, description="A global fact, true for every reader, asserted without any storage."
    )
    updated_at: Timestamp | None = Field(
        default=None,
        description=(
            "Reserved. Null in every payload ever written, because no run can revise "
            "an item: `rank.plan_vertical` drops a candidate already in the published "
            "ledger under `state/published/`, `cli` supplies that set, and "
            "`assemble.build_day` drops an item the day already holds. If a run ever "
            "does revise, the rule it must keep is that the item says so."
        ),
    )
    updated_by_run: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Reserved, and null everywhere for the same reason as `updated_at`. It "
            "would name the run that wrote the words this item carries, so the join to "
            "the run manifest answers with the right model. Until then "
            "`assemble.run_that_wrote` answers with `introduced_by_run`."
        ),
    )

    @model_validator(mode="after")
    def _item_id_is_addressed_by_vertical(self) -> Self:
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self

    @model_validator(mode="after")
    def _a_story_names_at_most_two_desks(self) -> Self:
        """The second desk is a second one, so it cannot be the first.

        A story filed under one name and claiming the same name twice reads as
        two desks to anything counting them, and is one desk to a reader.
        """
        if self.secondary_desk is not None and self.secondary_desk == (self.desk or self.vertical):
            raise ValueError("secondary_desk repeats the desk the day filed the story under")
        return self

    @model_validator(mode="after")
    def _a_revision_names_the_run_that_wrote_it(self) -> Self:
        if (self.updated_at is None) != (self.updated_by_run is None):
            raise ValueError("a revision carries both updated_at and updated_by_run")
        if self.updated_by_run is not None and self.updated_by_run < self.introduced_by_run:
            raise ValueError("a revision cannot precede the run that introduced the item")
        return self

    @model_validator(mode="after")
    def _the_clock_and_the_time_agree(self) -> Self:
        if self.time_source is not None and self.time_source.names_a_clock != (
            self.published_at is not None
        ):
            raise ValueError("time_source names a clock exactly when published_at carries a time")
        return self

    @model_validator(mode="after")
    def _a_collapsed_item_knows_its_count(self) -> Self:
        if self.same_story_as == self.item_id:
            raise ValueError("an item cannot be the same story as itself")
        if self.same_story_as is not None and self.also_covered_by is None:
            raise ValueError("an item the view collapses knows how many sources covered it")
        return self


class DigestEmbeddings(Model):
    """The day's item vectors, so a browser only ever embeds a reader's query.

    Inside the day payload rather than beside it, because the per-page request
    count is fixed and a sidecar would add one to every page whether or not a
    reader ever searches.

    Self-describing on purpose: a reader-side decoder that guesses the width or
    the dtype produces plausible nonsense instead of an error. Every field here
    exists so that a mismatch fails loudly.

    This whole block is optional and strippable. A day with no `embeddings`
    renders identically; it simply cannot be searched on the device.
    """

    model_id: Slug
    dimensions: int = Field(ge=1)
    dtype: Literal["int8"]
    vectors: dict[str, str] = Field(
        default_factory=dict,
        description="item_id -> base64 of the quantised vector, one entry per embedded item.",
    )


class DigestDay(Contract):
    """`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json`."""

    __schema_stem__: ClassVar[str] = "digest-day"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T22:30",
            change="Retired DigestVisual.path, which named the committed drawing.",
            why="The reader's browser draws the chart now, so no SVG is written.",
        ),
        ChangelogEntry(
            version="2026-09-13T20:00",
            change="Added DigestVisual.data_path - where this visual's data file landed.",
            why="The reader's browser draws the chart, so it needs the marks rather than an SVG.",
        ),
        ChangelogEntry(
            version="2026-09-13",
            change="Added DigestItem.secondary_desk - the one other desk a story has a claim to.",
            why="The desk ceiling sends an over-ceiling story to a second desk, unnamed.",
        ),
        ChangelogEntry(
            version="2026-09-12T18:40",
            change="item_id accepts a second shape: sixteen Crockford base32 symbols.",
            why="Ten decimal digits is 33 bits of an address, which collides on a busy day.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    date: DateStamp
    generated_at: Timestamp
    partial: bool = Field(description="A run with failures publishes, and says it was partial.")
    items_planned: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    retention_window_months: int = Field(
        default=-1,
        ge=-1,
        description="Stated to the reader before anything is deleted. -1 means nothing is deleted.",
    )
    runs: list[DigestRunRef] = Field(min_length=1)
    verticals: list[DigestVerticalRef]
    items: list[DigestItem]
    leads: list[DigestLead] = Field(
        default_factory=list,
        description=(
            "The day's leading stories, strongest first, chosen across the whole day "
            "rather than off the head of the published order. Empty is the normal "
            "state and it means the block does not render: a day with too few stories "
            "worth leading goes straight to the stream rather than padding. Every "
            "entry names an item this same day holds."
        ),
    )
    embeddings: DigestEmbeddings | None = None

    @model_validator(mode="after")
    def _order_is_global_and_append_only(self) -> Self:
        item_ids = [item.item_id for item in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("item ids must be distinct within a day")

        introduced = [item.introduced_by_run for item in self.items]
        if introduced != sorted(introduced):
            raise ValueError("a later run appends; it never reorders what a reader already read")

        run_numbers = [run.n for run in self.runs]
        if run_numbers != list(range(1, len(self.runs) + 1)):
            raise ValueError("runs are numbered from 1 without gaps")
        if introduced and max(introduced) > len(self.runs):
            raise ValueError("an item cannot be introduced by a run that is not recorded")

        revised = [item.updated_by_run for item in self.items if item.updated_by_run is not None]
        if revised and max(revised) > len(self.runs):
            raise ValueError("an item cannot be revised by a run that is not recorded")

        for run in self.runs:
            if introduced.count(run.n) != run.items_added:
                raise ValueError(f"run {run.n} items_added disagrees with the items it introduced")

        counted = {ref.id: ref.count for ref in self.verticals}
        if len(counted) != len(self.verticals):
            raise ValueError("vertical ids must be distinct")
        for item in self.items:
            if item.vertical not in counted:
                raise ValueError(f"item {item.item_id} names an unlisted vertical")
            if item.desk is not None and item.desk not in counted:
                raise ValueError(f"item {item.item_id} names an unlisted desk")
            if item.secondary_desk is not None and item.secondary_desk not in counted:
                raise ValueError(f"item {item.item_id} names an unlisted second desk")
        for vertical_id, count in counted.items():
            actual = sum(1 for item in self.items if item.vertical == vertical_id)
            if actual != count:
                raise ValueError(f"vertical {vertical_id} count disagrees with its items")
        for ref in self.verticals:
            if ref.desk_count is None:
                continue
            drawn = sum(1 for item in self.items if (item.desk or item.vertical) == ref.id)
            if drawn != ref.desk_count:
                raise ValueError(f"desk {ref.id} desk_count disagrees with its items")

        if self.partial != (self.items_failed > 0):
            raise ValueError("partial is exactly whether anything failed")
        if len(self.items) + self.items_failed > self.items_planned:
            raise ValueError("published plus failed cannot exceed planned")
        return self

    @model_validator(mode="after")
    def _a_lead_names_a_story_this_day_holds(self) -> Self:
        """The block is a way into the day, so it can only point at the day.

        A lead naming an item the payload does not carry is a link to nothing,
        and it fails here rather than on the page.
        """
        led = [lead.item_id for lead in self.leads]
        if len(set(led)) != len(led):
            raise ValueError("one story may lead only once")
        held = {item.item_id for item in self.items}
        for item_id in led:
            if item_id not in held:
                raise ValueError(f"lead {item_id} names a story this day does not hold")
        return self

    @model_validator(mode="after")
    def _the_view_collapses_onto_an_item_it_draws(self) -> Self:
        """A collapsed item points at one the day keeps, and the chain is one link.

        Two stories collapsed onto an item that is itself collapsed would leave
        the strongest of the three drawing a count that came from somewhere
        else, and the reader with no way back to either. The pass builds a
        keeper and its members; this is the shape that says so.
        """
        kept = {item.item_id for item in self.items if item.same_story_as is None}
        for item in self.items:
            target = item.same_story_as
            if target is None:
                continue
            if target not in kept:
                raise ValueError(
                    f"item {item.item_id} collapses onto {target}, "
                    "which this day does not keep"
                )
        return self
