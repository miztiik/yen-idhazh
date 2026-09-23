"""Commit what a job produced and push it, rebuilding when the push loses a race.

Every committing job in this repository runs this. They differ in what they
stage, in the three strings they pass, and in whether they can rebuild what they
commit, so the retry behaviour is written once and a test executes it against a
real repository.

The runner checked out main's tip at trigger time and a daily run takes hours,
so the base a job commits against is old by then. A scheduled job must not lose
its work because somebody pushed while it ran.

There are two ways to lose that race and they need different answers.

A job that only RECORDS what it saw rebases. Every writer owns the file it
writes - a work shard's segment is named for that shard of that run - so two
jobs racing this loop are never touching one path, and the rebase applies both
sides whole.

A job that REBUILDS its output rebuilds. A digest day is derived from origin's
tip plus this run's artifacts, so the answer to a stale base is a current base -
not a text merge of two derived files, which produces a payload no producer
would ever write. Such a job hands the derived paths back to the tip the push
wants, then runs its producer again against that tip.

When the rebase does conflict, who wrote a path decides it - never which side of
the rebase the version came from. A writer's filename carries
`<run_id>-<attempt>-<job>-<shard>`, so a conflicted name carrying this job's
four values is this job's own work and what this job wrote is kept. Every other
conflicted path stops the push and names itself: no retry makes another writer's
file this job's, and taking the tip's copy instead would delete that writer's
rows at exit 0.

The loop is bounded by a wall clock rather than by a count, and prints what each
attempt spent, split six ways.

It reads no configuration and imports nothing from `idhazh`, so it runs from a
checkout whose install step never ran. That matters because this is what commits
when a producer has already finished or already failed.

Usage: `python backend/utilities/commit_and_push.py <path>...`

Environment:
  COMMIT_MESSAGE            the commit subject
  NOTHING_STAGED_MESSAGE    printed when the staged paths hold no change
  PUSH_FAILED_MESSAGE       printed to stderr when the deadline is spent
  PUSH_DEADLINE_SECONDS     optional: how long to keep trying, default 300
  SHARD                     optional: which shard of the job this is. It names
                            the attempt line, and it is the last element of the
                            identity a conflicted filename is matched against.
                            A whole number, default 0. The filename spells it
                            with two digits, so it is padded here.
  REFRESH_PATHS             optional: the committed paths this job rebuilds
  REGENERATE_COMMAND        optional: the producer that rebuilds them
  DROP_RACED_ASSETS_COMMAND optional: deletes this attempt's rendered assets
                            from the paths the tip already publishes

The last three are split on spaces, so no path and no argument may carry one.
The first two are given together or not at all.

Outputs, when the caller is a workflow step:
  rebased  true when the push lost a race and this program rewrote the
           checkout, false when what it pushed is what it was handed
"""

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The one identity this repository commits under (CLAUDE.md section 8). A
#: machine account in the author field tells a reader nothing the commit message
#: does not already say.
COMMITTER_NAME: Final = "miztiik"
COMMITTER_EMAIL: Final = "miztiik@users.noreply.github.com"

#: What a caller that names no deadline gets. Four of the five committing steps
#: pass `run.push_deadline_seconds` from config instead; the bench has no job
#: that reads config before the one that commits, so it takes this.
DEFAULT_PUSH_DEADLINE_SECONDS: Final = 300

#: A whole number and nothing else. `str.isdigit` is true of a superscript and
#: of several non-Latin digit sets, so a deadline that parsed one of those would
#: be a number no reader of the workflow can see.
WHOLE_NUMBER: Final = re.compile(r"^[0-9]+$")

#: The longest single wait, and the failure count past which the backoff stops
#: doubling. `min(2^(k-1), 8)` seconds for k failures so far, so the sleeps run
#: 1, 2, 4, 8, 8, 8.
BACKOFF_CEILING_SECONDS: Final = 8
BACKOFF_CEILING_AFTER: Final = 4


