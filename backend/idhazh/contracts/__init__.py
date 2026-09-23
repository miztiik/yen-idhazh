"""Every persisted shape, as a Pydantic model.

This package is the bottom of the dependency graph and MUST NOT import any other
subpackage of `idhazh` (CLAUDE.md section 4). A contract that imports a stage is
a contract that cannot be loaded by a test of that stage.

`CONTRACTS` below is the registry: every top-level persisted document this
project writes. It is what a check over all of them iterates - the stamped read
boundary, the fixture map, the changelog shape. A shape that is not on it is not
a document a run persists.
"""

from typing import Final

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
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
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.console_band import ConsoleBand
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.corpus import CorpusMeta, CorpusRow
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.day_validation import DayValidationReceipt
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.digest_view import (
    DigestCoverage,
    DigestView,
    DigestViewItem,
    DigestViewVisual,
)
from idhazh.contracts.element import ElementTable
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.evidence import EvidenceItem
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.icon_manifest import IconManifest
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.label_row import LabelRow
from idhazh.contracts.machine_panels import MachinePanels
from idhazh.contracts.machine_shard import MachineShardRow
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.contracts.public_run_day import PublicRunDay
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.qualification import (
    QualificationReport,
    QualificationSamples,
    QualificationShard,
)
from idhazh.contracts.reference_dataset import (
    ReferenceCollectionMetadata,
    ReferenceDatasetLocalConfig,
    ReferenceDatasetRow,
    ReferenceExtractionRow,
    ReferenceManifestRow,
    ReferenceSelectionRow,
)
from idhazh.contracts.review_queue import ReviewQueue
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
from idhazh.contracts.run_timeline import RunTimelineRow
from idhazh.contracts.score_archive import ScoreArchive
from idhazh.contracts.search_index import SearchIndex
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.contracts.sources import FeedDef, SalienceFeedDef, SourceForm, Sources
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
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
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.contracts.validation_row import ValidationRow, ValidationVerdict
from idhazh.contracts.visual import VisualPlan
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import VisualDecision, VisualKind, VisualState
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.contracts.visual_telemetry import VisualAggregateRow, VisualAttemptRow
from idhazh.contracts.watchlist import EdgarPolicy, EntityDef, EntityFeed, Watchlist

#: Every top-level persisted document, and the whole of them.
#:
#: **A configuration file this project authors is not on this list.**
#: `ModelsConfig` is the shape of `config/models/<name>.json`, which nothing but
#: this repository writes and nothing but this repository reads, so a registry of
#: persisted documents has nothing to do with it (Guardrail #3, owner ruling
#: 2026-09-21).
CONTRACTS: Final[tuple[type[Contract], ...]] = (
    AppConfig,
    AppearanceConfig,
    Article,
    CollectionPruneRow,
    ConsoleBand,
    ContentSimilarityJudgeMetrics,
    CorpusMeta,
    CorpusRow,
    CouncilShardOutcome,
    CounterfactualScoreRow,
    DayMetrics,
    DayValidationReceipt,
    DigestDay,
    DigestRunFragment,
    DigestView,
    ElementTable,
    EvalRow,
    EvidenceItem,
    FeedHealthRow,
    FeedRetirementRow,
    FittedSimilarityThreshold,
    IconManifest,
    HostFingerprintRow,
    ItemHealthRow,
    LabelRow,
    MachinePanels,
    MachineShardRow,
    MergeLineHoldoutScore,
    ObservationIndexRow,
    PipelineTestsConfig,
    PublicRunDay,
    PublicTelemetryRow,
    QualificationReport,
    QualificationSamples,
    QualificationShard,
    ReferenceCollectionMetadata,
    ReferenceDatasetLocalConfig,
    ReferenceDatasetRow,
    ReferenceExtractionRow,
    ReferenceManifestRow,
    ReferenceSelectionRow,
    ReviewQueue,
    VisualDecision,
    RunManifest,
    PublishedRow,
    RunPlan,
    RunTimelineRow,
    ScoreArchive,
    SearchIndex,
    SeenRow,
    SimilarityHoldoutPair,
    SourceHealthView,
    Sources,
    SpanRollupRow,
    StorySimilarityDistribution,
    StorySimilarityPair,
    Summary,
    Taxonomy,
    TelemetryAggregateRow,
    ValidationRow,
    VisualAggregateRow,
    VisualAttemptRow,
    VisualData,
    VisualPlan,
    VisualPruneRow,
    Watchlist,
)

__all__ = [
    "CONTRACTS",
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
