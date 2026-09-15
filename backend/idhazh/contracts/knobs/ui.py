"""What the reading page looks like before a reader touches it."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import Model


class ThemeChoice(StrEnum):
    """The two themes. There is no third member for "follow the device".

    `system` was removed on 2026-08-31 with the control that offered it. It was
    not a theme - it was the absence of a choice - and keeping it here would let
    an operator set a value no surface can honour. `UiConfig` migrates an older
    file that names it (section 11).
    """

    LIGHT = "light"
    DARK = "dark"


class VisualSide(StrEnum):
    """Where a figure sits relative to the text it belongs to.

    `above` puts it before the text, `leading` beside the text on the side
    reading starts from, `trailing` after the text. A card is one column at
    every width the site ships, so `leading` cannot yet differ from `trailing`
    - a figure has no column of its own until the render spec is handed the
    width it will occupy (docs/concepts/design-system.md).
    """

    ABOVE = "above"
    LEADING = "leading"
    TRAILING = "trailing"


class UiConfig(Model):
    """The published surface's knobs.

    `sections` is the modularity story: reordering the page is a config edit,
    not a code change. What is deliberately absent is a per-element layout
    engine - on the surface that matters, a phone, there is no left and no
    right, and a per-reader layout would break the promise that a shared link
    shows the recipient what the sender saw.
    """

    sections: list[str] = Field(
        default_factory=lambda: ["notice", "leads", "topics", "items"],
        min_length=1,
        description="Render order of the day page's sections, by registry id.",
    )
    theme_default: ThemeChoice = Field(
        default=ThemeChoice.DARK,
        description=(
            "The theme a reader who has never touched the control is served. It is the "
            "theme `:root` carries in tokens.css, so it is also what a page paints "
            "before any script runs and what a page with no script keeps."
        ),
    )
    visual_side: VisualSide = Field(
        default=VisualSide.TRAILING,
        description=(
            "Where a story's figure sits relative to its text. Nothing reads it yet, and "
            "the default is what `DigestItem.svelte` renders: the figure comes after the "
            "summary at every width. It stays reserved until the render spec is handed "
            "the width the figure will occupy, because a chart drawn at 825 x 437 is "
            "illegible in a 20rem column (docs/concepts/design-system.md). "
            "`config/appearance.json` owns the value, as `digest.visual_side`."
        ),
    )
    source_mark: bool = Field(
        default=True, description="The monogram beside a source name. A scanning aid, not the id."
    )
    show_filter: bool = Field(
        default=True,
        description=(
            "An in-place filter inside the topic row. Never a top-level search bar: on a "
            "page this short it would promise an archive it cannot reach."
        ),
    )
    filter_min_chars: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "How many characters a reader types before an in-place filter narrows a "
            "list. It binds the day page and the archive, which share one panel since "
            "2026-09-01. Two rather than one because one letter narrows nothing: "
            "measured 2026-09-01 over the 12 committed days and 4,203 story titles - "
            "arithmetic over committed text, so the spread is zero by construction - "
            "the median single letter matches 80.2 percent of them and `e` matches 99.8 "
            "percent, against a median 0.8 percent for a two-letter pair. A first "
            "keystroke that redraws the page and removes almost nothing is work the "
            "reader watches for no answer. Over 8 the field stops narrowing anything a "
            "reader would think to type."
        ),
    )
    items_per_topic: int = Field(
        default=3,
        ge=1,
        deprecated=True,
        description=(
            "Retired 2026-09-01 and read by nothing. The all-topics page drew this many "
            "of each topic under a heading and put the rest behind a link, which on the "
            "431-story day of 2026-08-30 published 15 stories and hid 416. The leading "
            "block replaced the headings and the flat stream carries the whole day. "
            "Kept as a field, and dropped from the committed config, so a file written "
            "before today still validates - an unknown key is refused (section 11)."
        ),
    )
    leading_stories: int = Field(
        default=5,
        ge=1,
        description=(
            "The most stories the leading block may hold. They are chosen across the "
            "whole day, so the block is the page's first screen and the stream below it "
            "still carries every story in the published order."
        ),
    )
    leading_per_desk: int = Field(
        default=2,
        ge=1,
        description=(
            "The most leads one desk may hold. It matters more than it looks: 25 of the "
            "30 committed watchlist entries are technology companies, so the "
            "shared-subject term is structurally biased toward the AI and business "
            "desks, and this is the only thing holding it."
        ),
    )
    leading_min: int = Field(
        default=3,
        ge=1,
        description=(
            "The fewest leads worth drawing a block for. Under it nothing renders and "
            "the day goes straight to the stream, because four real leads beat five "
            "with one filler."
        ),
    )
    lead_cluster_floor: int = Field(
        default=3,
        ge=2,
        description=(
            "How many distinct sources must name one entity in their published titles "
            "before that shared subject counts for anything. Under it the term is zero. "
            "Measured 2026-09-01 over the 11 committed days and 4,086 items: at two "
            "sources 14.64 percent of stories sit in a cluster and at three it is 12.85 "
            "percent, so the stronger claim costs 73 stories in 11 days."
        ),
    )
    lead_shared_subject_weight: float = Field(
        default=0.2,
        ge=0.0,
        description=(
            "What a qualifying shared subject adds to a story's rank inside the leading "
            "block. It is a step and not a ramp: no measurement supports a shape, and a "
            "shape nobody measured may not justify a design (Guardrail #10). It must stay "
            "below what one more feed carrying the same address is worth, which is "
            "collect.carriage_step - 0.25 on the committed config - so a recurring "
            "subject cannot outrank a story two independent feeds carried today. Until "
            "2026-09-13 that bound was collect.tier_weights.trade_press times "
            "collect.repetition_weight, 0.6, because carriage multiplied a tier; it no "
            "longer multiplies anything, so the bound cannot either. Measured 2026-09-01: "
            "a second carrier fires on 4.49 percent of the stories that record it and a "
            "shared subject on 12.85 percent, 2.9 times as often. The derivation that "
            "divided 0.6 by 2.9 went with the 0.6; re-deriving this weight against the "
            "new step would move the leading block's order and belongs to plan 23 row "
            "#17's per-run loop."
        ),
    )
    lead_max_yesterday: int = Field(
        default=1,
        ge=0,
        description=(
            "The most leads the block may give to stories the feed dated to the "
            "previous calendar day. A day's leading stories are today's; one late "
            "arrival is a catch-up and three are yesterday's page."
        ),
    )
    topic_pills_max: int = Field(
        default=5,
        ge=1,
        description=(
            "How many topic pills stay on the row before an auto-created one goes "
            "inside a disclosure. A SOFT cap: a desk a person put in "
            "config/taxonomy.json is never folded away, so this bounds only the "
            "model-proposed desks sitting on the row beside them, and the row's "
            "height is the length of the vocabulary. The cut is decided by each "
            "topic's story count at build time, never by measuring the row in "
            "pixels - one order is computed in the backend and published, so a "
            "measurement taken on a reader's device could disagree with the order "
            "the payload carries. Five rather than eight since 2026-09-13: "
            "config/taxonomy.json declares five verticals, so eight was a cap "
            "nothing could reach, and the number now says what the row is for."
        ),
    )
    pill_move_min: int = Field(
        default=2,
        ge=1,
        le=3,
        description=(
            "How many stories ahead a desk must be before it takes another desk's "
            "place on the topic row. The row orders by how much of the day each "
            "desk holds and is redrawn at every publish, so with no margin a "
            "one-story lead reorders a control the reader is pointing at. One is "
            "strict count order and stays reachable. Three is the ceiling because "
            "every inversion above it sits between three-digit desks a reader "
            "cannot tell apart, so the margin stops protecting anything visible "
            "and hands the row back to the alphabet. Measured 2026-09-13 over the "
            "23 committed days carrying all five desks, 92 adjacent pairs: at two, "
            "one pair in 92 shows a smaller count first and it reads 1 ahead of 2; "
            "at three it is four pairs and the worst reads 1 ahead of 3. "
            "Arithmetic over committed payloads, so the spread is zero by "
            "construction. What it does NOT buy is steadiness across days - the "
            "same measurement counted 31 desk-days moving at two against 28 at "
            "one, so a bigger margin moves the row MORE. It bounds the reason a "
            "desk moves, never how often."
        ),
    )
    desk_thin_max: int = Field(
        default=12,
        ge=1,
        description=(
            "The most stories a desk may publish and still be called thin. A thin "
            "desk prints one sentence saying how many stories its sources offered "
            "and how many were too old to run; every other desk prints nothing, "
            "because a shortfall sentence under all five is a column of absences "
            "pretending to be information. Twelve is one page of the stream - what "
            "a reader sees before the first `Show more` - so a desk under it is a "
            "desk they see the whole of at once, which is where 'is this broken?' "
            "starts. Measured 2026-09-02 over the 12 committed days and 56 "
            "desk-days: 7 sit at or below it, 12.5 percent, and the record has a "
            "gap with nothing between 4 and 12 - so any value from 5 to 12 selects "
            "the same six startup desk-days and 12 adds the seventh. Arithmetic "
            "over committed payloads, so the spread is zero by construction."
        ),
    )
    shell_seed_items: int = Field(
        default=15,
        ge=1,
        description=(
            "How many of a day's stories a prerendered document carries. It is the "
            "one knob in this block a browser is never told, because the root "
            "layout inlines the rest of them into every document and a number no "
            "page reads would ride to every reader for ever. Fifteen covers the "
            "twelve a flat list pages at and the five the leading block draws. It "
            "is a floor rather than the whole answer: a lead is chosen across the "
            "whole day and is not inside any prefix, so the document has to carry "
            "those as well - measured 2026-09-01 on the 601-story day of "
            "2026-08-31, the five sat at positions 249, 285, 337, 344 and 493. "
            "Re-derive it when the block or the page size moves; do not raise it "
            "to cover a busy day, because the stories past the seed arrive by "
            "fetch. Measured 2026-09-01 on the 431-story day of 2026-08-30, gzip "
            "-9, Intel Core i7-1265U / Windows 11 / node 24.12.0: the first "
            "fifteen stories cost a dated route 20,302 bytes across the two "
            "documents it emits, against 420,074 for all 431."
        ),
    )
    payload_slow_ms: int = Field(
        default=1200,
        ge=250,
        le=30_000,
        description=(
            "How long a reader may wait for the rest of a day before the page says "
            "one sentence about it. The opposite of `shell_seed_items`: this is the "
            "one knob in this block only a browser reads, because the wait happens "
            "in the browser and a prerendered document is the only way to tell it "
            "anything. No spinner and no bar - a sentence, which is what a state a "
            "reader has to act on gets (docs/concepts/design-system.md). Under 250 "
            "ms the sentence fires on a fetch that was never slow, which teaches a "
            "reader to ignore it; over 30 s they have already decided the page is "
            "broken. Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / node "
            "24.12.0, Chromium against a local preview server: a 9,731-byte served "
            "day answered in 10.2 to 22.3 ms over 12 probes, median 13, so the "
            "default is about 90 times that median and cannot fire on a healthy "
            "fetch here. That is a server on the same machine and not a reader's "
            "connection, which is exactly why this is a knob and not a constant."
        ),
    )
    repo_url: str = Field(default="https://github.com/miztiik/yen-idhazh", min_length=1)
    site_title: str = Field(default="yen-idhazh", min_length=1)
    tagline: str = Field(
        default="A daily digest that checks its own work.",
        min_length=1,
    )
    read_mark_days: int = Field(
        default=14,
        ge=1,
        description=(
            "How far back a read mark is kept, counted in calendar days from today. "
            "Marks are held per digest date, so a mark made on one day can never "
            "grey out a different day's article, and every page load drops the dates "
            "that now sit outside this window. Fourteen days, the same span "
            "`archive_recent_days` lists, so the days the archive offers as rows of "
            "their own are exactly the days a reader can still see their own marks "
            "on. THIS RULE TRUSTS THE DEVICE CLOCK AND THE RULE IT REPLACED "
            "DELIBERATELY DID NOT: keeping the newest N dates present in the store "
            "needed no clock at all, and expiry by calendar cannot work without one, "
            "so a clock set wrong now keeps marks too long or drops them early. That "
            "is the price. It is worth paying because the old rule bounded the store "
            "by how often a reader came back rather than by time: a reader who opened "
            "one day a month kept marks from seven different months, and every one "
            "of them greyed out an article last seen most of a year ago. A wrong "
            "mark is the thing this store exists to avoid."
        ),
    )
    archive_page_size: int = Field(
        default=25,
        ge=1,
        description=(
            "How many stories the archive's list adds each time a reader asks for more. "
            "The day page pages at twelve because a day is short and the reader came to "
            "read it; the archive holds thousands and the reader came to find one, so "
            "it opens on the same twenty-five the console's failure list does."
        ),
    )
    archive_recent_days: int = Field(
        default=14,
        ge=1,
        le=31,
        description=(
            "How many of the newest published days the archive lists as rows of their "
            "own, each carrying the long date, the story count and whether every story "
            "finished. Every other day sits inside a disclosure for its month, so this "
            "block is the shortcut and never the only way in. Fourteen, and it matches "
            "`read_mark_days` for the same reason it matched it at seven: a row here is "
            "an invitation back to a day, and a day whose marks have already been "
            "dropped comes back looking unread. The two numbers move together or the "
            "block starts offering days it misrepresents. The ceiling is a month: "
            "above that the block is the wall of dates it replaced, and a month row "
            "already reaches any date in two clicks. Read by the build alone, like "
            "`shell_seed_items`, so it never rides to a reader."
        ),
    )
    archive_window_days: int = Field(
        default=30,
        ge=1,
        description=(
            "The span the archive's window control opens on, in days. IT MUST BE ONE "
            "OF `console.window_presets`, and `AppConfig` and `AppearanceConfig` both "
            "refuse a file where it is not - that is how the archive reuses the "
            "console's list of spans instead of declaring a second one, so the two "
            "surfaces cannot offer different day counts for the same idea. It names a "
            "span rather than a list for the reason `console.default_window_days` "
            "does: the list is the presets, and a second list is one more thing to "
            "keep in step. Thirty, because that is the span the console opens on and "
            "about the reach `assist.search_months` gives a search today, so the "
            "control ships opening on what the archive already costs. NOTHING READS "
            "IT YET - the control that will is row 25 of "
            "TODO/20260906-constant-cost-reads-plan.md. Read by the build alone, like "
            "`archive_recent_days`, so it never rides to a reader."
        ),
    )
    offline_version: int = Field(
        default=1,
        ge=1,
        description=(
            "The version the offline reader carries. The site ships a service worker so "
            "a day already opened can be read again with no network, and this number is "
            "how a build says which worker it is. It is compared against "
            "`offline_retired_through`, and nothing else reads it. Raise it by one to "
            "bring the worker back after a retirement; leave it alone otherwise. Read "
            "by the build alone, like `shell_seed_items`, so it never rides to a reader."
        ),
    )
    offline_retired_through: int = Field(
        default=0,
        ge=0,
        description=(
            "The switch that turns the offline reader off and cleans up after it. Every "
            "worker whose `offline_version` is at or below this number unregisters "
            "itself and deletes every cache it owns, the first time it activates. Zero "
            "retires none, because the lowest version a worker can carry is one. This "
            "is the one thing a worker outliving the tab needs and an ordinary page "
            "does not: a way out that does not depend on the worker being well "
            "(docs/concepts/ui-shell.md). It is published as `service-worker-kill.json` "
            "at the site root, so a retirement can be pushed as one file. Read by the "
            "build alone, so it never rides to a reader."
        ),
    )
    offline_days_kept: int = Field(
        default=14,
        ge=1,
        le=366,
        description=(
            "How many opened days the offline reader keeps on the reader's device. The "
            "worker caches a day only after that day has been fetched once - it never "
            "prefetches a day nobody asked for - and this is what stops the kept set "
            "growing with the archive. Fourteen is two weeks, the same span "
            "`read_mark_days` keeps a read mark for, so a day a reader can still see "
            "their marks on is a day they can still open with no network. Measured "
            "2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0 over the 12 "
            "served days: a day payload is 8,231 to 1,373,593 bytes uncompressed, "
            "median 727,622, so the full fourteen is about 10 MB at the median and "
            "about 19 MB at the largest. Arithmetic over committed payloads, so the "
            "spread is zero by construction. That 167-fold spread is why a day count "
            "cannot be the only bound - `offline_bytes_kept` is the other one. Read by "
            "the build alone, so it never rides to a reader."
        ),
    )
    offline_bytes_kept: int = Field(
        default=20_000_000,
        ge=2_000_000,
        le=100_000_000,
        description=(
            "The most bytes of cached day payloads the offline reader keeps on the "
            "reader's device. A SECOND BOUND BESIDE `offline_days_kept`, NOT A "
            "REPLACEMENT FOR IT, because a day count cannot bound bytes: measured "
            "2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0 over the 12 "
            "served days, one day payload runs 8,231 to 1,373,593 bytes uncompressed, "
            "median 727,622 - a factor of 167 between the smallest day and the largest, "
            "so fourteen days is anything from 115 KB to 19 MB and the count alone "
            "promises the reader nothing. Twenty million bytes is 20 MB, just over the "
            "19,230,302 the day count already permits at the largest day measured, so "
            "on today's payloads the day count still binds first and this is the "
            "backstop for the day payloads grow. The floor is 2 MB, above the largest "
            "single day measured, so no reachable value can leave the cache unable to "
            "hold one day - a ceiling that evicts a day as fast as it arrives is worse "
            "than no cache, because the reader pays the download and keeps nothing. "
            "The ceiling is 100 MB, a little over twice the 43.2 MB the on-device "
            "search model and its runtime already take, because taking a tenth of a "
            "gigabyte of somebody's phone for a news digest is not a thing a config "
            "edit should be able to do quietly. NOTHING READS IT YET - the eviction "
            "rule that will is row 8 of TODO/20260906-constant-cost-reads-plan.md. "
            "Read by the build alone, so it never rides to a reader."
        ),
    )

    @field_validator("theme_default", mode="before")
    @classmethod
    def _system_reads_as_the_base_theme(cls, value: object) -> object:
        """Read-side migration for a config written before 2026-08-31 (section 11).

        `system` meant "follow the device". Nothing asks the device any more, so
        the only honest reading of an older file is the base theme.
        """
        return ThemeChoice.DARK if value == "system" else value

    @model_validator(mode="after")
    def _the_leading_block_can_reach_its_own_floor(self) -> Self:
        """A floor above the ceiling is a block that can never draw.

        Both numbers read as reasonable on their own, and the failure is silent:
        the block simply never appears and nothing says why.
        """
        if self.leading_min > self.leading_stories:
            raise ValueError("leading_min cannot exceed leading_stories")
        if self.leading_per_desk > self.leading_stories:
            raise ValueError("leading_per_desk cannot exceed leading_stories")
        return self
