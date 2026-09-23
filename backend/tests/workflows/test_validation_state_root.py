"""Can a Model validation dispatch reach the state root a published day is built from?"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.evals.golden import GoldenResult
from idhazh.stages import common, decide
from utilities import candidate_pointer

from ._harness import (
    BENCH_CANDIDATE_CONFIG,
    BENCH_CONFIG_FLAG,
    BENCH_CONFIG_STEP,
    BENCH_TRIAL_STATE,
    CANDIDATE_CONFIG_ACTION,
    MODELS_POINTER_KEY,
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

#: The step that builds the scratch config, in each job that runs a stage. All
#: three copies say the same two things, which is what stops one of them
#: drifting. `decide` joined on 2026-09-18, when its verdict stopped being built
#: off the repository root.
VALIDATION_CONFIG_JOBS = ("plan", "qualify", "decide")

#: The step the redirect exists for. `plan` appends to the seen store, feed
#: health, feed retirements and the counterfactual scores; without the flag it
#: loads the committed config, which names no trial directory, and a
#: qualification marks real addresses seen.
VALIDATION_PLAN_STEP = "Read the feeds"

#: The three steps of the decide job, in the order they have to run: the gates
#: write a segment, the fold turns it into the day file, and the commit stages
#: what the fold wrote.
VALIDATION_GATES_STEP = "Run the gates"

VALIDATION_COMPACT_STEP = "Fold the verdict into its day"

VALIDATION_COMMIT_STEP = "Commit the validation ledger"

#: Every stage this dispatch runs, and the job that runs it.
VALIDATION_STAGES = (
    ("decide", "compact"),
    ("decide", "qualify-decide"),
    ("plan", "plan"),
    ("qualify", "qualify"),
)


def test_no_validation_stage_can_reach_the_production_state_root() -> None:
    """Every pipeline stage a qualification runs is told the config that redirects it.

    `cli` moves the state root off `run.trial_state_dirname`, and only the
    scratch copy carries it. `Read the feeds` was invoked without `--config`
    until 2026-09-17, so a qualification appended to the four ledgers `plan`
    writes. `qualify-decide` was the last one out, on 2026-09-18: it built its
    verdict's path off the repository root, so no config could move it and a
    trial dispatch wrote the tree a published day is built from.

    Asserted over every job in the file rather than over the three that run a
    stage today, so a fourth job that adds one is caught here rather than by a
    production day that came up short.
    """
    workflow = _load_workflows()[VALIDATION_WORKFLOW]

    invocations = []
    for job_name, step_name, stage, words in _stage_invocations(workflow, VALIDATION_WORKFLOW):
        invocations.append((job_name, stage))
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

    Three jobs build the scratch copy and all pass the same directory, so the
    dispatch has one answer to "where did this run's rows go" rather than three.
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


def test_the_gates_are_run_through_the_config_the_job_just_built() -> None:
    """The same ordering, in the job whose verdict is the record this dispatch leaves."""
    workflow = _load_workflows()[VALIDATION_WORKFLOW]
    names = [step.get("name") for step in _steps(workflow, "decide")]
    assert names.index(BENCH_CONFIG_STEP) < names.index(VALIDATION_GATES_STEP)
    assert names.index(VALIDATION_GATES_STEP) < names.index(VALIDATION_COMPACT_STEP), (
        "the fold turns the gates' segment into the day file, so it runs after them"
    )
    assert names.index(VALIDATION_COMPACT_STEP) < names.index(VALIDATION_COMMIT_STEP), (
        "a commit before the fold stages a segment and no head"
    )


def _golden(root: Path, model_id: str, measured: float) -> None:
    """One model's golden-set result, as `stage_decide` reads them back."""
    result = GoldenResult(
        model_id=model_id,
        leaderboard_hhem=0.75,
        scores=[measured] * 20,
        attempted=20,
    )
    (root / f"{model_id}.json").write_text(result.to_json(), encoding="utf-8")


def test_a_decide_run_on_a_trial_config_writes_nothing_outside_its_own_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row's oracle, other half. Every path the stage wrote, listed and placed.

    `evals.golden.ledger_relpath` returned `state/validation-<date>.csv` and both
    callers joined it to `config.REPO_ROOT`, so `run.trial_state_dirname` could
    not move it and a qualification wrote the tree a published day is built from.
    The verdict comes off the state root now, and the state root is the one the
    config names.

    Asserted by diffing the whole fixture tree either side of the call rather
    than by reading the one path the test expected: a stage that started writing
    somewhere else entirely would pass the second kind of check.
    """
    scratch = tmp_path / "candidate-config"
    shutil.copytree(REPO_ROOT / "config", scratch)
    committed = json.loads((scratch / "idhazh.json").read_text(encoding="utf-8"))
    candidate_pointer.point_at(
        committed[MODELS_POINTER_KEY], scratch=scratch, trial_state=BENCH_TRIAL_STATE
    )
    settings = config.load(scratch)
    assert settings.app.run.trial_state_dirname == BENCH_TRIAL_STATE

    golden_root = tmp_path / "var" / "validation"
    golden_root.mkdir(parents=True)
    _golden(golden_root, settings.models.summarizer.id, measured=0.90)
    _golden(golden_root, "a-challenger-that-lost", measured=0.50)
    monkeypatch.setattr(common, "VALIDATION_ROOT", golden_root)
    # Exactly what `cli` does when the config names a trial directory, and the
    # reason it is repeated rather than imported: the redirect is the thing under
    # test, so a test that called the router would be asking the router.
    production_root = tmp_path / "state"
    monkeypatch.setattr(
        common, "STATE_ROOT", production_root / settings.app.run.trial_state_dirname
    )
    before = {path for path in tmp_path.rglob("*") if path.is_file()}

    decide.stage_decide(
        settings=settings,
        date="2026-09-17",
        run_id="2026-09-17-900000001",
        commit_sha="c" * 40,
        runner="ubuntu-latest",
    )

    written = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file() and path not in before
    )
    assert written, "the stage recorded no verdict at all, so this proves nothing"
    trial_tree = f"state/{BENCH_TRIAL_STATE}/"
    assert [path for path in written if not path.startswith(trial_tree)] == [], (
        f"a stage on a trial config wrote outside {trial_tree}: {written}"
    )
    assert not (production_root / "validation").exists(), (
        "the production tree gained a validation ledger"
    )
