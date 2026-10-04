"""Does every job of a digest run read the plan its own plan job made?

The plan job files the plan into the run-plan ledger and hands that day's ledger
folder to the work and assemble jobs as the `plan` artifact. Each of those jobs
checks out the commit its run started from, which is older than the plan, so
the artifact is how the plan reaches them - and it still does when the plan
job's push loses a race (run 35660521768 lost a day that way). The folder can
also hold plans that earlier runs filed that day, so every step that reads the
plan names its own run with `--execution`.
"""

from __future__ import annotations

from typing import Final

import pytest

from ._harness import (
    SUBSTITUTED_EXECUTION,
    SUBSTITUTED_PLAN_DIR,
    _artifact_upload,
    _commit_call,
    _load_workflows,
    _mapping,
    _stage_invocations,
    _steps,
    _strings,
    _substitute,
)

pytestmark = pytest.mark.workflow

#: The workflows whose jobs hand a plan from the job that made it to the jobs that read it.
PLAN_HANDOFF_WORKFLOWS: Final = ("digest.yml",)

#: Every verb that reads the plan its run made. Declared by hand, mirroring the
#: verbs `idhazh.cli` routes through `_planned`.
PLAN_READING_VERBS: Final = frozenset(
    {"shards", "work", "record", "fingerprint", "job-clock", "assemble"}
)

#: The artifact the plan travels in, and the flag a step names its run with.
PLAN_ARTIFACT: Final = "plan"
EXECUTION_FLAG: Final = "--execution"


@pytest.mark.parametrize("workflow_name", PLAN_HANDOFF_WORKFLOWS)
def test_the_plan_travels_as_the_ledger_folder_it_was_filed_in(workflow_name: str) -> None:
    """Uploaded from the folder the ledger door files the day's plans in, and unpacked back into it."""
    workflow = _load_workflows()[workflow_name]
    upload = _mapping(_artifact_upload(workflow, "plan", PLAN_ARTIFACT).get("with"), "upload")
    assert _substitute(str(upload["path"])).rstrip("/") == SUBSTITUTED_PLAN_DIR

    landed = {
        job_name: _substitute(str(settings.get("path"))).rstrip("/")
        for job_name in _mapping(workflow.get("jobs"), f"{workflow_name} jobs")
        for step in _steps(workflow, job_name)
        if str(step.get("uses", "")).startswith("actions/download-artifact")
        and (settings := _mapping(step.get("with"), f"{job_name} download")).get("name")
        == PLAN_ARTIFACT
    }
    assert sorted(landed) == ["assemble", "work"], "both jobs after the plan read it"
    assert set(landed.values()) == {SUBSTITUTED_PLAN_DIR}, (
        "a plan unpacked anywhere else is a plan no stage reads"
    )
    assert not [text for text in _strings(workflow) if "plan.json" in text], (
        "the plan stage writes no plan.json, so a step that names one moves nothing"
    )


@pytest.mark.parametrize("workflow_name", PLAN_HANDOFF_WORKFLOWS)
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
