"""Every persisted shape, as a Pydantic model.

This package is the bottom of the dependency graph and MUST NOT import any other
subpackage of `idhazh` (CLAUDE.md section 4). A contract that imports a stage is
a contract that cannot be loaded by a test of that stage.
"""

from idhazh.contracts.app_config import (
    AppConfig,
    CollectConfig,
    DriftConfig,
    EvaluationConfig,
    ExtractConfig,
    InferenceConfig,
    LoggingConfig,
    LogLevel,
    ModelRef,
    ModelsConfig,
    RetentionConfig,
    RunConfig,
    TierWeights,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    canonical_json,
    derive_output_digest,
    derive_url_key,
)
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.fingerprint import FingerprintRow, PipelineInputs
from idhazh.contracts.golden import GoldenArticle, GoldenSet
from idhazh.contracts.route import Route, SpecFormat, VisualKind, VisualState
from idhazh.contracts.run_manifest import (
    ConfigDigest,
    ModelRole,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
    VerticalCount,
)
from idhazh.contracts.run_plan import PlannedItem, RunPlan, VerticalPlan
from idhazh.contracts.sources import FeedDef, SalienceFeedDef, Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import (
    EventDef,
    EventType,
    LensDef,
    LensId,
    Lifecycled,
    LifecycleStatus,
    SourceTier,
    Taxonomy,
    VerticalDef,
)
from idhazh.contracts.validation_row import ValidationRow, ValidationVerdict
from idhazh.contracts.watchlist import EdgarPolicy, EntityDef, EntityFeed, Watchlist

__all__ = [
    "AppConfig",
    "Article",
    "ArticleStatus",
    "ChangelogEntry",
    "CollectConfig",
    "ConfidenceBand",
    "ConfigDigest",
    "Contract",
    "DigestDay",
    "DigestItem",
    "DigestRunRef",
    "DigestVerticalRef",
    "DigestVisual",
    "DriftConfig",
    "EdgarPolicy",
    "EntityDef",
    "EntityFeed",
    "EvalRow",
    "EvaluationConfig",
    "EventDef",
    "EventType",
    "ExtractConfig",
    "FeedDef",
    "FingerprintRow",
    "GoldenArticle",
    "GoldenSet",
    "InferenceConfig",
    "LensDef",
    "LensId",
    "LifecycleStatus",
    "Lifecycled",
    "LogLevel",
    "LoggingConfig",
    "Model",
    "ModelRef",
    "ModelRole",
    "ModelUse",
    "ModelsConfig",
    "PipelineInputs",
    "PlannedItem",
    "RetentionConfig",
    "Route",
    "RunConfig",
    "RunManifest",
    "RunPlan",
    "RunRecord",
    "RunStatus",
    "SalienceFeedDef",
    "SourceTier",
    "Sources",
    "SpecFormat",
    "Summary",
    "SummaryStatus",
    "Taxonomy",
    "TierWeights",
    "ValidationRow",
    "ValidationVerdict",
    "VerticalCount",
    "VerticalDef",
    "VerticalPlan",
    "VisualKind",
    "VisualState",
    "Watchlist",
    "canonical_json",
    "derive_output_digest",
    "derive_url_key",
]
