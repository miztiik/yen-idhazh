"""How does one gardener shard land its one commit on main, however many shards race it?

This is the entry point a wake's shard runs: it reads the commit this checkout
is at, which of the shard's owned folders that commit holds, adds to a sparse
checkout the folders the complement task sweeps - which only the commit can
name - weighs every owned folder there, runs the shard through
`idhazh.gardener.runner`, and lands what the runner hands back. It sits here
rather than in the package because landing and reading the commit run git, and
nothing under `backend/idhazh/` may start a process
(`backend/tests/test_canaries.py`): the package that reads the open web holds no
machinery an injected instruction could use to act.

    python backend/utilities/gardener_publish.py NAME | --shard N --run-id R --attempt A

The work happens once, before `publish` is called. What is left is to stage
exactly what the shard wrote and deleted, commit it, and push - and to do that
again against a newer tip when another shard pushed first. Each try starts from
`origin/main` as it is now, so a lost race costs one fetch and one commit rather
than a merge.

**The record decides whether the shard has already landed.** Every shard writes
one record under the gardener's own ledger, and its bytes are unique to the
shard. If `origin/main` already holds that path with those bytes, an earlier try
landed and this one stops with success; the same path with other bytes is two
runs claiming one identity, and that is exit 2.

**Three checks run over what was staged, before every commit.** Nothing outside
the shard's writes and deletions is staged. Every write is staged, unless its
bytes already equal `origin/main`'s, which is a write that already landed. And
a deletion that staged nothing is an error only while the path still exists on
`origin/main`, because a path already gone is a deletion somebody finished.

The exit codes, and the order that picks the worst, are
`idhazh.gardener.outcome`'s.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Final

from idhazh.config import GardenerSettings
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import runner
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_KEPT_LOSING,
    Outcome,
    Shard,
    worst,
)
from idhazh.ledger import STATE_DIRNAME

#: The one identity every commit in this repository carries. The same two values
#: `backend/utilities/commit_and_push.py` sets, which a test holds in step.
COMMITTER_NAME: Final = "miztiik"
COMMITTER_EMAIL: Final = "miztiik@users.noreply.github.com"

#: The branch every shard lands on, and the remote it is fetched from.
REMOTE: Final = "origin"
BRANCH: Final = "main"

#: The longest one wait between two tries, in seconds.
MAX_BACKOFF_SECONDS: Final = 8

#: Git's switch that stops a partial clone downloading an object it lacks. The
#: weighing read sets it, so a folder outside the checkout fails instead.
NO_LAZY_FETCH_ENV: Final = "GIT_NO_LAZY_FETCH"


class Checkout:
    """The git commands the loop runs, all of them in one checkout."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self._repo, capture_output=True, text=True, check=False
        )

    def git(self, *args: str) -> str:
        """Run one command and hand back what it printed, or raise with what it said."""
        done = self._run(*args)
        if done.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout

    def git_ok(self, *args: str) -> bool:
        """Run one command and say whether it worked, for the ones that may fail."""
        return self._run(*args).returncode == 0

    def head(self) -> str | None:
        """The commit this checkout is at, or None when it is not a git checkout."""
        done = self._run("rev-parse", "--verify", "--quiet", "HEAD")
        return done.stdout.strip() if done.returncode == 0 else None

    def remote_blob(self, path: str) -> str | None:
        """The object `origin/main` holds at this path, or None when it holds nothing there."""
        done = self._run("rev-parse", "--verify", "--quiet", f"{REMOTE}/{BRANCH}:{path}")
        return done.stdout.strip() if done.returncode == 0 else None

    def local_blob(self, path: str) -> str | None:
        """The object this checkout's file at this path would be, or None when there is none."""
        if not (self._repo / path).is_file():
            return None
        return self.git("hash-object", "--", path).strip()

    def staged_names(self) -> set[str]:
        """Every path the next commit would change, a deletion always named as itself.

        Rename detection is off. A shard that deletes a file and writes one much
        like it - a fold replacing a day's one writer file with its settled file -
        is a pair git would otherwise report as one move, naming only the new
        path, so the deletion would read as unstaged and the shard would refuse
        to land.
        """
        listed = self.git("diff", "--cached", "--name-only", "--no-renames", "-z")
        return set(listed.split("\0")) - {""}

    def committed_folders(self, owned: Sequence[str]) -> frozenset[str]:
        """Which of these folders the commit holds, and every folder directly under `state/`.

        One `git ls-tree` over the object database, so a folder a sparse checkout
        left out is still seen, and nothing recurses: the cost is one entry per
        folder named and one per child of `state/`, whatever those folders hold.
        `state/` carries its slash, which lists what is inside it; an owned folder
        carries none, which names the folder itself - with a slash it would list
        its children, and the folder would read as absent. A child of `state/`
        that holds a named folder is listed as that folder and not as itself,
        because git walks into it to reach the name - so the sweep never reads a
        folder holding another task's folder as its own to take.
        """
        listed = self.git(
            "ls-tree",
            "-d",
            "--name-only",
            "-z",
            "HEAD",
            "--",
            f"{STATE_DIRNAME}/",
            *(folder.rstrip("/") for folder in owned),
        )
        return frozenset(listed.split("\0")) - {""}

    def is_sparse(self) -> bool:
        """Whether this checkout holds only some folders, as a shard's does."""
        return self._run("config", "--bool", "core.sparseCheckout").stdout.strip() == "true"

    def add_to_the_checkout(self, folders: Sequence[str]) -> str | None:
        """Widen a sparse checkout by these folders; None, or what git said when it refused.

        The names go on standard input, so none of them can be read as an option,
        and a partial clone downloads the folders' files in one request.
        """
        done = subprocess.run(
            ["git", "sparse-checkout", "add", "--stdin"],
            cwd=self._repo,
            input="".join(f"{folder}\n" for folder in folders),
            capture_output=True,
            text=True,
            check=False,
        )
        return None if done.returncode == 0 else done.stderr.strip()

    def cone_bytes(self, owned: Sequence[str]) -> dict[str, int]:
        """What each owned folder weighs at the commit, in bytes. A folder it lacks weighs 0.

        One `git ls-tree -r -l` over the commit, so a file a task writes cannot move
        the number and nothing the checkout holds beside the commit is counted. Run
        with lazy fetching off: every file named sits inside the shard's checkout,
        and a folder outside it would otherwise download every file it holds just
        to be weighed. Git prints such a file's size as `BAD` instead, and it is
        left out: its folder is one the checkout lacks, so the runner fails the
        task that owns it.
        """
        weights = dict.fromkeys(owned, 0)
        if not owned:
            return weights
        done = subprocess.run(
            ["git", "ls-tree", "-r", "-l", "-z", "HEAD", "--", *owned],
            cwd=self._repo,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, NO_LAZY_FETCH_ENV: "1"},
        )
        if done.returncode != 0:
            raise RuntimeError(f"git ls-tree -r -l failed: {done.stderr.strip()}")
        for entry in done.stdout.split("\0"):
            if not entry:
                continue
            described, path = entry.split("\t", 1)
            size = described.split()[3]
            folder = next(
                (held for held in owned if path == held or path.startswith(f"{held}/")), None
            )
            if folder is not None and size.isdigit():
                weights[folder] += int(size)
        return weights


