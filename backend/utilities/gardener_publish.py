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
it. Nothing lands, not even the record; the shard exits 0, and the next wake
does the work again on the new main. Only trees are compared, so nothing is
downloaded.

**When every try failed, main's tip says why.** The tip is fetched once more. If
it moved after the last try's base, other writers are landing, and the shard
exits 0. If it did not move, main refused the push: exit 3. A push's error text
is never read, because git's words change with versions and languages.

How the shard came to rest is one word of `idhazh.contracts.shard_landing`, and
`publish` hands it back rather than saying it. **The shard says how it ended
once, whatever ended it:** `run_and_land` logs one `shard-published` event - the
landing word, or why the shard never came to rest, with its exit code and what
that code means - and, when the run is a step on GitHub, adds the shard's
summary to the job's page (`idhazh.gardener.run_summary`). An exception that
escapes is said the same way, by its type and place, before it goes on, and the
trace printed as the program ends names each chained exception's type and
frames, never its text (`idhazh.crash_trace`). On GitHub the event log also
writes the warning a `stale` or `lost` shard shows on the run's page
(`idhazh.gardener.workflow_commands`). Only `main` reads the environment:
whether the run is a step on GitHub, and where its summary goes.

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
import logging
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh.config import GardenerSettings
from idhazh.contracts.gardener_events import (
    ShardPublished,
    ShardStop,
    TaskFinished,
    TaskOutcome,
)
from idhazh.contracts.knobs.gardener import GardenerConfig
from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import event_log, github_collections, run_summary, runner
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
    MEANS,
    Outcome,
    Shard,
    worst,
)
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range
from idhazh.site_weight import BYTES_PER_MB
from utilities.publish_to_repo import PushOutcome, publish

#: The one identity every commit in this repository carries. The same two values
#: `backend/utilities/commit_and_push.py` sets, which a test holds in step.
COMMITTER_NAME: Final = "miztiik"
COMMITTER_EMAIL: Final = "miztiik@users.noreply.github.com"

#: The branch every shard lands on, and the remote it is fetched from.
REMOTE: Final = "origin"
BRANCH: Final = "main"

#: What GitHub's runner sets to `true` in every step it runs, so a run knows it
#: is a step on GitHub and writes the workflow commands GitHub reads.
GITHUB_ACTIONS_ENV: Final = "GITHUB_ACTIONS"

#: The file GitHub's runner shows on the job's page as the step's summary.
STEP_SUMMARY_ENV: Final = "GITHUB_STEP_SUMMARY"

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
        # Keep existing ancestry for push hooks; shallow callers fetch only new commits.
        self.git("fetch", "--quiet", REMOTE, BRANCH)
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


