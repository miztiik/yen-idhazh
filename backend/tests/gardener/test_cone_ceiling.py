"""Does a shard weigh the folders it owns at its commit, and say so when they pass the ceiling?

The weight is read the way a wake reads it - `git ls-tree -r -l` over the commit
by `backend/utilities/gardener_publish.py` - from a real repository whose owned
folders are built to weigh exactly the ceiling, one byte under it and one byte
over it. The ceiling is an alarm rather than a gate: a shard over it still runs
every task and lands its record, and then exits 1. What each row records is the
weight, so where a shard's bytes sit is answered by the record.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.gardener import runner
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED
from idhazh.site_weight import BYTES_PER_MB
from utilities import gardener_publish

from ._garden import GARDENER_FIXTURES, a_config, an_origin, git, on_origin, quiet_git
from ._garden import task_package as a_package

pytestmark = pytest.mark.slow

WAKE: Final = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-27-18012345678"
NAMES: Final = ("compact-gardener", "old-days", "rehearsal")

#: The ceiling the fixture config sets, so a tree that reaches it stays small.
CEILING_MB: Final = 1

#: What the three owned folders hold apart from the one whose size is varied.
AGED_DAY: Final = "state/old-days/2026-09-01.txt"
AGED_BYTES: Final = 600_000
KEEP: Final = "state/compact/gardener/.keep"
KEEP_BYTES: Final = 100
VARIED: Final = "state/rehearsal/2026-09-01.txt"


def a_garden_weighing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, total: int
) -> tuple[Path, Path, GardenerSettings]:
    """The runner's fixture garden in a real clone, its owned folders weighing `total` bytes."""
    quiet_git(tmp_path, monkeypatch)
    varied = total - AGED_BYTES - KEEP_BYTES
    origin, checkout = an_origin(
        tmp_path, {AGED_DAY: "a" * AGED_BYTES, KEEP: "k" * KEEP_BYTES, VARIED: "r" * varied}
    )
    config_dir = a_config(checkout, GARDENER_FIXTURES / "runner")
    knobs = json.loads((config_dir / "idhazh_gardener.json").read_text(encoding="utf-8"))
    (config_dir / "idhazh_gardener.json").write_text(
        json.dumps(knobs | {"max_cone_mb": CEILING_MB}), encoding="ascii"
    )
    return origin, checkout, config.load_gardener(config_dir)


def landed(
    checkout: Path, settings: GardenerSettings, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, list[CollectionPruneRow], list[str], str]:
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        NAMES,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        package=a_package("garden_tasks_ok", monkeypatch),
        clock=lambda: WAKE,
        say=said.append,
    )
    assert outcome.record is not None, "the shard wrote no record"
    rows = ledger.load([outcome.record], model=CollectionPruneRow)
    return outcome.exit_code, rows, said, outcome.record.relative_to(checkout).as_posix()


@pytest.mark.parametrize(
    ("offset", "code"), [(-1, EXIT_OK), (0, EXIT_OK), (1, EXIT_TASK_FAILED)]
)
def test_a_shard_at_under_and_over_its_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int, code: int
) -> None:
    """One byte either side of the line, and the line itself, which is inside it."""
    total = CEILING_MB * BYTES_PER_MB + offset
    origin, checkout, settings = a_garden_weighing(tmp_path, monkeypatch, total)

    exit_code, rows, said, record = landed(checkout, settings, monkeypatch)

    assert exit_code == code
    assert {row.task for row in rows} == set(NAMES), "a task did not run"
    assert {row.cone_bytes for row in rows} == {total}, "a row does not carry the shard's weight"
    assert on_origin(origin, record) is not None, "the record did not land"
    assert on_origin(origin, AGED_DAY) is None, "the live task's deletion did not land"
    over = [line for line in said if "over max_cone_mb" in line]
    if code == EXIT_OK:
        assert not over
        return
    (line,) = over
    assert line.startswith(f"shard 0: its owned folders weigh 1.0 MB ({total:,} bytes)")
    assert f"over max_cone_mb {CEILING_MB} in config/idhazh_gardener.json" in line
    assert (
        "The heaviest: state/old-days 0.6 MB, state/rehearsal 0.4 MB, "
        "state/compact/gardener 0.0 MB." in line
    )


def test_the_weight_is_read_off_the_commit_and_not_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file nobody committed weighs nothing, and a folder the commit lacks weighs 0."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {AGED_DAY: "a" * 10, KEEP: "k" * 3})
    (checkout / "state" / "old-days" / "never-committed.bin").write_bytes(b"x" * 5000)

    weights = gardener_publish.Checkout(checkout).cone_bytes(
        ["state/compact/gardener", "state/old-days", "state/rehearsal"]
    )

    assert weights == {"state/compact/gardener": 3, "state/old-days": 10, "state/rehearsal": 0}


def test_a_hand_run_reads_no_commit_and_records_no_weight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`idhazh gardener run-task` starts no process, so the weight is empty and nothing is checked."""
    _, checkout, settings = a_garden_weighing(
        tmp_path, monkeypatch, CEILING_MB * BYTES_PER_MB + 1
    )

    outcome = runner.run(
        NAMES,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        package=a_package("garden_tasks_ok", monkeypatch),
        clock=lambda: WAKE,
        say=lambda _: None,
    )

    assert outcome.exit_code == EXIT_OK
    assert outcome.record is not None
    rows = ledger.load([outcome.record], model=CollectionPruneRow)
    assert {row.cone_bytes for row in rows} == {None}


def test_the_heaviest_folders_are_named_heaviest_first_and_ties_by_name() -> None:
    weights = {"state/b": 3 * BYTES_PER_MB, "state/a": 3 * BYTES_PER_MB, "state/c": 1, "state/d": 2}

    said = runner.over_the_ceiling(weights, ceiling_mb=5, shard=4)

    assert said is not None and said.startswith("shard 4: its owned folders weigh 6.0 MB")
    assert "The heaviest: state/a 3.0 MB, state/b 3.0 MB, state/d 0.0 MB." in said
    assert runner.over_the_ceiling(weights, ceiling_mb=7, shard=4) is None
