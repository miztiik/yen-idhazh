"""How are saved summaries scored through the maintained independent native APIs?"""

import asyncio
import os
from collections.abc import Sequence
from functools import partial
from pathlib import Path

import httpx
from local_api_host.propagate_trace_context import create_root_operation
from summary_evaluator.serve_http.api_settings import (
    load_api_configuration,
    resolve_scorer_api_settings,
)
from summary_evaluator.serve_http.contracts.api_deployment_settings import ApiDeploymentSettings
from summary_evaluator.serve_http.load_scorer_settings import (
    load_hhem_settings,
    load_unieval_settings,
)
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.unieval.prepare_unieval_resources import prepare_unieval_resources

from .contracts import WORKFLOW_VERSION, PipelineError
from .control import StartupPacket
from .evaluate_pair import evaluate_pair
from .failures import WorkflowError
from .phase_services import ScorerService
from .saved_requests import SavedSummary
from .settings import PipelineSettings
from .start_scorers import start_scorers
from .storage import write_result


def save_native_scores(directory: Path, summary: SavedSummary) -> None:
    for name, result in (
        ("hhem", summary.outcomes.hhem), ("unieval", summary.outcomes.unieval),
    ):
        if result is not None:
            write_result(directory / f"{summary.key}-{name}.json", result)


async def score_saved_summaries(
    root: Path,
    summaries: Sequence[SavedSummary],
    directory: Path,
    pipeline: PipelineSettings,
    errors: list[PipelineError],
) -> None:
    configuration = load_api_configuration(root / "config" / "summary-evals" / "api.json")
    if not isinstance(configuration, ApiDeploymentSettings):
        raise WorkflowError("INPUT_INVALID", "input")
    hhem_api = resolve_scorer_api_settings(configuration, "hhem")
    unieval_api = resolve_scorer_api_settings(configuration, "unieval")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
            output.write(f"log_directory={hhem_api.log_directory}\n")
    hhem = load_hhem_settings(
        root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json", hhem_api
    )
    unieval = load_unieval_settings(root, unieval_api)
    apis = (
        ScorerService("hhem", hhem_api, hhem.worker),
        ScorerService("unieval", unieval_api, unieval.worker),
    )
    packet = StartupPacket(
        version=WORKFLOW_VERSION,
        startup_id=create_execution_id(),
        context=StartupContext(
            run_id=os.environ.get("GITHUB_RUN_ID"),
            pipeline_name=os.environ.get("GITHUB_WORKFLOW") or pipeline.pipeline_name,
            task_name=os.environ.get("GITHUB_JOB") or pipeline.task_name,
        ),
        git_sha=os.environ.get("GITHUB_SHA"),
        attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        request_id=create_execution_id(),
        correlation_id=create_execution_id(),
    )
    operation = create_root_operation()
    try:
        try:
            with quiet_model_output():
                prepare_unieval_resources(root, unieval, include_weights=True)
        except (OSError, ValueError, SystemExit, httpx.HTTPError):
            apis[1].retain_error(WorkflowError("ASSET_FAILED", "preparation", "unieval").error)
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
            await start_scorers(root, client, apis, packet, pipeline, operation)
            for summary in summaries:
                await evaluate_pair(
                    client, summary.requests(), *apis, hhem, unieval, pipeline,
                    summary.outcomes, summary.errors,
                    partial(save_native_scores, directory, summary),
                    operation_metadata=operation,
                )
    finally:
        await asyncio.gather(*(asyncio.to_thread(api.close) for api in apis))
        for api in apis:
            errors.extend(api.errors)
