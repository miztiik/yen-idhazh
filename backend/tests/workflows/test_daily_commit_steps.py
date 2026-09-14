"""Does the daily run ever commit from a dirty tree, and do its commit steps share one script?"""

from __future__ import annotations

import re
import shlex

import pytest
from conftest import REPO_ROOT, read_text

from ._harness import (
    COMMIT_REFRESH_PATHS,
    COMMIT_SCRIPT,
    COMMIT_SCRIPT_ENV,
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    DROP_ENTRY_POINT,
    SCRIPTS_DIR,
    SETTLE_COMMAND,
    SETTLE_COVER_FLAG,
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

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


def test_no_rebase_in_the_daily_run_starts_on_a_dirty_tree() -> None:
    """A rebase that refuses to start throws away a day the run already computed.

    Run `32671663130` died exactly this way: one tracked file was modified in the
    checkout before any step ran, and the retry loop lost plan, four shards and
    assemble with it. The work is committed before the loop begins, so the fix is
    to drop what is left rather than to carry it into the rebase.

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
        assert any(
            "--untracked-files=no" in line for line in lines
        ), f"{where} must leave untracked files alone - they cannot block a rebase"
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

def test_both_settling_commit_steps_name_the_run_they_settle() -> None:
    """The bound, mirrored where a workflow that drops it reds (Guardrail #12).

    A run appends only to the partition its own date routes to, so a repeat the
    union merge left can only be in a file that run wrote, and the date names it.
    Drop the flag and `stages.dedupe_ledgers.stage_dedupe_ledgers` walks every
    feed-health day, every item-health day and every score day the archive holds
    - a bill that rises every day for an answer already given, because a finished
    partition was settled when it was written and cannot change again.

    The command refuses to run with no cover at all, so a workflow that lost the
    flag fails its commit step rather than quietly reading the archive. This
    names the step instead of waiting for the run.
    """
    settling = [
        label for label, names in COMMIT_SCRIPT_ENV.items() if "DROP_REPEATED_ROWS_COMMAND" in names
    ]
    assert settling == ["plan", "work"]

    for label in settling:
        settle = _commit_call(label)[1]["DROP_REPEATED_ROWS_COMMAND"].split()
        assert tuple(settle[: len(SETTLE_COMMAND)]) == SETTLE_COMMAND
        assert settle[len(SETTLE_COMMAND) :] == [SETTLE_COVER_FLAG, SUBSTITUTED_DATE], (
            f"{label} must name the run it settles, or the pass reads the whole archive"
        )

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

def test_the_append_only_ledgers_union_and_the_public_projection_does_not() -> None:
    """A text merge of two appends is a merge nobody asked for.

    Every file under `state/` is an append-only ledger of independent rows, so
    the union of both sides is the answer. `frontend/public/telemetry/` is a
    full rewrite of `state/item-health/`, so a union of two rewrites is a file
    with every row twice; assemble regenerates it instead.

    The set is closed rather than a membership check, because what this guards
    is the pattern nobody chose. The published day tree is named on a line of
    its own even though the catch-all above it already matched: a collection
    that inherits a merge rule in silence has had that rule decided for it, and
    a new pattern arriving here without its own reason should fail.

    `state/visual-prunes/**/*.csv` joined on 2026-09-08 when the cleanup record
    became a day tree, and it is here because this test refused it first. Its
    reason is its own rather than the neighbour's: a row is one pass by one run,
    so two runs of a day that both append are not in disagreement, and a repeat
    the union brings is dropped by `VISUAL_PRUNE_KEY`.
    """
    attributes = read_text(REPO_ROOT / ".gitattributes")
    unioned = {
        line.split()[0]
        for line in attributes.splitlines()
        if line and not line.startswith("#") and "merge=union" in line
    }

    assert unioned == {
        "state/*.csv",
        "state/**/*.csv",
        "state/published/**/*.csv",
        "state/visual-prunes/**/*.csv",
    }
    assert not any(
        "telemetry" in pattern or pattern.startswith("frontend") for pattern in unioned
    )
