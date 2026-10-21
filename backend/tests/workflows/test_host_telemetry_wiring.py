"""Measured workflows run Python work independently of their host collector."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT

from utilities import candidate_pointer

from ._harness import (
    _dispatch_inputs,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _script,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow

PRODUCERS = {
    "digest.yml": {
        "plan": ("Plan the day", "python backend/utilities/digest_publish.py run plan"),
        "work": ("Work the shard", "python backend/utilities/digest_publish.py run work"),
        "assemble": (
            "Assemble and publish", "python backend/utilities/digest_publish.py run assemble",
        ),
    },
    "measure.yml": {
        "llama-bench": ("Benchmark the candidate", "python3 backend/utilities/measure_llm.py bench"),
        "runtime": ("Measure runtime candidate", "python3 backend/utilities/runtime_sweep.py sweep"),
    },
    "encoder-comparison.yml": {
        "score": ("Score it", "python3 backend/utilities/compare_summary_encoders.py score"),
    },
    "idhazh-gardener.yml": {
        "run-tasks": (
            "Run the shard's tasks and land its record", "python backend/utilities/gardener_publish.py",
        ),
    },
    "llm-council.yml": {
        "save_council_results": (
            "Settle and publish every completed tenant output",
            "python backend/utilities/council_publish.py",
        ),
    },
}


@pytest.mark.parametrize("filename", PRODUCERS)
def test_python_is_the_default_and_whole_off_is_the_only_other_choice(filename: str) -> None:
    workflow = _load_workflows()[filename]
    inputs = _dispatch_inputs(workflow)
    host = _mapping(inputs["host_telemetry"], "host choice")
    memory = _mapping(inputs["memory_profiling"], "memory choice")
    assert host["default"] == "python"
    assert host["options"] == ["python", "off"]
    assert memory["default"] == "inherit"
    assert memory["options"] == ["inherit", "on", "off"]
    env = _mapping(workflow["env"], "workflow environment")
    assert env["IDHAZH_HOST_TELEMETRY_MODE"] == "${{ inputs.host_telemetry || 'python' }}"
    assert env["MEMORY_PROFILING"] == "${{ inputs.memory_profiling || 'inherit' }}"


@pytest.mark.parametrize("filename", PRODUCERS)
def test_real_work_runs_directly_after_resolving_the_selected_config(filename: str) -> None:
    workflow = _load_workflows()[filename]
    for job, (name, command) in PRODUCERS[filename].items():
        steps = _steps(workflow, job)
        resolver = _step(workflow, job, "id", "host_telemetry")
        producer = _step(workflow, job, "name", name)
        root = "backend/var/candidate-config" if (filename, job) == (
            "measure.yml", "runtime",
        ) else "config"
        resolve_script = _script(resolver, "host resolution")
        assert f'host_telemetry_control.py "$REQUESTED" --config-root {root}' in resolve_script
        assert 'IDHAZH_HOST_TELEMETRY_MODE=$MODE" >> "$GITHUB_ENV"' in resolve_script
        assert 'mode=$MODE" >> "$GITHUB_OUTPUT"' in resolve_script
        assert steps.index(resolver) < steps.index(producer)
        script = _script(producer, name)
        assert command in script
        assert "IDHAZH_HOST_TELEMETRY_MODE" not in script
        assert producer.get("if") in (None, "always()")
        if root != "config":
            config = _step(workflow, job, "name", "Build the candidate config")
            assert steps.index(config) < steps.index(resolver)


def test_python_postwork_measurements_are_guarded_without_guarding_item_publication() -> None:
    workflow = _load_workflows()["digest.yml"]
    for job in ("plan", "work", "assemble"):
        for name in ("What machine this job drew", "What this job cost"):
            step = _step(workflow, job, "name", name)
            condition = _normalize_condition(step["if"], name)
            assert "env.IDHAZH_HOST_TELEMETRY_MODE == 'python'" in condition
            assert f"--job {job}" in _script(step, name)
    for name in ("Record what this shard measured", "Commit what this shard measured"):
        step = _step(workflow, "work", "name", name)
        assert _normalize_condition(step["if"], name) == "always()"
    for name in ("Sample memory", "What memory this shard used"):
        step = _step(workflow, "work", "name", name)
        assert "env.IDHAZH_HOST_TELEMETRY_MODE == 'python'" in str(step["if"])
        assert "memory_profiling_control.py" in _script(step, name)
    log = _step(workflow, "work", "name", "Upload runtime log")
    assert log["if"] == "always()"
    assert str(_mapping(log["with"], "runtime log")["path"]).strip() == "llama-server.log"


def test_collector_artifacts_keep_their_job_and_encoder_ownership() -> None:
    workflows = _load_workflows()
    for filename, job, name in (
        ("digest.yml", "work", "Upload host measurements"),
        ("measure.yml", "llama-bench", "Upload the benchmark host record"),
        ("measure.yml", "runtime", "Upload the runtime host record"),
        ("encoder-comparison.yml", "score", "Upload the encoder host record"),
        ("encoder-comparison.yml", "score", "Upload the encoder host log"),
    ):
        step = _step(workflows[filename], job, "name", name)
        assert step["if"] == "always() && env.IDHAZH_HOST_TELEMETRY_MODE == 'python'"
    encoder = workflows["encoder-comparison.yml"]
    host = _step(encoder, "score", "name", "Upload the encoder host record")
    assert _mapping(host["with"], "encoder host record")["name"] == (
        "host-record-${{ matrix.encoder }}"
    )
    env = _mapping(_job(encoder, "score")["strategy"], "encoder strategy")
    assert "encoder" in _mapping(env["matrix"], "encoder matrix")


@pytest.mark.parametrize(
    "host_choice,master,memory",
    [
        ("python", True, "on"),
        ("python", True, "off"),
        ("python", False, "on"),
        ("python", False, "off"),
        ("off", True, "inherit"),
        ("off", True, "on"),
        ("off", True, "off"),
        ("off", False, "inherit"),
        ("off", False, "on"),
        ("off", False, "off"),
    ],
)
def test_generated_candidate_config_preserves_master_control_and_memory_override(
    tmp_path: Path, host_choice: str, master: bool, memory: str,
) -> None:
    config = tmp_path / "candidate-config"
    config.mkdir()
    payload = json.loads((CONFIG_DIR / "idhazh.json").read_text(encoding="utf-8"))
    payload["observability"]["host_telemetry_enabled"] = master
    payload["observability"]["memory_profiling_enabled"] = True
    (config / "idhazh.json").write_text(json.dumps(payload), encoding="ascii")
    candidate_pointer.point_at(
        "models/generated-candidate.json", scratch=config, trial_state="pipeline-tests",
    )
    resolver = _step(_load_workflows()["measure.yml"], "runtime", "id", "host_telemetry")
    words = shlex.split(_script(resolver, "host resolver").split("MODE=$(")[1].split(")")[0])
    assert words[:3] == ["python", "backend/utilities/host_telemetry_control.py", "$REQUESTED"]
    selected = subprocess.run(
        [sys.executable, str(REPO_ROOT / words[1]), host_choice, "--config-root", str(config)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert selected == ("python" if master and host_choice == "python" else "off")
    memory_done = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "backend/utilities/memory_profiling_control.py"),
            memory, "--config-root", str(config), "--write",
        ],
        env={**os.environ, "IDHAZH_HOST_TELEMETRY_MODE": selected},
        capture_output=True, text=True, check=True,
    )
    expected = selected == "python" and memory != "off"
    assert memory_done.stdout.strip() == ("on" if expected else "off")
    generated = json.loads((config / "idhazh.json").read_text(encoding="utf-8"))
    assert generated["models_file"] == "models/generated-candidate.json"
    assert generated["run"]["trial_state_dirname"] == "pipeline-tests"
    assert generated["observability"]["host_telemetry_enabled"] is master
