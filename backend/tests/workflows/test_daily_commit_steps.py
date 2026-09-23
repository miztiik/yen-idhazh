"""Does the daily run ever commit from a dirty tree, and do its commit steps share one program?"""

from __future__ import annotations

import ast
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import ledger, paths
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.base import ServerJob

from ._harness import (
    COMMIT_JOBS,
    COMMIT_PROGRAM,
    COMMIT_SCRIPT_ENV,
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    COMMIT_WORKFLOWS,
    DROP_ENTRY_POINT,
    FINGERPRINT_STEP,
    PLAN_STEP,
    SUBSTITUTED_DATE,
    SUBSTITUTED_DAY_DIR,
    TAKE_STATE_CALL,
    TAKE_STATE_STEP,
    TOLERATED,
    _commit_call,
    _git,
    _git_calls,
    _isolated_env,
    _load_workflows,
    _mapping,
    _mid_rebase,
    _normalize_condition,
    _race,
    _run_commit_script,
    _script,
    _scripted_origin,
    _step,
    _steps,
    _substitute,
    _write,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

#: A `git rebase` call, however many `-c <setting>` overrides sit between the two
#: words. Matched rather than compared as text, because the settings are what
#: this file has to be able to read: `git rebase ` as a literal stopped finding
#: the call the day one was added.
GIT_REBASE: Final = re.compile(r"\bgit\b(?:\s+-c\s+\S+)*\s+rebase\b")

#: What every rebase here turns off. Git reads a directory whose files all moved
#: away as RENAMED, and applies that to a file the other side added into it.
DIRECTORY_RENAMES_OFF: Final = "-c merge.directoryRenames=false"

#: The rows each writer in the three tests below puts in its own file, so a test
#: can say which writer's bytes survived rather than which side of a graph did.
RESOLVER_ROWS: Final = FIXTURES_DIR / "resolver"

#: The run this job belongs to, and the run a second job belongs to. Both are
#: spelled here because `_isolated_env` hands the script the environment it
#: inherited, and on a GitHub runner that already carries a real run's id.
THIS_EXECUTION: Final = "40000000001"
ANOTHER_EXECUTION: Final = "40000000002"

#: The day these writers belong to. A run id is `<date>-<execution>`, so the
#: date is in every committed filename and is not in anything the runner sets.
#: That gap is the whole reason the script looks for its identity anywhere in a
#: name rather than only at the front.
THE_DAY: Final = "2026-09-22"

#: What `ledger.day_shard_path` is given, as opposed to what GitHub allocates.
THIS_RUN: Final = f"{THE_DAY}-{THIS_EXECUTION}"
ANOTHER_RUN: Final = f"{THE_DAY}-{ANOTHER_EXECUTION}"

#: The other two elements of a writer's identity. One attempt and one job is all
#: these three tests need: what they vary is the run.
THIS_ATTEMPT: Final = 1
THIS_JOB: Final = ServerJob.PLAN

#: How the script spells this job when it refuses a path. Every job but a work
#: shard leaves `SHARD` empty, and the filename writes a shard with two digits,
#: so the identity ends `00`.
THIS_IDENTITY: Final = f"{THIS_EXECUTION}-{THIS_ATTEMPT}-{THIS_JOB.value}-00"


def _as_this_job(settings: dict[str, str]) -> dict[str, str]:
    """The commit step's own settings, plus the identity a runner would set.

    `SHARD` is named and left empty rather than left out. The environment a test
    inherits could carry one, and an identity that changes with the machine is
    an identity no assertion can name.
    """
    return {
        **settings,
        "GITHUB_RUN_ID": THIS_EXECUTION,
        "GITHUB_RUN_ATTEMPT": str(THIS_ATTEMPT),
        "GITHUB_JOB": THIS_JOB.value,
        "SHARD": "",
    }


def _writer_file(run_id: str) -> str:
    """One writer's own file, from the grammar the writer itself uses.

    Built through `ledger.day_shard_relpath` rather than spelled here, so a test
    of the predicate that reads a filename cannot pass against a filename no
    writer produces.
    """
    return ledger.day_shard_relpath(
        ledger.SegmentLedger.ITEM_HEALTH,
        date=THE_DAY,
        run_id=run_id,
        attempt=THIS_ATTEMPT,
        job=THIS_JOB,
        shard=0,
    )


def test_no_rebase_in_the_daily_run_starts_on_a_dirty_tree() -> None:
    """A rebase that refuses to start throws away a day the run already computed.

    Run `32671663130` died exactly this way: one tracked file was modified in the
    checkout before any step ran, and the retry loop lost plan, four shards and
    assemble with it. The work is committed before the loop begins, so the fix is
    to drop what is left rather than to carry it into the rebase.

    Run `35152132574` died the same way through the other door. An UNTRACKED file
    also stops the rebase, whenever the incoming commits add that same path: the
    detach refuses with `untracked working tree files would be overwritten`. A
    work shard's own `state/host-fingerprint/2026/09/16.csv` was the file, a
    sibling shard had just pushed it, and 303 measured rows went with the runner.
    So the loop clears both kinds, and the untracked half is narrow.

    This reads the shared program and the workflow's own `run:` bodies, so an
    inline loop written back into a step is still covered. The program's git
    calls are argument lists rather than shell words, so they are rendered back
    into command lines and read by the same rules.
    """
    workflow = _load_workflows()["digest.yml"]
    jobs = _mapping(workflow.get("jobs"), "jobs")

    bodies = [
        (f"{job_name}/{step.get('name')}", script)
        for job_name in jobs
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str)
    ]
    bodies.append(
        (
            COMMIT_PROGRAM.relative_to(REPO_ROOT).as_posix(),
            "\n".join(_git_calls(read_text(COMMIT_PROGRAM))),
        )
    )
    scripts = [(where, body) for where, body in bodies if GIT_REBASE.search(body)]
    assert scripts, "the daily run must still push through a rebase-and-retry loop"

    for where, script in scripts:
        lines = [line.strip() for line in script.splitlines()]
        # `--autostash` looks like the answer and is not: it stashes the noise,
        # then fails the step when the stash will not reapply.
        assert "--autostash" not in script, f"{where} must not stash before rebasing"
        discard = next(
            index for index, line in enumerate(lines) if line.startswith("git checkout -- .")
        )
        rebase = next(
            index
            for index, line in enumerate(lines)
            if not line.startswith("#") and GIT_REBASE.search(line) and "--abort" not in line
        )
        assert discard < rebase, f"{where} must clear the tree before it rebases"
        # A blanket clean is the wrong answer: `llama-server.log` and the memory
        # samples are untracked, and later steps upload them. Only the untracked
        # files the incoming tip is about to write go, because those are the ones
        # that make the checkout refuse to detach.
        assert any(
            "--untracked-files=no" in line for line in lines
        ), f"{where} must leave the untracked files nothing will write over alone"
        clear = next(
            (
                index
                for index, line in enumerate(lines)
                if "git ls-files --others --exclude-standard" in line
            ),
            None,
        )
        assert clear is not None, (
            f"{where} must find the untracked files the tip carries - an untracked file "
            "the incoming commits add makes the rebase refuse to detach HEAD"
        )
        assert clear < rebase, f"{where} must clear those files before it rebases"
        # A rebase that cannot finish must not be left half-applied for the next
        # attempt to trip over.
        assert any(
            not line.startswith("#") and GIT_REBASE.search(line) and "--abort" in line
            for line in lines
        ), f"{where} must leave no rebase in progress"
        # And no rebase here may guess that a drained directory was renamed. The
        # fold already empties `state/segments/`, so a sibling adding a new
        # segment into it is read as adding into a directory that moved, and the
        # rebase stops with `CONFLICT (file location)` over a correct tree.
        for line in lines:
            if line.startswith("#") or not GIT_REBASE.search(line):
                continue
            assert DIRECTORY_RENAMES_OFF in line, (
                f"{where} rebases with git's directory-rename guess left on: {line}"
            )


