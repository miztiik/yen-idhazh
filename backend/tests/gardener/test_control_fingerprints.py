"""Verify exact native gardener control evidence reaches ordinary Git publication."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, REPO_ROOT

from idhazh.contracts.host_fingerprint import HostHardwareRow
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.gardener.control_fingerprints import Job, Operation, artifact, expected, task_file
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, machine_evidence
from utilities import gardener_control_task
from utilities.gardener_fingerprint_publish import land
from utilities.publication_git import Repository
from utilities.publish_to_repo import Status

from ._garden import an_origin, git, quiet_git, write


def test_control_evidence_appends_without_shards_and_keeps_original_producing_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str],
) -> None:
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.delenv("FORCE", raising=False)
    monkeypatch.delenv(machine_api.ORIGIN_ENV, raising=False)
    day = datetime.now(UTC).date().isoformat()
    run_id = f"{day}-345"
    seed = {
        "config/gardener/config/idhazh_gardener.json": '{"shards":1,"task_names":[]}',
        "config/gardener/corpus-squash.json": (
            CONFIG_DIR / "gardener" / "corpus-squash.json"
        ).read_text(encoding="utf-8"),
        "config/push-retry.json": (CONFIG_DIR / "push-retry.json").read_text(encoding="utf-8"),
        "corpus/corpus.meta.json": json.dumps({"last_run": day}),
        "state/raw/gardener/keep.txt": "original gardener evidence",
        "state/raw/council-run-records/keep.txt": "original Council evidence",
    }
    origin, repo = an_origin(tmp_path, seed)
    revision = git(repo, "rev-parse", "HEAD").strip()
    specs = (
        (Job.PLAN, 1, Operation.PLAN, "success"),
        (Job.HISTORY, 1, Operation.CHECK_HISTORY, "success"),
        (Job.APPEND, 1, Operation.PREPARE_APPEND, "success"),
        (Job.HISTORY, 2, Operation.CHECK_HISTORY, "error"),
        (Job.APPEND, 2, Operation.PREPARE_APPEND, "success"),
    )
    readings = tuple(
        expected(job, run_id=run_id, attempt=attempt, revision=revision)
        for job, attempt, _, _ in specs
    )
    monkeypatch.chdir(repo)
    assert gardener_control_task.run(
        Operation.PLAN, repo=REPO_ROOT, opening=readings[0], bundle=tmp_path / "untimed",
    ) == 0
    assert "any_active_task=false" in capfd.readouterr().out.splitlines()
    due = [sys.executable, str(REPO_ROOT / "backend/utilities/corpus_squash_due.py")]
    assert gardener_control_task.run(
        Operation.CHECK_HISTORY, repo=REPO_ROOT, opening=readings[1], bundle=tmp_path / "untimed",
        command=due, worktree=repo,
    ) == 0
    assert "due=false" in capfd.readouterr().out.splitlines()
    write(repo / "corpus/corpus.meta.json", "{}")
    assert gardener_control_task.run(
        Operation.CHECK_HISTORY, repo=REPO_ROOT, opening=readings[3], bundle=tmp_path / "untimed",
        command=due, worktree=repo,
    ) == 1
    failed = capfd.readouterr()
    assert "due=" not in failed.out and "no last_run" in failed.err

    tasks = tuple(
        task_file(item, operation)
        for item, (_, _, operation, _) in zip(readings, specs, strict=True)
    )
    states = tuple(tmp_path / f"native-{job}-{attempt}" / "state" for job, attempt, _, _ in specs)
    bun = shutil.which("bun")
    assert bun is not None
    captured = subprocess.run(
        [bun, "run", "--no-install", "test/write-gardener-control.ts"],
        cwd=REPO_ROOT / "services" / "host-probes",
        input=json.dumps([
            {
                "state": str(state),
                "request": {"date": item.date, "writer": item.writer.model_dump(mode="json")},
                "tasks": [machine_api.record_request(
                    date=task.date, identity=task.writer, measurement={
                        "task_kind": "workflow-task", "outcome": outcome, "elapsed_ms": 1.25,
                    },
                )],
            }
            for state, item, task, (_, _, _, outcome) in zip(states, readings, tasks, specs, strict=True)
        ]),
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert captured.returncode == 0, captured.stderr
    replies = tuple(json.loads(line) for line in captured.stdout.splitlines())
    first, retry = tmp_path / "incoming-first", tmp_path / "incoming-retry"
    own_first, own_retry = tmp_path / "append-first", tmp_path / "append-retry"
    bundles = (
        first / artifact(Job.PLAN, run_id, 1),
        first / artifact(Job.HISTORY, run_id, 1),
        own_first,
        retry / artifact(Job.HISTORY, run_id, 2),
        own_retry,
    )
    proofs = []
    task_proofs = []
    for state, item, task, reply, bundle in zip(states, readings, tasks, replies, bundles, strict=True):
        opening = machine_evidence.verify_capture(
            state, machine_api.Captured.model_validate(reply["opening"]), item,
        )
        opening.save_receipt(bundle, item)
        proof = machine_evidence.read_receipt(bundle, item)
        assert proof is not None
        proofs.append(proof)
        observation = machine_api.Written.model_validate(reply["recorded"][0])
        (received,) = observation.files
        measured = machine_evidence.verify_file(state.parent, f"state/{received.path}", task)
        measured.save_receipt(bundle, task)
        task_proofs.append(measured)
    proofs[0].save_receipt(retry / artifact(Job.PLAN, run_id, 1), readings[0])
    task_proofs[0].save_receipt(retry / artifact(Job.PLAN, run_id, 1), tasks[0])
    assert land(
        repo, tmp_path / "empty-incoming", tmp_path / "empty-local",
        run_id=run_id, attempt=1, revision=revision, plan_attempt=None, history_attempt=None,
    ).status is Status.NO_CHANGES

    # Foreign local and pre-staged writes are not part of this append.
    changed = "state/raw/gardener/keep.txt"
    write(repo / changed, "unrelated staged change")
    git(repo, "add", "--", changed)
    assert land(
        repo, first, own_first, run_id=run_id, attempt=1, revision=revision,
        plan_attempt=1, history_attempt=1,
    ).status is Status.LANDED
    before_retry = git(origin, "rev-parse", "main")
    (bundles[3] / task_proofs[3].path).write_bytes(task_proofs[3].data + b"bad bytes")
    with pytest.raises(IntegrityError, match="bytes changed"):
        land(
            repo, retry, own_retry, run_id=run_id, attempt=2, revision=revision,
            plan_attempt=1, history_attempt=2,
        )
    (bundles[3] / task_proofs[3].path).write_bytes(task_proofs[3].data)
    # An artifact carrying an older file cannot be presented as a fresh capture.
    task_proofs[1].save_receipt(bundles[3], tasks[3])
    with pytest.raises(IntegrityError, match="exact path or writer"):
        land(
            repo, retry, own_retry, run_id=run_id, attempt=2, revision=revision,
            plan_attempt=1, history_attempt=2,
        )
    assert git(origin, "rev-parse", "main") == before_retry
    task_proofs[3].save_receipt(bundles[3], tasks[3])
    (bundles[3] / readings[3].receipt).unlink()
    with pytest.raises(IntegrityError, match="host reference lacks verified opening"):
        land(
            repo, retry, own_retry, run_id=run_id, attempt=2, revision=revision,
            plan_attempt=1, history_attempt=2,
        )
    assert git(origin, "rev-parse", "main") == before_retry
    proofs[3].save_receipt(bundles[3], readings[3])
    result = land(
        repo, retry, own_retry, run_id=run_id, attempt=2, revision=revision,
        plan_attempt=1, history_attempt=2,
    )
    assert result.status is Status.LANDED
    remote = Repository(origin, git_dir=origin)
    for proof, measured, (job, attempt, operation, outcome) in zip(proofs, task_proofs, specs, strict=True):
        for completed in (proof, measured):
            entry = remote.entry("main", completed.path)
            assert entry is not None and remote.blob(entry.oid) == completed.data
            assert not (repo / completed.path).exists()
        assert isinstance(proof.row, HostHardwareRow)
        assert (
            proof.row.job, proof.row.pipeline_name, proof.row.task_name, proof.envelope.identity.attempt,
        ) == (
            job, "gardener", job, attempt,
        )
        assert measured.envelope.identity.attempt == attempt
        assert measured.envelope.identity.git_sha == revision
        assert isinstance(measured.row, TaskPerformanceRow)
        assert (measured.row.task_name, measured.row.outcome) == (operation, outcome)
        assert measured.row.host_unit_id == str(proof.envelope.unit_id)
    advanced = git(origin, "rev-parse", "main").strip()
    assert set(git(origin, "diff", "--name-only", revision, advanced).splitlines()) == {
        proof.path for proof in (*proofs, *task_proofs)
    }
