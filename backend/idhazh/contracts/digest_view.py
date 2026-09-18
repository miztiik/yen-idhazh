"""The served day payload - what a reader's browser actually fetches.

`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json` is the committed day and
it is read from disk at build time. This is the other file: the projection
`frontend/scripts/copy-visuals.mjs` stages into `frontend/static/digest/`, which
the published site serves at `<base>/digest/<YYYY>/<MM>/<DD>/digest.json` and a
browser fetches over the network.

**It is a contract because it has a consumer we cannot upgrade** (Guardrail #3).
Until 2026-08-31 the field list was a JavaScript array in a build script, which
was honest while the one reader was our own archive page rendering a search
result. It stops being honest the moment a reader's cached shell fetches this
file: the shell in their browser can be older than the payload it reads, so the
shape has to carry its own `version` and every change to it has to say what an
older shell does (section 11). That address cannot move afterwards either.

**The read-side rule, in one sentence: absent and null both mean unknown, and a
reader may never fill either with a default.** Every plausible default is a
false claim - `0` for `carried_by` says no feed carried the story, `false` for
`on_front_page` denies a vote nobody counted, `0.0` for `rank_score` puts the
story at the bottom of its vertical. The projector writes an explicit null for a
key the committed day does not hold, so an older shell sees a key it knows with
a value it can read; a newer shell reading an older file sees the key missing.
Both are the same fact and neither is a value.

**The migration path a change to this shape has to take.** Additive: declare the
field optional, stamp the version, append the changelog entry - an older shell
ignores a key it does not know, so nothing else is owed. Breaking: the read-side
migration lands in the shell, not only in the build, because the two are not
upgraded together and a reader can hold a shell for as long as their cache does.

**Since 2026-09-09 it carries the day's own facts as well as the day's stories**,
and every one of them is optional. A dated URL is served by one shell that no
build wrote a day into, so the browser has no other source for the date, the
topics, the leading block, the run list or the day notice. A service worker keeps
a day, so a shell built after that change can be handed a payload written before
it - which is why absent has to be readable, and why absent reads as unknown and
never as a value.

What it drops, and what that is worth. Measured 2026-08-31 on this checkout,
11 committed days and 3,733 items, `gzip -9` over the compact projection: the
committed day is 792.65 gzipped bytes an item, and this projection is 468.58 -
40.9 percent less. `embeddings` is the block that pays for the projection
existing at all: no browser opens it, its one production reader is the backend's
index rebuild, and it was 40.0 percent of a day page. `events` and `entities`
are dropped because nothing renders them and the reading-page plan forbids
publishing them as reader-facing chips; `source_form`, `updated_at` and
`updated_by_run` because no component reads them - `updated_at` is null in every
payload ever written.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    Prose,
    RelPath,
    Slug,
    Timestamp,
    Url,
    compact_json,
)
from idhazh.contracts.digest_day import (
    EARLIER_OUTLETS_MAX,
    DigestLead,
    DigestRunRef,
    DigestVerticalRef,
    EarlierStory,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.visual_decision import VisualState

#: How many publisher names a served item may carry.
#:
#: A shape rather than a tuning, which is why it is here and not in `config/`.
#: The names ride to every reader on every grouped story, so the number decides
#: what the payload weighs and what an older shell has to be able to read - and a
#: file written under one cap has to stay readable under another. Three is what a
#: card can print on one line beside the confidence chip at 360px; the rest is a
#: count the reader already has in `also_covered_by`, so nothing is hidden by
#: stopping here.
COVERAGE_NAMES_MAX = 3


def coverage_names(items: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Which other newsrooms ran each story, by name, from the day's own grouping.

    `frontend/src/lib/payload/project.ts` holds the same rule for the projector
    that writes the file, and a contract test drives both over one day and
    compares. The derivation is here rather than on the committed item because
    every committed day already carries `same_story_as` and none of them carries
    this - so deriving it at projection time gives a reader the names on a day
    published before the names existed, where a new field on `DigestDay` would
    give them an empty list until the day was rebuilt, which never happens.

    One entry per OTHER OUTLET, never one per member: `also_covered_by` counts
    mastheads, so a list that counted pieces would print a longer stack than the
    sentence beside it admits to. The outlet's strongest piece is the one linked,
    because that is the telling of the story we would rather the reader opened.

    Ordered by `rank_score`, strongest first, with an unscored piece last and
    `item_id` breaking every tie - a total order, so the projector in the other
    language cannot sort the same day differently.
    """

    def strength(item: Mapping[str, Any]) -> tuple[float, str]:
        score = item.get("rank_score")
        address = str(item.get("item_id") or "")
        # `rank_score` is `ge=0.0`, so an unscored piece sorts behind every scored
        # one without a score being invented for it. A bool is an int in Python
        # and is not a score.
        if isinstance(score, bool) or not isinstance(score, int | float):
            return (1.0, address)
        return (-float(score), address)

    present = {
        item.get("item_id") for item in items if isinstance(item.get("item_id"), str)
    }
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        item_id = item.get("item_id")
        if not isinstance(item_id, str):
            continue
        named = item.get("same_story_as")
        # A story naming an anchor this day does not hold is its own group. The
        # page cannot draw a card that is not here, so neither may this list.
        anchor = named if isinstance(named, str) and named in present else item_id
        groups.setdefault(anchor, []).append(item)

    covered: dict[str, list[dict[str, Any]]] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        ranked = sorted(members, key=strength)
        for item in members:
            mine = item.get("source_name")
            seen: set[str] = set()
            names: list[dict[str, Any]] = []
            for other in ranked:
                outlet = other.get("source_name")
                if not isinstance(outlet, str) or outlet == mine or outlet in seen:
                    continue
                seen.add(outlet)
                names.append({"source_name": outlet, "item_id": other.get("item_id")})
            covered[str(item.get("item_id"))] = names[:COVERAGE_NAMES_MAX]
    return covered


