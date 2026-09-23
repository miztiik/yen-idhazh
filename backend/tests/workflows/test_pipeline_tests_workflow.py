"""Does one dispatch of the pipeline test workflow compare three cases over one pair of articles?"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.pipeline_tests import (
    MINIMUM_CANDIDATES,
    TRIAL_STATE_PREFIX,
    PipelineTestsConfig,
)
from idhazh.contracts.run_plan import RunPlan
from idhazh.llm.server import setting, window
from idhazh.telemetry import traces
from utilities import candidate_pointer, model_refs, pipeline_test_ledgers

from ._harness import (
    COMMIT_SCRIPT_CALL,
    DOWNLOAD_MODEL_FILES,
    INSTALL_RUNTIME_CALL,
    MODEL_RUNTIME_MODULE,
    PINNED_LLAMA_BUILD,
    WORKFLOWS_DIR,
    _declared_dispatch_inputs,
    _isolated_env,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _pin_output_name,
    _run_bodies,
    _script,
    _step,
    _steps,
    _strings,
    _triggers,
)

pytestmark = [pytest.mark.workflow, pytest.mark.slow]

WORKFLOW: str = "idhazh-pipeline-tests.yaml"

JOB: str = "cases"

#: The second job, which is the only thing here that writes to the repository.
COMMIT_JOB: str = "commit"

CHECK_STEP: str = "Check the ledgers against their contracts"

COMMIT_STEP: str = "Commit the ledgers the cases wrote"

#: The one module that moves a dispatch's ledgers and reads them back.
LEDGER_MODULE: str = "backend/utilities/pipeline_test_ledgers.py"

#: The one step that opens the address list, and the two steps that read what it
#: chose. Named here so a fourth reader has to be added on purpose.
PICK_STEP: str = "Pick the two articles"

PLAN_STEP: str = "Plan the two articles"

#: The modules the steps call, and the call each step must still carry. Reading
#: the step and running the module is what keeps this a test of the shipped
#: bytes rather than of a copy (Guardrail #7).
DRAW_MODULE: str = "backend/utilities/pipeline_draw.py"
CASE_CONFIG_MODULE: str = "backend/utilities/pipeline_case_config.py"
REPORT_MODULE: str = "backend/utilities/pipeline_case_report.py"
PICK_CALL: str = f"{DRAW_MODULE} pick"
PLAN_CALL: str = f"{DRAW_MODULE} plan"
CASE_CONFIG_CALL: str = CASE_CONFIG_MODULE
REPORT_CALL: str = REPORT_MODULE


def _module_outputs(
    argv: list[str], *, cwd: Path, module: str = DRAW_MODULE
) -> dict[str, str]:
    """The `KEY=value` lines a step appends to `$GITHUB_OUTPUT`, as a mapping."""
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / module), *argv],
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)

#: The step that restarts the server with two slots, and the step that reads its
#: outcome. Case three is the only case guarded on a step rather than only on the
#: job not being cancelled.
RESTART_STEP: str = "Restart the model with two slots"

REPORT_STEP: str = "Say what the three cases measured"

#: The program a case step runs, spelled as a step spells it, and the path this
#: module drives. Running the shipped file rather than a copy is Guardrail #7.
CASE_MODULE: str = "backend/utilities/pipeline_test_case.py"

CASE_RUNNER: Path = REPO_ROOT / CASE_MODULE

#: The one dispatch input, the action that acts on it, and the scratch root that
#: action writes. Named here so a second way of reaching a candidate has to be
#: added on purpose.
CANDIDATE_INPUT: str = "candidate_models_file"

CANDIDATE_ACTION: str = "./.github/actions/candidate-config"

SCRATCH_CONFIG: str = "backend/var/candidate-config"

#: Where this dispatch's own ledgers land, as `run.trial_state_dirname`. The
#: same directory the bench already writes to, so nothing a dispatch records
#: sits beside the rows the console reads.
TRIAL_STATE: str = "pipeline-tests"

#: What the pin step publishes for the cache key to read, read off the program
#: itself so this file cannot name an output the program does not print.
PIN_OUTPUT: str = _pin_output_name()

FETCH_STEP: str = "Fetch runtime and weights"

PIN_STEP: str = "Say which llama.cpp build this job installs"

CACHE_STEP: str = "Cache weights and runtime"

CASE_CONFIG_STEP: str = "Write each case's config"


def _required_environment(script: str) -> set[str]:
    """Every variable a shell script refuses to run without.

    Read off the script's own `: "${NAME:?...}"` guards rather than listed, so a
    guard added to the script is a guard the caller is held to from that commit
    on. A list here would be a second copy of the script's interface, and the
    copy is what goes stale.
    """
    return set(re.findall(r':\s*"\$\{([A-Z_][A-Z0-9_]*):\?', script))


def _recorded(root: Path, case: str, item_ids: Sequence[str]) -> None:
    """Write what one case's work stage would have left under `backend/var/cases/`."""
    items = root / "backend" / "var" / "cases" / case / "run" / "items"
    items.mkdir(parents=True, exist_ok=True)
    for item_id in item_ids:
        (items / f"{item_id}.article.json").write_text("{}", encoding="utf-8")
        (items / f"{item_id}.summary.json").write_text(
            json.dumps({"status": "ok", "summarize_ms": 1000}), encoding="utf-8"
        )


