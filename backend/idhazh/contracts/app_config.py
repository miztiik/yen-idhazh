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
    item_cap_per_day: int = Field(default=20, ge=1)
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
    min_feeds_floor: int = Field(
        default=25,
        ge=1,
        description="Default feed floor. A vertical may raise it; below it, nothing renders.",
    )
    quarantine_after_failures: int = Field(default=5, ge=1)
    watchlist_max_entities: int = Field(default=30, ge=1)
    tier_weights: TierWeights = Field(default_factory=TierWeights)
    repetition_weight: float = Field(default=1.0, ge=0.0)
    watchlist_bonus: float = Field(default=0.5, ge=0.0)
    front_page_bonus: float = Field(default=0.4, ge=0.0)


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
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
    max_output_tokens: int = Field(default=250, ge=1)


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
    compression_min: float = Field(default=0.03, gt=0.0, le=1.0)
    compression_max: float = Field(default=0.20, gt=0.0, le=1.0)
    spot_checks_per_week: int = Field(default=10, ge=0)
    golden_set_size: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _bands_and_ranges_are_ordered(self) -> Self:
        if self.band_medium_min >= self.band_high_min:
            raise ValueError("band_medium_min must sit below band_high_min")
        if self.compression_min >= self.compression_max:
            raise ValueError("compression_min must sit below compression_max")
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


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
