"""`config/appearance.json` - the published surface's own tunable file.

Split off `config/idhazh.json` on 2026-08-29. Curating a reading surface and
pinning a decode temperature are different activities with different review
cadences, and one file meant every appearance edit touched the file that also
holds the sampler seed. This is the same argument `config/sources.json` was
split on, one surface later.

The shapes `UiConfig`, `ConsoleConfig` and `AssistConfig` are imported from
`app_config` rather than copied: one definition, two exposure points. The file
moved; the contract did not fork. `AppConfig` keeps its `ui`, `console` and
`assist` fields so a config an earlier run wrote still validates, and the
frontend loader prefers this file and falls back to those (CLAUDE.md section
11).

Every knob here has bounds, and the bounds are the point. The 2026-08-28
advisory ruling against putting the frame width in config argued that a frame
set to 300px would need a code change to still look right. That is true of an
unvalidated number and false of a validated one: `frame.reading_max_px` cannot
be set below 960, so no reachable value breaks the design. The contract is the
answer to the objection, not a refusal of the knob.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.app_config import AssistConfig, ConsoleConfig, UiConfig
from idhazh.contracts.base import ChangelogEntry, Contract, Model

#: The measure, in characters, outside which a line stops being comfortable to
#: read. Bracketing rather than taste: below about 50 the eye returns too often,
#: above about 80 it loses the line on the way back. Bringhurst puts the range
#: at 45-75 for a single column; the wider top is because a screen at a normal
#: viewing distance carries a longer line than a page does.
MEASURE_CH_MIN: Final = 52
MEASURE_CH_MAX: Final = 80

#: Below this the frame stops being a frame. Measured 2026-08-28: a 672px shell
#: on a 1209px window left 51.6 percent of the screen used, and the same shell
#: on a 1536px window left 40.6 percent. 960 is the width at which a side rail
#: and a reading measure both fit, which is the narrowest arrangement this
#: design has.
FRAME_READING_MIN_PX: Final = 960
#: Above this a centred frame stops reading as a page and starts reading as a
#: window with the content pushed to the middle of a very wide desk.
FRAME_READING_MAX_PX: Final = 1600

#: The console carries tables, not prose, so it has no measure to protect and
#: its floor is set by its widest table instead. Measured 2026-08-28: the model
#: table is ten columns, and ten columns do not fit under about 1100px without
#: a horizontal scrollbar - which is the defect, not the fix.
FRAME_CONSOLE_MIN_PX: Final = 1100
FRAME_CONSOLE_MAX_PX: Final = 2000

#: A six-digit CSS hex, lower case. The one form `frontend/src/styles/tokens.css`
#: writes and the one form `tokens.spec.ts` reads back off it.
HEX_COLOUR: Final = r"^#[0-9a-f]{6}$"

#: The confidence ramp as `tokens.css` declares it, so the movement pair can be
#: refused for being it. Copied rather than imported because nothing in
#: `backend/` may read a frontend file (CLAUDE.md section 4), and the copy is
#: safe to hold: these three values are the ones the ramp had when the movement
#: pair was chosen, and a ramp that moves off them only widens the gap.
LIGHT_CONFIDENCE_RAMP: Final = {
    "--band-high": "#1a7f4b",
    "--band-medium": "#8a6300",
    "--band-low": "#b4331f",
}
DARK_CONFIDENCE_RAMP: Final = {
    "--band-high": "#4bbd84",
    "--band-medium": "#d6a743",
    "--band-low": "#f0836c",
}


class TintMode(StrEnum):
    """How an icon takes its colour.

    `SEMANTIC` tints a monochrome glyph from the token that matches what it
    means, which is how one glyph set covers every status and how a new status
    arrives with a slot already waiting. `MONO` is the fallback for a surface
    where a coloured mark would compete with the thing beside it.
    """

    SEMANTIC = "semantic"
    MONO = "mono"


class ChartPalette(StrEnum):
    """Which categorical ramp a chart draws from.

    Never the confidence ramp. `design-system.md` records the chart that
    borrowed the band tokens and told a reader the slowest stage was the
    failing one; both ramps here are green-free, amber-free and red-free for
    that reason.
    """

    CATEGORICAL = "categorical"
    SEQUENTIAL = "sequential"


class FrameConfig(Model):
    """How wide the page is, and where the reading measure lives.

    The measure is a property of a text element and never of the shell. Putting
    it on the shell is the single defect behind the 40.6-percent measurement:
    one `max-w-2xl` on the root layout gave the whole application a paragraph's
    width, including a console with five tables and six charts in it.
    """

    reading_max_px: int = Field(
        default=1280,
        ge=FRAME_READING_MIN_PX,
        le=FRAME_READING_MAX_PX,
        description=(
            "The widest the reader-facing frame grows, in CSS pixels. The frame is "
            "fluid below this and centred at it. It is NOT the width of a line of "
            "prose - `measure_ch` is - so raising it widens the page furniture and "
            "leaves the summary alone."
        ),
    )
    console_max_px: int = Field(
        default=1600,
        ge=FRAME_CONSOLE_MIN_PX,
        le=FRAME_CONSOLE_MAX_PX,
        description=(
            "The widest the operator frame grows. Wider than the reading frame on "
            "purpose: an instrument has tables and charts where a digest has "
            "sentences, and a table is allowed the screen it is on."
        ),
    )
    measure_ch: int = Field(
        default=68,
        ge=MEASURE_CH_MIN,
        le=MEASURE_CH_MAX,
        description=(
            "The reading measure, in characters, applied to a title, a summary and a "
            "key point. Applied to the text element, never to a container that also "
            "holds furniture."
        ),
    )
    gutter_min_px: int = Field(
        default=16,
        ge=8,
        le=32,
        description=(
            "The page's side padding on the narrowest screen. Measured 2026-08-28, a "
            "312px window spent 52px of its width on gutter - about two words a line, "
            "on the surface with the fewest words per line to spare."
        ),
    )
    gutter_max_px: int = Field(
        default=32,
        ge=16,
        le=64,
        description="The page's side padding once the frame has room for it.",
    )
    breakpoints_px: list[int] = Field(
        default_factory=lambda: [640, 1024, 1400],
        min_length=3,
        max_length=3,
        description=(
            "Exactly three, ascending. Three is a decision rather than a default: "
            "one phone-to-tablet step, one step where a side rail becomes possible, "
            "and one step where a third column does. A breakpoint must earn a "
            "STRUCTURAL change - a grid that splits on a viewport width instead of on "
            "its own available width is the bug that drew three charts at 164px, and "
            "`auto-fit` with a minimum is what replaces it."
        ),
    )

    @model_validator(mode="after")
    def _frame_and_gutters_are_ordered(self) -> Self:
        if self.gutter_min_px > self.gutter_max_px:
            raise ValueError("frame.gutter_min_px must not exceed gutter_max_px")
        if self.console_max_px < self.reading_max_px:
            raise ValueError(
                "frame.console_max_px must not be narrower than reading_max_px: "
                "an instrument that gets less room than a paragraph is the defect "
                "this contract exists to prevent"
            )
        if sorted(set(self.breakpoints_px)) != self.breakpoints_px:
            raise ValueError("frame.breakpoints_px must be three ascending, distinct widths")
        if self.breakpoints_px[0] <= self.gutter_max_px * 2:
            raise ValueError("frame.breakpoints_px[0] must leave room for both gutters")
        return self


class ThemeConfig(Model):
    """What the surface is allowed to draw with.

    Every switch here defaults to on. They exist so a surface can be measured
    with and without a treatment, not so the treatment can be quietly left off:
    a flag that ships false is a feature nobody built.
    """

    gradient_enabled: bool = Field(
        default=True,
        description=(
            "Gradients on chrome and identity only - the wordmark, a panel wash, an "
            "empty state. Never on an item and never inside a chart. A gradient that "
            "encodes nothing is decoration and is unconstrained; a gradient whose hue "
            "would tell a reader something is semantic colour and is refused."
        ),
    )
    elevation_enabled: bool = Field(
        default=True,
        description=(
            "The shadow and raised-surface scale. A page with one surface colour is a "
            "page where nothing is in front of anything. On the dark theme this lifts "
            "the surface and adds a hairline instead of deepening a shadow, because a "
            "shadow on a dark ground reads as nothing."
        ),
    )
    display_face_enabled: bool = Field(
        default=True,
        description=(
            "A self-hosted display face on headings. The body keeps the system stack: "
            "it renders on the first frame at zero bytes and the body is what the "
            "reader came for. Rule #1 permits a third-party asset; this project "
            "self-hosts because the HTTP cache is partitioned per site, so the "
            "shared-cache argument is dead and the request is the larger cost."
        ),
    )
    surface_tint_alpha: float = Field(
        default=0.07,
        ge=0.0,
        le=0.15,
        description=(
            "How strongly a panel takes the hue of what it means. Capped at 0.15 "
            "because past that a tint stops being a surface and starts being a fill, "
            "and a fill competes with the text on it. The reference surfaces measured "
            "2026-08-29 sit between 0.055 and 0.086."
        ),
    )
    movement_good_light: str = Field(
        default="#2f6f5e",
        pattern=HEX_COLOUR,
        description=(
            "`--movement-good` on the light theme: a figure went the way we wanted. "
            "Not the confidence ramp and never equal to it - health says a thing is "
            "broken, movement says a number moved the right way, and a summary that "
            "got 3 percent slower is not broken. Text weight, so it clears 4.5:1 on "
            "the surface; measured 2026-08-31 the default reads 5.905:1."
        ),
    )
    movement_bad_light: str = Field(
        default="#96453a",
        pattern=HEX_COLOUR,
        description=(
            "`--movement-bad` on the light theme. Quieter than `--band-low` on "
            "purpose: measured 2026-08-31 the default is 44.2 percent saturation "
            "against the confidence ramp's 70.6, so a movement reads as a direction "
            "beside a status chip rather than as a second status. 6.544:1 on the "
            "surface."
        ),
    )
    movement_good_dark: str = Field(
        default="#7fc9ae",
        pattern=HEX_COLOUR,
        description=(
            "`--movement-good` on the dark theme. Designed rather than derived: the "
            "light value over a dark ground is ink, not a colour. 9.118:1 on the dark "
            "surface, measured 2026-08-31."
        ),
    )
    movement_bad_dark: str = Field(
        default="#e3a396",
        pattern=HEX_COLOUR,
        description=(
            "`--movement-bad` on the dark theme. 8.344:1 on the dark surface, "
            "measured 2026-08-31."
        ),
    )

    @model_validator(mode="after")
    def _movement_is_not_the_confidence_ramp(self) -> Self:
        """The whole of `they are not the health ramp`, made mechanical.

        Two tokens that resolve to the same bytes as `--band-high` and
        `--band-low` ARE the confidence ramp under a second name, and the
        alarm-fatigue argument that put them here dies quietly.
        """
        for theme, ramp in (("light", LIGHT_CONFIDENCE_RAMP), ("dark", DARK_CONFIDENCE_RAMP)):
            good: str = getattr(self, f"movement_good_{theme}").lower()
            bad: str = getattr(self, f"movement_bad_{theme}").lower()
            if good == bad:
                raise ValueError(
                    f"theme.movement_good_{theme} and movement_bad_{theme} must differ: "
                    "one colour cannot say both directions"
                )
            for name, value in ramp.items():
                if value in (good, bad):
                    raise ValueError(
                        f"theme.movement_*_{theme} must not equal {name} ({value}): "
                        "movement colour says a number went the right way, and the "
                        "confidence ramp says a thing is broken"
                    )
        return self


class ChartConfig(Model):
    """How a chart is drawn, and what it does when a pointer reaches it."""

    height_px: int = Field(
        default=220,
        ge=120,
        le=520,
        description=(
            "The drawn height of a standard console chart, in CSS pixels. Raised from "
            "180 when the frame widened: a chart that grows only in one dimension "
            "flattens its own signal."
        ),
    )
    width_px: int = Field(
        default=760,
        ge=240,
        le=2000,
        description=(
            "The width a chart is drawn at on the SERVER, in CSS pixels. A prerendered "
            "chart has no element to measure, so this is what the page ships complete "
            "at; the client re-measures and redraws once a script runs. It must track "
            "the console frame - set it far below what the container gives and the "
            "chart visibly snaps on first paint."
        ),
    )
    hover_readout: bool = Field(
        default=True,
        description=(
            "Whether a pointer, a tap or an arrow key over a chart names the value it "
            "is nearest, in words. The readout is additive: it may never be the only "
            "place a fact appears, and every value it shows is also derivable from the "
            "axis - which is what keeps the old rule against tooltips carrying "
            "critical information intact while still answering 'what is that bar'."
        ),
    )
    readout_max_share: float = Field(
        default=0.33,
        gt=0.0,
        le=1.0,
        description=(
            "The widest the readout strip under a plot may be, as a share of that "
            "plot. The strip sits below the plot rather than over it, so it cannot "
            "cover a mark at any width; the cap is what stops it becoming a paragraph "
            "beside a chart a reader is glancing at. Measured 2026-08-29, the floating "
            "box this replaced covered 88 to 121px of a 220px plot - 40 to 55 percent "
            "of the chart it was explaining."
        ),
    )
    palette: ChartPalette = Field(
        default=ChartPalette.CATEGORICAL,
        description="Which ramp a chart draws from. Never the confidence ramp.",
    )
    tick_density: int = Field(
        default=6,
        ge=3,
        le=12,
        description=(
            "The MOST date labels a chart's day axis may carry. A ceiling and never "
            "a target: the axis then measures the labels against the room the plot "
            "actually has and drops more of them until no two touch. A count alone "
            "cannot hold at two widths - measured 2026-08-31 at 390px, six labels "
            "over a thirty-day window overlapped by 13.6px. Every column this "
            "number allows keeps its tick mark whether or not its date survived, "
            "because a reader counting columns needs the grid."
        ),
    )
    sparkline_height_px: int = Field(
        default=36,
        ge=16,
        le=96,
        description=(
            "A sparkline inside a card. Direction at a glance, no axis. The ceiling is "
            "below `height_px`'s floor of 120 on purpose, so a sparkline can never be "
            "configured taller than a chart - the bound does the work a cross-field "
            "validator would, and a validator that cannot fire is worse than none."
        ),
    )
    donut_thickness_px: int = Field(
        default=10,
        ge=4,
        le=40,
        description=(
            "The stroke of a donut gauge. Thin enough that the hole carries the "
            "number, thick enough that the arc is the thing the eye lands on."
        ),
    )


class IconsConfig(Model):
    """The icon set, and how it takes colour."""

    size_px: int = Field(
        default=16,
        ge=12,
        le=32,
        description="The default drawn size of an inline icon, in CSS pixels.",
    )
    tint_mode: TintMode = Field(
        default=TintMode.SEMANTIC,
        description="Whether an icon takes the hue of what it means, or stays with the text.",
    )
    topic_icons_enabled: bool = Field(
        default=True,
        description=(
            "A mark beside a topic name. Legal because a topic is a classification the "
            "pipeline actually made and carries in the payload. There is deliberately "
            "no switch for an icon beside a HEADLINE: 'what kind of story is this' is "
            "an assertion no stage ever produced, and a mark that invents it is the "
            "same failure the visual-routing rule already guards against."
        ),
    )


class MotionConfig(Model):
    """The motion budget. Small on purpose; a reading surface that animates interrupts."""

    enabled: bool = Field(
        default=True,
        description=(
            "The named set only: content arriving, a skeleton while a payload parses, "
            "and the rare notice. `prefers-reduced-motion` is a hard kill-switch above "
            "this flag and is not configurable - a reader who asked their operating "
            "system for stillness is not overridden by a config file."
        ),
    )
    duration_fast_ms: int = Field(default=120, ge=0, le=400)
    duration_base_ms: int = Field(default=200, ge=0, le=600)

    @model_validator(mode="after")
    def _fast_is_faster_than_base(self) -> Self:
        if self.duration_fast_ms > self.duration_base_ms:
            raise ValueError("motion.duration_fast_ms must not exceed duration_base_ms")
        return self


class AppearanceConfig(Contract):
    """`config/appearance.json` - everything the published surface is drawn from."""

    __schema_stem__: ClassVar[str] = "appearance-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-01T14:00",
            change=(
                "digest.filter_min_chars added, defaulting to 2. The shape is "
                "`UiConfig`, which this document and `AppConfig` share, so both schemas "
                "moved together. Additive with a default, so an appearance file written "
                "before today still validates."
            ),
            why=(
                "The day page's filter and the archive's topic pills became one panel, "
                "and the archive's field now narrows the loaded list as a reader types "
                "- so the same rule governs two surfaces and may not be spelled in "
                "either of them (Rule #6). Two rather than one because one letter "
                "narrows nothing: measured 2026-09-01 over the 12 committed days and "
                "4,203 story titles, the median single letter matches 80.2 percent of "
                "them and `e` matches 99.8 percent, against a median 0.8 percent for a "
                "two-letter pair."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T13:00",
            change=(
                "console.doubt_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppConfig` share, so both "
                "schemas moved together. Additive with a default, so an appearance "
                "file written before today still validates."
            ),
            why=(
                "The Summaries route now ranks sources by how often the faithfulness "
                "checker doubted their summaries, and an uncapped ranking is a page "
                "nobody reads to the end: measured 2026-09-01 over the committed "
                "score ledger, a thirty-day window holds 112 sources with a doubted "
                "summary. It takes the default `source_rows` and `feed_rows` already "
                "carry, so three ranked lists on one console do not each end at a "
                "different depth."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T12:30",
            change=(
                "digest.leading_stories, digest.leading_per_desk, "
                "digest.leading_min, digest.lead_cluster_floor, "
                "digest.lead_shared_subject_weight and digest.lead_max_yesterday "
                "added, defaulting to 5, 2, 3, 3, 0.2 and 1. "
                "digest.items_per_topic is deprecated, read by nothing, and dropped "
                "from the committed file. The shape is `UiConfig`, which this "
                "document and `AppConfig` share, so both schemas moved together."
            ),
            why=(
                "The day gets a leading block: five stories chosen across the whole "
                "day, each carrying one sentence saying why it is there. Every "
                "number that decides it is a knob rather than a literal in a stage "
                "(Rule #6). The block replaces the three-per-topic headings, which "
                "on the 431-story day of 2026-08-30 drew 15 stories and put 416 "
                "behind five links, so items_per_topic lost its only reader. "
                "Additive with defaults and one deprecation that still validates, "
                "so an appearance file written before today still reads "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T10:00",
            change=(
                "digest.payload_slow_ms added, defaulting to 1200. The shape is "
                "`UiConfig`, which this document and `AppConfig` share, so both "
                "schemas moved together. Additive with a default, so an appearance "
                "file written before today still validates."
            ),
            why=(
                "The rest of a day is about to arrive by fetch, so for the first "
                "time a reading page can be waiting on something. What it shows "
                "meanwhile is one sentence past this number - never a spinner and "
                "never a bar, because the first frame is already readable and a "
                "compressed response cannot report a byte count worth printing. "
                "This is the one knob in the block only a browser reads, which is "
                "the exact opposite of `shell_seed_items` beside it."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T02:00",
            change=(
                "console.source_rows and console.feed_rows added, both defaulting to "
                "10. The shape is `ConsoleConfig`, which this document and "
                "`AppConfig` share, so both schemas moved together."
            ),
            why=(
                "Two console lists gained a cap on the same day, and a cap a "
                "component hardcodes is one an operator cannot move (Rule #6). The "
                "failure section now ranks sources by the articles their failures "
                "cost the digest; measured 2026-09-01 over the committed "
                "projection, a thirty-day window holds 60 sources with a loss, so "
                "an uncapped ranking is a list nobody reads to the end. The feed "
                "list had no cap at all and draws 26 of 182 checked feeds. "
                "Additive with defaults, so an appearance file written before today "
                "still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01",
            change=(
                "digest.shell_seed_items added, defaulting to 15. The shape is "
                "`UiConfig`, which this document and `AppConfig` share, so both "
                "schemas moved together. Additive with a default, so an appearance "
                "file written before today still validates."
            ),
            why=(
                "A reading route's build-time load now splits a day into the facts "
                "that do not grow with the story count, the head of the published "
                "order, and the remainder. This number is where the head ends. "
                "Nothing fetches yet - the two halves are put straight back "
                "together, and the prerendered output is byte-identical - so the "
                "knob decides nothing today and everything once the item list "
                "moves to a browser fetch. It is also the one knob in this block "
                "the layout does not hand a browser, because no page reads it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:59",
            change=(
                "digest.topic_pills_max added, defaulting to 8. The shape is "
                "`UiConfig`, which this document and `AppConfig` share, so both "
                "schemas moved together. Additive with a default, so an appearance "
                "file written before today still validates."
            ),
            why=(
                "The topic row was a horizontal scroll container, which is a control "
                "that hides its own contents; the owner ruled on 2026-08-31 that no "
                "reader-facing surface carries one. The row wraps now, and the topics "
                "past this number sit inside a `+N more` disclosure so a day with "
                "many topics does not turn the row into the page. A cap a component "
                "spells is a cap an operator cannot move (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:56",
            change=(
                "theme.movement_good_light, theme.movement_bad_light, "
                "theme.movement_good_dark and theme.movement_bad_dark added, "
                "defaulting to #2f6f5e, #96453a, #7fc9ae and #e3a396. They are the "
                "values of the `--movement-good` and `--movement-bad` CSS tokens, one "
                "per theme, and a validator refuses any of them that equals a "
                "confidence-ramp value."
            ),
            why=(
                "Movement colour on the console read the sign of the number instead "
                "of the polarity of the measure, so a fall in time per summary - an "
                "improvement - painted the same as a fall in summaries published. "
                "The fix needs a colour pair that means `went the right way`, and the "
                "confidence ramp cannot be it: green there means `it worked`, and a "
                "summary that got 3 percent slower is not broken. Painting it in "
                "`--band-low` teaches an operator to ignore `--band-low`. The pair is "
                "quieter than the ramp on purpose - measured 2026-08-31 at 40.5 and "
                "44.2 percent saturation against 66 and 70.6 in light - and both "
                "clear 4.5:1 as text on their own surface. Additive with defaults, so "
                "an appearance file written before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:55",
            change=(
                "ThemeChoice lost its `system` member and digest.theme_default now "
                "defaults to `dark`; the committed file repeats it. The shape is "
                "`UiConfig`, which this document and `AppConfig` share, so both schemas "
                "moved together. Breaking: the enum is narrower. The read-side "
                "migration is a before-validator on `UiConfig.theme_default` that reads "
                "`system` as `dark`, so an appearance file written before today still "
                "loads."
            ),
            why=(
                "The site now starts dark and light is an opt-in stored choice, so the "
                "three-state theme control became one button with two states (owner "
                "decision, 2026-08-31). `system` was never a theme - it was the absence "
                "of a choice - and nothing asks the device any more. Leaving the member "
                "in would let an operator set a value no surface can honour. `dark` is "
                "the value `:root` carries in tokens.css, so this knob and the first "
                "painted frame now agree."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:45",
            change=(
                "assist.recall_min default moved from 0.69 to 0.61, and the committed "
                "file repeats it. The shape is `AssistConfig`, which this document and "
                "`AppConfig` share, so both schemas moved together."
            ),
            why=(
                "The backend retrieval gate reads this knob, and 0.69 stopped being a "
                "measurement of the system when the archive grew: reachable recall@10 "
                "over the 60 labelled queries is 0.690 +/- 0.041 on 2026-08-31 against "
                "0.767 +/- 0.036 on 2026-08-26. Four arms hold the corpus, the labels "
                "and the vectors still one at a time and find no ranking regression - "
                "the same items read with today's vectors score identically, and the "
                "whole drop is new items competing for the same ten slots against a "
                "frozen label set. 0.61 is two standard errors below the new baseline, "
                "which is the rule that set 0.69. Nothing the published surface draws "
                "reads this field; it lives here because `AssistConfig` is one shape "
                "with two exposure points, and a value that disagreed across the two "
                "files would make one knob mean two things. Same field, same type: an "
                "appearance file that names 0.69 still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31",
            change=(
                "chart.tick_density keeps its name, its type and its default of 6, "
                "and its meaning is narrowed: it is now the CEILING on a day axis's "
                "date labels rather than the number the axis aims for. No field is "
                "added, removed or retyped."
            ),
            why=(
                "A count alone cannot hold at two widths. Measured 2026-08-31 on the "
                "built console, six labels over a thirty-day window overlapped by "
                "13.6px at 390px and read as one longer string. The axis now measures "
                "the labels against the room the plot has and drops more of them "
                "until none touch, so this number can only ever be an upper bound. "
                "Every value that validated yesterday still validates and still "
                "means something - it just cannot force a label onto a phone."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T21:15",
            change=(
                "console.chart_arm_rule_days, console.chart_arm_minutes_target and "
                "console.chart_arm_coverage_pct added, defaulting to 14 days, 6.0 "
                "minutes and 5 percent. The shape is `ConsoleConfig`, which this "
                "document and `AppConfig` share, so both schemas moved together."
            ),
            why=(
                "The chart arm section now leads with the two figures its retirement "
                "rule names, each as a bar with the limit drawn on it. A limit a "
                "component hardcodes is one an operator cannot move (Rule #6), and "
                "these three were constants in a TypeScript module. Additive with "
                "defaults, so an appearance file written before today still validates "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T20:00",
            change=(
                "console.band_outlier_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppConfig` share, so both "
                "schemas moved together."
            ),
            why=(
                "The console now names the summaries furthest from the length the "
                "prompt asked for, in place of a scatter that drew 2,740 marks in one "
                "colour. A capped list needs its cap where an operator can move it. "
                "Additive with a default, so an appearance file written before today "
                "still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change=(
                "chart.readout_max_share added, defaulting to 0.33: the widest the "
                "readout strip under a plot may be, as a share of that plot."
            ),
            why=(
                "The stage-timing chart gained a readout, and a readout needs a bound "
                "somebody can move without editing a component. Measured 2026-08-29, "
                "the floating box this replaces covered 88 to 121px of a 220px plot - "
                "40 to 55 percent of the chart it was explaining. Additive with a "
                "default, so an appearance file written before today still validates "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T22:00",
            change=(
                "console.window_presets added, and console.default_window_days must "
                "now be one of its members. The shape is `ConsoleConfig`, which this "
                "document and `AppConfig` share, so both schemas moved together."
            ),
            why=(
                "The console gained one time-window control that governs every "
                "windowed section on it, and a control needs the list of spans it "
                "offers. Additive with a default, so an appearance file written "
                "before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29",
            change=(
                "New contract. `digest`, `console` and `assist` are the shapes "
                "`AppConfig.ui`, `AppConfig.console` and `AppConfig.assist` already "
                "carried, now filed under their own document; `frame`, `theme`, "
                "`chart`, `icons` and `motion` are new."
            ),
            why=(
                "Curating a reading surface and pinning a decode temperature are "
                "different activities with different review cadences, and one file "
                "meant every appearance edit touched the file holding the sampler "
                "seed. The new blocks exist because the surface had no frame, no "
                "elevation, no gradient, no icon set and no chart interaction to tune "
                "- measured 2026-08-28 at 40.6 percent of a 1536px screen with two "
                "responsive breakpoints in the entire frontend. Additive and "
                "backwards-compatible: `AppConfig` keeps the three moved blocks and "
                "the frontend loader falls back to them, so a config an earlier run "
                "wrote still resolves."
            ),
        ),
    )

    digest: UiConfig = Field(
        default_factory=UiConfig,
        description="The day page's knobs. Formerly `AppConfig.ui`, unchanged in shape.",
    )
    console: ConsoleConfig = Field(
        default_factory=ConsoleConfig,
        description="The operator console's viewport. Formerly `AppConfig.console`.",
    )
    assist: AssistConfig = Field(
        default_factory=AssistConfig,
        description="On-device archive search. Formerly `AppConfig.assist`.",
    )
    frame: FrameConfig = Field(default_factory=FrameConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    chart: ChartConfig = Field(default_factory=ChartConfig)
    icons: IconsConfig = Field(default_factory=IconsConfig)
    motion: MotionConfig = Field(default_factory=MotionConfig)

    @model_validator(mode="after")
    def _a_chart_fits_the_frame_it_is_drawn_in(self) -> Self:
        """The prerender width must be reachable inside the console frame.

        A server that draws at 760 into a container that offers 1400 is not
        wrong - the client re-measures. A server that draws WIDER than the frame
        can ever be is wrong on every first paint and self-corrects only after a
        script runs, which is the one moment a static site is supposed to be
        already finished.
        """
        if self.chart.width_px > self.frame.console_max_px:
            raise ValueError(
                "chart.width_px must not exceed frame.console_max_px: the server would "
                "prerender every chart wider than its container can ever be"
            )
        return self