class DigestCoverage(Model):
    """One other newsroom that ran the same story, and the way in to its piece.

    The link is to OUR page for that piece - our summary of it, and its own
    `Read the original` - never straight out to the publisher. A reader who
    wanted the publisher's version is one more click away and a reader who
    wanted ours has not lost it.
    """

    source_name: str = Field(min_length=1, description="The masthead, as the card prints it.")
    item_id: ItemId = Field(description="That newsroom's own story, which still has its address.")


class DigestViewVisual(Model):
    """The chart, as the browser that draws it needs it.

    `kind` is not here. It is read at build time off the committed tree for the
    console's chart count, and a browser that has already been handed the marks
    has no use for it.

    **`data_path` is the whole of what a fetched story gets**, and it replaced
    `path` on 2026-09-13. The reader's browser draws the chart from that file, so
    a projection that dropped the key would leave every story past the document's
    seed unable to ask for its own picture - which is every story on a dated page.
    """

    state: VisualState
    data_path: RelPath | None = Field(
        default=None,
        description=(
            "Where this visual's marks are, relative to frontend/public/. Null on a day "
            "published before the file existed - absent and null are the same fact, and "
            "both mean the story simply has no chart."
        ),
    )
    alt: UntrustedLine | None = Field(
        default=None,
        description=(
            "What the figure is labelled with. On a page that never runs a script it is "
            "the whole of what a reader receives for this visual."
        ),
    )


