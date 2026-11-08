"""How does one visible model phase retain work before closing its children?"""

import asyncio
import contextlib
import math
import signal
import sys
import time
from pathlib import Path

import httpx
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.api_settings import (
    load_api_configuration,
    resolve_scorer_api_settings,
)
from summary_evaluator.serve_http.contracts.api_deployment_settings import ApiDeploymentSettings
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings

from .contracts import (
    WORKFLOW_VERSION,
    GenerationReceipt,
    Hardware,
    PhaseName,
    PipelineError,
)
from .control import HostReady, StartupPacket
from .evaluate_pair import EvaluatorOutcomes, evaluate_pair
from .evaluation import bind_evaluations, read_owned_health
from .failures import WorkflowError
from .generation import generate_summary, read_turn_markers
from .inputs import read_manual_inputs
from .llama import OwnedLlama
from .model_selection import verify_staged_selection
from .phase_contracts import PhaseEvidence
from .phase_result import build_evidence
from .phase_services import PhaseServices, ScorerService
from .phase_services import guard_work as guard_work
from .preparation import read_prepared
from .scorer_control import SCORER_CONTROL_VERSION, ScorerReady, ScorerStartupPacket
from .services import OwnedService
from .settings import load_pipeline_settings
from .storage import read_generation_result, read_phase_result, write_result


