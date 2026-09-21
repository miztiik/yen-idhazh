"""What window the operator console opens on, and what it fetches to fill it."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class TodayAnchor(StrEnum):
    RIGHT = "right"
    CENTRE = "centre"


class ConsolePanelGroup(Model):
    """One heading on a console route, and the panels that sit under it in order."""

    id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description=(
            "What the group is called in markup, drawn as `data-console-group`. "
            "Lower case and hyphens, so it is a stable handle a test can name "
            "while the heading above it is reworded."
        ),
    )
    title: str = Field(
        description=(
            "The heading drawn above the group. An empty title draws no heading "
            "and no group element, so the panels stay flat siblings - which is "
            "what a route that wants an order without a grouping asks for. A "
            "route mixes the two at its peril, so the contract refuses it."
        ),
    )
    panels: list[str] = Field(
        min_length=1,
        description=(
            "The panels under this heading, in the order they are drawn. Each "
            "entry is a panel id the route implements; the route's `load` "
            "refuses a list that names a panel it does not draw, or omits one it "
            "does, so a rename here fails the build rather than dropping a panel "
            "off the page in silence."
        ),
    )


class ConsoleConfig(Model):
    """Knobs for the operator console's time viewport."""

    default_window_days: int = Field(
        default=30,
        ge=1,
        description=(
            "Initial time span for the console charts. A viewport, not a deletion. "
            "Thirty rather than fourteen because the page states its own retirement "
            "rules over fourteen days, so a window equal to the rule shows the rule "
            "with no margin either side of it."
        ),
    )
    window_presets: list[int] = Field(
        default_factory=lambda: [1, 7, 14, 30, 90],
        min_length=2,
        description=(
            "The day counts the console's window control offers, ascending and "
            "distinct. A short list rather than a slider: every value is a distinct "
            "fetch cost, because a wider window pulls more month files, and most "
            "values in between are indistinguishable on the page. "
            "`default_window_days` must be one of them, or the console would open on "
            "a window its own control cannot name. One day is the narrowest read the "
            "console can offer - one month file, and the run that has just finished - "
            "and it is the setting an operator wants when a run has gone wrong and "
            "the surrounding month is noise around it. It is also the only preset a "
            "reader can pick that reads no history at all."
        ),
    )
    today_anchor: TodayAnchor = Field(
        default=TodayAnchor.RIGHT,
        description="Where today sits in the initial viewport when enough history exists.",
    )
    pan_days: int = Field(default=7, ge=1, description="Days moved by one arrow-key pan.")
    zoom_factor: float = Field(default=1.5, gt=1.0)
    min_window_days: int = Field(
        default=1,
        ge=1,
        description=(
            "The narrowest span a preset may name. One, because the preset list "
            "offers a single day and a floor above it would refuse the list. It "
            "bounds the presets and nothing else - a reader sets the span through "
            "them and through no other control."
        ),
    )
    max_window_days: int = Field(
        default=366,
        ge=1,
        description=(
            "The widest span a preset may name, and through that the oldest month "
            "shard the pipeline may delete. It is a retention floor rather than a "
            "viewport clamp: the preset radio buttons are the only span control a "
            "reader can reach, so no page is held to this number and "
            "`observability` is - `AppConfig` refuses a cleanup age shorter than the "
            "months a window this wide can touch. Lowering it therefore does not "
            "make any page cheaper; it authorises deleting shards the console can "
            "still ask for, and a deleted shard draws as a gap that reads like a day "
            "the pipeline did nothing. Three hundred and sixty-six is a leap year, "
            "so a full year of history stays readable on every date."
        ),
    )
    min_attempts_for_rate: int = Field(
        default=5,
        ge=1,
        description="Below this count a rate is outlined because the denominator is thin.",
    )
    precision_axis_multiple: float = Field(
        default=10.0,
        gt=1.0,
        le=100.0,
        description=(
            "How many times assemble.same_story.adaptive_dedup_threshold.discard_share "
            "the precision axis reaches. The fit places the line so that the discard "
            "share of judged two-story pairs stays above it, so 1 percent is where the "
            "line should hover; ten times that shows the target and a tenfold overshoot "
            "on one fixed scale. A value past the top is clamped at the top and printed "
            "in the readout, because the worst day is the one a hidden mark would cost."
        ),
    )
    chart_height: int = Field(
        default=220,
        ge=120,
        description=(
            "The drawn height of a console chart, in CSS pixels. The same number "
            "`chart.height_px` carries: both were raised from 180 when the frame "
            "widened, because a chart that grows in one dimension only flattens its "
            "own signal. `config/appearance.json` owns the value, as "
            "`console.chart_height`."
        ),
    )
    chart_width: int = Field(
        default=760,
        ge=240,
        description=(
            "The width a console chart is drawn at on the server, in CSS pixels. A "
            "prerendered chart has no element to measure, and a chart drawn in "
            "arbitrary units and then stretched by its viewBox renders its labels at "
            "whatever the stretch factor happens to be - measured 2026-08-25, one page "
            "put the same font-size at 4.5px and at 16.6px. It is a seed rather than "
            "the final width: the client re-measures its container once a script runs, "
            "and the drawn SVG was its host's width to within a pixel at 1440, 768 and "
            "390 (measured 2026-09-01). 760 is the same number `chart.width_px` "
            "carries, so a console page has one answer to how wide a chart starts. "
            "`config/appearance.json` owns the value, as `console.chart_width`."
        ),
    )
    shimmer_after_ms: int = Field(
        default=400,
        ge=0,
        le=5000,
        description=(
            "How long a reserved console block stays still before it starts to "
            "shimmer, in milliseconds. The block is drawn the moment the document "
            "is, so this knob decides nothing about the shape of the page - only "
            "whether a wait short enough to be over already gets animated on its "
            "way past. Four hundred is a DECLARED ESTIMATE and not a measurement "
            "(CLAUDE.md Guardrail #10), and it stays one: the number it needs is the "
            "median time a payload takes to reach a READER, and a reader-facing "
            "timing measurement is scoped out by the same owner ruling that "
            "authorised the fetch (2026-09-08). Everything measurable instead is "
            "localhost, where arrival is a few milliseconds and any threshold "
            "derived from it is one nobody ever crosses. What would settle it is "
            "in docs/reference/pipeline-cost.md under Still unmeasured. "
            "`config/appearance.json` owns the value, as `console.shimmer_after_ms`."
        ),
    )
    failure_list_max: int = Field(
        default=25,
        ge=1,
        description=(
            "How many failed items the console lists before it offers more. The shape "
            "comes first and the rows come on demand: an uncapped list put the "
            "compression chart 9000 pixels down the page."
        ),
    )
    source_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many sources the console ranks by the articles their failures cost, "
            "before it states the tail in one sentence. Measured 2026-09-01 over the "
            "committed projection, a thirty-day window holds 60 sources with a loss, "
            "which is a list nobody reads to the end. Ten, matching the source-cut "
            "list above it."
        ),
    )
    feed_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many failing feeds the console lists before it states the tail in one "
            "sentence. Measured 2026-09-01 over the committed ledger, 26 of 182 "
            "checked feeds have failed at least once. Ten, matching "
            "`console.source_rows`."
        ),
    )
    band_outlier_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many summaries the console names as furthest from the length the "
            "prompt asked for. Capped, with the tail stated in a sentence, because the "
            "list exists to be acted on and the far tail is a one-word miss nobody "
            "chases. Ten, matching the source-cut table beside it."
        ),
    )
    doubt_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many sources the Summaries route ranks by the summaries its "
            "faithfulness checker doubted, before it states the tail in one sentence. "
            "Measured 2026-09-01 over the committed score ledger, a thirty-day window "
            "holds 112 sources carrying at least one doubted summary and the worst ten "
            "hold 266 of the 1,047 doubts - so the tail is sources with a single doubt "
            "in a month, which nobody acts on. Ten, matching `console.source_rows` and "
            "`console.feed_rows`."
        ),
    )
    timeline_bars: int = Field(
        default=120,
        ge=1,
        description=(
            "How many items the run timeline draws as bars before it states the tail in "
            "one sentence. The bars are in start order, so the first this many show the "
            "shape of the run - a staircase or a block - which is what the panel is for. "
            "Measured 2026-09-16 over the committed census, a day holds 349 to 465 rows, "
            "and a bar a row would put a thousand spans in a prerendered document for a "
            "queue whose shape is settled in its first minute. It is a cap on the "
            "DRAWING and never on the arithmetic: every figure the panel prints is over "
            "the whole run."
        ),
    )
    chart_rule_days: int = Field(
        default=14,
        ge=1,
        description=(
            "The span the chart retirement rule is stated over. A median taken "
            "over any other span is the same figure with a different meaning and "
            "nothing on the page to say which one is being read, so under this many "
            "days the section prints the rule's own span and no number at all."
        ),
    )
    chart_minutes_target: float = Field(
        default=6.0,
        gt=0.0,
        description=(
            "Router minutes per published chart above which the median day retires "
            "chart drawing. Drawn as a marker on the bar, never as a subtraction the "
            "reader performs."
        ),
    )
    chart_coverage_pct: float = Field(
        default=5.0,
        gt=0.0,
        le=100.0,
        description=(
            "The share of a day's published items that must carry a chart, in whole "
            "percent. Below this on the median day chart drawing is retired: drawing that "
            "reaches almost nothing is paying for a capability the digest does not "
            "use."
        ),
    )
    fleet_min_rows: int = Field(
        default=160,
        ge=1,
        description=(
            "How many recorded job placements the console needs before it draws the "
            "machines as bars. Under it the panel lists the counts in words, because "
            "bars over a handful of placements read as a distribution and it is not "
            "one. A DECLARED ESTIMATE and not a measurement (CLAUDE.md Guardrail "
            "#10): the rarest of the six machine kinds on record held 11 of 356 "
            "counter rows on 2026-09-17, 3.1 percent, and 5 of those - the floor "
            "min_attempts_for_rate already sets - needs about 162 rows. A seventh "
            "machine kind lowers every share and raises the bar, so re-derive it "
            "rather than argue with it."
        ),
    )
    fleet_top_kinds: int = Field(
        default=4,
        ge=1,
        le=6,
        description=(
            "How many kinds of machine keep a bar of their own on the fleet trend "
            "before the rest fold into one row named in words. A grouped bar is "
            "only a bar while it is wide enough to paint. At chart_width of 760 "
            "and the widest span the window control offers, 90 days, a day band is "
            "8.4 px; five bars in it draw 1.09 px each after the chart engine's own "
            "gaps and seven draw 0.77 px, which is the sub-pixel band the chart "
            "rules already refuse. Four kinds plus the fold row is the largest set "
            "that stays over a pixel there. It costs little: of the 40 placements "
            "on the committed machine record on 2026-09-20, seven distinct machines "
            "in all, the top four hold 37. The upper bound is six because the "
            "colour ramp keeps seven stops and the fold row needs one of them."
        ),
    )
    bandwidth_min_kinds: int = Field(
        default=3,
        ge=2,
        description=(
            "How many distinct machine kinds must carry a memory-bandwidth reading "
            "before bandwidth may be plotted against decode speed. Two points define "
            "a line, so a scatter of two is a claim rather than a measurement. "
            "Nothing plots it today - the panel was refused on 2026-09-17 and this "
            "is half of the trigger that would bring it back, the other half being "
            "fleet_min_rows."
        ),
    )
    machine_colour_stops: int = Field(
        default=7,
        ge=1,
        le=7,
        description=(
            "How many machines get a colour of their own before the rest fold into "
            "one row named in words. Seven, because the chart ramp holds eight stops "
            "and the eighth is reserved for shards that recorded no machine at all - "
            "an absence is not a machine and must not take a machine's hue. Folding "
            "is what keeps the assignment bounded: without it a seventh kind would "
            "either collide with a sixth or need a ninth stop nobody has drawn."
        ),
    )
    processor_lost_pct_marked: float = Field(
        default=1.0,
        gt=0.0,
        le=100.0,
        description=(
            "The share of an interval the host gave to another tenant's machine at "
            "which that day is drawn as a filled tile rather than an outlined one. "
            "One percent is where a reading stops rounding to zero, which is a "
            "statement about the platform's own accounting rather than about this "
            "design. A floor above zero, because a threshold of zero would mark a "
            "day on which nothing was taken. A DECLARED ESTIMATE and not a "
            "measurement (CLAUDE.md Guardrail #10): no committed row separates what "
            "the host took from what we spent, because the busy figure holds both. "
            "What replaces it is the distribution of the separated reading over the "
            "first day that records one."
        ),
    )
    processor_lost_pct_named: float = Field(
        default=10.0,
        gt=0.0,
        le=100.0,
        description=(
            "The share at which the panel's headline sentence names that day as its "
            "worst case, instead of leaving the tiles to speak for themselves. Ten "
            "percent is anchored on the work shard's own budget: a tenth of "
            "run.shard_timeout_minutes is the size of loss that turns a shard which "
            "fits into one which does not. A DECLARED ESTIMATE on the same footing "
            "as the mark above it, and the same reading replaces both."
        ),
    )
    model_disk_reads_marked: int = Field(
        default=1,
        ge=1,
        description=(
            "How many times the model server had to go to disk for memory it "
            "expected to be resident before that day is drawn as a filled tile. "
            "Counted over the items that are NOT first in their shard: the server "
            "maps its weights, so the first touch of each page is itself a read from "
            "disk, and item_index 0 records a server starting rather than a kernel "
            "taking pages back. What that exclusion costs, stated rather than "
            "implied: a reclaim inside the first item of a shard is invisible, and "
            "the panel says so. One, because with the exclusion the honest expected "
            "value is zero and the first recorded read is the finding. A DECLARED "
            "ESTIMATE and not a measurement (CLAUDE.md Guardrail #10); what replaces "
            "it is the first day recording a non-zero count away from index 0."
        ),
    )
    model_disk_reads_named: int = Field(
        default=1,
        ge=1,
        description=(
            "How many such reads put that day in the panel's headline sentence. "
            "Equal to the mark, and deliberately: a signal whose expected value is "
            "zero has no distribution to separate the two, so every day worth "
            "marking is worth naming. The pair is two knobs rather than one so that "
            "the day a steady background appears, somebody raises this number in the "
            "config file instead of editing a chart."
        ),
    )
    context_high_percentile: float = Field(
        default=99.0,
        gt=0.0,
        lt=100.0,
        description=(
            "Which percentile of an item's context use a run draws beside its "
            "largest. A run gets two marks because one cannot carry both the "
            "ordinary article and the worst one, and the decision to shrink the "
            "window turns on the worst. Ninety-nine rather than the largest twice: "
            "measured 2026-09-21 over the 1,312 committed item rows that record both "
            "a window and a per-call token split, the 99th item used 9,900 tokens "
            "and the largest used 13,569, so the pair says how far the worst sits "
            "past the crowd. Lowering it draws a more typical article and hides how "
            "long the tail is; raising it collapses the two marks onto each other."
        ),
    )
    context_cut_off_reason: str = Field(
        default="length",
        min_length=1,
        description=(
            "The word the model server uses when a reply stopped because it ran out "
            "of window rather than because the model finished. The vocabulary is "
            "llama-server's, not this project's, which is why it is a knob: a "
            "runtime that spells it differently is a config edit rather than a code "
            "change. Measured 2026-09-21, the committed rows record one reason across "
            "2,624 calls and it is `stop`, so nothing has ever been cut off - a panel "
            "that could not name the other word could not say that."
        ),
    )
    panel_groups: dict[str, list[ConsolePanelGroup]] = Field(
        default_factory=lambda: {
            "pipelines": [
                ConsolePanelGroup(
                    id="pipelines",
                    title="",
                    panels=[
                        "at-a-glance",
                        "run-health",
                        "site-cost-per-item",
                        "failure-mix",
                        "item-time-split",
                        "throughput-viewport",
                        "stage-timings",
                        "item-cost",
                        "run-timeline",
                        "chart-drawing",
                        "extraction",
                    ],
                )
            ],
            "machine": [
                ConsolePanelGroup(
                    id="what-the-machine-was-doing",
                    title="What the machine was doing",
                    panels=[
                        "two-clocks",
                        "machine-cards",
                        "reading-against-writing",
                        "platform-mix",
                    ],
                ),
                ConsolePanelGroup(
                    id="where-the-time-went",
                    title="Where the time went",
                    panels=[
                        "shard-board",
                        "tail-trend",
                    ],
                ),
                ConsolePanelGroup(
                    id="how-close-to-the-limits",
                    title="How close we are to the limits",
                    panels=[
                        "memory-board",
                        "context-headroom",
                    ],
                ),
                ConsolePanelGroup(
                    id="what-the-model-spends",
                    title="What the model spends",
                    panels=[
                        "prompt-cache",
                        "read-against-written",
                        "counterfactual-cost",
                    ],
                ),
            ],
        },
        description=(
            "The order the panels of a console route are drawn in, and the "
            "headings they group under. Keyed by route id. A column of equal "
            "siblings gives the eye nothing to land on first, and "
            "a heading naming a time grain answers no question anybody arrives "
            "with - so each Hardware heading names a decision instead, in the "
            "order an operator takes them: what the machine was doing, where the "
            "time went, how close we are to the limits, and what the model "
            "spends. Each group's answer decides whether the next is worth "
            "reading. A grain is a fact about one panel and is stated on that "
            "panel, which is what lets one group hold a snapshot of a run beside "
            "a reading over the open span. The first panel of the first group is "
            "the one that verdicts the rest. The Pipelines route takes one "
            "untitled group, because what it needed was an order rather than a "
            "grouping. An id here is a panel the route implements, and the route "
            "refuses a list that names one it does not."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _the_old_chart_keys_still_read(cls, data: Any) -> Any:
        """`chart_arm_*` became `chart_*` on 2026-09-15. A config spelling it still loads.

        Only the names moved. `arm` was benchmarking's word for the same work run
        again under different settings, and this section's own prose stopped using
        it in the same commit - so the keys followed rather than being left as the
        one place a person still has to type it.

        These go a release later, the way a renamed config knob does: a config
        file is a file somebody can edit, so the alias buys the edit time and is
        then replaced by a refusal (section 11).
        """
        if not isinstance(data, dict):
            return data
        moved = {
            "chart_arm_rule_days": "chart_rule_days",
            "chart_arm_minutes_target": "chart_minutes_target",
            "chart_arm_coverage_pct": "chart_coverage_pct",
        }
        if not any(old in data for old in moved):
            return data
        migrated = dict(data)
        for old, new in moved.items():
            if old in migrated and new not in migrated:
                migrated[new] = migrated.pop(old)
            else:
                migrated.pop(old, None)
        return migrated

    @model_validator(mode="after")
    def _window_bounds_are_ordered(self) -> Self:
        if self.min_window_days > self.default_window_days:
            raise ValueError("console.min_window_days must not exceed default_window_days")
        if self.default_window_days > self.max_window_days:
            raise ValueError("console.default_window_days must not exceed max_window_days")
        if self.window_presets != sorted(set(self.window_presets)):
            raise ValueError("console.window_presets must be ascending and distinct")
        if self.default_window_days not in self.window_presets:
            raise ValueError("console.default_window_days must be one of console.window_presets")
        # The presets are the only way the page sets its span, so these two bounds
        # would have no reader at all if a preset could sit outside them.
        outside = [
            days
            for days in self.window_presets
            if days < self.min_window_days or days > self.max_window_days
        ]
        if outside:
            raise ValueError(
                "console.window_presets must lie between min_window_days and max_window_days"
            )
        # A rule no preset can reach is a rule the page can never print. The
        # section would show the widen-the-window notice at every setting of the
        # control, which reads as a broken surface rather than as a narrow one.
        if max(self.window_presets) < self.chart_rule_days:
            raise ValueError(
                "console.window_presets must offer a span of at least chart_rule_days"
            )
        return self

    @model_validator(mode="after")
    def _a_day_is_marked_no_later_than_it_is_named(self) -> Self:
        """A rare event is drawn twice, and the drawing has to happen in that order.

        Crossing the first threshold fills the day's tile. Crossing the second
        puts that day in the panel's headline sentence. Set the second below the
        first and the sentence names a day the strip under it left outlined, so
        the reader is told about a day the evidence says was quiet.

        Equal is allowed. A signal whose expected value is zero has no
        distribution to separate the two, and forcing a gap would make somebody
        invent one.
        """
        pairs = (
            ("processor_lost_pct", self.processor_lost_pct_marked, self.processor_lost_pct_named),
            ("model_disk_reads", self.model_disk_reads_marked, self.model_disk_reads_named),
        )
        for signal, marked, named in pairs:
            if marked > named:
                raise ValueError(
                    f"console.{signal}_marked must not exceed {signal}_named: a day the "
                    "headline names is a day the strip has already marked"
                )
        return self

    @model_validator(mode="after")
    def _every_panel_is_named_once(self) -> Self:
        """A panel belongs to one group of one route, and a route groups all or none.

        Two rules, and each catches a different way the knob goes quietly wrong.
        A panel named twice draws twice, which reads as a duplicated instrument
        rather than as a config anybody would look at. And a route that titles
        some groups and not others has no heading level left to give the panels:
        a titled group steps its panels down to an h3 under its own h2, so a
        route holding both kinds would draw two panel titles at two sizes with
        nothing on the page to say why.
        """
        seen_groups: set[str] = set()
        for route, groups in self.panel_groups.items():
            for group in groups:
                if group.id in seen_groups:
                    raise ValueError(f"console.panel_groups repeats the group id {group.id}")
                seen_groups.add(group.id)
            titled = [group.title != "" for group in groups]
            if any(titled) and not all(titled):
                raise ValueError(
                    f"console.panel_groups[{route}] titles some groups and not others"
                )
            named = [panel for group in groups for panel in group.panels]
            if len(named) != len(set(named)):
                raise ValueError(f"console.panel_groups[{route}] names a panel twice")
        return self
