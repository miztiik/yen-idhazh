"""Which services, evaluation and host observations belong to this workflow run?"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx

from hhem_evaluator.contracts.base import SCHEMA_VERSION, OutcomeStatus
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_settings import StartupContext
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.resolve_ids import create_execution_id

from .contracts import Hardware, PipelineError, PipelineEvidence, ServiceShutdown
from .control import ApiReady, HostReady, StartupPacket
from .evaluation import evaluate, read_owned_health
from .failures import WorkflowFailure
from .host_reader import MachineUsage, measurement_complete
from .http import loopback_url
from .inputs import read_manual_inputs
from .services import OwnedService
from .settings import load_pipeline_settings


@contextmanager
def progress(name: str) -> Iterator[None]:
    print(f"::group::{name}", flush=True)
    try:
        yield
    finally:
        print("::endgroup::", flush=True)


def build_evidence(
    evaluation: EvaluationResult | None,
    hardware: Hardware | None,
    machine: MachineUsage | None,
    shutdown: ServiceShutdown,
    errors: list[PipelineError],
) -> PipelineEvidence:
    complete = (
        evaluation is not None
        and evaluation.status == "complete"
        and hardware is not None
        and hardware.status == "collected"
        and measurement_complete(machine)
        and not errors
        and shutdown.hhem_stopped is True
        and shutdown.host_stopped is True
        and shutdown.worker_exit_confirmed is True
    )
    status: OutcomeStatus = (
        "complete"
        if complete
        else ("partial" if evaluation is not None and evaluation.hhem is not None else "failed")
    )
    return PipelineEvidence(
        version=SCHEMA_VERSION,
        status=status,
        evaluation=evaluation,
        hardware=hardware,
        machine=machine,
        shutdown=shutdown,
        errors=tuple(errors),
        unieval="not_implemented",
    )


async def collect(root: Path) -> PipelineEvidence:
    settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
    pipeline = load_pipeline_settings(root)
    api: OwnedService | None = None
    host: OwnedService | None = None
    evaluation: EvaluationResult | None = None
    hardware: Hardware | None = None
    machine: MachineUsage | None = None
    hhem_stopped: bool | None = None
    host_stopped: bool | None = None
    errors: list[PipelineError] = []
    try:
        request = read_manual_inputs(settings, pipeline)
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        context = StartupContext(
            run_id=f"{day}-{os.environ['GITHUB_RUN_ID']}",
            pipeline_name=pipeline.pipeline_name,
            task_name=pipeline.task_name,
        )
        packet = StartupPacket(
            version=SCHEMA_VERSION,
            startup_id=create_execution_id(),
            context=context,
            git_sha=os.environ["GITHUB_SHA"],
            attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
            request_id=request.request_id,
            correlation_id=request.correlation_id,
        )
        directory = root / ".github" / "scripts" / "summary-eval-hhem"
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
            with progress("Starting HHEM API"):
                api = OwnedService(
                    "hhem",
                    [sys.executable, str(directory / "serve.py"), "--root", str(root)],
                    root,
                    packet,
                    settings,
                    pipeline,
                )
                ready = await asyncio.to_thread(api.wait_ready, settings.worker.startup_timeout_ms)
                if not isinstance(ready, ApiReady):
                    raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "startup", "hhem")
            base_url = loopback_url(settings.listener.host, settings.listener.port)
            with progress("Checking HHEM API health"):
                await read_owned_health(
                    client, base_url, ready.service_instance_id, settings, pipeline
                )
                print("Health check OK", flush=True)
            with progress("Starting shared hardware and whole-machine measurement"):
                try:
                    host = OwnedService(
                        "host",
                        ["bun", "run", "--no-install", str(directory / "measure-host.ts")],
                        root,
                        packet,
                        settings,
                        pipeline,
                    )
                    host_ready = await asyncio.to_thread(
                        host.wait_ready,
                        settings.worker.startup_timeout_ms,
                    )
                    if not isinstance(host_ready, HostReady):
                        raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "startup", "host")
                    hardware = host_ready.hardware
                    if hardware.status == "failed" or not host_ready.profile_started:
                        errors.append(WorkflowFailure("HOST_FAILED", "host", "host").error)
                except WorkflowFailure as failure:
                    errors.append(failure.error)
            with progress("Doing HHEM summary evaluation"):
                api.check_alive()
                status, evaluation = await evaluate(client, base_url, request, settings, pipeline)
                if status != 200:
                    errors.append(
                        WorkflowFailure(
                            "EVALUATION_FAILED",
                            "evaluation",
                            "hhem",
                            status,
                        ).error
                    )
                api.confirm_terminal(evaluation.terminal_event_id, evaluation.execution_id)
                api.check_alive()
            with progress("Doing UniEval summary evaluation"):
                print("Not run - future task.", flush=True)
    except WorkflowFailure as failure:
        errors.append(failure.error)
    finally:
        with progress("Stopping measurement and owned HHEM API"):
            if host is not None:
                try:
                    if host.ready is not None:
                        host.finish_measurement(
                            "success"
                            if evaluation is not None and evaluation.status == "complete"
                            else "error"
                        )
                except WorkflowFailure as failure:
                    errors.append(failure.error)
                try:
                    timeout = (
                        host.ready.lifecycle_timeout_ms + settings.worker.stop_grace_ms
                        if isinstance(host.ready, HostReady)
                        else settings.worker.shutdown_timeout_ms
                    )
                    await asyncio.to_thread(host.close, timeout)
                    host_stopped = True
                except WorkflowFailure as failure:
                    host_stopped = False
                    errors.append(failure.error)
                if host.stopped is not None:
                    machine = host.stopped.machine
            if api is not None:
                try:
                    await asyncio.to_thread(api.close, settings.worker.shutdown_timeout_ms)
                    hhem_stopped = True
                except WorkflowFailure as failure:
                    hhem_stopped = False
                    errors.append(failure.error)
    return build_evidence(
        evaluation,
        hardware,
        machine,
        ServiceShutdown(
            hhem_stopped=hhem_stopped,
            host_stopped=host_stopped,
            worker_exit_confirmed=(
                api.stopped.worker_exit_confirmed
                if api is not None and api.stopped is not None
                else None
            ),
        ),
        errors,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        evidence = asyncio.run(collect(root))
        directory = root / load_pipeline_settings(root).output_directory
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "evaluation.json.tmp"
        temporary.write_text(evidence.model_dump_json(), encoding="utf-8")
        temporary.replace(directory / "evaluation.json")
    except (OSError, ValueError, KeyError):
        print(json.dumps({"event": "summary_evaluation_failed", "reason": "invalid_run_setup"}))
        raise SystemExit(1) from None
    print(json.dumps({"event": "summary_evaluation_finished", "status": evidence.status}))
    raise SystemExit(0 if evidence.status == "complete" else 1)
