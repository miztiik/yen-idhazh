"""How does one gardener shard land its one commit on main, however many shards race it?

This is the entry point a wake's shard runs. Its checkout holds only the code
and config it runs. It reads the commit this checkout is at, the exact folders
its tasks own or read, and the files under each task's named periods. A task
that names a period as it runs has it listed from the same commit then. It runs the shard through
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
downloaded, git prints no size, so GitHub's blob API is asked for that named
file and its size is matched by blob id.

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

**A shard whose paths main changed after its commit lands nothing.** After each
fetch, `git diff-tree` compares the commit this checkout is at - the one the
shard ran on - with `origin/main`, over every path the shard writes or deletes
but its record. A path it lists is one main changed after the shard's commit, so
the shard's version is stale. A re-run is the usual cause: it checks out its
run's old commit and names its record afresh, so the record check cannot catch
it. Nothing lands, not even the record; the shard warns and exits 0, and the
next wake does the work again on the new main. Only trees are compared, so
nothing is downloaded.

**When every try failed, main's tip says why.** The tip is fetched once more. If
it moved after the last try's base, other writers are landing: a warning, and
exit 0. If it did not move, main refused the push: exit 3. A push's error text
is never read, because git's words change with versions and languages.

How the shard came to rest is one word of `idhazh.contracts.shard_landing`, and
the line that says so names it.

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
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import github_collections, runner
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.file_listing import (
    FileListing,
    TreeEntry,
    TreeReader,
    parse_tree,
    sizes_from_github,
    sizes_of,
)
from idhazh.gardener.outcome import (
    EXIT_INTEGRITY,
    EXIT_OK,
    EXIT_PUSH_REFUSED,
    EXIT_TASK_FAILED,
    Outcome,
    Shard,
    worst,
)
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range

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

#: Leave headroom below Windows' 32K process command-line limit.
_MAX_PATHSPEC_CHARACTERS: Final = 16_000


def _pathspec_batches(paths: Sequence[str]) -> list[tuple[str, ...]]:
    """Split named Git pathspecs before the process command line can overflow."""
    batches: list[tuple[str, ...]] = []
    current: list[str] = []
    characters = 0
    for path in sorted(set(paths)):
        size = len(path) + 1
        if size > _MAX_PATHSPEC_CHARACTERS:
            raise ValueError(f"Git pathspec is too long to list safely: {path!r}")
        if current and characters + size > _MAX_PATHSPEC_CHARACTERS:
            batches.append(tuple(current))
            current = []
            characters = 0
        current.append(path)
        characters += size
    if current:
        batches.append(tuple(current))
    return batches


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

    def fetch(self) -> str:
        """Fetch `main` as it is now into `origin/main`, and hand back the commit it is at."""
        self.git("fetch", "--quiet", REMOTE, BRANCH, "--depth=1")
        return self.git("rev-parse", "--verify", f"{REMOTE}/{BRANCH}").strip()

    def changed_on_main(self, paths: Sequence[str]) -> list[str]:
        """Which of these paths differ between the commit this checkout is at and `origin/main`.

        Trees only, so a partial clone downloads nothing: it holds every tree of
        both commits. Rename detection is off, so each path is judged by its own
        entry. The names are taken literally, as `ls-tree` takes them, in groups
        below Windows' process limit.
        """
        listed: set[str] = set()
        for batch in _pathspec_batches(paths):
            listed.update(
                self.git(
                    "--literal-pathspecs",
                    "diff-tree",
                    "-r",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "HEAD",
                    f"{REMOTE}/{BRANCH}",
                    "--",
                    *batch,
                ).split("\0")
            )
        return sorted(listed - {""})

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
        """Which exact configured folders the commit holds, without listing their children."""
        listed = self.git(
            "ls-tree",
            "-d",
            "--name-only",
            "-z",
            "HEAD",
            "--",
            *(folder.rstrip("/") for folder in owned),
        )
        return frozenset(listed.split("\0")) - {""}

    def list_files(self, paths: Sequence[str]) -> list[TreeEntry]:
        """Every file under these named period paths, with git's size where it has one.

        Bounded groups of pathspecs keep the command below Windows' process
        limit. Each call reads trees and never file contents: a file the clone
        never downloaded is named with no size, because git prints `BAD`.
        """
        if not paths:
            return []
        found = {
            entry.path: entry
            for batch in _pathspec_batches(paths)
            for entry in parse_tree(self.git("ls-tree", "-r", "-l", "-z", "HEAD", "--", *batch))
        }
        return [found[path] for path in sorted(found)]

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
    """Land this shard on main, trying again on a newer tip, `attempts` times at most.

    Every way it comes to rest is said with its word from `ShardLanding`.
    """
    refused = _refuse_a_directory(shard, repo)
    if refused is not None:
        say(f"shard {shard.index}: {refused}")
        return EXIT_INTEGRITY
    checkout = Checkout(repo)
    written, deleted = sorted(shard.written_paths), sorted(shard.deleted_paths)
    compared = sorted((shard.written_paths | shard.deleted_paths) - {shard.record_path})
    base = ""
    for attempt in range(1, attempts + 1):
        base = checkout.fetch()
        landed = checkout.remote_blob(shard.record_path)
        if landed is not None:
            if landed == checkout.local_blob(shard.record_path):
                say(f"shard {shard.index}: {ShardLanding.ALREADY_ON_MAIN}, try {attempt}")
                return EXIT_OK
            say(
                f"shard {shard.index}: {shard.record_path} is on {BRANCH} with other bytes, "
                "so two runs claimed one record"
            )
            return EXIT_INTEGRITY
        stale = checkout.changed_on_main(compared)
        if stale:
            more = f" and {len(stale) - 1} more" if len(stale) > 1 else ""
            say(
                f"::warning::shard {shard.index}: {ShardLanding.STALE} - {BRANCH} changed "
                f"{stale[0]}{more} after the commit this shard ran on, so nothing landed. "
                f"The next wake does the work again on the new {BRANCH}"
            )
            return EXIT_OK
        index = checkout.stage(written, deleted)
        missed = _what_staging_missed(shard, checkout, index)
        if missed is not None:
            say(f"shard {shard.index}: {missed}")
            return EXIT_INTEGRITY
        if checkout.push(checkout.commit(index, shard.message)):
            say(
                f"shard {shard.index}: {ShardLanding.LANDED} on {BRANCH}, "
                f"try {attempt} of {attempts}"
            )
            return EXIT_OK
        say(f"shard {shard.index}: try {attempt} of {attempts}, the push failed")
        if attempt < attempts:
            sleep_with_jitter(attempt)
    if checkout.fetch() != base:
        say(
            f"::warning::shard {shard.index}: {ShardLanding.LOST} - {BRANCH} moved after try "
            f"{attempts} of {attempts}, so other writers are landing. Nothing landed; the "
            "next wake does the work again"
        )
        return EXIT_OK
    say(
        f"shard {shard.index}: {ShardLanding.REFUSED} - {BRANCH} did not move after try "
        f"{attempts} of {attempts}, so {BRANCH} refused the push. Nothing landed"
    )
    return EXIT_PUSH_REFUSED


def read_the_listing(
    checkout: Checkout,
    repo_root: Path,
    folders: Sequence[str],
    period_paths: Sequence[str],
    trees: TreeReader | None,
) -> FileListing:
    """Every file the commit holds under these named period paths, with its size.

    The listing answers only for these paths, and refuses a path under its
    folders that none of them names. Git's size where the clone holds the
    file. For one it never downloaded, GitHub's blob API is asked for that
    named file and its size is matched by blob id. `trees` stands in for that
    API, and None reaches it for this repo. A step that names a period as it
    runs has it listed the same way, from the same commit.

    The checkout is widened only by a file the commit lists, a folder above one,
    or a name directly inside such a folder - a file an earlier task of the
    shard wrote beside the commit's own - so a name a task hands back never
    widens it where the commit holds nothing. A period named later counts once
    it is listed.
    """
    chosen = sorted(set(folders))
    named = sorted(set(period_paths))
    listed: set[str] = set()
    above: set[str] = set()

    def asked_of_github(entries: Sequence[TreeEntry]) -> dict[str, int]:
        """The size GitHub gives each blob git printed no size for, by blob id."""
        unsized = [entry.blob for entry in entries if entry.size is None]
        if not unsized:
            return {}
        api = trees if trees is not None else github_collections.api_of_this_repository()
        return sizes_from_github(api, unsized)

    def remember(entries: Sequence[TreeEntry]) -> None:
        listed.update(entry.path for entry in entries)
        above.update(
            parent.as_posix()
            for entry in entries
            for parent in PurePosixPath(entry.path).parents
            if parent.parts
        )

    entries = checkout.list_files(named)
    remember(entries)

    def lister(wanted: Sequence[str]) -> dict[str, int]:
        found = checkout.list_files(wanted)
        remember(found)
        return sizes_of(found, asked_of_github(found))

    def widen(wanted: Sequence[str]) -> None:
        stray = [
            entry
            for entry in wanted
            if entry not in listed
            and entry not in above
            and PurePosixPath(entry).parent.as_posix() not in above
        ]
        if stray:
            raise ValueError(
                f"{stray[0]} is not a file the commit lists or a folder that holds one, so "
                "the checkout is not widened by it"
            )
        checkout.widen(wanted)

    return FileListing.from_commit(
        repo_root,
        chosen,
        entries,
        asked_of_github(entries),
        paths=named,
        widen=widen,
        lister=lister,
    )


def declared_folders(
    names: Sequence[str], settings: GardenerSettings
) -> tuple[list[str], list[str]]:
    """The folders these tasks own, and the ones they only read, each sorted."""
    owned = sorted({folder for name in names for folder in settings.tasks[name].owns})
    read = sorted({folder for name in names for folder in settings.tasks[name].reads})
    return owned, read


def run_and_land(
    names: Sequence[str],
    *,
    settings: GardenerSettings,
    repo_root: Path,
    run_id: str,
    attempt: int,
    shard: int,
    period_range: tuple[str, str] | None = None,
    package: ModuleType = shipped_tasks,
    trees: TreeReader | None = None,
    clock: Callable[[], datetime] = runner.utc_now,
    say: Callable[[str], None] = print,
) -> Outcome:
    """Read the commit's names, run the shard, and land what it hands back; the worst code wins.

    The listing covers only the named periods each task may read, and a period
    a step names as it runs. A listing that cannot be read runs no task and
    lands nothing, and the shard exits 1, so the next wake tries again. A
    deletion of a file the shard never listed from the commit lands nothing
    either: a task decided it from something other than the commit.
    """
    checkout = Checkout(repo_root)
    sha = checkout.head()
    if sha is None:
        say(f"shard {shard}: {repo_root.name} is not a git checkout, so no record can name it")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    if period_range is not None and len(names) != 1:
        say("a named period range runs one task, not a shard")
        return Outcome(exit_code=EXIT_INTEGRITY, record=None, landing=None)
    started_at = clock()
    owned, read = declared_folders(names, settings)
    committed = checkout.committed_folders([*owned, *read])
    try:
        paths = sorted(
            {
                path.relative_to(repo_root).as_posix()
                for name in names
                for path in paths_for_task(
                    repo_root,
                    name,
                    settings.tasks[name],
                    period_range
                    if period_range is not None
                    else scheduled_range(name, settings.tasks[name], started_at.date()),
                    today=started_at.date(),
                )
            }
        )
        listing = read_the_listing(checkout, repo_root, [*owned, *read], paths, trees)
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
        cone_bytes=None,
        listing=listing,
        period_range=period_range,
        package=package,
        clock=clock,
        started_at=started_at,
        say=say,
    )
    if ran.landing is None:
        return ran
    unlisted = sorted(ran.landing.deleted_paths - listing.listed())
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
    parser.add_argument("--from", dest="from_period")
    parser.add_argument("--to", dest="to_period")
    args = parser.parse_args(argv)
    settings = gardener_cli.settings_or_none(args.config)
    if settings is None:
        return EXIT_INTEGRITY
    names, shard = gardener_cli.chosen(settings, args, parser)
    selected_range = gardener_cli.period_range(settings, args, parser)
    outcome = run_and_land(
        names,
        settings=settings,
        repo_root=args.repo_root,
        run_id=args.run_id,
        attempt=args.attempt,
        shard=shard,
        period_range=selected_range,
    )
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
