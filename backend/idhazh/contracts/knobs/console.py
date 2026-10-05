"""What window the operator console opens on, and what it fetches to fill it."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class TodayAnchor(StrEnum):
    RIGHT = "right"
    CENTRE = "centre"


ConsoleChrome = Literal["console", "workbench"]


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
        default=14,
        ge=1,
        description=(
            "Initial time span for the console charts. A viewport, not a deletion. "
            "Fourteen on every route, so two routes always open on the same span and "
            "a reader can compare them. What it costs: a route that states a "
            "fourteen-day rule opens on a window equal to the rule, with no margin "
            "either side of it, and thirty days is one press away."
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
    completeness_grace_days: int = Field(
        default=1,
        ge=1,
        description=(
            "How many whole UTC days the day the console's record was written may "
            "trail the reader's own UTC day before the sentence under the tab strip "
            "stops saying how complete the record is and says how many days are "
            "missing. One, because a run finishes at least once a day: a record "
            "from yesterday is what a morning before the first run looks like, and "
            "one from the day before that means a whole day passed with nothing "
            "recorded. It decides only when the count is said, never what it "
            "counts - the count is the whole days between the record's day and "
            "today, so at least one, which is why zero is refused."
        ),
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
    faithfulness_axis_step: int = Field(
        default=5,
        ge=1,
        le=25,
        description=(
            "The grain the faithfulness plot's value axis floor rounds down to, and "
            "the headroom it leaves under the lowest point drawn. A floor sitting "
            "exactly on the lowest point puts that day's mark on the axis line, "
            "where it reads as a missing day rather than as the worst one."
        ),
    )
    faithfulness_axis_floor_max: int = Field(
        default=75,
        ge=10,
        le=95,
        description=(
            "The highest the faithfulness plot's value axis floor may rise to, so a "
            "fixed share of the scale is always on screen. Without it a fortnight "
            "that never left the nineties fills the panel with a three-point wobble, "
            "and an operator learns that a normal day is an incident. The floor's "
            "lower bound is deliberately not a knob: it is evaluation.band_medium_min, "
            "because below that score every summary carries the same published band "
            "and there is nothing left to zoom into."
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
            "How many kinds of machine keep a row of their own on the fleet panel, "
            "the most placed first, before the rest may fold. A kind past these "
            "folds only with kinds on its own speed step, and a step holding one "
            "such kind names it, because a fold that crossed a step would say two "
            "speeds were one. So this chooses how many rows are named for being "
            "common, and the speed steps choose which of the rest may combine. Six "
            "at most, because every named row is one more entry in the strip under "
            "the plot and one more segment in each day's bar."
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
        default=5,
        ge=1,
        le=7,
        description=(
            "How many steps the machine colour has, slowest to fastest. A machine "
            "kind takes the step its median prompt reading speed falls in, cut at "
            "the quantiles of every kind's median over the whole record the page "
            "holds, so a machine keeps its colour when the span changes. Five, "
            "because a reader cannot rank many steps of one hue on a thin bar. "
            "Kinds on one step share its colour, and the name and the speed are "
            "printed beside every one of them."
        ),
    )
    machine_colour_floor_share: float = Field(
        default=0.4,
        gt=0.0,
        lt=1.0,
        description=(
            "How much of the machine hue the slowest step carries, the rest being "
            "the panel's own ground; the steps above it rise evenly to the full "
            "hue. 0.4, because at 0.2 the slowest step stood 1.3 to 1 against the "
            "panel and nearly vanished, and slow machines are what the panel exists "
            "to show. Measured 2026-09-30 on --chart-1: 1.89 to 1 in both themes."
        ),
    )
    absent_hatch_degrees: int = Field(
        default=45,
        ge=0,
        lt=180,
        description=(
            "The angle of the stripes that mark a known thing with no reading - a "
            "machine nobody timed, an item that carries no kernel reading. One "
            "angle for every such hatch, so the texture means one thing on every "
            "panel that draws it."
        ),
    )
    fleet_dot_max_px: int = Field(
        default=8,
        ge=2,
        le=24,
        description=(
            "The largest square, in CSS pixels, the fleet panel draws for one job "
            "when the open span holds too few placements for bars. A busier day "
            "draws smaller squares, so the busiest day still fits the plot."
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

    explorer_chrome: ConsoleChrome = Field(
        default="workbench",
        description=(
            "The frame the console layout draws around the Data explorer route. "
            "Console keeps the full chrome; workbench keeps the compact strip "
            "and lets the route draw the span and Run beside the question."
        ),
    )
    explorer_row_page: int = Field(
        default=50,
        ge=1,
        description="Rows added by one Show more press on the Data explorer answer table.",
    )
    explorer_max_rows: int = Field(
        default=1000,
        ge=1,
        description="Most rows one Data explorer answer holds before it is capped.",
    )
    explorer_max_fetch_bytes: int = Field(
        default=67108864,
        ge=1,
        description=(
            "Most bytes one Data explorer question may fetch. Measured 2026-10-04 on a local "
            "real build in Chromium with the CPU slowed 4x: a question fetching 9.9 MB "
            "(10,379,116 bytes, 138 files, six ledgers over 30 days) answered in about "
            "6 seconds, and no main-thread task passed 1 second; the longest of three "
            "runs was 857 ms. So 64 MiB stands, but the site holds only 22.5 MB today, "
            "so 64 MiB itself is untested until a ledger holds 90 days."
        ),
    )
    explorer_query_max_chars: int = Field(
        default=5790,
        ge=1,
        description=(
            "Most characters one Data explorer SQL statement may hold. The value comes "
            "from docs/reference/benchmarks/address-length-on-pages.md: 5,790 "
            "ASCII characters is the longest worst-case question that fits the "
            "measured GitHub Pages request target with every ledger selected."
        ),
    )
    explorer_reach_days: int = Field(
        default=365,
        ge=1,
        description=(
            "The number of UTC days the Data explorer page's custom From and To date "
            "inputs may reach, including the reader's UTC day."
        ),
    )
    explorer_chart_min_rows: int = Field(
        default=3,
        ge=1,
        description=(
            "Fewest UTC days the Data explorer chart panel needs before it draws "
            "a date chart."
        ),
    )
    explorer_rank_max: int = Field(
        default=30,
        ge=1,
        description="Most rows the Data explorer chart panel draws in a ranked list.",
    )
    explorer_saved_max: int = Field(
        default=20,
        ge=1,
        description="Saved Data explorer questions this browser keeps before dropping the oldest.",
    )
    explorer_history_max: int = Field(
        default=10,
        ge=1,
        description="Recent Data explorer runs this browser keeps.",
    )
    explorer_save_name_max_chars: int = Field(
        default=40,
        ge=1,
        description=(
            "Longest name the Data explorer Save field fills from the statement's "
            "first line."
        ),
    )
    explorer_series_floor_share: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description=(
            "Smallest largest-value share a Data explorer date-chart series must have "
            "against the largest series before it is drawn."
        ),
    )
    explorer_rail_rem: float = Field(
        default=14.0,
        gt=0.0,
        description="Side rail width on the Data explorer question panel, in rem.",
    )
    explorer_readout_lines: tuple[int, int, int, int] = Field(
        default=(5, 3, 4, 2),
        description=(
            "Lines reserved by the Data explorer status bar, for the four frame "
            "breakpoint bands from narrowest to widest."
        ),
    )
    explorer_notice_ms: int = Field(
        default=6000,
        ge=0,
        description=(
            "How long a Data explorer notice that answers a press stays visible, "
            "in milliseconds. Focus or hover holds it."
        ),
    )
    explorer_editor_lines_shown: tuple[int, int] = Field(
        default=(8, 10),
        description=(
            "Fixed visible lines for the Data explorer SQL editor, below 1024 px "
            "and from 1024 px."
        ),
    )
    explorer_strip_shown: tuple[int, int] = Field(
        default=(3, 6),
        description="Example chips shown before the rest fold at phone and wider widths.",
    )
    explorer_answer_svh: int = Field(
        default=60,
        ge=10,
        le=100,
        description="Fixed Data explorer answer region height, in svh percent.",
    )
    explorer_cell_max_ch: int = Field(
        default=40,
        ge=1,
        description="Text cell wrap width in the Data explorer answer table, in characters.",
    )
    explorer_bar_spread_share: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Largest allowed minimum-to-maximum share for in-cell bars.",
    )
    explorer_counter_from_share: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Share of the SQL character limit at which the counter appears.",
    )
    explorer_examples: list[dict[str, object]] = Field(
        default_factory=lambda: [
            {
                "id": "p99-by-machine",
                "title": "p99 job time by machine kind",
                "ledgers": ['host-fingerprint'],
                "days": 14,
                "sql": (
                    "SELECT cpu_model, quantile_cont(job_seconds, 0.99) AS p99_job_seconds, "
                    "count(job_seconds) AS jobs FROM \"host-fingerprint\" "
                    "WHERE job_seconds IS NOT NULL GROUP BY cpu_model ORDER BY p99_job_seconds DESC"
                ),
            },
            {
                "id": "throughput-by-machine",
                "title": "Prompt throughput by machine kind",
                "ledgers": ['host-fingerprint'],
                "days": 14,
                "sql": (
                    "SELECT cpu_model, sum(server_prompt_tokens) / sum(server_prompt_seconds) "
                    "AS prompt_tokens_per_second, count(*) AS jobs FROM \"host-fingerprint\" "
                    "WHERE server_prompt_seconds > 0 GROUP BY cpu_model "
                    "ORDER BY prompt_tokens_per_second DESC"
                ),
            },
            {
                "id": "feeds-gone-quiet",
                "title": "Feeds with no good fetch in the span",
                "ledgers": ['feed-health'],
                "days": 14,
                "sql": (
                    "SELECT feed_id, count(*) AS checks, max(checked_at) AS last_checked "
                    "FROM \"feed-health\" GROUP BY feed_id "
                    "HAVING count(*) FILTER (WHERE outcome = 'ok') = 0 ORDER BY checks DESC"
                ),
            },
            {
                "id": "why-items-failed",
                "title": "What failed to summarize, and why",
                "ledgers": ['item-health'],
                "days": 14,
                "sql": (
                    "SELECT stage, code, count(*) AS items FROM \"item-health\" "
                    "WHERE outcome = 'failed' GROUP BY stage, code ORDER BY items DESC"
                ),
            },
            {
                "id": "scored-per-day",
                "title": "Summaries scored, day by day",
                "ledgers": ['summary-quality-evals'],
                "days": 14,
                "sql": (
                    "SELECT date, count(*) AS scored FROM \"summary-quality-evals\" "
                    "GROUP BY date ORDER BY date"
                ),
            }
        ],
        description=(
            "Example questions shown on the Data explorer page. Each statement is written "
            "against its ledgers' row contracts and answers what its title says."
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
                        "processor-lost",
                        "disk-reads",
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
                        "memory-held",
                        "context-headroom",
                    ],
                ),
                ConsolePanelGroup(
                    id="what-the-model-spends",
                    title="What the model spends",
                    panels=[
                        "article-cost",
                        "prompt-reuse",
                        "read-against-written",
                        "counterfactual-cost",
                    ],
                ),
            ],
            "data-explorer": [
                ConsolePanelGroup(
                    id="data-explorer",
                    title="",
                    panels=[
                        "data-explorer-ask",
                        "data-explorer-rows",
                        "data-explorer-shape",
                    ],
                )
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
    judged_panel_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The panels the sufficiency gates judge, by the ids `panel_groups` "
            "places. Nothing reads it but the gate spec. It is an opt-in list "
            "rather than every panel because two of the gates read attributes no "
            "panel draws yet, and a third needs every trend a panel draws to say "
            "whether it draws the settings-change rule, which most do not. A gate "
            "that is red on the day it lands is a gate people learn to skip. A "
            "panel joins in the pull request that redraws it. Every panel in "
            "`panel_groups` is still pictured by the capture, judged or not."
        ),
    )
    plot_min_fill_share: float = Field(
        default=0.85,
        gt=0.0,
        le=1.0,
        description=(
            "The share of a judged panel's content width its drawn plots must "
            "cover, at every width the console is pictured at. Width and not area: "
            "a full-width chart under a title, a note and a readout strip covers "
            "well under this share of the panel's area, and a floor on area would "
            "teach people to stretch a chart to pass. An estimate, not a "
            "measurement: no panel is judged yet, so nothing has been measured "
            "against it. What replaces it is the share the first judged panels "
            "cover at 390 CSS px, the narrowest width."
        ),
    )

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
    def _explorer_editor_bounds(self) -> Self:
        if any(lines < 1 for lines in self.explorer_readout_lines):
            raise ValueError("console.explorer_readout_lines must hold four positive values")
        if (
            self.explorer_editor_lines_shown[0] < 1
            or self.explorer_editor_lines_shown[0] > self.explorer_editor_lines_shown[1]
        ):
            raise ValueError("console.explorer_editor_lines_shown must be ascending and positive")
        if (
            self.explorer_strip_shown[0] < 1
            or self.explorer_strip_shown[0] > self.explorer_strip_shown[1]
        ):
            raise ValueError("console.explorer_strip_shown must be ascending and positive")
        return self

    @model_validator(mode="after")
    def _every_panel_is_named_once(self) -> Self:
        """A panel belongs to one group of one route, and a route groups all or none.

        Three rules, and each catches a different way the knob goes quietly wrong.
        A panel named twice draws twice, which reads as a duplicated instrument
        rather than as a config anybody would look at. A route that titles
        some groups and not others has no heading level left to give the panels:
        a titled group steps its panels down to an h3 under its own h2, so a
        route holding both kinds would draw two panel titles at two sizes with
        nothing on the page to say why. And a panel id on two routes is one name
        for two panels.
        """
        seen_groups: set[str] = set()
        route_of: dict[str, str] = {}
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
            # One id is one panel on the whole console. A panel's pictures are
            # filed by its id alone, and the judged list is a flat list of ids,
            # so an id on two routes would be two panels that one name picks at
            # random.
            for panel in named:
                if panel in route_of:
                    raise ValueError(
                        f"console.panel_groups names {panel} on {route_of[panel]} and on {route}"
                    )
                route_of[panel] = route
        return self

    @model_validator(mode="after")
    def _only_a_drawn_panel_is_judged(self) -> Self:
        """The gates judge a panel the console draws, and each one once.

        A judged id no route places is a panel the gate spec would look for and
        never find, so it would fail on a page rather than on the file that named
        it. A judged id listed twice is one panel judged twice.
        """
        drawn = {
            panel
            for groups in self.panel_groups.values()
            for group in groups
            for panel in group.panels
        }
        seen: set[str] = set()
        for panel in self.judged_panel_ids:
            if panel in seen:
                raise ValueError(f"console.judged_panel_ids names {panel} twice")
            if panel not in drawn:
                raise ValueError(
                    f"console.judged_panel_ids names {panel}, and no route in "
                    "console.panel_groups draws it"
                )
            seen.add(panel)
        return self
