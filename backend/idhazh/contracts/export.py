"""Generate `schemas/` from the Pydantic models.

One-way and never reversed: the models are hand-written, the schemas are not.
CI regenerates and fails on any diff, which is what makes "never hand-edit a
generated artifact" a control rather than an aspiration.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.corpus import CorpusMeta, CorpusRow
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.evidence import EvidenceItem
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.fingerprint import FingerprintRow
from idhazh.contracts.icon_manifest import IconManifest
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.label_row import LabelRow
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.qualification import QualificationReport, QualificationShard
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.score_archive import ScoreArchive
from idhazh.contracts.search_index import SearchIndex
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.source_health_view import SourceHealthView
from idhazh.contracts.sources import Sources
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow
from idhazh.contracts.validation_row import ValidationRow
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.contracts.watchlist import Watchlist

CONTRACTS: Final[tuple[type[Contract], ...]] = (
    AppConfig,
    AppearanceConfig,
    Article,
    CorpusMeta,
    CorpusRow,
    DigestDay,
    DigestView,
    EvalRow,
    EvidenceItem,
    FeedHealthRow,
    FeedRetirementRow,
    FingerprintRow,
    IconManifest,
    ItemHealthRow,
    LabelRow,
    PublicTelemetryRow,
    QualificationReport,
    QualificationShard,
    VisualDecision,
    RunManifest,
    PublishedRow,
    RunPlan,
    RuntimeCountersRow,
    ScoreArchive,
    SearchIndex,
    SeenRow,
    SourceHealthView,
    Sources,
    SpanRollupRow,
    Summary,
    Taxonomy,
    TelemetryAggregateRow,
    ValidationRow,
    VisualPruneRow,
    Watchlist,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
DEFAULT_SCHEMAS_DIR: Final = REPO_ROOT / "schemas"


def export(target: Path) -> list[Path]:
    """Write one schema file per contract. LF regardless of the host's line endings."""
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for contract in CONTRACTS:
        path = target / contract.schema_filename()
        path.write_text(contract.schema_text(), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def expected_filenames() -> set[str]:
    return {contract.schema_filename() for contract in CONTRACTS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_SCHEMAS_DIR)
    args = parser.parse_args()
    for path in export(args.out):
        print(path.relative_to(REPO_ROOT).as_posix())


if __name__ == "__main__":
    main()
