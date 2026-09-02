"""Report which worktrees on this box are finished, and remove them on request.

The symptom this exists for. Every row of a plan takes its own worktree, and the
closing step that removes it is the one step a worker killed mid-row never
reaches. Measured 2026-09-02 on a developer box: 38 sibling directories holding
156,482 files, every one of them a row whose pull request had merged days
earlier. Nothing removes them, because `git worktree prune` only clears the
admin entry for a directory that is ALREADY gone - it never deletes a checkout.

The rule is three signals, and it needs all three. A squash merge leaves the
branch a non-ancestor of the trunk, so ancestry cannot answer "did this land";
that is why the pull request is asked. And a branch with no pull request at all
is pending work rather than stale work - twice here it held a real fix nobody
had proposed yet. So a tree is removable only when its pull request is MERGED,
its remote branch is gone, and its own tree is clean. A detached worktree is the
one case ancestry does settle on its own.

    python backend/utilities/sweep_worktrees.py            # report, change nothing
    python backend/utilities/sweep_worktrees.py --remove   # remove what it names

Every refusal prints its reason, so a tree that stays says why it stayed. The
default is a report: this deletes checkouts, and a sibling agent creates one
between any two commands.

What it deliberately does not do. It does not stop the processes that hold a
dead tree's files open, and there are two: an `esbuild` service running from
inside the tree, and the editor's language server, which loads a native module
out of every worktree it has ever indexed and can hold fourteen at once. Killing
the first is safe and killing the second is somebody's editor, so the difference
is not one an unattended sweep should decide. It prints the files it could not
delete instead; the recipe for both is in docs/reference/agent-notes.md.

It reads no configuration and imports nothing from `idhazh`, so it runs from a
fresh clone with any supported Python and no install. Every knob is a flag whose
default is a constant below.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# What a finished branch is measured against. A flag, because a fresh clone in a
# test has no remote and a project may not call its trunk this.
TRUNK: Final = "origin/main"

# The remote whose branch list settles the second signal.
REMOTE: Final = "origin"

# The pull request state that means the row landed. `gh` spells it upper case.
MERGED: Final = "MERGED"


@dataclass(frozen=True)
class Worktree:
    """One checkout `git worktree list` names."""

    path: Path
    head: str
    branch: str | None


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str


@dataclass(frozen=True)
class Facts:
    """What was read about one worktree. `None` anywhere means "could not read"."""

    tree: Worktree
    uncommitted: int | None
    remote_branch: bool | None
    in_trunk: bool | None
    pull_request: PullRequest | None
    pull_request_read: bool


@dataclass(frozen=True)
class Verdict:
    remove: bool
    reason: str


def decide(facts: Facts) -> Verdict:
    """Judge one worktree. Pure, so the rule can be tested without a repository."""
    tree = facts.tree
    if facts.uncommitted is None:
        return Verdict(False, "its own git status could not be read")
    if facts.uncommitted > 0:
        noun = "file" if facts.uncommitted == 1 else "files"
        return Verdict(False, f"{facts.uncommitted} uncommitted {noun}")

    if tree.branch is None:
        if facts.in_trunk is None:
            return Verdict(False, "detached, and the trunk could not be read")
        if facts.in_trunk:
            return Verdict(True, "detached, and its commit is already on the trunk")
        return Verdict(False, "detached at a commit the trunk does not carry")

    if not facts.pull_request_read:
        return Verdict(False, f"the pull request state of {tree.branch} could not be read")
    if facts.pull_request is None:
        return Verdict(False, f"no pull request was ever opened for {tree.branch}")
    if facts.pull_request.state != MERGED:
        state = facts.pull_request.state.lower()
        return Verdict(False, f"pull request {facts.pull_request.number} is {state}")
    if facts.remote_branch is None:
        return Verdict(False, "the remote branch list could not be read")
    if facts.remote_branch:
        return Verdict(False, f"{tree.branch} is still on the remote")
    return Verdict(
        True,
        f"pull request {facts.pull_request.number} merged, "
        f"{tree.branch} is gone from the remote, and the tree is clean",
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


def read_worktrees(repo: Path) -> list[Worktree]:
    """Every worktree except the main one, which is the first block git prints."""
    done = _git(repo, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        raise SystemExit(f"git worktree list failed: {done.stderr.strip()}")

    trees: list[Worktree] = []
    for block in done.stdout.split("\n\n"):
        path: Path | None = None
        head = ""
        branch: str | None = None
        bare = False
        for line in block.splitlines():
            entry = line.strip()
            if entry.startswith("worktree "):
                path = Path(entry.removeprefix("worktree "))
            elif entry.startswith("HEAD "):
                head = entry.removeprefix("HEAD ")
            elif entry.startswith("branch refs/heads/"):
                branch = entry.removeprefix("branch refs/heads/")
            elif entry == "bare":
                bare = True
        if path is not None and not bare:
            trees.append(Worktree(path=path, head=head, branch=branch))
    return trees[1:]


def read_uncommitted(tree: Path) -> int | None:
    done = _git(tree, "status", "--porcelain")
    if done.returncode != 0:
        return None
    return len([line for line in done.stdout.splitlines() if line.strip()])


def read_in_trunk(repo: Path, head: str, trunk: str) -> bool | None:
    done = _git(repo, "merge-base", "--is-ancestor", head, trunk)
    if done.returncode in (0, 1):
        return done.returncode == 0
    return None


def read_remote_branch(repo: Path, branch: str, remote: str) -> bool | None:
    done = _git(repo, "ls-remote", "--heads", remote, branch)
    if done.returncode != 0:
        return None
    return bool(done.stdout.strip())


def read_pull_request(repo: Path, branch: str) -> PullRequest | None:
    """The pull request for this branch, preferring a merged one. Raises if `gh` cannot say."""
    try:
        done = subprocess.run(
            ["gh", "pr", "list", "--state", "all", "--head", branch, "--json", "number,state"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise LookupError(str(error)) from error
    if done.returncode != 0:
        raise LookupError(done.stderr.strip() or "gh pr list failed")

    raw: object = json.loads(done.stdout or "[]")
    if not isinstance(raw, list):
        raise LookupError("gh did not return a list of pull requests")
    entries = [entry for entry in raw if isinstance(entry, dict)]
    merged = [entry for entry in entries if entry.get("state") == MERGED]
    chosen = merged[0] if merged else (entries[0] if entries else None)
    if chosen is None:
        return None
    number = chosen.get("number")
    state = chosen.get("state")
    if not isinstance(number, int) or not isinstance(state, str):
        raise LookupError("gh returned a pull request with no number or state")
    return PullRequest(number=number, state=state)


def read_facts(repo: Path, tree: Worktree, trunk: str, remote: str, *, ask_gh: bool) -> Facts:
    pull_request: PullRequest | None = None
    read = False
    if tree.branch is not None and ask_gh:
        try:
            pull_request = read_pull_request(repo, tree.branch)
            read = True
        except LookupError:
            read = False
    return Facts(
        tree=tree,
        uncommitted=read_uncommitted(tree.path),
        remote_branch=(
            None if tree.branch is None else read_remote_branch(repo, tree.branch, remote)
        ),
        in_trunk=read_in_trunk(repo, tree.head, trunk),
        pull_request=pull_request,
        pull_request_read=read,
    )


def remove(repo: Path, tree: Worktree) -> list[Path]:
    """Remove one worktree and return the files that survived it.

    `git worktree remove` deregisters the worktree even when it cannot delete the
    directory - it exits 255 and the entry is gone either way - so its exit code
    is deliberately not checked.
    """
    _git(repo, "worktree", "remove", "--force", "--", str(tree.path))
    _git(repo, "worktree", "prune")
    if tree.path.exists():
        shutil.rmtree(tree.path, ignore_errors=True)
    if not tree.path.exists():
        return []
    return sorted(path for path in tree.path.rglob("*") if path.is_file())


def sweep(
    repo: Path, *, trunk: str, remote: str, ask_gh: bool, remove_finished: bool
) -> list[tuple[Facts, Verdict]]:
    judged: list[tuple[Facts, Verdict]] = []
    for tree in read_worktrees(repo):
        facts = read_facts(repo, tree, trunk, remote, ask_gh=ask_gh)
        verdict = decide(facts)
        judged.append((facts, verdict))
        if verdict.remove and remove_finished:
            for survivor in remove(repo, tree):
                print(f"  a live process still holds {survivor}")
    return judged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--trunk", default=TRUNK)
    parser.add_argument("--remote", default=REMOTE)
    parser.add_argument(
        "--remove", action="store_true", help="remove the worktrees this names; off by default"
    )
    parser.add_argument(
        "--no-pull-requests",
        action="store_true",
        help="do not ask gh, which keeps every branch worktree",
    )
    args = parser.parse_args()

    judged = sweep(
        args.repo,
        trunk=args.trunk,
        remote=args.remote,
        ask_gh=not args.no_pull_requests,
        remove_finished=args.remove,
    )
    for facts, verdict in judged:
        if not verdict.remove:
            label = "keep"
        else:
            label = "removed" if args.remove else "would remove"
        print(f"{label:<13} {facts.tree.path.name:<24} {verdict.reason}")

    removable = sum(1 for _, verdict in judged if verdict.remove)
    noun = "worktree" if len(judged) == 1 else "worktrees"
    print(f"{len(judged)} {noun}, {removable} finished")
    if removable and not args.remove:
        print("re-run with --remove to remove them")


if __name__ == "__main__":
    main()
