"""Real Git coverage for planner period compact sibling selection."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.gardener_events import CompactionStep
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing, parse_tree, sizes_of
from idhazh.gardener.tasks._compact_tree import CompactTree

pytestmark = pytest.mark.contract

PLANNER_LEDGERS: Final = (
    LedgerName.FEED_INGEST_PLAN_DISCOVERED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_SELECTED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_REJECTED_ARTICLES,
    LedgerName.FEED_INGEST_PLAN_FEED_HEALTH_STATE,
    LedgerName.FEED_INGEST_PLAN_PLAN_RUNS,
)

RAW_FIXTURE: Final = b"recorded-planner-raw-fixture"
RAW_FILE_NAME: Final = "00000000-0000-4000-8000-000000000001.parquet"


def git(repo: Path, *args: str) -> str:
    """Run Git with this fixture repository's identity and no developer config."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=os.environ | {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
        },
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def write_indexes(root: Path, which: LedgerName) -> list[Path]:
    """Write the three real compact index shapes for one fixture repository."""
    state_dir = root / ledger.STATE_DIRNAME
    written: list[Path] = []
    for period in Period:
        path = ledger.compact_index_path(state_dir, which, period)
        path.parent.mkdir(parents=True, exist_ok=True)
        held = CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=period,
            entries=[],
        )
        path.write_bytes(held.to_json().encode("ascii"))
        written.append(path)
    return written


def commit_fixture(
    root: Path,
    which: LedgerName,
    *,
    sibling_formats: Sequence[Format] = (),
) -> tuple[list[Path], Path]:
    """Seed a real Git fixture repository with indexes, a raw file and named siblings."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "Planner Fixture")
    git(root, "config", "user.email", "planner-fixture@example.invalid")
    indexes = write_indexes(root, which)
    raw_path = (
        ledger.raw_root(root / ledger.STATE_DIRNAME, which)
        / "2026"
        / "10"
        / "20"
        / RAW_FILE_NAME
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(RAW_FIXTURE)

    sibling_paths: list[Path] = []
    sibling_base = ledger.compact_path(
        root / ledger.STATE_DIRNAME,
        which,
        Period.MONTHLY,
        "2026-10",
    )
    for fmt in sibling_formats:
        sibling = sibling_base.with_suffix(f".{fmt.value}")
        sibling.parent.mkdir(parents=True, exist_ok=True)
        sibling.write_bytes(b"recorded-legacy-compact-sibling")
        sibling_paths.append(sibling)

    tracked = [
        *(path.relative_to(root).as_posix() for path in indexes),
        raw_path.relative_to(root).as_posix(),
        *(path.relative_to(root).as_posix() for path in sibling_paths),
    ]
    git(root, "add", "--", *tracked)
    git(root, "commit", "--quiet", "-m", "record planner compaction fixture")
    return indexes, raw_path


def commit_listing(
    root: Path,
    which: LedgerName,
) -> tuple[FileListing, list[list[str]]]:
    """Build a commit listing for a fixture tree and retain every widening request."""
    state_dir = root / ledger.STATE_DIRNAME
    folders = [
        ledger.raw_root(state_dir, which).relative_to(root).as_posix(),
        ledger.compact_folder(state_dir, which).relative_to(root).as_posix(),
    ]
    index_paths = [
        ledger.compact_index_path(state_dir, which, period).relative_to(root).as_posix()
        for period in Period
    ]
    initial_entries = parse_tree(
        git(root, "ls-tree", "-r", "-l", "-z", "HEAD", "--", *index_paths)
    )

    def lister(paths: Sequence[str]) -> dict[str, int]:
        entries = parse_tree(
            git(root, "ls-tree", "-r", "-l", "-z", "HEAD", "--", *paths)
        )
        return sizes_of(entries, {})

    asked: list[list[str]] = []
    listing = FileListing.from_commit(
        root,
        folders,
        initial_entries,
        {},
        paths=index_paths,
        widen=lambda paths: asked.append(list(paths)),
        lister=lister,
        budget=1,
    )
    return listing, asked


def tree_fixture(
    root: Path,
    which: LedgerName,
) -> tuple[CompactTree, FileListing, list[list[str]]]:
    """Create one real-Git compaction tree for a caller-level period test."""
    listing, asked = commit_listing(root, which)
    tree = CompactTree(
        state_dir=root / ledger.STATE_DIRNAME,
        ledger=which,
        listing=listing,
        daily={},
        monthly={},
        yearly={},
        raw_days=[],
    )
    return tree, listing, asked


@pytest.mark.parametrize("which", PLANNER_LEDGERS)
@pytest.mark.parametrize(
    ("period", "covers", "step", "reopened"),
    (
        (Period.DAILY, "2026-10-20", CompactionStep.PACK_DAYS, False),
        (Period.MONTHLY, "2026-10", CompactionStep.CLOSE_MONTHS, False),
        (Period.MONTHLY, "2026-10", CompactionStep.REOPEN_MONTHS, True),
        (Period.YEARLY, "2026", CompactionStep.PACK_YEARS, False),
    ),
    ids=("daily", "monthly", "reopened-month", "yearly"),
)
def test_real_git_caller_names_only_compact_siblings_the_commit_holds(
    tmp_path: Path,
    which: LedgerName,
    period: Period,
    covers: str,
    step: CompactionStep,
    reopened: bool,
) -> None:
    """A caller-level compact period stops at budget before reading absent siblings."""
    root = tmp_path / which.value
    _indexes, raw_path = commit_fixture(root, which)
    raw_path.unlink()
    tree, _listing, asked = tree_fixture(root, which)

    stop = tree.compact_planner_period(
        period,
        covers,
        step=step,
        most=100,
        reopened=reopened,
    )

    assert stop is not None
    assert asked == []

    if period is Period.DAILY:
        candidate_period, candidate_covers = Period.MONTHLY, "2026-10"
    elif period is Period.MONTHLY:
        candidate_period, candidate_covers = Period.MONTHLY, covers
    else:
        candidate_period, candidate_covers = Period.YEARLY, covers
    candidate = ledger.compact_path(
        tree.state_dir,
        which,
        candidate_period,
        candidate_covers,
        fmt=Format.PARQUET,
    )
    with pytest.raises(ValueError, match="is not a file the listing holds"):
        tree.listing.fetch(beside=[candidate])


@pytest.mark.parametrize("which", PLANNER_LEDGERS)
@pytest.mark.parametrize(
    "formats",
    (
        (Format.JSON,),
        (Format.PARQUET, Format.JSON),
    ),
    ids=("json-only", "parquet-and-json"),
)
def test_json_sibling_is_kept_as_an_explicit_candidate(
    tmp_path: Path,
    which: LedgerName,
    formats: tuple[Format, ...],
) -> None:
    """JSON is not guessed away when configured Parquet is not the sibling present."""
    root = tmp_path / which.value
    commit_fixture(root, which, sibling_formats=formats)
    tree, _listing, _asked = tree_fixture(root, which)
    tree.name_days(["2026-10-20"])

    held = tree._held_compact_siblings(
        (
            (Period.MONTHLY, "2026-10"),
            (Period.YEARLY, "2026"),
        )
    )

    expected = tuple(
        ledger.compact_path(
            tree.state_dir,
            which,
            Period.MONTHLY,
            "2026-10",
            fmt=fmt,
        )
        for fmt in formats
    )
    assert held[: len(expected)] == expected
    if Format.PARQUET not in formats:
        parquet = ledger.compact_path(
            tree.state_dir,
            which,
            Period.MONTHLY,
            "2026-10",
            fmt=Format.PARQUET,
        )
        assert parquet not in held
