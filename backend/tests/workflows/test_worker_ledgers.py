"""Does a worker's work survive the run that produced it being thrown away?"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest
from conftest import REPO_ROOT, writer_identity
from retention._trees import health_row

from idhazh import ledger, path_classes, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.telemetry.publish import day_metrics

from ._harness import (
    COMMIT_STAGED_PATHS,
    COMMIT_STEPS,
    FINGERPRINT_COMMAND,
    FINGERPRINT_JOB_FLAG,
    FINGERPRINT_JOBS,
    FINGERPRINT_STEP,
    HARVEST_STEP,
    JOB_CLOCK_COMMAND,
    JOB_CLOCK_STEP,
    METRICS_FILE,
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
    _run_commit_script,
    _script,
    _scripted_origin,
    _step,
    _steps,
    _substitute,
    requires_bash,
    requires_space_free_paths,
)

pytestmark = pytest.mark.workflow


def _under(relpath: str, named: str) -> bool:
    """Whether handing `named` back would carry this path with it."""
    return relpath == named or relpath.startswith(f"{named}/")


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


def test_the_job_clock_step_is_handed_every_reading_the_probe_cannot_take() -> None:
    """The other half of the host row, and every one of its inputs lives on this runner.

    The machine probe runs before the model server, because the bandwidth
    reading wants an idle host. What the job cost is only knowable at its end,
    and none of these numbers can be read from the checkout: the stamp comes from
    a step that ran before it existed, the log belongs to the server this job
    started, and the scrape is what a step above wrote out of that server before
    it went. So the step has to hand all three over, and a step that named none
    would write a row with four empty cells and no failure.
    """
    workflow = _load_workflows()["digest.yml"]
    step = _step(workflow, "work", "name", JOB_CLOCK_STEP)
    script = _substitute(_script(step, f"work step {JOB_CLOCK_STEP}"))

    assert JOB_CLOCK_COMMAND in script
    assert f'--date "{SUBSTITUTED_DATE}"' in script
    assert f"--shard {SUBSTITUTED_SHARD}" in script
    # `:-` rather than a bare expansion, so a stamp that never arrived is an
    # empty cell instead of the word `unbound` reaching a contract.
    assert '--job-started-at "${JOB_STARTED_AT:-}"' in script
    assert "--server-log llama-server.log" in script
    # The second instrument's two cells. Named rather than left to the flag's own
    # default, so a reader of the step can see every file the row is built from.
    assert f"--counters-file {METRICS_FILE}" in script
    # The job the row files under, which is the key column that joins it to the
    # probe's half. A clock filed under another job is a second row, not a half.
    assert f"{FINGERPRINT_JOB_FLAG} work" in script


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
    uploads = [_artifact_upload(workflow, "work", artifact) for artifact in WORK_PAYLOAD_ARTIFACTS]

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
    # publish nothing and report success. The fold step and its commit are here
    # for the harvest's reason: they run after the day is committed and touch
    # only days that can gain no more rows, so the most a
    # failure costs is one run's worth of bytes and the next run folds the same
    # days again. The picture download joins them because a day where nothing
    # was drawable produces no `shard-visuals-*` artifact at all, and every item
    # then publishes with no picture. The review tree joins it one rung further
    # out again: nothing downloads it, no gate reads it, and it is built after
    # the day is committed - so the most a failure costs is one day's contact
    # sheet, and the next run builds its own. The assemble job's own machine
    # probe is the newest: a run whose cost nobody can attribute is worse than a
    # run with one host row missing, but not worse than a day that never
    # published - and this job runs `if: always()`, so it is the one that has to
    # survive a bad day.
    #
    # The plan job's commit is the one that reads like the publish step and is
    # not. What that job owes the run is the plan artifact below it; the sight
    # and health rows it pushes here are worth a run and are not worth the run.
    # Run `35660521768` settled it: the push lost a race, this step failed, and
    # the upload after it was skipped with the job - so a plan that was already
    # computed never reached the shards and the day was lost to a ledger.
    tolerant = {
        (job_name, step.get("name") or step.get("uses"))
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if step.get("continue-on-error") == TOLERATED
    }
    assert tolerant == {
        *(("work", name) for name in WORK_LEDGER_STEPS),
        ("plan", COMMIT_STEPS["plan"]),
        ("assemble", "actions/download-artifact@v8"),
        ("assemble", FINGERPRINT_STEP),
        ("assemble", HARVEST_STEP),
        ("assemble", REVIEW_STEP),
    }


def test_every_job_that_records_a_machine_says_which_job_it_is() -> None:
    """A row that cannot name its job is a row nobody can group by.

    The column is an enum and the value is the job's own id in this file, so a
    step that drifts from its job id writes a row that reads as another job's.

    Closed-world, because a fourth job that draws a runner and records it would
    otherwise file a `--job` value nothing here ever reads. Where its row LANDS is
    somebody else's question: `test_ledger_staging.py` charges every job with the
    ledgers the verbs in its own `run:` bodies write, so a new probing job is held
    to staging `state/raw/host-fingerprint` without an edit anywhere.
    """
    workflow = _load_workflows()["digest.yml"]
    probing = {
        job_name
        for job_name in _mapping(workflow.get("jobs"), "jobs")
        for step in _steps(workflow, job_name)
        if step.get("name") == FINGERPRINT_STEP
    }
    assert probing == set(FINGERPRINT_JOBS), (
        f"{sorted(probing)} record a machine but {sorted(FINGERPRINT_JOBS)} were expected - "
        "every job that draws a runner records it, so add the new one here"
    )

    for job_name, expected in sorted(FINGERPRINT_JOBS.items()):
        step = _step(workflow, job_name, "name", FINGERPRINT_STEP)
        script = _script(step, f"job {job_name} fingerprint step")
        assert FINGERPRINT_COMMAND in script, f"{job_name} must run {FINGERPRINT_COMMAND}"
        words = shlex.split(_substitute(script))
        flag = words.index(FINGERPRINT_JOB_FLAG)
        assert words[flag + 1] == expected, (
            f"the {job_name} job files its machine as {words[flag + 1]}, not {expected}"
        )


def test_every_path_the_work_job_stages_is_in_a_fresh_checkout() -> None:
    """`git add` on a path that is not there aborts the whole step.

    The commit step runs under `set -euo pipefail` and stages every path in one
    call, so one absent path takes all the others down with it on a fresh clone.

    Asked of the staged list rather than of a list written again here, so a path
    added to the commit step without a seed fails this instead of failing a
    scheduled run - which is how `state/host-fingerprint` would have landed as a
    directory nothing had ever committed.

    `state/traces` ships a keep-file rather than a sample trace: a trace is
    evidence with a seven-day window, so a committed sample would be the one file
    in it the prune could never justify keeping.
    """
    staged = COMMIT_STAGED_PATHS["work"]
    for relative in staged:
        assert (REPO_ROOT / relative).exists(), f"{relative} must be in a fresh checkout"

    committed = subprocess.run(
        ["git", "ls-files", "--", *staged],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    for relative in staged:
        carriers = [
            path for path in committed if path == relative or path.startswith(f"{relative}/")
        ]
        assert carriers, f"{relative} must hold at least one committed file"


def test_the_observation_index_travels_with_the_rows_it_describes() -> None:
    """The index is what the writer reads instead of the rows, so it has to be committed.

    A shard pushed without its index is a day the next run cannot recognise. The
    dedupe would read an index that stops short of the rows beside it, call every
    measurement past that point new, and record each one a second time - the one
    promise the eval ledger makes about itself.

    **The two now travel as one commit rather than as two staged heads.** A work
    shard files its rows through the ledger door under `state/raw/summary-quality-evals/` and
    writes its digests into `state/summary-quality-evals-index/<day>/`, and both are inside the
    one path the shard stages - so there is no order in which one is committed
    and the other is not.

    Neither is handed back any more. A file one writer filed is computed by
    nothing else, so restoring the tip's copy would delete this shard's own and
    the producer would not write it again. That is why both trees left the
    derived set on 2026-09-22.

    The path the shard stages is `state` whole. Its raw tree need not have a
    committed sample file: it holds nothing
    until a shard files into it, and nothing again once the compaction has packed
    every day in it.
    """
    staged = COMMIT_STAGED_PATHS["work"]
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()
    for tree in (
        ledger.raw_root(Path(ledger.STATE_DIRNAME), LedgerName.SUMMARY_QUALITY_EVALS).as_posix(),
        ledger.tree_relpath(LedgerName.SUMMARY_QUALITY_EVALS_INDEX),
    ):
        carriers = [path for path in staged if _under(tree, path)]
        assert carriers, f"{tree} is written by this shard and no path in {staged} carries it"
        assert not any(_under(tree, path) for path in refreshed), (
            f"{tree} holds a file one writer filed, so handing it back deletes it"
        )
        for carrier in carriers:
            assert (REPO_ROOT / carrier).is_dir(), f"{carrier} must be in a fresh checkout"


def test_a_file_one_writer_owns_takes_no_merge_driver_and_a_shared_one_takes_a_union() -> None:
    """Asked of git rather than of a pattern matcher written here.

    `.gitattributes` is the file that decides, so the question goes to the tool
    that reads it. A second implementation of its globbing could agree with this
    test and disagree with the merge.

    Two classes and two answers. A file named for one run, attempt, job and
    shard has exactly one writer, so there is nothing for a driver to settle and
    git answers `unspecified` - its ordinary text merge, which stops the push if
    two sides ever did change one of them. A collection two jobs append
    independent rows to takes `merge=union`, and `idhazh.path_classes.UNION_SAFE` is
    this repository's own list of those. The list is read here rather than
    copied, so a collection that joins it without a line in `.gitattributes`
    fails in the same commit.

    Every tree under `state/` carried a union driver until 2026-09-19, which is
    what let a second attempt at one job stack a row the first attempt had
    already pushed. `state/feed-health` was the tree that showed why the
    written-once name replaced it: two plan jobs of one night can hold different
    verdicts on one feed, and a union there kept both and made the
    disagreement quiet.

    No path has to exist. `check-attr` matches a name against the rules and
    never opens a file, and a committed date literal in a test is a date that
    stops being interesting.
    """
    one_writer = [
        ledger.day_shard_relpath(
            which,
            date=SUBSTITUTED_DATE,
            run_id=f"{SUBSTITUTED_DATE}-1",
            attempt=1,
            job=ServerJob.WORK,
            shard=1,
        )
        for which in DAY_TREES
    ]
    one_writer.append(
        telemetry.committed_trace_relpath(
            run_id=f"{SUBSTITUTED_DATE}-1", attempt=1, job=ServerJob.WORK, shard=1
        )
    )
    shared = [
        entry if entry.endswith(".csv") else f"{entry}/2026/01/01/a.csv"
        for entry in path_classes.UNION_SAFE
    ]

    answered = subprocess.run(
        ["git", "check-attr", "merge", "--", *one_writer, *shared],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert answered == [
        *(f"{path}: merge: unspecified" for path in one_writer),
        *(f"{path}: merge: union" for path in shared),
    ]


@requires_bash
@requires_space_free_paths
def test_every_shard_of_a_full_fan_out_lands_its_rows(tmp_path: Path) -> None:
    """Two workers, one branch, one raw file each.

    Both clones start before either pushes, so the second finds a stale base.
    This proves the rebase resolves that state without losing either shard's
    rows. It does not prove the three-attempt budget: concurrent pushes cannot
    be made deterministic in a test.

    They wrote one shared file until 2026-09-18 and a union merge driver is what
    made that survive a race. Each shard files its census through the ledger
    door now, which names every raw file with an id no other write can take, so
    the two sides of the race add distinct paths and need no merge driver.

    The files come from the ledger door rather than being spelled here, so each
    name is one a run can produce. A raw file is binary, so what landed is
    compared by the blob git stored rather than by its text.
    """
    staged_paths, settings = _commit_call("work")
    env = _isolated_env(tmp_path)
    origin, _ = _scripted_origin(tmp_path, env, staged_paths)
    shards = range(2)
    run_id = f"{SUBSTITUTED_DATE}-1"
    written: dict[int, str] = {}
    runners = []
    for shard in shards:
        runner = tmp_path / f"shard-{shard}"
        _git(tmp_path, env, "clone", str(origin), str(runner))
        state = runner / ledger.STATE_DIRNAME
        [filed] = ledger.persist(
            state,
            [health_row(day=SUBSTITUTED_DATE, run=1, number=shard, stage=ItemStage.PUBLISH)],
            ledger=LedgerName.ITEM_HEALTH,
            covers=SUBSTITUTED_DATE,
            identity=writer_identity(run_id, job=ServerJob.WORK, shard=shard),
        )
        written[shard] = f"{ledger.STATE_DIRNAME}/{filed.relative_to(state).as_posix()}"
        runners.append(runner)
    assert len(set(written.values())) == len(shards), "two shards were given one name"

    results = [_run_commit_script(runner, env, staged_paths, settings) for runner in runners]

    assert [result.returncode for result in results] == [0] * len(runners)
    for shard, runner in zip(shards, runners, strict=True):
        landed = _git(origin, env, "rev-parse", f"main:{written[shard]}").strip()
        assert landed == _git(runner, env, "hash-object", written[shard]).strip(), (
            f"shard {shard}'s rows did not land as it filed them"
        )
    assert not any(_mid_rebase(runner) for runner in runners)


def test_assemble_hands_back_no_tree_a_worker_wrote_into() -> None:
    """Handing a day tree back would delete the rows this job is about to commit.

    A lost race is answered by restoring the refreshed paths from the tip and
    running the producer again. That is right for a file two runs rebuild to
    different bytes, and it is destructive for a day tree: the restore takes the
    tip's copy of the whole directory, so this attempt's own file in it - named
    for this run and written by nothing else - goes with it and the producer does
    not write it again.

    Asked of every declared tree rather than of the ones a shard happens to fill
    today, so a tree that joins the set is covered the day it is declared.
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()

    for which in DAY_TREES:
        tree = f"{ledger.STATE_DIRNAME}/{which.value}"
        covered = [path for path in refreshed if tree == path or tree.startswith(f"{path}/")]
        assert not covered, (
            f"{covered} hands back {tree}, and a writer's own file in it is deleted by "
            "the restore rather than rebuilt by the producer"
        )


