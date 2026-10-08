"""Can a workflow that writes no run plan still record the machine its job drew?

`digest.yml` and `measure.yml` both open with a stage that files a run plan, so
until this was asked the probe could read one back and nobody noticed. The
gardener's wakes and the council's nights draw their own runners and plan
nothing, and the probe is worth exactly as much to them: a gardener task that
takes twice as long this month is a question about the machine first.

A workflow that mints its own run name rather than computing one is here too,
because a machine row under a second address answers nothing the night asked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import SEED_COMMIT, read_text

from idhazh import cli, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.stages import common

from ._harness import _copy_config

#: A UTC day outside the committed archive, so only this test writes it.
WAKE_DAY = "2026-09-19"

#: One `github.run_id`. GitHub allocates it per workflow run and it is unique
#: across every workflow in the repository, so a gardener wake and a digest run
#: on one day cannot derive the same run id.
WAKE_EXECUTION = "33274853468"

#: The shard of the gardener's task matrix this row is filed for.
WAKE_SHARD = 3


def a_config_with_no_bandwidth_probe(root: Path) -> Path:
    """The committed config, with the one reading that wants a spare gigabyte off.

    Guardrail #6: the knob switches it, so this moves the knob rather than the
    code. What the bandwidth reading measures is driven over built text in
    `tests/test_silicon.py`; what this file asks is whether the verb runs at all
    for a job with no plan behind it.
    """
    target = root / "config"
    _copy_config(target)
    knobs = json.loads(read_text(target / "idhazh.json"))
    knobs["observability"]["host_fingerprint_bandwidth_floor_mib"] = 0
    (target / "idhazh.json").write_text(json.dumps(knobs), encoding="utf-8")
    return target


def test_the_fingerprint_verb_records_a_machine_on_a_day_no_run_planned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row lands on its own day, under the run the workflow names.

    Driven through the verb rather than through the stage, because the plan was
    read in the router and no code below it ever opened one. A workflow with no
    plan stage reached `FileNotFoundError` here, which made a machine reading
    something only the two workflows that plan could take.

    The last assertion is the one that would catch the regression returning: a
    plan tree on disk means something read for a plan, found none, and wrote one
    to carry on.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    config_dir = a_config_with_no_bandwidth_probe(tmp_path)

    code = cli.main(
        [
            "fingerprint",
            "--config",
            str(config_dir),
            "--date",
            WAKE_DAY,
            "--execution",
            WAKE_EXECUTION,
            "--commit",
            SEED_COMMIT,
            "--job",
            ServerJob.RUN_TASKS.value,
            "--shard",
            str(WAKE_SHARD),
        ]
    )

    assert code == 0, "a job that planned nothing still has a machine to report"
    (row,) = ledger.load_days(
        common.STATE_ROOT, LedgerName.HOST_FINGERPRINT, [WAKE_DAY], model=HostFingerprintRow
    )
    assert (row.date, row.run_id) == (WAKE_DAY, f"{WAKE_DAY}-{WAKE_EXECUTION}")
    assert (row.job, row.shard) == (ServerJob.RUN_TASKS, WAKE_SHARD)
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.RUN_PLAN).exists(), (
        "the verb read no plan, so it may not have written one either"
    )


def test_the_job_clock_closes_that_row_without_a_plan_either(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both halves or neither: a probe nothing can close is a half-row for ever.

    The clock step reads back the row this job's own probe filed and files the
    whole row again under the same writer, so the two verbs have to agree about
    the run they are filing for. They agree here because both are handed the
    same address rather than each recovering one.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    config_dir = a_config_with_no_bandwidth_probe(tmp_path)
    address = [
        "--config",
        str(config_dir),
        "--date",
        WAKE_DAY,
        "--execution",
        WAKE_EXECUTION,
        "--commit",
        SEED_COMMIT,
        "--job",
        ServerJob.HISTORY.value,
    ]

    assert cli.main(["fingerprint", *address]) == 0
    assert cli.main(["job-clock", *address, "--job-started-at", "1"]) == 0

    (row,) = ledger.load_days(
        common.STATE_ROOT, LedgerName.HOST_FINGERPRINT, [WAKE_DAY], model=HostFingerprintRow
    )
    assert row.fingerprint is not None, "the clock carries the machine the probe measured"
    assert row.job_seconds is not None, "the clock filled the cell only it can know"
    assert len({held.envelope.unit_id for held in _raw(common.STATE_ROOT)}) == 1, (
        "one job, one writer, one work unit - however many verbs filed for it"
    )


def test_a_workflow_that_mints_its_own_name_files_the_machine_under_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The council names its night once and every verb that writes a row takes it.

    A machine row that computed its own address instead would sit beside the
    night's other rows under a second name, and the join that asks which machine
    judged a night is on `run_id`.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    minted = f"{WAKE_DAY}-{WAKE_EXECUTION}0"

    code = cli.main(
        [
            "fingerprint",
            "--config",
            str(a_config_with_no_bandwidth_probe(tmp_path)),
            "--date",
            WAKE_DAY,
            "--run-id",
            minted,
            "--commit",
            SEED_COMMIT,
            "--job",
            ServerJob.SAVE_COUNCIL_RESULTS.value,
        ]
    )

    assert code == 0
    (row,) = ledger.load_days(
        common.STATE_ROOT, LedgerName.HOST_FINGERPRINT, [WAKE_DAY], model=HostFingerprintRow
    )
    assert row.run_id == minted, "the row took the name it was handed, not one it computed"


def test_a_run_id_and_an_execution_that_disagree_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two addresses for one job is a step handed one of them by mistake.

    Filing under either would put a machine on a run that never drew it, which
    is the single reading this ledger exists to make. Refused at the parser, so
    nothing is written before anybody finds out.
    """
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")

    with pytest.raises(SystemExit) as refused:
        cli.main(
            [
                "fingerprint",
                "--config",
                str(a_config_with_no_bandwidth_probe(tmp_path)),
                "--date",
                WAKE_DAY,
                "--run-id",
                f"{WAKE_DAY}-1",
                "--execution",
                WAKE_EXECUTION,
                "--commit",
                SEED_COMMIT,
            ]
        )

    assert refused.value.code == 2, "argparse refuses the pair before any row is written"
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.HOST_FINGERPRINT).exists()


def _raw(state: Path) -> list[ledger.RawFile]:
    """Every raw host row of the wake day, each with the envelope of its writer."""
    return ledger.list_raw_files(state, LedgerName.HOST_FINGERPRINT, days={WAKE_DAY})
