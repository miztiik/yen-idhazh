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
import hashlib
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Final

from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
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
    EXIT_TASK_FAILED,
    MEANS,
    Outcome,
    Shard,
    worst,
)
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range
from idhazh.site_weight import BYTES_PER_MB
from utilities.publication_git import Repository
from utilities.publication_request import Delete, IntegrityError, PublicationRequest, Write
from utilities.publish_to_repo import Status
from utilities.publish_to_repo import publish as publish_request
from utilities.push_retry import DEFAULT_CONFIG, load_retry

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

#: Git's switch that stops a partial clone downloading an object it lacks. Every
#: call here sets it but the one that widens the checkout for a task.
NO_LAZY_FETCH_ENV: Final = "GIT_NO_LAZY_FETCH"

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
    ) -> subprocess.CompletedProcess[str]:
        """One git command, with lazy fetching off unless it is a named fetch.

        A command handed `index` reads and writes that index file instead of the
        checkout's, as a whole index.
        """
        done = Repository(self._repo).run(
            *args,
            data=stdin.encode("utf-8") if stdin is not None else None,
            fetches=fetches,
        )
        return subprocess.CompletedProcess(
            done.args,
            done.returncode,
            done.stdout.decode("utf-8"),
            done.stderr.decode("utf-8"),
        )

    def git(
        self,
        *args: str,
        stdin: str | None = None,
        fetches: bool = False,
    ) -> str:
        """Run one command and hand back what it printed, or raise with what it said."""
        done = self._run(*args, stdin=stdin, fetches=fetches)
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


def _refuse_a_directory(shard: Shard, repo: Path) -> str | None:
    """A write or a deletion names one file. A folder here would stand for everything under it."""
    for path in sorted(shard.written_paths | shard.deleted_paths):
        if (repo / path).is_dir():
            return f"{path} is a folder, and a shard writes and deletes files one at a time"
    return None


@dataclass(frozen=True, slots=True)
class PushOutcome:
    """Gardener's exit convention, separate from producer failure."""

    exit_code: int
    landing: ShardLanding | None = None
    push_try: int | None = None
    stale_paths: tuple[str, ...] = ()


def publish(
    shard: Shard,
    *,
    attempts: int,
    repo: Path,
    identity: WriterIdentity,
    write_permissions: tuple[str, ...],
    delete_permissions: tuple[str, ...],
    say: Callable[[str], None] = print,
) -> PushOutcome:
    """Apply gardener's whole-shard stale policy through the common publisher."""
    git = Repository(repo)
    try:
        refused = _refuse_a_directory(shard, repo)
        if refused is not None:
            raise IntegrityError(refused)
        source = git.git("rev-parse", "HEAD").strip()
        git.prime(source, set(shard.written_paths) | set(shard.deleted_paths))
        writes = {
            path: Write(
                hashlib.sha256((repo / path).read_bytes()).hexdigest(),
                git.entry(source, path),
                path == shard.record_path,
            )
            for path in shard.written_paths
        }
        deletions: dict[str, Delete] = {}
        for path in shard.deleted_paths:
            baseline = git.entry(source, path)
            if baseline is None:
                raise IntegrityError("deletion was not listed in the source", (path,))
            deletions[path] = Delete(baseline, not (repo / path).exists())
        request = PublicationRequest(
            identity,
            shard.message,
            source,
            write_permissions,
            delete_permissions,
            writes,
            deletions,
        )
        result = publish_request(
            request,
            repo=repo,
            retry=load_retry(repo / DEFAULT_CONFIG)
            if (repo / DEFAULT_CONFIG).is_file()
            else load_retry(Path(__file__).resolve().parents[2] / DEFAULT_CONFIG),
            max_pushes=attempts,
        )
    except (OSError, ValueError, RuntimeError) as error:
        say(f"shard {shard.index}: {error}")
        return PushOutcome(EXIT_INTEGRITY)
    if result.status is Status.INTEGRITY_REFUSED:
        say(f"shard {shard.index}: {result.detail}: {', '.join(result.refusal_paths)}")
        return PushOutcome(EXIT_INTEGRITY)
    if result.status in (Status.STALE, Status.LOST):
        code = EXIT_OK
    elif result.status is Status.REFUSED:
        code = 3
    else:
        code = result.exit_code
    landing = (
        ShardLanding(result.status.value)
        if result.status.value in {word.value for word in ShardLanding}
        else None
    )
    return PushOutcome(
        code,
        landing,
        max(1, result.push_count),
        result.refusal_paths if result.status is Status.STALE else (),
    )


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
    pushed = publish(
        ran.landing,
        attempts=settings.config.attempts,
        repo=repo_root,
        say=say,
        identity=WriterIdentity(
            run_id=run.run_id,
            attempt=run.attempt,
            job=ServerJob.RUN_TASKS,
            shard=shard,
            producer="gardener.runner",
            git_sha=sha,
        ),
        write_permissions=tuple(sorted({*owned, "state/raw/gardener"})),
        delete_permissions=tuple(owned),
    )
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