async def collect_phase(root: Path, phase: PhaseName) -> PhaseEvidence:
    pipeline = load_pipeline_settings(root)
    configuration = (
        load_api_configuration(root / "config" / "summary-evals" / "api.json")
        if phase == "evaluation"
        else None
    )
    if configuration is not None and not isinstance(configuration, ApiDeploymentSettings):
        raise WorkflowError("INPUT_INVALID", "input")
    hhem_api = resolve_scorer_api_settings(configuration, "hhem") if configuration else None
    unieval_api = resolve_scorer_api_settings(configuration, "unieval") if configuration else None
    settings: ServiceSettings | None = (
        load_settings(
            root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json", hhem_api
        )
        if hhem_api is not None
        else None
    )
    prepared, selected = read_prepared(root)
    if prepared.status != "complete":
        if prepared.errors:
            error = prepared.errors[0]
            raise WorkflowError(error.code, error.phase, error.service, error.http_status)
        raise WorkflowError("ASSET_FAILED", "preparation")
    inputs = read_manual_inputs(pipeline)
    directory = root / pipeline.output_directory
    scripts = root / "tools" / "summary-eval"
    destination = directory / (
        "generation-phase.json" if phase == "generation" else "evaluation.json"
    )
    services = PhaseServices(prepared.run)
    outcomes = EvaluatorOutcomes()
    requests: tuple[EvaluateRequest, UnievalRequest] | None = None
    receipt: GenerationReceipt | None = None
    receipt_sha256: str | None = None
    hardware: Hardware | None = None
    errors: list[PipelineError] = []
    unieval_settings: UnievalSettings | None = None

    def evidence() -> PhaseEvidence:
        return build_evidence(
            outcomes.hhem,
            hardware,
            services.machine,
            services.shutdown(),
            errors,
            run=prepared.run,
            phase=phase,
            servers=tuple(services.servers),
            generation_sha256=receipt_sha256,
            reference_summary_sha256=prepared.reference_summary_sha256,
            unieval=outcomes.unieval,
            scorer_apis=tuple(api.evidence() for api in services.scorer_apis.values()),
            evaluation_request_id=requests[0].request_id if requests else None,
            evaluation_correlation_id=requests[0].correlation_id if requests else None,
        )

    try:
        if phase == "evaluation":
            if settings is None or hhem_api is None or unieval_api is None:
                raise WorkflowError("RECEIPT_INVALID", "input")
            receipt, receipt_sha256 = read_generation_result(
                directory / "generation.json", pipeline.max_response_bytes
            )
            previous = read_phase_result(
                directory / "generation-phase.json", pipeline.max_response_bytes
            )
            requests = bind_evaluations(
                prepared, inputs, receipt, previous, generation_sha256=receipt_sha256
            )
            unieval_settings = load_unieval_settings(root, unieval_api)
            services.scorer_apis = {
                "hhem": ScorerService("hhem", hhem_api, settings.worker),
                "unieval": ScorerService("unieval", unieval_api, unieval_settings.worker),
            }
        packet = StartupPacket(
            version=WORKFLOW_VERSION,
            startup_id=create_execution_id(),
            context=StartupContext(
                run_id=f"{prepared.run.started_at:%Y-%m-%d}-{prepared.run.run_id}",
                pipeline_name=pipeline.pipeline_name,
                task_name=f"{pipeline.task_name}-{phase}",
            ),
            git_sha=prepared.run.git_sha,
            attempt=prepared.run.attempt,
            request_id=requests[0].request_id if requests is not None else create_execution_id(),
            correlation_id=(
                requests[0].correlation_id if requests is not None else create_execution_id()
            ),
            run=prepared.run,
            phase=phase,
        )
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
            if phase == "generation":
                verify_staged_selection(directory, selected)
                services.native = OwnedLlama(root, prepared, selected, pipeline)
                services.native.start()
                await services.native.wait_ready(client)
            else:
                # Construct both children before the first readiness wait.
                for api in services.scorer_apis.values():
                    api.started = time.monotonic()
                    try:
                        api.owner = OwnedService(
                            "api",
                            [
                                sys.executable, str(scripts / "serve.py"), "--root", str(root),
                            ],
                            root,
                            ScorerStartupPacket(
                                version=SCORER_CONTROL_VERSION,
                                scorer=api.scorer,
                                startup=packet.model_copy(
                                    update={"startup_id": create_execution_id()}
                                ),
                            ),
                            api.worker_settings,
                            pipeline,
                            api_settings=api.api_settings,
                        )
                    except WorkflowError as error:
                        api.retain_error(error.error)
                        api.startup_ms = (time.monotonic() - api.started) * 1000
                    except (OSError, ValueError, TypeError):
                        api.retain_error(WorkflowError("STARTUP_FAILED", "startup", "api").error)
                        api.startup_ms = (time.monotonic() - api.started) * 1000

                async def wait_scorer(api: ScorerService) -> None:
                    if api.owner is None or api.started is None:
                        return
                    deadline = api.started + api.worker_settings.startup_timeout_ms / 1000
                    try:
                        remaining_ms = math.ceil((deadline - time.monotonic()) * 1000)
                        if remaining_ms <= 0:
                            raise WorkflowError("STARTUP_FAILED", "startup", "api")
                        waiting = asyncio.create_task(
                            asyncio.to_thread(api.owner.wait_ready, remaining_ms)
                        )
                        try:
                            ready = await asyncio.shield(waiting)
                        except asyncio.CancelledError:
                            # Join the bounded control read before close drains the same channel.
                            try:
                                await waiting
                            except WorkflowError as error:
                                api.retain_error(error.error)
                            raise
                        if not isinstance(ready, ScorerReady):
                            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", "api")
                        await guard_work(
                            read_owned_health(
                                client,
                                api.origin,
                                ready.service_instance_id,
                                api.worker_settings,
                                pipeline,
                                api.scorer,
                                deadline=deadline,
                                observe=api.observe_health,
                            ),
                            api.owner,
                            pipeline,
                        )
                    except WorkflowError as error:
                        api.retain_error(error.error)
                    except asyncio.CancelledError:
                        api.retain_error(WorkflowError("TASK_CANCELLED", "startup", "api").error)
                        raise
                    except (OSError, ValueError, KeyError, TypeError):
                        api.retain_error(WorkflowError("STARTUP_FAILED", "startup", "api").error)
                    finally:
                        api.startup_ms = (time.monotonic() - api.started) * 1000

                await asyncio.gather(
                    *(wait_scorer(api) for api in services.scorer_apis.values())
                )
            try:
                host = OwnedService(
                    "host",
                    ["bun", "run", "--no-install", str(scripts / "machine-task.ts"), str(root)],
                    root,
                    packet,
                    None,
                    pipeline,
                )
                services.host = host
                host_ready = await asyncio.to_thread(
                    host.wait_ready, pipeline.host_startup_timeout_ms
                )
                if not isinstance(host_ready, HostReady):
                    raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", "host")
                hardware = host_ready.hardware
                if hardware.status != "collected" or not host_ready.profile_started:
                    errors.append(WorkflowError("HOST_FAILED", "host", "host").error)
            except WorkflowError as error:
                errors.append(error.error)
            if phase == "generation":
                native = services.native
                if native is None or native.loaded is None:
                    raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "generation", "llama")
                markers = await guard_work(
                    read_turn_markers(client, selected, pipeline), native, pipeline
                )
                receipt = await guard_work(
                    generate_summary(
                        client,
                        inputs,
                        prepared,
                        selected,
                        native.loaded,
                        markers,
                        pipeline,
                    ),
                    native,
                    pipeline,
                )
                # Save the accepted answer before any instrument or service cleanup.
                receipt_sha256 = write_result(directory / "generation.json", receipt)
            else:
                if (
                    requests is None
                    or settings is None
                    or unieval_settings is None
                ):
                    raise WorkflowError("RECEIPT_INVALID", "input")
                await evaluate_pair(
                    client,
                    requests,
                    services.scorer_apis["hhem"],
                    services.scorer_apis["unieval"],
                    settings,
                    unieval_settings,
                    pipeline,
                    outcomes,
                    errors,
                    lambda: write_result(destination, evidence()),
                )
    except WorkflowError as error:
        errors.append(error.error)
    except asyncio.CancelledError:
        errors.append(WorkflowError("TASK_CANCELLED", phase).error)
    except (OSError, ValueError, KeyError, TypeError):
        errors.append(
            WorkflowError(
                "GENERATION_FAILED" if phase == "generation" else "EVALUATION_FAILED", phase
            ).error
        )
    finally:
        if phase == "generation" and (receipt is None or receipt.status != "complete"):
            receipt = GenerationReceipt(
                version=WORKFLOW_VERSION,
                run=prepared.run,
                selected=prepared.selected,
                loaded=services.native.loaded if services.native is not None else None,
                source_sha256=prepared.source_sha256,
                reference_summary_sha256=prepared.reference_summary_sha256,
                summary_sha256=None,
                summary_text=None,
                status="failed",
                errors=tuple(errors) or (WorkflowError("GENERATION_FAILED", "generation").error,),
            )
            try:
                receipt_sha256 = write_result(directory / "generation.json", receipt)
            except OSError:
                errors.append(WorkflowError("RESULT_WRITE_FAILED", "generation").error)
        work_complete = (
            receipt is not None and receipt.status == "complete"
            if phase == "generation"
            else (
                outcomes.hhem is not None
                and outcomes.hhem.status == "complete"
                and outcomes.unieval is not None
                and outcomes.unieval.status == "complete"
            )
        )
        await asyncio.to_thread(
            services.close,
            errors,
            work_complete,
            pipeline=pipeline,
        )
    result = evidence()
    write_result(destination, result)
    return result


def run_phase(root: Path, phase: PhaseName) -> PhaseEvidence:
    async def run() -> PhaseEvidence:
        loop, task = asyncio.get_running_loop(), asyncio.current_task()
        previous = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(
                signum,
                lambda *_: (
                    loop.call_soon_threadsafe(task.cancel)
                    if task is not None and not task.cancelling()
                    else None
                ),
            )
        try:
            return await collect_phase(root, phase)
        finally:
            for signum, handler in previous.items():
                with contextlib.suppress(ValueError):
                    signal.signal(signum, handler)

    return asyncio.run(run())
