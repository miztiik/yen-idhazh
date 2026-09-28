"""Squash the corpus history older than its window, record the run, and push it.

The history job in `.github/workflows/prune.yml` runs this once, after its full
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
6. Push, and refuse if origin's tip moved while this ran.

**The run is recorded whether or not anything was old enough**, and pushed
without force when nothing was rewritten. An unrecorded run is due again at the
next wake, and a clone and an install every day is what that costs. Only a
refused push leaves the run unrecorded.

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

**The push refuses if `main` moved.** A forcing push is a whole-ref operation: it
replaces the branch with this checkout, so a commit another run pushed while the
squash ran would be deleted, and nothing would record that it existed. So the
tip is read again immediately before the push and compared with the commit this
job checked out. A tip that moved means another run pushed while the squash ran,
and this refuses instead of forcing. Nothing is retried and nothing is rebased:
the commits below this checkout have already been rewritten, so there is no base
left to replay them onto. The refusal leaves the run unrecorded, and the squash
is due again the next day - one wake, not one cadence.

It sits here and not in `backend/idhazh/` because it runs git, and nothing in
the package may start a process (`backend/tests/test_canaries.py`). Its module
scope is the standard library alone; `idhazh` is imported by the one function
that reads the declaration and binds the task.

Exit codes:
  0  squashed and pushed, or nothing was old enough and the run was pushed, or a dry run
  1  the push was refused because origin's tip moved, so the run is not recorded
  2  this cannot rewrite the repository: a detached head, a dirty tree, a boundary
     that does not resolve, a replay that conflicts or moves the tip's tree, a
     declaration that does not load or is not active, or a run it cannot record
A git command that fails ends the program with git's own exit code.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import traceback
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
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

#: A day as `--today` takes one, `YYYY-MM-DD`.
_A_DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


class CannotRewriteError(Exception):
    """The repository is not one this can rewrite. `squash_history` exits 2 on it."""


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


def push_rewritten(repo: Path, *, tip_before: str, rewritten: bool) -> int:
    """Push `main`, forcing only when it was rewritten, and refuse if origin's tip moved.

    The refusal, its words and its exit code 1 are the ones the history job has
    always had. A plain push loses the same race anyway - git refuses a
    non-fast-forward - so a run that rewrote nothing takes the same answer, and
    it names which commit moved rather than leaving an operator to read a
    rejection message.

    It is `--force` and not `--force-with-lease`, because a lease compares
    against a ref this job fetched at checkout, and the rewrite has already
    replaced every commit the lease would name.
    """
    _git(repo, "fetch", REMOTE, BRANCH)
    tip = _git(repo, "rev-parse", "FETCH_HEAD").strip()

    if tip != tip_before:
        for line in (
            "main moved while the prune was rewriting it, so nothing was pushed",
            f"  this job checked out {tip_before}",
            f"  origin/main is now {tip}",
            "pushing would discard every commit between the two.",
            "the prune is unstamped, so it is due again at the next daily wake.",
        ):
            print(line, file=sys.stderr)
        return EXIT_TIP_MOVED

    # Written as two whole command lines rather than one with a computed flag,
    # so the one forcing push in this repository is legible to a reader and to
    # the test that holds it to being the only one.
    #
    # Not captured either: this is the push whose output a person reads in the
    # step log when it fails.
    if rewritten:
        return subprocess.run(
            ["git", "push", "--force", "origin", "main"], cwd=repo, check=False
        ).returncode
    return subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=False).returncode


def squash_history(
    repo: Path,
    *,
    keep_days: int,
    today: date,
    message: str,
    dry_run: bool,
    record: Callable[[], Sequence[str]],
) -> int:
    """The whole squash, in order. `record` records the run and returns the files it wrote.

    Resolve the boundary; squash and replay when there is one; record the run
    and commit it; then push. A refused push leaves the record on this checkout
    alone, so the squash is due again at the next wake. A dry run resolves the
    boundary, says what a squash would collapse, and writes, records and pushes
    nothing, so it is due again at the next wake too.
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
    except Exception:
        traceback.print_exc()
        print("nothing was pushed: the run could not be recorded", file=sys.stderr)
        return EXIT_CANNOT_REWRITE

    _commit_the_record(repo, written, today=today)
    return push_rewritten(repo, tip_before=tip_before, rewritten=boundary is not None)


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
    from idhazh.gardener import registry, runner
    from idhazh.gardener.context import TaskContext

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
        held = registry.bind(TASK_NAME, TaskKind.HISTORY, registry.discover())
    except (ValueError, registry.DiscoveryError) as refusal:
        print(f"nothing was rewritten: {refusal}", file=sys.stderr)
        return EXIT_CANNOT_REWRITE

    owns = runner.owner_of(TASK_NAME, settings.tasks)
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
        owned_folders=tuple(policy.owns or ()),
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
    raise SystemExit(main())
