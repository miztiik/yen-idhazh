"""How many shards run, where does the number come from, and does every job get what it waits on?"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from utilities import shard_bound

from ._harness import (
    CONTENT_REFRESH_SHARD_DEFAULT,
    CONTENT_REFRESH_SHARDS,
    WORK_BOUND_KEYS,
    _dispatch_inputs,
    _evaluate_shard_matrix,
    _expression,
    _job,
    _load_workflows,
    _mapping,
    _needs,
    _script,
    _step,
    _steps,
    _string_list,
    _strings,
    _substitute,
    _values_keyed,
)

pytestmark = pytest.mark.workflow

#: What the site serves, relative to the repository root. Only the job that
#: publishes writes under it.
PUBLISHED_TREE: Final = "frontend/public/"


def test_content_refresh_has_eight_total_work_shards_at_most() -> None:
    workflow = _load_workflows()["digest.yml"]
    shards = _mapping(_dispatch_inputs(workflow).get("shards"), "shards input")
    options = _string_list(shards.get("options"), "shards options")

    assert shards.get("type") == "choice"
    assert shards.get("default") == CONTENT_REFRESH_SHARD_DEFAULT
    assert len(options) == len(CONTENT_REFRESH_SHARDS)
    assert frozenset(options) == CONTENT_REFRESH_SHARDS


def test_the_work_job_reads_its_bound_and_its_width_from_the_plan() -> None:
    """A bound written twice is a bound that can disagree with itself.

    `timeout-minutes` said 330 while `run.shard_timeout_minutes` said 150 and
    nothing read the config number, so a model sized against config was sized
    against a number production ignored. Both keys now resolve through
    `needs.plan.outputs`, and neither may go back to being a number typed here.
    """
    workflow = _load_workflows()["digest.yml"]
    work = _job(workflow, "work")
    strategy = _mapping(work.get("strategy"), "work strategy")

    assert work.get("timeout-minutes") == _expression(
        "fromJSON(needs.plan.outputs.shard_timeout_minutes)"
    )
    # The run's own worker count, never a fixed one. The matrix and concurrency
    # cap must agree for both automatic and manual runs.
    assert strategy.get("max-parallel") == _expression("fromJSON(needs.plan.outputs.shards)")

    for key, value in _values_keyed(work, WORK_BOUND_KEYS):
        assert not value.isdigit(), f"the work job writes {key} as the literal {value}"


def test_the_work_bound_is_whatever_the_config_says_it_is(tmp_path: Path) -> None:
    """Change the number in `config/idhazh.json` and the rendered bound changes.

    Running the shipped program against a real config directory is what makes
    this a test of the step rather than of a copy of its arithmetic.
    """
    workflow = _load_workflows()["digest.yml"]
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")
    assert outputs.get("shard_timeout_minutes") == _expression(
        "steps.bounds.outputs.shard_timeout_minutes"
    )

    script = _script(_step(workflow, "plan", "id", "bounds"), "digest.yml/plan/bounds")
    assert "backend/utilities/shard_bound.py" in script, "the bound comes from one module"
    assert '>> "$GITHUB_OUTPUT"' in script

    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["run"]
    assert shard_bound.minutes(CONFIG_DIR) == committed["shard_timeout_minutes"]

    def config_saying(minutes: object) -> Path:
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "config" / "idhazh.json").write_text(
            json.dumps({"run": {"shard_timeout_minutes": minutes}}), encoding="utf-8"
        )
        return tmp_path / "config"

    moved = int(committed["shard_timeout_minutes"]) + 7
    assert shard_bound.minutes(config_saying(moved)) == moved

    # `timeout-minutes` takes whatever it is handed, and a value it cannot read
    # as a number leaves the worker with no bound at all - which the run finds
    # out six hours later. So the one place that writes it is where a bound that
    # is not a whole count of minutes has to stop.
    for unusable in ("150", 0, -1, 12.5, True, None):
        with pytest.raises(SystemExit, match="shard_timeout_minutes"):
            shard_bound.minutes(config_saying(unusable))


def test_content_refresh_derives_the_shard_count_after_the_plan() -> None:
    """The matrix was written before the plan existed, so `run.shard_size` could not reach it.

    `shards` and `matrix` therefore move to their own step behind `Plan the day`,
    and the job outputs move with them. A relocated step id that nothing
    re-points is a silent break no shell assertion catches.
    """
    workflow = _load_workflows()["digest.yml"]
    outputs = _mapping(_job(workflow, "plan").get("outputs"), "plan outputs")
    assert outputs.get("shards") == "${{ steps.fanout.outputs.shards }}"
    assert outputs.get("matrix") == "${{ steps.fanout.outputs.matrix }}"

    steps = _steps(workflow, "plan")
    assert [step.get("id") for step in steps].index("fanout") > (
        [step.get("name") for step in steps].index("Plan the day")
    )
    decide_script = _step(workflow, "plan", "id", "decide").get("run")
    assert isinstance(decide_script, str)
    assert "SHARDS" not in decide_script, "the fan-out no longer rides on the date step"


def test_content_refresh_caps_total_jobs_by_behavior() -> None:
    workflow = _load_workflows()["digest.yml"]
    fanout = _step(workflow, "plan", "id", "fanout")
    script = fanout.get("run")
    assert isinstance(script, str)

    # Nobody asked, so the day decides. A day that needs fewer workers gets
    # fewer, and every extra worker restores the weights again.
    for derived in sorted(int(shards) for shards in CONTENT_REFRESH_SHARDS):
        assert _evaluate_shard_matrix(script, "", derived) == list(range(derived))
    # A config that outruns the ceiling costs the tail of the fan-out, never the
    # day: the feeds have already been read when this step runs.
    assert _evaluate_shard_matrix(script, "", 12) == list(range(int(max(CONTENT_REFRESH_SHARDS))))

    # An operator's own value still wins, and is still checked rather than clamped.
    expected = {shards: list(range(int(shards))) for shards in sorted(CONTENT_REFRESH_SHARDS)}
    for requested_shards, matrix in expected.items():
        assert _evaluate_shard_matrix(script, requested_shards, 1) == matrix
    # Both edges of the ceiling, plus the shapes that are not an integer.
    for invalid_shards in ("0", "9", "10", "-1", "1.5", "text", "04", " 4"):
        assert _evaluate_shard_matrix(script, invalid_shards, 4) is None


def test_every_output_a_job_reads_is_one_its_producer_declares() -> None:
    """A renamed job leaves `needs.<old>.outputs.<x>` resolving to the empty string.

    GitHub does not fail on that. The expression evaluates to nothing, the step
    runs with an empty argument, and the run is green - so a job rename is the
    one edit whose damage shows up only in the output. This walks every
    `needs.<job>.outputs.<name>` in every workflow and asks two things of it:
    that the job is one this job waits on, and that the job declares that output.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        jobs = _mapping(workflow.get("jobs"), "jobs")
        declared = {
            job_name: set(_mapping(_job(workflow, job_name).get("outputs") or {}, "outputs"))
            for job_name in jobs
        }
        for job_name in jobs:
            waits_on = set(_needs(workflow, job_name))
            read = {
                (match.group(1), match.group(2))
                for text in _strings(_job(workflow, job_name))
                for match in re.finditer(r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)", text)
            }
            for producer, output in sorted(read):
                where = f"{filename} job {job_name}"
                assert producer in jobs, f"{where} reads an output of the absent job {producer}"
                assert producer in waits_on, f"{where} reads {producer} without needing it"
                assert output in declared[producer], (
                    f"{where} reads needs.{producer}.outputs.{output}, "
                    f"which {producer} does not declare"
                )


