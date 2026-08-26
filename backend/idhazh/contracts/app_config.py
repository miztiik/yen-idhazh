"""The tunable knobs (`config/idhazh.json`).

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache, the 1 GB published site - are deliberately absent: they are properties of
the platform, and making them editable would invite raising the budget instead
of simplifying the feature (Rule #2).

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, Model, Sha256, Slug
from idhazh.contracts.route import VisualKind


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ModelRef(Model):
    """Which weights, from where. Per-item payloads carry only the `id`."""

    id: Slug
    repo: str = Field(min_length=1, description="Hugging Face repository the GGUF is pulled from.")
    revision: CommitSha | None = Field(
        default=None,
        description=(
            "The hub commit the weights are fetched at. A download that names a branch "
            "gets whatever was uploaded last, so the bytes can change under a config "
            "that still records the old sha256."
        ),
    )
    file: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256: Sha256 | None = Field(
        default=None,
        description="Recorded once measured. A weight that changes silently changes every output.",
    )


class TierWeights(Model):
    """The ranking weight of a source tier. Tier 1 is the institution that IS the fact."""

    institution: float = Field(default=1.0, ge=0.0, le=1.0)
    trade_press: float = Field(default=0.6, ge=0.0, le=1.0)
    community: float = Field(default=0.3, ge=0.0, le=1.0)


class RunConfig(Model):
    safety_ceiling_per_run: int = Field(
        default=160,
        ge=1,
        description=(
            "A crash guard, not an editorial choice. Supply and the ranking decide how "
            "big a day is; this only stops a mis-parsed feed from publishing hundreds "
            "of items in one run. A normal day never reaches it. It is also what sizes "
            "the worst case a work shard and the route stage have to finish, so it is "
            "bounded by the slower of those two."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description="URLs per worker VM. Set by measured model-load amortization, not by taste.",
    )
    max_parallel: int = Field(
        default=4,
        ge=1,
        description=(
            "The most workers a run may derive for itself. It is four rather than the "
            "eight digest.yml lets an operator dispatch, because eight has never "
            "published a day; the three conditions that would move it are in "
            "docs/reference/measurements.md."
        ),
    )
    shard_timeout_minutes: int = Field(
        default=150,
        ge=1,
        description="Derived from the WORST-case article, not the blended figure.",
    )
    route_budget_minutes: int = Field(
        default=40,
        ge=1,
        description=(
            "What the route stage may spend before it stops asking the model and leaves "
            "the rest of the day unrouted. Sized below the job's own timeout, not equal "
            "to it: a job killed at its bound uploads no artifact, so the whole hour's "
            "decisions are lost rather than the tail it could not reach."
        ),
    )
    success_floor_pct: int = Field(
        default=70, ge=0, le=100, description="Below this, the run additionally opens an issue."
    )


class CollectConfig(Model):
    quarantine_after_failures: int = Field(default=5, ge=1)
    watchlist_max_entities: int = Field(default=30, ge=1)
    max_per_source: int = Field(
        default=2,
        ge=1,
        description=(
            "Most items one feed may contribute to one vertical in a day. Without it, a "
            "quiet news day is whichever blog published most."
        ),
    )
    tier_weights: TierWeights = Field(default_factory=TierWeights)
    repetition_weight: float = Field(default=1.0, ge=0.0)
    watchlist_bonus: float = Field(default=0.5, ge=0.0)
    front_page_bonus: float = Field(default=0.4, ge=0.0)
    recency_weight: float = Field(
        default=0.6,
        ge=0.0,
        description=(
            "How much freshness may move a score. A bonus, never a filter: a strong "
            "older item still outranks a weak new one, which a hard age cutoff cannot do."
        ),
    )
    recency_half_life_hours: float = Field(
        default=18.0,
        gt=0.0,
        description=("Hours for the recency bonus to halve. At 18 h a day-old item keeps a third."),
    )
    max_future_hours: float = Field(
        default=6.0,
        ge=0.0,
        description=(
            "A publish date further ahead than this is not believed and the item falls "
            "back to first sight. Feeds that stamp tomorrow would otherwise take the "
            "top slot every single day."
        ),
    )
    seen_window_days: int = Field(
        default=90,
        ge=1,
        description=(
            "How far back the first-sight store is consulted. Older shards stay "
            "committed and readable; they are just not evidence about today."
        ),
    )
    blocked_url_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Case-insensitive substrings of a canonical address that never enter the "
            "pool. For the promotional page a working news feed syndicates: an affiliate "
            "product review is short declarative prose, so it is trivially entailed and "
            "no faithfulness threshold detects it at any cut. Empty by default - the "
            "entries are a source list and live in config/ (Rule #6)."
        ),
    )


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
    )
    min_source_words: int = Field(
        default=60,
        ge=1,
        description=(
            "Below this the item publishes through the brief tier. It is derived in "
            "AppConfig from summarize.bands[0].target_words_min divided by "
            "evaluation.brief_compression_ceiling."
        ),
    )
    prose_sentence_min: int = Field(
        default=3,
        ge=1,
        description="Sentences of prose needed before a page stops carrying the not_prose signal.",
    )
    prose_sentence_words_min: int = Field(
        default=8,
        ge=1,
        description="Words a sentence needs before it counts as prose for the shape signal.",
    )
    prose_line_count_min: int = Field(
        default=12,
        ge=1,
        description="Lines needed before the line-shape guard runs.",
    )
    prose_line_ratio_min: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum share of lines that must look like prose on a line-heavy page.",
    )
    reject_not_prose: bool = Field(
        default=False,
        description="If true, a not_prose signal rejects the item. Default records and publishes.",
    )
    reject_boilerplate: bool = Field(
        default=False,
        description=(
            "If true, a boilerplate signal rejects the item. Default records and publishes."
        ),
    )
    boilerplate_ratio_max: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="Share of an item's lines also seen on sibling items from the same host.",
    )
    paywall_markers: list[str] = Field(
        default_factory=lambda: [
            "isaccessibleforfree\":false",
            "isaccessibleforfree\": false",
            "subscribe to continue reading",
            "register or subscribe to continue",
        ],
        min_length=1,
        description=(
            "Fallback markers used only when publisher JSON-LD does not declare the paywall."
        ),
    )
    max_body_bytes: int = Field(default=2_000_000, ge=1024)
    max_retries: int = Field(default=3, ge=0)
    backoff_initial_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    request_timeout_seconds: float = Field(default=20.0, gt=0.0)
    user_agent: str = Field(default="yen-idhazh/1.0 (+https://github.com/miztiik/yen-idhazh)")


class InferenceConfig(Model):
    """Decoding is pinned here so a change of output is a reviewable diff."""

    n_ctx: int = Field(default=8192, ge=512)
    n_threads: int = Field(default=4, ge=1)
    n_batch: int = Field(default=512, ge=1)
    n_ubatch: int = Field(default=512, ge=1)
    n_parallel: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -np. None omits the flag and keeps the runtime default.",
    )
    n_threads_batch: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -tb. None omits the flag and lets it follow n_threads.",
    )
    startup_warmup: bool = Field(
        default=True,
        description="If false, emit --no-warmup. True lets llama-server warm at startup.",
    )
    metrics: bool = Field(
        default=True,
        description=(
            "If true, emit --metrics and llama-server serves its counters on "
            "/metrics. On by default: without them a run cannot say how close it came "
            "to n_ctx, and a concurrency result has no busy-slot number to read it by."
        ),
    )
    flash_attention: Literal["on", "off"] | None = Field(
        default=None,
        description="llama-server -fa. None omits the flag and leaves the runtime on auto.",
    )
    load_mode: Literal["mmap+mlock"] | None = Field(
        default=None,
        description="llama-server -lm. None omits the flag and keeps the runtime default.",
    )
    cache_type_k: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctk. None omits the flag and keeps full-precision KV.",
    )
    cache_type_v: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctv. None omits the flag and keeps full-precision KV.",
    )
    priority: int | None = Field(
        default=None,
        ge=-1,
        le=3,
        description="llama-server --prio. None omits the flag and keeps normal priority.",
    )
    poll: int | None = Field(
        default=None,
        ge=0,
        description="llama-server --poll. None omits the flag and keeps the runtime default.",
    )
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    seed: int = Field(
        default=0,
        description="Dead code under greedy decoding. Never cited as the determinism control.",
    )
    thinking: bool = Field(
        default=False,
        description="Off. Reasoning measurably increases hallucination when summarizing.",
    )
    max_output_tokens: int = Field(
        default=900,
        ge=1,
        description=(
            "A crash guard, not a length target. The prompt sets the length; this only "
            "stops a runaway decode from burning a shard's whole timeout. Sized at 250 "
            "the reply ran out of budget mid-object and failed as a shape error, which "
            "named the wrong cause - so it is set well above any summary we want."
        ),
    )
    request_timeout_minutes: float = Field(
        default=22.1,
        gt=0.0,
        description=(
            "One summarizer POST may wait this long. Sized from the measured worst "
            "8B long article plus one cold prompt prefix, doubled; the shard timeout "
            "remains the outer bound."
        ),
    )


class ModelsConfig(Model):
    summarize: ModelRef
    route: ModelRef
    inference: InferenceConfig = Field(default_factory=InferenceConfig)


class SummaryBand(Model):
    """How long a summary to ask for, once the article is at least this long."""

    min_source_words: int = Field(
        ge=0, description="The band applies to articles this long and longer."
    )
    target_words_min: int = Field(ge=1, description="The shortest summary the prompt asks for.")
    target_words_max: int = Field(ge=1, description="The longest summary the prompt asks for.")

    @model_validator(mode="after")
    def _the_range_is_ordered(self) -> Self:
        if self.target_words_min >= self.target_words_max:
            raise ValueError("target_words_min must sit below target_words_max")
        return self


def _default_bands() -> list[SummaryBand]:
    """Three sizes: the release note, the article, the long read.

    Starting points chosen from the shape of the sources we collect, not
    measurements - nothing here may be quoted as one (Rule #10). The first
    band begins at zero so every article lands in one, and the shortest ask sits
    above `evaluation.summary_words_min` so a summary that misses low by a few
    words is still publishable.
    """
    return [
        SummaryBand(min_source_words=0, target_words_min=30, target_words_max=45),
        SummaryBand(min_source_words=60, target_words_min=50, target_words_max=90),
        SummaryBand(min_source_words=700, target_words_min=70, target_words_max=150),
        SummaryBand(min_source_words=2000, target_words_min=110, target_words_max=200),
    ]


class SummarizeConfig(Model):
    """What the prompt asks the model for.

    Separate from `evaluation`, which is what the pipeline agrees to accept. The
    two ranges are deliberately different: a prompt is a request and a gate is a
    rule, and asking for a tighter range than we enforce is what stops a
    two-word miss from losing a story. `AppConfig` checks the invariant that
    actually matters - every ask sits inside the gate - because only there are
    both blocks visible.

    Every value here is substituted into the prompt text at render time, so the
    prompt cannot drift from the bounds the pipeline enforces (Rule #6).
    """

    bands: list[SummaryBand] = Field(
        default_factory=_default_bands,
        min_length=1,
        description=(
            "One length ask per article size, ordered by min_source_words. A release "
            "note and a long read asked for the same range gives a padded summary of "
            "the first and a thin one of the second."
        ),
    )
    key_points_min: int = Field(
        default=2,
        ge=1,
        description=(
            "Also the decoder's floor. The prompt and the response schema read this same "
            "number, or the decoder rejects a reply that did exactly what was asked."
        ),
    )
    key_points_max: int = Field(default=5, ge=1, description="Also the decoder's ceiling.")
    title_words_min: int = Field(
        default=6,
        ge=1,
        description=(
            "Shortest title the prompt asks for. Below this a headline stops naming "
            "who did what, and the reader is back to guessing from the source's own "
            "framing."
        ),
    )
    title_words_max: int = Field(
        default=14,
        ge=1,
        le=40,
        description=(
            "Longest title the prompt asks for, and the decoder's ceiling. Unlike the "
            "summary there is no floor on the decoder: a headline does not stop early, "
            "and a floor would only pad a good short one. Capped at 40 so the widest "
            "decoder ceiling this can produce still fits an UntrustedLine, which is "
            "what the payload field is."
        ),
    )
    max_verbatim_words: int = Field(
        default=20,
        ge=1,
        description=(
            "Longest quotation the prompt allows, and it must be attributed. Long "
            "enough to carry a real sentence somebody said, short enough that a summary "
            "cannot become the article. The ledger measures the run that actually came "
            "back (`verbatim_run`), so this number is the ask and that column is the "
            "answer."
        ),
    )

    @model_validator(mode="after")
    def _the_bands_cover_every_article(self) -> Self:
        if self.bands[0].min_source_words != 0:
            raise ValueError("the first band must start at zero, or a short article has no band")
        starts = [band.min_source_words for band in self.bands]
        if starts != sorted(set(starts)):
            raise ValueError("bands must climb, and no two may start at the same length")
        if self.key_points_min > self.key_points_max:
            raise ValueError("key_points_min must not exceed key_points_max")
        if self.title_words_min > self.title_words_max:
            raise ValueError("title_words_min must not exceed title_words_max")
        return self

    def band_for(self, source_words: int) -> SummaryBand:
        """The longest band the article reaches. Total, because band one starts at zero."""
        chosen = self.bands[0]
        for band in self.bands:
            if source_words >= band.min_source_words:
                chosen = band
        return chosen


class EvaluationConfig(Model):
    band_high_min: float = Field(default=0.80, ge=0.0, le=1.0)
    band_medium_min: float = Field(default=0.50, ge=0.0, le=1.0)
    lead_coverage_min: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description=(
            "Below this the summary missed the source lead. It caps a high band at "
            "medium rather than forcing low."
        ),
    )
    truncation_gap_max: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Score gap that flags a truncation artifact rather than a hallucination.",
    )
    summary_words_min: int = Field(
        default=25,
        ge=1,
        description=(
            "Below this it is a headline, not a summary. Set under the lowest band in "
            "`summarize.bands`: the prompt is a request, and dropping an item for missing "
            "it by two words loses a story to a rounding error."
        ),
    )
    brief_compression_ceiling: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "Maximum summary/source ratio for a brief item. Also caps verbatim_run on "
            "briefs and derives extract.min_source_words from the first brief ask."
        ),
    )
    summary_words_max: int = Field(
        default=250, ge=1, description="Above this it is a copy. Absolute, not a ratio."
    )
    spot_checks_per_week: int = Field(default=10, ge=0)
    labellers: list[Slug] = Field(
        default_factory=list,
        description=(
            "Who may write a faithfulness label. Empty by default, so a fresh clone can "
            "draw the queue and read it but cannot record a verdict. The list is what "
            "keeps a machine out of the label ledger: there is no author field a model "
            "could fill, and adding one would be a schema change with a written reason "
            "(CLAUDE.md section 0a)."
        ),
    )
    label_draw_per_decile: int = Field(
        default=6,
        ge=1,
        description=(
            "Labels drawn from each hhem decile. Uniform, not weighted to the cuts: the "
            "first question is what `high` means at all, and a boundary-weighted draw "
            "cannot answer that."
        ),
    )
    label_min_run_days: int = Field(
        default=10,
        ge=1,
        description=(
            "Distinct run-days at one scorer version and one pipeline fingerprint before "
            "a draw is worth finalising. A draw over one day is a draw over one day's "
            "sources."
        ),
    )
    golden_set_size: int = Field(default=20, ge=1)
    validation_articles: int = Field(
        default=20,
        ge=1,
        description="Golden articles a candidate must be scored on before its mean counts.",
    )
    validation_drop_max: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description=(
            "How far below its leaderboard number the incumbent may land before the "
            "ranking stops being a usable prior and the challengers get scored too."
        ),
    )
    validation_switch_margin: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description=(
            "How much better a challenger must be on our own corpus to change the pick. "
            "A number, because 'materially diverges' is an argument waiting to happen."
        ),
    )
    qualification_pool_multiple: int = Field(
        default=6,
        ge=1,
        description=(
            "Articles a qualification shard extracts for every one it replays. A floor "
            "on the choice the stratified selection gets, never a cap on the walk: a "
            "shard that has not yet been offered every length tier keeps going through "
            "its slice. Raising it buys fetch seconds, never model minutes, because the "
            "model still sees corpus_per_shard articles - one address measured 2.1 s on "
            "2026-08-26 over 150 of them, against 330 minutes for the job."
        ),
    )

    @model_validator(mode="after")
    def _bands_and_ranges_are_ordered(self) -> Self:
        if self.band_medium_min >= self.band_high_min:
            raise ValueError("band_medium_min must sit below band_high_min")
        if self.summary_words_min >= self.summary_words_max:
            raise ValueError("summary_words_min must sit below summary_words_max")
        return self


class DriftConfig(Model):
    month_over_month_pct: float = Field(default=10.0, gt=0.0)
    year_over_year_pct: float = Field(default=5.0, gt=0.0)
    quarterly_refresh_fraction: float = Field(default=0.5, gt=0.0, le=1.0)


class RetentionConfig(Model):
    """Ships disabled. A default is a promise, not a placeholder."""

    image_months: int = Field(
        default=-1, ge=-1, description="-1 disables pruning entirely. Age-based only, never size."
    )
    dry_run: bool = True
    max_deletes_per_run: int = Field(
        default=200,
        ge=0,
        description="The fuse. An off-by-one in a date parse must not eat the archive.",
    )
    site_budget_mb: int = Field(
        default=800,
        ge=1,
        description=(
            "Logs a warning above this, and does nothing else: it never fails a build "
            "and never deletes. Sized in days of warning, not in round numbers. It sits "
            "224 MB below the platform's 1 GB ceiling, which is 26 days of warning at "
            "the fastest growth this project has measured (a PNG on every item, "
            "8,537 KB/day, 2026-08-23), against a 14-day target. The target is a "
            "judgement about one maintainer acting on one warning, not a measurement "
            "(Rule #10). The arithmetic and its inputs are in "
            "docs/reference/measurements.md, 'Where the alarm fires, and what it buys'."
        ),
    )


class LoggingConfig(Model):
    level: LogLevel = LogLevel.INFO


class VisualsConfig(Model):
    """Routing and rendering knobs. "Nothing" is the common answer, by design.

    `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. The
    four-way enum lives in the contract because a payload must be able to say
    `image`; the router may only choose a kind whose renderer exists, so turning
    one on is a config edit rather than a code change.
    """

    enabled_kinds: list[VisualKind] = Field(
        default_factory=lambda: [VisualKind.CHART],
        description=(
            "Kinds the router may choose. `none` is always available and never listed. "
            "Diagram ships off: the model drafted it zero times in 88 items and rendered "
            "it zero times in 703 (ubuntu-latest, 2026-08-24/25), while its presence made "
            "the router's own pre-filter unfireable, because a diagram's steps come from "
            "prose and nothing about it is decidable in advance. The renderer is built and "
            "tested; turning the arm back on is this one word."
        ),
    )
    min_chart_points: int = Field(
        default=3,
        ge=2,
        description="Below this a chart says less than the sentence it sits under.",
    )
    max_chart_points: int = Field(default=8, ge=2)
    min_diagram_steps: int = Field(default=3, ge=2)
    max_diagram_steps: int = Field(default=6, ge=2)
    canvas_width: int = Field(
        default=800,
        ge=200,
        description="One fixed canvas for every visual. Height follows the 16:10 ratio.",
    )
    max_output_tokens: int = Field(
        default=400,
        ge=1,
        description="Routing emits a small object. It does not need the summarizer's budget.",
    )
    max_facts: int = Field(
        default=16,
        ge=2,
        description=(
            "How many quantities the router may choose between. A long indexed menu is "
            "lost-in-the-middle for a small model picking an integer index."
        ),
    )
    lead_words: int = Field(
        default=150,
        ge=1,
        description=(
            "How much of the article's own opening the router reads beside the summary. "
            "This is most of each request's prefill, and prefill is most of the stage's "
            "wall-clock, so it is a measured lever rather than a literal (Rule #6)."
        ),
    )
    request_timeout_minutes: float = Field(
        default=2.0,
        gt=0.0,
        description=(
            "One routing POST may wait this long. Sized from the measured worst routed "
            "item - 56.0 s on ubuntu-latest, 2026-08-24 - doubled. The stage used the "
            "summarizer's 150-minute shard bound before this existed, which is longer "
            "than the job it runs in, so it could never fire."
        ),
    )

    @property
    def canvas_height(self) -> int:
        """16:10, matching the frontend's fixed figure box exactly."""
        return round(self.canvas_width * 10 / 16)

    @model_validator(mode="after")
    def _bounds_are_orderable(self) -> Self:
        if self.max_chart_points < self.min_chart_points:
            raise ValueError("max_chart_points is below min_chart_points")
        if self.max_diagram_steps < self.min_diagram_steps:
            raise ValueError("max_diagram_steps is below min_diagram_steps")
        if VisualKind.NONE in self.enabled_kinds:
            raise ValueError("`none` is always reachable and is never listed as enabled")
        return self


class ThemeChoice(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class VisualSide(StrEnum):
    """Where a visual sits beside its text, at `sm` and above. Below that, always above."""

    ABOVE = "above"
    LEADING = "leading"
    TRAILING = "trailing"


class TodayAnchor(StrEnum):
    RIGHT = "right"
    CENTRE = "centre"


class ConsoleConfig(Model):
    """Knobs for the operator console's time viewport."""

    default_window_days: int = Field(
        default=30,
        ge=1,
        description="Initial time span for the console charts. A viewport, not a deletion.",
    )
    today_anchor: TodayAnchor = Field(
        default=TodayAnchor.RIGHT,
        description="Where today sits in the initial viewport when enough history exists.",
    )
    pan_days: int = Field(default=7, ge=1, description="Days moved by one arrow-key pan.")
    zoom_factor: float = Field(default=1.5, gt=1.0)
    min_window_days: int = Field(default=7, ge=1)
    max_window_days: int = Field(default=366, ge=1)
    min_attempts_for_rate: int = Field(
        default=5,
        ge=1,
        description="Below this count a rate is outlined because the denominator is thin.",
    )
    chart_height: int = Field(default=180, ge=120)
    chart_width: int = Field(
        default=600,
        ge=240,
        description=(
            "The width a console chart is drawn at on the server, in CSS pixels. A "
            "prerendered chart has no element to measure, and a chart drawn in "
            "arbitrary units and then stretched by its viewBox renders its labels at "
            "whatever the stretch factor happens to be - measured 2026-08-25, one page "
            "put the same font-size at 4.5px and at 16.6px. 600 is what the reading "
            "column leaves a full-width chart on any window wide enough to reach it; "
            "a narrower one redraws at its measured width once a script runs."
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

    @model_validator(mode="after")
    def _window_bounds_are_ordered(self) -> Self:
        if self.min_window_days > self.default_window_days:
            raise ValueError("console.min_window_days must not exceed default_window_days")
        if self.default_window_days > self.max_window_days:
            raise ValueError("console.default_window_days must not exceed max_window_days")
        return self


class UiConfig(Model):
    """The published surface's knobs.

    `sections` is the modularity story: reordering the page is a config edit,
    not a code change. What is deliberately absent is a per-element layout
    engine - on the surface that matters, a phone, there is no left and no
    right, and a per-reader layout would break the promise that a shared link
    shows the recipient what the sender saw.
    """

    sections: list[str] = Field(
        default_factory=lambda: ["notice", "topics", "items"],
        min_length=1,
        description="Render order of the day page's sections, by registry id.",
    )
    theme_default: ThemeChoice = ThemeChoice.SYSTEM
    visual_side: VisualSide = VisualSide.ABOVE
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
    items_per_topic: int = Field(
        default=3,
        ge=1,
        description=(
            "How many of a topic's stories the all-topics page shows before it links to "
            "the rest. One long queue has no usable first screen: its opening items are "
            "whichever topic sorts first. Nothing is removed or re-ranked - every item "
            "stays one click away on its own topic page."
        ),
    )
    repo_url: str = Field(default="https://github.com/miztiik/yen-idhazh", min_length=1)
    site_title: str = Field(default="yen-idhazh", min_length=1)
    tagline: str = Field(
        default="A daily digest that checks its own work.",
        min_length=1,
    )
    read_mark_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How many digest days of read marks the browser keeps. Marks are held per "
            "digest date, so a mark made on one day can never grey out a different "
            "day's article. Every page load keeps the newest days up to this number "
            "and drops the rest, which bounds the store without trusting the device "
            "clock. One week covers a reader who comes back after a break."
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


class PageWeightConfig(Model):
    """A gzip-size ceiling per prerendered route, enforced by
    `frontend/scripts/bundle-gate.mjs`.

    The gate reads `config/idhazh.json`, never this model, so a number here
    would be a second copy of what the file already holds, free to drift from
    the one the gate enforces. The default is empty for that reason: the
    committed config is the single source, and this model owns only the shape
    and the validation (Rule #6).

    Only a route whose HTML does not grow with the published corpus is worth a
    fixed ceiling. `/404` and `/evals/` render no day and no ledger, so their
    weight is a function of source alone. `/archive/` inlines every committed
    day and `/console/` grows with the ledger its charts read, so a byte ceiling
    on either fails on an ordinary publish rather than catching a regression;
    the marker count in `frontend/tests/payload-weight.spec.ts` covers the class
    those two belong to, and a route the config does not name is reported by the
    gate without failing it.
    """

    ceilings_bytes: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Route class -> the largest gzip -9 size that route's prerendered HTML may "
            "reach. The committed values live in config/idhazh.json, which the gate "
            "reads; this default is empty so the numbers are not duplicated here where "
            "they could drift from the file the gate enforces (Rule #6). A route the "
            "object does not name is measured and reported by the gate but not failed, "
            "so only routes whose weight does not grow with the published corpus - "
            "/404 and /evals/ today - carry a ceiling."
        ),
    )

    @model_validator(mode="after")
    def _a_ceiling_bounds_a_route(self) -> Self:
        for route, ceiling in self.ceilings_bytes.items():
            if not route.startswith("/"):
                raise ValueError(f"page_weight ceiling {route!r} is not a route")
            if ceiling <= 0:
                raise ValueError(f"page_weight ceiling for {route} must be above zero")
        return self


class AssistConfig(Model):
    """On-device archive search: what the encoder reads, and what the list shows.

    Every value here was a literal with no override path (Rule #6). The first two
    describe how much of an item the encoder is allowed to read; the rest describe
    what the reader's list keeps. All five are set from measurement rather than
    from taste.
    """

    max_tokens: int = Field(
        default=256,
        ge=16,
        le=512,
        description=(
            "How far into an item's text the encoder reads before it truncates. 512 "
            "is the hard ceiling because that is the encoder's position table; the "
            "default is 256 because that is what the model was trained at, and the "
            "measurement says nothing is waiting above it. Measured 2026-08-26 over "
            "the 1886 embedded items of the six committed days: p95 217 tokens, p99 "
            "243, max 280, and 0.58 percent of items run past 256 by a mean of 13 "
            "tokens. Raising it would read 0.05 percent more text and re-date every "
            "committed vector."
        ),
    )
    min_readable_letter_share: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much of an item's alphabet the encoder has to know before the item "
            "gets a vector at all. The committed weights carry an English uncased "
            "vocabulary, so an item written in another script still produces a "
            "confident unit vector that no query can retrieve. Below this share the "
            "item gets no vector and the run records why. Half is a plain reading of "
            "'mostly not in our alphabet', and it sits in the middle of an empty "
            "band: measured 2026-08-26 over the six committed days, 3 of 1889 items "
            "score 0.0 and the next lowest scores 0.9975, so every threshold between "
            "0.01 and 0.99 selects the same three items."
        ),
    )
    similarity_floor: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine similarity a result must reach to be shown at all. A SELECTOR, "
            "never reported to a reader as a quality signal. Re-measured 2026-08-26 on "
            "the backfilled archive (Windows 11, 12 logical CPUs, onnxruntime 1.29.0; "
            "2,119 embedded items, 60 labelled queries, 126,843 same-domain non-answer "
            "pairs): non-answers score a mean of 0.0761, a p95 of 0.2716 and a p99 of "
            "0.3992; the 297 right answers score a p10 of 0.3753 and a median of 0.5314. "
            "The noise distribution did not move when the corpus grew 3.7x - the earlier "
            "reading over 34,715 pairs was mean 0.074, p95 0.269, p99 0.399 - so the "
            "floor does not move either. 0.35 sits at the p98.12 of same-domain noise, "
            "keeps 93.6% of right answers, and lets 1.88% of non-answers survive. 0.45 "
            "would cut noise to 0.50% and cost 0.073 of recall@10, which is two standard "
            "errors and so a measurable loss."
        ),
    )
    result_limit: int = Field(
        default=10,
        ge=1,
        description=(
            "How many results the flat list shows. The list carries no rank cue, so "
            "this is also the denominator the recall bar is measured against - the "
            "denominator is min(right answers, this), because more right answers than "
            "slots cannot all be shown."
        ),
    )
    recall_min: float = Field(
        default=0.69,
        ge=0.0,
        le=1.0,
        description=(
            "The regression bar for recall@result_limit over the committed query set, "
            "counted over right answers that carry a vector. Coverage is excluded on "
            "purpose: an item the pipeline never embedded cannot be retrieved at any "
            "threshold, so counting it here would fail this gate for a defect in "
            "another stage. Set two standard errors below the 2026-08-26 baseline of "
            "0.767 +/- 0.036 (n=60), measured on Windows 11, 12 logical CPUs, "
            "onnxruntime 1.29.0 against the fully backfilled archive. That baseline is a "
            "LOWER BOUND: 55.5% of the unlabelled items now holding a slot were "
            "unembedded when the labels were pooled, so the labeller could not have "
            "judged them, and every one of them is counted as a wrong answer. Until the "
            "labels are completed against the whole corpus this bar can drift down for a "
            "reason that is not a regression - see docs/concepts/evaluation.md."
        ),
    )


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27",
            change="ui.archive_page_size added, defaulting to 25.",
            why=(
                "The archive now lists every published story instead of a row per day, "
                "and a list of thousands needs a first screen. The number belongs in "
                "config rather than in the page (Rule #6). Additive with a default, so "
                "an older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T21:45",
            change=(
                "page_weight.ceilings_bytes default is now empty, and /archive/ and "
                "/console/ are dropped from the committed config."
            ),
            why=(
                "The default duplicated the four numbers the gate reads from "
                "config/idhazh.json, so raising a ceiling meant editing two files a test "
                "then forced to agree - config is the single source now (Rule #6). "
                "/archive/ grows with every committed day and /console/ with the ledger "
                "its charts read, so their fixed ceilings failed on ordinary publishes "
                "rather than catching regressions; the gate now reports an unnamed route "
                "without failing it. Older config still validates and the empty default "
                "changes no committed value, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T20:00",
            change="ModelRef gained an optional revision: the hub commit the weights are at.",
            why=(
                "Every weights download in the pipeline and the measurement harness read "
                "`resolve/main`, which is a branch. Upstream re-uploads a GGUF and the "
                "bytes change under a config that still records the old sha256, so a run "
                "either dies at the checksum or - where no checksum runs - measures a "
                "model nobody named (Rule #10). This field was rejected once as "
                "speculative because nothing read it; validate.yml now pins a revision "
                "and the adoption target names one, so it has readers. Optional with a "
                "null default, so the published run manifests that carry no revision "
                "still validate and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:45",
            change="page_weight.ceilings_bytes['/archive/'] moved from 1,676,048 to 1,676,110.",
            why=(
                "The archive page now carries the search box, and a box costs bytes. "
                "Measured by building one tree twice on the same machine, same day "
                "payloads: with main's frontend /archive/ gzips to 1,675,988 and with "
                "the search box to 1,676,050, so the box costs 62 bytes against 60 of "
                "headroom. The new ceiling keeps the same 60-byte allowance the other "
                "three routes carry rather than rounding up to a number that would stop "
                "the gate firing. What the bytes buy is the input, its label and its "
                "empty state on the one page that can search the whole archive. Same "
                "field, same type: an older config still validates. A changed default, "
                "so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:20",
            change=(
                "assist.recall_min default moved from 0.85 to 0.69. "
                "assist.similarity_floor keeps 0.35 and carries a re-measured description."
            ),
            why=(
                "0.85 was calibrated against an archive where only 44.5% of items carried "
                "a vector, and the backfill took that to 99.9%. On the same 47 queries, "
                "the same labels and the same ranker, the number went 0.902 +/- 0.036 to "
                "0.743 +/- 0.042. That is not a ranking regression: holding the corpus to "
                "the same 944 items and swapping in the re-encoded vectors gives 0.910 "
                "+/- 0.034, so the vectors improved by 0.007. The whole effect is 1,175 "
                "items that the index could not see competing for the same ten slots "
                "(-0.142) plus a denominator that grew with coverage (-0.018). The new "
                "baseline over all 60 queries is 0.767 +/- 0.036 and the bar is two "
                "standard errors below it. It is a lower bound: 55.5% of the unlabelled "
                "items now holding a slot were unembedded when the labels were pooled, so "
                "nobody could have judged them, and they are counted as wrong answers. "
                "The floor does not move because the measurement says not to - the "
                "same-domain noise distribution is unchanged at 3.7x the pair count "
                "(p95 0.269 -> 0.2716, p99 0.399 -> 0.3992). Same fields, same types: an "
                "older config still validates and a committed config that names 0.85 "
                "still loads. A changed default, so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:10",
            change="Added the assist search knobs: similarity_floor, result_limit and recall_min.",
            why=(
                "Archive search had no measurement at all, and its two behavioural "
                "constants were literals in the ranking module with no override path "
                "(Rule #6). The floor was 0.20 and is now 0.35, which is a measured "
                "change rather than a preference: at 0.20 every one of eight off-domain "
                "probe queries returned results - one of them eighteen - so 'Nothing in "
                "the archive is close to that' was a promise the selector could not keep. "
                "Measured 2026-08-26 on the committed archive over 60 hand-labelled "
                "queries: the floor cuts surviving non-answers from 11.4% to 1.9% and "
                "costs 0.035 of reachable recall@10, which is inside one standard error. "
                "recall_min is the regression bar the new backend eval enforces. All "
                "three are additive with defaults, so an older config still validates and "
                "no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:05",
            change="Added the assist block: max_tokens and min_readable_letter_share.",
            why=(
                "The encoder's token cap was a literal in embed.py, which is exactly the "
                "kind of tunable Rule #6 puts in config. The second knob is new "
                "behaviour: an item the encoder cannot read used to get a confident "
                "vector no query could retrieve, and now gets no vector and a logged "
                "reason. Both defaults are measured, not chosen - see the field "
                "descriptions. Additive with defaults, so an older config still "
                "validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:00",
            change="Added the page_weight block.",
            why=(
                "A prerendered page could grow without limit and nothing said so. The "
                "marker count in payload-weight.spec.ts catches a day payload inlined "
                "where no day is rendered; it cannot see /archive/, which inlines every "
                "day on purpose, and it cannot see growth that carries no marker. A "
                "ceiling per route catches both. It is a knob rather than a literal in "
                "the gate script (Rule #6). Additive with a default, so an older config "
                "still validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change=(
                "run.safety_ceiling_per_run default moved from 200 to 160. "
                "run.max_parallel gained a description."
            ),
            why=(
                "The ceiling is the worst case every downstream bound has to clear, and "
                "200 cleared neither of them. digest.yml now derives the automatic work "
                "fan-out as min(ceil(items / run.shard_size), run.max_parallel), so at "
                "the ceiling a worker draws 50 items across the four workers a scheduled "
                "run gets. Against the Qwen3.5-9B candidate that is 318 derived minutes "
                "by length interpolation and 345 by decode ratio, over a 330-minute work "
                "timeout that nobody may raise (Rule #2); at 160 the same arithmetic "
                "gives 40 items, 254 and 276 minutes. The route stage says the same "
                "thing from the other side: its measured slow-host ceiling is 166 items "
                "at a 50-minute budget (2026-08-25, six runs, 703 items), so 200 and the "
                "router never agreed and 160 does. The largest day ever planned is 149 "
                "items (run 32742672105, 2026-08-24), so 160 removes nothing that has "
                "ever been read. run.max_parallel had no description at all while being "
                "the bound the derivation clamps by, and it is deliberately four while "
                "digest.yml lets an operator dispatch eight. Same fields, same types, "
                "same units: an older config still validates, and a committed config "
                "that names 200 still loads. A changed default, so it is stamped here "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T19:30",
            change="Added models.inference.metrics, on by default.",
            why=(
                "A run could not say how close it came to the context wall, and no "
                "number said whether more than one slot was ever busy. llama-server "
                "counts both already and only publishes them under --metrics. The flag "
                "is a knob rather than a workflow literal (Rule #6), and the endpoint "
                "it opens is llama-server's own loopback surface inside a CI job, so no "
                "reader is served by it and Rule #1 is untouched. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T18:00",
            change="Added console.chart_width.",
            why=(
                "Every console chart is prerendered, so on the server there is no element "
                "to measure and the chart needs a width given to it. Without one each "
                "chart drew into an arbitrary viewBox and let the browser stretch it: "
                "measured 2026-08-25 at a 1057px window, one page scaled the same "
                "font-size to 4.5px in one panel and 16.6px in the next. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change=(
                "run.route_budget_minutes now stops the route stage instead of warning it, "
                "and visuals.enabled_kinds defaults to chart alone."
            ),
            why=(
                "Warning after the fact never saved a day. Measured on ubuntu-latest over "
                "six runs on 2026-08-24/25 (703 routed items): the mean per-item cost is "
                "20.7 s on a fast host and 40.3 s on a slow one, so a 145-item day needs "
                "50 to 97 minutes against a 60-minute job. Four of the six runs were "
                "cancelled at the bound, and a cancelled job skips its upload step - so "
                "every decision the hour bought was discarded and the day published with "
                "zero visuals. The diagram arm is what made the existing pre-filter "
                "unfireable: it is reachable for every item by construction, so the model "
                "was asked about 145 of 145 items on 2026-08-25 while it drafted zero "
                "diagrams in 88 and rendered zero in 703. With the arm off, 68 of those "
                "145 items (46.9%) never reach the model at all. Same fields, same types, "
                "same units; an older config still validates. Semantic shift on one and a "
                "changed default on the other, so both are stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:40",
            change=(
                "Added evaluation.labellers, evaluation.label_draw_per_decile and "
                "evaluation.label_min_run_days."
            ),
            why=(
                "The faithfulness cuts are a reader-facing promise with no measured error "
                "rate behind them, and the missing instrument was labels rather than more "
                "rows. The draw size and the collection floor are tuning decisions, not "
                "literals (Rule #6). `labellers` is empty by default, so a fresh clone can "
                "draw the queue and read it but cannot record a verdict - and because the "
                "row has no author field a model could fill, that list is a structural "
                "control rather than a discouragement. Additive with defaults."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:10",
            change=(
                "Added visuals.request_timeout_minutes, visuals.lead_words and "
                "run.route_budget_minutes."
            ),
            why=(
                "The route stage crossed its 60-minute job bound on five of the last "
                "eight runs. Measured on ubuntu-latest 2026-08-24 (run 32742672105): "
                "fixed cost 47 s, stage 3155 s, 149 items at a mean of 21.0 s. So "
                "per-item inference owns the time, not model load. The router had no "
                "request budget of its own and borrowed run.shard_timeout_minutes - "
                "150 minutes against a 60-minute job, which can never fire. lead_words "
                "was a literal on the hot path and is most of each request's prefill. "
                "The route budget warns before the bound instead of after it. All three "
                "are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T21:40",
            change="Added ui.items_per_topic and console.failure_list_max.",
            why=(
                "Both are the same defect at two altitudes: a page that renders every "
                "row it holds. 586 items in one queue gave the day page a first screen "
                "chosen by whichever topic id sorts first, and 800 failed rows measured "
                "7824 pixels and pushed the compression chart off the operator's reach. "
                "How many to show first is a tuning decision, not a literal (Rule #6). "
                "Both are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added collect.blocked_url_markers, empty by default.",
            why=(
                "A working news feed syndicated affiliate credit-card pages, which "
                "published at 0.92 to 0.95 faithfulness and banded high. The summaries "
                "were faithful - that is the point. Short declarative marketing prose is "
                "trivially entailed, so no faithfulness threshold detects it at any cut "
                "and raising the bar rewards it. The control has to sit where the item is "
                "collected, before anything is spent on it (Rule #2)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:50",
            change=(
                "Added the brief summary band, lowered evaluation.summary_words_min to 25, "
                "lowered extract.min_source_words to its derived value, added "
                "evaluation.brief_compression_ceiling, and added line-shape prose knobs."
            ),
            why=(
                "Short sources should publish with an honest brief instead of being padded "
                "or dropped. The old word gate forced the decoder to keep writing on a "
                "small source, which made invention more likely."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:40",
            change="Added the console block for the interactive telemetry viewport.",
            why=(
                "The console now lets the operator pan and zoom over the published "
                "item-health projection, so the default window, pan step, zoom factor, "
                "minimum denominator and chart size are tunable config values (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:35",
            change="Added llama-server runtime-sweep knobs to models.inference.",
            why=(
                "The runtime sweep must change one measured flag at a time through config, "
                "not through workflow literals. The startup_warmup default matches the "
                "current digest workflow, so the fingerprint input describes the server "
                "that actually runs."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change=(
                "Added extract prose-shape, enforcement and paywall-marker knobs; changed "
                "extract.min_source_words to a brief-tier threshold."
            ),
            why=(
                "Extraction now records short or list-shaped pages instead of dropping "
                "them by length, while publisher-declared paywalls still stop publication. "
                "The new thresholds and switches are tunable config values (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:52",
            change="Added models.inference.request_timeout_minutes.",
            why=(
                "One hung summarizer request was using the whole shard timeout, so a "
                "single bad item could burn 150 minutes and hide the cause. The new "
                "per-request budget is sized from the measured worst 8B long article "
                "plus a cold prompt prefix, doubled, while run.shard_timeout_minutes "
                "stays the outer bound. Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:41",
            change="Added evaluation.lead_coverage_min.",
            why=(
                "Lead coverage now caps a high confidence band at medium. The threshold "
                "is a tunable band input, so it belongs in config rather than in score.py "
                "(Rule #6). Additive - an older config still validates through the "
                "schema default."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T16:00",
            change="Added ui.read_mark_days.",
            why=(
                "Read marks were one flat list of item ids that never expired, so an id "
                "reused on a later day greyed out an article the reader had never "
                "opened, and the store grew for ever. Marks are now held per digest "
                "date and pruned to the newest days this number allows. Additive - an "
                "older config still validates, and the browser drops the old flat list "
                "on sight because there is no honest way to tell which day those ids "
                "belonged to."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T15:00",
            change="Added summarize.title_words_min and summarize.title_words_max.",
            why=(
                "The digest published the source's own headline, which is written to "
                "win a click rather than to say what happened. The summarizer now "
                "writes the title too, and the range it is asked for is a knob like "
                "every other length in this block (Rule #6). Additive - an older "
                "config still validates, and an item whose title misses the range "
                "falls back to the source's."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Added the summarize block: length bands, key-point range and quote cap.",
            why=(
                "The lengths the prompt asks for were literals inside the prompt text, "
                "where no schema could see them and nothing checked them against the "
                "range the pipeline accepts (Rule #6). They are bands rather than "
                "one range because a release note and a long read asked for the same "
                "number of words gives a padded summary of the first and a thin one of "
                "the second. Moving them here also puts them inside the prompt string "
                "the fingerprint hashes, so changing what we ask for now re-summarizes "
                "rather than reusing a cached reply written under the old ask. "
                "Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change=(
                "Replaced run.item_cap_per_day with run.safety_ceiling_per_run. Added "
                "collect.recency_weight, collect.recency_half_life_hours, "
                "collect.max_future_hours and collect.seen_window_days. Raised "
                "inference.max_output_tokens to 900."
            ),
            why=(
                "A daily cap decided the size of the day; supply and the ranking should. "
                "The ceiling that remains is a crash guard against a mis-parsed feed. "
                "Recency is a bonus rather than a cutoff so a strong older item is never "
                "dropped for a weak new one. The token stop is labelled as the crash "
                "guard it always was, and sized so the prompt sets the length."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T09:00",
            change="Removed collect.min_feeds_floor.",
            why=(
                "Nothing read it. The floor a vertical is actually held to is its own "
                "min_feeds in taxonomy.json, so a second number calling itself the "
                "default described a mechanism that does not exist."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Added the visuals block.",
            why=(
                "Routing needs its bounds and its enabled-kinds gate in config before the "
                "router may choose a kind. Additive - an older payload still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T06:00",
            change="Added the ui block.",
            why="The published surface's knobs need a home before a component reads one.",
        ),
        ChangelogEntry(
            version="2026-08-21T05:00",
            change="Added collect.max_per_source.",
            why=(
                "The first live run planned a whole vertical from one blog: with no story "
                "carried twice, the tie-break decided the day and one source won it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T03:00",
            change=(
                "Replaced evaluation.compression_min/max with summary_words_min/max; added "
                "extract.min_source_words and extract.boilerplate_ratio_max."
            ),
            why=(
                "At a fixed output budget a compression ratio measures the article's length, "
                "not the summary's quality - it would have flagged every short article "
                "forever. Absolute word bounds detect the two real failures directly."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: run, collect, extract, models, evaluation, drift, retention.",
            why="Contracts before logic - no stage may reach for a tunable that has no home.",
        ),
    )

    run: RunConfig = Field(default_factory=RunConfig)
    collect: CollectConfig = Field(default_factory=CollectConfig)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    models: ModelsConfig
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    assist: AssistConfig = Field(default_factory=AssistConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    page_weight: PageWeightConfig = Field(default_factory=PageWeightConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="after")
    def _the_ask_sits_inside_the_gate(self) -> Self:
        """The prompt may ask for less than we accept. It may never ask for more.

        An operator editing one block cannot see the other, and the failure is
        silent in the worst way: the prompt asks for 300 words, the model
        complies, and the gate drops a correct summary every single run. So the
        two blocks are checked together here, where both are in scope.
        """
        for band in self.summarize.bands:
            if band.target_words_min < self.evaluation.summary_words_min:
                raise ValueError(
                    f"summarize band at {band.min_source_words} words asks for a summary "
                    "shorter than evaluation.summary_words_min accepts"
                )
            if band.target_words_max > self.evaluation.summary_words_max:
                raise ValueError(
                    f"summarize band at {band.min_source_words} words asks for a summary "
                    "longer than evaluation.summary_words_max accepts"
                )
        brief_target = self.summarize.bands[0].target_words_min
        derived_floor = math.ceil(brief_target / self.evaluation.brief_compression_ceiling)
        if self.extract.min_source_words != derived_floor:
            raise ValueError(
                "extract.min_source_words must equal summarize.bands[0].target_words_min "
                "divided by evaluation.brief_compression_ceiling"
            )
        return self
