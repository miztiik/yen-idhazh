from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml  # type: ignore[import-untyped]

from idhazh.cli import _workflow_host_event_mode
from utilities.d7_host_telemetry import _native_command_supported

from ._harness import (
    _dispatch_inputs,
    _job,
    _load_workflows,
    _mapping,
    _normalize_condition,
    _step,
    _steps,
)

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = (
    "digest.yml",
    "measure.yml",
    "encoder-comparison.yml",
    "idhazh-gardener.yml",
    "llm-council.yml",
)
MEASURED_JOBS = {
    "digest.yml": ("plan", "work", "assemble"),
    "measure.yml": ("llama-bench", "runtime"),
    "encoder-comparison.yml": ("score",),
    "idhazh-gardener.yml": ("run-tasks",),
    "llm-council.yml": ("save_council_results",),
}


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


def test_named_producers_select_one_reversible_telemetry_writer() -> None:
    for name in WORKFLOWS:
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "IDHAZH_HOST_TELEMETRY_MODE" in text
        assert "inputs.host_telemetry || 'rust'" in text
        assert "default: rust" in text
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


def test_workflow_selection_keeps_legacy_and_allows_whole_host_off() -> None:
    assert _workflow_host_event_mode({}) is None
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "legacy"}) == "legacy"
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "rust"}) == "rust"
    assert _workflow_host_event_mode({"IDHAZH_HOST_TELEMETRY_MODE": "off"}) == "off"
    digest = (ROOT / ".github/workflows/digest.yml").read_text(encoding="utf-8")
    assert "IDHAZH_HOST_TELEMETRY_MODE" in digest
    for name in ("plan", "work", "assemble"):
        environment = _job(_workflow("digest.yml"), name).get("env", {})
        assert isinstance(environment, dict)
        assert "IDHAZH_HOST_TELEMETRY_MODE" not in environment


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


def test_only_the_plan_builds_for_digest_and_other_measured_jobs_build_once() -> None:
    action = yaml.safe_load(
        (ROOT / ".github/actions/d7-host-telemetry/action.yml").read_text(encoding="utf-8")
    )
    build_step = next(step for step in action["runs"]["steps"] if step.get("id") == "build")
    assert build_step["working-directory"] == "backend/rust/host-telemetry"
    assert "cargo build --locked --release" in build_step["run"]
    expected = {**MEASURED_JOBS, "digest.yml": ("plan",)}
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
            assert sum(
                step.get("uses") == "./.github/actions/d7-host-telemetry" for step in steps
            ) == 1
    digest = _workflow("digest.yml")
    plan = _job(digest, "plan")
    assert _mapping(plan["outputs"], "plan outputs")["host_monitor_artifact"] == (
        "${{ steps.host_monitor.outputs.artifact_name }}"
    )
    builder = _step(digest, "plan", "id", "host_monitor")
    assert _mapping(builder["with"], "plan monitor")["publish"] == "true"
    for job in ("work", "assemble"):
        steps = _steps(digest, job)
        assert not any(step.get("uses") == "./.github/actions/d7-host-telemetry" for step in steps)
        assert not any(_is_host_crate_cache(step) for step in steps)
        assert not any("rustup" in str(step.get("run", "")) for step in steps)
        download = _step(digest, job, "uses", "./.github/actions/download-host-telemetry")
        assert _mapping(download["with"], "shared monitor")["artifact_name"] == (
            "${{ needs.plan.outputs.host_monitor_artifact }}"
        )
        needs = _job(digest, job)["needs"]
        assert needs == "plan" or (isinstance(needs, list) and "plan" in needs)
        producer = next(
            step for step in steps if "d7_host_telemetry.py run" in str(step.get("run", ""))
        )
        assert steps.index(download) < steps.index(producer)


