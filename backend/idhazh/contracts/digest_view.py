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
from collections.abc import Mapping
from typing import Annotated, Any, ClassVar, Self

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
    compact_json,
)
from idhazh.contracts.digest_day import DigestLead, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.run_plan import TimeSource
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.visual_decision import VisualState


class DigestViewVisual(Model):
    """The rendered chart, as the `<img>` needs it.

    `kind` is not here. It is read at build time off the committed tree for the
    console's chart count, and a browser drawing the image has no use for it.
    """

    state: VisualState
    path: RelPath | None = None
    alt: UntrustedLine | None = None

    @model_validator(mode="after")
    def _only_a_rendered_visual_has_a_path(self) -> Self:
        if (self.state is VisualState.RENDERED) != (self.path is not None):
            raise ValueError("a path is present exactly when the visual rendered")
        return self


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
    summary: str = Field(min_length=1)
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
            "How many other sources carried the same story today. 0 is the sentence "
            "'Only one of our sources carried this.' Null is unknown, and prints "
            "nothing at all."
        ),
    )
    introduced_by_run: int = Field(
        ge=1, description="A global fact, true for every reader, asserted without any storage."
    )
    lenses: list[Slug] = Field(default_factory=list)
    key_points: list[str] = Field(min_length=1)

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
            version="2026-09-12T18:40",
            change=(
                "item_id accepts a second shape: sixteen Crockford base32 symbols "
                "beside the decimal digits it already took."
            ),
            why=(
                "Ten decimal digits is 33 bits of the address, which collides often "
                "enough that the collision had to be resolved - and the only way to "
                "resolve one is to step the loser past whatever else the run planned, "
                "so a collided id depended on the day's pool rather than on the "
                "address alone. Two runs of one day draw different pools, so the same "
                "article came back under a second id and published twice. Eighty bits "
                "do not collide. This widens and never contracts: every day published "
                "before today carries the decimal shape and a published day is frozen, "
                "so nothing was rewritten and no read-side migration is owed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T06:56",
            change=(
                "Added DigestViewItem.desk, so a served item says which topic the day "
                "publishes it under. DigestVerticalRef, which this file reuses, gained "
                "desk_count beside count; count keeps meaning the vertical count."
            ),
            why=(
                "This is the copy a browser fetches, and the reading page is what groups "
                "stories under a topic - so a desk the committed day knows and this file "
                "drops is a grouping the page cannot make. Additive and optional: an "
                "older shell ignores a key it does not know, and a newer shell reading a "
                "payload written before today sees null and falls back to `vertical`, "
                "which is what every one of those days meant. So nothing else is owed on "
                "the read side (section 11). Costs one name on the item list, which is "
                "the per-item half of the wire; the day-level desk_count rides on "
                "`verticals`, which was already carried."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T03:55",
            change=(
                "lenses on a served item is a list of Slug rather than of the closed "
                "LensId enum, which is deleted. The schema gates the slug pattern and "
                "no longer enumerates the members."
            ),
            why=(
                "This is the payload a browser fetches, so the enum was a second copy of "
                "the vocabulary that had to be regenerated and redeployed before a "
                "config edit could take effect. Read-compatible, and here that is a "
                "promise to a device rather than to a job: a service worker keeps days, "
                "so a shell holding a payload written weeks ago reads every id it "
                "carries unchanged. The reading side takes the other half of the same "
                "change - it renders an id the committed vocabulary cannot name rather "
                "than dropping the chip, so a day cannot quietly stop saying what it "
                "said (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Added the day's own facts to a served day: date, generated_at, "
                "partial, items_planned, items_failed, retention_window_months, runs, "
                "verticals and leads. Every one of them is optional."
            ),
            why=(
                "Until now this file carried a day's stories and nothing about the day "
                "itself, which was enough while the only page reading it already held "
                "those facts in its own document. A dated URL is about to be served by "
                "one shell that no build wrote a day into, so the browser has no other "
                "source for them: no topic pills, no leading block, no day notice and "
                "no story count. Nine names, each with a named renderer - date, "
                "verticals and leads for DigestList; runs, partial, items_planned, "
                "items_failed and retention_window_months for the day notice and the "
                "footer; generated_at for the revision key the day cache already reads "
                "and never found. Measured 2026-09-09 on Intel Core i7-1265U / "
                "Windows 11 over the 20 committed days and 7,967 items, gzip -9 over "
                "the compact projection: 322 bytes a day on average and 478 on the "
                "worst day, against 3,657,996 bytes of served days, which is 0.18 "
                "percent. A day pays it once, where an item field pays it per story, "
                "so nine names here cost less than one name on the item list. "
                "Additive, so a shell holding a payload written before this - "
                "a service worker keeps days - reads every one of them as absent, and "
                "absent is unknown rather than a value."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T09:00",
            change="Added also_covered_by to a served item.",
            why=(
                "It has a named renderer, which is the bar every field here answers "
                "to: `ItemMeta` prints the sentence that says how many other sources "
                "carried the story, or that only one of ours did. Measured 2026-09-01 "
                "on Intel Core i7-1265U / Windows 11 over 11 committed days and 3,978 "
                "items, gzip -9 over the compact projection, the name added to the "
                "twenty-two-field arm: 467.49 bytes an item before and 468.24 after, "
                "which is 0.75 an item and 0.16 percent. Its sibling on the committed "
                "item, same_story_as, is NOT here: no page draws a group as one item "
                "yet, and a field without a reader does not earn the wire. It arrives "
                "when a reading route can also say where the items it stopped drawing "
                "went. Additive, so an older shell ignores the key and draws the page "
                "it drew yesterday."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T12:00",
            change=(
                "Initial shape: the day's items narrowed to what a page renders, "
                "carrying a version of their own."
            ),
            why=(
                "The staged day payload was a thirteen-name array in a build script, "
                "which was enough while the only reader was our own archive page. A "
                "reading route is about to fetch this file, so a browser we cannot "
                "upgrade will parse it and its address stops being movable - which is "
                "a persisted shape and therefore a contract before logic reads it "
                "(Guardrail #3). The version is here from the first byte so that an older "
                "shell reading a newer payload has something to branch on. Nine names "
                "join the thirteen in the same commit, each with a named renderer: "
                "carried_by, watchlist_hit, on_front_page and rank_score for the lead "
                "block, published_at and time_source for the time rail, "
                "introduced_by_run for the run divider, lenses for the topic chips, and "
                "key_points for the in-page filter that reads them today. Measured "
                "2026-08-31 over 11 committed days and 3,733 items, gzip -9: 361.10 "
                "bytes an item before and 468.58 after, against 792.65 for the "
                "committed day."
            ),
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
