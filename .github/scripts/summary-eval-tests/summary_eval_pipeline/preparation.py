"""How are the selected run and pinned native assets prepared before generation?"""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.unieval.prepare_unieval_resources import prepare_unieval_resources
from utilities.model_runtime import download_model_files, install_runtime, verify_model_files

from .artifact_paths import write_artifact_paths
from .contracts import WORKFLOW_VERSION, PreparedRun, RunIdentity, text_sha256
from .failures import WorkflowError
from .inputs import read_manual_inputs
from .model_selection import SelectedModel, select_model, stage_configuration
from .settings import load_pipeline_settings
from .storage import read_result, write_result


def prepare_run(root: Path) -> tuple[PreparedRun, SelectedModel]:
    pipeline = load_pipeline_settings(root)
    inputs = read_manual_inputs(pipeline)
    selected = select_model(root, inputs.models_file)
    revision = (
        os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    )
    prepared = PreparedRun(
        version=WORKFLOW_VERSION,
        run=RunIdentity(
            run_id=os.environ.get("GITHUB_RUN_ID") or str(UUID(create_execution_id()).int),
            attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
            git_sha=revision,
            started_at=datetime.now(UTC),
        ),
        selected=selected.identity,
        source_sha256=text_sha256(inputs.source_text),
        reference_summary_sha256=text_sha256(inputs.reference_summary_text),
        status="pending",
        errors=(),
    )
    directory = root / pipeline.output_directory
    write_result(directory / "run.json", prepared)
    return prepared, selected


def read_prepared(root: Path) -> tuple[PreparedRun, SelectedModel]:
    pipeline = load_pipeline_settings(root)
    prepared = read_result(
        root / pipeline.output_directory / "run.json", PreparedRun, pipeline.max_response_bytes
    )
    inputs = read_manual_inputs(pipeline)
    selected = select_model(root, inputs.models_file)
    expected = (
        os.environ.get("GITHUB_RUN_ID", prepared.run.run_id),
        int(os.environ.get("GITHUB_RUN_ATTEMPT", str(prepared.run.attempt))),
        os.environ.get("GITHUB_SHA", prepared.run.git_sha),
    )
    if (
        expected != (prepared.run.run_id, prepared.run.attempt, prepared.run.git_sha)
        or selected.identity != prepared.selected
        or text_sha256(inputs.source_text) != prepared.source_sha256
        or text_sha256(inputs.reference_summary_text) != prepared.reference_summary_sha256
    ):
        raise WorkflowError("RECEIPT_INVALID", "input")
    return prepared, selected


def prepare_assets(root: Path, *, artifact_output: Path | None = None) -> None:
    prepared, selected = prepare_run(root)
    pipeline = load_pipeline_settings(root)
    directory = root / pipeline.output_directory
    failure: WorkflowError | None = None
    try:
        if artifact_output is not None:
            write_artifact_paths(pipeline, artifact_output)
        if not os.environ.get("GITHUB_TOKEN"):
            raise WorkflowError("ASSET_AUTH_MISSING", "preparation")
        stage_configuration(root, directory, selected)
        # Existing utilities derive all files, revisions, digests and native library assets.
        install_runtime()
        configuration = Path(load_pipeline_settings(root).output_directory) / "config"
        download_model_files(configuration)
        verify_model_files(configuration)
        shared = load_api_settings(root / "config" / "summary-evals" / "api.json")
        with quiet_model_output():
            prepare_unieval_resources(
                root, load_unieval_settings(root, shared), include_weights=True
            )
    except WorkflowError as error:
        failure = error
    except (OSError, ValueError, SystemExit, httpx.HTTPError):
        failure = WorkflowError("ASSET_FAILED", "preparation")
    outcome = PreparedRun.model_validate_json(
        prepared.model_copy(
            update={
                "status": "failed" if failure is not None else "complete",
                "errors": (failure.error,) if failure is not None else (),
            }
        ).model_dump_json()
    )
    write_result(directory / "run.json", outcome)
    if failure is not None:
        raise failure