def test_unmeasured_jobs_do_not_inherit_native_sessions() -> None:
    expected = {
        "measure.yml": ("models", "corpus", "budgets", "batched"),
        "encoder-comparison.yml": ("pairs", "collect"),
        "idhazh-gardener.yml": ("plan", "history"),
        "llm-council.yml": ("draw", "judge"),
    }
    for filename, jobs in expected.items():
        for job in jobs:
            environment = _job(_workflow(filename), job)["env"]
            assert isinstance(environment, dict)
            assert environment.get("IDHAZH_HOST_TELEMETRY_MODE") == (
                "${{ inputs.host_telemetry == 'off' && 'off' || 'legacy' }}"
            )
            assert not any(
                "d7_host_telemetry.py run" in str(step.get("run", ""))
                for step in _steps(_workflow(filename), job)
            )


def test_every_dispatch_keeps_memory_distinct_and_resolves_off_before_native_setup() -> None:
    for filename, jobs in MEASURED_JOBS.items():
        inputs = _dispatch_inputs(_load_workflows()[filename])
        host = _mapping(inputs["host_telemetry"], "host choice")
        memory = _mapping(inputs["memory_profiling"], "memory choice")
        assert host["default"] == "rust" and host["options"] == ["rust", "legacy", "off"]
        assert memory["default"] == "inherit" and memory["options"] == ["inherit", "on", "off"]
        workflow = _workflow(filename)
        for job in jobs:
            steps = _steps(workflow, job)
            resolver = _step(workflow, job, "id", "host_telemetry")
            script = str(resolver["run"])
            assert 'host_telemetry_control.py "$REQUESTED" --config-root config' in script
            assert 'IDHAZH_HOST_TELEMETRY_MODE=$MODE" >> "$GITHUB_ENV"' in script
            assert 'mode=$MODE" >> "$GITHUB_OUTPUT"' in script
            native = [
                step for step in steps
                if _is_host_crate_cache(step)
                or step.get("name") == "Select the pinned host toolchain"
                or step.get("uses") in (
                    "./.github/actions/d7-host-telemetry",
                    "./.github/actions/download-host-telemetry",
                )
            ]
            assert native
            for step in native:
                assert steps.index(resolver) < steps.index(step)
                assert _normalize_condition(step["if"], "native setup") == (
                    "env.IDHAZH_HOST_TELEMETRY_MODE == 'rust'"
                )
            producer = next(
                step for step in steps if "d7_host_telemetry.py run" in str(step.get("run", ""))
            )
            assert '--mode "$IDHAZH_HOST_TELEMETRY_MODE"' in str(producer["run"])
            for step in steps:
                script = str(step.get("run", ""))
                if "run fingerprint" in script or "run job-clock" in script:
                    assert "IDHAZH_HOST_TELEMETRY_MODE == 'legacy'" in str(step.get("if", ""))
                if "memory_sampler.py" in script:
                    assert (
                        "IDHAZH_HOST_TELEMETRY_MODE == 'legacy'" in str(step.get("if", ""))
                        or "IDHAZH_HOST_TELEMETRY_MODE != 'off'" in str(step.get("if", ""))
                    )


def test_off_shards_keep_ordinary_publication_without_a_native_receipt() -> None:
    digest = _workflow("digest.yml")
    for name in ("Record what this shard measured", "Commit what this shard measured"):
        condition = _normalize_condition(
            _step(digest, "work", "name", name)["if"], "ordinary publication"
        )
        assert "IDHAZH_HOST_TELEMETRY_MODE == 'off'" in condition
        assert "IDHAZH_HOST_TELEMETRY_VERIFIED == '1'" in condition
    bench = _step(_workflow("measure.yml"), "llama-bench", "name", "Benchmark the candidate")
    script = str(bench["run"])
    assert script.index('if [ "$IDHAZH_HOST_TELEMETRY_MODE" != off ]') < script.index(
        "memory_profiling_control.py"
    )


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
    step_environment = step["env"]
    step_run = step["run"]
    assert isinstance(step_environment, dict)
    assert isinstance(step_run, str)
    assert step_environment["IDHAZH_D7_LIVE_TEST"] == "1"
    assert "backend/tests/test_d7_family_lifecycle.py" in step_run
    assert "-n 0" in step_run
    text = (ROOT / ".github/workflows/rust-host-telemetry.yml").read_text(encoding="utf-8")
    assert "persist-credentials: false" in text
    assert "backend/var/d7-family-tests.xml" in text
    assert "publish_to_repo" not in text
    assert "git push" not in text