def test_every_artifact_a_job_downloads_is_uploaded_by_a_job_it_waits_on() -> None:
    """An artifact name is a string agreed between two jobs and checked by nobody.

    `download-artifact` on a name nothing uploaded fails the step, and both of
    the daily run's cross-job downloads carry `continue-on-error` - so a
    mismatched name degrades the day to no visuals rather than failing it. Same
    silence as the glob below, one layer up.

    A `pattern:` download takes any number of matching artifacts, so it is
    checked as a prefix rather than as a name.
    """
    for filename, workflow in sorted(_load_workflows().items()):
        uploads = {
            str(_mapping(step.get("with"), "upload").get("name")): job_name
            for job_name in _mapping(workflow.get("jobs"), "jobs")
            for step in _steps(workflow, job_name)
            if str(step.get("uses", "")).startswith("actions/upload-artifact")
        }
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            reachable = set(_needs(workflow, job_name))
            for step in _steps(workflow, job_name):
                if not str(step.get("uses", "")).startswith("actions/download-artifact"):
                    continue
                asked = _mapping(step.get("with"), f"{job_name} download")
                where = f"{filename} job {job_name}"
                if isinstance(pattern := asked.get("pattern"), str):
                    prefix = pattern.removesuffix("*")
                    # A job's own later upload can match the prefix and cannot
                    # exist yet, so it is not a producer of this download:
                    # `validate.yml` reads `qualification-*` and then writes
                    # `qualification-report`.
                    producers = {
                        uploads[name] for name in uploads if name.startswith(prefix)
                    } - {job_name}
                    assert producers, f"{where} downloads pattern {pattern}, which nothing uploads"
                    assert producers <= reachable, (
                        f"{where} downloads pattern {pattern} from {sorted(producers - reachable)}, "
                        "which it does not wait on"
                    )
                    continue
                name = str(asked.get("name"))
                assert name in uploads, f"{where} downloads {name}, which no job uploads"
                assert uploads[name] in reachable, (
                    f"{where} downloads {name} from {uploads[name]}, which it does not wait on"
                )


def test_no_job_hands_a_published_file_to_another_job() -> None:
    """The checkout that publishes writes the published tree, so no artifact carries any of it.

    Run `37212772816` (2026-10-04): each work shard uploaded its whole day
    directory so that assemble could collect the charts, and assemble unpacked
    all four into its own day directory at once. Two shards whose ledger pushes
    had rebased onto a newer tip carried a 128-story `digest.json` and the other
    two carried 73 stories. The overlapping writes left the shorter file with the
    longer one's tail, and assemble could not read the day it was extending.

    A chart's bytes travel inside its decision in `items-<shard>`, and assemble
    writes the file itself (`render.write.write_charts_from_decisions`). So no
    upload or download in any workflow names a path under the published tree.
    """
    for filename, workflow in _load_workflows().items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            for step in _steps(workflow, job_name):
                uses = str(step.get("uses", ""))
                if not uses.startswith(("actions/upload-artifact", "actions/download-artifact")):
                    continue
                asked = _mapping(step.get("with"), f"{filename} job {job_name} artifact step")
                for line in _substitute(str(asked.get("path", ""))).splitlines():
                    assert not line.strip().removeprefix("!").startswith(PUBLISHED_TREE), (
                        f"{filename} job {job_name} moves {line.strip()} between jobs; "
                        "the job that publishes writes the published tree itself"
                    )
