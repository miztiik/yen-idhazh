"""Does the visual-prune task file the report the old pass filed, and only where it may?"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName

from ._oracle_tree import RUN_ID, TODAY, build
from ._task import GIT_SHA, declared, oracle, run_task

pytestmark = pytest.mark.contract

NAME: Final = "visual-prune"


def a_picture(root: Path, day: date, name: str = "ai-0000000001.json") -> Path:
    (folder,) = declared()[NAME].owns or []
    path = root / folder / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 1000)
    return path


@pytest.mark.parametrize("mode", ["dry", "live"])
def test_the_report_is_the_row_the_old_pass_filed_key_by_key(mode: str, tmp_path: Path) -> None:
    root = build(tmp_path / "checkout")
    recorded = oracle()["visual-prune-rows"][mode]

    run_task(NAME, root, dry_run=mode == "dry")

    (row,) = ledger.load_visual_prunes(root / ledger.STATE_DIRNAME)
    filed = row.model_dump(mode="json")
    assert sorted(filed) == sorted(recorded)
    assert {key: filed[key] for key in recorded} == recorded


def test_a_dry_run_files_its_report_through_the_ledger_door(tmp_path: Path) -> None:
    root = build(tmp_path / "checkout")

    outcome = run_task(NAME, root, dry_run=True)

    (held,) = ledger.list_raw_files(root / ledger.STATE_DIRNAME, LedgerName.VISUAL_PRUNES)
    assert outcome.written == ()
    assert outcome.appended == (held.path.relative_to(root).as_posix(),)
    assert held.envelope.covers == TODAY.isoformat()
    identity = held.envelope.identity
    assert (identity.run_id, identity.job, identity.git_sha) == (
        RUN_ID,
        ServerJob.RUN_TASKS,
        GIT_SHA,
    )
    assert identity.producer == "gardener.tasks.visual_prune"


def test_an_operator_range_reports_only_its_named_days(tmp_path: Path) -> None:
    root = build(tmp_path / "checkout")

    run_task(NAME, root, dry_run=True, period_range=("2026-10-20", "2026-10-20"))

    (row,) = ledger.load_visual_prunes(root / ledger.STATE_DIRNAME)
    assert (row.window_start, row.window_end, row.candidates_found) == (
        "2026-10-20",
        "2026-10-20",
        1,
    )


def test_a_second_pass_by_one_execution_is_one_report(tmp_path: Path) -> None:
    """One execution writing one work unit twice leaves one row: the reader keeps the later."""
    for n in range(3):
        a_picture(tmp_path, date(2026, 10, 20), f"p-{n:010d}.json")

    first = run_task(NAME, tmp_path, dry_run=False, max_deletes_per_run=2)
    second = run_task(NAME, tmp_path, dry_run=False, max_deletes_per_run=2)

    (row,) = ledger.load_visual_prunes(tmp_path / ledger.STATE_DIRNAME)
    assert (len(first.taken), len(second.taken)) == (2, 1)
    assert (row.deleted, row.skipped_by_fuse, row.candidates_found) == (1, 0, 1)


def test_the_report_names_what_the_fuse_held_back(tmp_path: Path) -> None:
    """The row the pass files says it, so no log line has to: two went, one waits for the fuse."""
    for n in range(3):
        a_picture(tmp_path, date(2026, 10, 20), f"p-{n:010d}.json")

    run_task(NAME, tmp_path, dry_run=False, max_deletes_per_run=2)

    (row,) = ledger.load_visual_prunes(tmp_path / ledger.STATE_DIRNAME)
    assert (row.deleted, row.skipped_by_fuse, row.max_deletes_per_run, row.bytes_reclaimed) == (
        2,
        1,
        2,
        2000,
    )


def test_a_tree_the_commit_does_not_hold_is_neither_walked_nor_reported(
    tmp_path: Path,
) -> None:
    outcome = run_task(NAME, tmp_path, dry_run=False)

    assert (outcome.seen, outcome.taken, outcome.appended) == (0, (), ())
    assert not (tmp_path / ledger.STATE_DIRNAME).exists()


def test_a_window_of_forever_takes_nothing_and_still_reports_the_backlog(
    tmp_path: Path,
) -> None:
    kept = a_picture(tmp_path, date(2026, 10, 20))

    outcome = run_task(NAME, tmp_path, dry_run=False, window={"unit": "forever"})

    (row,) = ledger.load_visual_prunes(tmp_path / ledger.STATE_DIRNAME)
    assert kept.exists()
    assert outcome.taken == ()
    assert (row.policy_months, row.cutoff_date, row.candidates_found) == (-1, None, 0)
    assert row.oldest_kept is None


@pytest.mark.parametrize(
    "changed",
    [
        {"owns": ["frontend/public/digest", "frontend/public/other"]},
        {"max_deletes_per_run": None},
    ],
)
def test_the_declaration_names_one_tree_and_a_fuse(
    changed: dict[str, Any], tmp_path: Path
) -> None:
    a_picture(tmp_path, date(2026, 10, 20))

    with pytest.raises(ValueError, match="owns exactly one folder and names a"):
        run_task(NAME, tmp_path, dry_run=False, **changed)