def test_the_day_the_console_reads_is_handed_back_and_the_published_rows_are_not() -> None:
    """Two answers to one race, and each path takes the one that fits it.

    `state/day-metrics` is one whole JSON a day that assemble rewrites from the
    day's rows, so two attempts at one day really do land on one path with
    different bytes. Handing it back and rebuilding it is the answer, and it
    costs milliseconds.

    The published ledger is the opposite case. Its rows are filed through the
    ledger door, one written-once file named for this run, attempt, job and
    shard, so two runs of one day are two adds of two paths and there is
    nothing to settle. Handing that tree back would restore the tip's copy of
    it and delete this attempt's own file, leaving the guard against publishing
    one story twice to whatever the producer happens to write again.

    The paths are read from the writer's own helpers rather than spelled here,
    so moving either ledger fails this instead of leaving a refresh set naming a
    directory nothing writes (Guardrail #6).
    """
    refreshed = _commit_call("assemble")[1]["REFRESH_PATHS"].split()
    rebuilt = day_metrics.day_metrics_relpath(SUBSTITUTED_DATE)
    filed = ledger.raw_root(Path(ledger.STATE_DIRNAME), LedgerName.PUBLISHED).as_posix()

    assert any(_under(rebuilt, path) for path in refreshed), (
        f"{rebuilt} is rewritten whole by this job and no entry of {refreshed} hands it back"
    )
    assert not any(_under(filed, path) for path in refreshed), (
        f"{filed} holds one written-once file per writer, so handing it back would "
        "delete this attempt's own file"
    )
