"""Does planner compaction use exact local siblings without Git or a new download?"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.gardener_events import CompactionStep
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.ledger.planner_maintenance import maintain_period

from .._garden import planner_raw_fixture

pytestmark = pytest.mark.contract

PLANNER_LEDGERS: Final = (
    LedgerName.FEED_INGEST_PLAN_DISCOVERED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_SELECTED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_REJECTED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_FEED_HEALTH_STATE,
    LedgerName.FEED_INGEST_PLAN_PLAN_RUNS,
)


def fixture_tree(
    root: Path,
    which: LedgerName,
    *,
    sibling_formats: Sequence[Format] = (),
) -> tuple[CompactTree, Path]:
    """Use recorded native rows and the three existing scheduler indexes."""
    root.mkdir(parents=True, exist_ok=True)
    raw = planner_raw_fixture(root, which)
    state_dir = root / ledger.STATE_DIRNAME
    indexes = []
    for period in Period:
        path = ledger.compact_index_path(state_dir, which, period)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            CompactIndex(
                version=CompactIndex.schema_version(),
                ledger=which,
                period=period,
                entries=[],
            ).to_json(),
            encoding="ascii",
        )
        indexes.append(path)
    if Format.PARQUET in sibling_formats:
        result = maintain_period(root, which, "monthly", "2026-10", max_raw_files_per_period=100)
        assert (
            result.status == "written"
            and result.target_path is not None
            and result.data is not None
        )
        result.target_path.parent.mkdir(parents=True, exist_ok=True)
        result.target_path.write_bytes(result.data)
    if Format.JSON in sibling_formats:
        path = ledger.compact_path(state_dir, which, Period.MONTHLY, "2026-10", fmt=Format.JSON)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="ascii")
    folders = [
        ledger.raw_root(state_dir, which).relative_to(root).as_posix(),
        ledger.compact_folder(state_dir, which).relative_to(root).as_posix(),
    ]
    listing = FileListing.from_disk(root, folders, paths=indexes, budget=1)
    tree = CompactTree(
        state_dir=state_dir,
        ledger=which,
        listing=listing,
        daily={},
        monthly={},
        yearly={},
        raw_days=[],
    )
    return tree, raw


@pytest.mark.parametrize("which", PLANNER_LEDGERS)
@pytest.mark.parametrize(
    ("period", "covers", "step", "reopened"),
    (
        (Period.DAILY, "2026-10-21", CompactionStep.PACK_DAYS, False),
        (Period.MONTHLY, "2026-10", CompactionStep.CLOSE_MONTHS, False),
        (Period.MONTHLY, "2026-10", CompactionStep.REOPEN_MONTHS, True),
        (Period.YEARLY, "2026", CompactionStep.PACK_YEARS, False),
    ),
    ids=("daily", "monthly", "reopened-month", "yearly"),
)
def test_file_only_caller_compacts_recorded_native_rows_without_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    which: LedgerName,
    period: Period,
    covers: str,
    step: CompactionStep,
    reopened: bool,
) -> None:
    tree, raw = fixture_tree(tmp_path / which.value, which)
    bun = shutil.which("bun")
    assert bun is not None
    monkeypatch.setenv("PATH", str(Path(bun).parent))
    assert shutil.which("git") is None
    stop = tree.compact_planner_period(period, covers, step=step, most=100, reopened=reopened)
    assert stop is None
    target = ledger.compact_path(tree.state_dir, which, period, covers, fmt=Format.PARQUET)
    writes = [change for change in tree.changes if change.data is not None]
    assert len(writes) == 1 and writes[0].path == target
    assert writes[0].data is not None
    assert writes[0].data[:4] == b"PAR1" and writes[0].data[-4:] == b"PAR1"
    assert {change.path for change in tree.changes if change.data is None} == {raw}
    assert tree.entries(period)[covers].rows == 1
    downloaded = tree.listing.downloaded()
    assert downloaded is not None and set(downloaded.values()) == {0}
    assert raw.is_file(), "planning changes must not delete input before the pass applies"


@pytest.mark.parametrize("which", PLANNER_LEDGERS)
@pytest.mark.parametrize(
    "formats",
    ((Format.JSON,), (Format.PARQUET, Format.JSON)),
    ids=("json-only", "parquet-and-json"),
)
def test_json_sibling_is_kept_as_an_explicit_local_candidate(
    tmp_path: Path,
    which: LedgerName,
    formats: tuple[Format, ...],
) -> None:
    tree, _raw = fixture_tree(tmp_path / which.value, which, sibling_formats=formats)
    tree.name_days(["2026-10-21"])
    held = tree._held_compact_siblings(
        ((Period.MONTHLY, "2026-10"), (Period.YEARLY, "2026")),
    )
    assert held == tuple(
        ledger.compact_path(tree.state_dir, which, Period.MONTHLY, "2026-10", fmt=fmt)
        for fmt in formats
    )
