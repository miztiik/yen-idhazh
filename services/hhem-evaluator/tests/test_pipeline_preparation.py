"""Retain real pre-network preparation failures without inventing model-phase results."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import PipelineEvidence, PreparedRun
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.model_selection import select_model, stage_configuration
from summary_eval_pipeline.phases import collect_phase
from summary_eval_pipeline.preparation import prepare_assets, prepare_run, read_prepared
from summary_eval_pipeline.report_task import collect_results
from summary_eval_pipeline.settings import load_pipeline_settings
from utilities.model_runtime import install_runtime

from .contract_examples import REPOSITORY
from .generation_cases import handoff_case, selected_root


def prepare_dispatch(root: Path, monkeypatch: pytest.MonkeyPatch) -> ManualInputs:
    selected_root(root)
    inputs, prepared, _ = handoff_case()
    event = root / "event.json"
    event.write_text(json.dumps({"inputs": inputs.model_dump()}), encoding="utf-8")
    for key, value in {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_RUN_ID": prepared.run.run_id,
        "GITHUB_RUN_ATTEMPT": str(prepared.run.attempt),
        "GITHUB_SHA": prepared.run.git_sha,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(root)
    return inputs


def test_existing_runtime_utility_refuses_a_missing_token_before_network_or_asset_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "llama-cpp-pin.json").write_bytes(
        (REPOSITORY / "config" / "llama-cpp-pin.json").read_bytes()
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit) as failure:
        install_runtime()
    assert failure.value.code == "GITHUB_TOKEN must be set to look the pinned release up"
    assert not (tmp_path / "backend").exists()


@pytest.mark.parametrize("failure", ["missing_token", "missing_named_input", "invalid_runtime_pin"])
def test_real_preparation_failure_is_saved_and_reported_with_both_model_phases_not_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    prepare_dispatch(tmp_path, monkeypatch)
    token = "PrivatePreparationTokenCanary"
    if failure == "missing_token":
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        code = "ASSET_AUTH_MISSING"
    else:
        monkeypatch.setenv("GITHUB_TOKEN", token)
        if failure == "missing_named_input":
            # The generated root deliberately lacks the next named configuration input.
            assert not (tmp_path / "config" / "hono-server.json").exists()
        else:
            for name in (
                "hono-server.json",
                "host-fingerprints.json",
                "host-probes.json",
                "ledgers.json",
                "typescript-event-sources.json",
            ):
                (tmp_path / "config" / name).write_bytes(
                    (REPOSITORY / "config" / name).read_bytes()
                )
            (tmp_path / "config" / "llama-cpp-pin.json").write_text(
                json.dumps({"build": "../PrivateRuntimePinCanary"}),
                encoding="utf-8",
            )
        code = "ASSET_FAILED"
    with pytest.raises(WorkflowError) as original:
        prepare_assets(tmp_path)
    assert original.value.error.code == code
    prepared, _ = read_prepared(tmp_path)
    assert prepared.status == "failed" and prepared.errors == (original.value.error,)
    evidence = collect_results(tmp_path)
    assert evidence.status == "failed" and evidence.prepared == prepared
    assert evidence.generation is None and evidence.generation_phase is None
    assert evidence.evaluation_phase is None and evidence.errors == ()
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    assert not (directory / "generation.json").exists()
    assert not (directory / "evaluation.json").exists()
    assert not (directory / "logs").exists()
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / ".github" / "scripts" / "summary-eval-tests" / "report.py"),
            "--root",
            str(tmp_path),
        ],
        env={
            **os.environ,
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_SERVER_URL": "https://example.test",
            "GITHUB_REPOSITORY": "fixture/repository",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert '"event": "summary_report_created"' in result.stdout, result.stdout + result.stderr
    report = (directory / "report.md").read_text(encoding="utf-8")
    assert (directory / "report.md").read_bytes() == summary.read_bytes()
    assert "| Preparation | failed |" in report
    assert "| Generation | Not run |" in report and "| HHEM | Not run |" in report
    assert f"preparation / caller: {code}" in report
    assert "RECEIPT_INVALID" not in report
    saved = PipelineEvidence.model_validate_json((directory / "results.json").read_bytes())
    assert saved == evidence
    assert token not in result.stdout + result.stderr + report + saved.model_dump_json()
    assert "PrivateRuntimePinCanary" not in result.stdout + result.stderr + report


def test_unfinished_preparation_is_not_assumed_complete_or_reported_as_a_missing_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_dispatch(tmp_path, monkeypatch)
    prepared, _ = prepare_run(tmp_path)
    assert prepared.status == "pending" and prepared.errors == ()
    evidence = collect_results(tmp_path)
    assert evidence.status == "failed" and evidence.prepared == prepared
    assert evidence.errors == () and evidence.generation is None
    assert evidence.generation_phase is None and evidence.evaluation_phase is None


def test_staged_machine_configuration_needs_no_feed_settings(tmp_path: Path) -> None:
    selected_root(tmp_path)
    for name in (
        "hono-server.json",
        "host-fingerprints.json",
        "host-probes.json",
        "ledgers.json",
        "typescript-event-sources.json",
    ):
        (tmp_path / "config" / name).write_bytes(
            (REPOSITORY / "config" / name).read_bytes()
        )
    selected = select_model(tmp_path, "")
    directory = tmp_path / "runtime"
    stage_configuration(tmp_path, directory, selected)
    assert (directory / "config" / "hono-server.json").read_bytes() == (
        tmp_path / "config" / "hono-server.json"
    ).read_bytes()
    probes = json.loads((directory / "config" / "host-probes.json").read_bytes())
    assert probes["task_profile"]["enabled"] is True
    assert not (tmp_path / "config" / "feed-ingest-plan-service.json").exists()
    assert not (directory / "config" / "feed-ingest-plan-service.json").exists()


def test_reference_identity_is_saved_before_generation_and_changed_reference_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = prepare_dispatch(tmp_path, monkeypatch)
    prepared, _ = prepare_run(tmp_path)
    from summary_eval_pipeline.contracts import text_sha256

    assert prepared.status == "pending"
    assert prepared.reference_summary_sha256 == text_sha256(inputs.reference_summary_text)
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    assert not (directory / "generation.json").exists()
    assert inputs.reference_summary_text not in (directory / "run.json").read_text(encoding="utf-8")
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {"inputs": {**inputs.model_dump(), "reference_summary_text": "Changed reference."}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError) as failure:
        read_prepared(tmp_path)
    assert failure.value.error.code == "RECEIPT_INVALID"


@pytest.mark.parametrize("reference", [None, "", " \n", True, "\ud800"])
def test_invalid_reference_blocks_preparation_before_a_model_or_asset_can_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reference: object,
) -> None:
    inputs = prepare_dispatch(tmp_path, monkeypatch)
    payload = inputs.model_dump()
    if reference is None:
        del payload["reference_summary_text"]
    else:
        payload["reference_summary_text"] = reference
    (tmp_path / "event.json").write_text(json.dumps({"inputs": payload}), encoding="utf-8")
    with pytest.raises(WorkflowError) as failure:
        prepare_assets(tmp_path)
    assert failure.value.error.code == "INPUT_INVALID"
    assert not (tmp_path / load_pipeline_settings(REPOSITORY).output_directory).exists()


@pytest.mark.parametrize("phase", ["generation", "evaluation"])
def test_failed_preparation_refuses_each_model_phase_before_starting_any_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: Literal["generation", "evaluation"],
) -> None:
    prepare_dispatch(tmp_path, monkeypatch)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(WorkflowError):
        prepare_assets(tmp_path)
    with pytest.raises(WorkflowError) as failure:
        asyncio.run(collect_phase(tmp_path, phase))
    assert failure.value.error.code == "ASSET_AUTH_MISSING"
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    assert not (directory / "logs").exists()
    assert not (directory / "generation.json").exists()
    assert not (directory / "evaluation.json").exists()


@pytest.mark.parametrize(
    "change", ["missing_status", "failed_without_error", "complete_with_error"]
)
def test_preparation_reader_never_assumes_assets_were_prepared(change: str) -> None:
    _, prepared, _ = handoff_case()
    value = prepared.model_dump(mode="json")
    if change == "missing_status":
        del value["status"]
        del value["errors"]
    elif change == "failed_without_error":
        value["status"] = "failed"
    else:
        value["errors"] = [
            WorkflowError("ASSET_FAILED", "preparation").error.model_dump(mode="json")
        ]
    with pytest.raises(ValidationError):
        PreparedRun.model_validate_json(json.dumps(value))