def _subprocess_calls(tree: ast.AST) -> list[tuple[str, ast.Call]]:
    """Every call spelled `subprocess.<verb>`, with the verb it names."""
    return [
        (node.func.attr, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]


def _runs_a_command(func: ast.expr) -> bool:
    """Whether this call runs a command: the git wrapper, or `subprocess` itself."""
    if isinstance(func, ast.Name):
        return func.id == "_git"
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
    )


def test_no_command_in_the_retry_loop_can_raise_or_go_unread() -> None:
    """`check=True` is the Python spelling of the defect that cost a day.

    Run `32671663130` lost a finished day to one unguarded `git pull --rebase`
    under `bash -e`. The run ended inside attempt 1: no attempt 2, no failure
    message, and a checkout left mid-rebase. An exception raised out of a
    subprocess call leaves this loop in exactly that state, so the hazard
    changed spelling rather than going away, and `check=False` is what has to
    be spelled at every call. `subprocess.check_call` and `check_output` raise
    by definition, so the closed set of verbs is asserted rather than the flag
    alone.

    The second half is the other way the same failure arrives. With
    `check=False`, a command nobody reads fails silently and the loop carries
    on as though it worked - which is how a rebase reaches `--continue` over an
    index that was never settled. Every command has to be read by somebody, so
    none of them may stand as a statement on its own.

    Read over the whole module rather than over the `while` body. The loop's
    work is in the functions it calls - the noise discard, the hand-back, the
    conflict resolver - so a rule scoped to the `while` alone would walk past
    every command in the program and pass on an empty set.
    """
    tree = ast.parse(read_text(COMMIT_PROGRAM))

    calls = _subprocess_calls(tree)
    assert calls, "no subprocess call was read, so this test would pass on nothing"
    verbs = {verb for verb, _ in calls}
    assert verbs == {"run"}, (
        f"subprocess.{sorted(verbs - {'run'})} raises where `run` hands back a return code"
    )
    for _, node in calls:
        asked = [word.value for word in node.keywords if word.arg == "check"]
        assert asked and isinstance(asked[0], ast.Constant) and asked[0].value is False, (
            f"line {node.lineno} must pass check=False, spelled where a reader can see it"
        )

    unread = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and _runs_a_command(node.value.func)
    ]
    assert not unread, f"line(s) {unread} run a command and read nothing back"