def _say(message: str) -> None:
    """One line to stdout, flushed.

    Git writes to the same file descriptor from its own process, so an unflushed
    line here would reach the run log after output that happened later.
    """
    print(message, flush=True)


def _warn(message: str) -> None:
    """One line to stderr, flushed, for the same reason."""
    print(message, file=sys.stderr, flush=True)


def _git(
    *args: str,
    capture: bool = False,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one git command and hand back what it did, whether or not it worked.

    `check=False` on purpose, everywhere. An exception raised mid-rebase leaves
    the checkout in exactly the state `set -e` used to leave it in, which is the
    defect this loop exists to have stopped having: run `32671663130` spent one
    attempt of three and left a half-applied rebase behind. Every caller reads
    the return code.

    Only stdout is captured, and only when the caller asks. Git's own stderr
    stays on the job's stderr, so a failure still names itself in the run log.
    """
    return subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE if capture else None,
        text=True,
        env=None if environment is None else dict(environment),
    )


def _lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The captured stdout as the paths it names, with the blank tail dropped."""
    return [line for line in result.stdout.split("\n") if line]


@dataclass
class Stamps:
    """What one attempt spent, split six ways.

    A single figure cannot tell a slow rebuild from a slow push, and which of the
    two the deadline is being spent on is the whole reason to collect this.
    """

    window_ms: int = 0
    fetch_ms: int = 0
    handback_ms: int = 0
    rebase_ms: int = 0
    rebuild_ms: int = 0
    push_ms: int = 0


def _elapsed_ms(since: float) -> int:
    """Milliseconds since a monotonic reading, truncated."""
    return int((time.monotonic() - since) * 1000)


#: What every attempt record is published behind, so a job log can be grepped
#: for it and a reader can find where the record starts without a format to
#: agree on. The reader imports this rather than spelling it again.
PUSH_ATTEMPT_LABEL = "push attempt"


def _report_rebased(rebased: bool) -> None:
    """Whether the tree this program pushed is still the tree it was handed.

    A push that lands first try leaves the checkout every earlier step read; a
    push that rebases replaces it with origin's, and a later step that measured
    the old one is measuring a tree nobody has. So the answer is written where a
    workflow can read it, and the step that rebuilds the site keys its `if:` off
    it.

    Both values are written explicitly: an output nobody wrote is the empty
    string, which is falsy and would look exactly like this program dying before
    it got here.

    `GITHUB_OUTPUT` is absent when a test drives this in a temporary clone, so
    the write is skipped rather than refused. A runner whose output file will not
    take a line is broken, and by then the push has either happened or is past
    saving; the rebuild is skipped, which costs a red gate rather than the day
    (CLAUDE.md section 1a: degrade, do not fail).
    """
    destination = os.environ.get("GITHUB_OUTPUT")
    if not destination:
        return
    try:
        with Path(destination).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"rebased={'true' if rebased else 'false'}\n")
    except OSError:
        _warn("could not say whether the push rebased")


