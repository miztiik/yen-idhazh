"""Does one dispatch of the pipeline test workflow run every enabled test case, all at once?"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.pipeline_tests import (
    MINIMUM_CANDIDATES,
    TRIAL_STATE_PREFIX,
    PipelineTestsConfig,
)
from idhazh.contracts.run_plan import RunPlan
from idhazh.llm.server import setting, window
from idhazh.telemetry import traces
from utilities import (
    candidate_pointer,
    model_refs,
    pipeline_draw,
    pipeline_test_case,
    pipeline_test_case_config,
    pipeline_test_ledgers,
)

from ._harness import (
    COMMIT_PROGRAM_CALL,
    MODEL_RUNTIME_MODULE,
    MODEL_SERVER_ACTION,
    PINNED_LLAMA_BUILD,
    WORKFLOWS_DIR,
    _action_call,
    _copy_config,
    _declared_dispatch_inputs,
    _isolated_env,
    _job,
    _load_workflows,
    _mapping,
    _needs,
    _normalize_condition,
    _pin_output_name,
    _run_bodies,
    _script,
    _step,
    _steps,
    _strings,
    _triggers,
)

pytestmark = pytest.mark.workflow

WORKFLOW: str = "idhazh-pipeline-tests.yaml"

#: The four jobs, in the order they run. Named here so a fifth is added on purpose.
PLAN_JOB: str = "plan"
TEST_CASE_JOB: str = "test-case"
REPORT_JOB: str = "report"
COMMIT_JOB: str = "commit"

CHECK_STEP: str = "Check the ledgers against their contracts"

COMMIT_STEP: str = "Commit the ledgers the test cases wrote"

#: The one module that moves a dispatch's ledgers and reads them back.
LEDGER_MODULE: str = "backend/utilities/pipeline_test_ledgers.py"

#: The one step that opens the address list, the step that reads what it chose,
#: and the step that lists the runners. Named here so a fourth reader has to be
#: added on purpose.
PICK_STEP: str = "Pick the articles"
PLAN_STEP: str = "Plan the articles"
JOBS_STEP: str = "List the runners the enabled test cases need"

RUN_STEP: str = "Run the test case"
PROVE_STEP: str = "The server proves the entry"
REPORT_STEP: str = "Say what the test cases did"
TEST_CASE_CONFIG_STEP: str = "Write each test case's config"
PIN_STEP: str = "Say which llama.cpp build this run installs"

#: The modules the steps call, and the call each step must still carry. Reading
#: the step and running the module is what keeps this a test of the shipped
#: bytes rather than of a copy (Guardrail #7).
DRAW_MODULE: str = "backend/utilities/pipeline_draw.py"
TEST_CASE_CONFIG_MODULE: str = "backend/utilities/pipeline_test_case_config.py"
REPORT_MODULE: str = "backend/utilities/pipeline_test_case_report.py"
TEST_CASE_MODULE: str = "backend/utilities/pipeline_test_case.py"
PROVE_MODULE: str = "backend/utilities/prove_the_entry.py"
TEST_CASE_RUNNER: Path = REPO_ROOT / TEST_CASE_MODULE
PICK_CALL: str = f"{DRAW_MODULE} pick"
PLAN_CALL: str = f"{DRAW_MODULE} plan"
JOBS_CALL: str = f"{TEST_CASE_MODULE} jobs"
RUN_CALL: str = f"{TEST_CASE_MODULE} run"

#: The one dispatch input, the action that acts on it, and the scratch root that
#: action writes. Named here so a second way of reaching a candidate has to be
#: added on purpose.
CANDIDATE_INPUT: str = "candidate_models_file"

CANDIDATE_ACTION: str = "./.github/actions/candidate-config"

SCRATCH_CONFIG: str = "backend/var/candidate-config"

#: Where this dispatch's own ledgers land, as `run.trial_state_dirname`, before
#: each test case moves its own under a root of its own.
TRIAL_STATE: str = "pipeline-tests"

#: What the pin step publishes for the model block to read, read off the program
#: itself so this file cannot name an output the program does not print, and
#: how every runner reads it back: as the plan job's output.
PIN_OUTPUT: str = _pin_output_name()
PIN_RELAYED: str = f"${{{{ needs.plan.outputs.{PIN_OUTPUT} }}}}"

#: The artifact the one plan crosses from the job that writes it to every runner.
PLAN_ARTIFACT: str = "pipeline-tests-plan-${{ github.run_id }}"

#: The config root one runner serves, proves and runs, as the workflow spells it.
TEST_CASE_ROOT: str = "backend/var/test-cases/${{ matrix.test_case }}/config"


def _module_outputs(argv: list[str], *, cwd: Path, module: str = DRAW_MODULE) -> dict[str, str]:
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


def _settings() -> PipelineTestsConfig:
    """The committed config, read inside the test that needs it.

    Never at module scope: a fixture opened while the module loads is opened
    before any test exists to own the failure, and one bad shape then takes
    every test in the file with it (`CLAUDE.md` section 13).
    """
    return PipelineTestsConfig.from_json(read_text(CONFIG_DIR / "pipeline-tests.json"))


def _switched(settings: PipelineTestsConfig, *, on: Sequence[str]) -> PipelineTestsConfig:
    """The same config with exactly these test cases switched on."""
    payload = settings.model_dump(mode="json")
    for test_case in payload["test_cases"]:
        test_case["enabled"] = test_case["id"] in on
    return PipelineTestsConfig.model_validate(payload)


def _config_tree(root: Path, settings: PipelineTestsConfig) -> Path:
    """A copy of `config/` holding this pipeline-tests config, under `root/config`."""
    _copy_config(root / "config")
    (root / "config" / "pipeline-tests.json").write_text(settings.to_json(), encoding="utf-8")
    return root / "config"


def _write_the_settings(root: Path, settings: PipelineTestsConfig) -> None:
    """Only the file the test case runner reads, under `root/config`."""
    (root / "config").mkdir()
    (root / "config" / "pipeline-tests.json").write_text(settings.to_json(), encoding="utf-8")


def _recorded(
    root: Path, test_case: str, item_ids: Sequence[str], *, summary_status: str | None = "ok"
) -> None:
    """Write what one test case's work stage would have left under its folder.

    `summary_status` None is an article that stopped before the model - a refused
    download or a failed extraction - which `work` files with its article and its
    health row and no summary. "failed" is a call that came back unusable.
    """
    items = root / pipeline_test_case.TEST_CASES_ROOT / test_case / "run" / "items"
    items.mkdir(parents=True, exist_ok=True)
    for item_id in item_ids:
        (items / f"{item_id}.article.json").write_text("{}", encoding="utf-8")
        health = {"outcome": "ok", "code": None, "item_total_ms": 61000}
        if summary_status is None:
            health = {"outcome": "failed", "code": "http_client_error", "item_total_ms": 200}
        else:
            (items / f"{item_id}.summary.json").write_text(
                json.dumps({"status": summary_status, "summarize_ms": 1000}), encoding="utf-8"
            )
            if summary_status != "ok":
                health = {"outcome": "failed", "code": "schema_invalid", "item_total_ms": 61000}
        (items / f"{item_id}.health.json").write_text(json.dumps(health), encoding="utf-8")


def _report(root: Path, expected: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run the report the step runs, over a tree of test case results.

    The shipped bytes, not a copy of them (Guardrail #7). It prints a markdown
    table rather than `key=value` lines, so it is run rather than read.
    """
    assert REPORT_MODULE in _script(
        _step(_load_workflows()[WORKFLOW], REPORT_JOB, "name", REPORT_STEP), REPORT_STEP
    ), "the report step no longer calls the module this drives"
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / REPORT_MODULE), "--expected", " ".join(expected)],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_only_way_to_start_it_is_a_person_asking() -> None:
    """Dispatch and nothing else, and the form asks one question.

    A schedule would spend runner-hours on a workflow nobody is reading the
    result of, and a push or pull_request trigger would spend them per commit.

    The form asks which model to run, and nothing else. Every test case setting
    is read from config or drawn (Guardrail #6) - the addresses, the draw size,
    the shard size, the job bound, which test cases run, the slot counts, the
    windows. Which model is the one question config cannot answer, because the
    committed config names the incumbent by design.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    declared = _declared_dispatch_inputs(workflow)
    assert sorted(declared) == [CANDIDATE_INPUT], (
        "one input, and it names the model: every test case setting is read from config"
    )
    named = _mapping(declared[CANDIDATE_INPUT], f"{WORKFLOW} input {CANDIDATE_INPUT}")
    assert named.get("default") == "", (
        "empty is the default, so a dispatch that types nothing runs the configured model"
    )


def test_every_runner_of_every_enabled_test_case_is_a_job_of_its_own() -> None:
    """One job per runner, all at once, and the matrix is read off config.

    Speed is the point: the articles split into shards the way a production day
    is split across workers, and a dispatch takes as long as its slowest
    article. A runner that fails costs its own shards and nothing else, so the
    matrix never fails fast. The commit job beside them runs no test case and
    measures nothing; it exists so the write lands where no runner's
    permissions reach.
    """
    workflow = _load_workflows()[WORKFLOW]
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict) and list(jobs) == [
        PLAN_JOB,
        TEST_CASE_JOB,
        REPORT_JOB,
        COMMIT_JOB,
    ]

    runner = _job(workflow, TEST_CASE_JOB)
    assert _needs(workflow, TEST_CASE_JOB) == [PLAN_JOB], "every runner waits for the one plan"
    strategy = _mapping(runner.get("strategy"), "the runners' strategy")
    assert str(strategy.get("fail-fast")).lower() == "false", (
        "one runner that fails may not cancel the runners still reading their articles"
    )
    matrix = _mapping(strategy.get("matrix"), "the runners' matrix")
    assert set(matrix) == {"include"}, "the matrix is the list config produced, and only that"
    assert matrix["include"] == "${{ fromJSON(needs.plan.outputs.jobs) }}"
    assert runner.get("runs-on") == "ubuntu-latest"

    assert _needs(workflow, COMMIT_JOB) == [PLAN_JOB, TEST_CASE_JOB], "nothing commits early"
    for text in _strings(_job(workflow, COMMIT_JOB)):
        assert TEST_CASE_MODULE not in text, "the committing job runs no test case"


def test_the_job_bound_is_the_budget_config_declares() -> None:
    """The bound on one runner lives in config, so the number is written once.

    A literal in the YAML and a number in `config/pipeline-tests.json` would be
    two answers to one question, and the one an operator edits would be the one
    nothing reads.
    """
    runner = _job(_load_workflows()[WORKFLOW], TEST_CASE_JOB)
    assert runner.get("timeout-minutes") == str(_settings().budget_minutes)


def test_the_draw_happens_once_and_every_runner_reads_it() -> None:
    """The Oracle. One step opens the address list and every runner reads its answer.

    This is what makes the test cases read the same articles. A runner that drew
    its own would read different ones, and what one test case did could not be
    set beside what another did.

    Asserted by reading rather than by listing: every step in every job that
    calls the draw is discovered, and there must be exactly one.
    """
    workflow = _load_workflows()[WORKFLOW]
    drawing = [
        (job, step.get("name"))
        for job in (PLAN_JOB, TEST_CASE_JOB, REPORT_JOB, COMMIT_JOB)
        for step in _steps(workflow, job)
        if PICK_CALL in str(step.get("run") or "")
    ]
    assert drawing == [(PLAN_JOB, PICK_STEP)], f"one step draws, and it is {PICK_STEP!r}"

    pick = _step(workflow, PLAN_JOB, "name", PICK_STEP)
    assert '--seed "$PICK_SEED"' in _script(pick, PICK_STEP), "the draw is seeded, never arbitrary"
    assert "github.run_id" in str(pick.get("env")), (
        "the seed is the run id GitHub allocated, which nothing in the run can compute"
    )

    plan = _step(workflow, PLAN_JOB, "name", PLAN_STEP)
    assert "steps.pick.outputs.addresses" in str(plan.get("env"))
    assert "steps.pick.outputs.feeds" in str(plan.get("env"))
    names = [step.get("name") for step in _steps(workflow, PLAN_JOB)]
    assert names.index(PICK_STEP) < names.index(PLAN_STEP), "the draw comes before the plan"

    written = [
        (job, step.get("name"))
        for job in (PLAN_JOB, TEST_CASE_JOB, REPORT_JOB, COMMIT_JOB)
        for step in _steps(workflow, job)
        if PLAN_CALL in str(step.get("run") or "")
    ]
    assert written == [(PLAN_JOB, PLAN_STEP)], "one step mints the plan every runner shares"

    uploaded = [
        step
        for step in _steps(workflow, PLAN_JOB)
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
    ]
    assert [_mapping(step.get("with"), "upload")["name"] for step in uploaded] == [PLAN_ARTIFACT]
    taken = _step(workflow, TEST_CASE_JOB, "uses", "actions/download-artifact@v8")
    assert _mapping(taken.get("with"), "the plan download")["name"] == PLAN_ARTIFACT, (
        "every runner reads the plan the plan job wrote, and no other"
    )


def test_each_runner_runs_its_own_test_case_on_the_one_plan() -> None:
    """The matrix names the test case and the runner, and the step hands both on.

    Through `env`, never pasted into the program: the values come from committed
    config, but a value pasted into a `run:` body is text before it is a value.
    """
    workflow = _load_workflows()[WORKFLOW]
    step = _step(workflow, TEST_CASE_JOB, "name", RUN_STEP)
    body = _script(step, RUN_STEP)
    assert RUN_CALL in body
    assert '"$TEST_CASE" "$RUN_DATE" --runner "$RUNNER"' in body
    assert "${{" not in body, "the step pastes no expression into the program"
    env = _mapping(step.get("env"), "the run step's env")
    assert env["TEST_CASE"] == "${{ matrix.test_case }}"
    assert env["RUNNER"] == "${{ matrix.runner }}"
    assert env["RUN_DATE"] == "${{ needs.plan.outputs.date }}"
    assert env["LLAMA_CPP_BUILD"] == PIN_RELAYED, (
        "the build the run manifest stamps is the build the model block installed"
    )

    jobs = _step(workflow, PLAN_JOB, "name", JOBS_STEP)
    assert JOBS_CALL in _script(jobs, JOBS_STEP)
    declared = _mapping(_job(workflow, PLAN_JOB).get("outputs"), "the plan job's outputs")
    assert declared["jobs"] == "${{ steps.jobs.outputs.jobs }}"


def test_every_runner_serves_its_model_through_the_production_model_block() -> None:
    """The cache, fetch, digest check, start and health probe production runs, once.

    A runner that spelled those steps itself would be a second copy of how a
    model is served, and the copy this workflow used to carry had already lost
    the check that the server loaded the declared weights. The block reads this
    test case's own config root, so the slot count and the window it starts
    are the ones the test case declares, and the entry is then proven against
    the server before an article is read.
    """
    workflow = _load_workflows()[WORKFLOW]
    given = _action_call(workflow, TEST_CASE_JOB, MODEL_SERVER_ACTION)
    assert given["config_root"] == TEST_CASE_ROOT
    assert given["llama_cpp_build"] == PIN_RELAYED
    assert given["probe_url"] == "${{ env.MODEL_SERVER_PROBE }}"

    declared = _mapping(_job(workflow, PLAN_JOB).get("outputs"), "the plan job's outputs")
    assert declared[PIN_OUTPUT] == f"${{{{ steps.runtime.outputs.{PIN_OUTPUT} }}}}", (
        "the build every runner installs is read once, by the job every runner waits on"
    )
    assert _step(workflow, PLAN_JOB, "name", PIN_STEP).get("id") == "runtime"

    steps = [step.get("name") or step.get("uses") for step in _steps(workflow, TEST_CASE_JOB)]
    served = steps.index(MODEL_SERVER_ACTION)
    assert steps.index(TEST_CASE_CONFIG_STEP) < served, "the root the block reads is written first"
    assert served < steps.index(PROVE_STEP) < steps.index(RUN_STEP), (
        "the entry is proven against the running server, and before an article is read"
    )

    prove = _step(workflow, TEST_CASE_JOB, "name", PROVE_STEP)
    body = _script(prove, PROVE_STEP)
    assert PROVE_MODULE in body
    assert '--config-root "backend/var/test-cases/${TEST_CASE}/config"' in body
    assert _mapping(prove.get("env"), "prove env")["TEST_CASE"] == "${{ matrix.test_case }}"


def test_the_report_holds_every_enabled_test_case_to_the_drawn_items() -> None:
    """The runtime half of the Oracle, and it fails the run rather than warning.

    Reading the workflow proves the runners were HANDED one plan. It cannot
    prove they landed on it, so the report reads every runner's articles back
    against the item ids the plan job published; the tests below run it.
    """
    workflow = _load_workflows()[WORKFLOW]
    report = _step(workflow, REPORT_JOB, "name", REPORT_STEP)
    assert "needs.plan.outputs.item_ids" in str(report.get("env"))
    download = _step(workflow, REPORT_JOB, "uses", "actions/download-artifact@v8")
    taken = _mapping(download.get("with"), "the report's download")
    assert taken["pattern"] == "pipeline-tests-${{ github.run_id }}-*"
    assert str(taken["merge-multiple"]) == "true", "every runner's articles land in one tree"


def test_a_failed_runner_costs_its_own_shards_and_nothing_else() -> None:
    """The report and the commit still run when a runner fails.

    A runner that failed still measured what it reached, and the report is where
    the failure is named. Only a cancelled run, or a plan that never happened,
    stops them: without a plan there is nothing to read the runners against.
    """
    workflow = _load_workflows()[WORKFLOW]
    for job in (REPORT_JOB, COMMIT_JOB):
        condition = _normalize_condition(_job(workflow, job).get("if"), f"{job} condition")
        assert "!cancelled()" in condition, f"{job} gives up when a runner fails"
        assert "needs.plan.result == 'success'" in condition, f"{job} runs without a plan"
        assert "test-case" not in condition, f"{job} waits on every runner succeeding"


#: A config with every declared test case switched on, which is what the report
#: tests read against. The committed config switches most of them off.
def _everything_on() -> PipelineTestsConfig:
    settings = _settings()
    return _switched(settings, on=[test_case.id for test_case in settings.test_cases])


def test_the_report_names_a_test_case_that_recorded_nothing_and_prints_the_rest(
    tmp_path: Path,
) -> None:
    """A test case that produced nothing is a census line, not a broken comparison.

    Its runners have already failed, their jobs are red and the run is red with
    them. What the report owes is the name: a table that quietly dropped the row
    would leave a reader counting test cases to notice one was missing.
    """
    settings = _everything_on()
    _config_tree(tmp_path, settings)
    expected = ["ai-0000000001", "world-0000000002"]
    test_cases = [test_case.id for test_case in settings.test_cases]
    for test_case in test_cases[:-1]:
        _recorded(tmp_path, test_case, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr.strip()
    assert f"these test cases produced nothing: {test_cases[-1]}" in completed.stdout
    assert f"| {test_cases[-1]} | 0 | 0 | 0 | nothing recorded |" in completed.stdout
    for test_case in test_cases[:-1]:
        assert f"| {test_case} | 2 | 2 | 61 | - |" in completed.stdout, (
            "a test case that ran is still reported beside the one that did not"
        )


def test_the_report_refuses_a_test_case_that_read_other_articles(tmp_path: Path) -> None:
    """An article the draw did not choose means a runner read another plan.

    Nothing that runner reports belongs to this dispatch, and the table is
    plausible either way, so the run fails. A test case that recorded nothing
    must not be able to trip it.
    """
    settings = _everything_on()
    _config_tree(tmp_path, settings)
    expected = ["ai-0000000001", "world-0000000002"]
    test_cases = [test_case.id for test_case in settings.test_cases]
    for test_case in test_cases[:-1]:
        _recorded(tmp_path, test_case, expected)
    _recorded(tmp_path, test_cases[-1], ["ai-0000000001", "world-0000000003"])

    completed = _report(tmp_path, expected)
    assert completed.returncode != 0, "an article the draw did not choose fails the run"
    assert "recorded articles the draw did not choose" in completed.stderr
    assert f"{test_cases[-1]} recorded world-0000000003" in completed.stderr


@pytest.mark.parametrize(
    ("summary_status", "code"),
    [(None, "http_client_error"), ("failed", "schema_invalid")],
    ids=["every article stopped before the model", "every call came back unusable"],
)
def test_the_report_refuses_a_test_case_that_got_no_article_summarized(
    summary_status: str | None, code: str, tmp_path: Path
) -> None:
    """Its articles all failed before a usable answer, so it said nothing about the model.

    That used to end green: a fetch that failed is the pipeline degrading one
    item, which is correct for a production day and wrong for a model check,
    where it reads as a pass for a model that was never asked anything. The test
    case is named, and the one beside it that did get its articles summarized
    is not.
    """
    settings = _everything_on()
    _config_tree(tmp_path, settings)
    expected = ["ai-0000000001", "world-0000000002"]
    first, *rest = [test_case.id for test_case in settings.test_cases]
    _recorded(tmp_path, first, expected, summary_status=summary_status)
    for test_case in rest:
        _recorded(tmp_path, test_case, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode != 0
    assert "no article came back summarized" in completed.stderr
    named = completed.stderr.rsplit(":", 1)[-1]
    assert first in named, "the test case that summarized nothing is named"
    for test_case in rest:
        assert test_case not in named, f"{test_case} summarized its articles"
    assert f"| {first} | 2 | 0 | " in completed.stdout
    assert code in completed.stdout, "the report says why each one failed"


def test_the_report_names_the_articles_a_failed_runner_never_filed(tmp_path: Path) -> None:
    """A runner that failed files no run, so its articles are missing, and named.

    Its own job is already red, so the report does not fail twice: the article
    the other runner did summarize still says the model walked the path.
    """
    settings = _settings()
    _config_tree(tmp_path, settings)
    expected = ["ai-0000000001", "world-0000000002"]
    enabled = [test_case.id for test_case in settings.test_cases if test_case.enabled]
    for test_case in enabled:
        _recorded(tmp_path, test_case, expected[:1])

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr
    assert f"{enabled[0]} is missing world-0000000002" in completed.stdout
    assert f"| {enabled[0]} | 1 | 1 | 61 | - |" in completed.stdout


def test_the_report_leaves_a_switched_off_test_case_out_of_the_table(tmp_path: Path) -> None:
    """Off is a decision in config, not a failure, so it is named once and not measured."""
    settings = _settings()
    _config_tree(tmp_path, settings)
    expected = ["ai-0000000001"]
    enabled = [test_case.id for test_case in settings.test_cases if test_case.enabled]
    off = [test_case.id for test_case in settings.test_cases if not test_case.enabled]
    assert off, "the committed config switches nothing off, so this test checks nothing"
    for test_case in enabled:
        _recorded(tmp_path, test_case, expected)

    completed = _report(tmp_path, expected)
    assert completed.returncode == 0, completed.stderr
    assert f"switched off in config/pipeline-tests.json: {', '.join(off)}" in completed.stdout
    for test_case in off:
        assert f"| {test_case} |" not in completed.stdout
    assert "produced nothing" not in completed.stdout


def test_it_publishes_nothing_a_reader_sees_and_writes_only_the_trial_roots() -> None:
    """A test workflow that could write the site would be a second publisher.

    It does commit, and that is the whole of the write: one job appends what the
    test cases measured under their own trial roots, which no console page
    reads. Everything else lives under `backend/var/`, which is never committed,
    and leaves as an artifact.
    """
    workflow = _load_workflows()[WORKFLOW]
    assert workflow.get("permissions") == {"contents": "read"}, (
        "the file-level default is read, so a job that writes has to say so itself"
    )
    for job in (PLAN_JOB, TEST_CASE_JOB, REPORT_JOB):
        assert _job(workflow, job).get("permissions") == {"contents": "read"}, (
            f"{job} holds no write"
        )
    assert _job(workflow, COMMIT_JOB).get("permissions") == {"contents": "write"}, (
        "the committing job takes the write, and takes nothing else with it"
    )

    for text in _strings(workflow):
        assert "frontend/public" not in text, "a test dispatch publishes nothing"

    upload = _step(workflow, TEST_CASE_JOB, "name", "Upload what the test case produced")
    with_block = _mapping(upload.get("with"), "the runner's upload")
    assert str(with_block.get("path")).startswith("backend/var/")
    assert with_block.get("retention-days") == "90"
    assert "${{ matrix.test_case }}-${{ matrix.runner }}" in str(with_block.get("name")), (
        "two runners of one test case upload two artifacts, never one overwriting the other"
    )


#: The folder the ledger module gathers into and the commit job downloads into.
LEDGER_TREE: str = "backend/var/trial-ledgers"

#: A path under `backend/var/` as a step spells it. It ends where a path ends in
#: a shell line: at whitespace, a quote or a closing bracket.
SCRATCH_PATH: re.Pattern[str] = re.compile(r"backend/var/[^\s\"'`)]*")


def test_every_scratch_path_the_workflow_names_is_under_one_declared_folder() -> None:
    """The test case folder and the plan are spelled once in Python, and the workflow is read against them.

    The three test case programs import one constant,
    `pipeline_test_case.TEST_CASES_ROOT`, and the runner and the plan writer
    agree on `pipeline_test_case.PLAN`. The workflow cannot import either, so a
    step still spelling an old folder would pass every other test and fail only
    on a real dispatch.
    """
    test_case_folder = pipeline_test_case.TEST_CASES_ROOT.as_posix()
    plan_folder = pipeline_test_case.PLAN.parent.as_posix()
    folders = (test_case_folder, plan_folder, SCRATCH_CONFIG, LEDGER_TREE)
    named = {
        found.rstrip("/")
        for text in _strings(_load_workflows()[WORKFLOW])
        for found in SCRATCH_PATH.findall(text)
    }

    stray = sorted(
        path
        for path in named
        if not any(path == folder or path.startswith(f"{folder}/") for folder in folders)
    )
    assert not stray, f"these paths sit under none of the declared scratch folders: {stray}"
    assert any(path.startswith(f"{test_case_folder}/") for path in named), (
        f"no step names a path under {test_case_folder}, so this test is checking nothing"
    )


def test_the_commit_job_stages_the_declared_trial_roots_and_nothing_wider() -> None:
    """Every path handed to `git add` comes from committed config, not from a body.

    The staged paths are printed by `pipeline_test_ledgers place`, which reads
    the declared test cases and names one root each. A path spelled in the
    workflow would be a second copy of the naming rule, and a wider one would
    let this job push a ledger the daily run owns.
    """
    workflow = _load_workflows()[WORKFLOW]
    body = _script(_step(workflow, COMMIT_JOB, "name", COMMIT_STEP), "the commit step")

    assert f"{LEDGER_MODULE} place" in body, "the roots to stage are printed, never spelled"
    assert " ".join(COMMIT_PROGRAM_CALL) in body, "it commits through the shared program"
    staged = re.search(rf"{re.escape(COMMIT_PROGRAM_CALL[1])} (?P<paths>.+)", body)
    assert staged is not None
    assert staged["paths"].strip() == '"${TRIAL_ROOTS[@]}"', (
        f"the commit step stages a path of its own: {staged['paths']}"
    )

    roots = [test_case.trial_state_dirname for test_case in _settings().test_cases]
    assert len(set(roots)) == len(roots), (
        "two test cases share a trial root, so one overwrites the other"
    )
    for root in roots:
        assert root.startswith(f"{TRIAL_STATE_PREFIX}-"), (
            f"{root} is not under the prefix the bench and the qualification already use"
        )


def test_trial_gather_reads_the_planned_day_only() -> None:
    step = _step(
        _load_workflows()[WORKFLOW], TEST_CASE_JOB, "name", "Gather the ledgers the test case wrote"
    )
    body = _script(step, "the ledger gather step")
    assert f"{LEDGER_MODULE} gather" in body
    assert '--day "$RUN_DATE"' in body
    env = _mapping(step.get("env"), "the ledger gather environment")
    assert env["RUN_DATE"] == "${{ needs.plan.outputs.date }}"


#: How a job condition reads another job: `needs.<id>` or `needs['<id>']`, then
#: optionally the output or the result it takes.
NEEDS_REFERENCE: re.Pattern[str] = re.compile(
    r"needs(?:\['(?P<indexed>[^']+)'\]|\.(?P<dotted>[A-Za-z0-9_-]+))"
    r"(?:\.outputs\.(?P<output>[A-Za-z0-9_-]+))?"
)


def test_every_job_reads_only_jobs_it_waits_on_and_outputs_they_declare() -> None:
    """A wrong job name in a condition skips a job with no error.

    GitHub reads an output of a job that does not exist, or one the job does not
    declare, as an empty string. So every job another job reads is one it waits
    on and one the workflow has, and every output it reads is one that job
    declares.
    """
    workflow = _load_workflows()[WORKFLOW]
    jobs = _mapping(workflow.get("jobs"), f"{WORKFLOW} jobs")
    for reader in jobs:
        needed = _needs(workflow, reader)
        for text in _strings(_job(workflow, reader)):
            for found in NEEDS_REFERENCE.finditer(text):
                job = found["indexed"] or found["dotted"]
                assert found["indexed"] or "-" not in job, (
                    f"{found[0]} reads a hyphenated job id in the dotted form; use needs['{job}']"
                )
                assert job in jobs, f"{reader}: {found[0]} reads a job this workflow does not have"
                assert job in needed, f"{reader}: {found[0]} reads a job it does not wait on"
                if found["output"]:
                    declared = _mapping(_job(workflow, job).get("outputs"), f"{job} outputs")
                    assert found["output"] in declared, (
                        f"{reader}: {found[0]} reads an output {job} does not declare"
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
    assert settings["pattern"] == "pipeline-tests-ledgers-${{ github.run_id }}-*"
    assert str(settings["merge-multiple"]) == "true"
    assert str(settings["path"]).startswith("backend/var/"), (
        "a download unpacked over state/ would be read together with rows already committed"
    )
    assert steps.index(download) < names.index(CHECK_STEP), (
        "the check reads what arrived, so it runs after the download"
    )


#: The one writer the downloaded tree carries, spelled through the producers a
#: test case run uses. `GITHUB_RUN_ID` is GitHub's eleven-digit execution number,
#: so the run id is the project's `<date>-<execution>` rather than that number
#: alone.
TEST_CASE_DATE: str = "2026-09-22"
TEST_CASE_RUN_ID: str = f"{TEST_CASE_DATE}-40000000001"
TEST_CASE_ATTEMPT: int = 1
TEST_CASE_JOB_KIND: ServerJob = ServerJob.WORK
TEST_CASE_SHARD: int = 0
TEST_CASE_DAY_PATH: str = TEST_CASE_DATE.replace("-", "/")
TEST_CASE_WRITER: str = ledger.segment_name(
    run_id=TEST_CASE_RUN_ID,
    attempt=TEST_CASE_ATTEMPT,
    job=TEST_CASE_JOB_KIND,
    shard=TEST_CASE_SHARD,
)
TEST_CASE_TRACE: str = ledger.segment_name(
    run_id=TEST_CASE_RUN_ID,
    attempt=TEST_CASE_ATTEMPT,
    job=TEST_CASE_JOB_KIND,
    shard=TEST_CASE_SHARD,
    suffix=traces.TRACE_SUFFIX,
)


def _a_downloaded_tree(root: Path, *, test_case: str) -> Path:
    """One test case's ledgers as the artifact carries them: a day shard and a trace.

    Both paths are built by the producers a test case run uses, so a grammar that
    moves takes this fixture with it rather than leaving it green against a
    shape nothing writes.
    """
    row = FeedHealthRow.model_validate(
        {
            "date": TEST_CASE_DATE,
            "run_id": TEST_CASE_RUN_ID,
            "feed_id": "example-feed",
            "checked_at": f"{TEST_CASE_DATE}T06:00:00Z",
            "outcome": "ok",
            "status": 200,
            "items": 2,
        }
    )
    ledger.write_segment(
        root / test_case,
        LedgerName.FEED_HEALTH,
        [row],
        run_id=TEST_CASE_RUN_ID,
        attempt=TEST_CASE_ATTEMPT,
        job=TEST_CASE_JOB_KIND,
        shard=TEST_CASE_SHARD,
    )
    trace = traces.committed_trace_path(
        root / test_case,
        run_id=TEST_CASE_RUN_ID,
        attempt=TEST_CASE_ATTEMPT,
        job=TEST_CASE_JOB_KIND,
        shard=TEST_CASE_SHARD,
    )
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text('{"kind":"span","name":"item","duration_ms":1}\n', encoding="utf-8")
    return root


def test_the_check_passes_the_two_shapes_a_test_case_really_writes(tmp_path: Path) -> None:
    """A day shard and a trace, filed under a declared test case's own trial root."""
    test_case = _settings().test_cases[0]
    tree = _a_downloaded_tree(tmp_path / "trial-ledgers", test_case=test_case.trial_state_dirname)

    assert (
        pipeline_test_ledgers.refusals(tree, roots=frozenset({test_case.trial_state_dirname})) == []
    )


