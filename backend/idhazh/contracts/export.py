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
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.fingerprint import FingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.label_row import LabelRow
from idhazh.contracts.qualification import QualificationReport, QualificationShard
from idhazh.contracts.route import Route
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.search_index import SearchIndex
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.sources import Sources
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.validation_row import ValidationRow
from idhazh.contracts.watchlist import Watchlist

CONTRACTS: Final[tuple[type[Contract], ...]] = (
    AppConfig,
    Article,
    DigestDay,
    EvalRow,
    FeedHealthRow,
    FingerprintRow,
    ItemHealthRow,
    LabelRow,
    QualificationReport,
    QualificationShard,
    Route,
    RunManifest,
    PublishedRow,
    RunPlan,
    SearchIndex,
    SeenRow,
    Sources,
    Summary,
    Taxonomy,
    ValidationRow,
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
