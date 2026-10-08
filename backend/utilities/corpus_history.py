"""Squash the corpus history older than its window, record the run, and push it.

The history job in `.github/workflows/idhazh-gardener.yml` runs this once, after its full
clone and its install. It is the one program in this repository that
force-pushes `main` (CLAUDE.md section 8), and everything that push depends on
happens in this one process, so no decision crosses a workflow step as an
environment string:

    python backend/utilities/corpus_history.py --today D --run-id R --attempt A

1. Remember the tip origin handed over.
2. Find the boundary, the newest commit old enough to collapse (below).
3. Collapse the boundary and everything before it into one new root commit.
4. Replay every later commit onto that root, and refuse if the tip's tree moved.
5. Record the run through the `corpus-squash` task, bound the way a shard binds
   its tasks, and commit what it wrote.
6. Push with a lease on the tip from step 1. If origin's `main` moved, wait,
   take origin's new tip as step 1 and go round again, up to `push_attempts`
   pushes in all.

**The run is recorded whether or not anything was old enough**, and pushed
without force when nothing was rewritten. An unrecorded run is due again at the
next wake, and a clone and an install every day is what that costs. Only a run
whose every push was refused is left unrecorded.

**The boundary is read off author dates, because a squash rewrites committer
dates.** The replay gives every commit it moves the day of the squash as its
committer date, so a cut read off committer dates would find nothing at the next
two due wakes, and history would reach back 150 days rather than 60 to 90. The
cut is 00:00 UTC on `today` minus the window, so the hour the job woke cannot
move it. The boundary is the last commit of the unbroken run, from the root
along first parents, whose author dates are all at or before the cut - so a
commit near the tip that was authored long before it landed cannot pull the
boundary past newer work. The error that walk can make is keeping more history,
never less. The new root carries the boundary's author date, so the next squash
can reach past it.

**The push carries a lease on the tip this run read.** A forcing push is a
whole-ref operation: it replaces the branch with this checkout, so a commit
another run pushed while the squash ran would be deleted, and nothing would
record that it existed. `--force-with-lease=refs/heads/main:<tip>` names the
commit step 1 read, and git replaces origin's `main` only while it still holds
that commit. The check and the update are one step where the push is received,
so nothing can land between them. A run that rewrote nothing pushes without
force, and git refuses that push too once `main` has moved, because it is no
longer a fast-forward. After a refused push origin's tip is read again, which
tells a moved `main` apart from any other failure.

**A refused push is followed by a new squash, never by the same one.** The
rewrite replaced every commit below the old tip, and pushing it again would be
refused again: it does not hold the commit that moved `main`. So the program
waits `push_retry_delay_seconds`, fetches `main`, puts this checkout's `main`
on it, and runs steps 2 to 6 on the new tip, so the other run's commits are
replayed with every other commit after the boundary. The task's context - the
run id and the attempt - is made once for the run, and every pass records into
the same file, `corpus/corpus.meta.json`, written from the new tip's copy so a
change another run made to it is kept. Both numbers are in
`config/gardener/corpus-squash.json`. After the last refused push the run is
left unrecorded, and the squash is due again the next day - one wake, not one
cadence.

It sits here and not in `backend/idhazh/` because it runs git, and nothing in
the package may start a process (`backend/tests/test_canaries.py`). Its module
scope is the standard library alone: `idhazh` is imported by the one function
that reads the declaration and binds the task, and `idhazh.crash_trace` where
a crash is printed, so a run that cannot be recorded names the exception's type
and frames and never its text.

Exit codes:
  0  squashed and pushed, or nothing was old enough and the run was pushed, or a dry run
  1  every push was refused because origin's tip moved, so the run is not recorded
  2  this cannot rewrite the repository: a detached head, a dirty tree, a boundary
     that does not resolve, a replay that conflicts or moves the tip's tree, a
     declaration that does not load or is not active, or a run it cannot record
A git command that fails ends the program with git's own exit code, and so does
a push git refused while origin's tip stayed where this run read it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from time import sleep
from typing import Final

#: The checkout this file sits in, which is the one the history job cloned.
REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The branch that is rewritten, and the remote it is pushed back to.
REMOTE: Final = "origin"
BRANCH: Final = "main"

#: The one identity every commit in this repository carries. The same two values
#: `backend/utilities/commit_and_push.py` sets, which a test holds in step.
COMMITTER_NAME: Final = "miztiik"
COMMITTER_EMAIL: Final = "miztiik@users.noreply.github.com"

#: The new root's message: the one line a person greps rewritten history for.
SQUASH_MESSAGE: Final = "corpus: squash history older than {keep_days} days"

#: The message of the commit that records the run.
RECORD_MESSAGE: Final = "corpus: pruned {today}"

#: The declaration this program runs, `config/gardener/<TASK_NAME>.json`.
TASK_NAME: Final = "corpus-squash"

EXIT_OK: Final = 0
EXIT_TIP_MOVED: Final = 1
EXIT_CANNOT_REWRITE: Final = 2

#: What a push refused because `main` moved prints first, on every pass. The
#: words have not changed since the push was a program of its own: they are what
#: an operator reads.
MAIN_MOVED: Final = (
    "main moved while the prune was rewriting it, so nothing was pushed",
    "  this job checked out {read}",
    "  origin/main is now {now}",
    "pushing would discard every commit between the two.",
)

#: The line that ends the refusal of the last push a run may make, and only
#: that one: before it, another pass may still record the run.
DUE_AGAIN: Final = "the prune is unstamped, so it is due again at the next daily wake."

#: A day as `--today` takes one, `YYYY-MM-DD`.
_A_DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


class CannotRewriteError(Exception):
    """The repository is not one this can rewrite. `squash_history` exits 2 on it."""


class MainMovedError(Exception):
    """Origin's `main` is no longer the commit this run read, so its push was refused."""

    def __init__(self, *, read: str, now: str) -> None:
        super().__init__(f"{BRANCH} moved from {read} to {now}")
        self.read = read
        self.now = now


