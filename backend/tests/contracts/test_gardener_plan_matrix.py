"""Does the workflow read only what the plan payload declares, and does its writer write exactly that?

The plan job's script cannot import `GardenerPlan` - it runs before anything of
ours is installed - so the payload crosses the boundary as a hand-written copy
on both sides of it: `backend/utilities/gardener_shards.py` writes it and the
workflow's expressions read it. An expression naming a key the payload does not
carry evaluates to the empty string with no error, so a misspelt `shard` hands
the landing step no shard to run, a misspelt `task_names` names every shard's
job for no task, and nothing says why. So both sides are held to the model
here, field for field.
"""

from __future__ import annotations

import re
from typing import Any, Final

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.gardener_plan import GardenerPlan, Matrix, MatrixLeg, ShardPlan
from utilities import gardener_shards

pytestmark = pytest.mark.contract

WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "idhazh-gardener.yml"

#: The step in the plan job whose outputs are the payload's fields.
PLAN_STEP: Final = "shards"

#: A read of one leg's field: the `matrix` context, never a name that ends in `matrix`.
LEG_FIELD: Final = r"(?<![\w.])matrix\.([A-Za-z_]+)"


def the_workflow() -> dict[str, Any]:
    parsed: dict[str, Any] = yaml.safe_load(read_text(WORKFLOW))
    return parsed


def spelled(pattern: str, value: Any) -> set[str]:
    """Every name the pattern's one group captures, in any string of a parsed block."""
    if isinstance(value, dict):
        return {name for key, held in value.items() for name in spelled(pattern, [key, held])}
    if isinstance(value, list):
        return {name for held in value for name in spelled(pattern, held)}
    return set(re.findall(pattern, str(value)))


def test_the_plan_job_hands_on_only_fields_the_payload_declares() -> None:
    """Each output the planner's step writes is a field of `GardenerPlan`, and the step writes each."""
    outputs = the_workflow()["jobs"]["plan"]["outputs"]
    from_the_planner = {
        name
        for name, value in outputs.items()
        if re.fullmatch(rf"\$\{{\{{ steps\.{PLAN_STEP}\.outputs\.{name} \}}\}}", value)
    }
    written = {
        line.split("=", 1)[0]
        for line in gardener_shards.outputs(gardener_shards.plan(CONFIG_DIR))
    }
    assert from_the_planner == written
    assert written <= set(GardenerPlan.model_fields)


def test_the_matrix_expression_reads_only_keys_the_models_declare() -> None:
    """The fan-out reads the plan's outputs, the matrix's `include` and each leg's fields.

    A leg is read anywhere in the shard job: its name lists the shard's tasks,
    and its steps hand the shard on. Both are read here, so a job name that
    reads a key the leg does not declare is refused.
    """
    jobs = the_workflow()["jobs"]
    planned = set(jobs["plan"]["outputs"])
    shard_job = jobs["run-tasks"]
    read_from_plan = spelled(r"needs\.plan\.outputs\.([A-Za-z_]+)", shard_job)
    assert read_from_plan <= planned, read_from_plan - planned
    payload_reads = spelled(r"fromJSON\(needs\.plan\.outputs\.([A-Za-z_]+)\)", shard_job)
    assert payload_reads <= set(GardenerPlan.model_fields), payload_reads
    assert spelled(r"fromJSON\(needs\.plan\.outputs\.matrix\)\.([A-Za-z_]+)", shard_job) <= set(
        Matrix.model_fields
    )
    assert spelled(LEG_FIELD, shard_job.get("name", "")), (
        "the job's name reads no leg, so this checks nothing"
    )
    assert spelled(LEG_FIELD, shard_job["steps"]), (
        "no step reads the matrix, so this checks nothing"
    )
    legs = spelled(LEG_FIELD, shard_job)
    assert legs <= set(MatrixLeg.model_fields), legs - set(MatrixLeg.model_fields)


def test_the_planner_writes_exactly_the_keys_each_model_declares() -> None:
    """Field for field, at every level: the plan, each shard, the matrix and each leg."""
    planned = gardener_shards.plan(CONFIG_DIR)
    assert planned["shards"], "the committed garden plans no shard, so this checks nothing"

    assert set(planned) == set(GardenerPlan.model_fields)
    for shard in planned["shards"]:
        assert set(shard) == set(ShardPlan.model_fields)
    assert set(planned["matrix"]) == set(Matrix.model_fields)
    for leg in planned["matrix"]["include"]:
        assert set(leg) == set(MatrixLeg.model_fields)
    GardenerPlan.model_validate(planned)
