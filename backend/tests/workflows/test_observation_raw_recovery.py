"""Interrupted evaluation writers recover only their own named raw outputs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from idhazh import ledger
from idhazh.atomic_write import write_atomic
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_lookup import (
    ObservationBatch,
    ObservationLookupSettings,
    ObservationPreparation,
)
from idhazh.evals.lookup_nodes import node_path
from idhazh.evals.observation_batches import (
    file_batch,
    input_root,
    lookup_root,
    preparation_path,
    prepare,
    row_digest,
    save_batch,
)
from idhazh.evals.observation_lookup import ObservationLookup

from ._harness import _git, _run_commit_script
from .test_observation_publication import _batch, _commit_settings, _publication_origin

pytestmark = pytest.mark.workflow


def _crash_at_index(
    state: Path,
    batch: ObservationBatch,
    *,
    event: str = "call",
    boundary: str = "index",
    recovery: Path | None = None,
) -> None:
    save_batch(state, batch)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys\n"
            "from pathlib import Path\n"
            "from idhazh.contracts.observation_lookup import ObservationBatch, ObservationLookupSettings\n"
            "from idhazh.evals.observation_batches import file_batch, prepare\n"
            "def interrupt(frame, event, argument):\n"
            "    module = frame.f_globals.get('__name__', '')\n"
            "    function = frame.f_code.co_name\n"
            "    stop = (sys.argv[4] == 'index' and event == sys.argv[3]\n"
            "            and function == 'put' and module == 'idhazh.evals.observation_lookup')\n"
            "    stop |= (sys.argv[4] == 'before-publish' and event == 'call'\n"
            "             and function == 'publish_outputs' and module == 'idhazh.evals.observation_outputs')\n"
            "    stop |= (sys.argv[4] == 'partial-publish' and event == 'return'\n"
            "             and function == 'hardlink_to' and module.startswith('pathlib'))\n"
            "    stop |= (sys.argv[4] == 'partial-stage' and event == 'return'\n"
            "             and function == 'write_atomic_bytes' and module == 'idhazh.atomic_write'\n"
            "             and frame.f_back.f_code.co_name == 'persist')\n"
            "    if stop:\n"
            "        os._exit(73)\n"
            "    return interrupt\n"
            "state = Path(sys.argv[1])\n"
            "batch = ObservationBatch.read(Path(sys.argv[2]))\n"
            "sys.settrace(interrupt)\n"
            "if sys.argv[5]:\n"
            "    prepare(state, Path(sys.argv[5]), settings=ObservationLookupSettings())\n"
            "else:\n"
            "    file_batch(state, batch.rows, batch.identity, ObservationLookupSettings())\n",
            str(state),
            str(input_root(state) / "batches" / f"{batch.batch_id}.json"),
            event,
            boundary,
            str(recovery) if recovery is not None else "",
        ],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 73, result.stdout + result.stderr


def test_a_crash_before_index_does_not_leave_an_unrecorded_raw_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    batch = _batch(1)
    _crash_at_index(state, batch)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    assert len(list(raw.rglob("*.parquet"))) == 1

    assert file_batch(state, batch.rows, batch.identity, ObservationLookupSettings()) == 1

    assert len(list(raw.rglob("*.parquet"))) == 1
    assert len(ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)) == 1


@pytest.mark.parametrize("named_recovery", [False, True], ids=["job", "named-recovery"])
def test_receipted_output_paths_survive_a_crash_before_the_manifest_update(
    tmp_path: Path, named_recovery: bool
) -> None:
    state = tmp_path / "state"
    batch = _batch(1)
    manifest_path = preparation_path(state, batch.identity)
    recovery = None
    if named_recovery:
        recovery = input_root(state) / "recoveries" / f"{batch.batch_id}.json"
        write_atomic(
            recovery,
            ObservationPreparation.model_validate({"batches": [batch.batch_id], "paths": []}).to_json(),
        )
    _crash_at_index(state, batch, event="return", recovery=recovery)
    with ObservationLookup(lookup_root(state)) as lookup:
        receipt = lookup.receipt(batch.batch_id)
        assert receipt is not None
        leaf = node_path(lookup.root, lookup.manifest().node)
    original = {state / name for name in receipt.output_paths}

    if recovery is None:
        assert file_batch(state, batch.rows, batch.identity, ObservationLookupSettings()) == 0
    else:
        prepare(state, recovery, settings=ObservationLookupSettings())

    expected = {path.relative_to(state.parent).as_posix() for path in original | {leaf}}
    for path in {manifest_path, recovery or manifest_path}:
        assert expected <= set(ObservationPreparation.read(path).paths)
    assert all(path.is_file() for path in original)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    assert set(raw.rglob("*.parquet")) == original


@pytest.mark.parametrize("named_recovery", [False, True], ids=["job", "named-recovery"])
def test_raw_paths_are_durable_before_any_file_is_published(
    tmp_path: Path, named_recovery: bool
) -> None:
    state = tmp_path / "state"
    batch = _batch(1)
    manifest_path = preparation_path(state, batch.identity)
    recovery = None
    if named_recovery:
        recovery = input_root(state) / "recoveries" / f"{batch.batch_id}.json"
        write_atomic(
            recovery,
            ObservationPreparation.model_validate({"batches": [batch.batch_id], "paths": []}).to_json(),
        )
    _crash_at_index(state, batch, boundary="before-publish", recovery=recovery)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    assert not list(raw.rglob("*.parquet"))
    staged = input_root(state) / "outputs" / batch.batch_id / "state"
    outputs = {
        (state / path.relative_to(staged)).relative_to(state.parent).as_posix()
        for path in staged.rglob("*.parquet")
    }
    assert len(outputs) == 1
    for path in {manifest_path, recovery or manifest_path}:
        assert outputs <= set(ObservationPreparation.read(path).paths)

    paths = prepare(state, recovery or manifest_path, settings=ObservationLookupSettings())

    assert outputs <= set(paths)
    assert len(list(raw.rglob("*.parquet"))) == 1
    assert not list(staged.rglob("*.parquet"))


@pytest.mark.parametrize("boundary", ["partial-stage", "partial-publish"])
def test_a_multiday_batch_recovers_a_partial_raw_write(tmp_path: Path, boundary: str) -> None:
    state = tmp_path / "state"
    first = _batch(1)
    second = _batch(2, run_id="2026-10-03-200")
    batch = ObservationBatch.model_validate(
        {"identity": first.identity, "rows": [*first.rows, *second.rows]}
    )
    _crash_at_index(state, batch, boundary=boundary)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    abandoned = set(raw.rglob("*.parquet"))
    assert len(abandoned) == (1 if boundary == "partial-publish" else 0)
    if abandoned:
        manifest = ObservationPreparation.read(preparation_path(state, batch.identity))
        assert {path.relative_to(state.parent).as_posix() for path in abandoned} <= set(manifest.paths)

    assert file_batch(state, batch.rows, batch.identity, ObservationLookupSettings()) == 2

    assert all(not path.exists() for path in abandoned)
    assert len(list(raw.rglob("*.parquet"))) == 2
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert {row_digest(row) for row in rows} == {row_digest(row) for row in batch.rows}
    assert {row.date for row in rows} == {"2026-10-02", "2026-10-03"}


@pytest.mark.parametrize("all_accepted", [False, True], ids=["overlap", "zero-fresh"])
def test_a_winner_on_another_day_leaves_no_abandoned_loser_output(
    tmp_path: Path, all_accepted: bool
) -> None:
    state = tmp_path / "state"
    loser = _batch(1, 2)
    winner = _batch(*(range(1, 3) if all_accepted else [1]), run_id="2026-10-03-200")
    _crash_at_index(state, loser)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    abandoned = set(raw.rglob("*.parquet"))
    settings = ObservationLookupSettings()
    assert file_batch(state, winner.rows, winner.identity, settings) == len(winner.rows)
    with ObservationLookup(lookup_root(state)) as lookup:
        winner_receipt = lookup.receipt(winner.batch_id)
        assert winner_receipt is not None
    retained = {state / name: (state / name).read_bytes() for name in winner_receipt.output_paths}

    assert file_batch(state, loser.rows, loser.identity, settings) == (0 if all_accepted else 1)

    assert all(not path.exists() for path in abandoned)
    assert all(path.read_bytes() == data for path, data in retained.items())
    assert len(list(raw.rglob("*.parquet"))) == (1 if all_accepted else 2)
    rows = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(rows) == 2
    winning_keys = {row_digest(row) for row in winner.rows}
    assert all(row.date == ("2026-10-03" if row_digest(row) in winning_keys else "2026-10-02") for row in rows)
    manifest = ObservationPreparation.read(preparation_path(state, loser.identity))
    assert {path.relative_to(state.parent).as_posix() for path in abandoned} <= set(manifest.paths)
    with ObservationLookup(lookup_root(state)) as lookup:
        receipt = lookup.receipt(loser.batch_id)
        assert receipt is not None and receipt.accepted == (0 if all_accepted else 1)
        if all_accepted:
            assert receipt.output_paths == []


def test_named_recovery_inherits_only_its_batches_prepared_paths(tmp_path: Path) -> None:
    state = tmp_path / "state"
    first = _batch(1)
    unrelated = _batch(2)
    settings = ObservationLookupSettings()
    assert file_batch(state, first.rows, first.identity, settings) == 1
    assert file_batch(state, unrelated.rows, unrelated.identity, settings) == 1
    with ObservationLookup(lookup_root(state)) as lookup:
        first_receipt = lookup.receipt(first.batch_id)
        other_receipt = lookup.receipt(unrelated.batch_id)
        assert first_receipt is not None and other_receipt is not None
    recovery = input_root(state) / "recoveries" / f"{first.batch_id}.json"
    write_atomic(
        recovery,
        ObservationPreparation.model_validate({"batches": [first.batch_id], "paths": []}).to_json(),
    )

    paths = set(prepare(state, recovery, settings=settings))

    first_paths = {(state / name).relative_to(state.parent).as_posix() for name in first_receipt.output_paths}
    other_paths = {(state / name).relative_to(state.parent).as_posix() for name in other_receipt.output_paths}
    assert first_paths <= paths
    assert not paths & other_paths
    assert paths == set(ObservationPreparation.read(recovery).paths)


def test_a_raw_crash_then_a_lost_push_cannot_publish_the_abandoned_file(tmp_path: Path) -> None:
    origin, losing, environment = _publication_origin(tmp_path)
    winning = tmp_path / "winning"
    _git(tmp_path, environment, "clone", str(origin), str(winning))
    loser = _batch(1, run_id="2026-10-03-300")
    winner = _batch(1, run_id="2026-10-02-200")
    state = losing / "state"
    _crash_at_index(state, loser)
    raw = ledger.raw_root(state, LedgerName.SUMMARY_QUALITY_EVALS)
    abandoned = {path.relative_to(losing).as_posix() for path in raw.rglob("*.parquet")}
    assert len(abandoned) == 1
    settings = ObservationLookupSettings()
    assert file_batch(winning / "state", winner.rows, winner.identity, settings) == 1
    result = _run_commit_script(
        winning,
        environment,
        ["state"],
        {
            "COMMIT_MESSAGE": "Publish the winning evaluation",
            "NOTHING_STAGED_MESSAGE": "The winning evaluation is published",
            "PUSH_FAILED_MESSAGE": "Could not publish the winning evaluation",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with ObservationLookup(lookup_root(winning / "state")) as lookup:
        winner_receipt = lookup.receipt(winner.batch_id)
        assert winner_receipt is not None

    result = _run_commit_script(
        losing,
        environment,
        ["state"],
        {**_commit_settings(losing, loser), "PUSH_DEADLINE_SECONDS": "90"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "push rejected" in result.stdout
    assert "CONFLICT" not in result.stdout + result.stderr
    published = tmp_path / "published"
    _git(tmp_path, environment, "clone", str(origin), str(published))
    held = ledger.load_ledger_rows(published / "state", LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert len(held) == 1 and held[0].date == "2026-10-02"
    assert row_digest(held[0]) == row_digest(winner.rows[0])
    physical = set(ledger.raw_root(published / "state", LedgerName.SUMMARY_QUALITY_EVALS).rglob("*.parquet"))
    assert physical == {published / "state" / name for name in winner_receipt.output_paths}
    assert all(not (published / name).exists() for name in abandoned)
    with ObservationLookup(lookup_root(published / "state")) as lookup:
        receipt = lookup.receipt(loser.batch_id)
        assert receipt is not None and receipt.accepted == 0 and receipt.output_paths == []
        assert lookup.receipt(winner.batch_id) == winner_receipt
    manifest = ObservationPreparation.read(preparation_path(state, loser.identity))
    assert abandoned <= set(manifest.paths)
    assert not _git(published, environment, "ls-files", "--", "backend/var/evaluation-inputs")