def test_the_check_has_nothing_to_refuse_when_nothing_arrived(tmp_path: Path) -> None:
    """A dispatch whose runners all failed early uploads nothing, and that is not a refusal."""
    assert pipeline_test_ledgers.refusals(tmp_path / "never-made", roots=frozenset()) == []


@pytest.mark.parametrize(
    ("relative", "because"),
    [
        (
            f"a-tenant/feed-health/{TEST_CASE_DAY_PATH}/{TEST_CASE_WRITER}",
            "no declared test case",
        ),
        (
            "{test_case}/items/ai-0000000001.summary.json",
            "a ledger a test case run does not write",
        ),
        (f"{{test_case}}/summaries/{TEST_CASE_DAY_PATH}/{TEST_CASE_WRITER}", "no such ledger"),
        (
            f"{{test_case}}/traces/{TEST_CASE_DAY_PATH}/{TEST_CASE_TRACE}",
            "a line that is not a span",
        ),
    ],
)
def test_the_check_refuses_what_no_test_case_producer_wrote(
    tmp_path: Path, relative: str, because: str
) -> None:
    """The oracle for the control. A check nothing can fail is not a control.

    Every row here is a path an artifact could carry and a test case producer
    could not: a directory no config declares, a ledger no test case run writes,
    a ledger outside the closed set, and a payload that does not read back. The
    last one is why the check opens the files rather than matching their names.
    """
    test_case = _settings().test_cases[0]
    tree = _a_downloaded_tree(tmp_path / "trial-ledgers", test_case=test_case.trial_state_dirname)
    path = tree / relative.format(test_case=test_case.trial_state_dirname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a span\n", encoding="utf-8")

    refused = pipeline_test_ledgers.refusals(tree, roots=frozenset({test_case.trial_state_dirname}))

    assert refused, f"the check let through {because}"


@pytest.mark.parametrize("wrote", [True, False])
def test_the_gather_verb_prints_nothing_a_step_could_mistake_for_output(
    tmp_path: Path, wrote: bool
) -> None:
    """Gather talks to a person on stderr and to nothing on stdout.

    Nothing reads a step output of it any more, and a line on stdout is the one
    thing a later edit could append to `$GITHUB_OUTPUT` by habit - where a line
    that is not `key=value` fails the step and loses the push.
    """
    test_case = _settings().test_cases[0]
    state = tmp_path / "state"
    if wrote:
        _a_downloaded_tree(state, test_case=test_case.trial_state_dirname)
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
    assert done.stdout == ""
    if wrote:
        assert test_case.trial_state_dirname in done.stderr, "a person still reads what arrived"
    else:
        assert "nothing to push" in done.stderr, "a dispatch that gathered nothing says so"


def test_every_declared_test_case_is_placed_whether_or_not_it_wrote_anything(
    tmp_path: Path,
) -> None:
    """`git add` aborts on a path the checkout does not hold, and takes the step with it.

    A dispatch that lost a test case still has to hand the commit script paths it
    can stage. An empty directory git cannot see costs nothing; a missing one
    costs the whole push, including the test case that did produce rows.
    """
    test_cases = _settings().test_cases
    tree = _a_downloaded_tree(
        tmp_path / "trial-ledgers", test_case=test_cases[0].trial_state_dirname
    )
    state = tmp_path / "state"

    staged = pipeline_test_ledgers.place(
        tree, state, roots=[test_case.trial_state_dirname for test_case in test_cases]
    )

    assert len(staged) == len(test_cases)
    for test_case in test_cases:
        assert (state / test_case.trial_state_dirname).is_dir()
    assert ledger.tree_root(
        state / test_cases[0].trial_state_dirname, LedgerName.FEED_HEALTH
    ).is_dir()


def test_a_config_with_every_test_case_switched_off_is_refused() -> None:
    """A dispatch that runs nothing is a mistake, and the file is where it is made."""
    settings = _settings()
    payload = settings.model_dump(mode="json")
    for test_case in payload["test_cases"]:
        test_case["enabled"] = False

    with pytest.raises(ValidationError, match="no test case is enabled"):
        PipelineTestsConfig.model_validate(payload)


def test_one_enabled_test_case_is_enough() -> None:
    """Checking that a model walks the production path compares it with nothing."""
    settings = _settings()
    first = settings.test_cases[0].id
    assert [test_case.id for test_case, _ in _switched(settings, on=[first]).runs()] != []


@pytest.mark.parametrize(
    ("articles", "per_shard", "slots", "expected"),
    [
        (2, 1, 1, [(0,), (1,)]),
        (2, 1, 2, [(0, 1)]),
        (3, 1, 2, [(0, 1), (2,)]),
        (1, 1, 2, [(0,)]),
        (4, 2, 1, [(0,), (1,)]),
    ],
)
def test_a_test_case_takes_one_runner_for_every_server_its_shards_need(
    articles: int, per_shard: int, slots: int, expected: list[tuple[int, ...]]
) -> None:
    """Shards are the articles split the production way; a runner holds `slots` of them.

    One article a shard and one slot a server is every article on its own
    machine, which is the fastest a dispatch can be. Two slots put two shards on
    one server at once, which is the only way the server's second slot is ever
    asked for anything - and one article cannot fill two slots, so it gets one.
    """
    settings = _settings()
    payload = settings.model_dump(mode="json")
    payload["articles_a_dispatch"] = articles
    payload["articles_a_shard"] = per_shard
    payload["test_cases"][0].update({"enabled": True, "n_parallel": slots})
    reshaped = PipelineTestsConfig.model_validate(payload)
    test_case = reshaped.test_cases[0]

    held = [reshaped.shards_on(test_case, runner) for runner in range(reshaped.runners(test_case))]
    assert held == expected
    assert sorted(shard for shards in held for shard in shards) == list(
        range(reshaped.shard_count())
    ), "every shard is on exactly one runner"


def test_the_jobs_verb_lists_one_entry_for_every_runner_of_every_enabled_test_case(
    tmp_path: Path,
) -> None:
    """Run the shipped bytes against the committed config and against one that switches all on."""
    for settings in (_settings(), _everything_on()):
        root = tmp_path / str(len(list(tmp_path.iterdir())))
        _config_tree(root, settings)
        published = _module_outputs(["jobs"], cwd=root, module=TEST_CASE_MODULE)
        listed = json.loads(published[pipeline_test_case.JOBS_KEY])
        assert listed == [
            {"test_case": test_case.id, "runner": runner} for test_case, runner in settings.runs()
        ]
        switched_off = {test_case.id for test_case in settings.test_cases if not test_case.enabled}
        assert not switched_off & {entry["test_case"] for entry in listed}, (
            "a test case that is off starts no job"
        )


def test_the_address_list_can_still_answer_a_draw() -> None:
    """Twenty candidates at least, all distinct, each naming a feed we really read.

    A candidate on a feed `config/sources.json` no longer carries is an address
    the run would have to invent a vertical and a tier for. The plan step reads
    both off the feed, so an orphan candidate is a `KeyError` in the plan job
    rather than a failure here.

    The live list, never the file's text. The dispatch builds its map from
    `settings.sources.feeds`, so a candidate whose feed has moved to `retired`
    is that same `KeyError` while a search of the whole file still finds the id
    on the tombstone shelf.
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
    """The typo is a hand edit to this file, so this is where it has to land."""
    settings = _settings()
    payload = settings.model_dump(mode="json")
    payload["candidates"][0]["title"] = headline

    with pytest.raises(ValidationError):
        PipelineTestsConfig.model_validate(payload)


def test_the_draw_is_decided_by_the_seed_and_by_nothing_else() -> None:
    """Same seed, same articles, anywhere. Different seed, different articles."""
    settings = _settings()
    once = settings.draw("34852763827")
    assert once == settings.draw("34852763827")
    assert len(once) == settings.articles_a_dispatch
    assert len({candidate.url for candidate in once}) == len(once)

    seeds = {tuple(c.url for c in settings.draw(str(seed))) for seed in range(40)}
    assert len(seeds) > 1, "the seed has to move the articles, or the list is decorative"


def test_the_pick_step_publishes_the_articles_the_plan_step_asks_for() -> None:
    """Run the shipped bytes, do not read them (Guardrail #7).

    The two steps meet through three output names. A step that printed `urls=`
    while the next one read `addresses=` would fail with an empty plan and no
    article fetched.
    """
    workflow = _load_workflows()[WORKFLOW]
    seed = "34852763827"
    assert PICK_CALL in _script(_step(workflow, PLAN_JOB, "name", PICK_STEP), PICK_STEP)
    published = _module_outputs(["pick", "--seed", seed], cwd=REPO_ROOT)

    assert published["seed"] == seed
    drawn = _settings().draw(seed)
    assert published["addresses"] == " ".join(candidate.url for candidate in drawn)
    assert published["feeds"] == " ".join(candidate.source_id for candidate in drawn)


@pytest.fixture(scope="module")
def written_test_cases(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Every test case's config root, written once by the shipped generator.

    Two tests read the same output, so the program runs once for the module.
    Nothing here is written to after the run.
    """
    root = tmp_path_factory.mktemp("test-cases")
    scratch = _scratch(root, models_file=None)
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = pipeline_test_case_config.main(
            ["--config-root", scratch.as_posix(), "--test-cases-root", (root / "out").as_posix()]
        )
    assert code == 0
    return {
        key: Path(value)
        for key, value in (line.split("=", 1) for line in printed.getvalue().splitlines())
    }


def test_every_test_case_config_the_workflow_writes_loads(
    written_test_cases: dict[str, Path],
) -> None:
    """Every declared test case's config root survives `config.load`, switched on or not.

    The work stage and the argv builder both open it. A test case that wrote a
    knob outside its schema would fail on the runner after the weights were
    fetched - and a test case that is off today would fail the day somebody
    switched it on, which is the worst day to find out.

    Cut from the scratch root the step names, not from `config/`, so this drives
    the route a candidate dispatch really takes.
    """
    workflow = _load_workflows()[WORKFLOW]
    test_case_config = _script(
        _step(workflow, TEST_CASE_JOB, "name", TEST_CASE_CONFIG_STEP), "test case config"
    )
    assert TEST_CASE_CONFIG_MODULE in test_case_config
    assert f"--config-root {SCRATCH_CONFIG}" in test_case_config, (
        "the test cases are cut from the scratch copy, so a candidate reaches every one"
    )
    written = written_test_cases

    settings = _settings()
    assert sorted(written) == sorted(test_case.id for test_case in settings.test_cases)
    for test_case in settings.test_cases:
        loaded = config.load(written[test_case.id])
        assert loaded.app.summarize.asks_for_a_visual_plan is test_case.asks_for_a_visual_plan
        if not test_case.asks_for_a_visual_plan:
            assert loaded.app.visuals.enabled_kinds == [], "no picture is reachable"
        served = loaded.models.summarizer.server
        committed = config.load(CONFIG_DIR).models.summarizer.server
        assert setting(served, "n_parallel") == (
            test_case.n_parallel or setting(committed, "n_parallel")
        )
        assert window(served) == (test_case.n_ctx or window(committed))


def test_each_test_case_writes_its_own_trial_root(written_test_cases: dict[str, Path]) -> None:
    """Every test case its own root, and no two of them share a path.

    The dispatch runs one plan, so every test case shares a run id, a job and an
    attempt, and two test cases share each shard number. Those fields are the
    whole of a writer's filename, so without a root of its own the last test case
    to write would be the only one anybody could read.

    Read out of the config each test case really runs on, not out of the helper:
    the helper agreeing with itself says nothing about what `work` opens.
    """
    roots = {
        test_case_id: config.load(written).app.run.trial_state_dirname
        for test_case_id, written in written_test_cases.items()
    }
    declared = {test_case.id: test_case.trial_state_dirname for test_case in _settings().test_cases}

    assert len(set(roots.values())) == len(roots), f"two test cases share a trial root: {roots}"
    for test_case_id, root in roots.items():
        assert root == declared[test_case_id]
        assert root.startswith(f"{TRIAL_STATE_PREFIX}-"), (
            f"{root} is outside the prefix the bench and the qualification already use"
        )


def test_a_parallel_test_case_keeps_the_window_the_gate_admits_articles_against() -> None:
    """A slot count without a window beside it is a test of a smaller window.

    llama-server divides the window it is given between its slots, so two slots
    on the committed number halve what each one holds - and the sequence gate
    still admits articles against the config number. The test case would then
    refuse long articles and read as a concurrency result.
    """
    committed = config.load(CONFIG_DIR).models.summarizer.server
    for test_case in _settings().test_cases:
        if test_case.n_parallel is None or test_case.n_parallel == (
            setting(committed, "n_parallel") or 1
        ):
            continue
        assert test_case.n_ctx is not None, (
            f"{test_case.id} moves the slot count and not the window"
        )
        assert test_case.n_ctx >= window(committed) * test_case.n_parallel, (
            f"{test_case.id} leaves each slot less than the gate admits articles against"
        )


def test_the_plan_step_writes_a_plan_the_work_stage_can_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one payload every runner reads, built by the shipped program.

    `RunPlan` refuses a list whose desk counts disagree with its items, and the
    program builds those counts itself because nothing read a feed. Asserting
    the shape by eye is how that is found on the runner instead of here.
    """
    seed = "34852763827"
    drawn = _settings().draw(seed)

    # The step reads the committed config in place and writes under the working
    # folder, so nothing is copied and the program runs in this process.
    monkeypatch.chdir(tmp_path)
    code = pipeline_draw.main(
        [
            "--config-root",
            CONFIG_DIR.as_posix(),
            "plan",
            "--addresses",
            " ".join(candidate.url for candidate in drawn),
            "--feeds",
            " ".join(candidate.source_id for candidate in drawn),
            "--execution",
            seed,
        ]
    )
    assert code == 0
    published = dict(
        line.split("=", 1) for line in capsys.readouterr().out.splitlines() if "=" in line
    )

    written = tmp_path / pipeline_test_case.PLAN
    plan = RunPlan.from_json(read_text(written))
    assert plan.run_id == f"{published['date']}-{seed}"
    assert [item.source_url for item in plan.items] == [c.url for c in drawn]
    assert [item.title for item in plan.items] == [c.title for c in drawn], (
        "a planned item with no headline is refused by extract, so every runner reads zero items"
    )
    assert published["item_ids"] == " ".join(item.item_id for item in plan.items)
    assert plan.feeds_read == 0, "this plan came off a config list, so no feed was asked"


def _ran_a_test_case(
    tmp_path: Path, argv: list[str], settings: PipelineTestsConfig | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the shipped test case runner against a fixture tree (Guardrail #7).

    A fixture tree rather than the committed one, because what is being read is
    the exit code and the exit code is the same for two articles as for none
    (CLAUDE.md section 13).
    """
    if not (tmp_path / "config").exists():
        _write_the_settings(tmp_path, settings or _settings())
    return subprocess.run(
        [sys.executable, str(TEST_CASE_RUNNER), *argv],
        cwd=tmp_path,
        env={**_isolated_env(tmp_path), "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        check=False,
    )


def _enabled_id() -> str:
    return next(test_case.id for test_case in _settings().test_cases if test_case.enabled)


def _switched_off_id() -> str:
    return next(test_case.id for test_case in _settings().test_cases if not test_case.enabled)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "usage:"),
        (["run"], "usage:"),
        (["run", "{enabled}"], "usage:"),
        (["run", "not-a-test-case", "2026-09-14"], "unknown test case"),
        (["run", "{off}", "2026-09-14"], "is switched off"),
        (["run", "{enabled}", "2026-09-14", "--runner", "7"], "holds no shard"),
    ],
)
def test_the_test_case_runner_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    """Run it, do not read it (Guardrail #7).

    A step passes a test case id and a runner as bare strings. A typo would
    otherwise run the committed config under another test case's name, and a
    test case that is switched off would run because somebody asked for it by
    hand.
    """
    (tmp_path / pipeline_test_case.TEST_CASES_ROOT / _enabled_id() / "config").mkdir(parents=True)
    words = [word.format(enabled=_enabled_id(), off=_switched_off_id()) for word in argv]
    completed = _ran_a_test_case(tmp_path, words)
    assert completed.returncode == 2
    assert message in completed.stderr


