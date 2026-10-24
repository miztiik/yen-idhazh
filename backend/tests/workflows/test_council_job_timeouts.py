"""Do planning and collection use independent, validated whole-job deadlines?"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT

from utilities import shard_bound

from ._harness import (
    _job,
    _load_workflows,
    _needs,
    _normalize_condition,
    _script,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow

CONFIG_FILE = "llm_council_job_timeouts.json"
JOB_KEYS = (
    ("draw", "planning_timeout_minutes"),
    ("save_council_results", "collection_timeout_minutes"),
)


def _command(key: str) -> list[str]:
    workflow = _load_workflows()["llm-council.yml"]
    output = _job(workflow, "job_bounds")["outputs"]
    assert isinstance(output, dict)
    producer = re.fullmatch(
        rf"\$\{{\{{ steps\.(\w+)\.outputs\.{key} \}}\}}", str(output[key])
    )
    assert producer, f"{key} must publish its matching validated step output"
    step = _step(workflow, "job_bounds", "id", producer[1])
    script = _script(step, f"{key} producer").replace("\\\n", " ")
    assert script.startswith("set -euo pipefail\n")
    lines = script.splitlines()
    assert len(lines) == 2, "the producer must run only the stdlib bound reader"
    command = shlex.split(lines[1])
    assert command == [
        "python3", "backend/utilities/shard_bound.py",
        "--key", key, "--config-file", CONFIG_FILE, ">>", "$GITHUB_OUTPUT",
    ], f"{key} must read its own named config key and publish to Actions"
    return command[1:-2]


def _run_bound(key: str, config_root: Path) -> subprocess.CompletedProcess[str]:
    command = _command(key)
    return subprocess.run(
        [sys.executable, "-S", *command, "--config-root", str(config_root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(("job_name", "key"), JOB_KEYS)
def test_job_deadlines_follow_validated_bootstrap_outputs(job_name: str, key: str) -> None:
    workflow = _load_workflows()["llm-council.yml"]
    job = _job(workflow, job_name)
    assert "job_bounds" in _needs(workflow, job_name), (
        f"{job_name} must directly depend on its deadline producer"
    )
    assert job["timeout-minutes"] == f"${{{{ fromJSON(needs.job_bounds.outputs.{key}) }}}}"
    _command(key)
    assert shard_bound.minutes(CONFIG_DIR, key=key, config_file=CONFIG_FILE) == 30


def test_job_timeout_values_substitute_independently(tmp_path: Path) -> None:
    path = tmp_path / CONFIG_FILE
    for planning, collection in ((7, 19), (11, 19), (11, 23)):
        values = dict(zip((key for _, key in JOB_KEYS), (planning, collection), strict=True))
        path.write_text(json.dumps(values), encoding="utf-8")
        for _, key in JOB_KEYS:
            assert shard_bound.minutes(tmp_path, key=key, config_file=CONFIG_FILE) == values[key]
            result = _run_bound(key, tmp_path)
            assert result.returncode == 0, result.stderr
            assert result.stdout == f"{key}={values[key]}\n"
            assert result.stderr == ""


@pytest.mark.parametrize("key", [key for _, key in JOB_KEYS])
@pytest.mark.parametrize(
    "invalid",
    [None, True, "12", 1.5, 0, -1],
    ids=["missing-key", "bool", "string", "float", "zero", "negative"],
)
def test_job_timeout_reader_and_cli_refuse_invalid_values(
    tmp_path: Path, key: str, invalid: object,
) -> None:
    values = {name: 13 for _, name in JOB_KEYS}
    payload: dict[str, object] = dict(values)
    if invalid is None:
        del payload[key]
    else:
        payload[key] = invalid
    (tmp_path / CONFIG_FILE).write_text(json.dumps(payload), encoding="utf-8")
    message = (
        f"{key} is not in the config file, so the job would have no bound"
        if invalid is None
        else f"{key} must be a whole number of minutes, 1 or more"
    )
    with pytest.raises(SystemExit, match=re.escape(message)):
        shard_bound.minutes(tmp_path, key=key, config_file=CONFIG_FILE)
    result = _run_bound(key, tmp_path)
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() == message


def test_bootstrap_uses_only_checkout_and_stdlib_reader() -> None:
    workflow = _load_workflows()["llm-council.yml"]
    bootstrap = _job(workflow, "job_bounds")
    assert bootstrap["permissions"] == {"contents": "read"}
    assert bootstrap["runs-on"] == "ubuntu-latest"
    assert "timeout-minutes" not in bootstrap, "bootstrap inherits the platform ceiling"
    assert _needs(workflow, "job_bounds") == []
    steps = _steps(workflow, "job_bounds")
    assert len(steps) == 3
    assert steps[0] == {"uses": "actions/checkout@v6"}
    assert all(set(step) == {"id", "run"} for step in steps[1:])
    for _, key in JOB_KEYS:
        _command(key)


def test_judging_keeps_its_separate_shard_deadline() -> None:
    workflow = _load_workflows()["llm-council.yml"]
    assert _needs(workflow, "judge") == ["draw"]
    assert _job(workflow, "judge")["timeout-minutes"] == (
        "${{ fromJSON(needs.draw.outputs.shard_timeout_minutes) }}"
    )
    outputs = _job(workflow, "draw")["outputs"]
    assert isinstance(outputs, dict)
    assert outputs["shard_timeout_minutes"] == "${{ steps.bounds.outputs.shard_timeout_minutes }}"
    script = _script(_step(workflow, "draw", "id", "bounds"), "shard deadline")
    assert (
        "backend/utilities/shard_bound.py --key shard_timeout_minutes --config-file llm_council.json"
        in script
    )


def test_collection_requires_only_successful_bootstrap() -> None:
    workflow = _load_workflows()["llm-council.yml"]
    assert set(_needs(workflow, "save_council_results")) == {"job_bounds", "draw", "judge"}
    collector = _job(workflow, "save_council_results")
    assert _normalize_condition(collector["if"], "collection job") == (
        "always() && needs.job_bounds.result == 'success'"
    ), "draw/judge failure or cancellation must not suppress collection after valid bounds"
