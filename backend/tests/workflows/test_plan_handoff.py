"""Does every job of a run read the plan its own run filed?

The plan stage files the plan into the run-plan ledger. A workflow that plans in
one job and reads the plan in another hands that day's ledger folder on as the
`plan` artifact, because the reading jobs check out the commit their run started
from, which is older than the plan - and the artifact still arrives when the plan
job's push loses a race (run 35660521768 lost a day that way). A bench or a test
rig files its plan on the runner that reads it. Either way the folder can hold
plans other runs filed that day, so every step that reads a plan names its own
run with `--execution`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.ledger_name import LedgerName
from utilities import pipeline_test_case

from ._harness import (
    BENCH_CONFIG_STEP,
    BENCH_CORPUS_STEP,
    SUBSTITUTED_EXECUTION,
    _bash,
    _commit_call,
    _load_workflows,
    _mapping,
    _script,
    _stage_invocations,
    _step,
    _steps,
    _strings,
    requires_bash,
)

pytestmark = pytest.mark.workflow

#: Each workflow that hands a plan from its `plan` job to other jobs, and those jobs.
PLAN_HANDOFFS: Final = {
    "digest.yml": ("assemble", "work"),
    "validate.yml": ("qualify",),
}

#: Every workflow with a step that reads a plan through an `idhazh` verb.
PLAN_READING_WORKFLOWS: Final = ("digest.yml", "measure.yml", "validate.yml")

#: Every verb that reads the plan its run made. Declared by hand, mirroring the
#: verbs `idhazh.cli` routes through `_planned`.
PLAN_READING_VERBS: Final = frozenset(
    {"shards", "work", "record", "fingerprint", "job-clock", "assemble", "qualify", "validate"}
)

#: The artifact the plan travels in, and the flag a step names its run with.
PLAN_ARTIFACT: Final = "plan"
EXECUTION_FLAG: Final = "--execution"

#: How a `run:` body names its run: the GitHub run id the plan stage was given.
NAMES_THE_RUN: Final = '--execution "${{ github.run_id }}"'

#: Where the plan job puts the plan's folder, and where a reading job takes it from.
FILED_IN: Final = "${{ steps.decide.outputs.plan_dir }}/"
TAKEN_FROM: Final = "${{ needs.plan.outputs.plan_dir }}/"

#: The bench step that times the cut corpus, and the pipeline-tests step that runs it.
BENCH_SWEEP_STEP: Final = "Measure runtime candidate"
PIPELINE_TESTS_WORKFLOW: Final = "idhazh-pipeline-tests.yaml"
PIPELINE_TESTS_RUN_STEP: Final = "Run the test case"


def _calls(script: str, program: str) -> list[str]:
    """The lines of a `run:` body that call `program`, continuations folded."""
    return [line for line in script.replace("\\\n", " ").splitlines() if program in line]


@pytest.mark.parametrize("workflow_name", sorted(PLAN_HANDOFFS))
def test_the_plan_travels_as_the_ledger_folder_it_was_filed_in(workflow_name: str) -> None:
    """Uploaded from the folder the plan was filed in, and unpacked back into it by every reader."""
    workflow = _load_workflows()[workflow_name]
    uploads = [
        settings
        for step in _steps(workflow, "plan")
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
        and (settings := _mapping(step.get("with"), "plan upload")).get("name") == PLAN_ARTIFACT
    ]
    assert len(uploads) == 1, f"{workflow_name} must upload one artifact named {PLAN_ARTIFACT}"
    assert uploads[0]["path"] == FILED_IN
    assert uploads[0]["if-no-files-found"] == "error", "a plan job that filed no plan fails here"

    landed = {
        job_name: settings.get("path")
        for job_name in _mapping(workflow.get("jobs"), f"{workflow_name} jobs")
        for step in _steps(workflow, job_name)
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and (settings := _mapping(step.get("with"), f"{job_name} download")).get("name")
        == PLAN_ARTIFACT
    }
    assert sorted(landed) == sorted(PLAN_HANDOFFS[workflow_name])
    assert set(landed.values()) == {TAKEN_FROM}, "a plan unpacked anywhere else is read by no stage"
    assert not [text for text in _strings(workflow) if "plan.json" in text], (
        "the plan stage writes no plan.json, so a step that names one moves nothing"
    )


@requires_bash
def test_a_qualification_hands_on_the_trial_folder_its_plan_is_filed_in(tmp_path: Path) -> None:
    """The plan job plans under the candidate config, whose trial folder holds the plan."""
    workflow = _load_workflows()["validate.yml"]
    trial = _mapping(_step(workflow, "plan", "name", BENCH_CONFIG_STEP).get("with"), "config")[
        "trial_state"
    ]
    script = tmp_path / "decide.sh"
    script.write_text(
        _script(_step(workflow, "plan", "id", "decide"), "validate.yml/plan/decide"),
        encoding="ascii",
        newline="\n",
    )
    written = tmp_path / "github-output"
    written.write_text("", encoding="ascii")
    bash = _bash()
    assert bash is not None
    completed = subprocess.run(
        [bash, script.as_posix()],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_OUTPUT": written.as_posix()},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    outputs = dict(
        line.split("=", 1) for line in written.read_text(encoding="utf-8").splitlines() if line
    )
    expected = ledger.raw_root(Path(ledger.STATE_DIRNAME) / str(trial), LedgerName.RUN_PLAN)
    assert outputs["plan_dir"] == expected.joinpath(*outputs["date"].split("-")).as_posix()


@pytest.mark.parametrize("workflow_name", PLAN_READING_WORKFLOWS)
def test_every_step_that_reads_the_plan_names_its_own_run(workflow_name: str) -> None:
    """Unnamed, a stage reads the newest plan of the day, which can be another run's."""
    workflow = _load_workflows()[workflow_name]
    unnamed: list[str] = []
    checked = 0
    for job_name, step_name, stage, words in _stage_invocations(workflow, workflow_name):
        if stage not in PLAN_READING_VERBS:
            continue
        checked += 1
        if EXECUTION_FLAG in words and words[words.index(EXECUTION_FLAG) + 1].startswith(
            "expression"
        ):
            continue
        unnamed.append(
            f"{workflow_name} job {job_name}, step {step_name!r}, runs `idhazh {stage}` "
            f"and does not name its run. Pass {EXECUTION_FLAG} with the run id the plan "
            "stage was given."
        )
    assert not unnamed, "\n".join(unnamed)
    assert checked, f"no step in {workflow_name} reads the plan, so nothing here was checked"