def sleep_with_jitter(attempt: int, *, sleep: Callable[[float], None] = time.sleep) -> None:
    """Wait a random time before try `attempt + 1`, longer after each loss, never past the cap."""
    sleep(random.uniform(0, min(2 ** (attempt - 1), MAX_BACKOFF_SECONDS)))


def _refuse_a_directory(shard: Shard, repo: Path) -> str | None:
    """A deletion names one file. A folder here would stage everything under it."""
    for path in sorted(shard.deleted_paths):
        if (repo / path).is_dir():
            return f"{path} is a folder, and a shard deletes files one at a time"
    return None


def _what_staging_missed(shard: Shard, checkout: Checkout) -> str | None:
    """The three checks over what was staged, or None when the index is exactly the shard."""
    staged = checkout.staged_names()
    stray = sorted(staged - shard.written_paths - shard.deleted_paths)
    if stray:
        return f"{', '.join(stray)} staged, and this shard neither wrote nor deleted it"
    for path in sorted(shard.written_paths - staged):
        mine = checkout.local_blob(path)
        if mine is None or mine != checkout.remote_blob(path):
            return f"{path} was written and did not stage"
    for path in sorted(shard.deleted_paths - staged):
        if checkout.remote_blob(path) is not None:
            return f"{path} was deleted, did not stage, and {REMOTE}/{BRANCH} still holds it"
    return None