def test_the_test_case_runner_refuses_to_run_without_the_plan_the_test_cases_share(
    tmp_path: Path,
) -> None:
    """A test case with no plan would summarize nothing and say so quietly.

    `idhazh work` with an absent plan is a failure four steps later about a file
    a reader of the log has to go and find. This one names what is missing and
    which job writes it.
    """
    (tmp_path / pipeline_test_case.TEST_CASES_ROOT / _enabled_id() / "config").mkdir(parents=True)
    completed = _ran_a_test_case(tmp_path, ["run", _enabled_id(), "2026-09-14"])
    assert completed.returncode == 2
    assert "no plan to run" in completed.stderr


def test_a_test_case_whose_pipeline_failed_is_not_reported_as_a_call_it_could_not_serve(
    tmp_path: Path,
) -> None:
    """The other half of the exit-code contract.

    `2` says this program was asked for something it cannot serve. A pipeline
    that ran and failed returns its own code, so a person reading the run page
    tells a typo in a test case id from a test case that really failed. Driven by
    handing the pipeline a config root with nothing in it, which is a real
    failure of the real program rather than a stub that returns a number. One
    article is one shard, so the failure costs one `work` and one `record`
    process and not two of each.

    The half-written run goes with it: a test case that failed leaves no `run`
    directory for the report to read as a result.
    """
    test_case_root = tmp_path / pipeline_test_case.TEST_CASES_ROOT / _enabled_id()
    (test_case_root / "config").mkdir(parents=True)
    plan = tmp_path / pipeline_test_case.PLAN
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")

    one_shard = PipelineTestsConfig.model_validate(
        {**_settings().model_dump(mode="json"), "articles_a_dispatch": 1}
    )
    assert one_shard.shard_count() == 1
    completed = _ran_a_test_case(tmp_path, ["run", _enabled_id(), "2026-09-14"], one_shard)
    assert completed.returncode != 0, "a failed pipeline fails the step that ran it"
    assert completed.returncode != 2, (
        "2 is reserved for a call this program cannot serve, so a failed "
        f"pipeline may not spell it: {completed.stderr}"
    )
    assert not (test_case_root / "run").exists(), (
        "nothing is filed under a test case that did not finish"
    )


