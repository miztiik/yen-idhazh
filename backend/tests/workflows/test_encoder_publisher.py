"""Does the encoder collector publish its complete comparison without sweeping other files?"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import REPO_ROOT
from gardener._garden import an_origin, git, quiet_git, write

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
from utilities import encoder_publish, publication_evidence
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError
from utilities.publish_to_repo import PublicationResult, Status

DIRECTORY = "corpus/encoder-comparison-1"
EXECUTION = "123"
PAIR_SET = json.dumps({
    "first_day": "2026-09-01", "last_day": "2026-09-01", "days_named": 1,
    "articles_read": 2, "articles_encoded": 2, "same_pairs": 1,
    "different_pairs": 1, "pair_build": {},
})
CONTROL = {
    "slug": "control", "model_id": "recorded/control", "state": "unavailable",
    "reason": "recorded fixture", "why": "saved control",
    "pair_set_sha256": hashlib.sha256(PAIR_SET.encode()).hexdigest(),
}
SETTINGS = {
    "version": "2026-10-09", "pair_build": {}, "encode": {"threads": 0},
    "corpus": {"published_articles": 2, "articles_a_batch": 2},
    "encoders": [
        {"slug": "control", "model_id": "recorded/control", "why": "saved control"},
        {"slug": "candidate", "model_id": "recorded/candidate", "why": "new candidate"},
    ],
}
RETRY = {
    "deadline_seconds": {"default": 300},
    "base_step_seconds": 0.001, "ceiling_seconds": 0.001, "ceiling_after": 1,
}


def comparison(
    root: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, WriterIdentity]:
    quiet_git(root, monkeypatch)
    origin, repo = an_origin(root, {
        "seed": "seed\n",
        ".gitignore": (REPO_ROOT / ".gitignore").read_text(encoding="utf-8"),
        "config/push-retry.json": json.dumps(RETRY),
        "config/encoder-comparison.json": json.dumps(SETTINGS),
        f"{DIRECTORY}/pairs.json": PAIR_SET,
        f"{DIRECTORY}/readings/encoders.json": json.dumps({"encoders": [CONTROL]}),
        f"{DIRECTORY}/readings/encoders.md": "saved table\n",
        f"{DIRECTORY}/manifest.json": "{}",
        f"{DIRECTORY}/logs/candidate.log": "saved log\n",
    })
    source = git(repo, "rev-parse", "HEAD").strip()
    identity = WriterIdentity(
        run_id=f"2026-10-10-{EXECUTION}", attempt=1, job=ServerJob.COLLECT, shard=0,
        producer=encoder_publish.PRODUCER, git_sha=source,
    )
    write(repo / "downloaded/readings/candidate.json", json.dumps({
        "slug": "candidate", "model_id": "recorded/candidate", "state": "encoding",
        "articles_done": 1, "articles_to_encode": 2, "why": "new candidate",
        "pair_set_sha256": CONTROL["pair_set_sha256"],
    }))
    write(repo / "downloaded/logs/candidate.log", "checkpoint reached\n")
    write(repo / "downloaded/logs/control.log", "not selected\n")
    write(repo / "downloaded/logs/foreign.log", "not a configured encoder\n")
    write(repo / "pair-build.log", "reused pairs\n")
    return origin, repo, identity


def collect(repo: Path, identity: WriterIdentity, *, selected: str = "candidate") -> None:
    encoder_publish.collect(
        repo, DIRECTORY, identity=identity,
        readings_from=repo / "downloaded/readings",
        logs_from=repo / "downloaded/logs", pair_log=repo / "pair-build.log",
        selected=selected, preserve_existing=True, run_url="https://example.invalid/run",
    )


def land(repo: Path, identity: WriterIdentity) -> PublicationResult:
    return encoder_publish.land(
        repo, DIRECTORY, execution=EXECUTION, attempt=identity.attempt,
        code_sha=identity.git_sha, selected="candidate",
    )


def test_complete_selected_comparison_lands_without_foreign_files_or_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    collect(repo, identity)
    before = git(repo, "rev-parse", "HEAD").strip()
    foreign = f"{DIRECTORY}/judgments/foreign.json"
    write(repo / foreign, '{"unrelated": true}\n')
    git(repo, "add", foreign)
    index = (repo / ".git/index").read_bytes()
    result = land(repo, identity)
    assert result.status is Status.LANDED, result
    assert git(repo, "rev-parse", "HEAD").strip() == before
    assert (repo / ".git/index").read_bytes() == index
    remote = Repository(origin)
    assert remote.entry("main", foreign) is None
    receipt = PublicationReceipt.read(publication_evidence.receipt_path(repo, identity, "encoder-comparison"))
    expected = {
        f"{DIRECTORY}/{name}"
        for name in (*encoder_publish.OUTPUTS, "logs/candidate.log", "logs/pair-build.log")
    }
    assert receipt.writes.keys() == expected
    for path in expected:
        entry = remote.entry("main", path)
        assert entry is not None
        assert remote.blob(entry.oid) == (repo / path).read_bytes()
    data = json.loads((repo / DIRECTORY / "readings/encoders.json").read_text())
    assert next(row for row in data["encoders"] if row["slug"] == "control") == CONTROL
    assert next(row for row in data["encoders"] if row["slug"] == "candidate")["state"] == "encoding"
    assert remote.entry("main", f"{DIRECTORY}/logs/control.log") is None
    ignored = Repository(repo).run("check-ignore", "downloaded/logs/foreign.log")
    assert ignored.returncode == 0
    assert Repository(repo).run(
        "check-ignore", "--no-index", f"{DIRECTORY}/logs/pair-build.log",
    ).returncode == 1
    assert git(origin, "log", "-1", "--format=%B").strip() == "Encoder readings, taken on the runner"
    assert git(origin, "log", "-1", "--format=%an <%ae>").strip() == (
        "miztiik <miztiik@users.noreply.github.com>"
    )
    assert land(repo, identity).status is Status.ALREADY_ON_MAIN


def test_unrelated_new_main_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    collect(repo, identity)
    other = tmp_path / "other"
    git(tmp_path, "clone", "--quiet", str(origin), str(other))
    write(other / "other-work", "keep newer work\n")
    git(other, "add", "other-work")
    git(other, "commit", "--quiet", "-m", "another writer")
    git(other, "push", "--quiet", "origin", "main")
    newer = git(origin, "rev-parse", "main").strip()
    result = land(repo, identity)
    assert result.status is Status.LANDED, result
    assert git(origin, "rev-parse", "main^").strip() == newer
    assert git(origin, "show", "main:other-work") == "keep newer work\n"


@pytest.mark.parametrize("path", [
    "pairs.json", "readings/encoders.json", "manifest.json", "logs/candidate.log",
])
def test_changed_comparison_refuses_the_whole_stale_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    collect(repo, identity)
    other = tmp_path / "other"
    git(tmp_path, "clone", "--quiet", str(origin), str(other))
    write(other / DIRECTORY / path, "a newer comparison\n")
    git(other, "add", f"{DIRECTORY}/{path}")
    git(other, "commit", "--quiet", "-m", "newer comparison")
    git(other, "push", "--quiet", "origin", "main")
    newer = git(origin, "rev-parse", "main").strip()
    result = land(repo, identity)
    assert result.status is Status.STALE, result
    assert result.exit_code == 1 and result.push_count == 0
    assert git(origin, "rev-parse", "main").strip() == newer


@pytest.mark.parametrize("damage", ["bytes", "missing", "foreign", "identity"])
def test_invalid_receipt_or_modified_output_cannot_land(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    collect(repo, identity)
    path = publication_evidence.receipt_path(repo, identity, "encoder-comparison")
    receipt = json.loads(path.read_text())
    if damage == "bytes":
        write(repo / DIRECTORY / "manifest.json", "changed after collection\n")
    elif damage == "missing":
        del receipt["writes"][f"{DIRECTORY}/pairs.json"]
    elif damage == "foreign":
        receipt["writes"][f"{DIRECTORY}/judgments/unrelated.json"] = "0" * 64
    else:
        receipt["identity"]["attempt"] = 2
    write(path, json.dumps(receipt))
    if damage == "bytes":
        assert land(repo, identity).status is Status.INTEGRITY_REFUSED
    else:
        with pytest.raises(IntegrityError):
            land(repo, identity)
    assert git(origin, "rev-parse", "main").strip() == identity.git_sha


def test_full_collection_records_missing_shards_and_logs_truthfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo, identity = comparison(tmp_path, monkeypatch)
    collect(repo, identity, selected="")
    rows = json.loads((repo / DIRECTORY / "readings/encoders.json").read_text())["encoders"]
    assert next(row for row in rows if row["slug"] == "control")["state"] == "did not report"
    receipt = PublicationReceipt.read(publication_evidence.receipt_path(repo, identity, "encoder-comparison"))
    assert f"{DIRECTORY}/logs/control.log" in receipt.writes
    assert f"{DIRECTORY}/logs/foreign.log" not in receipt.writes


def test_fresh_pair_set_and_missing_logs_still_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    pairs = repo / DIRECTORY / "pairs.json"
    write(pairs, PAIR_SET + "\n")
    reading = repo / "downloaded/readings/candidate.json"
    data = json.loads(reading.read_text())
    data["pair_set_sha256"] = hashlib.sha256(pairs.read_bytes()).hexdigest()
    write(reading, json.dumps(data))
    (repo / "downloaded/logs/candidate.log").unlink()
    (repo / "pair-build.log").unlink()
    encoder_publish.collect(
        repo, DIRECTORY, identity=identity,
        readings_from=repo / "downloaded/readings",
        logs_from=repo / "downloaded/logs", pair_log=repo / "pair-build.log",
        selected="candidate", preserve_existing=False, run_url="",
    )
    receipt = PublicationReceipt.read(
        publication_evidence.receipt_path(repo, identity, "encoder-comparison")
    )
    assert receipt.writes.keys() == {
        f"{DIRECTORY}/{name}" for name in encoder_publish.OUTPUTS
    }
    assert land(repo, identity).status is Status.LANDED
    assert git(origin, "show", f"main:{DIRECTORY}/pairs.json") == PAIR_SET + "\n"


def test_configured_slugs_cannot_grant_parent_path_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo, _ = comparison(tmp_path, monkeypatch)
    config = json.loads(json.dumps(SETTINGS))
    config["encoders"][1]["slug"] = "../judgments/foreign"
    write(repo / "config/encoder-comparison.json", json.dumps(config))
    with pytest.raises(ValueError):
        encoder_publish.declarations(repo, DIRECTORY, "")


def test_cli_collection_does_not_publish_when_commit_is_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin, repo, identity = comparison(tmp_path, monkeypatch)
    process = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "backend/utilities/encoder_publish.py"), "run",
            "--set-directory", DIRECTORY, "--selected", "candidate", "--preserve-existing",
            "--execution", EXECUTION, "--commit", identity.git_sha,
        ],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert (repo / DIRECTORY / "manifest.json").is_file()
    assert git(origin, "rev-parse", "main").strip() == identity.git_sha
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github/workflows/encoder-comparison.yml").read_text()
    )
    steps = workflow["jobs"]["collect"]["steps"]
    assert any("pip install --quiet -e ." in step.get("run", "") for step in steps)
    assert any("encoder_publish.py run" in step.get("run", "") for step in steps)
    publisher = next(step for step in steps if "encoder_publish.py land" in step.get("run", ""))
    assert publisher["if"] == "inputs.commit_readings"
    assert not any("git add" in step.get("run", "") or "git push" in step.get("run", "") for step in steps)
    artifact = next(step for step in steps if step.get("with", {}).get("name") == "encoder-comparison")
    assert artifact["if"] == "always()"


@pytest.mark.parametrize("directory, selected", [
    ("corpus", "candidate"), ("state/raw", "candidate"),
    ("corpus/../other", "candidate"), (DIRECTORY, "unknown"),
])
def test_invalid_declarations_fail_before_any_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str, selected: str,
) -> None:
    _, repo, _ = comparison(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        encoder_publish.declarations(repo, directory, selected)