def _run(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """One git call in `repo`, as the repository's own committer, whatever it returns."""
    return subprocess.run(
        ["git", "-c", f"user.name={COMMITTER_NAME}", "-c", f"user.email={COMMITTER_EMAIL}", *args],
        cwd=repo,
        env=None if env is None else {**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """One git call, or the end of the program carrying git's own exit code.

    The shell this replaced ran under `set -e`. Reading the exit code rather
    than the message keeps that behaviour whatever git prints.
    """
    done = _run(repo, *args, env=env)
    if done.returncode:
        sys.stderr.write(done.stderr)
        raise SystemExit(done.returncode)
    return done.stdout


def cut_of(today: date, keep_days: int) -> datetime:
    """00:00 UTC on the day `keep_days` before `today`. A commit authored at or before it is old."""
    return datetime.combine(today - timedelta(days=keep_days), time.min, tzinfo=UTC)


def _tip_to_rewrite(repo: Path) -> str:
    """The commit `main` is at, or a refusal when this checkout cannot be rewritten."""
    branch = _run(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode:
        raise CannotRewriteError("HEAD is detached, so there is no branch to rewrite")
    if branch.stdout.strip() != BRANCH:
        raise CannotRewriteError(
            f"HEAD is on {branch.stdout.strip()}, and only {BRANCH} is rewritten"
        )
    if _git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise CannotRewriteError("the tree has uncommitted changes, which a rewrite would lose")
    return _git(repo, "rev-parse", "HEAD").strip()


def boundary_commit(repo: Path, *, keep_days: int, today: date) -> str | None:
    """The newest commit the squash may collapse, or None when a squash is not worth doing.

    The last commit of the unbroken run, from the root along first parents, whose
    author dates are all at or before the cut. `--first-parent` so a merged
    branch's own commits cannot be picked as the boundary. None when the root
    itself is younger than the cut, when the run reaches the tip - the squash
    would collapse the whole branch - or when the boundary is already the root.
    None means the squash is not worth doing this wake, which is a success and
    not a failure.

    The walk reads the first-parent chain once, and that chain is what this
    program keeps to 60 to 90 days of commits at the committed window.
    """
    cut = cut_of(today, keep_days).timestamp()
    day = (today - timedelta(days=keep_days)).isoformat()
    boundary: str | None = None
    chain = _git(repo, "log", "--first-parent", "--reverse", "--format=%H %at", "HEAD")
    for line in chain.splitlines():
        sha, authored = line.split()
        if int(authored) > cut:
            break
        boundary = sha
    if boundary is None:
        print(f"no commit is older than {day} - nothing to squash")
        return None
    if boundary == _git(repo, "rev-parse", "HEAD").strip():
        print(
            "the boundary is the tip, so squashing would collapse the whole branch",
            file=sys.stderr,
        )
        return None
    print(f"boundary {day} resolves to {boundary}")
    behind = int(_git(repo, "rev-list", "--count", boundary))
    if behind <= 1:
        print(f"only {behind} commit is behind the boundary - already pruned")
        return None
    return boundary


def squash_below(repo: Path, *, boundary: str, message: str) -> str:
    """Collapse everything at or before `boundary` into one orphan root. Returns its sha.

    The root holds the boundary's complete tree, so no data is lost - only the
    deltas behind it. That is also why no `keep_generations` knob is needed: the
    root holds one whole dataset and the tip holds another, so N and N-1 always
    survive. It carries the boundary's author date, because the next squash reads
    author dates and a root dated today would stop it for another whole window.
    """
    if _run(repo, "rev-parse", "--verify", "--quiet", f"{boundary}^{{commit}}").returncode:
        raise CannotRewriteError(f"the boundary {boundary} is not a commit in this repository")
    authored = _git(repo, "log", "-1", "--format=%aI", boundary).strip()
    tree = f"{boundary}^{{tree}}"
    root = _git(repo, "commit-tree", tree, "-m", message, env={"GIT_AUTHOR_DATE": authored})
    return root.strip()


def replay_above(repo: Path, *, boundary: str, onto: str) -> None:
    """Rebase every commit after `boundary` onto `onto`, trees unchanged.

    A replay that stops on a conflict is aborted and refused, so the branch is
    left where it was and nothing is pushed.
    """
    done = _run(repo, "rebase", "--quiet", "--onto", onto, boundary, BRANCH)
    if done.returncode:
        _run(repo, "rebase", "--abort")
        said = (done.stderr or done.stdout).strip()
        raise CannotRewriteError(f"replaying the commits after {boundary} stopped: {said}")


def _refuse_a_moved_tree(repo: Path, tip_before: str) -> None:
    """The rewrite changes which commits hold the tree, never the tree at the tip."""
    before = _git(repo, "rev-parse", f"{tip_before}^{{tree}}").strip()
    after = _git(repo, "rev-parse", "HEAD^{tree}").strip()
    if before != after:
        raise CannotRewriteError(
            f"the replayed tip holds tree {after} and {tip_before} held {before}, so this "
            f"checkout's {BRANCH} is rewritten and must be thrown away"
        )


def _commit_the_record(repo: Path, written: Sequence[str], *, today: date) -> None:
    """Commit exactly the files the task wrote. A run already recorded today commits nothing."""
    _git(repo, "add", "--", *written)
    if _run(repo, "diff", "--cached", "--quiet").returncode == 0:
        print("the stamp did not move")
        return
    _git(repo, "commit", "--quiet", "-m", RECORD_MESSAGE.format(today=today.isoformat()))


def _push(repo: Path, *, tip_before: str, rewritten: bool) -> int:
    """Push `main` once. Returns 0 or git's own code, and raises `MainMovedError` when it moved.

    A rewrite goes with a lease on `tip_before`, so git replaces origin's `main`
    only while it still holds that commit. A run that rewrote nothing goes
    without force, which git refuses once `main` moved because it is no longer a
    fast-forward. Origin's tip is read again after a refused push, so a moved
    `main` is told apart from any other failure, which keeps git's own code.
    """
    # Written as two whole command lines rather than one with a computed flag,
    # so the one forcing push in this repository is legible to a reader and to
    # the test that holds it to being the only one. The lease names the commit
    # this run read before it rewrote anything, never what origin holds when the
    # push starts.
    #
    # Not captured either: this is the push whose output a person reads in the
    # step log when it fails.
    if rewritten:
        pushed = subprocess.run(
            ["git", "push", "--force-with-lease=refs/heads/main:" + tip_before, "origin", "main"],
            cwd=repo,
            check=False,
        ).returncode
    else:
        pushed = subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=False).returncode
    if pushed == EXIT_OK:
        return EXIT_OK
    _git(repo, "fetch", REMOTE, BRANCH)
    tip = _git(repo, "rev-parse", "FETCH_HEAD").strip()
    if tip != tip_before:
        raise MainMovedError(read=tip_before, now=tip)
    return pushed


def _say_main_moved(moved: MainMovedError, *, then: str) -> None:
    """The refusal an operator reads, ending with what happens next."""
    for line in MAIN_MOVED:
        print(line.format(read=moved.read, now=moved.now), file=sys.stderr)
    print(then, file=sys.stderr)


def push_rewritten(repo: Path, *, tip_before: str, rewritten: bool) -> int:
    """Push `main` once, and refuse for good, naming both commits, if origin's tip moved.

    The last push a run may make. The refusal, its words and its exit code 1 are
    the ones the history job has always had. A plain push loses the same race
    anyway - git refuses a non-fast-forward - so a run that rewrote nothing takes
    the same answer, and it names which commit moved rather than leaving an
    operator to read a rejection message.
    """
    try:
        return _push(repo, tip_before=tip_before, rewritten=rewritten)
    except MainMovedError as moved:
        _say_main_moved(moved, then=DUE_AGAIN)
        return EXIT_TIP_MOVED


def _take_origins_tip(repo: Path) -> str:
    """Put this checkout's `main` on origin's tip, leaving the refused rewrite behind.

    `--keep` rather than `--hard`: the record is committed by now, so the tree is
    clean, and a reset that met an uncommitted change would refuse rather than
    lose it. Returns the tip, read the way the first pass read its own.
    """
    _git(repo, "fetch", REMOTE, BRANCH)
    _git(repo, "reset", "--keep", "FETCH_HEAD")
    return _tip_to_rewrite(repo)


def squash_history(
    repo: Path,
    *,
    keep_days: int,
    today: date,
    message: str,
    dry_run: bool,
    record: Callable[[], Sequence[str]],
    push_attempts: int,
    push_retry_delay_seconds: int,
) -> int:
    """The whole squash, in order. `record` records the run and returns the files it wrote.

    Resolve the boundary; squash and replay when there is one; record the run
    and commit it; then push with a lease on the tip this pass started from. A
    push refused because origin's `main` moved is followed, after
    `push_retry_delay_seconds`, by the whole squash again on origin's new tip, up
    to `push_attempts` pushes in all. The last refusal leaves the record on this
    checkout alone, so the squash is due again at the next wake. A dry run
    resolves the boundary, says what a squash would collapse, and writes,
    records and pushes nothing, so it is due again at the next wake too.
    """
    try:
        tip_before = _tip_to_rewrite(repo)
    except CannotRewriteError as refusal:
        print(f"nothing was rewritten: {refusal}", file=sys.stderr)
        return EXIT_CANNOT_REWRITE

    boundary = boundary_commit(repo, keep_days=keep_days, today=today)
    if dry_run:
        _say_what_a_squash_would_do(repo, boundary)
        return EXIT_OK

    push = 1
    while True:
        try:
            if boundary is not None:
                behind = int(_git(repo, "rev-list", "--count", boundary))
                root = squash_below(repo, boundary=boundary, message=message)
                replay_above(repo, boundary=boundary, onto=root)
                _refuse_a_moved_tree(repo, tip_before)
                print(f"{behind} commits collapsed into {root}")
            written = record()
        except CannotRewriteError as refusal:
            print(f"nothing was pushed: {refusal}", file=sys.stderr)
            return EXIT_CANNOT_REWRITE
        except Exception as failure:
            from idhazh import crash_trace

            crash_trace.print_trace(failure)
            print("nothing was pushed: the run could not be recorded", file=sys.stderr)
            return EXIT_CANNOT_REWRITE

        _commit_the_record(repo, written, today=today)
        rewritten = boundary is not None
        if push >= push_attempts:
            return push_rewritten(repo, tip_before=tip_before, rewritten=rewritten)
        try:
            return _push(repo, tip_before=tip_before, rewritten=rewritten)
        except MainMovedError as moved:
            _say_main_moved(
                moved,
                then=(
                    f"waiting {push_retry_delay_seconds} s, then squashing again on the new "
                    f"tip: push {push + 1} of {push_attempts}"
                ),
            )
        sleep(push_retry_delay_seconds)
        push += 1
        try:
            tip_before = _take_origins_tip(repo)
        except CannotRewriteError as refusal:
            print(f"nothing was pushed: {refusal}", file=sys.stderr)
            return EXIT_CANNOT_REWRITE
        print(f"push {push} of {push_attempts} starts from {tip_before}")
        boundary = boundary_commit(repo, keep_days=keep_days, today=today)


def _say_what_a_squash_would_do(repo: Path, boundary: str | None) -> None:
    if boundary is None:
        print("dry run: nothing is old enough to squash, and nothing was written")
        return
    authored = _git(repo, "log", "-1", "--format=%aI", boundary).strip()
    behind = int(_git(repo, "rev-list", "--count", boundary))
    print(
        f"dry run: a squash would collapse {behind} commits into one root holding "
        f"{boundary}, authored {authored}. Nothing was written, recorded or pushed"
    )


def _squash_as_declared(
    repo: Path, *, config_dir: Path, today: date, run_id: str, attempt: int
) -> int:
    """Load the declaration, bind its task, and run the squash it declares.

    The one function that imports `idhazh`. Everything it refuses, it refuses
    before the tip is read, so a declaration that does not load rewrites nothing.
    """
    from idhazh import config, ledger
    from idhazh.contracts.base import RUN_ID_PATTERN, ServerJob
    from idhazh.contracts.knobs.gardener import HistoryPolicy, TaskKind
    from idhazh.gardener import registry, runner, tasks
    from idhazh.gardener.context import TaskContext
    from idhazh.gardener.file_listing import FileListing

    try:
        if not re.fullmatch(RUN_ID_PATTERN, run_id):
            raise ValueError(f"--run-id takes YYYY-MM-DD-N, not {run_id!r}")
        if attempt < 1:
            raise ValueError(f"--attempt counts from 1, not {attempt}")
        settings = config.load_gardener(config_dir)
        runner.runnable(settings, TASK_NAME)
        policy = settings.tasks[TASK_NAME]
        if not isinstance(policy, HistoryPolicy):
            raise ValueError(f"config/gardener/{TASK_NAME}.json is a {policy.kind} task")
        held = registry.bind(
            TASK_NAME,
            TaskKind.HISTORY,
            registry.discover(tasks, {TASK_NAME: policy}),
        )
    except (ValueError, registry.DiscoveryError) as refusal:
        print(f"nothing was rewritten: {refusal}", file=sys.stderr)
        return EXIT_CANNOT_REWRITE

    owns = runner.owner_of(TASK_NAME, settings.tasks)
    # Made once for the run and never again: a pass after a refused push records
    # under the same run id and attempt, into the same file, as the first pass.
    context = TaskContext(
        state_dir=repo / ledger.STATE_DIRNAME,
        repo_root=repo,
        today=today,
        policy=policy,
        run_id=run_id,
        attempt=attempt,
        job=ServerJob.HISTORY,
        shard=0,
        git_sha=_git(repo, "rev-parse", "HEAD").strip(),
        owned_folders=tuple(policy.owns),
        listing=FileListing.from_paths(repo, (), folders=policy.owns),
        first_ledger_year=settings.config.first_ledger_year,
    )

    def record() -> tuple[str, ...]:
        written = held.run(context).written
        outside = [path for path in written if not owns(path)]
        if outside:
            raise CannotRewriteError(f"{TASK_NAME} wrote {outside[0]}, which it does not own")
        return written

    keep_days = policy.window.value
    return squash_history(
        repo,
        keep_days=keep_days,
        today=today,
        message=SQUASH_MESSAGE.format(keep_days=keep_days),
        dry_run=policy.dry_run,
        record=record,
        push_attempts=policy.push_attempts,
        push_retry_delay_seconds=policy.push_retry_delay_seconds,
    )


def _day(text: str) -> date:
    if not _A_DAY.fullmatch(text):
        raise argparse.ArgumentTypeError(f"a day is YYYY-MM-DD, not {text!r}")
    return date.fromisoformat(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="corpus_history.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--today",
        type=_day,
        required=True,
        help="The UTC day of this wake, as the due check printed it: the one clock read.",
    )
    parser.add_argument("--run-id", required=True, help="The run this is, as YYYY-MM-DD-N.")
    parser.add_argument(
        "--attempt",
        type=int,
        required=True,
        help="Which attempt of that run. A re-run keeps its run id and counts this up.",
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--config", type=Path, default=None, help="Defaults to config/ in the checkout."
    )
    args = parser.parse_args(argv)
    return _squash_as_declared(
        args.repo_root,
        config_dir=args.config if args.config is not None else args.repo_root / "config",
        today=args.today,
        run_id=args.run_id,
        attempt=args.attempt,
    )


if __name__ == "__main__":
    # A crash prints where it broke, never what it said. The printer is imported
    # from this checkout's `backend/`, as the plan job's programs import it.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idhazh import crash_trace

    crash_trace.install()
    raise SystemExit(main())
