"""Does a trial run keep its ledgers out of the published series, and get cleaned up?"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh import ledger, retention
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.stages.prune_state import _prune_trial_shards, _trial_roots

pytestmark = pytest.mark.contract

TRIAL = "trial-runs"


def a_tree(root: Path, *, days: dict[str, list[str]]) -> Path:
    """`state/<trial>/<ledger>/<yyyy>/<mm>/<dd>.csv`, the shape every ledger writes."""
    for ledger_name, dates in days.items():
        for written in dates:
            day = root / TRIAL / ledger_name / written[:4] / written[5:7] / f"{written[8:10]}.csv"
            day.parent.mkdir(parents=True, exist_ok=True)
            day.write_text("version,date\n2026-09-15," + written + "\n", encoding="utf-8")
    return root


def a_store_day(root: Path, *, written: str) -> Path:
    """One declared store's day file, beside the trial roots and not one of them."""
    day = root / ledger.ITEM_HEALTH_DIRNAME / written[:4] / written[5:7] / f"{written[8:10]}.csv"
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("version,date\n2026-09-15," + written + "\n", encoding="utf-8")
    return day


def test_a_trial_day_past_the_window_goes_and_a_recent_one_stays(tmp_path: Path) -> None:
    """The window is what the knob says, counted from the day it is handed.

    Ninety days is the artifact retention this project already uses, so a
    trial's rows outlive the run's own artifacts by nothing.
    """
    state = a_tree(
        tmp_path / "state",
        days={"seen": ["2026-01-01", "2026-09-10"], "item-health": ["2026-02-01"]},
    )

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert sorted(result.deleted) == [
        "state/trial-runs/item-health/2026/02/01.csv",
        "state/trial-runs/seen/2026/01/01.csv",
    ]
    assert result.kept == 1
    assert (state / TRIAL / "seen" / "2026" / "09" / "10.csv").is_file()


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    """The list is the deliverable. It is what a person reads before switching it on."""
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90, dry_run=True
    )

    assert result.deleted == ("state/trial-runs/seen/2026/01/01.csv",)
    assert (state / TRIAL / "seen" / "2026" / "01" / "01.csv").is_file()


def test_a_day_dated_ahead_of_today_is_kept(tmp_path: Path) -> None:
    """A run handed an older `--date` must not delete the day the next one appends to.

    The same property `prune_seen` and `prune_traces` hold, restated here
    because this prune walks a tree the others do not.
    """
    state = a_tree(tmp_path / "state", days={"seen": ["2026-12-25"]})

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert result.deleted == ()
    assert result.kept == 1


def test_a_tree_that_was_never_written_is_not_an_error(tmp_path: Path) -> None:
    """Most days there is no trial tree at all, and that is the quiet answer."""
    result = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert not result.changed
    assert result.kept == 0


def test_the_segments_and_traces_a_trial_run_really_writes_are_read(tmp_path: Path) -> None:
    """The two shapes `work` leaves under a trial root, neither of them a day file.

    A trial run writes `segments/<ledger>/<run-id>-...csv` two levels down and a
    trace whose name is a day plus a run and a shard. The walk used to hand each
    child of the root to a day-tree reader, which raises on both - so the first
    prune pointed at a real trial root would have ended the nightly job rather
    than emptying anything.
    """
    root = tmp_path / "state" / TRIAL
    old_segment = root / "segments" / "span-rollup" / "2026-01-01-40000000001-1-work-00.csv"
    new_segment = root / "segments" / "span-rollup" / "2026-09-10-40000000002-1-work-00.csv"
    old_trace = root / "traces" / "2026" / "01" / "01-40000000001-00.jsonl"
    for path in (old_segment, new_segment, old_trace):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    result = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert sorted(result.deleted) == [
        "state/trial-runs/segments/span-rollup/2026-01-01-40000000001-1-work-00.csv",
        "state/trial-runs/traces/2026/01/01-40000000001-00.jsonl",
    ]
    assert new_segment.is_file()


def test_a_file_whose_path_spells_no_day_is_kept_rather_than_refused(tmp_path: Path) -> None:
    """Nothing reads a trial root, so an odd name must not cost the whole prune.

    A day tree refuses a stray because a reader that skipped one would start
    missing rows. Here the only reader is the deletion itself, and a refusal
    would end a nightly pass over every other ledger for one file nobody wanted.
    """
    stray = tmp_path / "state" / TRIAL / "segments" / "span-rollup" / "notes.txt"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("what is this\n", encoding="utf-8")

    result = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert result.deleted == ()
    assert result.kept == 1
    assert stray.is_file()


def test_an_emptied_trial_root_is_taken_away_with_its_last_file(tmp_path: Path) -> None:
    """Without this the child count under `state/` only ever rises (Guardrail #12).

    A trial that ran once would leave a directory for ever, and a reader opening
    `state/` could not tell an empty husk from a tree still being written.
    """
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})
    before = len(list(state.iterdir()))

    retention.prune_trial_state(state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90)

    assert not (state / TRIAL).exists()
    assert len(list(state.iterdir())) == before - 1


def test_a_month_head_is_kept_until_its_whole_month_has_aged_out(tmp_path: Path) -> None:
    """A month has no day of its own, so it takes the last day it could hold."""
    head = tmp_path / "state" / TRIAL / "span-rollup" / "2026-06.csv"
    head.parent.mkdir(parents=True, exist_ok=True)
    head.write_text("version\n2026-09-15\n", encoding="utf-8")

    inside = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )
    assert inside.deleted == ()

    outside = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 30), within_days=90
    )
    assert outside.deleted == ("state/trial-runs/span-rollup/2026-06.csv",)


def test_the_production_config_prunes_a_trial_root_it_was_never_told_about(
    tmp_path: Path,
) -> None:
    """The Oracle, and the defect it replaces.

    `config/idhazh.json` leaves `run.trial_state_dirname` null and cannot do
    otherwise - `cli` redirects `STATE_ROOT` into that directory on every stage
    but this one, so a production value would move the daily pipeline's own
    ledgers into the trial root. The prune used to read that knob and return at
    once, so `state/pipeline-tests/` had never been touched by anything.

    Nothing here names the trial. The roots come off the tree.
    """
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})
    store_day = a_store_day(state, written="2026-01-01")
    before = len(list(state.iterdir()))

    removed = _prune_trial_shards(state, RetentionConfig(), date(2026, 9, 15), dry_run=False)

    assert removed == ["state/trial-runs/seen/2026/01/01.csv"]
    assert not (state / TRIAL).exists()
    assert len(list(state.iterdir())) == before - 1
    assert store_day.is_file(), "a declared store is not a trial root, however old its rows"


def test_every_declared_store_is_subtracted_from_the_trial_roots(tmp_path: Path) -> None:
    """What holds `STORE_DIRNAMES` honest.

    A store missing from the set reads as a trial root, and its files would then
    be aged out against a window that is not its own.
    """
    state = tmp_path / "state"
    for name in sorted(ledger.STORE_DIRNAMES):
        (state / name).mkdir(parents=True)
    (state / TRIAL).mkdir()

    assert _trial_roots(state) == [TRIAL]


def test_a_state_tree_that_does_not_exist_yet_names_no_trial_root(tmp_path: Path) -> None:
    """A fresh clone that has never run is not an error."""
    assert _trial_roots(tmp_path / "state") == []
