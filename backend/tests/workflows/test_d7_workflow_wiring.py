from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml  # type: ignore[import-untyped]

from utilities.d7_host_telemetry import _native_command_supported

from ._harness import _job, _normalize_condition, _step, _steps

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = (
    "digest.yml",
    "measure.yml",
    "encoder-comparison.yml",
    "idhazh-gardener.yml",
    "llm-council.yml",
)


def _workflow(name: str) -> dict[str, object]:
    document = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast(dict[str, object], document)


def _is_host_crate_cache(step: dict[str, object]) -> bool:
    settings = step.get("with")
    return (
        step.get("uses") == "actions/cache@v6"
        and isinstance(settings, dict)
        and "host-crates-" in str(settings.get("key", ""))
    )


def test_named_producers_use_only_the_native_telemetry_writer() -> None:
    for name in WORKFLOWS:
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "host_telemetry:" not in text
        assert "IDHAZH_HOST_TELEMETRY_MODE" not in text
        assert "legacy" not in text
        assert ".github/actions/d7-host-telemetry" in text
        assert "d7_host_telemetry.py run" in text
        assert "d7_host_telemetry.py cleanup" in text
        assert "IDHAZH_HOST_TELEMETRY_VERIFIED" in text


def test_d7_launcher_declares_isolated_identity_and_lifecycle_order() -> None:
    text = (ROOT / "backend/utilities/d7_host_telemetry.py").read_text(encoding="utf-8")
    assert "backend/var/d7-host-telemetry" in text
    assert "effective-config.json" in text
    assert "IDHAZH_HOST_TELEMETRY_WORKER_PID" in text
    assert "IDHAZH_HOST_TELEMETRY_WORKER_START_TICKS" in text
    assert "IDHAZH_MODEL_SERVER_PID" in text
    assert "IDHAZH_MODEL_SERVER_START_TICKS" in text
    assert "monitor = subprocess.Popen" in text
    assert text.index("monitor = subprocess.Popen") < text.index("gate.touch()")
    assert text.index("gate.touch()") < text.index("_stop(workspace, manifest, status,")
    assert "monitor.stopped" in text
    assert "receipt.json" in text
    assert re.search(
        r"_verified_receipt\(\s*ROOT,\s*manifest,\s*native\.verification_limits[,)]", text
    )
    assert "verify_host_output(" in text
    assert '"verified": True' not in text
    assert '"--mode"' not in text
    assert "host_telemetry_reference" not in text
    assert "monitor-cleanup" in text


@pytest.mark.parametrize(
    "command",
    [
        ["backend/utilities/digest_publish.py", "run", "plan"],
        ["backend/utilities/digest_publish.py", "run", "work"],
        ["backend/utilities/digest_publish.py", "run", "assemble"],
        ["backend/utilities/runtime_sweep.py", "sweep"],
        ["backend/utilities/measure_llm.py", "bench"],
        ["backend/utilities/compare_summary_encoders.py", "score"],
        ["backend/utilities/gardener_publish.py", "--shard", "0"],
        ["backend/utilities/council_publish.py", "--run-id", "2026-10-12-fixture"],
    ],
)
def test_every_table_w_producer_is_connected(command: list[str]) -> None:
    assert _native_command_supported(["python", *command])
    assert not _native_command_supported(["python", "backend/utilities/measure_judge_call.py"])


@pytest.mark.parametrize(
    "command",
    [
        ["backend/utilities/digest_publish.py", "run", "fingerprint"],
        ["backend/utilities/digest_publish.py", "run", "job-clock"],
        ["backend/utilities/record_publish.py", "run", "measure", "fingerprint"],
        ["backend/utilities/compare_summary_encoders.py", "collect"],
    ],
)
def test_retired_collectors_and_unmeasured_stages_are_not_native_producers(
    command: list[str],
) -> None:
    assert not _native_command_supported(["python", *command])


def test_workflow_wrappers_name_only_the_measured_families() -> None:
    expected = {
        "digest.yml": {"plan", "work", "assemble"},
        "measure.yml": {"runtime"},
        "encoder-comparison.yml": {"collect"},
        "idhazh-gardener.yml": {"run-tasks"},
        "llm-council.yml": {"save_council_results"},
    }
    for name, jobs in expected.items():
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        invoked = set(re.findall(r"d7_host_telemetry\.py run.*?--job ([a-z_-]+)", text, re.DOTALL))
        assert invoked == jobs
    encoder_score = _step(_workflow("encoder-comparison.yml"), "score", "name", "Score it")
    score_run = encoder_score["run"]
    assert isinstance(score_run, str)
    assert "d7_host_telemetry.py run" in score_run
    assert "compare_summary_encoders.py score" in score_run
    assert score_run.index("d7_host_telemetry.py run") < score_run.index(
        "compare_summary_encoders.py score"
    )
    assert "record_publish.py run measure fingerprint" not in score_run
    assert "IDHAZH_HOST_TELEMETRY_MODE=legacy" not in score_run
    assert _native_command_supported(
        ["python", "backend/utilities/digest_publish.py", "run", "work"]
    )


def test_model_server_exports_pid_reuse_safe_identity() -> None:
    text = (ROOT / ".github/actions/model-server/action.yml").read_text(encoding="utf-8")
    assert "server_pid:" in text
    assert "server_start_ticks:" in text
    assert "model_runtime.py export-server-identity" in text
    assert "s/^server_pid=/IDHAZH_MODEL_SERVER_PID=/" in text
    assert "s/^server_start_ticks=/IDHAZH_MODEL_SERVER_START_TICKS=/" in text
    assert text.index("export-server-identity") > text.index("the loaded weights are not")


