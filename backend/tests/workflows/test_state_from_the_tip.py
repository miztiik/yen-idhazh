"""Does a bounded import preserve code, the shared index, sparse patterns and foreign work?"""

from pathlib import Path

import pytest
from gardener._garden import an_origin, git, quiet_git, write

from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError
from utilities.take_state_from_the_tip import take_inputs

OLD = "state/raw/item-health/2026/09/21/old.jsonl"
NEW = "state/compact/item-health/daily/2026/09/21.parquet"
INPUTS = ("state/raw/item-health/2026/09/21", NEW)


def stale_checkout(tmp_path: Path) -> tuple[Path, Path, str, str]:
    origin, repo = an_origin(
        tmp_path, {OLD: "completed source\n", NEW: "old head\n", "outside": "original\n"}
    )
    trigger = git(repo, "rev-parse", "HEAD").strip()
    ahead = tmp_path / "ahead"
    git(tmp_path, "clone", "--quiet", str(origin), str(ahead))
    (ahead / OLD).unlink()
    write(ahead / NEW, "fresh head\n")
    write(ahead / "outside", "foreign commit\n")
    git(ahead, "add", "--all")
    git(ahead, "commit", "--quiet", "-m", "named source advances")
    git(ahead, "push", "--quiet", "origin", "HEAD:main")
    return origin, repo, trigger, git(ahead, "rev-parse", "HEAD").strip()


def test_source_proven_deletion_and_named_import_do_not_change_head_or_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, repo, trigger, fresh = stale_checkout(tmp_path)
    write(repo / "foreign-staged", "keep this\n")
    git(repo, "add", "foreign-staged")
    write(repo / "state/raw/unrelated/local", "keep foreign state\n")
    before = (repo / ".git/index").read_bytes()
    assert take_inputs(repo, INPUTS) == fresh
    assert not (repo / OLD).exists()
    assert (repo / NEW).read_bytes() == b"fresh head\n"
    assert (repo / "outside").read_bytes() == b"original\n"
    assert (repo / "state/raw/unrelated/local").read_bytes() == b"keep foreign state\n"
    assert (repo / ".git/index").read_bytes() == before
    assert git(repo, "rev-parse", "HEAD").strip() == trigger
    assert git(repo, "rev-parse", "refs/worktree/publication-input-state").strip() == fresh
    # An imported deletion is baseline data, not a change to the checkout's index.
    assert OLD in git(repo, "ls-files", "--", OLD)


@pytest.mark.parametrize("staged", [False, True])
def test_a_foreign_named_change_is_refused_before_any_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    staged: bool,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, repo, _, _ = stale_checkout(tmp_path)
    write(repo / NEW, "foreign input\n")
    if staged:
        git(repo, "add", NEW)
    index = (repo / ".git/index").read_bytes()
    with pytest.raises(IntegrityError, match="foreign"):
        take_inputs(repo, INPUTS)
    assert (repo / OLD).exists()
    assert (repo / NEW).read_bytes() == b"foreign input\n"
    assert (repo / ".git/index").read_bytes() == index


def test_a_failed_blob_download_leaves_the_complete_previous_input_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, repo, _, _ = stale_checkout(tmp_path)
    original = Repository.blob

    def fail(self: Repository, oid: str, *, fetches: bool = False) -> bytes:
        data = original(self, oid, fetches=fetches)
        if data == b"fresh head\n":
            raise OSError("named download failed")
        return data

    monkeypatch.setattr(Repository, "blob", fail)
    with pytest.raises(OSError, match="download failed"):
        take_inputs(repo, INPUTS)
    assert (repo / OLD).read_bytes() == b"completed source\n"
    assert (repo / NEW).read_bytes() == b"old head\n"
    assert not list((repo / "backend/var/publication").glob("inputs-*"))
