"""Verify native openings reach ordinary Git publication even without tasks or a rewrite."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, REPO_ROOT

from idhazh.gardener.control_fingerprints import Job, artifact, expected
from idhazh.publication_paths import IntegrityError
from idhazh.telemetry import machine_api, machine_evidence
from utilities import corpus_squash_due, gardener_shards
from utilities.gardener_fingerprint import retain
from utilities.gardener_fingerprint_publish import land
from utilities.publication_git import Repository
from utilities.publish_to_repo import Status

from ._garden import an_origin, git, quiet_git, write


def test_control_openings_append_after_no_shards_and_no_rewrite_then_keep_original_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    quiet_git(tmp_path, monkeypatch)
    monkeypatch.delenv("FORCE", raising=False)
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
    assert gardener_shards.plan(repo / "config")["any_active_task"] is False
    assert corpus_squash_due.main([
        "--config-root", str(repo / "config"), "--corpus-meta", str(repo / "corpus/corpus.meta.json"),
    ]) == 0
    assert "due=false" in capsys.readouterr().out.splitlines()

    specs = (
        (Job.PLAN, 1), (Job.HISTORY, 1), (Job.APPEND, 1),
        (Job.HISTORY, 2), (Job.APPEND, 2),
    )
    readings = tuple(
        expected(job, run_id=run_id, attempt=attempt, revision=revision) for job, attempt in specs
    )
    states = tuple(tmp_path / f"native-{job}-{attempt}" / "state" for job, attempt in specs)
    bun = shutil.which("bun")
    assert bun is not None
    captured = subprocess.run(
        [bun, "run", "--no-install", "test/write-workflow-fingerprint.ts"],
        cwd=REPO_ROOT / "services" / "host-probes",
        input=json.dumps([
            {
                "state": str(state),
                "request": {"date": item.date, "writer": item.writer.model_dump(mode="json")},
            }
            for state, item in zip(states, readings, strict=True)
        ]),
        capture_output=True, text=True, timeout=45, check=False,
    )
    assert captured.returncode == 0, captured.stderr
    replies = tuple(
        machine_api.Captured.model_validate_json(line) for line in captured.stdout.splitlines()
    )
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
    for state, item, reply, bundle in zip(states, readings, replies, bundles, strict=True):
        retain(state, bundle, item, reply)
        proof = machine_evidence.read_receipt(bundle, item)
        assert proof is not None
        proofs.append(proof)
    proofs[0].save_receipt(retry / artifact(Job.PLAN, run_id, 1), readings[0])

    # Foreign local and pre-staged writes are not part of this append.
    changed = "state/raw/gardener/keep.txt"
    write(repo / changed, "unrelated staged change")
    git(repo, "add", "--", changed)
    assert land(
        repo, first, own_first, run_id=run_id, attempt=1, revision=revision,
        plan_attempt=1, history_attempt=1,
    ).status is Status.LANDED
    before_retry = git(origin, "rev-parse", "main")
    (bundles[3] / proofs[3].path).write_bytes(proofs[3].data + b"bad bytes")
    with pytest.raises(IntegrityError, match="bytes changed"):
        land(
            repo, retry, own_retry, run_id=run_id, attempt=2, revision=revision,
            plan_attempt=1, history_attempt=2,
        )
    (bundles[3] / proofs[3].path).write_bytes(proofs[3].data)
    # An artifact carrying an older file cannot be presented as a fresh capture.
    proofs[1].save_receipt(bundles[3], readings[3])
    with pytest.raises(IntegrityError, match="exact path or writer"):
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
    for proof, (job, attempt) in zip(proofs, specs, strict=True):
        entry = remote.entry("main", proof.path)
        assert entry is not None and remote.blob(entry.oid) == proof.data
        assert (proof.envelope.identity.job, proof.envelope.identity.attempt) == (
            f"gardener-{job}", attempt,
        )
        assert not (repo / proof.path).exists()
    advanced = git(origin, "rev-parse", "main").strip()
    assert set(git(origin, "diff", "--name-only", revision, advanced).splitlines()) == {
        proof.path for proof in proofs
    }