def test_the_loop_is_bounded_by_a_clock_and_not_by_a_count() -> None:
    """A fixed number of attempts is spent at once however high the number is.

    Under several runs committing together, the counter buys nothing: each loser
    spends its three and gives up while the tip keeps moving. A deadline with a
    jittered backoff converges in expectation at any commit rate.

    Read off the program rather than run, because what this settles is that no
    count is left anywhere in the loop. The Oracle below runs it.
    """
    source = read_text(COMMIT_PROGRAM)
    lines = source.splitlines()
    loop = next(
        node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.While)
    )
    assert loop.end_lineno is not None
    body = "\n".join(lines[loop.lineno - 1 : loop.end_lineno])

    assert "for attempt in " not in source, "the retry count is what this row removed"
    assert "deadline" in body, "the loop must stop on a clock"
    assert "_back_off(" in body, "every loser of one race must not refetch in lockstep"
    # The deadline is a knob, and the one place its standing value is written
    # down is the config file. The program's own fallback covers a caller with
    # no config reader on its runner.
    assert "PUSH_DEADLINE_SECONDS" in source
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    defaults = AppConfig.model_validate({})
    assert committed["run"]["push_deadline_seconds"] == defaults.run.push_deadline_seconds


def test_the_shard_keeps_a_shorter_deadline_than_the_rest_of_the_run() -> None:
    """One deadline does not fit two jobs, and the reserve is why.

    A work shard keeps `run.shard_wrap_up_minutes` back for everything after its
    last item - the records, the manifest and the artifact upload. The run's own
    300 s would be a quarter of that reserve. The assemble job has no such
    problem: it used 1.8 of its 20 minutes on run 35701213155.
    """
    shard = int(_commit_call("work")[1]["PUSH_DEADLINE_SECONDS"])
    run_wide = int(_commit_call("assemble")[1]["PUSH_DEADLINE_SECONDS"])
    reserve_seconds = AppConfig.model_validate({}).run.shard_wrap_up_minutes * 60

    assert shard < run_wide, "a shard that spends the run's deadline loses its upload"
    assert shard * 4 <= reserve_seconds, (
        f"{shard}s is more than a quarter of the shard's {reserve_seconds}s reserve"
    )


