"""Tests for the worktree sweep.

The decision is pure and the collection is real. `decide` is exercised directly
over crafted facts, because the rule is the thing that must not drift; the
end-to-end arms build an actual repository with actual worktrees in `tmp_path`
and let the tool remove one, because a stub of `git worktree remove` would pass
against a tool that never removed anything.

Nothing here reaches the network. `ask_gh=False` is a real flag - it is what a
box with no `gh` gets - and every arm that uses it asserts the SAFE answer, so
the test cannot pass by accident on a machine that happens to be authenticated.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

import pytest

from utilities.sweep_worktrees import (
    Facts,
    PullRequest,
    Worktree,
    decide,
    read_worktrees,
    sweep,
)

TRUNK: Final = "main"
REMOTE: Final = "origin"

# A frozen record, so one instance is a safe default for the builder below.
LANDED: Final = PullRequest(number=7, state="MERGED")


def _run(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return done.stdout


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    root.mkdir()
    _run(root, "init", "-b", TRUNK)
    _run(root, "config", "user.email", "sweep@example.test")
    _run(root, "config", "user.name", "Sweep Test")
    (root / "README.md").write_text("one\n", encoding="ascii")
    _run(root, "add", "README.md")
    _run(root, "commit", "-m", "one")
    return root


def _facts(
    *,
    branch: str | None = "feat/a-row",
    uncommitted: int | None = 0,
    remote_branch: bool | None = False,
    in_trunk: bool | None = False,
    pull_request: PullRequest | None = LANDED,
    pull_request_read: bool = True,
) -> Facts:
    return Facts(
        tree=Worktree(path=Path("yi-p07"), head="abc123", branch=branch),
        uncommitted=uncommitted,
        remote_branch=remote_branch,
        in_trunk=in_trunk,
        pull_request=pull_request,
        pull_request_read=pull_request_read,
    )


def test_a_merged_branch_whose_remote_is_gone_and_whose_tree_is_clean_goes() -> None:
    verdict = decide(_facts())
    assert verdict.remove
    assert "7" in verdict.reason


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (_facts(uncommitted=3), "3 uncommitted files"),
        (_facts(uncommitted=1), "1 uncommitted file"),
        (_facts(uncommitted=None), "could not be read"),
        (_facts(remote_branch=True), "still on the remote"),
        (_facts(remote_branch=None), "could not be read"),
        (_facts(pull_request=None), "no pull request was ever opened"),
        (_facts(pull_request=PullRequest(number=7, state="OPEN")), "is open"),
        (_facts(pull_request=PullRequest(number=7, state="CLOSED")), "is closed"),
        (_facts(pull_request_read=False), "could not be read"),
        (_facts(branch=None, in_trunk=False), "the trunk does not carry"),
        (_facts(branch=None, in_trunk=None), "could not be read"),
    ],
    ids=[
        "three-uncommitted",
        "one-uncommitted",
        "status-unreadable",
        "remote-branch-alive",
        "remote-unreadable",
        "no-pull-request",
        "pull-request-open",
        "pull-request-closed",
        "gh-unreadable",
        "detached-off-trunk",
        "trunk-unreadable",
    ],
)
def test_every_reason_to_keep_a_worktree_says_which_one_it_is(
    facts: Facts, expected: str
) -> None:
    verdict = decide(facts)
    assert not verdict.remove
    assert expected in verdict.reason


def test_a_detached_worktree_already_on_the_trunk_goes() -> None:
    verdict = decide(_facts(branch=None, in_trunk=True))
    assert verdict.remove
    assert "detached" in verdict.reason


def test_the_main_worktree_is_never_a_candidate(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    assert read_worktrees(root) == []

    _run(root, "worktree", "add", "--detach", str(tmp_path / "yi-a"), TRUNK)
    named = read_worktrees(root)
    assert [tree.path.name for tree in named] == ["yi-a"]


def test_a_finished_worktree_is_removed_and_deregistered(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    spare = tmp_path / "yi-finished"
    _run(root, "worktree", "add", "--detach", str(spare), TRUNK)
    assert spare.exists()

    judged = sweep(root, trunk=TRUNK, remote=REMOTE, ask_gh=False, remove_finished=True)

    assert [verdict.remove for _, verdict in judged] == [True]
    assert not spare.exists()
    assert "yi-finished" not in _run(root, "worktree", "list")


def test_a_worktree_with_uncommitted_work_survives_the_sweep(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    spare = tmp_path / "yi-busy"
    _run(root, "worktree", "add", "--detach", str(spare), TRUNK)
    (spare / "half-written.md").write_text("not finished\n", encoding="ascii")

    judged = sweep(root, trunk=TRUNK, remote=REMOTE, ask_gh=False, remove_finished=True)

    (_, verdict) = judged[0]
    assert not verdict.remove
    assert verdict.reason == "1 uncommitted file"
    assert spare.exists()


def test_a_branch_worktree_survives_when_the_pull_request_cannot_be_read(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    spare = tmp_path / "yi-branch"
    _run(root, "worktree", "add", "-b", "feat/a-row", str(spare), TRUNK)

    judged = sweep(root, trunk=TRUNK, remote=REMOTE, ask_gh=False, remove_finished=True)

    (_, verdict) = judged[0]
    assert not verdict.remove
    assert "feat/a-row" in verdict.reason
    assert spare.exists()
