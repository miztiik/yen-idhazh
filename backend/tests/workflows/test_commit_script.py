"""What does the shared commit program do when it loses the race to push?"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

import pytest
from conftest import read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.evals import writer as score_writer
from utilities import commit_and_push

from ._harness import (
    COMMIT_IDENTITY,
    COMMIT_PROGRAM,
    COMMIT_STEPS,
    GIT_IDENTITY_SOURCES,
    RACED_ASSET,
    RACED_ITEM_ID,
    SUBSTITUTED_DATE,
    SUBSTITUTED_DAY_DIR,
    _chart,
    _commit_call,
    _digest_origin,
    _drop_command,
    _git,
    _isolated_env,
    _mid_rebase,
    _push_attempts,
    _race,
    _race_the_day,
    _reading_its_output,
    _rebuild,
    _rebuild_command,
    _reject_the_first_pushes,
    _rows,
    _run_commit_script,
    _scripted_origin,
    _seed_ledger,
    _step_outputs,
    _tracked,
    _write,
    requires_space_free_paths,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


def _a_writers_file(*, attempt: int) -> str:
    """One writer's own file inside a day directory, spelled by the producer.

    A test of what a rebase does to two committed names has to use names a run
    can actually produce: the shard is two digits in a committed name and the
    date comes from the rows rather than from the runner, so a name written by
    hand here would be a name no writer ever takes.
    """
    return ledger.day_shard_relpath(
        ledger.SegmentLedger.ITEM_HEALTH,
        date=SUBSTITUTED_DATE,
        run_id=f"{SUBSTITUTED_DATE}-40000000001",
        attempt=attempt,
        job=ServerJob.PLAN,
        shard=0,
    )


def _committed_day(origin: Path, env: dict[str, str], relpath: str) -> list[dict[str, str]]:
    """Every writer's rows for one committed day, in the order a settlement reads them.

    A day is a directory of writer-owned files now, so one `git show` answers
    with a listing rather than with rows. The files are read in name order,
    which is the order `day_shards` reads them in.
    """
    listed = _git(origin, env, "ls-tree", "--name-only", f"main:{relpath}").split()
    return [
        row
        for name in sorted(listed)
        for row in _rows(_git(origin, env, "show", f"main:{relpath}/{name}"))
    ]


def test_every_committing_job_configures_the_same_identity() -> None:
    """The repository commits under one name, and it says so in one voice.

    A hosted runner carries no git identity, so a job that commits has to set
    one or `git commit` refuses. The commit program is executed by the tests
    below, which read the name off the commit it pushed - so what is left here
    is every other file that sets an identity and that nothing runs. One of
    those could drift to a different name and nothing would notice until a
    reader wondered who the other authors were.
    """
    assert f"{commit_and_push.COMMITTER_NAME} <{commit_and_push.COMMITTER_EMAIL}>" == (
        COMMIT_IDENTITY
    )

    assert GIT_IDENTITY_SOURCES, "no file is read, so this test would pass on nothing"
    for path in GIT_IDENTITY_SOURCES:
        text = read_text(path)
        author = re.search(r'git config user\.name "([^"]+)"', text)
        address = re.search(r'git config user\.email "([^"]+)"', text)
        assert author is not None, f"{path.name} commits, so it must set user.name"
        assert address is not None, f"{path.name} commits, so it must set user.email"
        assert f"{author.group(1)} <{address.group(1)}>" == COMMIT_IDENTITY


@requires_space_free_paths
@pytest.mark.parametrize("job_name", sorted(COMMIT_STEPS))
def test_the_commit_step_pushes_what_it_staged(tmp_path: Path, job_name: str) -> None:
    staged_paths, settings = _commit_call(job_name)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    if "REGENERATE_COMMAND" in settings:
        # The push wins here, so the producer never runs. Point it at the
        # harness one anyway: the pipeline's own `assemble` anchors its paths on
        # the installed repository, so a regression that made it run would write
        # into the working repository rather than fail the test.
        settings = {**settings, "REGENERATE_COMMAND": _rebuild_command(SUBSTITUTED_DATE)}

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        settings["COMMIT_MESSAGE"]
    )
    # The script sets the committer itself, and the test supplies none.
    assert _git(origin, env, "log", "-1", "--format=%an <%ae>").strip() == COMMIT_IDENTITY
    # And it adds no attribution tag (CLAUDE.md section 8). Nothing refused one
    # until now, so the day a tool starts writing `Co-authored-by` into a commit
    # body it would reach the permanent record with no test in the way.
    assert "Co-authored-by" not in _git(origin, env, "log", "-1", "--format=%B")
    assert _git(runner, env, "status", "--porcelain").strip() == ""


def test_the_commit_step_says_so_and_stops_when_nothing_changed(tmp_path: Path) -> None:
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    before = _git(origin, env, "rev-parse", "main").strip()

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _git(origin, env, "rev-parse", "main").strip() == before
    assert _git(runner, env, "rev-parse", "HEAD").strip() == before


def test_the_commit_step_rebases_past_a_racing_commit(tmp_path: Path) -> None:
    """The whole point of the loop: a push that loses a race still lands."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    _write(runner / "runner-noise.txt", "dirty\n")
    _write(runner / "leftover.log", "kept\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert "discarding working-tree noise before the rebase:" in result.stdout
    assert "runner-noise.txt" in result.stdout
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    # The noise was discarded; the untracked file was not.
    assert (runner / "runner-noise.txt").read_text(encoding="ascii") == "clean\n"
    assert (runner / "leftover.log").is_file()
    assert _git(runner, env, "status", "--porcelain", "--untracked-files=no").strip() == ""


@requires_space_free_paths
def test_a_rebase_is_not_blocked_by_an_untracked_file_the_tip_carries(tmp_path: Path) -> None:
    """Run `35152132574`: an untracked file stopped the rebase and cost a shard its rows.

    A work shard wrote `state/host-fingerprint/2026/09/16.csv` at a time when its
    commit step did not stage that path, so the file stayed untracked. A sibling
    shard pushed the same path while this one was still reading articles, and the
    rebase would not even detach - `untracked working tree files would be
    overwritten by checkout`. There was no rebase left to abort, the loop broke on
    the first of its three attempts, and 303 measured rows over six ledgers were
    committed locally and thrown away with the runner.

    The work shard stages `state` whole now, which closes that collision for
    every tree under it. The list a job hands the script is still written by
    hand, and a new writer has arrived without it three times - so the path
    modelled here is one outside the tree this job stages. A path this job did
    not stage is a path it is not pushing, so the file goes and everything that
    WAS staged still lands.
    """
    staged_paths, settings = _commit_call("work")
    unstaged = "frontend/public/a-later-writer/2026-09-16.json"
    assert not any(unstaged == path or unstaged.startswith(f"{path}/") for path in staged_paths), (
        "this models a writer the staging list has not caught up with"
    )
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, unstaged, "version\nthe sibling shard\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    _write(runner / unstaged, "version\nthis shard\n")
    _write(runner / "llama-server.log", "kept\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert unstaged in result.stdout, "the log must name every file it removed"
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    # What this shard staged landed.
    assert "fresh" in _git(origin, env, "show", f"main:{_seed_ledger(staged_paths[0])}")
    # The tip's copy of the path nobody staged is what the tree holds now, and the
    # untracked file nothing was going to write over is untouched.
    assert (runner / unstaged).read_text(encoding="ascii") == "version\nthe sibling shard\n"
    assert (runner / "llama-server.log").is_file()


def test_a_push_that_landed_first_try_reports_no_rebase(tmp_path: Path) -> None:
    """What the rebuild step reads. A clean push left the tree it was handed.

    Written explicitly rather than left unwritten. An output nobody wrote is the
    empty string, which is falsy and would skip the rebuild too - and which is
    indistinguishable from the script dying before it could answer.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected" not in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


def test_a_commit_that_staged_nothing_reports_no_rebase(tmp_path: Path) -> None:
    """Nothing was pushed, so there is no new tree for a later step to read."""
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["NOTHING_STAGED_MESSAGE"] in result.stdout
    assert _step_outputs(written) == {"rebased": "false"}


def test_a_push_that_lost_the_race_reports_the_rebase(tmp_path: Path) -> None:
    """The rebase replaced the checkout, so the build made before it is stale.

    This is what `digest.yml` keys the rebuild on. Run 33270983446 weighed one
    tree's pages against another tree's ceilings and failed a day that had
    already published; a rebase that reported nothing would do it again.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    _, runner = _scripted_origin(tmp_path, env, staged_paths)
    _race(tmp_path, env, "docs/unrelated.md", "racing\n")
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    settings, written = _reading_its_output(tmp_path, settings)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "push rejected, rebasing (attempt 1)" in result.stdout
    assert _step_outputs(written) == {"rebased": "true"}


def test_the_commit_script_still_runs_where_no_step_output_exists(tmp_path: Path) -> None:
    """The guard on the write, and it is what lets one copy of the script serve both.

    `set -u` ends the run on an unset variable, so an unguarded write would kill
    every one of these tests and anybody running the script by hand. Only a
    workflow step has `$GITHUB_OUTPUT`.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")

    assert "GITHUB_OUTPUT" not in {**env, **settings}, "the harness is what removes it"
    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "GITHUB_OUTPUT" not in result.stderr, "an unset variable must not end the script"
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == settings["COMMIT_MESSAGE"]


#: Every way `main` hands a number back that is not a caller error. Three come
#: back zero - nothing staged, the push landed, the rebuild produced nothing new
#: - two cannot commit what the job produced, and one gives up on the clock. A
#: caller error returns 2 and is deliberately outside this count.
WAYS_OUT: Final = 6


def _statement_blocks(node: ast.AST) -> Iterator[list[ast.stmt]]:
    """Every list of statements under a node, so a return reads with its neighbours."""
    for child in ast.walk(node):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(child, field, None)
            if isinstance(block, list) and all(isinstance(item, ast.stmt) for item in block):
                yield block


def _says_whether_it_rebased(before: Sequence[ast.stmt]) -> bool:
    """Whether one of these statements is the call that writes the step output."""
    return any(
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "_report_rebased"
        for statement in before
    )


def test_every_way_out_of_the_commit_program_says_whether_it_rebased() -> None:
    """Three exits return zero and a fixture reaches two of them.

    The third - origin already holding everything a rebuild produced - needs a
    racing run that publishes the same items, and the value it reports decides
    whether the day's own gate reads a stale build. So the exits are checked
    where they are written instead.

    A caller error returns 2 and is deliberately out of scope. Those fire before
    anything is committed, they fail the step, and a step that failed has
    already stopped the rebuild.
    """
    routine = next(
        node
        for node in ast.walk(ast.parse(read_text(COMMIT_PROGRAM)))
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    ways_out = [
        (node.lineno, _says_whether_it_rebased(block[max(0, index - 3) : index]))
        for block in _statement_blocks(routine)
        for index, node in enumerate(block)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and node.value.value in {0, 1}
    ]

    assert len(ways_out) == WAYS_OUT, (
        "three ways out with nothing wrong, two that cannot commit, and the one that gives up"
    )
    silent = [line for line, said in ways_out if not said]
    assert not silent, (
        f"line(s) {silent} leave without saying whether the checkout was rewritten"
    )


def test_two_runs_writing_their_own_files_both_land(tmp_path: Path) -> None:
    """Two writers, two files, one rebase, and nothing has to choose.

    This is where the loop used to die. `git pull --rebase origin main` was the
    one unguarded command in it, so a conflicting rebase ended the script inside
    attempt 1 under `set -e`: no attempt 2, no failure message, no day, and a
    checkout left mid-rebase. Measured that way on 2026-08-25, git 2.55.0, bash
    5.3.15. Every command in the loop is guarded now.

    A union merge driver on the shared ledger head was the other half of the
    answer until 2026-09-19, and it was the wrong half: it concatenated two
    attempts at the same row as readily as two independent ones. Each writer
    takes the file its own run, attempt, job and shard name instead, so two
    sides of a race are two adds of two paths and the rebase applies both whole.

    The two names come from the producer. A shard is two digits in a committed
    name and a runner holds a bare number, so a name spelled by hand here is not
    a name a run can produce.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    theirs = _a_writers_file(attempt=1)
    ours = _a_writers_file(attempt=2)
    _race(tmp_path, env, theirs, "header\ntheirs\n")
    _write(runner / ours, "header\nours\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-2").splitlines() == [
        settings["COMMIT_MESSAGE"],
        "racing change",
    ]
    assert _git(origin, env, "show", f"main:{theirs}").splitlines() == ["header", "theirs"]
    assert _git(origin, env, "show", f"main:{ours}").splitlines() == ["header", "ours"]
    assert not _mid_rebase(runner)


def test_a_rebase_it_cannot_finish_still_ends_the_script_cleanly(tmp_path: Path) -> None:
    """The guard, proved by running it: no command in the loop can exit early.

    A ledger retired upstream while this run appended to it is a modify/delete,
    which no merge driver resolves. The loop must abort the rebase, say what
    happened, print the failure message and leave the checkout usable - not stop
    on the line that failed.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    other = tmp_path / "other"
    _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _git(other, env, "rm", "--quiet", f"{staged_paths[0]}/ledger.csv")
    _git(other, env, "commit", "-m", "retire the ledger")
    _git(other, env, "push", "origin", "main")
    _write(runner / staged_paths[0] / "ledger.csv", "header\nrow-0\nours\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "the rebase did not apply cleanly" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    # The attempt it really spent. A conflicting rebase leaves the loop on the
    # first one, so a message naming the count it was allowed sends the reader
    # to the retry budget, which is not what stopped it.
    assert "the push was given up on attempt 1" in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == "retire the ledger"
    assert not _mid_rebase(runner)


def test_a_push_rejected_more_times_than_the_old_loop_allowed_still_lands(
    tmp_path: Path,
) -> None:
    """Row 4's Oracle: the loop stops on a clock, so a fourth attempt exists.

    Origin refuses the first four pushes and takes the fifth. The old loop had
    three attempts and would have given up on the third, published nothing, and
    said it had spent three - so this case could not pass before and its whole
    value is that it does now.

    Every attempt prints one line, and the windows those lines report sum to
    less than the deadline. What this cannot settle is the real window on a
    runner: that is what the printed line exists to collect, over twenty runs.
    """
    staged_paths, settings = _commit_call("plan")
    deadline = 60
    settings = {**settings, "PUSH_DEADLINE_SECONDS": str(deadline)}
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    _reject_the_first_pushes(origin, 4)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == settings["COMMIT_MESSAGE"]

    attempts = _push_attempts(result.stdout)
    assert [row["attempt"] for row in attempts] == [1, 2, 3, 4, 5]
    assert [row["outcome"] for row in attempts] == [
        *["rejected"] * 4,
        "landed",
    ]
    # Attempt 1 has no window in the retry sense: nothing fetches before the
    # first push, so its exposure is the whole job rather than a retry
    # parameter, and its zero is the truth about it.
    assert attempts[0]["window_ms"] == 0
    assert all(row["window_ms"] > 0 for row in attempts[1:])
    assert sum(row["window_ms"] for row in attempts) < deadline * 1000
    # Six stamps, because one figure cannot tell a slow rebuild from a slow push.
    for row in attempts:
        assert set(row) == {
            "attempt",
            "job",
            "shard",
            "outcome",
            "window_ms",
            "fetch_ms",
            "handback_ms",
            "rebase_ms",
            "rebuild_ms",
            "push_ms",
        }
    assert not _mid_rebase(runner)


def test_a_push_nothing_will_take_gives_up_on_the_clock_and_says_what_it_spent(
    tmp_path: Path,
) -> None:
    """The other end of the deadline: it is a bound, not a promise.

    Origin refuses every push. The loop has to give up on its own clock, leave
    no rebase in progress, print the caller's own sentence, and name the attempt
    it really reached - which is what a reader needs to tell a run that spent
    its budget from a run that stopped on the first conflict.

    **How many attempts fit in three seconds is a fact about the machine.** This
    asserted two until 2026-09-24, and failed on a box running several test
    suites at once: one rejected push there costs more than the whole deadline,
    so the loop gets a single attempt and the count is right rather than wrong.
    The claim it was reaching for - that the deadline is a clock and not a retry
    counter - is proven without a stopwatch by the test above, which reaches a
    fifth attempt inside sixty seconds and could not pass against the three-try
    loop this replaced. What is left here is what only this case can show, and
    none of it depends on how fast the push was.
    """
    staged_paths, settings = _commit_call("plan")
    settings = {**settings, "PUSH_DEADLINE_SECONDS": "3"}
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    before = _git(origin, env, "rev-parse", "main").strip()
    _write(runner / _seed_ledger(staged_paths[0]), "header\nrow-0\nfresh\n")
    _reject_the_first_pushes(origin, 99)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    spent = _push_attempts(result.stdout)
    assert spent, "a run that gave up without attempting a push reports nothing to read"
    # The count it names is the count it printed, whether the box fitted one
    # attempt into the deadline or seven.
    assert f"the push was given up on attempt {len(spent)} after 3s" in result.stderr
    assert [row["attempt"] for row in spent] == list(range(1, len(spent) + 1))
    assert all(row["outcome"] == "rejected" for row in spent)
    assert _git(origin, env, "rev-parse", "main").strip() == before
    assert not _mid_rebase(runner)


def test_a_new_file_in_a_drained_directory_still_rebases(tmp_path: Path) -> None:
    """Row 2's Oracle, run rather than read: the B6 shape, at exit 0.

    One job drains a directory - which is what the closed-day fold does to a day
    that can gain no more rows - while another writes a brand-new file into it.
    Git reads the emptied directory as having been RENAMED to wherever its files
    went, and applies that guess to the arriving file, so the rebase stops with
    `CONFLICT (file location)` over a tree that was correct and the job loses
    what it had already finished.

    `merge.directoryRenames=false` is what turns the guess off. Nothing about
    the data changes: both sides are applied whole, the tip's deletion still
    stands, and the arriving file lands.

    What this cannot settle is whether the guess is left on somewhere else in
    the pipeline. It drives the one script the daily run pushes through.
    """
    staged_paths, settings = _commit_call("plan")
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    drained = _a_writers_file(attempt=1)
    arriving = _a_writers_file(attempt=2)

    # The base both sides start from: one writer's file waiting to be folded.
    other = tmp_path / "other"
    _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _write(other / drained, "header\nwaiting\n")
    _git(other, env, "add", drained)
    _git(other, env, "commit", "-m", "one writer's file is waiting")
    _git(other, env, "push", "origin", "main")
    _git(runner, env, "pull", "--ff-only", "origin", "main")

    # Origin's tip: a sibling folded that day and deleted the file it read,
    # which leaves the day directory holding nothing.
    _git(other, env, "pull", "--ff-only", "origin", "main")
    _git(other, env, "rm", "--quiet", drained)
    _git(other, env, "commit", "-m", "the fold drained the day")
    _git(other, env, "push", "origin", "main")

    # This job: a straggler, written into the day the tip just emptied.
    _write(runner / arriving, "header\nmine\n")

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert "the rebase did not apply cleanly" not in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "show", f"main:{arriving}").splitlines() == ["header", "mine"]
    assert not _tracked(origin, env, drained), "the tip's own deletion must still stand"
    assert not _mid_rebase(runner)


@requires_space_free_paths
def test_the_day_publishes_when_origin_moved_under_it(tmp_path: Path) -> None:
    """The Oracle: a stale base is answered by a current base, not by a text merge.

    Run `32772221068` lost a finished day here. The assemble job checks out
    main's tip at TRIGGER time and the run takes 164-184 min, so the day was
    always rebuilt from a base up to three hours old, and the push found a main
    that had moved. Here it has moved twice: another run published the same day,
    and a pull request merged on top.

    So the day is refreshed from the tip the push wants and built again against
    it. Both runs' items reach the reader, both runs' rows reach all three
    ledgers exactly once, the pull request is untouched, and this run's rendered
    chart - which no producer in this job can make again - is still there.
    """
    date = SUBSTITUTED_DATE
    month = date[:7]
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path, env, date, ["item-c"], "Merge pull request #123 from someone/branch"
    )
    # This run: the visuals artifact unpacked a chart into the day's directory,
    # and assemble published two items on the base the checkout carried.
    _write(runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg", "<svg />\n")
    _rebuild(runner, env, date, ["item-d", "item-e"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert "rebuilding the day against origin/main" in result.stdout
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert _git(origin, env, "log", "--format=%s", "-3").splitlines() == [
        f"digest: {date}",
        "Merge pull request #123 from someone/branch",
        f"digest: {date}",
    ]

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Run three, not a second run two. The rebuild read the day origin holds, so
    # it knows which run it is; on its own last attempt it would not.
    assert day["runs"] == [
        {"n": 1, "items_added": 2},
        {"n": 2, "items_added": 1},
        {"n": 3, "items_added": 2},
    ]
    manifest = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/run.json"))
    assert manifest["runs"] == day["runs"]

    published = _rows(_git(origin, env, "show", f"main:{ledger.published_relpath(date)}"))
    scores = _committed_day(origin, env, score_writer.ledger_relpath(date))
    health = _committed_day(origin, env, ledger.item_health_relpath(date))
    every_item = ["item-a", "item-b", "item-c", "item-d", "item-e"]
    # Exactly once each in the two day trees. Each run writes the one file its
    # own run, attempt, job and shard name, so a rebuild cannot add to what a
    # previous attempt wrote - it replaces the file it owns.
    assert [row["item_id"] for row in scores] == every_item
    assert [row["item_id"] for row in health] == every_item
    # `state/published` is the one ledger here that is still one file a day and
    # still appends blind, and it is deliberately not handed back to the tip:
    # the union driver settles it. The rebuild therefore appends this run's two
    # items a second time, on top of the pair its first attempt had already
    # written. That costs two rows and moves no publication date, because
    # `ledger.load_published` keeps the earliest date per address.
    assert [row["item_id"] for row in published] == [*every_item, "item-d", "item-e"]
    assert sorted({row["item_id"] for row in published}) == every_item

    telemetry = _rows(_git(origin, env, "show", f"main:frontend/public/telemetry/{month}.csv"))
    assert telemetry == health, "the public projection is a rewrite of item-health, not a merge"

    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"
    assert _tracked(origin, env, f"{SUBSTITUTED_DAY_DIR}/assets/chart-1.svg")
    assert (runner / SUBSTITUTED_DAY_DIR / "assets" / "chart-1.svg").is_file()
    assert not _mid_rebase(runner)


@requires_space_free_paths
def test_two_runs_that_rendered_one_item_still_publish_the_day(tmp_path: Path) -> None:
    """The Oracle above, with the one thing it never had: both sides create the path.

    Run `32869125768` finished eight workers and a visual planner and then lost
    the whole day here. A chart was filed by its vertical and its ordinal within
    the day, and the ordinal was seeded by reading the day's directory - so two
    runs of one day, neither able to see what the other pushed, wrote
    `energy-01.svg`
    for DIFFERENT items with different bytes. Git cannot rebase two adds of one
    path, `assemble` exited 1, and the `items-*` artifacts expired with every
    summary in them.

    A chart is now filed under its item's own id, so that case cannot happen at
    all. What is left is this one: two runs rendering the SAME item, which is
    one story's picture drawn twice. The tip's copy is published and a reader
    may already hold that address, and the rebuild keeps the tip's item anyway,
    so this run's copy is dropped and the day publishes.
    """
    date = SUBSTITUTED_DATE
    raced, fresh = RACED_ITEM_ID, "energy-0000000002"
    fresh_asset = f"digest/{date.replace('-', '/')}/{fresh}.json"
    staged_paths, settings = _commit_call("assemble")
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command(date),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(
        tmp_path,
        env,
        date,
        [raced],
        "Merge pull request #125 from someone/branch",
        charts={raced: RACED_ASSET},
    )
    # This run planned the same item, because the push above had not happened
    # when it planned - and drew it again, to different bytes.
    _chart(runner, date, raced, RACED_ASSET, body="ours")
    _chart(runner, date, fresh, fresh_asset)
    _rebuild(runner, env, date, [raced, fresh])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("push rejected, rebasing (attempt ") == 1
    assert f"{RACED_ASSET} is already published, so this run's copy of it was dropped" in (
        result.stdout
    )
    assert settings["PUSH_FAILED_MESSAGE"] not in result.stderr
    assert not _mid_rebase(runner)

    day = json.loads(_git(origin, env, "show", f"main:{SUBSTITUTED_DAY_DIR}/digest.json"))
    assert day["items"] == ["item-a", "item-b", raced, fresh]
    # The item this run introduced kept its picture, and no two items share one.
    assert day["visuals"] == {raced: RACED_ASSET, fresh: fresh_asset}
    assert len(set(day["visuals"].values())) == len(day["visuals"])
    # The gate a broken image would fail: every path the day publishes is a file
    # the day publishes. A picture that 404s is worse than a job that stops.
    for relpath in day["visuals"].values():
        assert _tracked(origin, env, f"frontend/public/{relpath}")
    # The published address still holds the bytes that were published under it,
    # rather than this run's second attempt at the same picture.
    assert _git(origin, env, "show", f"main:frontend/public/{RACED_ASSET}") == (
        f'{{"item_id": "{raced}"}}\n'
    )
    assert _git(origin, env, "show", f"main:frontend/public/{fresh_asset}") == (
        f'{{"item_id": "{fresh}"}}\n'
    )
    assert _git(origin, env, "show", "main:docs/unrelated.md") == "merged by a pull request\n"


@requires_space_free_paths
def test_a_rebuild_that_fails_spends_the_attempts_and_says_which(tmp_path: Path) -> None:
    """A producer that cannot run is a lost day, said out loud, not a half-rebased tree."""
    date = SUBSTITUTED_DATE
    staged_paths, settings = _commit_call("assemble")
    # A date this checkout has no artifacts for: the producer really fails, on a
    # real missing input, rather than being told to pretend.
    settings = {
        **settings,
        "REGENERATE_COMMAND": _rebuild_command("2026-08-24"),
        "DROP_RACED_ASSETS_COMMAND": _drop_command(date),
    }
    env = _isolated_env(tmp_path)
    origin, runner = _digest_origin(tmp_path, env, date)
    _race_the_day(tmp_path, env, date, ["item-c"], "Merge pull request #124 from someone/other")
    _rebuild(runner, env, date, ["item-d"])

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert "the rebuild failed against origin/main" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == (
        "Merge pull request #124 from someone/other"
    )
    assert not _mid_rebase(runner)