def test_both_daily_commit_steps_run_the_one_shared_program() -> None:
    """Two copies of a retry loop is one copy nobody can execute in a test.

    The program runs on a runner that has restored the checkout and nothing
    else. Nine workflows call it, and four of them call it in a job that never
    installs this project's dependencies, so an import of `idhazh` or of any
    third-party package would fail the push rather than the install.
    """
    assert COMMIT_PROGRAM.is_file()
    roots = {
        (node.module or "").split(".")[0]
        if isinstance(node, ast.ImportFrom)
        else node.names[0].name.split(".")[0]
        for node in ast.walk(ast.parse(read_text(COMMIT_PROGRAM)))
        if isinstance(node, ast.Import | ast.ImportFrom)
    }
    assert roots, "no import was read, so this test would pass on nothing"
    outside = roots - set(sys.stdlib_module_names) - {"__future__"}
    assert not outside, f"the commit program must run on a bare checkout, but imports {outside}"

    for job_name in COMMIT_STEPS:
        staged_paths, settings = _commit_call(job_name)
        assert staged_paths == COMMIT_STAGED_PATHS[job_name]
        assert set(settings) == COMMIT_SCRIPT_ENV[job_name]
        assert all(value for value in settings.values())

    plan = _commit_call("plan")[1]
    assemble = _commit_call("assemble")[1]
    # The two jobs say different things about the same event, and the extraction
    # kept both rather than choosing one.
    assert plan != assemble
    assert plan["COMMIT_MESSAGE"] == f"plan: {SUBSTITUTED_DATE}"
    assert assemble["COMMIT_MESSAGE"] == f"digest: {SUBSTITUTED_DATE}"
    # And the fold says a third thing, in the same job as the day's own commit.
    assert _commit_call("fold")[1]["COMMIT_MESSAGE"] != assemble["COMMIT_MESSAGE"]


