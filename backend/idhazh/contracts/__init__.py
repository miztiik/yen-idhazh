"""Every persisted shape, as a Pydantic model.

This package is the bottom of the dependency graph and MUST NOT import any other
subpackage of `idhazh` (CLAUDE.md section 4). A contract that imports a stage is
a contract that cannot be loaded by a test of that stage.
"""

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    StalePayloadError,
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
from idhazh.contracts.digest_view import (
    DigestCoverage,
    DigestView,
    DigestViewItem,
    DigestViewVisual,
)
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.fingerprint import PipelineInputs
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
from idhazh.contracts.sources import FeedDef, SalienceFeedDef, SourceForm, Sources
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import (
    EventDef,
    LensDef,
    Lifecycled,
    LifecycleStatus,
    SourceTier,
    Taxonomy,
    VerticalDef,
)
from idhazh.contracts.validation_row import ValidationRow, ValidationVerdict
from idhazh.contracts.visual_decision import VisualDecision, VisualKind, VisualState
from idhazh.contracts.watchlist import EdgarPolicy, EntityDef, EntityFeed, Watchlist

__all__ = [
    "AppConfig",
    "Article",
    "ArticleStatus",
    "ChangelogEntry",
    "ConfidenceBand",
    "ConfigDigest",
    "Contract",
    "DigestCoverage",
    "DigestDay",
    "DigestItem",
    "DigestRunRef",
    "DigestVerticalRef",
    "DigestView",
    "DigestViewItem",
    "DigestViewVisual",
    "DigestVisual",
    "EdgarPolicy",
    "EntityDef",
    "EntityFeed",
    "EvalRow",
    "EventDef",
    "FeedDef",
    "LensDef",
    "LifecycleStatus",
    "Lifecycled",
    "Model",
    "ModelRole",
    "ModelUse",
    "PipelineInputs",
    "PlannedItem",
    "RunManifest",
    "RunPlan",
    "RunRecord",
    "RunStatus",
    "SalienceFeedDef",
    "SourceForm",
    "SourceTier",
    "Sources",
    "StalePayloadError",
    "Summary",
    "SummaryStatus",
    "Taxonomy",
    "ValidationRow",
    "ValidationVerdict",
    "VerticalCount",
    "VerticalDef",
    "VerticalPlan",
    "VisualDecision",
    "VisualKind",
    "VisualState",
    "Watchlist",
    "canonical_json",
    "derive_output_digest",
    "derive_url_key",
]