def _scratch(tmp_path: Path, *, models_file: str | None) -> Path:
    """The scratch config root the composite action builds, built the same way.

    The named config inputs are copied and the shipped program moves the pointer, so a
    test that passes here is a test of the bytes the action runs (Guardrail #7).
    `None` means an empty dispatch, which is the committed pointer.
    """
    scratch = tmp_path / "backend" / "var" / "candidate-config"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    _copy_config(scratch, models_file=models_file)
    named = models_file or json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    candidate_pointer.point_at(named, scratch=scratch, trial_state=TRIAL_STATE)
    return scratch


def test_a_dispatch_that_names_nothing_runs_the_model_config_already_names() -> None:
    """The empty form is the old behaviour, and the program is what says so.

    The input exists to check a candidate. It may not change what a dispatch
    that types nothing runs.
    """
    empty = dict(
        row.split("=", 1) for row in model_refs.trial_rows(CONFIG_DIR, "", prefix="candidate_")
    )
    configured = dict(row.split("=", 1) for row in model_refs.pinned_rows(CONFIG_DIR))

    pointer = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    assert empty["candidate_models_file"] == pointer
    for field in model_refs.CONFIGURED_FIELDS:
        assert empty[f"candidate_{field}"] == configured[f"summarizer_{field}"], field


