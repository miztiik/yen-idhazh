"""Can a Model validation dispatch reach the state root a published day is built from?"""

from __future__ import annotations

import json

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.app_config import AppConfig

from ._harness import (
    BENCH_CANDIDATE_CONFIG,
    BENCH_CONFIG_FLAG,
    BENCH_CONFIG_STEP,
    BENCH_TRIAL_STATE,
    CANDIDATE_CONFIG_ACTION,
    _load_workflows,
    _mapping,
    _stage_invocations,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow

#: The workflow this module reads. It qualifies one candidate summarizer, and a
#: qualification is not a published day - so nothing it appends may reach the
#: ledgers the next production run draws from.
VALIDATION_WORKFLOW = "validate.yml"

#: The step that builds the scratch config, in each job that runs a stage. Both
#: copies say the same two things, which is what stops one of them drifting.
VALIDATION_CONFIG_JOBS = ("plan", "qualify")

#: The step the redirect exists for. `plan` appends to the seen store, feed
#: health, feed retirements and the counterfactual scores; without the flag it
#: loads the committed config, which names no trial directory, and a
#: qualification marks real addresses seen.
VALIDATION_PLAN_STEP = "Read the feeds"

#: Every stage this dispatch runs, and the job that runs it.
VALIDATION_STAGES = (
    ("decide", "qualify-decide"),
    ("plan", "plan"),
    ("qualify", "qualify"),
)

#: The one stage that is deliberately not redirected. `qualify-decide` writes the
#: run's own verdict, which is the record the dispatch exists to leave, and
#: `writer.append_validation` is handed a path off the repository root rather
#: than off the state root - so that row lands in `state/` whatever
#: `run.trial_state_dirname` says. Its job builds no scratch copy, so there is
#: nothing a `--config` flag could point at.
VALIDATION_UNREDIRECTED = frozenset({("decide", "qualify-decide")})


def test_no_validation_stage_can_reach_the_production_state_root() -> None:
    """Every pipeline stage a qualification runs is told the config that redirects it.

    `cli` moves the state root off `run.trial_state_dirname`, and only the
    scratch copy carries it. `Read the feeds` was invoked without `--config`
    until 2026-09-17, so a qualification appended to the four ledgers `plan`
    writes. Nothing in that job is committed, so the rows died with the runner -
    but the job could reach the production root, this workflow holds
    `contents: write`, and `decide` already commits `state`, so the distance
    between the two was one step somebody would add without reading this far.

    Asserted over every job in the file rather than over the three that run a
    stage today, so a fourth job that adds one is caught here rather than by a
    production day that came up short.
    """
    workflow = _load_workflows()[VALIDATION_WORKFLOW]

    invocations = []
    for job_name, step_name, stage, words in _stage_invocations(workflow, VALIDATION_WORKFLOW):
        invocations.append((job_name, stage))
        if (job_name, stage) in VALIDATION_UNREDIRECTED:
            assert BENCH_CONFIG_FLAG not in words, (
                f"{VALIDATION_WORKFLOW}/{job_name}/{step_name} carries --config, and its job "
                "builds no scratch copy for the flag to point at"
            )
            continue
        assert BENCH_CONFIG_FLAG in words, (
            f"{VALIDATION_WORKFLOW}/{job_name}/{step_name} runs `idhazh {stage}` "
            "without --config, so its ledgers land in production's state root"
        )
        assert words[words.index(BENCH_CONFIG_FLAG) + 1] == BENCH_CANDIDATE_CONFIG, (
            f"{VALIDATION_WORKFLOW}/{job_name}/{step_name} reads a config that is "
            f"not {BENCH_CANDIDATE_CONFIG}"
        )

    assert sorted(invocations) == list(VALIDATION_STAGES), (
        "a job started running a pipeline stage, or one stopped"
    )

    scratch = json.loads(read_text(REPO_ROOT / "config" / "idhazh.json"))
    scratch["run"]["trial_state_dirname"] = BENCH_TRIAL_STATE
    assert AppConfig.model_validate(scratch).run.trial_state_dirname == BENCH_TRIAL_STATE, (
        "the flag is worth nothing if the copy it points at cannot carry the redirect"
    )


def test_both_halves_of_a_qualification_name_one_trial_directory() -> None:
    """The flag redirects nothing unless the copy it names carries the trial directory.

    Two jobs build the scratch copy and both pass the same directory, so the
    dispatch has one answer to "where did this run's rows go" rather than two.
    """
    workflow = _load_workflows()[VALIDATION_WORKFLOW]

    for job_name in VALIDATION_CONFIG_JOBS:
        step = _step(workflow, job_name, "name", BENCH_CONFIG_STEP)
        uses = step.get("uses")
        assert isinstance(uses, str) and uses.endswith(CANDIDATE_CONFIG_ACTION), (
            f"{VALIDATION_WORKFLOW}/{job_name}/{BENCH_CONFIG_STEP} must use the shared action"
        )
        with_block = _mapping(step.get("with"), f"{job_name} {BENCH_CONFIG_STEP} with")
        assert with_block.get("trial_state") == BENCH_TRIAL_STATE, (
            f"{VALIDATION_WORKFLOW}/{job_name} builds a config that still names "
            "the production state root"
        )


def test_the_feeds_are_read_through_the_config_the_job_just_built() -> None:
    """A flag pointing at a directory that does not exist yet redirects nothing.

    The plan job builds the scratch copy and then reads the feeds. Reversing the
    two leaves `plan` pointed at an absent path, which fails the step rather
    than writing to production - but it fails a five-hour dispatch at its first
    minute, and this is the cheaper place to find out.
    """
    workflow = _load_workflows()[VALIDATION_WORKFLOW]
    names = [step.get("name") for step in _steps(workflow, "plan")]
    assert names.index(BENCH_CONFIG_STEP) < names.index(VALIDATION_PLAN_STEP)
