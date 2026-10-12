from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from idhazh.cli import _workflow_host_event_mode
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
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))


def test_named_producers_select_one_reversible_telemetry_writer() -> None:
    for name in WORKFLOWS:
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "IDHAZH_HOST_TELEMETRY_MODE" in text
        assert "inputs.host_telemetry || 'legacy'" in text
        assert "default: legacy" in text
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
    assert 'default=os.environ.get("IDHAZH_HOST_TELEMETRY_MODE", "legacy")' in text
    assert "monitor-cleanup" in text


@pytest.mark.parametrize(
    "command",
    [
        ["backend/utilities/digest_publish.py", "run", "plan"],
        ["backend/utilities/digest_publish.py", "run", "work"],
        ["backend/utilities/digest_publish.py", "run", "assemble"],
        ["backend/utilities/runtime_sweep.py", "sweep"],
        ["backend/utilities/measure_llm.py", "bench"],
        ["backend/utilities/record_publish.py", "run", "measure", "fingerprint"],
        ["backend/utilities/gardener_publish.py", "--shard", "0"],
        ["backend/utilities/council_publish.py", "--run-id", "2026-10-12-fixture"],
    ],
)
def test_every_table_w_producer_is_connected(command: list[str]) -> None:
    assert _native_command_supported(["python", *command])
    assert not _native_command_supported(["python", "backend/utilities/measure_judge_call.py"])


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
    assert _native_command_supported(
        ["python", "backend/utilities/digest_publish.py", "run", "work"]
    )


def test_workflow_selection_maps_to_native_or_legacy_without_config_flags() -> None:
    assert _workflow_host_event_mode({}) is None
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "legacy"}) == "legacy"
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "rust"}) == "rust"
    digest = (ROOT / ".github/workflows/digest.yml").read_text(encoding="utf-8")
    assert "IDHAZH_HOST_TELEMETRY_MODE" in digest
    for name in ("plan", "work", "assemble"):
        assert "IDHAZH_HOST_TELEMETRY_MODE" not in _job(_workflow("digest.yml"), name).get(
            "env", {}
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
    step = _step(_workflow("digest.yml"), "work", "name", "Sample memory")
    assert "IDHAZH_HOST_TELEMETRY_MODE == 'legacy'" in _normalize_condition(
        step["if"], "legacy sampler"
    )


def test_native_runtime_memory_is_summarized_and_uploaded_from_the_session() -> None:
    workflow = _workflow("digest.yml")
    summary = _step(workflow, "work", "name", "What memory this shard used")
    upload = _step(workflow, "work", "name", "Upload runtime log")
    assert "native-artifacts/rss-samples.jsonl" in summary["run"]
    assert "native-artifacts/python-procs.jsonl" in summary["run"]
    assert "native-artifacts/cgroup-memory-peak.txt" in summary["run"]
    assert "backend/var/d7-host-telemetry/**/native-artifacts/**" in upload["with"]["path"]


def test_council_workflow_allows_only_the_explicit_no_work_skip() -> None:
    text = (ROOT / ".github/workflows/llm-council.yml").read_text(encoding="utf-8")
    assert "IDHAZH_HOST_TELEMETRY_SKIPPED" in text
    assert "council-no-active-publishers" in text


def test_each_measured_job_builds_the_pinned_native_binary_before_its_producer() -> None:
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
                step
                for step in steps
                if step.get("uses") == "actions/cache@v6"
                and "host-crates-" in str(step.get("with", {}).get("key", ""))
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


def test_unmeasured_jobs_do_not_inherit_native_sessions() -> None:
    expected = {
        "measure.yml": ("models", "corpus", "budgets", "batched"),
        "encoder-comparison.yml": ("pairs", "collect"),
        "idhazh-gardener.yml": ("plan", "history"),
        "llm-council.yml": ("draw", "judge"),
    }
    for filename, jobs in expected.items():
        for job in jobs:
            assert _job(_workflow(filename), job)["env"]["IDHAZH_HOST_TELEMETRY_MODE"] == ("legacy")


def test_cleanup_uses_the_session_not_the_repository_file_workspace() -> None:
    for filename in WORKFLOWS:
        text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
        assert '--workspace "$IDHAZH_HOST_TELEMETRY_SESSION"' in text
        assert '--workspace "$IDHAZH_HOST_TELEMETRY_WORKSPACE"' not in text


def test_native_family_evidence_runs_only_in_the_isolated_artifact_workflow() -> None:
    workflow = _workflow("rust-host-telemetry.yml")
    assert workflow["permissions"] == {"contents": "read"}
    step = _step(
        workflow, "work", "name", "Generated D7 families and single-writer publication evidence"
    )
    assert step["env"]["IDHAZH_D7_LIVE_TEST"] == "1"
    assert "backend/tests/test_d7_family_lifecycle.py" in step["run"]
    assert "-n 0" in step["run"]
    text = (ROOT / ".github/workflows/rust-host-telemetry.yml").read_text(encoding="utf-8")
    assert "persist-credentials: false" in text
    assert "backend/var/d7-family-tests.xml" in text
    assert "publish_to_repo" not in text
    assert "git push" not in text