def test_a_named_candidate_moves_one_line_and_leaves_the_committed_config_alone(
    tmp_path: Path,
) -> None:
    """One line moves, and it is the line a swap would later move.

    A dispatch that edited `config/` would leave the checkout it ran on
    disagreeing with the tree it was cut from, and every control this workflow
    holds fixed - the prompt, the schema, the sampler, the window, the
    truncation cap - is the committed one only because the copy differs by that
    one line and nothing else.
    """
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    named = "models/fixture-candidate.json"

    scratch = _scratch(tmp_path, models_file=named)
    written = json.loads(read_text(scratch / "idhazh.json"))

    assert written["models_file"] == named
    assert written["run"]["trial_state_dirname"] == TRIAL_STATE
    moved = {key for key in set(committed) | set(written) if committed.get(key) != written.get(key)}
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
    build = _step(workflow, TEST_CASE_JOB, "uses", CANDIDATE_ACTION)
    with_block = _mapping(build.get("with"), "the candidate action")
    assert with_block.get("models_file") == "${{ needs.plan.outputs.models_file }}"
    assert with_block.get("trial_state") == TRIAL_STATE, (
        "the ledgers this dispatch writes land off the production state root"
    )
    declared = _mapping(_job(workflow, PLAN_JOB).get("outputs"), "the plan job's outputs")
    assert declared["models_file"] == "${{ steps.models.outputs.candidate_models_file }}", (
        "the file every runner serves is the one the plan job resolved and proved"
    )

    for body in _run_bodies(workflow):
        for line in body.splitlines():
            if line.lstrip().startswith("#"):
                continue
            assert '"config/idhazh.json"' not in line, line
            assert 'Path("config")' not in line, line

    steps = [step.get("name") or step.get("uses") for step in _steps(workflow, TEST_CASE_JOB)]
    assert steps.index(build.get("name")) < steps.index(TEST_CASE_CONFIG_STEP), (
        "every test case is cut from the copy, so the copy has to exist first"
    )


def test_the_pin_verb_prints_the_build_the_model_block_reads(tmp_path: Path) -> None:
    """Run it, do not read it (Guardrail #7).

    The build is one value in one file, the install reads that file, and the
    cache key is built from what the program prints out of it. This is the one
    place the printed value and the pinned value are compared.
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


def test_no_test_case_setting_is_written_into_the_workflow() -> None:
    """Guardrail #6. The test cases, the slot counts and the windows are all in config.

    A test case id, a slot count or a window written into the YAML would be the
    value an operator edits in the wrong place, invisible to the schema that
    bounds it - and a step named for a test case is how a test case keeps
    running after config switched it off.
    """
    text = read_text(WORKFLOWS_DIR / WORKFLOW)
    settings = _settings()
    for test_case in settings.test_cases:
        assert test_case.id not in text, f"the workflow names test case {test_case.id}"
        if test_case.n_ctx is not None:
            assert str(test_case.n_ctx) not in text, (
                f"{test_case.id} writes its window into the workflow"
            )
    for candidate in settings.candidates:
        assert candidate.url not in text, "an address belongs in config, never in the workflow"