def test_native_work_has_no_competing_python_memory_sampler() -> None:
    steps = _steps(_workflow("digest.yml"), "work")
    assert not any("start-sampler" in str(step.get("run", "")) for step in steps)
    assert not any(step.get("name") == "Sample memory" for step in steps)


def test_native_runtime_memory_is_summarized_and_uploaded_from_the_session() -> None:
    workflow = _workflow("digest.yml")
    summary = _step(workflow, "work", "name", "What memory this shard used")
    upload = _step(workflow, "work", "name", "Upload runtime log")
    summary_run = summary["run"]
    upload_with = upload["with"]
    assert isinstance(summary_run, str)
    assert isinstance(upload_with, dict)
    upload_path = upload_with.get("path")
    assert isinstance(upload_path, str)
    assert "native-artifacts/rss-samples.jsonl" in summary_run
    assert "native-artifacts/python-procs.jsonl" in summary_run
    assert "native-artifacts/cgroup-memory-peak.txt" in summary_run
    assert "backend/var/d7-host-telemetry/**/native-artifacts/**" in upload_path


def test_council_workflow_allows_only_the_explicit_no_work_skip() -> None:
    text = (ROOT / ".github/workflows/llm-council.yml").read_text(encoding="utf-8")
    assert "IDHAZH_HOST_TELEMETRY_SKIPPED" in text
    assert "council-no-active-publishers" in text


def test_each_measured_job_builds_the_pinned_native_binary_before_its_producer() -> None:
    action = yaml.safe_load(
        (ROOT / ".github/actions/d7-host-telemetry/action.yml").read_text(encoding="utf-8")
    )
    build_step = next(step for step in action["runs"]["steps"] if step.get("id") == "build")
    assert "inputs" not in action
    assert "if" not in build_step
    assert build_step["working-directory"] == "backend/rust/host-telemetry"
    assert "cargo build --locked --release" in build_step["run"]
    expected = {
        "digest.yml": ("plan", "work", "assemble"),
        "measure.yml": ("llama-bench", "runtime"),
        "encoder-comparison.yml": ("score",),
        "idhazh-gardener.yml": ("run-tasks",),
        "llm-council.yml": ("save_council_results",),
    }
    for name, jobs in expected.items():
        for job in jobs:
            steps = _steps(_workflow(name), job)
            pin = next(
                step for step in steps if step.get("name") == "Select the pinned host toolchain"
            )
            cache = next(
                step for step in steps if _is_host_crate_cache(step)
            )
            build = next(
                step for step in steps if step.get("uses") == "./.github/actions/d7-host-telemetry"
            )
            producer = next(
                step for step in steps if "d7_host_telemetry.py run" in str(step.get("run", ""))
            )
            assert (
                steps.index(pin) < steps.index(cache) < steps.index(build) < steps.index(producer)
            )
            assert pin["working-directory"] == "backend/rust/host-telemetry"
            assert all("if" not in step for step in (pin, cache, build))
            assert "with" not in build


def test_unmeasured_jobs_do_not_inherit_native_sessions() -> None:
    expected = {
        "measure.yml": ("models", "corpus", "budgets", "batched"),
        "encoder-comparison.yml": ("pairs", "collect"),
        "idhazh-gardener.yml": ("plan", "history"),
        "llm-council.yml": ("draw", "judge"),
    }
    for filename, jobs in expected.items():
        for job in jobs:
            environment = _job(_workflow(filename), job).get("env", {})
            assert isinstance(environment, dict)
            assert "IDHAZH_HOST_TELEMETRY_MODE" not in environment
            assert not any(
                "d7_host_telemetry" in str(step)
                for step in _steps(_workflow(filename), job)
            )


def test_cleanup_uses_the_session_not_the_repository_file_workspace() -> None:
    for filename in WORKFLOWS:
        text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
        assert '--workspace "$IDHAZH_HOST_TELEMETRY_SESSION"' in text
        assert '--workspace "$IDHAZH_HOST_TELEMETRY_WORKSPACE"' not in text


def test_normal_ci_keeps_native_functionality_and_generated_family_tests() -> None:
    assert not (ROOT / ".github/workflows/rust-host-telemetry.yml").exists()
    steps = _steps(_workflow("ci.yml"), "gates")
    prepare = next(step for step in steps if step.get("name") == "Pinned locked Rust preparation")
    gates = next(step for step in steps if step.get("name") == "Offline Rust module gates")
    tests = next(step for step in steps if "pytest --junitxml=" in str(step.get("run", "")))
    assert "cargo build --locked --all-targets" in str(prepare["run"])
    assert "cargo test --locked --offline" in str(gates["run"])
    assert steps.index(prepare) < steps.index(gates) < steps.index(tests)
    family = (ROOT / "backend/tests/test_d7_family_lifecycle.py").read_text(encoding="utf-8")
    assert "IDHAZH_D7_LIVE_TEST" not in family


def test_native_receipt_guards_cannot_be_bypassed_by_a_mode_choice() -> None:
    for filename in WORKFLOWS:
        for job in cast(dict[str, object], _workflow(filename)["jobs"]):
            for step in _steps(_workflow(filename), job):
                if "D7 receipt verification failed" not in str(step.get("run", "")):
                    continue
                assert _normalize_condition(step["if"], "native receipt guard") == "always()"
                body = str(step["run"])
                assert '${IDHAZH_HOST_TELEMETRY_VERIFIED:-0}' in body
                assert "IDHAZH_HOST_TELEMETRY_MODE" not in body
                assert "exit 1" in body
