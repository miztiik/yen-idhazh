"""The tunable knobs (`config/idhazh.json`).

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache, the 1 GB published site - are deliberately absent: they are properties of
the platform, and making them editable would invite raising the budget instead
of simplifying the feature (Holy Law #2).

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model, Sha256, Slug
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
        default=200,
        ge=1,
        description=(
            "A crash guard, not an editorial choice. Supply and the ranking decide how "
            "big a day is; this only stops a mis-parsed feed from publishing hundreds "
            "of items in one run. A normal day never reaches it."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description="URLs per worker VM. Set by measured model-load amortization, not by taste.",
    )
    max_parallel: int = Field(default=4, ge=1)
    shard_timeout_minutes: int = Field(
        default=150,
        ge=1,
        description="Derived from the WORST-case article, not the blended figure.",
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


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
    )
    min_source_words: int = Field(
        default=120,
        ge=1,
        description="Below this the item is not summarized at all. Page furniture is short.",
    )
    boilerplate_ratio_max: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="Share of an item's lines also seen on sibling items from the same host.",
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


class ModelsConfig(Model):
    summarize: ModelRef
    route: ModelRef
    inference: InferenceConfig = Field(default_factory=InferenceConfig)


class EvaluationConfig(Model):
    band_high_min: float = Field(default=0.80, ge=0.0, le=1.0)
    band_medium_min: float = Field(default=0.50, ge=0.0, le=1.0)
    truncation_gap_max: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Score gap that flags a truncation artifact rather than a hallucination.",
    )
    summary_words_min: int = Field(
        default=40,
        ge=1,
        description=(
            "Below this it is a headline, not a summary. Set under what the prompt asks "
            "for: the prompt is a request, and dropping an item for missing it by two "
            "words loses a story to a rounding error."
        ),
    )
    summary_words_max: int = Field(
        default=250, ge=1, description="Above this it is a copy. Absolute, not a ratio."
    )
    spot_checks_per_week: int = Field(default=10, ge=0)
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
        description="Opens an issue above this. The platform's hard ceiling is 1 GB.",
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
        default_factory=lambda: [VisualKind.CHART, VisualKind.DIAGRAM],
        description="Kinds the router may choose. `none` is always available and never listed.",
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
    repo_url: str = Field(default="https://github.com/miztiik/yen-idhazh", min_length=1)
    site_title: str = Field(default="yen-idhazh", min_length=1)
    tagline: str = Field(
        default="A daily digest that checks its own work.",
        min_length=1,
    )


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