def test_a_day_rebuilt_after_a_lost_race_reads_the_same_runs_plan() -> None:
    """The rebuild runs on a tip that may hold a plan a later run filed the same day."""
    rebuild = _commit_call("assemble")[1]["REGENERATE_COMMAND"].split()
    assert rebuild[rebuild.index(EXECUTION_FLAG) + 1] == SUBSTITUTED_EXECUTION


def test_the_bench_cuts_and_times_its_own_runs_plan() -> None:
    """The cut replaces this run's plan, and every repeat works this run's plan."""
    workflow = _load_workflows()["measure.yml"]
    bodies = {
        str(step.get("name")): str(step.get("run", ""))
        for job_name in _mapping(workflow.get("jobs"), "measure.yml jobs")
        for step in _steps(workflow, job_name)
    }
    for step_name, verb in (
        (BENCH_CORPUS_STEP, "runtime_sweep.py freeze-corpus"),
        (BENCH_SWEEP_STEP, "runtime_sweep.py sweep"),
    ):
        calls = _calls(bodies[step_name], verb)
        assert len(calls) == 1, f"{step_name} must run {verb} once"
        assert NAMES_THE_RUN in calls[0], f"{verb} must name the run whose plan it reads"
    freeze = _calls(bodies[BENCH_CORPUS_STEP], "runtime_sweep.py freeze-corpus")[0]
    assert "--commit" in freeze, "the cut is filed through the ledger door, which names a commit"


def test_a_pipeline_test_runner_runs_the_plan_its_dispatch_drew() -> None:
    """The runner is told its run, and both production commands it starts are told too."""
    workflow = _load_workflows()[PIPELINE_TESTS_WORKFLOW]
    step = _step(workflow, "test-case", "name", PIPELINE_TESTS_RUN_STEP)
    assert _mapping(step.get("env"), "run step env")["RUN_EXECUTION"] == "${{ github.run_id }}"
    calls = _calls(_script(step, PIPELINE_TESTS_RUN_STEP), "pipeline_test_case.py run")
    assert len(calls) == 1 and '--execution "$RUN_EXECUTION"' in calls[0]

    for verb in ("work", "record"):
        words = pipeline_test_case._stage(
            verb, date="2026-09-14", execution=7, config_root=Path("config"), shard=0, shards=1
        )
        assert words[words.index(EXECUTION_FLAG) + 1] == "7", f"{verb} must read this run's plan"
