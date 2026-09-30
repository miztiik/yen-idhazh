"""How does one gardener shard land its one commit on main, however many shards race it?

This is the entry point a wake's shard runs. Its checkout holds only the code
and config it runs. It reads the commit this checkout is at, which of the
folders its tasks own or read that commit holds, and the name and size of every
file under them - the complement task's folders included, which only the commit
can name - and downloads none of those files. It runs the shard through
`idhazh.gardener.runner`, whose tasks fetch only the folders they read, and
lands what the runner hands back. It sits here rather than in the package
because landing and reading the commit run git, and nothing under
`backend/idhazh/` may start a process (`backend/tests/test_canaries.py`): the
package that reads the open web holds no machinery an injected instruction
could use to act.

    python backend/utilities/gardener_publish.py NAME | --shard N --run-id R --attempt A

**Only a named fetch downloads a file.** Every git call runs with lazy fetching
off but the one that widens the checkout for a task, so a call that would have
downloaded a file the clone lacks fails instead of paying for it quietly. A
file's size is git's where the clone holds the file. For one it never
downloaded, git prints no size, so GitHub's trees API is asked, one request a
listed folder, and its answer is matched to git's names by blob id.

The work happens once, before `publish` is called. What is left is to build a
commit of exactly what the shard wrote and deleted, and push it - and to do that
again against a newer tip when another shard pushed first. Each try starts from
`origin/main` as it is now, so a lost race costs one fetch and one commit rather
than a merge.

**The commit is built in an index of its own.** Each try reads `origin/main`'s
tree into a separate index file, sets each write's new content there and takes
each deletion out by its name, so a file the checkout never downloaded is
deleted as easily as one it holds, and the checkout's own index is never
expanded. The push sends whole objects rather than deltas against files the
clone lacks, which it could only compute by downloading them.

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
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh.config import GardenerSettings
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import github_collections, runner
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.file_listing import (
    FileListing,
    TreeEntry,
    TreeReader,
    parse_tree,
    sizes_from_github,
)
from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_KEPT_LOSING,
    EXIT_TASK_FAILED,
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

#: Git's switch that stops a partial clone downloading an object it lacks. Every
#: call here sets it but the one that widens the checkout for a task.
NO_LAZY_FETCH_ENV: Final = "GIT_NO_LAZY_FETCH"

#: Git's switch that points a command at an index file other than the checkout's.
INDEX_FILE_ENV: Final = "GIT_INDEX_FILE"

#: The index file each try builds its commit in, inside the checkout's git folder.
COMMIT_INDEX: Final = "gardener-commit.index"

#: What every command on that index runs under. The checkout is sparse, and git
#: applies its patterns to any index it reads - which reads files the clone never
#: downloaded, and with lazy fetching off, fails. The commit's index is whole.
_A_WHOLE_INDEX: Final = ("-c", "core.sparseCheckout=false", "-c", "index.sparse=false")

#: How git spells no object at all: an index line carrying it takes a path out.
_NO_OBJECT: Final = "0" * 40

#: The mode of a plain file, which is every file a task writes.
_PLAIN_FILE: Final = "100644"


class Checkout:
    """The git commands a shard runs, all of them in one checkout."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    def _run(
        self,
        *args: str,
        stdin: str | None = None,
        fetches: bool = False,
        index: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """One git command, with lazy fetching off unless it is a named fetch.

        A command handed `index` reads and writes that index file instead of the
        checkout's, as a whole index.
        """
        env = dict(os.environ)
        if not fetches:
            env[NO_LAZY_FETCH_ENV] = "1"
        if index is not None:
            env[INDEX_FILE_ENV] = str(index)
            args = (*_A_WHOLE_INDEX, *args)
        return subprocess.run(
            ["git", *args],
            cwd=self._repo,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def git(
        self,
        *args: str,
        stdin: str | None = None,
        fetches: bool = False,
        index: Path | None = None,
    ) -> str:
        """Run one command and hand back what it printed, or raise with what it said."""
        done = self._run(*args, stdin=stdin, fetches=fetches, index=index)
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

    def staged_names(self, index: Path) -> set[str]:
        """Every path the next commit would change against `origin/main`, a deletion as itself.

        Rename detection is off. A shard that deletes a file and writes one much
        like it - a fold replacing a day's one writer file with its settled file -
        is a pair git would otherwise report as one move, naming only the new
        path, so the deletion would read as unstaged and the shard would refuse
        to land. Detecting it would also read both files, and the clone may hold
        neither.
        """
        listed = self.git(
            "diff-index",
            "--cached",
            "--name-only",
            "--no-renames",
            "-z",
            f"{REMOTE}/{BRANCH}",
            index=index,
        )
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

    def list_files(self, folders: Sequence[str]) -> list[TreeEntry]:
        """Every file the commit holds under these folders, with git's size where it has one.

        One `git ls-tree -r -l`, which reads trees and never a file: a file the
        clone never downloaded is named with no size, because git prints `BAD`.
        """
        if not folders:
            return []
        return parse_tree(self.git("ls-tree", "-r", "-l", "-z", "HEAD", "--", *folders))

    def folder_trees(self, folders: Sequence[str]) -> dict[str, str]:
        """The tree id the commit holds at each of these folders, by folder."""
        if not folders:
            return {}
        listed = self.git(
            "ls-tree", "-d", "-z", "HEAD", "--", *(folder.rstrip("/") for folder in folders)
        )
        trees: dict[str, str] = {}
        for record in listed.split("\0"):
            if record:
                described, path = record.split("\t", 1)
                trees[path] = described.split()[2]
        return trees

    def widen(self, entries: Sequence[str]) -> None:
        """Add these folders, or the files beside these files, to the sparse checkout.

        One call, which a partial clone serves with one download. The names go on
        standard input, so none of them can be read as an option. `--skip-checks`
        lets an entry name a file, which brings the files beside it and no folder
        below it.
        """
        self.git(
            "sparse-checkout",
            "add",
            "--skip-checks",
            "--stdin",
            stdin="".join(f"{entry}\n" for entry in entries),
            fetches=True,
        )

    def ignored(self, paths: Sequence[str]) -> set[str]:
        """Which of these paths a `.gitignore` pattern matches, whatever the index holds."""
        if not paths:
            return set()
        done = self._run(
            "check-ignore",
            "--no-index",
            "-z",
            "--stdin",
            stdin="".join(f"{path}\0" for path in paths),
        )
        # 0 names at least one ignored path and 1 names none; anything else failed.
        if done.returncode not in (0, 1):
            raise RuntimeError(f"git check-ignore failed: {done.stderr.strip()}")
        return set(done.stdout.split("\0")) - {""}

    def stage(self, written: Sequence[str], deleted: Sequence[str]) -> Path:
        """The next commit's index: `origin/main`'s tree, these writes set, these deletions out.

        Built in a file of its own each try, so the checkout's sparse index is
        never expanded and nothing is read but trees and the written files. A
        write git ignores is left out the way `git add` leaves it out, unless
        `origin/main` already holds it, and so is a write with no file on disk;
        the checks after name either one.
        """
        named = Path(self.git("rev-parse", "--git-path", COMMIT_INDEX).strip())
        index = named if named.is_absolute() else self._repo / named
        self.git("read-tree", f"{REMOTE}/{BRANCH}", index=index)
        ignored = self.ignored(written)
        staged = [
            path
            for path in written
            if (self._repo / path).is_file()
            and (path not in ignored or self.remote_blob(path) is not None)
        ]
        blobs = (
            self.git(
                "hash-object", "-w", "--stdin-paths", stdin="".join(f"{path}\n" for path in staged)
            ).split()
            if staged
            else []
        )
        lines = [
            f"{_PLAIN_FILE} {blob}\t{path}\0" for blob, path in zip(blobs, staged, strict=True)
        ]
        lines += [f"0 {_NO_OBJECT}\t{path}\0" for path in deleted]
        if lines:
            self.git("update-index", "-z", "--index-info", stdin="".join(lines), index=index)
        return index

    def commit(self, index: Path, message: str) -> str:
        """A commit of that index on top of `origin/main`, under the repository's one identity.

        `--missing-ok`, because the index names every file `origin/main` holds and
        the clone holds few of them: checking that each one exists would
        download it.
        """
        tree = self.git("write-tree", "--missing-ok", index=index).strip()
        return self.git(
            "-c",
            f"user.name={COMMITTER_NAME}",
            "-c",
            f"user.email={COMMITTER_EMAIL}",
            "commit-tree",
            tree,
            "-p",
            f"{REMOTE}/{BRANCH}",
            "-m",
            message,
        ).strip()

    def push(self, commit: str) -> bool:
        """Whether `main` took this commit, sent as whole objects rather than as deltas.

        A delta is computed against a file the remote holds, and for a file the
        clone never downloaded that means downloading it first; with lazy
        fetching off, the push would fail instead.
        """
        return self.git_ok("push", "--quiet", "--no-thin", REMOTE, f"{commit}:refs/heads/{BRANCH}")


def sleep_with_jitter(attempt: int, *, sleep: Callable[[float], None] = time.sleep) -> None:
    """Wait a random time before try `attempt + 1`, longer after each loss, never past the cap."""
    sleep(random.uniform(0, min(2 ** (attempt - 1), MAX_BACKOFF_SECONDS)))


def _refuse_a_directory(shard: Shard, repo: Path) -> str | None:
    """A write or a deletion names one file. A folder here would stand for everything under it."""
    for path in sorted(shard.written_paths | shard.deleted_paths):
        if (repo / path).is_dir():
            return f"{path} is a folder, and a shard writes and deletes files one at a time"
    return None


def _what_staging_missed(shard: Shard, checkout: Checkout, index: Path) -> str | None:
    """The three checks over what was staged, or None when the index is exactly the shard."""
    staged = checkout.staged_names(index)
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
    """Commit and push this shard, trying again on a newer tip, `attempts` times at most."""
    refused = _refuse_a_directory(shard, repo)
    if refused is not None:
        say(f"shard {shard.index}: {refused}")
        return EXIT_INTEGRITY
    checkout = Checkout(repo)
    written, deleted = sorted(shard.written_paths), sorted(shard.deleted_paths)
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
        index = checkout.stage(written, deleted)
        missed = _what_staging_missed(shard, checkout, index)
        if missed is not None:
            say(f"shard {shard.index}: {missed}")
            return EXIT_INTEGRITY
        if checkout.push(checkout.commit(index, shard.message)):
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
            swept.update(runner.folders_of(name, settings.tasks, repo_root, committed).walk)
    return sorted(swept)


def read_the_listing(
    checkout: Checkout, repo_root: Path, folders: Sequence[str], trees: TreeReader | None
) -> FileListing:
    """Every file the commit holds under these folders, each with its size, downloading none.

    Git's size where the clone holds the file. For one it never downloaded,
    GitHub's trees API is asked once for each listed folder that holds one, and
    its sizes are matched to git's names by blob id; a full clone never asks.
    `trees` stands in for that API, and None reaches it for this repository.

    The checkout is widened only by a file the commit lists, a folder above one,
    or a name directly inside such a folder - a file an earlier task of the
    shard wrote beside the commit's own - so a name a task hands back never
    widens it where the commit holds nothing.
    """
    chosen = sorted(set(folders))
    entries = checkout.list_files(chosen)
    unsized = [entry.path for entry in entries if entry.size is None]
    sizes: dict[str, int] = {}
    if unsized:
        held = checkout.folder_trees(chosen)
        asked = [
            tree
            for folder, tree in sorted(held.items())
            if any(path.startswith(f"{folder}/") for path in unsized)
        ]
        api = trees if trees is not None else github_collections.api_of_this_repository()
        sizes = sizes_from_github(api, asked)
    named = {entry.path for entry in entries}
    above = {
        parent.as_posix()
        for path in named
        for parent in PurePosixPath(path).parents
        if parent.parts
    }

    def widen(wanted: Sequence[str]) -> None:
        stray = [
            entry
            for entry in wanted
            if entry not in named
            and entry not in above
            and PurePosixPath(entry).parent.as_posix() not in above
        ]
        if stray:
            raise ValueError(
                f"{stray[0]} is not a file the commit lists or a folder that holds one, so "
                "the checkout is not widened by it"
            )
        checkout.widen(wanted)

    return FileListing.from_commit(repo_root, chosen, entries, sizes, widen=widen)


def folder_weights(listing: FileListing, folders: Sequence[str]) -> dict[str, int]:
    """What each folder weighs at the commit, in bytes. A folder the commit lacks weighs 0."""
    return {
        folder: sum(listing.size_of(path) for path in listing.files_under(folder))
        for folder in folders
    }


def run_and_land(
    names: Sequence[str],
    *,
    settings: GardenerSettings,
    repo_root: Path,
    run_id: str,
    attempt: int,
    shard: int,
    package: ModuleType = shipped_tasks,
    trees: TreeReader | None = None,
    clock: Callable[[], datetime] = runner.utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Read the commit's names, run the shard, and land what it hands back; the worst code wins.

    The listing covers every folder the shard's tasks own or read, and the ones
    the complement task sweeps, which only the commit can name. A listing that
    cannot be read runs no task and lands nothing, and the shard exits 1, so the
    next wake tries again. A deletion of a file the commit did not list lands
    nothing either: a task decided it from something other than the commit.
    """
    checkout = Checkout(repo_root)
    sha = checkout.head()
    if sha is None:
        say(f"shard {shard}: {repo_root.name} is not a git checkout, so no record can name it")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    owned = sorted({folder for name in names for folder in settings.tasks[name].owns or ()})
    read = sorted({folder for name in names for folder in settings.tasks[name].reads})
    committed = checkout.committed_folders([*owned, *read])
    swept = find_the_swept_folders(names, settings, repo_root, committed)
    try:
        listing = read_the_listing(checkout, repo_root, [*owned, *read, *swept], trees)
    except (OSError, RuntimeError, ValueError) as refusal:
        say(
            f"shard {shard}: the files under its folders could not be listed, so no task "
            f"ran: {refusal}"
        )
        return Outcome(exit_code=EXIT_TASK_FAILED, record=None, landing=None)
    ran = runner.run(
        names,
        settings=settings,
        repo_root=repo_root,
        run_id=run_id,
        attempt=attempt,
        shard=shard,
        git_sha=sha,
        committed_folders=committed,
        cone_bytes=folder_weights(listing, [*owned, *swept]),
        listing=listing,
        package=package,
        clock=clock,
        say=say,
    )
    if ran.landing is None:
        return ran
    unlisted = sorted(ran.landing.deleted_paths - set(listing.sizes))
    if unlisted:
        say(
            f"shard {shard}: {unlisted[0]} was deleted, and the commit this shard read lists "
            "no such file. Nothing lands"
        )
        return dataclasses.replace(ran, exit_code=worst(ran.exit_code, EXIT_INTEGRITY))
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
