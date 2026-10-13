"""Can the native launcher admit a job's machine identity without a run plan?"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT, SEED_COMMIT

from idhazh import cli, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.stages import common
from utilities import d7_host_telemetry as lifecycle

from ._harness import _copy_config

WAKE_DAY = "2026-09-19"
WAKE_EXECUTION = "33274853468"
WAKE_SHARD = 3


@pytest.fixture(autouse=True)
def unbound_runner_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("IDHAZH_HOST_TELEMETRY_"):
            monkeypatch.delenv(name)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


@pytest.mark.parametrize(
    ("script", "job", "config_flag", "run_id", "shard"),
    [
        (
            "gardener_publish.py",
            ServerJob.RUN_TASKS,
            "--config",
            f"{WAKE_DAY}-{WAKE_EXECUTION}",
            WAKE_SHARD,
        ),
        (
            "council_publish.py",
            ServerJob.SAVE_COUNCIL_RESULTS,
            "--config-root",
            f"{WAKE_DAY}-{WAKE_EXECUTION}0",
            0,
        ),
    ],
)
def test_native_no_plan_admission_keeps_the_workflows_exact_identity(
    tmp_path: Path,
    script: str,
    job: ServerJob,
    config_flag: str,
    run_id: str,
    shard: int,
) -> None:
    config_root = tmp_path / "config"
    _copy_config(config_root)
    command = [
        sys.executable,
        str(REPO_ROOT / "backend" / "utilities" / script),
        config_flag,
        str(config_root),
        "--run-id",
        run_id,
    ]
    if job is ServerJob.RUN_TASKS:
        command.extend(["--shard", str(shard), "--attempt", "1"])
    else:
        command.extend(["--date", WAKE_DAY, "--commit", SEED_COMMIT])
    source = lifecycle._source_settings(job.value, command[2:])
    invocation = lifecycle._invocation(
        argparse.Namespace(
            command=command, run_id=None, git_sha=SEED_COMMIT, attempt=1, shard=shard
        ),
        job,
        source,
    )
    session = tmp_path / "session"
    session.mkdir()
    selected, windows = lifecycle._selected_plan(invocation, source, session, repo=tmp_path)

    assert selected == invocation
    assert selected.date == WAKE_DAY
    assert selected.identity.run_id == run_id
    assert selected.identity.job is job
    assert selected.identity.shard == shard
    assert selected.identity.attempt == 1
    assert selected.identity.git_sha == SEED_COMMIT
    assert selected.command == tuple(command)
    assert selected.host_enabled
    assert selected.plan_path is None and selected.plan_sha256 is None
    assert windows == ()
    assert not (session / "selected-plan.json").exists()
    assert not (tmp_path / "state").exists()
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.RUN_PLAN).exists()


@pytest.mark.parametrize("verb", ["fingerprint", "job-clock"])
def test_standalone_host_verbs_require_the_native_launcher_without_writing_a_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], verb: str
) -> None:
    config_root = tmp_path / "config"
    _copy_config(config_root)
    with pytest.raises(SystemExit) as refused:
        cli.main(
            [
                verb,
                "--config",
                str(config_root),
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

    assert refused.value.code == 2
    assert "host measurements require the bound Rust telemetry launcher" in capsys.readouterr().err
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.HOST_FINGERPRINT).exists()
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.RUN_PLAN).exists()


def test_native_no_plan_admission_refuses_another_workflows_run(tmp_path: Path) -> None:
    config_root = tmp_path / "config"
    _copy_config(config_root)
    command = [
        sys.executable,
        str(REPO_ROOT / "backend" / "utilities" / "council_publish.py"),
        "--config-root",
        str(config_root),
        "--date",
        WAKE_DAY,
        "--run-id",
        f"{WAKE_DAY}-{WAKE_EXECUTION}0",
        "--commit",
        SEED_COMMIT,
    ]
    source = lifecycle._source_settings(ServerJob.SAVE_COUNCIL_RESULTS.value, command[2:])
    with pytest.raises(ValueError, match="run address differs from the producer invocation"):
        lifecycle._invocation(
            argparse.Namespace(
                command=command, run_id=f"{WAKE_DAY}-1", git_sha=None, attempt=1, shard=0
            ),
            ServerJob.SAVE_COUNCIL_RESULTS,
            source,
        )

    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.HOST_FINGERPRINT).exists()
    assert not ledger.raw_root(common.STATE_ROOT, LedgerName.RUN_PLAN).exists()