def _report(root: Path, expected: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the report the step runs, over a tree of case results.

    The shipped bytes, not a copy of them (Guardrail #7). It prints a markdown
    table rather than `key=value` lines, so it is run rather than read.
    """
    assert REPORT_CALL in _script(
        _step(_load_workflows()[WORKFLOW], JOB, "name", REPORT_STEP), REPORT_STEP
    ), "the report step no longer calls the module this drives"
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / REPORT_MODULE), "--expected", " ".join(expected)],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )


def _settings() -> PipelineTestsConfig:
    """The committed config, read inside the test that needs it.

    Never at module scope: a fixture opened while the module loads is opened
    before any test exists to own the failure, and one bad shape then takes
    every test in the file with it (`CLAUDE.md` section 13).
    """
    return PipelineTestsConfig.from_json(read_text(CONFIG_DIR / "pipeline-tests.json"))


def test_the_only_way_to_start_it_is_a_person_asking() -> None:
    """Dispatch and nothing else, and the form asks one question.

    A schedule would spend a runner-hour a day on a workflow nobody is reading
    the result of, and a push or pull_request trigger would spend one per
    commit.

    The form asks which model to run, and nothing else. Every case setting is
    still read from config or drawn (Guardrail #6) - the addresses, the draw
    size, the job bound, the slot counts, the windows. Which model is the one
    question config cannot answer, because the committed config names the
    incumbent by design, and a second input would be a value somebody could
    mistype into a job measured in hours.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    declared = _declared_dispatch_inputs(workflow)
    assert sorted(declared) == [CANDIDATE_INPUT], (
        "one input, and it names the model: every case setting is read from config"
    )
    named = _mapping(declared[CANDIDATE_INPUT], f"{WORKFLOW} input {CANDIDATE_INPUT}")
    assert named.get("default") == "", (
        "empty is the default, so a dispatch that types nothing runs the configured model"
    )


def test_the_cases_run_in_sequence_in_one_job_on_one_runner() -> None:
    """Not a matrix, and the reason is the spread between hosts.

    Prefill spans 4.2x between GitHub-hosted runners, which is larger than
    anything a case here is looking for. Three jobs would report the three hosts
    they drew. One job in sequence cancels the host, so the cases differ by what
    they changed and by nothing else.

    The commit job beside it runs no case and measures nothing. It exists so the
    write lands somewhere the case job's permissions do not reach.
    """
    workflow = _load_workflows()[WORKFLOW]
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and list(jobs) == [JOB, COMMIT_JOB], (
        "one job measures, so the cases share one runner and one model load"
    )
    job = _job(workflow, JOB)
    assert "strategy" not in job, "a matrix would measure the hosts rather than the cases"
    assert job.get("runs-on") == "ubuntu-latest"
    assert _job(workflow, COMMIT_JOB).get("needs") == JOB, "nothing commits before the cases run"
    for text in _strings(_job(workflow, COMMIT_JOB)):
        assert CASE_MODULE not in text, "the committing job runs no case"


def test_the_job_bound_is_the_budget_config_declares() -> None:
    """The promise is a loop inside the hour, so the number lives in config.

    A literal in the YAML and a number in `config/pipeline-tests.json` would be
    two answers to one question, and the one an operator edits would be the one
    nothing reads.
    """
    job = _job(_load_workflows()[WORKFLOW], JOB)
    assert job.get("timeout-minutes") == str(_settings().budget_minutes)


def test_the_draw_happens_once_and_every_case_reads_it() -> None:
    """The Oracle. One step opens the address list and the cases read its answer.

    This is what makes the three numbers comparable. A case that drew its own
    pair would run different articles, and the difference between two cases would
    then be the articles rather than the change - which is exactly the confound
    a production day already has and this workflow exists to remove.

    Asserted by reading rather than by listing: every step that opens
    `config/pipeline-tests.json` for the draw is discovered, and there must be
    one. The report step opens the same file for the case names and is not a
    second draw, so the test looks for the call that draws.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    drawing = [step.get("name") for step in steps if PICK_CALL in str(step.get("run") or "")]
    assert drawing == [PICK_STEP], f"one step draws the pair, and it is {PICK_STEP!r}"

    pick = _script(_step(workflow, JOB, "name", PICK_STEP), f"{WORKFLOW}/{JOB}/{PICK_STEP}")
    assert '--seed "$PICK_SEED"' in pick, "the draw is seeded, never arbitrary"
    assert "github.run_id" in str(_step(workflow, JOB, "name", PICK_STEP).get("env")), (
        "the seed is the run id GitHub allocated, which nothing in the run can compute"
    )
    assert '"$GITHUB_OUTPUT"' in pick, "a dispatch publishes the seed it drew on"

    plan = _step(workflow, JOB, "name", PLAN_STEP)
    plan_env = str(plan.get("env"))
    assert "steps.pick.outputs.addresses" in plan_env, "the plan reads the pair the draw chose"
    assert "steps.pick.outputs.feeds" in plan_env

    names = [step.get("name") for step in steps]
    assert names.index(PICK_STEP) < names.index(PLAN_STEP), "the draw comes before the plan"


def test_every_case_runs_the_one_plan_and_nothing_else_writes_one() -> None:
    """One plan file, written once, run three times.

    The cases are steps rather than one loop so the run page shows each case's own
    wall clock, and that is exactly the shape that lets a case quietly run
    something else. So the case steps are held to the config's case ids in order,
    and the only thing they are allowed to do is call the shared script.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, JOB)
    settings = _settings()

    case_steps = [
        step
        for step in steps
        if isinstance(step.get("run"), str) and CASE_MODULE in str(step.get("run"))
    ]
    assert [step.get("name") for step in case_steps] == [
        f"Case {case.id}" for case in settings.cases
    ], "one step per declared case, named for it, in the order config declares"

    for case, step in zip(settings.cases, case_steps, strict=True):
        body = _script(step, f"{WORKFLOW}/{JOB}/{step.get('name')}")
        assert f"{CASE_MODULE} {case.id} " in body, "the step runs the case it is named for"
        assert "steps.plan.outputs.date" in str(step.get("env")), (
            "a case reads the day the one plan was written for"
        )
        assert PICK_CALL not in body, "a case never draws its own pair"

    written = [step.get("name") for step in steps if PLAN_CALL in str(step.get("run") or "")]
    assert written == [PLAN_STEP], "one step mints the plan the cases share"


def test_the_report_holds_the_cases_to_the_two_items_the_draw_chose() -> None:
    """The runtime half of the Oracle, and it fails the job rather than warning.

    Reading the workflow proves the cases were HANDED one pair. It cannot prove
    they landed on it: an address can 404, and a case that summarized one item
    where another summarized two would still print two rows of plausible
    numbers. So the report compares what each case recorded against what the plan
    asked for, and raises.
    """
    workflow = _load_workflows()[WORKFLOW]
    report = _step(workflow, JOB, "name", REPORT_STEP)
    body = _script(report, f"{WORKFLOW}/{JOB}/report")
    assert "steps.plan.outputs.item_ids" in str(report.get("env"))
    assert REPORT_CALL in body, "the report the step runs"
    source = read_text(REPO_ROOT / REPORT_MODULE)
    assert "landed != expected" in source, "the cases are compared against the plan"
    assert "raise SystemExit(" in source, "a disagreement fails the job"
    assert report.get("if") == "always()", (
        "the case that failed is the one whose census is worth printing"
    )


def test_a_failed_case_costs_the_run_that_case_and_nothing_else() -> None:
    """Three cases are three readings, and one broken case may not take the other two.

    The first dispatch failed exactly that way. The baseline step could not
    start, the two cases behind it never ran, and the run reported one failure
    where it had three to report - which read as a problem with the baseline
    rather than as a problem with the call all three share. A case is read
    against the cases beside it, so a case that did not run is evidence lost.

    `parallel-2` is the one case that reads a step as well, and the reason is
    what a failed restart leaves behind: a healthy ONE-slot server. The case
    would run against it and file that reading under two slots.
    """
    workflow = _load_workflows()[WORKFLOW]
    for case in _settings().cases:
        step = _step(workflow, JOB, "name", f"Case {case.id}")
        condition = _normalize_condition(step.get("if"), f"case {case.id} condition")
        assert "!cancelled()" in condition, (
            f"case {case.id} stops when a sibling case fails, and its reading is lost with it"
        )

    restart = _step(workflow, JOB, "name", RESTART_STEP)
    assert restart.get("id") == "restart", "the case that needs the restart has to name it"
    assert "!cancelled()" in _normalize_condition(restart.get("if"), "restart condition"), (
        "the restart runs after a failed case, or the case behind it is lost too"
    )
    parallel = _normalize_condition(
        _step(workflow, JOB, "name", "Case parallel-2").get("if"), "parallel-2 condition"
    )
    assert "steps.restart.conclusion == 'success'" in parallel, (
        "the two-slot case runs only where the two-slot server started"
    )


def test_the_report_names_a_case_that_recorded_nothing_and_prints_the_rest(
    tmp_path: Path,
) -> None:
    """A case that produced nothing is a census line, not a broken comparison.

    It has already failed or been skipped, its own step is red and the job is
    red with it. What the report owes is the name: a table that quietly dropped
    the row would leave a reader counting cases to notice one was missing, and
    raising on it would hide the failure that really matters underneath a
    sentence about articles.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    cases = [case.id for case in _settings().cases]
    for case in cases[:-1]:
        _recorded(tmp_path, case, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr.strip()
    assert f"these cases produced nothing: {cases[-1]}" in completed.stdout
    assert f"| {cases[-1]} | 0 | 0 | 0 | nothing recorded |" in completed.stdout
    for case in cases[:-1]:
        assert f"| {case} | 2 | 2 | 2000 | - |" in completed.stdout, (
            "a case that ran is still measured beside the one that did not"
        )


def test_the_report_refuses_a_comparison_across_different_articles(tmp_path: Path) -> None:
    """The half that still raises, and the reason it has to.

    Two cases that read different articles produce two numbers nobody may
    subtract, and the table is three rows of plausible milliseconds either way.
    This is the one thing the report fails the job over, and a case that
    recorded nothing must not be able to trip it.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    expected = ["ai-0000000001", "world-0000000002"]
    cases = [case.id for case in _settings().cases]
    for case in cases[:-1]:
        _recorded(tmp_path, case, expected)
    _recorded(tmp_path, cases[-1], ["ai-0000000001", "world-0000000003"])

    completed = _report(tmp_path, expected)
    assert completed.returncode != 0, "a disagreement about the articles fails the job"
    assert "did not all read the same two articles" in completed.stderr
    assert cases[-1] in completed.stderr, "the case that disagreed is named"


def test_it_publishes_nothing_a_reader_sees_and_writes_only_the_trial_roots() -> None:
    """A test workflow that could write the site would be a second publisher.

    It does commit now, and that is the whole of the write: a second job appends
    what the cases measured under their own trial roots, which no console page
    reads. Everything else it produced lives under `backend/var/`, which is never
    committed, and leaves as an artifact.

    Spelled against the two jobs rather than against the words `git commit`. The
    file carried that pair of assertions until 2026-09-22 and they would have
    stayed green through this change by accident, because `commit-and-push.sh`
    contains neither word.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert workflow.get("permissions") == {"contents": "read"}, (
        "the file-level default is read, so a job that writes has to say so itself"
    )
    assert _job(workflow, JOB).get("permissions") == {"contents": "read"}, (
        "the job that reads the open web holds no write"
    )
    assert _job(workflow, COMMIT_JOB).get("permissions") == {"contents": "write"}, (
        "the committing job takes the write, and takes nothing else with it"
    )

    for text in _strings(workflow):
        assert "frontend/public" not in text, "a test dispatch publishes nothing"

    upload = _step(workflow, JOB, "name", "Upload what the cases produced")
    with_block = upload.get("with")
    assert isinstance(with_block, dict)
    assert str(with_block.get("path")).startswith("backend/var/")
    assert with_block.get("retention-days") == "90"


def test_the_commit_job_stages_the_declared_trial_roots_and_nothing_wider() -> None:
    """Every path handed to `git add` comes from committed config, not from a body.

    The staged paths are printed by `pipeline_test_ledgers place`, which reads
    the declared cases and names one root each. A path spelled in the workflow
    would be a second copy of the naming rule, and a wider one - `state`, or
    `state/pipeline-tests` before the cases had their own roots - would let this
    job push a ledger the daily run owns.
    """
    workflow = _load_workflows()[WORKFLOW]
    body = _script(_step(workflow, COMMIT_JOB, "name", COMMIT_STEP), "the commit step")

    assert f"{LEDGER_MODULE} place" in body, "the roots to stage are printed, never spelled"
    assert " ".join(COMMIT_SCRIPT_CALL) in body, "it commits through the shared script"
    staged = re.search(r"commit-and-push\.sh (?P<paths>.+)", body)
    assert staged is not None
    assert staged["paths"].strip() == '"${TRIAL_ROOTS[@]}"', (
        f"the commit step stages a path of its own: {staged['paths']}"
    )

    settings = _settings()
    roots = [case.trial_state_dirname for case in settings.cases]
    assert len(set(roots)) == len(roots), "two cases share a trial root, so one overwrites the other"
    for root in roots:
        assert root.startswith(f"{TRIAL_STATE_PREFIX}-"), (
            f"{root} is not under the prefix the bench and the qualification already use"
        )


def test_the_check_reads_the_download_before_anything_is_staged() -> None:
    """The control is the check, not the job split (Guardrail #11).

    The bytes are downstream of pages this project did not write. The split
    bounds what a bad push could reach; what stops one is reading every payload
    through the contract that declares it, and the reading has to come first.
    """
    workflow = _load_workflows()[WORKFLOW]
    steps = _steps(workflow, COMMIT_JOB)
    names = [step.get("name") for step in steps]
    check = _script(_step(workflow, COMMIT_JOB, "name", CHECK_STEP), "the check step")

    assert f"{LEDGER_MODULE} check" in check
    assert names.index(CHECK_STEP) < names.index(COMMIT_STEP), (
        "a check after the push is a report, not a control"
    )

    download = _step(workflow, COMMIT_JOB, "uses", "actions/download-artifact@v8")
    settings = _mapping(download.get("with"), "the ledger download")
    assert str(settings["merge-multiple"]) == "true"
    assert str(settings["path"]).startswith("backend/var/"), (
        "a download unpacked over state/ would be read together with rows already committed"
    )
    assert steps.index(download) < names.index(CHECK_STEP), (
        "the check reads what arrived, so it runs after the download"
    )


#: The one writer the downloaded tree carries, spelled through the producers a
#: case run uses. `GITHUB_RUN_ID` is GitHub's eleven-digit execution number, so
#: the run id is the project's `<date>-<execution>` rather than that number
#: alone.
CASE_DATE: str = "2026-09-22"
CASE_RUN_ID: str = f"{CASE_DATE}-40000000001"
CASE_ATTEMPT: int = 1
CASE_JOB: ServerJob = ServerJob.WORK
CASE_SHARD: int = 0
CASE_DAY_PATH: str = CASE_DATE.replace("-", "/")
CASE_WRITER: str = ledger.segment_name(
    run_id=CASE_RUN_ID, attempt=CASE_ATTEMPT, job=CASE_JOB, shard=CASE_SHARD
)
CASE_TRACE: str = ledger.segment_name(
    run_id=CASE_RUN_ID,
    attempt=CASE_ATTEMPT,
    job=CASE_JOB,
    shard=CASE_SHARD,
    suffix=traces.TRACE_SUFFIX,
)


def _a_downloaded_tree(root: Path, *, case: str) -> Path:
    """One case's ledgers as the artifact carries them: a day shard and a trace.

    Both paths are built by the producers a case run uses, so a grammar that
    moves takes this fixture with it rather than leaving it green against a
    shape nothing writes.
    """
    rows = ledger.segment_contract(ledger.SegmentLedger.SPAN_ROLLUP).csv_columns()
    segment = ledger.day_shard_path(
        root / case,
        ledger.SegmentLedger.SPAN_ROLLUP,
        date=CASE_DATE,
        run_id=CASE_RUN_ID,
        attempt=CASE_ATTEMPT,
        job=CASE_JOB,
        shard=CASE_SHARD,
    )
    segment.parent.mkdir(parents=True, exist_ok=True)
    segment.write_text(
        ",".join(rows)
        + "\n"
        + ",".join(
            {
                "version": "2026-09-06T15:00",
                "date": CASE_DATE,
                "run_id": CASE_RUN_ID,
                "shard": str(CASE_SHARD),
                "span_name": "item",
                "count": "2",
                "total_ms": "9000",
            }.get(column, "")
            for column in rows
        )
        + "\n",
        encoding="utf-8",
    )
    trace = traces.committed_trace_path(
        root / case,
        run_id=CASE_RUN_ID,
        attempt=CASE_ATTEMPT,
        job=CASE_JOB,
        shard=CASE_SHARD,
    )
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text('{"kind":"span","name":"item","duration_ms":1}\n', encoding="utf-8")
    return root


def test_the_check_passes_the_two_shapes_a_case_really_writes(tmp_path: Path) -> None:
    """A day shard and a trace, filed under a declared case's own trial root."""
    case = _settings().cases[0]
    tree = _a_downloaded_tree(tmp_path / "trial-ledgers", case=case.trial_state_dirname)

    assert pipeline_test_ledgers.refusals(tree, roots=frozenset({case.trial_state_dirname})) == []


@pytest.mark.parametrize(
    ("relative", "because"),
    [
        (f"a-tenant/span-rollup/{CASE_DAY_PATH}/{CASE_WRITER}", "no declared case"),
        ("{case}/items/ai-0000000001.summary.json", "a store a case run does not write"),
        (f"{{case}}/summaries/{CASE_DAY_PATH}/{CASE_WRITER}", "no such ledger"),
        (f"{{case}}/traces/{CASE_DAY_PATH}/{CASE_TRACE}", "a line that is not a span"),
    ],
)
def test_the_check_refuses_what_no_case_producer_wrote(
    tmp_path: Path, relative: str, because: str
) -> None:
    """The oracle for the control. A check nothing can fail is not a control.

    Every row here is a path an artifact could carry and a case producer could
    not: a directory no config declares, a store no case run writes, a ledger
    outside the closed set, and a payload that does not read back. The last one
    is why the check opens the files rather than matching their names.
    """
    case = _settings().cases[0]
    tree = _a_downloaded_tree(tmp_path / "trial-ledgers", case=case.trial_state_dirname)
    path = tree / relative.format(case=case.trial_state_dirname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a span\n", encoding="utf-8")

    refused = pipeline_test_ledgers.refusals(
        tree, roots=frozenset({case.trial_state_dirname})
    )

    assert refused, f"the check let through {because}"


@pytest.mark.parametrize("wrote", [True, False])
def test_the_gather_verb_writes_nothing_to_stdout_that_is_not_a_step_output(
    tmp_path: Path, wrote: bool
) -> None:
    """The step appends this stdout to `$GITHUB_OUTPUT`, which takes `key=value` only.

    One other line there fails the step, and the step that fails is the one
    holding every ledger three cases just spent an hour producing - so the
    dispatch measures what it was dispatched to measure and pushes none of it.

    Both arms, because the progress lines only appear when a case did write:
    a dispatch that lost every case was the one shape that passed before.
    """
    case = _settings().cases[0]
    state = tmp_path / "state"
    if wrote:
        _a_downloaded_tree(state, case=case.trial_state_dirname)
    else:
        state.mkdir(parents=True)

    done = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / LEDGER_MODULE),
            "gather",
            "--tree",
            str(tmp_path / "trial-ledgers"),
            "--state",
            str(state),
            "--config-root",
            str(CONFIG_DIR),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    for line in done.stdout.splitlines():
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", line), (
            f"{line!r} is not a step output, and `$GITHUB_OUTPUT` takes nothing else"
        )
    assert f"{pipeline_test_ledgers.FOUND_KEY}={'true' if wrote else 'false'}" in done.stdout
    if wrote:
        assert case.trial_state_dirname in done.stderr, "a person still reads what arrived"
    else:
        assert "nothing to push" in done.stderr, "a dispatch that gathered nothing says so"


def test_every_declared_case_is_placed_whether_or_not_it_wrote_anything(tmp_path: Path) -> None:
    """`git add` aborts on a path the checkout does not hold, and takes the step with it.

    A dispatch that lost two cases still has to hand the commit script paths it
    can stage. An empty directory git cannot see costs nothing; a missing one
    costs the whole push, including the case that did produce rows.
    """
    cases = _settings().cases
    tree = _a_downloaded_tree(tmp_path / "trial-ledgers", case=cases[0].trial_state_dirname)
    state = tmp_path / "state"

    staged = pipeline_test_ledgers.place(
        tree, state, roots=[case.trial_state_dirname for case in cases]
    )

    assert len(staged) == len(cases)
    for case in cases:
        assert (state / case.trial_state_dirname).is_dir()
    assert (
        state / cases[0].trial_state_dirname / ledger.SegmentLedger.SPAN_ROLLUP.value
    ).is_dir()


def test_the_address_list_can_still_answer_a_draw() -> None:
    """Twenty candidates at least, all distinct, each naming a feed we really read.

    A candidate on a feed `config/sources.json` no longer carries is an address
    the run would have to invent a vertical and a tier for. The plan step reads
    both off the feed, so an orphan candidate is a `KeyError` 40 minutes into a
    dispatch rather than a failure here.

    The live list, never the file's text. The dispatch builds its map from
    `settings.sources.feeds`, so a candidate whose feed has moved to `retired`
    is that same `KeyError` while a search of the whole file still finds the id
    on the tombstone shelf. It would also have the test workflow request a
    source we decided to stop asking.
    """
    settings = _settings()
    assert len(settings.candidates) >= MINIMUM_CANDIDATES

    live = {feed.id for feed in config.load(CONFIG_DIR).sources.feeds}
    for candidate in settings.candidates:
        assert candidate.source_id in live, (
            f"{candidate.source_id} is not a live feed in config/sources.json"
        )


@pytest.mark.parametrize("headline", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_a_candidate_with_a_blank_headline_is_refused_by_the_config(headline: str) -> None:
    """The typo is a hand edit to this file, so this is where it has to land.

    Extract refuses an item with no headline, which degrades that item and costs
    a dispatch half its articles. A blank headline in the list is a mistake we
    can see before anything is dispatched, and a minimum length of one would not
    see it: three spaces is three characters.
    """
    settings = _settings()
    payload = settings.model_dump(mode="json")
    payload["candidates"][0]["title"] = headline

    with pytest.raises(ValidationError):
        PipelineTestsConfig.model_validate(payload)


def test_the_draw_is_decided_by_the_seed_and_by_nothing_else() -> None:
    """Same seed, same pair, anywhere. Different seed, different pair.

    A draw that moved between two runs of the same seed could not be replayed,
    and a draw that ignored the seed would read the same two articles forever -
    which is the fixed pair this list exists instead of.
    """
    settings = _settings()
    once = settings.draw("34852763827")
    assert once == settings.draw("34852763827")
    assert len(once) == settings.articles_a_dispatch
    assert len({candidate.url for candidate in once}) == len(once)

    seeds = {tuple(c.url for c in settings.draw(str(seed))) for seed in range(40)}
    assert len(seeds) > 1, "the seed has to move the pair, or the list is decorative"


def test_the_pick_step_publishes_the_pair_the_plan_step_asks_for() -> None:
    """Run the shipped bytes, do not read them (Guardrail #7).

    The two steps meet through three output names. A step that printed
    `urls=` while the next one read `addresses=` would fail 40 minutes into a
    dispatch, with an empty plan and no article fetched.
    """
    workflow = _load_workflows()[WORKFLOW]
    seed = "34852763827"
    assert PICK_CALL in _script(_step(workflow, JOB, "name", PICK_STEP), PICK_STEP)
    published = _module_outputs(["pick", "--seed", seed], cwd=REPO_ROOT)

    assert published["seed"] == seed
    drawn = _settings().draw(seed)
    assert published["addresses"] == " ".join(candidate.url for candidate in drawn)
    assert published["feeds"] == " ".join(candidate.source_id for candidate in drawn)


def test_the_case_configs_the_workflow_writes_all_load(tmp_path: Path) -> None:
    """Every case's config root has to survive `config.load`, or the case cannot start.

    The work stage and the argv builder both open it. A case that wrote a knob
    outside its schema would fail on the runner after the weights were fetched,
    and the case whose numbers are worth having most - two slots, a doubled
    window - is the last one to run.

    Cut from the scratch root the step names, not from `config/`, so this drives
    the route a candidate dispatch really takes.
    """
    scratch = _scratch(tmp_path, models_file=None)
    workflow = _load_workflows()[WORKFLOW]
    case_config = _script(_step(workflow, JOB, "name", CASE_CONFIG_STEP), "case config")
    assert CASE_CONFIG_CALL in case_config
    assert f"--config-root {SCRATCH_CONFIG}" in case_config, (
        "the cases are cut from the scratch copy, so a candidate reaches all three"
    )
    written = _module_outputs(
        ["--config-root", scratch.as_posix()], cwd=tmp_path, module=CASE_CONFIG_MODULE
    )

    settings = _settings()
    assert sorted(written) == sorted(case.id for case in settings.cases)
    for case in settings.cases:
        loaded = config.load(tmp_path / written[case.id])
        assert loaded.app.summarize.asks_for_a_visual_plan is case.asks_for_a_visual_plan
        if not case.asks_for_a_visual_plan:
            assert loaded.app.visuals.enabled_kinds == [], "no picture is reachable"
        served = loaded.models.summarizer.server
        committed = config.load(CONFIG_DIR).models.summarizer.server
        assert setting(served, "n_parallel") == (
            case.n_parallel or setting(committed, "n_parallel")
        )
        assert window(served) == (case.n_ctx or window(committed))


def test_each_case_writes_its_own_trial_root(tmp_path: Path) -> None:
    """Three cases, three roots, and no two of them share a path.

    The dispatch runs one plan, so the three cases share a run id, a shard, a
    job and an attempt. Those four fields are the whole of a writer's filename,
    so without a root of its own the last case to write would be the only one
    anybody could read - and the three numbers this workflow exists to subtract
    would be one number.

    Read out of the config each case really runs on, not out of the helper: the
    helper agreeing with itself says nothing about what `work` opens.
    """
    scratch = _scratch(tmp_path, models_file=None)
    written = _module_outputs(
        ["--config-root", scratch.as_posix()], cwd=tmp_path, module=CASE_CONFIG_MODULE
    )

    roots = {
        case_id: config.load(tmp_path / relative).app.run.trial_state_dirname
        for case_id, relative in written.items()
    }
    declared = {case.id: case.trial_state_dirname for case in _settings().cases}

    assert len(set(roots.values())) == len(roots), f"two cases share a trial root: {roots}"
    for case_id, root in roots.items():
        assert root == declared[case_id]
        assert root.startswith(f"{TRIAL_STATE_PREFIX}-"), (
            f"{root} is outside the prefix the bench and the qualification already use"
        )


def test_the_parallel_case_keeps_the_window_the_gate_admits_articles_against() -> None:
    """A slot count without a window beside it is a test of a smaller window.

    llama-server divides the window it is given between its slots, so two slots
    on the committed number halve what each one holds - and the sequence gate
    still admits articles against the config number. The case would then refuse
    long articles and read as a concurrency result.
    """
    committed = config.load(CONFIG_DIR).models.summarizer.server
    for case in _settings().cases:
        if case.n_parallel is None or case.n_parallel == (setting(committed, "n_parallel") or 1):
            continue
        assert case.n_ctx is not None, f"{case.id} moves the slot count and not the window"
        assert case.n_ctx >= window(committed) * case.n_parallel, (
            f"{case.id} leaves each slot less than the gate admits articles against"
        )


def test_the_plan_step_writes_a_plan_the_work_stage_can_open(tmp_path: Path) -> None:
    """The one payload every case reads, built by the shipped program.

    `RunPlan` refuses a list whose desk counts disagree with its items, and the
    program builds those counts itself because nothing read a feed. Asserting
    the shape by eye is how that is found on the runner instead of here.
    """
    shutil.copytree(CONFIG_DIR, tmp_path / "config")
    seed = "34852763827"
    drawn = _settings().draw(seed)

    published = _module_outputs(
        [
            "plan",
            "--addresses",
            " ".join(candidate.url for candidate in drawn),
            "--feeds",
            " ".join(candidate.source_id for candidate in drawn),
            "--execution",
            seed,
        ],
        cwd=tmp_path,
    )

    written = tmp_path / "backend" / "var" / "pipeline-tests" / "plan.json"
    plan = RunPlan.from_json(read_text(written))
    assert plan.run_id == f"{published['date']}-{seed}"
    assert [item.source_url for item in plan.items] == [c.url for c in drawn]
    assert [item.title for item in plan.items] == [c.title for c in drawn], (
        "a planned item with no headline is refused by extract, so every case reads zero items"
    )
    assert published["item_ids"] == " ".join(item.item_id for item in plan.items)
    assert plan.feeds_read == 0, "this plan came off a config list, so no feed was asked"


def _ran_a_case(tmp_path: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the shipped case runner against a fixture tree (Guardrail #7).

    A fixture tree rather than the committed one, because what is being read is
    the exit code and the exit code is the same for two articles as for none
    (CLAUDE.md section 13).
    """
    return subprocess.run(
        [sys.executable, str(CASE_RUNNER), *argv],
        cwd=tmp_path,
        env={**_isolated_env(tmp_path), "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "usage:"),
        (["baseline"], "usage:"),
        (["not-a-case", "2026-09-14"], "unknown case"),
    ],
)
def test_the_case_runner_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it (Guardrail #7).

    Three steps pass a case id as a bare string. A typo would otherwise run the
    committed config under another case's name, and the report would file that
    case's number against a config it never used.
    """
    completed = _ran_a_case(tmp_path, argv)
    assert completed.returncode == 2
    assert message in completed.stderr


def test_the_case_runner_refuses_to_run_without_the_plan_the_cases_share(tmp_path: Path) -> None:
    """A case with no plan is a case that would summarize nothing and say so quietly.

    `idhazh work` with an absent plan is a failure four steps later about a file
    a reader of the log has to go and find. This one names what is missing and
    which step writes it.
    """
    (tmp_path / "backend" / "var" / "cases" / "baseline" / "config").mkdir(parents=True)
    completed = _ran_a_case(tmp_path, ["baseline", "2026-09-14"])
    assert completed.returncode == 2
    assert "no plan to run" in completed.stderr


def test_a_case_whose_pipeline_failed_is_not_reported_as_a_call_it_could_not_serve(
    tmp_path: Path,
) -> None:
    """The other half of the exit-code contract, and the half nothing has held.

    `2` says this program was asked for something it cannot serve. A pipeline
    that ran and failed returns its own code, so a person reading the run page
    tells a typo in a case id from a case that really failed. Driven by handing
    the pipeline a config root with nothing in it, which is a real failure of
    the real program rather than a stub that returns a number.

    The half-written run goes with it: a case that failed leaves no `run`
    directory for the report to read as a measurement.
    """
    case_root = tmp_path / "backend" / "var" / "cases" / "baseline"
    (case_root / "config").mkdir(parents=True)
    plan = tmp_path / "backend" / "var" / "pipeline-tests" / "plan.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")

    completed = _ran_a_case(tmp_path, ["baseline", "2026-09-14"])
    assert completed.returncode != 0, "a failed pipeline fails the step that ran it"
    assert completed.returncode != 2, (
        "2 is reserved for a call this program cannot serve, so a failed "
        f"pipeline may not spell it: {completed.stderr}"
    )
    assert not (case_root / "run").exists(), "nothing is filed under a case that did not finish"


def _scratch(tmp_path: Path, *, models_file: str | None) -> Path:
    """The scratch config root the composite action builds, built the same way.

    The committed tree is copied and the shipped program moves the pointer, so a
    test that passes here is a test of the bytes the action runs (Guardrail #7).
    `None` means an empty dispatch, which is the committed pointer.
    """
    scratch = tmp_path / "backend" / "var" / "candidate-config"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(CONFIG_DIR, scratch)
    named = models_file or json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    candidate_pointer.point_at(named, scratch=scratch, trial_state=TRIAL_STATE)
    return scratch


def test_a_dispatch_that_names_nothing_runs_the_model_config_already_names() -> None:
    """The empty form is the old behaviour, and the program is what says so.

    The input exists to check a candidate. It may not change what a dispatch
    that types nothing runs, because every reading this workflow has ever taken
    was taken that way - and a form whose default quietly moved the model would
    make the old numbers describe something else (Guardrail #10).
    """
    empty = dict(
        row.split("=", 1)
        for row in model_refs.trial_rows(CONFIG_DIR, "", prefix="candidate_")
    )
    configured = dict(
        row.split("=", 1) for row in model_refs.pinned_rows(CONFIG_DIR)
    )

    pointer = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    assert empty["candidate_models_file"] == pointer
    for field in model_refs.CONFIGURED_FIELDS:
        assert empty[f"candidate_{field}"] == configured[f"summarizer_{field}"], field


def test_a_named_candidate_moves_one_line_and_leaves_the_committed_config_alone(
    tmp_path: Path,
) -> None:
    """One line moves, and it is the line a swap would later move.

    A dispatch that edited `config/` would leave the checkout it measured on
    disagreeing with the tree it was cut from, and every control this workflow
    holds fixed - the prompt, the schema, the sampler, the window, the
    truncation cap - is the committed one only because the copy differs by that
    one line and nothing else.
    """
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    named = next(
        path.relative_to(CONFIG_DIR).as_posix()
        for path in sorted((CONFIG_DIR / "models").glob("*.json"))
        if path.relative_to(CONFIG_DIR).as_posix() != committed["models_file"]
    )

    scratch = _scratch(tmp_path, models_file=named)
    written = json.loads(read_text(scratch / "idhazh.json"))

    assert written["models_file"] == named
    assert written["run"]["trial_state_dirname"] == TRIAL_STATE
    moved = {
        key
        for key in set(committed) | set(written)
        if committed.get(key) != written.get(key)
    }
    assert moved == {"models_file", "run"}, f"one pointer and one state root, not {moved}"
    assert json.loads(read_text(CONFIG_DIR / "idhazh.json")) == committed, (
        "the committed config is read, never written"
    )
    assert config.load(scratch).models.summarizer.id, "the scratch root still loads"


def test_no_step_opens_the_committed_models_file_once_a_candidate_may_be_named() -> None:
    """Every reader of a model fact reads the copy, or a candidate is half-applied.

    The failure this stops is a dispatch that fetches the candidate, checks it
    against the incumbent's recorded digest, and starts a server on flags the
    committed entry declares. Each of those is a step that looks right on its
    own.
    """
    workflow = _load_workflows()[WORKFLOW]
    build = _step(workflow, JOB, "uses", CANDIDATE_ACTION)
    with_block = build.get("with")
    assert isinstance(with_block, dict)
    assert with_block.get("models_file") == "${{ steps.models.outputs.candidate_models_file }}"
    assert with_block.get("trial_state") == TRIAL_STATE, (
        "the ledgers this dispatch writes land off the production state root"
    )

    for body in _run_bodies(workflow):
        for line in body.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert '"config/idhazh.json"' not in line, line
            assert 'Path("config")' not in line, line

    names = [step.get("name") for step in _steps(workflow, JOB)]
    assert names.index(build.get("name")) < names.index("Verify the weights"), (
        "the digest is read out of the copy, so the copy has to exist first"
    )
    assert names.index(build.get("name")) < names.index(CASE_CONFIG_STEP)


def test_the_fetch_step_is_two_calls_and_reads_the_config_the_cases_run_under() -> None:
    """One token through `env`, one config root on the command line, and nothing else.

    The step used to hand a script seven values through `env` - a repository, a
    commit, a filename and a draft head's three - each of them a copy of a fact
    the models file already held. The program reads that file itself, so the
    step passes the root and the token and nothing a copy could be made of.

    The root is the scratch copy the cases are cut from, not the committed one.
    Checking a candidate against the committed config's digest is the failure
    this dispatch exists to catch, so a step that read `config` here would
    verify the wrong model's bytes and pass.
    """
    fetch = _step(_load_workflows()[WORKFLOW], JOB, "name", FETCH_STEP)
    body = _script(fetch, FETCH_STEP)
    assert INSTALL_RUNTIME_CALL in body, "the step must install the pinned build"
    assert DOWNLOAD_MODEL_FILES in body, "the step must fetch what the model declares"
    assert f"--config-root {SCRATCH_CONFIG}" in body, f"the download must read {SCRATCH_CONFIG}"

    supplied = fetch.get("env")
    assert isinstance(supplied, dict)
    assert set(supplied) == {"GITHUB_TOKEN"}, (
        f"the step hands over more than the token it cannot read itself: {sorted(supplied)}"
    )


def test_the_cache_key_names_the_build_and_the_file_set_it_holds() -> None:
    """The key holds the runtime and the weights, so a key naming less serves the wrong bytes.

    The fetch runs only on a miss. A key that could name a build the install
    does not put down would restore one binary under the name of another and
    never fetch again, which is the instability of following the newest release
    with none of its freshness.

    The model half is a digest over every file the entry declares rather than a
    filename and a commit. Two builds of one model share a name, and an entry
    that gains a companion keeps both - so the old key restored a
    complete-looking entry with a file missing.
    """
    workflow = _load_workflows()[WORKFLOW]
    cache = _step(workflow, JOB, "name", CACHE_STEP)
    with_block = cache.get("with")
    assert isinstance(with_block, dict)
    key = str(with_block.get("key"))
    assert f"steps.runtime.outputs.{PIN_OUTPUT}" in key, key
    assert "steps.models.outputs.candidate_cache_key" in key, key

    names = [step.get("name") for step in _steps(workflow, JOB)]
    assert names.index(PIN_STEP) < names.index(CACHE_STEP), "the key cannot read a later step"


def test_the_pin_verb_prints_the_build_the_cache_key_reads(tmp_path: Path) -> None:
    """Run it, do not read it (Guardrail #7).

    The build is one value in one file, the install reads that file, and the
    cache key is built from what the program prints out of it. This is the one
    place the printed value and the pinned value are compared, and it is what
    makes the extraction safe: an upgrade that moved the value and not the print
    would key the cache on the old build and restore the old binary forever.
    """
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / MODEL_RUNTIME_MODULE), "print-pinned-build"],
        cwd=REPO_ROOT,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == f"{PIN_OUTPUT}={PINNED_LLAMA_BUILD}"
    assert not (tmp_path / "backend").exists(), "asking which build must not fetch one"


def test_no_case_setting_is_written_into_the_workflow() -> None:
    """Guardrail #6. The cases, the slot counts and the windows are all in config.

    A slot count written into the YAML would be the number an operator edits in
    the wrong place, and it would be invisible to the schema that bounds it.
    """
    text = read_text(WORKFLOWS_DIR / WORKFLOW)
    settings = _settings()
    for case in settings.cases:
        if case.n_ctx is not None:
            assert str(case.n_ctx) not in text, f"{case.id} writes its window into the workflow"
    for candidate in settings.candidates:
        assert candidate.url not in text, "an address belongs in config, never in the workflow"