def test_the_plan_job_takes_the_tips_state_before_anything_writes_into_it() -> None:
    """A run reads a state root as old as its trigger commit unless it asks for a fresh one.

    `actions/checkout` restores the commit the run was triggered at. A run waits
    for a runner after that, and another run may be committing under `state/`
    the whole time. Run 35660521768 started 46 minutes behind its trigger and
    planned against what the run ahead had already superseded.

    The order is the whole of the fix. Taken after any step that writes into
    `state/`, it discards what that step wrote - which is why it runs ahead of
    the probe, the plan and the commit.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "plan")]
    assert names.index(TAKE_STATE_STEP) < names.index(FINGERPRINT_STEP)
    assert names.index(TAKE_STATE_STEP) < names.index(PLAN_STEP)
    assert names.index(TAKE_STATE_STEP) < names.index(COMMIT_STEPS["plan"])

    step = _step(workflow, "plan", "name", TAKE_STATE_STEP)
    taken = shlex.split(_script(step, f"digest.yml/plan/{TAKE_STATE_STEP}"))
    assert tuple(taken) == TAKE_STATE_CALL
    assert taken[-1] == ledger.STATE_DIRNAME


def test_only_assemble_rebuilds_and_it_rebuilds_with_its_own_publish_command() -> None:
    """The producer named in the loop is the producer the job already ran.

    Compared as argv rather than as text: the step runs its command through a
    shell and quotes what it interpolates, and the loop runs the same words with
    no shell at all. Two copies of the invocation would be two things to keep in
    step, and the one inside the loop only runs on a race - which is the copy
    nobody would notice going stale.
    """
    workflow = _load_workflows()["digest.yml"]
    publish = _script(
        _step(workflow, "assemble", "name", "Assemble and publish"), "assemble publish step"
    )
    settings = _commit_call("assemble")[1]

    # `shlex.split` keeps a backslash-newline as a token of its own, so the
    # step's line continuations are folded first.
    published_argv = shlex.split(_substitute(publish).replace("\\\n", " "))
    assert published_argv == settings["REGENERATE_COMMAND"].split()
    # The list itself lives in `idhazh.paths`, and the step reads it through a
    # step output. The harness carried a second copy of it until 2026-09-22;
    # three lists that can drift was the defect, not two.
    assert settings["REFRESH_PATHS"].split() == paths.refresh_paths(
        day_dir=SUBSTITUTED_DAY_DIR
    ).split()
    # Never the day's directory itself. The visuals artifact unpacks this run's
    # rendered charts into it and no producer here can make them again, so the
    # two payload files are named one at a time.
    assert SUBSTITUTED_DAY_DIR not in settings["REFRESH_PATHS"].split()
    # Which is why the charts get their own answer: this run's copy is dropped
    # rather than handed back, so the rebase never sees two adds of one path.
    # The entry point is the shipped one, not a copy of its logic.
    assert settings["DROP_RACED_ASSETS_COMMAND"].split()[1:] == [
        "backend/utilities/drop_raced_assets.py",
        "--date",
        SUBSTITUTED_DATE,
    ]
    assert DROP_ENTRY_POINT.is_file()
    # Neither setting may carry a space inside one of its words: the loop
    # word-splits both, and nothing here re-parses shell quoting.
    assert not any(
        '"' in value or "'" in value
        for value in (settings["REFRESH_PATHS"], settings["REGENERATE_COMMAND"])
    )
    # The plan job records what it saw and cannot rebuild it, so it resolves a
    # race by rebasing, and `.gitattributes` unions its ledgers. It commits no
    # rendered asset either, so it has nothing to drop.
    assert "REGENERATE_COMMAND" not in _commit_call("plan")[1]
    assert "DROP_RACED_ASSETS_COMMAND" not in _commit_call("plan")[1]


def test_only_the_collections_this_repository_declares_union() -> None:
    """A union merge keeps both sides, which is right for nine of these and wrong for the rest.

    Every file under `state/` carried this driver until 2026-09-19. It kept two
    attempts at one row as readily as two independent rows, and a lost push race
    is exactly how a second attempt arrives. Each writer owns the file its run,
    attempt, job and shard name now, so there is nothing for a merge to settle.

    What is left is held against `idhazh.paths.UNION_SAFE`, which is this
    repository's own list of the collections two writers may both append to. The
    list is one hand-written set rather than two: a line added to
    `.gitattributes` and not to the list fails here, and so does a list entry
    with no line behind it. `frontend/public/telemetry/` is in neither - that
    file is a full rewrite of a day's rows, so a union of two rewrites is a file
    with every row twice, and assemble regenerates it instead.

    The set is closed rather than a membership check, because what this guards is
    the pattern nobody chose. A collection that picks up a merge rule in silence
    has had that rule decided for it, and a new pattern arriving here without its
    own reason should fail.
    """
    attributes = read_text(REPO_ROOT / ".gitattributes")
    unioned = {
        line.split()[0]
        for line in attributes.splitlines()
        if line and not line.startswith("#") and "merge=union" in line
    }

    assert unioned == {
        entry if entry.endswith(".csv") else f"{entry}/**/*.csv" for entry in paths.UNION_SAFE
    }


def test_a_commit_that_loses_its_push_cannot_throw_away_what_the_job_already_made() -> None:
    """Run `35660521768`, asked of the workflow file.

    That run computed a whole plan and published nothing. Its push lost a race,
    the commit step failed, and every step after it was skipped with the job -
    including the upload `assemble` downloads the plan from. The work was
    finished and sitting on the runner's disk; nothing could reach it.

    Two kinds of step may not be skipped that way, and both are read off the
    file rather than listed here.

    An artifact upload is the only way a finished piece of work leaves a job, so
    one standing after a commit step must survive that commit failing.

    And `continue-on-error: true` is this file's own mark for a step whose
    failure must never cost a reader the day. A step carrying that mark, sitting
    behind a commit step that can fail the job, is skipped by that failure
    anyway - so the mark says one thing and the job does another.

    Reachable is one of exactly two things: every commit step at or before it
    tolerates its own failure, or the step declares `always()`.

    A step that measures the published tree is neither of those and never enters
    this, which is the right answer - after a lost push there is no published
    tree to measure.
    """
    workflow = _load_workflows()["digest.yml"]
    labels = [label for label, name in COMMIT_WORKFLOWS.items() if name == "digest.yml"]
    assert labels, "no digest.yml job commits, so this test proves nothing"

    checked = 0
    for job_name in dict.fromkeys(COMMIT_JOBS[label] for label in labels):
        steps = _steps(workflow, job_name)
        commits = [
            index
            for index, step in enumerate(steps)
            if step.get("name") in set(COMMIT_STEPS.values())
        ]
        assert commits, f"{job_name} is listed as a committing job and commits nothing"

        intolerant = [
            index for index in commits if steps[index].get("continue-on-error") != TOLERATED
        ]
        for index, step in enumerate(steps):
            if index <= commits[0]:
                continue
            carries = "actions/upload-artifact" in str(step.get("uses", ""))
            declared = step.get("continue-on-error") == TOLERATED
            if not (carries or declared):
                continue
            checked += 1
            if not any(stop < index for stop in intolerant):
                continue
            where = f"{job_name}/{step.get('name') or step.get('uses')}"
            assert _normalize_condition(step.get("if"), where) == "always()", (
                f"{where} is skipped when the commit step before it fails, and it carries "
                "work that was already finished - give it `if: always()`"
            )

    assert checked, "no step after a commit step carries anything, so this test proves nothing"


def test_two_runs_that_conflict_each_keep_the_file_they_wrote(tmp_path: Path) -> None:
    """A conflicted path is settled by who wrote it, and the other writer is untouched.

    Two runs are in flight and each writes its own file. The tip also carries a
    file under THIS run's name, which is what an earlier push of this same job
    leaves when the push that followed it lost the race - so the rebase has an
    add of one path from each side, and `state/segments/**/*.csv` refuses to
    merge content at all.

    The script keeps what this job wrote there, because that filename can only
    have come from this job. The second run's file is nothing this job may touch
    and the rebase applies it whole, so both writers land and neither has to
    know about the other.
    """
    staged_paths, settings = _commit_call("plan")
    settings = _as_this_job(settings)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    this_run = read_text(RESOLVER_ROWS / "this-run.csv")
    another_run = read_text(RESOLVER_ROWS / "another-run.csv")
    ours, theirs = _writer_file(THIS_RUN), _writer_file(ANOTHER_RUN)
    _race(tmp_path, env, theirs, another_run)
    _race(tmp_path, env, ours, read_text(RESOLVER_ROWS / "an-earlier-push.csv"))
    _write(runner / ours, this_run)

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 0, result.stderr
    assert f"keeping what this job wrote at {ours}" in result.stdout
    assert _git(origin, env, "show", f"main:{ours}").splitlines() == this_run.splitlines()
    assert _git(origin, env, "show", f"main:{theirs}").splitlines() == another_run.splitlines()
    assert not _mid_rebase(runner)


def test_a_conflicted_path_this_job_did_not_write_stops_the_push(tmp_path: Path) -> None:
    """The other half of the rule, and the half that should never fire.

    A filename carries the run, the attempt, the job and the shard that wrote
    it, so no second writer can name it. A conflict on a path that names another
    writer therefore means two jobs claimed one file, and that is a defect to
    report rather than a race to settle: taking the tip's copy would delete the
    other writer's rows and exit 0, and retrying cannot make another writer's
    file this job's.

    So the push stops, and the message names the path and this job. One
    identity, not two: this job is the only one the script can speak for.
    """
    staged_paths, settings = _commit_call("plan")
    settings = _as_this_job(settings)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    another_run = read_text(RESOLVER_ROWS / "another-run.csv")
    unowned = _writer_file(ANOTHER_RUN)
    _race(tmp_path, env, unowned, another_run)
    _write(runner / unowned, read_text(RESOLVER_ROWS / "this-run.csv"))

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert "a conflicted path this job did not write stops the push" in result.stderr
    assert f"path: {unowned}" in result.stderr
    assert f"this job: {THIS_IDENTITY}" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    # The other writer's rows are still what the tip carries.
    assert _git(origin, env, "show", f"main:{unowned}").splitlines() == another_run.splitlines()
    assert not _mid_rebase(runner)


def test_a_file_this_job_wrote_that_the_tip_deleted_stops_the_push(tmp_path: Path) -> None:
    """The third case, and the one that exits 0 unless the index is read again.

    Git's spelling for keeping one side of a conflict exits 0 and changes
    nothing when the side it is asked for is the deleted one, so a file this job
    wrote and the tip removed is left unmerged with no error anywhere. Under
    `set -euo pipefail` the script would walk straight past it.

    Nothing but retention or a person can have taken a file named for this job,
    so putting it back is not a resolution this script may make. The push stops
    and the message names the path and this job.
    """
    staged_paths, settings = _commit_call("plan")
    settings = _as_this_job(settings)
    env = _isolated_env(tmp_path)
    origin, runner = _scripted_origin(tmp_path, env, staged_paths)
    ours = _writer_file(THIS_RUN)
    _race(tmp_path, env, ours, read_text(RESOLVER_ROWS / "an-earlier-push.csv"))
    # The checkout this job started from carried the file, or the tip taking it
    # away would be an add rather than a modify against a delete.
    _git(runner, env, "pull", "--ff-only", "origin", "main")
    other = tmp_path / "other"
    _git(other, env, "rm", "--quiet", ours)
    _git(other, env, "commit", "-m", "retention took it")
    _git(other, env, "push", "origin", "main")
    _write(runner / ours, read_text(RESOLVER_ROWS / "this-run.csv"))

    result = _run_commit_script(runner, env, staged_paths, settings)

    assert result.returncode == 1
    assert "the tip has deleted a file this job wrote" in result.stderr
    assert f"path: {ours}" in result.stderr
    assert f"this job: {THIS_IDENTITY}" in result.stderr
    assert settings["PUSH_FAILED_MESSAGE"] in result.stderr
    assert _git(origin, env, "log", "-1", "--format=%s").strip() == "retention took it"
    assert not _mid_rebase(runner)