def read_the_listing(
    checkout: Checkout,
    repo_root: Path,
    folders: Sequence[str],
    period_paths: Sequence[str],
    trees: TreeReader | None,
    *,
    budget: int | None = None,
) -> FileListing:
    """Every file the commit holds under these named period paths, with its size.

    The listing answers only for these paths, and refuses a path under its
    folders that none of them names. Git's size where the clone holds the
    file. For one it never downloaded, GitHub's blob API is asked for that
    named file and its size is matched by blob id. `trees` stands in for that
    API, and None reaches it for this repo. A step that names a period as it
    runs has it listed the same way, from the same commit. `budget` is the most
    bytes the shard may download, which a step that chooses its periods by it
    asks the listing about; None answers to no budget.

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
        budget=budget,
    )


def declared_folders(
    names: Sequence[str], settings: GardenerSettings
) -> tuple[list[str], list[str]]:
    """The folders these tasks own, and the ones they only read, each sorted."""
    owned = sorted({folder for name in names for folder in settings.tasks[name].owns})
    read = sorted({folder for name in names for folder in settings.tasks[name].reads})
    return owned, read


#: Python's own exit status when an exception ends it: what a shard that crashed exits with.
_CRASHED_EXIT: Final = EXIT_TASK_FAILED


@dataclass(frozen=True, slots=True)
class _ShardRun:
    """Which shard of which run this is, and the knobs its last word names."""

    names: tuple[str, ...]
    shard: int
    run_id: str
    attempt: int
    config: GardenerConfig

    def published(
        self,
        exit_code: int,
        *,
        ran: Outcome | None = None,
        pushed: PushOutcome | None = None,
        stopped: ShardStop | None = None,
        failure: BaseException | None = None,
    ) -> ShardPublished:
        """How the shard ended: its landing, or the word for why it never came to rest.

        `ran` is what the runner came to, when it ran; `pushed` what the push
        loop came to, when it ran; `failure` the exception a listing that failed
        or a crash raised, named by its type and place and never its text.
        """
        finished = () if ran is None else ran.finished_tasks
        error, where = event_log.cause_of(failure)
        return ShardPublished(
            shard=self.shard,
            run_id=self.run_id,
            attempt=self.attempt,
            tasks=list(self.names),
            failed_tasks=[each.task for each in finished if each.outcome is TaskOutcome.FAILED],
            landing=None if pushed is None else pushed.landing,
            stopped_because=stopped,
            push_try=None if pushed is None else pushed.push_try,
            push_tries=self.config.attempts,
            record=None if ran is None or ran.landing is None else ran.landing.record_path,
            stale_paths=[] if pushed is None else list(pushed.stale_paths),
            downloaded_bytes=None if ran is None else ran.downloaded_bytes,
            over_budget=ran is not None and ran.over_budget,
            max_downloaded_mb=self.config.max_downloaded_mb,
            exit_code=exit_code,
            means=MEANS[exit_code],
            error=error,
            where=where,
        )


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
    summary: Path | None = None,
) -> Outcome:
    """Run the shard and land it, then say once how it ended, whatever ended it.

    The shard's last word is one `shard-published` event, and `summary`, when
    the run is a step on GitHub, is the file its job's summary page shows: the
    shard's summary is added to it. An exception that escapes is said the same
    way, by its type and place, and then goes on, so Python exits 1 with it.
    """
    run = _ShardRun(
        names=tuple(names), shard=shard, run_id=run_id, attempt=attempt, config=settings.config
    )
    try:
        ran, published = _run_and_land(
            run,
            settings=settings,
            repo_root=repo_root,
            period_range=period_range,
            package=package,
            trees=trees,
            clock=clock,
            say=say,
        )
    except Exception as crash:
        crashed = run.published(_CRASHED_EXIT, stopped=ShardStop.CRASHED, failure=crash)
        _said_how_it_ended(crashed, (), summary=summary, say=say)
        raise
    _said_how_it_ended(published, ran.finished_tasks, summary=summary, say=say)
    return ran


def _run_and_land(
    run: _ShardRun,
    *,
    settings: GardenerSettings,
    repo_root: Path,
    period_range: tuple[str, str] | None,
    package: ModuleType,
    trees: TreeReader | None,
    clock: Callable[[], datetime],
    say: Callable[[str], None],
) -> tuple[Outcome, ShardPublished]:
    """Read the commit's names, run the shard, and land what it hands back; the worst code wins.

    The listing covers only the named periods each task may read, and a period
    a step names as it runs. A listing that cannot be read runs no task and
    lands nothing, and the shard exits 1, so the next wake tries again; its line
    names the exception's type and place, never its text, which can quote a
    value. A deletion of a file the shard never listed from the commit lands
    nothing either: a task decided it from something other than the commit.
    """
    names, shard = run.names, run.shard
    checkout = Checkout(repo_root)
    sha = checkout.head()
    if sha is None:
        say(f"shard {shard}: {repo_root.name} is not a git checkout, so no record can name it")
        return _refused(run, EXIT_INTEGRITY)
    if period_range is not None and len(names) != 1:
        say("a named period range runs one task, not a shard")
        return _refused(run, EXIT_INTEGRITY)
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
        listing = read_the_listing(
            checkout,
            repo_root,
            [*owned, *read],
            paths,
            trees,
            budget=settings.config.max_downloaded_mb * BYTES_PER_MB,
        )
    except (OSError, RuntimeError, ValueError) as refusal:
        error, where = event_log.cause_of(refusal)
        place = "" if where is None else f" at {where}"
        say(
            f"shard {shard}: the files under its folders could not be listed, so no task "
            f"ran ({error}{place})"
        )
        unlisted = Outcome(exit_code=EXIT_TASK_FAILED, record=None, landing=None)
        return unlisted, run.published(
            EXIT_TASK_FAILED, stopped=ShardStop.LISTING_FAILED, failure=refusal
        )
    ran = runner.run(
        names,
        settings=settings,
        repo_root=repo_root,
        run_id=run.run_id,
        attempt=run.attempt,
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
        return ran, run.published(ran.exit_code, ran=ran, stopped=ShardStop.CHECK_REFUSED)
    unlisted_deletions = sorted(ran.landing.deleted_paths - listing.listed())
    if unlisted_deletions:
        say(
            f"shard {shard}: {unlisted_deletions[0]} was deleted, and the commit this shard "
            "read lists no such file. Nothing lands"
        )
        code = worst(ran.exit_code, EXIT_INTEGRITY)
        return dataclasses.replace(ran, exit_code=code), run.published(
            code, ran=ran, stopped=ShardStop.CHECK_REFUSED
        )
    pushed = publish(ran.landing, attempts=settings.config.attempts, repo=repo_root, say=say)
    code = worst(ran.exit_code, pushed.exit_code)
    stopped = None if pushed.landing is not None else ShardStop.CHECK_REFUSED
    return dataclasses.replace(ran, exit_code=code), run.published(
        code, ran=ran, pushed=pushed, stopped=stopped
    )


def _refused(run: _ShardRun, exit_code: int) -> tuple[Outcome, ShardPublished]:
    """A shard a check refused before any task ran: no record, and nothing to land."""
    nothing = Outcome(exit_code=exit_code, record=None, landing=None)
    return nothing, run.published(exit_code, stopped=ShardStop.CHECK_REFUSED)


def _level_of(published: ShardPublished) -> int:
    """The level a shard's last word is logged at.

    An error when it exits other than 0, a warning when nothing landed because
    main moved on, and information otherwise.
    """
    if published.exit_code != EXIT_OK:
        return logging.ERROR
    if published.landing in (ShardLanding.STALE, ShardLanding.LOST):
        return logging.WARNING
    return logging.INFO


def _said_how_it_ended(
    published: ShardPublished,
    finished: Sequence[TaskFinished],
    *,
    summary: Path | None,
    say: Callable[[str], None],
) -> None:
    """Log the shard's last word, and add its summary to the job's page when there is one.

    A page that will not take the summary costs the summary, never the shard's
    exit code: the record has landed or not by then. The line that says so
    names the error's type alone.
    """
    event_log.emit(published, level=_level_of(published))
    if summary is None:
        return
    try:
        with summary.open("a", encoding="utf-8", newline="\n") as page:
            page.write(run_summary.markdown(published, finished))
    except OSError as refusal:
        say(
            f"shard {published.shard}: its job summary could not be written "
            f"({type(refusal).__name__})"
        )


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
    on_github = os.environ.get(GITHUB_ACTIONS_ENV) == "true"
    summary = os.environ.get(STEP_SUMMARY_ENV)
    settings = gardener_cli.settings_or_none(args.config, github=on_github)
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
        summary=Path(summary) if summary else None,
    )
    return outcome.exit_code


if __name__ == "__main__":
    # A crash prints where it broke, never what it said. The printer is imported
    # from this checkout's `backend/`, as the plan job's programs import it.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idhazh import crash_trace

    crash_trace.install()
    sys.exit(main())
