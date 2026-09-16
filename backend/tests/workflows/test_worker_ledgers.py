"""Does a worker's work survive the run that produced it being thrown away?"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import ledger, telemetry
from idhazh.evals import writer as score_writer

from ._harness import (
    COMMIT_REFRESH_PATHS,
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    FOLD_STEP,
    HARVEST_STEP,
    RECORD_COMMAND,
    RECORD_STEP,
    REVIEW_STEP,
    RUN_ARTIFACTS,
    SUBSTITUTED_DATE,
    SUBSTITUTED_SHARD,
    SUBSTITUTED_SHARDS,
    TOLERATED,
    WORK_LEDGER_STEPS,
    WORK_PAYLOAD_ARTIFACTS,
    _artifact_upload,
    _commit_call,
    _git,
    _isolated_env,
    _load_workflows,
    _mapping,
    _mid_rebase,
    _normalize_condition,
    _race,
    _run_commit_script,
    _script,
    _scripted_origin,
    _seed_ledger,
    _settled_in_the_clone,
    _step,
    _steps,
    _substitute,
    _write,
    requires_bash,
    requires_space_free_paths,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]


def test_a_worker_commits_its_rows_before_the_run_can_throw_them_away() -> None:
    """The Oracle, in YAML: a cancelled job runs `always()` steps and skips the rest.

    A shard's verdicts leave the runner inside its `items-<shard>` artifact,
    which is never committed and expires. Until these steps existed a run
    stopped between the workers and the publish had measured every item and kept
    none of the measurements, so they are the copy that outlives the artifact.
    """
    workflow = _load_workflows()["digest.yml"]
    names = [step.get("name") for step in _steps(workflow, "work")]

    for name in WORK_LEDGER_STEPS:
        step = _step(workflow, "work", "name", name)
        assert _normalize_condition(step.get("if"), f"work step {name}") == "always()"

    record = _substitute(
        _script(_step(workflow, "work", "name", RECORD_STEP), f"work step {RECORD_STEP}")
    )
    assert RECORD_COMMAND in record
    assert f'--date "{SUBSTITUTED_DATE}"' in record
    # This shard's own items. A record step that asked for the whole day would
    # file rows for items seven other workers are still holding. The step's line
    # continuations are folded first, the way bash reads them.
    assert shlex.split(record.replace("\\\n", " "))[-4:] == [
        "--shard",
        SUBSTITUTED_SHARD,
        "--shards",
        SUBSTITUTED_SHARDS,
    ]
    # Ahead of every `always()` step that only writes a log, because a cancelled
    # job spends one grace period on all of them in order and these are the ones
    # whose loss the group exists to prevent. Consecutive, and in this order: the
    # counters step writes a row the commit step stages.
    assert [names.index(name) for name in WORK_LEDGER_STEPS] == [
        names.index(RECORD_STEP) + offset for offset in range(len(WORK_LEDGER_STEPS))
    ]
    assert names.index(COMMIT_STEPS["work"]) < names.index("Prompt cache log summary")


def test_a_killed_shard_still_hands_assemble_the_items_it_finished() -> None:
    """The Oracle, in YAML: a step with no `if:` runs on `success()`, and a killed job is not one.

    `work` writes each item's payloads as it finishes that item, so the items
    directory holds every story the shard completed at the moment the bound
    lands - which is how `record` above files rows on a cancelled shard at all.
    Both artifacts carried no condition, so a cancelled shard uploaded neither
    and assemble composed the day without them.

    Measured on run 34852763827 (2026-09-14, four shards): three were cancelled
    at `run.shard_timeout_minutes`, their `always()` ledger steps ran and filed
    33 items as `outcome=ok, stage=publish`, and all three uploads were skipped.
    The committed day carries 13 items - shard 3's count, and shard 3 is the one
    shard that finished. The census over-reported by 3.5x and 33 articles of
    model time were paid for and thrown away.

    The two are named together because they have to be guarded together: the
    decision naming a chart travels in `items/` and the chart's own bytes travel
    in `shard-visuals-*`, so a guard on one alone publishes a story naming a
    picture file that is not there.

    It cannot settle whether assemble composes a partially-uploaded shard
    correctly in every case; a real run is the check for that.
    """
    workflow = _load_workflows()["digest.yml"]
    steps = _steps(workflow, "work")
    uploads = [
        _artifact_upload(workflow, "work", artifact) for artifact in WORK_PAYLOAD_ARTIFACTS
    ]

    for artifact, step in zip(WORK_PAYLOAD_ARTIFACTS, uploads, strict=True):
        guard = step.get("if")
        assert guard is not None, (
            f"the {artifact} upload carries no condition, so it runs on success() alone "
            f"and a shard stopped by its own timeout skips it"
        )
        assert _normalize_condition(guard, f"work upload {artifact}") == "always()", (
            f"a shard stopped by its own timeout must still upload {artifact}"
        )

    # Behind the ledger steps and never in front of them. A cancelled job spends
    # one grace period on every `always()` step in order, and the committed rows
    # are the copy that outlives this artifact's own expiry.
    last_ledger = max(
        steps.index(_step(workflow, "work", "name", name)) for name in WORK_LEDGER_STEPS
    )
    for artifact, step in zip(WORK_PAYLOAD_ARTIFACTS, uploads, strict=True):
        assert steps.index(step) > last_ledger, (
            f"the {artifact} upload must not spend the grace period the ledger steps need"
        )


def test_a_shard_hands_over_every_payload_it_wrote_beside_an_item() -> None:
    """The hand-off is the directory, so a payload a stage adds travels without a YAML change.

    A work shard writes four files an item and no step names any of them: the
    upload is rooted at the items directory and the download unpacks the whole
    thing back into the same place. `<item_id>.health.json` - the census row the
    recorder validated, added on 2026-09-15 - reached assemble on the strength of
    that alone.

    Narrowing either side to a list of suffixes is what this refuses, and it
    would fail silently: the stage would still write the payload, the shard would
    still report success, and assemble would compose a day without it.
    """
    workflow = _load_workflows()["digest.yml"]
    items_dir = f"{RUN_ARTIFACTS}/{SUBSTITUTED_DATE}/items/"

    upload = _mapping(
        _artifact_upload(workflow, "work", "items-${{ matrix.shard }}").get("with"), "upload"
    )
    assert _substitute(str(upload.get("path")).strip()) == items_dir, (
        "the whole items directory and nothing narrower, or the next per-item "
        "payload stays on the runner that wrote it"
    )

    collected = [
        asked
        for step in _steps(workflow, "assemble")
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and str((asked := _mapping(step.get("with"), "assemble download")).get("pattern", ""))
        == "items-*"
    ]
    assert len(collected) == 1, "assemble must collect the shards' items exactly once"
    assert str(collected[0].get("merge-multiple")).lower() == "true", (
        "eight shards unpack into one items directory"
    )
    assert _substitute(str(collected[0].get("path")).strip()) == items_dir, (
        "the artifact is rooted at the items directory, so it unpacks back into it"
    )


def test_a_ledger_that_will_not_push_cannot_cost_the_day_a_worker() -> None:
    """Which loss is cheaper, said in the workflow rather than left to an exit code.

    The shard's product is the items artifact assemble publishes from, and
    assemble writes the same census again - so a ledger push that spends its
    three attempts costs this run an early copy of rows it gets anyway. A failed
    shard costs the day a whole worker. The script exits 1 when it gives up
    (proved in `test_a_rebase_it_cannot_finish_still_ends_the_script_cleanly`),
    which is why saying so is load-bearing rather than decorative.
    """
    workflow = _load_workflows()["digest.yml"]

    for name in WORK_LEDGER_STEPS:
        step = _step(workflow, "work", "name", name)
        assert step.get("continue-on-error") == TOLERATED, (
            f"work step {name} must not fail the shard"
        )
    # Closed-world, because a publish step that swallowed its own failure would
    # publish nothing and report success. The two fold steps are here for the
    # harvest's reason: they run after the day is committed and touch only
    # months past `observability.item_health_full_grain_months`, so the most a
    # failure costs is one run's worth of bytes and the next run folds the same
    # month again. The picture download joins them because a day where nothing
    # was drawable produces no `shard-visuals-*` artifact at all, and every item
    # then publishes with no picture. The review tree joins it one rung further
    # out again: nothing downloads it, no gate reads it, and it is built after
    # the day is committed - so the most a failure costs is one day's contact
    # sheet, and the next run builds its own.
    tolerant = {
        (job_name, step.get("name") or step.get("uses"))
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if step.get("continue-on-error") == TOLERATED
    }
    assert tolerant == {
        *(("work", name) for name in WORK_LEDGER_STEPS),
        ("assemble", "actions/download-artifact@v8"),
        ("assemble", HARVEST_STEP),
        ("assemble", FOLD_STEP),
        ("assemble", REVIEW_STEP),
        ("assemble", COMMIT_STEPS["fold"]),
    }


def test_every_path_the_work_shard_stages_is_union_merged() -> None:
    """Eight shards append to one branch, so every shared file needs the union driver.

    Asked of git rather than of a pattern matcher written here: `.gitattributes`
    is the file that decides, and a second implementation of its globbing could
    agree with this test and disagree with the merge.

    `state/traces` is the one staged path deliberately outside the driver, so it
    is asserted to be outside rather than left unmentioned. A trace file is named
    for one shard of one run, so two shards never write one path and there is
    nothing for a merge driver to settle. Unioning them would also be wrong: the
    file is JSON lines, and a union of two different runs' spans is a tree that
    reconciles against neither shard's clock.
    """
    # The file each staged path resolves to. All four directories file by day
    # now, so the union driver has to reach a nested path - `state/**/*.csv` is
    # the attribute line that does it. The span rollup files by month, and the
    # same attribute line covers it.
    written = {
        "state/item-health": ledger.item_health_relpath(SUBSTITUTED_DATE),
        "state/scores": score_writer.ledger_relpath(SUBSTITUTED_DATE),
        "state/score-index": score_writer.index_relpath(SUBSTITUTED_DATE),
        "state/runtime-counters.csv": "state/runtime-counters.csv",
        "state/span-rollup": ledger.span_rollup_relpath(SUBSTITUTED_DATE[:7]),
    }
    per_shard = {
        "state/traces": telemetry.committed_trace_relpath(f"{SUBSTITUTED_DATE}-1", 1),
    }
    assert set(written) | set(per_shard) == set(COMMIT_STAGED_PATHS["work"])

    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *written.values(), *per_shard.values()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [
        *(f"{path}: merge: union" for path in written.values()),
        *(f"{path}: merge: unspecified" for path in per_shard.values()),
    ]


#: Where each ledger the work stage appends to directly lands, as the staged path
#: names it. Written out rather than derived, because `append_runtime_counters`
#: writes a flat file and `append_span_rollup` writes a directory, so no rule
#: turns a helper name into a path.
WORK_STAGE_APPENDS: Final = {
    "append_span_rollup": "state/span-rollup",
}

#: The same, for the writers that are not ledger appends. `stage_work` opens a
#: file sink straight onto the trace path, so no `ledger.append_*` call names it.
WORK_STAGE_SINKS: Final = {
    "committed_trace_path": "state/traces",
}


def test_every_ledger_the_work_stage_appends_to_is_staged_by_the_work_job() -> None:
    """A shard's fold is worth nothing if the runner is the only place it lands.

    `roll_up_spans` ran on every shard from 2026-09-06 and `append_span_rollup`
    wrote `state/span-rollup/<YYYY-MM>.csv` into the runner's checkout. No commit
    step named the path, so every fold died with its runner, and assemble - on
    another machine, projecting a directory that was never there - published a
    header row and no data for nine days. Nothing failed; the instrument simply
    reported nothing. `state/traces`, the raw evidence the fold is taken from, was
    missed the same way and is covered here for the same reason.

    The two lists this compares are written by different people at different
    times: one is a call in a stage, the other is an argument in a workflow. This
    is the test that makes the second follow the first.
    """
    source = read_text(REPO_ROOT / "backend" / "idhazh" / "stages" / "work.py")
    expected = WORK_STAGE_APPENDS | WORK_STAGE_SINKS
    called = set(re.findall(r"\bledger\.(append_[a-z_]+)\(", source))
    called |= {
        name for name in WORK_STAGE_SINKS if re.search(rf"\btelemetry\.{name}\(", source)
    }
    assert called, "the work stage writes no ledger - has the call moved?"
    assert called <= set(expected), (
        f"the work stage writes {sorted(called - set(expected))}, which this test "
        "cannot say a staged path for. Add it to WORK_STAGE_APPENDS or "
        "WORK_STAGE_SINKS, and to the work job's commit step."
    )
    assert set(WORK_STAGE_SINKS) <= called, (
        "the trace sink is no longer opened in stage_work - if it moved, move this "
        "entry with it rather than deleting the guard"
    )
    staged = set(COMMIT_STAGED_PATHS["work"])
    for helper in sorted(called):
        assert expected[helper] in staged, (
            f"stage_work calls {helper} but the work job never stages "
            f"{expected[helper]}, so the rows die with the runner"
        )


def test_the_span_rollup_ships_with_a_header_so_the_commit_step_can_name_it() -> None:
    """`git add` on a path that is not there aborts the whole step.

    The commit step runs under `set -euo pipefail` and stages six paths in one
    call, so a missing `state/span-rollup` or `state/traces` would take
    item-health, the scores and the runtime counters down with it on every fresh
    clone. The same reason `state/feed-retirements.csv` and
    `state/counterfactual-scores/` ship with a header and no rows.

    The trace directory ships a keep-file rather than a sample trace: a trace is
    evidence with a seven-day window, so a committed sample would be the one file
    in it the prune could never justify keeping.
    """
    for relative in (
        f"{ledger.STATE_DIRNAME}/{ledger.SPAN_ROLLUP_DIRNAME}",
        f"{ledger.STATE_DIRNAME}/{telemetry.TRACES_DIRNAME}",
    ):
        assert (REPO_ROOT / relative).is_dir(), f"{relative} must be in a fresh checkout"
        committed = subprocess.run(
            ["git", "ls-files", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert committed, f"{relative} must hold at least one committed file"


def test_the_observation_index_travels_with_the_rows_it_describes() -> None:
    """The index is what the writer reads instead of the rows, so it has to be committed.

    A shard pushed without its index is a month the next run cannot recognise.
    The dedupe would read an index that stops short of the rows beside it, call
    every measurement past that point new, and append each one a second time -
    the one promise the eval ledger makes about itself.

    The assemble job refreshes it for the mirror-image reason. A retry hands the
    rows back to origin's tip and runs the producer again; an index left holding
    the first attempt's digests would make the producer refuse the day it just
    rebuilt, and the day's measurements would be lost rather than doubled.

    The directory is named rather than derived, and `git add` on a path that is
    not there aborts the whole step, so a fresh checkout has to carry it.
    """
    assert score_writer.INDEX_RELDIR in COMMIT_STAGED_PATHS["work"]
    assert score_writer.INDEX_RELDIR in COMMIT_REFRESH_PATHS["assemble"]
    assert (REPO_ROOT / score_writer.INDEX_RELDIR).is_dir()
    tracked = subprocess.run(
        ["git", "ls-files", score_writer.INDEX_RELDIR],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked, f"{score_writer.INDEX_RELDIR} must be in a fresh checkout"


def test_the_retirement_ledger_needs_no_gitattributes_edit() -> None:
    """`state/**/*.csv` already answers union, so the new ledger inherits the driver.

    Asked of git rather than of a pattern matcher written here, for the same
    reason the test above is: `.gitattributes` is the file that decides. Two
    stale checkouts can each append the same retirement, and the union keeps both
    lines - which is why the file is also registered in `ledger.keyed_paths`, so
    the post-merge settlement collapses them to one.
    """
    relative = ledger.feed_retirements_relpath()

    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [f"{relative}: merge: union"]


@requires_bash
@requires_space_free_paths
def test_every_shard_of_a_full_fan_out_lands_its_rows(tmp_path: Path) -> None:
    """Eight workers, one branch, one row each.

    They run in turn from clones taken before any of them pushed, so every one
    after the first finds a base that has already moved - which is the state a
    real fan-out puts them in. What this proves is that the rebase resolves it
    and no row is lost, and that the post-merge pass leaves eight different rows
    alone: they share a file, not a key. It does not prove the three-attempt
    budget: eight truly concurrent pushes cannot be made deterministic in a test.
    """
    staged_paths, settings = _commit_call("work")
    env = _isolated_env(tmp_path)
    origin, _ = _scripted_origin(tmp_path, env, staged_paths)
    relative = _seed_ledger(staged_paths[0])
    settings = _settled_in_the_clone(settings, relative, "header")
    shards = range(8)
    runners = []
    for shard in shards:
        runner = tmp_path / f"shard-{shard}"
        _git(tmp_path, env, "clone", str(origin), str(runner))
        _write(runner / relative, f"header\nrow-0\nshard-{shard}\n")
        runners.append(runner)

    results = [_run_commit_script(runner, env, staged_paths, settings) for runner in runners]

    assert [result.returncode for result in results] == [0] * len(runners)
    landed = _git(origin, env, "show", f"main:{relative}").splitlines()
    assert landed[0] == "header"
    assert sorted(landed[1:]) == ["row-0", *(f"shard-{shard}" for shard in shards)]
    assert not any(_mid_rebase(runner) for runner in runners)


def _keyed_origin(tmp_path: Path, env: dict[str, str], relative: str) -> tuple[Path, Path]:
    """An origin holding one keyed ledger, and a clone taken before anything raced it.

    Built here rather than through `_scripted_origin`, which seeds a one-word
    ledger: two rows that share a key and disagree about everything else need
    two columns, and that shape is what this file is about.
    """
    origin = tmp_path / "origin.git"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, env, "init", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git(tmp_path, env, "clone", str(origin), str(seed))
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _write(seed / relative, "key,cells\n")
    _git(seed, env, "add", ".gitattributes", relative)
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


@requires_bash
@requires_space_free_paths
def test_a_second_attempt_at_one_shard_leaves_the_row_the_first_one_pushed(
    tmp_path: Path,
) -> None:
    """The defect this step exists for, reproduced and then closed, on real git.

    A shard's append filters against the checkout, and `actions/checkout` pins a
    job to the commit its run was triggered at. So a second attempt at the same
    work cannot see the row the first attempt pushed afterwards: it appends its
    own, `merge=union` keeps both lines, and the ledger ends up with a key twice.
    That is how run `2026-08-29-3` came to hold six counter rows for four shards.

    Both cases run the shipped script over the same repository. The one without
    the setting is the defect; the one with it is the fix. The row that survives
    is the one origin already published, so the commit adds nothing and deletes
    nothing the tip holds - which is the property that makes settling after a
    merge safe rather than a rewrite of somebody else's history.
    """
    relative = "state/runtime-counters.csv"
    _, settings = _commit_call("work")

    def attempt(root: Path, drop: bool) -> list[str]:
        root.mkdir(parents=True, exist_ok=True)
        env = _isolated_env(root)
        origin, runner = _keyed_origin(root, env, relative)
        _race(root, env, relative, "key,cells\nk1,attempt-one\n")
        _write(runner / relative, "key,cells\nk1,attempt-two\n")
        settled = (
            _settled_in_the_clone(settings, relative, "key")
            if drop
            else {name: value for name, value in settings.items() if "REPEATED" not in name}
        )
        result = _run_commit_script(runner, env, [relative], settled)
        assert result.returncode == 0, result.stderr
        assert "rebasing" in result.stdout, "the push has to lose, or nothing merged"
        return _git(origin, env, "show", f"main:{relative}").splitlines()

    assert attempt(tmp_path / "unsettled", drop=False) == [
        "key,cells",
        "k1,attempt-one",
        "k1,attempt-two",
    ], "without the pass the union keeps both attempts, which is the defect"

    assert attempt(tmp_path / "settled", drop=True) == ["key,cells", "k1,attempt-one"]


def test_assemble_hands_back_every_ledger_a_worker_committed() -> None:
    """Why assemble cannot append a row a shard already pushed.

    Assemble checks out main as it was when the run was queued, so its copy of
    these two ledgers predates the shards' pushes and its own push always loses
    the race. The loop answers a lost race by restoring the rebuilt paths from
    the tip it wants and running the producer again - so the assemble that
    finally commits reads the file the workers wrote and files against it. A
    staged path missing from that refresh set would be rebased instead, and
    `merge=union` keeps both appends.
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()

    assert set(COMMIT_STAGED_PATHS["work"]) <= set(refreshed)


def test_assemble_hands_back_the_published_ledger_it_appends_to() -> None:
    """The refresh set covers the day file this stage writes, and asks it where.

    Assemble appends published rows blind, so a second attempt that rebuilt on
    top of its own first attempt would file every item twice. The day is handed
    back to origin's tip before the producer runs again, which is what makes the
    rebuilt append land on the file origin holds rather than on this attempt's.

    The path is read from the writer's own helper rather than spelled here, so
    moving the ledger again fails this instead of leaving a refresh set naming a
    directory nothing writes (Guardrail #6).
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()
    day = ledger.published_relpath(SUBSTITUTED_DATE)

    assert any(day == path or day.startswith(f"{path}/") for path in refreshed), (
        f"{day} is written by this job and no entry of {refreshed} hands it back"
    )
