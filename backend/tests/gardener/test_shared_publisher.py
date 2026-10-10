"""Does a private candidate contain only independently permitted, confirmed bytes?"""

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from utilities.publication_git import Repository
from utilities.publication_request import Delete, PublicationRequest, Write
from utilities.publish_to_repo import Status, publish
from utilities.push_retry import PushRetry

from ._garden import a_hook, an_origin, git, on_origin, quiet_git, write

RETRY = PushRetry({"default": 300}, .001, .001, 1)
OUTPUT = "state/raw/seen/2026/10/09/result.json"


def request(repo: Path, *, paths: tuple[str, ...] = (OUTPUT,)) -> PublicationRequest:
    repository = Repository(repo)
    source = git(repo, "rev-parse", "HEAD").strip()
    identity = WriterIdentity(
        run_id="2026-10-09-123", attempt=1, job=ServerJob.PLAN, shard=0,
        producer="tests.publisher", git_sha=source,
    )
    return PublicationRequest(
        identity, "completed", source, ("state/raw/seen",), ("state/raw/seen",),
        {path: Write(hashlib.sha256((repo / path).read_bytes()).hexdigest(),
                     repository.entry(source, path), True) for path in paths},
    )


def test_foreign_index_and_worktree_are_unchanged(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"foreign.txt": "before\n"})
    write(repo / "foreign.txt", "prestaged\n")
    git(repo, "add", "foreign.txt")
    before = git(repo, "rev-parse", "HEAD"), (repo / ".git" / "index").read_bytes()
    write(repo / OUTPUT, "completed\n")
    result = publish(request(repo), repo=repo, retry=RETRY)
    assert result.status is Status.LANDED
    assert result.push_count == 1
    assert on_origin(origin, OUTPUT) == "completed\n"
    assert on_origin(origin, "foreign.txt") == "before\n"
    assert before == (git(repo, "rev-parse", "HEAD"), (repo / ".git" / "index").read_bytes())
    assert (repo / "foreign.txt").read_text() == "prestaged\n"
    assert git(origin, "rev-parse", "main^").strip() == result.base


@pytest.mark.parametrize("permission", ["state", "state/raw", "state/compact", "state/raw/see"])
def test_broad_and_prefix_permissions_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                             permission: str) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"foreign.txt": "before\n"})
    write(repo / OUTPUT, "completed\n")
    before = git(origin, "rev-parse", "main")
    result = publish(replace(request(repo), write_permissions=(permission,)),
                     repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert result.push_count == 0
    assert git(origin, "rev-parse", "main") == before


def test_same_identity_with_different_committed_bytes_refuses(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {OUTPUT: "committed\n"})
    write(repo / OUTPUT, "completed\n")
    result = publish(request(repo), repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert on_origin(origin, OUTPUT) == "committed\n"


def test_matching_record_does_not_prove_other_operations(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {OUTPUT: "record\n"})
    second = OUTPUT + ".second"
    write(repo / second, "missing operation\n")
    result = publish(request(repo, paths=(OUTPUT, second)), repo=repo, retry=RETRY)
    assert result.status is Status.LANDED
    assert on_origin(origin, second) == "missing operation\n"


def test_filters_cannot_change_confirmed_bytes(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {".gitattributes": "*.json text eol=lf\n"})
    (repo / OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    (repo / OUTPUT).write_bytes(b"completed\r\n")
    result = publish(request(repo), repo=repo, retry=RETRY)
    assert result.status is Status.INTEGRITY_REFUSED
    assert "filter" in result.detail
    assert on_origin(origin, OUTPUT) is None


def test_actual_push_limit_and_refused_outcome(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"foreign.txt": "before\n"})
    write(repo / OUTPUT, "completed\n")
    a_hook(origin, "exit 1")
    result = publish(request(repo), repo=repo, retry=RETRY, max_pushes=2)
    assert result.status is Status.REFUSED
    assert result.push_count == 2
    assert result.candidate and result.base and result.observed_tip


def test_stale_deletion_does_not_remove_newer_bytes(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {OUTPUT: "old\n"})
    initial = request(repo)
    baseline = Repository(repo).entry(initial.source_tip, OUTPUT)
    assert baseline is not None
    (repo / OUTPUT).unlink()
    deletion = replace(initial, writes={}, deletions={OUTPUT: Delete(baseline, True)})
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / OUTPUT, "new\n")
    git(mover, "add", OUTPUT)
    git(mover, "-c", "user.name=mover", "-c", "user.email=mover@example.invalid",
        "commit", "--quiet", "-m", "new")
    git(mover, "push", "--quiet", "origin", "HEAD:main")
    result = publish(deletion, repo=repo, retry=RETRY)
    assert result.status is Status.STALE
    assert result.refusal_paths == (OUTPUT,)
    assert on_origin(origin, OUTPUT) == "new\n"