class DigestViewItem(Model):
    """One item, narrowed to what a page renders from it.

    Every field here has a named renderer. The list is not "the published item
    minus the big bits" - it is traced along the render path, and a field
    without a reader does not earn the wire.
    """

    item_id: ItemId
    vertical: Slug
    desk: Slug | None = Field(
        default=None,
        description=(
            "Where the day publishes this story, which is the topic a reader finds it "
            "under. Null says nothing relabelled it and the page falls back to "
            "`vertical`. Null is never read as a desk of its own."
        ),
    )
    title: UntrustedLine
    summary: Prose = Field(min_length=1)
    reader_note: str | None = Field(
        default=None,
        description="Our sentence explaining a source limitation, never a badge.",
    )
    band: ConfidenceBand
    band_reason: BandReason | None = Field(
        default=None,
        description=(
            "Why the item is not in the top band. Null on a `high` item and on a day "
            "published before this existed - 14 of 3,733 committed items on 2026-08-31."
        ),
    )
    truncated: bool = Field(
        default=False, description="The reader is told before they find out by clicking through."
    )
    visual: DigestViewVisual | None = None
    source_name: str = Field(min_length=1)
    source_id: Slug
    source_kind: SourceKind = Field(
        default=SourceKind.REPORTING,
        description="Who is speaking. A vendor's own copy must not look like a reporter's.",
    )
    source_url: Url
    published_at: Timestamp | None = None
    time_source: TimeSource | None = Field(
        default=None,
        description=(
            "Which clock `published_at` came from. Null reads as unknown: a page that "
            "prints a time without naming its clock cannot say which of the two it has."
        ),
    )
    carried_by: int | None = Field(
        default=None,
        ge=1,
        description="How many feeds carried this one address. Null is unknown, never 1.",
    )
    watchlist_hit: bool | None = Field(
        default=None,
        description="The story names a watchlist entity. Null is unknown, never false.",
    )
    on_front_page: bool | None = Field(
        default=None,
        description="A salience feed voted for it. Null is unknown, never false.",
    )
    rank_score: float | None = Field(
        default=None,
        ge=0.0,
        description="What the planning step scored the story at. Null is unknown, never 0.",
    )
    also_covered_by: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many other OUTLETS carried the same story today - a masthead, not a "
            "feed, so an outlet with four feeds counts once. It is the count and "
            "`covered_by` is the names, and the two answer different questions: this one "
            "is whole where the names are capped, so the card prints the difference as a "
            "remainder. On a card with no stack, 1 or more prints 'Also covered by N "
            "other sources today.' 0 and null both print nothing: null "
            "means the day recorded no answer, and 0 stopped printing 'Only one of our "
            "sources carried this.' on 2026-09-14 because the pass finds far too little "
            "of the day's duplication for that sentence to be true. See "
            "docs/architecture/publishing/layout.md."
        ),
    )
    introduced_by_run: int = Field(
        ge=1, description="A global fact, true for every reader, asserted without any storage."
    )
    lenses: list[Slug] = Field(default_factory=list)
    key_points: list[str] = Field(min_length=1)
    same_story_as: ItemId | None = Field(
        default=None,
        description=(
            "The item the page draws this story on, null on the one that is drawn. It was "
            "on the committed item and off the wire until 2026-09-16, because no page "
            "folded a group and a field with no renderer does not earn the wire. The page "
            "folds now: a story naming another is not drawn as its own card. It is not "
            "removed - it keeps its address, its archive entry and its month search "
            "entry, and the anchor's card links to it by name."
        ),
    )
    covered_by: list[DigestCoverage] = Field(
        default_factory=list,
        max_length=COVERAGE_NAMES_MAX,
        description=(
            "Which other newsrooms ran this story, by name, strongest first. Empty on a "
            "story the day grouped with nothing, and empty on a day published before the "
            "pass existed - both mean the page draws no publisher stack. It is capped, so "
            "it is never the whole of the count: `also_covered_by` is how many other "
            "outlets there are, and the card prints the difference as a remainder."
        ),
    )
    also_ran_earlier: tuple[EarlierStory, ...] = Field(
        default=(),
        max_length=EARLIER_OUTLETS_MAX,
        description=(
            "Which newsrooms ran this same story on an EARLIER published day. Copied "
            "straight off the committed item rather than derived here, because this "
            "projection can only see one day and a name it would have to fetch from "
            "another day is a name it would silently drop. Each entry is one more name "
            "in the card's stack, pointing at that day's page rather than at an anchor "
            "on this one. It folds nothing: the story keeps its own card."
        ),
    )

    @model_validator(mode="after")
    def _item_id_is_addressed_by_vertical(self) -> Self:
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self

    @model_validator(mode="after")
    def _the_clock_and_the_time_agree(self) -> Self:
        if self.time_source is not None and self.time_source.names_a_clock != (
            self.published_at is not None
        ):
            raise ValueError("time_source names a clock exactly when published_at carries a time")
        return self


