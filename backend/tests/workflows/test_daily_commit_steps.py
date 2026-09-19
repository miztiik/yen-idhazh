"""Does the daily run ever commit from a dirty tree, and do its commit steps share one script?"""

from __future__ import annotations

import re
import shlex

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import ledger

from ._harness import (
    COMMIT_REFRESH_PATHS,
    COMMIT_SCRIPT,
    COMMIT_SCRIPT_ENV,
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    COMPACT_STEP,
    DROP_ENTRY_POINT,
    FINGERPRINT_STEP,
    PLAN_STEP,
    SCRIPTS_DIR,
    SUBSTITUTED_DATE,
    SUBSTITUTED_DAY_DIR,
    _commit_call,
    _load_workflows,
    _mapping,
    _script,
    _step,
    _steps,
    _substitute,
)

pytestmark = pytest.mark.workflow


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

    This reads the shared script and the workflow's own `run:` bodies, so an
    inline loop written back into a step is still covered.
    """
    workflow = _load_workflows()["digest.yml"]
    jobs = _mapping(workflow.get("jobs"), "jobs")

    bodies = [
        (f"{job_name}/{step.get('name')}", script)
        for job_name in jobs
        for step in _steps(workflow, job_name)
        if isinstance(script := step.get("run"), str)
    ]
    bodies += [
        (path.relative_to(REPO_ROOT).as_posix(), read_text(path))
        for path in sorted(SCRIPTS_DIR.glob("*.sh"))
    ]
    scripts = [(where, body) for where, body in bodies if "git rebase" in body]
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
            if "git rebase " in line and "--abort" not in line
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
        assert "git rebase --abort" in script, f"{where} must leave no rebase in progress"


def test_every_command_in_the_retry_loop_is_guarded() -> None:
    """`set -e` plus one unguarded command is the whole defect.

    `git pull --rebase origin main` was the only unguarded command in the loop,
    so a conflicting rebase ended the script inside attempt 1 and left the
    checkout mid-rebase. This reads the loop body and asserts every command in it
    is either a condition, a guarded call, or an `echo`, which is what makes the
    three attempts real. The Oracle test below proves the same thing by running
    it; this one names the line when a new command arrives unguarded.

    A plain assignment is allowed because `set -e` has nothing to act on: the
    exit status is the value's, and a literal always succeeds. One whose value
    comes from a command substitution is still a command, so it is still
    flagged - that is where the hazard would come back.
    """
    lines = read_text(COMMIT_SCRIPT).splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("for attempt in "))
    end = next(index for index, line in enumerate(lines) if line.startswith("done"))
    assert start < end

    literal_assignment = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^\s`]*$")
    unguarded = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        guarded = (
            stripped.startswith(("if ", "elif ", "fi", "else", "echo ", "["))
            or stripped in {"exit 0", "break", "continue", "then"}
            or "||" in stripped
            or (literal_assignment.match(stripped) is not None and "$(" not in stripped)
        )
        if not guarded:
            unguarded.append(stripped)
    assert unguarded == [], f"unguarded inside the retry loop: {unguarded}"


def test_both_daily_commit_steps_run_the_one_shared_script() -> None:
    """Two copies of a retry loop is one copy nobody can execute in a test."""
    assert COMMIT_SCRIPT.is_file()
    assert read_text(COMMIT_SCRIPT).startswith("#!/usr/bin/env bash\n")

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


def test_the_catch_up_compaction_runs_before_the_plan_job_commits() -> None:
    """A segment folded after the commit is a segment the runner throws away.

    `assemble` drains the store on every run that reaches it. This job is the
    only other caller, so a run whose assemble never happened has exactly one
    chance to have its rows folded into a head - and that chance is over the
    moment this job has pushed.

    It is also why the job stages `state` whole: the compaction writes into
    whichever head a waiting segment's own rows name, which no hand-written list
    can know.

    And it runs before this job's OWN probe, which is what keeps a head down to
    one writer a run. The probe writes a segment; a fold placed after it would
    find that segment, write the day file here, and leave `assemble` writing the
    same file again. Nothing would be lost - the fold is idempotent - but two
    head writers in one run is the shape this design removes, and the third
    arrives by looking like the second.

    It runs before the PLAN as well, and that one is about what a refusal costs.
    The fold is the one step here that does not degrade: a row it cannot read
    ends the job. Placed after the feed reads, a refusal throws away every read
    the job had already paid for. Nothing in the fold needs the day the plan
    writes - a waiting row is filed under the date in its own cells.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "plan")]
    assert names.index(COMPACT_STEP) < names.index(PLAN_STEP)
    assert names.index(COMPACT_STEP) < names.index(COMMIT_STEPS["plan"])
    assert names.index(COMPACT_STEP) < names.index(FINGERPRINT_STEP)
    assert COMMIT_STAGED_PATHS["plan"] == ["state"]


def test_the_segment_store_is_handed_back_to_the_tip_with_the_heads() -> None:
    """A lost push refreshes the store as well as what the compaction wrote.

    Without it the rebuild would fold this attempt's already-drained store onto
    the tip's heads and miss every segment a sibling pushed while this run was
    working - the rows would sit in the tree with nothing left to read them.
    """
    refreshed = COMMIT_REFRESH_PATHS["assemble"]
    assert f"{ledger.STATE_DIRNAME}/{ledger.SEGMENTS_DIRNAME}" in refreshed


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
    assert settings["REFRESH_PATHS"].split() == COMMIT_REFRESH_PATHS["assemble"]
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


def test_only_the_two_single_writer_day_trees_union() -> None:
    """A union merge keeps both sides, which is right for two of these and wrong for the rest.

    Every file under `state/` carried this driver until 2026-09-19. It kept two
    attempts at one row as readily as two independent rows, and a lost push race
    is exactly how a second attempt arrives. Each writer owns its own segment
    now, so there is nothing for a merge to settle.

    Two day trees keep it, each with one writing job and each saying why in its
    own line. `frontend/public/telemetry/` never had it: that file is a full
    rewrite of `state/item-health/`, so a union of two rewrites is a file with
    every row twice, and assemble regenerates it instead.

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
        "state/published/**/*.csv",
        "state/visual-prunes/**/*.csv",
    }