def publish(
    shard: Shard,
    *,
    attempts: int,
    repo: Path,
    say: Callable[[str], None] = print,
) -> int:
    """Stage, commit and push this shard, trying again on a newer tip, `attempts` times at most."""
    refused = _refuse_a_directory(shard, repo)
    if refused is not None:
        say(f"shard {shard.index}: {refused}")
        return EXIT_INTEGRITY
    checkout = Checkout(repo)
    for attempt in range(1, attempts + 1):
        checkout.git("fetch", "--quiet", REMOTE, BRANCH, "--depth=1")
        landed = checkout.remote_blob(shard.record_path)
        if landed is not None:
            if landed == checkout.local_blob(shard.record_path):
                say(f"shard {shard.index}: already on {BRANCH}, try {attempt}")
                return EXIT_OK
            say(
                f"shard {shard.index}: {shard.record_path} is on {BRANCH} with other bytes, "
                "so two runs claimed one record"
            )
            return EXIT_INTEGRITY
        checkout.git("reset", "--quiet", "--mixed", f"{REMOTE}/{BRANCH}")
        for path in sorted(shard.written_paths):
            checkout.git_ok("add", "--sparse", "--", path)
        for path in sorted(shard.deleted_paths):
            checkout.git_ok("rm", "--quiet", "--cached", "--sparse", "--ignore-unmatch", "--", path)
        missed = _what_staging_missed(shard, checkout)
        if missed is not None:
            say(f"shard {shard.index}: {missed}")
            return EXIT_INTEGRITY
        checkout.git(
            "-c",
            f"user.name={COMMITTER_NAME}",
            "-c",
            f"user.email={COMMITTER_EMAIL}",
            "commit",
            "--quiet",
            "-m",
            shard.message,
        )
        if checkout.git_ok("push", "--quiet", REMOTE, f"HEAD:refs/heads/{BRANCH}"):
            say(f"shard {shard.index}: landed on {BRANCH}, try {attempt} of {attempts}")
            return EXIT_OK
        say(f"shard {shard.index}: try {attempt} of {attempts} lost the push")
        if attempt < attempts:
            sleep_with_jitter(attempt)
    return EXIT_PUSH_KEPT_LOSING


def find_the_swept_folders(
    names: Sequence[str],
    settings: GardenerSettings,
    repo_root: Path,
    committed: frozenset[str],
) -> list[str]:
    """Every folder the commit holds that this shard's complement task sweeps.

    The plan job cannot name them: they are the folders under `state/` that no
    declaration and no ledger claims, and only the commit says what is there.
    """
    swept: set[str] = set()
    for name in names:
        if settings.tasks[name].owns is None:
            folders = runner.folders_of(name, settings.tasks, repo_root, committed)
            swept.update(folders.walk, folders.missing)
    return sorted(swept)


def run_and_land(
    names: Sequence[str],
    *,
    settings: GardenerSettings,
    repo_root: Path,
    run_id: str,
    attempt: int,
    shard: int,
    package: ModuleType = shipped_tasks,
    clock: Callable[[], datetime] = runner.utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Read the commit, run the shard, and land what it hands back; the worst code wins.

    A sparse checkout is widened by the complement task's folders before
    anything is weighed or run, and by nothing else: a declared folder the
    checkout lacks means the plan was wrong, so its task still fails.
    """
    checkout = Checkout(repo_root)
    sha = checkout.head()
    if sha is None:
        say(f"shard {shard}: {repo_root.name} is not a git checkout, so no record can name it")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    owned = sorted({folder for name in names for folder in settings.tasks[name].owns or ()})
    committed = checkout.committed_folders(owned)
    swept = find_the_swept_folders(names, settings, repo_root, committed)
    lacking = [folder for folder in swept if not (repo_root / folder).is_dir()]
    if lacking and checkout.is_sparse():
        refused = checkout.add_to_the_checkout(lacking)
        say(
            f"shard {shard}: added {', '.join(lacking)} to the checkout"
            if refused is None
            else f"shard {shard}: could not add {', '.join(lacking)} to the checkout: {refused}"
        )
    ran = runner.run(
        names,
        settings=settings,
        repo_root=repo_root,
        run_id=run_id,
        attempt=attempt,
        shard=shard,
        git_sha=sha,
        committed_folders=committed,
        cone_bytes=checkout.cone_bytes([*owned, *swept]),
        package=package,
        clock=clock,
        say=say,
    )
    if ran.landing is None:
        return ran
    pushed = publish(ran.landing, attempts=settings.config.attempts, repo=repo_root, say=say)
    return dataclasses.replace(ran, exit_code=worst(ran.exit_code, pushed))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gardener_publish.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gardener_cli.add_the_run(parser)
    args = parser.parse_args(argv)
    settings = gardener_cli.settings_or_none(args.config)
    if settings is None:
        return EXIT_INTEGRITY
    names, shard = gardener_cli.chosen(settings, args, parser)
    outcome = run_and_land(
        names,
        settings=settings,
        repo_root=args.repo_root,
        run_id=args.run_id,
        attempt=args.attempt,
        shard=shard,
    )
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