class DigestView(Contract):
    """`<base>/digest/<YYYY>/<MM>/<DD>/digest.json`, as a browser fetches it."""

    __schema_stem__: ClassVar[str] = "digest-view"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-17",
            change="DigestViewItem.summary is Prose - paragraphs split by one blank line.",
            why="A long summary is two paragraphs, and read-side folding keeps old days readable.",
        ),
        ChangelogEntry(
            version="2026-09-16T00:40",
            change="Added DigestViewItem.same_story_as and .covered_by.",
            why="The page folds a group into one card, which has to name the other outlets.",
        ),
        ChangelogEntry(
            version="2026-09-13T22:30",
            change="DigestViewVisual.path became data_path.",
            why="The reader's browser draws the chart from the marks, so no SVG is published.",
        ),
        ChangelogEntry(
            version="2026-09-12T18:40",
            change="item_id accepts a second shape: sixteen Crockford base32 symbols.",
            why="Ten decimal digits is 33 bits of an address, which collides on a busy day.",
        ),
        ChangelogEntry(
            version="2026-08-31T12:00",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    # The day's own facts. Every one of them is optional and that is the read-side
    # rule rather than a softness: a service worker keeps a day, so a shell built
    # after this can fetch a payload written before it, and the only honest reading
    # of a name that file does not carry is unknown. A page fills none of them in.
    date: DateStamp | None = None
    generated_at: Timestamp | None = Field(
        default=None,
        description=(
            "What a republish moves and nothing else does, so a browser holding this "
            "day can tell a re-fetch that changed nothing from one that did."
        ),
    )
    partial: bool | None = Field(
        default=None,
        description="Null is unknown, never false: false says the run lost nothing.",
    )
    items_planned: int | None = Field(default=None, ge=0)
    items_failed: int | None = Field(
        default=None, ge=0, description="Null is unknown, never 0: 0 says nothing failed."
    )
    retention_window_months: int | None = Field(
        default=None,
        ge=-1,
        description=(
            "Stated to the reader before anything is deleted. -1 is the day saying "
            "nothing is deleted; null is the payload not saying, and a page prints "
            "neither sentence for it."
        ),
    )
    runs: Annotated[list[DigestRunRef], Field(min_length=1)] | None = None
    verticals: list[DigestVerticalRef] | None = Field(
        default=None,
        description="Null is unknown, never an empty list: empty says the day had no desk.",
    )
    leads: list[DigestLead] | None = Field(
        default=None,
        description=(
            "Null is the payload not saying; an empty list is the day saying it has no "
            "leading block, which is its ordinary state. Both draw nothing."
        ),
    )
    items: list[DigestViewItem]

    @classmethod
    def project(cls, day: Mapping[str, Any]) -> Self:
        """A committed day narrowed the way `frontend/src/lib/payload/project.ts` narrows it.

        The field list is read off the models rather than written out again, so
        this and the projector cannot name two different shapes - and a contract
        test reads the arrays out of `project.ts` and fails when they drift.

        An absent key becomes an explicit null rather than being left out, which
        is what makes every served item the same shape whichever day it was
        published on.

        **A day whose item list is not a list of objects is handed to the model
        as it arrived.** Narrowing it here would throw a `TypeError`, and the
        one caller that matters is a validator over every committed day: a
        stack trace on day three tells nobody which day is broken or why, where
        the model reports both.
        """
        served: dict[str, Any] = {
            name: day.get(name) for name in cls.model_fields if name not in {"version", "items"}
        }
        served["version"] = cls.schema_version()
        written = day.get("items")
        if not isinstance(written, list) or not all(isinstance(item, Mapping) for item in written):
            return cls.model_validate({**served, "items": written})
        visual_names = list(DigestViewVisual.model_fields)
        # The one name on a served item the committed day does not hold. It is a
        # fact about the day rather than about one story, so it is computed once
        # over the whole list and read out of the map below.
        covered = coverage_names(written)
        items: list[dict[str, Any]] = []
        for item in written:
            names = DigestViewItem.model_fields
            item_view: dict[str, Any] = {name: item.get(name) for name in names}
            visual = item.get("visual")
            item_view["visual"] = (
                {name: visual.get(name) for name in visual_names}
                if isinstance(visual, Mapping)
                else None
            )
            item_view["covered_by"] = covered.get(str(item.get("item_id")), [])
            # Absent on every day published before 2026-09-16, and an absent list
            # is an empty one rather than a null - the field is a list of names
            # and null is not one.
            item_view["also_ran_earlier"] = item.get("also_ran_earlier") or []
            items.append(item_view)
        return cls.model_validate({**served, "items": items})

    @model_validator(mode="after")
    def _the_published_order_survives_the_projection(self) -> Self:
        item_ids = [item.item_id for item in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("item ids must be distinct within a day")
        introduced = [item.introduced_by_run for item in self.items]
        if introduced != sorted(introduced):
            raise ValueError("a later run appends; it never reorders what a reader already read")
        return self

    @model_validator(mode="after")
    def _a_day_fact_agrees_with_the_stories_beside_it(self) -> Self:
        """The same rules `DigestDay` holds, over whichever facts this file carries.

        A narrowing that keeps a fact and drops the check on it is a weaker
        contract than the one it narrows, and this is the copy a browser reads.
        Each clause is skipped when the payload does not carry what it needs,
        because an older file carries none of them.
        """
        if self.partial is not None and self.items_failed is not None:
            if self.partial != (self.items_failed > 0):
                raise ValueError("partial is exactly whether anything failed")
        if self.items_planned is not None and self.items_failed is not None:
            if len(self.items) + self.items_failed > self.items_planned:
                raise ValueError("published plus failed cannot exceed planned")
        if self.verticals is not None:
            counted = {ref.id: ref.count for ref in self.verticals}
            if len(counted) != len(self.verticals):
                raise ValueError("vertical ids must be distinct")
            drawn = Counter(item.vertical for item in self.items)
            unlisted = sorted(set(drawn) - set(counted))
            if unlisted:
                raise ValueError(f"items name an unlisted vertical: {', '.join(unlisted)}")
            for vertical_id, count in counted.items():
                if drawn[vertical_id] != count:
                    raise ValueError(f"vertical {vertical_id} count disagrees with its items")
            published = Counter(item.desk or item.vertical for item in self.items)
            unlisted = sorted(set(published) - set(counted))
            if unlisted:
                raise ValueError(f"items name an unlisted desk: {', '.join(unlisted)}")
            for ref in self.verticals:
                if ref.desk_count is not None and published[ref.id] != ref.desk_count:
                    raise ValueError(f"desk {ref.id} desk_count disagrees with its items")
        if self.leads is not None:
            led = [lead.item_id for lead in self.leads]
            if len(set(led)) != len(led):
                raise ValueError("one story may lead only once")
            held = {item.item_id for item in self.items}
            for item_id in led:
                if item_id not in held:
                    raise ValueError(f"lead {item_id} names a story this day does not hold")
        return self

    def to_json(self) -> str:
        """Compact, like the month index and unlike every committed payload.

        A reader downloads this whole and its entries are counted in hundreds.
        The indent every other payload pays for buys a reviewable diff, and
        nobody reviews a diff of a file that is regenerated on every build.
        """
        return compact_json(self.model_dump(mode="json"))
