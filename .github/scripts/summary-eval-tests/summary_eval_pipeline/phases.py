"""How does one visible model phase retain work before closing its children?"""

import asyncio
import contextlib
import signal
import sys
import time
from collections.abc import Awaitable
from pathlib import Path

import httpx
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
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
    PhaseEvidence,
    PhaseName,
    PipelineError,
    text_sha256,
)
from .control import ApiReady, HostReady, StartupPacket
from .evaluate_pair import EvaluatorOutcomes, evaluate_pair
from .evaluation import bind_evaluations, read_owned_health
from .failures import WorkflowError
from .generation import generate_summary, read_turn_markers
from .http import loopback_url
from .inputs import read_manual_inputs
from .llama import OwnedLlama
from .model_selection import verify_staged_selection
from .phase_result import build_evidence
from .phase_services import PhaseServices
from .preparation import read_prepared
from .services import OwnedService
from .settings import PipelineSettings, load_pipeline_settings
from .storage import read_result, write_result


async def guard_work[Result](
    work: Awaitable[Result],
    service: OwnedService | OwnedLlama,
    pipeline: PipelineSettings,
) -> Result:
    async def watch() -> None:
        while True:
            service.check_alive()
            await asyncio.sleep(pipeline.poll_interval_ms / 1000)

    task, watcher = asyncio.ensure_future(work), asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait((task, watcher), return_when=asyncio.FIRST_COMPLETED)
        # A completed native result survives a subsequent child-exit observation.
        if task not in done:
            await watcher
        return await task
    finally:
        for pending in (task, watcher):
            pending.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)


async def collect_phase(root: Path, phase: PhaseName) -> PhaseEvidence:
    pipeline = load_pipeline_settings(root)
    shared: ApiSettings | None = (
        load_api_settings(root / "config" / "summary-evals" / "api.json")
        if phase == "evaluation"
        else None
    )
    settings: ServiceSettings | None = (
        load_settings(
            root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json", shared
        )
        if shared is not None
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
    scripts = root / ".github" / "scripts" / "summary-eval-tests"
    destination = directory / (
        "generation-phase.json" if phase == "generation" else "evaluation.json"
    )
    services = PhaseServices(prepared.run)
    outcomes = EvaluatorOutcomes()
    requests: tuple[EvaluateRequest, UnievalRequest] | None = None
    receipt: GenerationReceipt | None = None
    hardware: Hardware | None = None
    errors: list[PipelineError] = []
    unieval_settings: UnievalSettings | None = None
    origin: str | None = None

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
            generation_sha256=text_sha256(receipt.model_dump_json()) if receipt else None,
            reference_summary_sha256=prepared.reference_summary_sha256,
            unieval=outcomes.unieval,
            api_health=services.health,
            evaluation_request_id=requests[0].request_id if requests else None,
            evaluation_correlation_id=requests[0].correlation_id if requests else None,
        )

    try:
        if phase == "evaluation":
            if settings is None or shared is None:
                raise WorkflowError("RECEIPT_INVALID", "input")
            receipt = read_result(
                directory / "generation.json", GenerationReceipt, pipeline.max_response_bytes
            )
            previous = read_result(
                directory / "generation-phase.json", PhaseEvidence, pipeline.max_response_bytes
            )
            requests = bind_evaluations(
                prepared, inputs, receipt, previous, settings.listener.max_body_bytes
            )
            unieval_settings = load_unieval_settings(root, shared)
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
                if shared is None or settings is None or unieval_settings is None:
                    raise WorkflowError("RECEIPT_INVALID", "input")
                startup_timeout_ms = max(
                    settings.worker.startup_timeout_ms,
                    unieval_settings.worker.startup_timeout_ms,
                )
                started = time.monotonic()
                api = OwnedService(
                    "api",
                    [sys.executable, str(scripts / "serve.py"), "--root", str(root)],
                    root,
                    packet,
                    settings,
                    pipeline,
                )
                services.api = api
                services.api_started = started
                ready = await asyncio.to_thread(api.wait_ready, startup_timeout_ms)
                if not isinstance(ready, ApiReady):
                    raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", "api")
                origin = loopback_url(shared.listener.host, shared.listener.port)
                services.health = await guard_work(
                    read_owned_health(
                        client,
                        origin,
                        ready.service_instance_id,
                        settings,
                        pipeline,
                        ("hhem", "unieval"),
                        startup_timeout_ms,
                        errors=errors,
                    ),
                    api,
                    pipeline,
                )
                services.startup_ms = (time.monotonic() - started) * 1000
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
                write_result(directory / "generation.json", receipt)
            else:
                if (
                    requests is None
                    or settings is None
                    or unieval_settings is None
                    or services.api is None
                    or services.health is None
                    or origin is None
                ):
                    raise WorkflowError("RECEIPT_INVALID", "input")
                await guard_work(
                    evaluate_pair(
                        client,
                        origin,
                        requests,
                        services.health,
                        settings,
                        unieval_settings,
                        pipeline,
                        outcomes,
                        errors,
                        lambda: write_result(destination, evidence()),
                    ),
                    services.api,
                    pipeline,
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
                write_result(directory / "generation.json", receipt)
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
            settings,
            shared,
            errors,
            work_complete,
            unieval_settings,
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