def _say_what_this_attempt_spent(attempt: int, outcome: str, stamps: Stamps) -> None:
    """Publish one attempt's record, to the job log and to the step summary.

    One record, one encoding. It is published as the fields it carries rather
    than as a sentence with the fields spelled into it, because a reader that
    has to split a sentence back apart is a second spelling of the same record
    and either can drift while the other stays green.

    Attempt 1 has no window in the retry sense. Nothing fetches before the first
    push, so its exposure is the whole job - checkout to push, two to three hours
    - which is not a retry parameter, and its zeros are the truth about it. What
    measures attempt 1 is the share of runs whose first push lands.

    The step summary is where an operator reads it without opening a log, and it
    is absent when a test drives this, so that write is skipped rather than
    refused (CLAUDE.md section 1a: degrade, do not fail).
    """
    record = {
        "attempt": attempt,
        "job": os.environ.get("GITHUB_JOB") or "local",
        "shard": os.environ.get("SHARD") or "none",
        "outcome": outcome,
        "window_ms": stamps.window_ms,
        "fetch_ms": stamps.fetch_ms,
        "handback_ms": stamps.handback_ms,
        "rebase_ms": stamps.rebase_ms,
        "rebuild_ms": stamps.rebuild_ms,
        "push_ms": stamps.push_ms,
    }
    line = f"{PUSH_ATTEMPT_LABEL} {json.dumps(record)}"
    _say(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    try:
        with Path(summary).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except OSError:
        _warn("could not record what this attempt spent")


def _back_off(failures: int, attempt: int) -> None:
    """Wait before the next attempt, so the losers of one race do not refetch together.

    `min(2^(k-1), 8)` seconds for k failures so far, drawn against U(0.5, 1.5):
    the spread widens with the backoff, so collisions fall as more runs contend.
    """
    step = BACKOFF_CEILING_SECONDS if failures > BACKOFF_CEILING_AFTER else 1 << (failures - 1)
    jittered_ms = step * (500 + random.randrange(1001))
    _say(f"waiting {jittered_ms // 1000}.{jittered_ms % 1000:03d}s before attempt {attempt + 1}")
    time.sleep(jittered_ms / 1000)


def _discard_noise() -> bool:
    """Drop whatever the runner left in the working tree, and name it.

    The work is in a commit by the time the loop runs, so anything still in the
    working tree is runner noise - a line ending, a build artifact, a file some
    step left behind. A rebase refuses to start while any of it is there, and
    refusing costs the reader a day the run already finished.

    Most untracked files are left alone: nothing upstream is going to write over
    them, and a later step may still want them. The ones the tip DOES write over
    are cleared separately, below.
    """
    status = _git("status", "--porcelain", "--untracked-files=no", capture=True)
    if status.returncode != 0:
        return False
    noise = status.stdout.rstrip("\n")
    if not noise:
        return True
    _say("discarding working-tree noise before the rebase:")
    _say(noise)
    return _git("checkout", "--", ".").returncode == 0


def _clear_what_the_tip_will_write_over(tip: str) -> bool:
    """Remove the untracked files the incoming commits add, and name each one.

    An untracked file CAN block a rebase. A rebase detaches HEAD onto the tip
    first, and that checkout refuses when a file the incoming commits add is
    already sitting untracked in the working tree: `error: The following
    untracked working tree files would be overwritten by checkout`. The rebase
    never starts, so `git rebase --abort` has nothing to abort, and the loop
    spends its whole budget on the first attempt.

    Run `35152132574` is the record. A work shard wrote
    `state/host-fingerprint/2026/09/16.csv`, which its commit step did not stage
    yet, so the file stayed untracked. A sibling shard pushed the same path while
    this one was reading articles, and the rebase would not start: 303 rows over
    six ledgers were committed locally and thrown away with the runner.

    So the tolerance is narrow: only a file the tip is about to write is removed.
    A file this job did not stage is a file this job is not pushing, so removing
    it costs nothing the push was going to carry. Everything else untracked
    survives - `llama-server.log` and the memory samples are read by later steps.
    """
    listed = _git("ls-files", "--others", "--exclude-standard", capture=True)
    if listed.returncode != 0:
        return False
    # Absent upstream means nothing is going to write over it.
    blocked = [
        path
        for path in _lines(listed)
        if _git("rev-parse", "--verify", "--quiet", f"{tip}:{path}", capture=True).returncode == 0
    ]
    if not blocked:
        return True
    _say("removing untracked files origin/main carries, which would block the rebase:")
    for path in blocked:
        _say(f"  {path}")
        Path(path).unlink(missing_ok=True)
    return True


def _this_job_wrote(path: str, identity: str) -> bool:
    """True for a file this job is entitled to keep.

    One string comparison, and it reads no state. Off a runner there is no
    execution number, and a checkout that is not a job owns nothing - so that
    case answers no before the match runs, which an unanchored pattern would
    otherwise let through.
    """
    if not os.environ.get("GITHUB_RUN_ID"):
        return False
    return identity in path.rsplit("/", 1)[-1]


def _keep_what_this_job_wrote(path: str) -> bool:
    """Which version of a path survives, said as who wrote it.

    Never as which side of the rebase the version came from: git's own names for
    the two sides invert between a rebase and a merge - under a rebase
    `--theirs` is the commit being replayed, which is this job's own work - so a
    design that reasons in them is a design nobody can check. That word is
    spelled here and nowhere else.
    """
    if _git("checkout", "--theirs", "--", path).returncode != 0:
        return False
    return _git("add", "--", path).returncode == 0


def _keep_what_origin_has(tip: str, path: str) -> bool:
    """The tip's version, named by the tip rather than by a side.

    This one runs before the rebase starts, so there is no side to name yet.
    """
    return _git("checkout", tip, "--", path).returncode == 0


def _resolve_what_this_job_owns(tip: str, identity: str) -> bool:
    """Settle every conflicted path this job wrote, and stop the push on every other one.

    A conflicted filename that carries this job's identity is this job's own
    work, so what this job wrote is kept. Every other conflicted path stops the
    push and names itself. A path this job rebuilds cannot reach here - it was
    handed back to the tip before the rebase - so one that does is a gap in the
    refresh list, and the same refusal names it.

    A path the tip has deleted is left unmerged on purpose. Git exits 0 and
    changes nothing when the side it is asked for is the deleted one, and staging
    the file instead would settle a deletion this job never made: retention and
    the closed-day fold are what remove a file named for a job. So the index is
    read again at the end, and a path still unmerged there stops the push rather
    than reaching `git rebase --continue`.

    One identity is printed, never two. A file named for this job that the tip
    has deleted was deleted by retention or by a person rather than by another
    run, so a second identity field would always be empty.
    """
    listed = _git("diff", "--name-only", "--diff-filter=U", capture=True)
    if listed.returncode != 0:
        return False
    conflicted = _lines(listed)
    if not conflicted:
        _warn("the rebase stopped with no conflicted path to settle")
        return False
    for path in conflicted:
        if not _this_job_wrote(path, identity):
            _warn("a conflicted path this job did not write stops the push:")
            _warn(f"  path: {path}")
            _warn(f"  this job: {identity}")
            return False
        # Absent upstream means the tip deleted it, which the index read below
        # refuses. Leaving it here is what makes that read find it.
        present = _git("rev-parse", "--verify", "--quiet", f"{tip}:{path}", capture=True)
        if present.returncode != 0:
            continue
        if not _keep_what_this_job_wrote(path):
            return False
        _say(f"keeping what this job wrote at {path}")
    reread = _git("diff", "--name-only", "--diff-filter=U", capture=True)
    if reread.returncode != 0:
        return False
    unsettled = _lines(reread)
    if not unsettled:
        return True
    _warn("the tip has deleted a file this job wrote, so the push stops:")
    for path in unsettled:
        _warn(f"  path: {path}")
    _warn(f"  this job: {identity}")
    return False


def _hand_back(tip: str, refresh: Sequence[str]) -> bool:
    """Hand the rebuilt paths back to the tip the push wants.

    So the rebase finds no derived state to text-merge. What that tip carries is
    restored; what only this attempt created is removed, or the producer below
    reads its own last attempt as the day's history and counts itself twice.

    Every path is named. A directory that also holds this run's rendered assets
    is never refreshed whole: those assets came from another job's artifact and
    no producer here can make them again.
    """
    listed = _git(
        "diff", "--name-only", "--diff-filter=A", tip, "HEAD", "--", *refresh, capture=True
    )
    if listed.returncode != 0:
        return False
    for path in _lines(listed):
        if _git("rm", "--quiet", "--force", "--", path).returncode != 0:
            return False
    for path in refresh:
        # Absent upstream means this attempt introduced it, and the loop above
        # has already removed it.
        present = _git("rev-parse", "--verify", "--quiet", f"{tip}:{path}", capture=True)
        if present.returncode != 0:
            continue
        if not _keep_what_origin_has(tip, path):
            return False
    return True


def _spare_the_published_assets(
    tip: str, staged_paths: Sequence[str], drop_command: Sequence[str]
) -> bool:
    """Delete this run's copy of any rendered asset origin already publishes.

    A rendered asset is filed under the item's own id, so a path both sides hold
    is one story rendered twice - never two stories under one name. Two runs of a
    day overlap, neither checkout sees what the other has not pushed, and git
    cannot rebase two adds of one path: run 32869125768 finished eight workers
    and a visual planner and then threw the whole day away here.

    The tip's copy is published and a reader may already hold that address, and
    the rebuild keeps the tip's item over this run's in any case - so this run's
    file is the one nothing will reference. Deleting it is what lets the rebase
    apply, and the visual payload still names a file that is really in the tree.
    """
    listed = _git("ls-tree", "-r", "--name-only", tip, "--", *staged_paths, capture=True)
    if listed.returncode != 0:
        return False
    dropped = subprocess.run(list(drop_command), check=False, input=listed.stdout, text=True)
    return dropped.returncode == 0


def main(argv: Sequence[str]) -> int:
    """Commit the staged paths and push them, rebuilding while the clock allows."""
    settings = {
        name: os.environ.get(name, "")
        for name in ("COMMIT_MESSAGE", "NOTHING_STAGED_MESSAGE", "PUSH_FAILED_MESSAGE")
    }
    for name, value in settings.items():
        if not value:
            _warn(f"commit_and_push.py needs {name}")
            return 2
    message = settings["COMMIT_MESSAGE"]
    nothing_staged_message = settings["NOTHING_STAGED_MESSAGE"]
    push_failed_message = settings["PUSH_FAILED_MESSAGE"]

    deadline_seconds = os.environ.get("PUSH_DEADLINE_SECONDS", "")
    if not deadline_seconds:
        deadline_seconds = str(DEFAULT_PUSH_DEADLINE_SECONDS)
    if not WHOLE_NUMBER.match(deadline_seconds) or int(deadline_seconds) == 0:
        _warn("PUSH_DEADLINE_SECONDS must be a whole number of seconds, 1 or more")
        return 2

    staged_paths = list(argv)
    if not staged_paths:
        _warn("commit_and_push.py needs at least one path to stage")
        return 2

    # Split on spaces, so no path and no argument may carry one. A workflow
    # writes each of these as a folded scalar, which arrives as one line of
    # words.
    refresh = os.environ.get("REFRESH_PATHS", "").split()
    regenerate = os.environ.get("REGENERATE_COMMAND", "").split()
    drop_raced = os.environ.get("DROP_RACED_ASSETS_COMMAND", "").split()
    # A refresh with no producer hands this job's work to origin and never
    # rebuilds it. A producer with no refresh rebuilds on top of its own last
    # attempt and reads that attempt as the day's history.
    if refresh and not regenerate:
        _warn("REFRESH_PATHS needs REGENERATE_COMMAND: a refresh with no rebuild discards work")
        return 2
    if regenerate and not refresh:
        _warn(
            "REGENERATE_COMMAND needs REFRESH_PATHS: "
            "a rebuild with no refresh reads its own last attempt"
        )
        return 2
    # Only the amend below carries a drop into the commit the rebase replays, and
    # only a rebuilding job amends. Elsewhere the file would be deleted and then
    # left out of the push.
    if drop_raced and not regenerate:
        _warn(
            "DROP_RACED_ASSETS_COMMAND needs REGENERATE_COMMAND: "
            "only a rebuilding job commits the drops"
        )
        return 2

    # The identity this job's own files carry. `ledger.segment_name` names a
    # writer's file `<run_id>-<attempt>-<job>-<shard>`, and this project's run id
    # is itself `<date>-<execution>` - so a committed name reads
    # `2026-09-22-35743751882-1-work-03.csv`. That leading date is why the match
    # is not anchored to the first character: the runner hands this program the
    # execution number, and the date is the plan job's to choose. The execution
    # number is allocated by GitHub and is eleven digits, so finding it with the
    # attempt, the job and the shard behind it names one writer and no other.
    #
    # The shard is two digits in the filename and written plainly on the runner,
    # so it is padded here rather than compared as it arrives.
    shard_number = os.environ.get("SHARD") or "0"
    if not WHOLE_NUMBER.match(shard_number):
        _warn("SHARD must be a whole number of shards, 0 or more")
        return 2
    identity = (
        f"{os.environ.get('GITHUB_RUN_ID', '')}"
        f"-{os.environ.get('GITHUB_RUN_ATTEMPT', '')}"
        f"-{os.environ.get('GITHUB_JOB', '')}"
        f"-{int(shard_number):02d}"
    )
    # Said out loud so a dispatch can hold this against a filename the same run
    # committed. The identity decides which conflicted file this job may keep,
    # and until now it was only ever printed when it refused one.
    _say(f"this job's files are named for {identity}")

    rebased = False
    # `all` over a generator stops at the first failure, which is what `set -e`
    # did for these three. A `git add` that failed and was not read would reach
    # the check below, find nothing staged, and report success over work that
    # was never staged at all.
    prepared = all(
        _git(*command).returncode == 0
        for command in (
            ("config", "user.name", COMMITTER_NAME),
            ("config", "user.email", COMMITTER_EMAIL),
            ("add", *staged_paths),
        )
    )
    if not prepared:
        _warn("could not stage what this job produced")
        _report_rebased(rebased)
        return 1
    if _git("diff", "--cached", "--quiet").returncode == 0:
        _say(nothing_staged_message)
        _report_rebased(rebased)
        return 0
    if _git("commit", "-m", message).returncode != 0:
        _warn("could not commit what this job produced")
        _report_rebased(rebased)
        return 1

    # The loop is bounded by a clock rather than by a count. A fixed number of
    # attempts is spent at once however high it is set, once several runs commit
    # together; an optimistic rebase-and-push converges in expectation at any
    # commit rate, and a counter does not. Three attempts were what the loop
    # allowed and what every failure message claimed to have spent.
    #
    # Monotonic, so a clock the runner corrects mid-run cannot move the deadline.
    deadline = time.monotonic() + int(deadline_seconds)
    attempt = 0
    failures = 0
    window_opened: float | None = None
    stamps = Stamps()
    while True:
        attempt += 1
        step_started = time.monotonic()
        pushed = _git("push")
        stamps.push_ms = _elapsed_ms(step_started)
        stamps.window_ms = 0 if window_opened is None else _elapsed_ms(window_opened)
        if pushed.returncode == 0:
            _say_what_this_attempt_spent(attempt, "landed", stamps)
            _report_rebased(rebased)
            return 0
        _say_what_this_attempt_spent(attempt, "rejected", stamps)
        _say(f"push rejected, rebasing (attempt {attempt})")
        # Set before the rebase rather than after it. Every path out of here has
        # either rewritten the checkout or is about to, and a later step that
        # skipped its rebuild on a maybe is the failure this output exists to
        # stop.
        rebased = True
        failures += 1
        if time.monotonic() >= deadline:
            break
        _back_off(failures, attempt)
        if not _discard_noise():
            _warn("could not clear the working tree before the rebase")
            break
        # The next attempt's window opens here, at the fetch. What it measures is
        # the span another run has to push into before this one pushes again, so
        # the waiting above is deliberately outside it.
        window_opened = time.monotonic()
        stamps.fetch_ms = 0
        stamps.handback_ms = 0
        stamps.rebase_ms = 0
        stamps.rebuild_ms = 0
        step_started = time.monotonic()
        # A fetch that fails is a transient, and riding it out is what the
        # deadline is for. A broken token spends 300 s of a six-hour budget and
        # says so six times.
        fetched = _git("fetch", "origin", "main")
        stamps.fetch_ms = _elapsed_ms(step_started)
        if fetched.returncode != 0:
            _warn("could not read origin/main, so this attempt waits and asks again")
            continue
        # After the fetch, because the answer is a question about the tip.
        if not _clear_what_the_tip_will_write_over("FETCH_HEAD"):
            _warn("could not clear the untracked files origin/main would write over")
            break
        if drop_raced and not _spare_the_published_assets("FETCH_HEAD", staged_paths, drop_raced):
            _warn("could not drop this attempt's copies of the assets origin publishes")
            break
        step_started = time.monotonic()
        if refresh:
            if not _hand_back("FETCH_HEAD", refresh):
                _warn("could not hand the rebuilt paths back to origin/main")
                break
            # The drops above are worktree deletions, which no index knows about
            # yet.
            if _git("add", *staged_paths).returncode != 0:
                _warn("could not stage the refreshed paths")
                break
            if _git("commit", "--amend", "--no-edit", "--allow-empty").returncode != 0:
                _warn("could not fold the refreshed paths into the commit")
                break
        stamps.handback_ms = _elapsed_ms(step_started)
        step_started = time.monotonic()
        # `merge.directoryRenames=false` on both spellings below. Git guesses
        # that a directory whose files all moved away was RENAMED to wherever
        # they went, and it applies that guess to a file the other side added
        # into the emptied directory. The closed-day fold replaces a day's writer
        # files with one settled file, so a sibling adding a new writer file into
        # that day is read as adding into a directory that no longer exists, and
        # the rebase stops with `CONFLICT (file location)` over a tree that was
        # correct. Proved in a scratch repository on 2026-09-22: the same replay
        # conflicts with the guess on and reports `Successfully rebased` with it
        # off, losing nothing.
        replayed = _git("-c", "merge.directoryRenames=false", "rebase", "FETCH_HEAD")
        if replayed.returncode != 0:
            settled = _resolve_what_this_job_owns("FETCH_HEAD", identity) and (
                _git(
                    "-c",
                    "merge.directoryRenames=false",
                    "rebase",
                    "--continue",
                    environment={**os.environ, "GIT_EDITOR": "true"},
                ).returncode
                == 0
            )
            if not settled:
                _warn("the rebase did not apply cleanly")
                if _git("-c", "merge.directoryRenames=false", "rebase", "--abort").returncode != 0:
                    _warn("the rebase could not be aborted")
                break
        stamps.rebase_ms = _elapsed_ms(step_started)
        if not refresh:
            continue
        # Keep the content, drop the commit: the producer is about to rewrite
        # most of it, and one run leaves one commit however many attempts it
        # took.
        if _git("reset", "--soft", "FETCH_HEAD").returncode != 0:
            _warn("could not reopen the commit for the rebuild")
            break
        _say("rebuilding the day against origin/main")
        step_started = time.monotonic()
        rebuilt = subprocess.run(list(regenerate), check=False)
        if rebuilt.returncode != 0:
            _warn("the rebuild failed against origin/main")
            break
        stamps.rebuild_ms = _elapsed_ms(step_started)
        if _git("add", *staged_paths).returncode != 0:
            _warn("could not stage the rebuilt paths")
            break
        if _git("diff", "--cached", "--quiet").returncode == 0:
            # origin already carries everything this run made.
            _say(nothing_staged_message)
            _report_rebased(rebased)
            return 0
        if _git("commit", "-m", message).returncode != 0:
            _warn("could not commit the rebuild")
            break

    # The attempt this run really spent, printed beside the caller's own sentence
    # rather than folded into it. A conflicting rebase leaves the loop on the
    # first attempt, so every recorded failure had spent one while the message
    # said three, and that sentence sends the next reader to the retry count -
    # which cannot help them.
    _report_rebased(rebased)
    _warn(push_failed_message)
    _warn(f"the push was given up on attempt {attempt} after {deadline_seconds}s")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
