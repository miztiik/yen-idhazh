"""How does one manual run own both services, score once and retain safe evidence?"""

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

import httpx
from pydantic import ValidationError

from .call_local_api import loopback_url
from .contracts.base import SCHEMA_VERSION
from .contracts.host_profile_reader import TaskIdentity
from .contracts.service_settings import ServiceSettings, StartupContext
from .contracts.workflow_control import ApiReady, HostReady, StartupPacket
from .contracts.workflow_report import ServiceShutdown, WorkflowReport
from .fail_manual_evaluation import WorkflowFailure
from .load_manual_settings import ManualSettings, load_manual_settings
from .load_settings import SettingsLoadError, load_settings
from .observe_manual_evaluation import (
    ManualObservation,
    observe_manual_evaluation,
    wait_owned_health,
)
from .own_services import OwnedService
from .read_manual_inputs import read_manual_inputs
from .report_evaluation import (
    REPORT_DIRECTORY,
    build_report,
    build_resource_evidence,
    render_report,
    write_report,
)
from .resolve_ids import create_execution_id


async def run_manual_evaluation(
    root: Path,
    settings: ServiceSettings,
    manual: ManualSettings,
) -> WorkflowReport:
    observation = ManualObservation()
    services: list[OwnedService] = []
    shutdown = ServiceShutdown(hhem_stopped=None, host_stopped=None, worker_exit_confirmed=None)
    profile_timeout_ms = settings.listener.body_read_timeout_ms
    try:
        request = read_manual_inputs(settings, manual)
        if request.request_id is None or request.correlation_id is None:
            raise WorkflowFailure("INPUT_INVALID", "input")
        run_id = os.environ.get("GITHUB_RUN_ID", request.request_id)
        context = StartupContext(
            run_id=run_id,
            pipeline_name=manual.pipeline_name,
            task_name=manual.task_name,
        )
        identity = TaskIdentity(
            pipeline_name=manual.pipeline_name,
            task_name=manual.task_name,
            run_id=run_id,
            request_id=request.request_id,
            correlation_id=request.correlation_id,
        )
        api = OwnedService(
            "hhem",
            [sys.executable, "-m", "hhem_evaluator.serve_owned_api", "--root", str(root)],
            root,
            StartupPacket(
                version=SCHEMA_VERSION, startup_id=create_execution_id(), context=context
            ),
            settings,
            manual,
        )
        services.append(api)
        api_ready = await asyncio.to_thread(api.wait_ready, settings.worker.startup_timeout_ms)
        if not isinstance(api_ready, ApiReady):
            raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "startup", "hhem")
        host_url: str | None = None
        try:
            bun = shutil.which("bun")
            if bun is None:
                raise WorkflowFailure("STARTUP_FAILED", "startup", "host")
            host = OwnedService(
                "host",
                [
                    bun,
                    "run",
                    "--no-install",
                    str(root / "services" / "hhem-evaluator" / "scripts" / "serve-host-probes.ts"),
                ],
                root,
                StartupPacket(
                    version=SCHEMA_VERSION, startup_id=create_execution_id(), context=context
                ),
                settings,
                manual,
            )
            services.append(host)
            host_ready = await asyncio.to_thread(
                host.wait_ready, settings.worker.startup_timeout_ms
            )
            if not isinstance(host_ready, HostReady):
                raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "startup", "host")
            host_url = loopback_url(host_ready.host, host_ready.port)
            profile_timeout_ms = host_ready.lifecycle_timeout_ms + manual.http_connect_timeout_ms
        except WorkflowFailure as failure:
            observation.errors.append(failure.error)
        api_url = loopback_url(settings.listener.host, settings.listener.port)
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
            health = await wait_owned_health(
                client, api_url, api_ready.service_instance_id, settings, manual
            )
            api.check_alive()
            await observe_manual_evaluation(
                client,
                api_url,
                host_url,
                health,
                identity,
                request,
                settings,
                manual,
                profile_timeout_ms,
                observation,
            )
            result = observation.evaluation
            if result is not None and result.terminal_event_id is not None:
                await asyncio.to_thread(
                    api.confirm_terminal, result.terminal_event_id, result.execution_id
                )
            for service in services:
                service.check_alive()
    except WorkflowFailure as failure:
        observation.errors.append(failure.error)
    except (httpx.HTTPError, OSError):
        observation.errors.append(WorkflowFailure("HTTP_FAILED", "cleanup").error)
    except (ValueError, ValidationError):
        observation.errors.append(WorkflowFailure("INPUT_INVALID", "input").error)
    finally:
        # Profile closing above precedes both service stops, including error paths.
        for service in reversed(services):
            timeout_ms = (
                settings.worker.shutdown_timeout_ms
                if service.service == "hhem"
                else profile_timeout_ms
            )
            try:
                stopped = await asyncio.to_thread(service.close, timeout_ms)
                if service.service == "hhem":
                    shutdown = shutdown.model_copy(
                        update={
                            "worker_exit_confirmed": stopped.worker_exit_confirmed,
                        }
                    )
            except WorkflowFailure as failure:
                observation.errors.append(failure.error)
            except OSError:
                observation.errors.append(
                    WorkflowFailure("SERVICE_STOP_FAILED", "cleanup", service.service).error
                )
            finally:
                shutdown = shutdown.model_copy(
                    update={
                        f"{service.service}_stopped": service.process.poll() is not None,
                    }
                )
    measurement = observation.measurement
    final_worker = observation.final_health.worker if observation.final_health is not None else None
    resources = build_resource_evidence(measurement, final_worker, shutdown)
    return build_report(observation.evaluation, resources, observation.errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        manual = load_manual_settings(root)
        settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
        report = asyncio.run(run_manual_evaluation(root, settings, manual))
        write_report(report, root / REPORT_DIRECTORY)
        summary = render_report(report)
        if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(summary)
        sys.stdout.write(summary)
        sys.stdout.flush()
    except (ValueError, ValidationError, SettingsLoadError):
        parser.exit(1, "The committed manual evaluation settings or report are invalid.\n")
    except OSError:
        parser.exit(1, "The body-free report could not be written.\n")
    raise SystemExit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
