"""How does one explicitly selected scorer stay bound to its owner's private pipe?"""

import argparse
import asyncio
import contextlib
import os
import sys
import threading
from pathlib import Path

from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.configure_server import (
    create_server_config,
    report_startup_failure,
)
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings
from summary_evaluator.serve_http.serve_api import create_app

from .channels import OwnedChannels, open_owned_channels
from .scorer_control import SCORER_CONTROL_VERSION, ScorerStartFailed, ScorerStartupPacket
from .serve_scorer_lifetime import (
    emit_control,
    serve_scorer_lifetime,
    watch_parent_lifetime,
)
from .settings import load_pipeline_settings

__all__ = ["emit_control", "watch_parent_lifetime"]


async def serve_owned_api(
    root: Path,
    packet: ScorerStartupPacket,
    finished: threading.Event,
    channels: OwnedChannels,
    announced: threading.Event,
    *,
    api: ApiSettings,
    service_operation: OperationMetadata,
) -> None:
    if packet.phase != "evaluation":
        raise ValueError("Generation starts no scorer API")
    startup = packet.startup
    pipeline = load_pipeline_settings(root)
    events = EventWriter(
        api.logging,
        channels.events,
        directory=root / pipeline.output_directory / "logs",
        run_id=startup.run.run_id if startup.run is not None else startup.startup_id,
        attempt=startup.attempt,
        started_at=startup.run.started_at if startup.run is not None else None,
        scorer=packet.scorer,
        service_operation=service_operation,
        propagate_trace_context=api.propagate_trace_context,
    )
    app = create_app(
        api,
        load_hhem_settings(
            root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json", api
        )
        if packet.scorer == "hhem"
        else None,
        root,
        startup.context,
        writer=events,
    )
    config = create_server_config(app, api)
    try:
        listener = config.bind_socket()
    except (OSError, SystemExit):
        events.diagnostic(
            ApiDiagnosticData(
                component="api", action="failed", level="ERROR", code="LISTENER_BIND_FAILED"
            )
        )
        events.close()
        raise
    try:
        await serve_scorer_lifetime(
            app, api, packet, finished, channels, [listener], announced,
            control_max_bytes=pipeline.control_max_bytes,
        )
    finally:
        listener.close()
        events.close()


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    return parser


def main() -> None:
    parser = create_argument_parser()
    args = parser.parse_args()
    with open_owned_channels() as channels:
        packet: ScorerStartupPacket | None = None
        api: ApiSettings | None = None
        service_operation: OperationMetadata | None = None
        announced = threading.Event()
        try:
            root = args.root.resolve()
            manual = load_pipeline_settings(root)
            line = sys.stdin.buffer.readline(manual.control_max_bytes + 1)
            if len(line) > manual.control_max_bytes or not line.endswith(b"\n"):
                raise ValueError("Invalid private startup packet")
            packet = ScorerStartupPacket.model_validate_json(line)
            service_operation = create_child_operation(packet.operation_metadata)
            api = load_scorer_api_settings(
                root / "config" / "summary-evals" / "api.json", packet.scorer
            )
            finished = threading.Event()
            asyncio.run(serve_owned_api(
                root, packet, finished, channels, announced,
                api=api, service_operation=service_operation,
            ))
            finished.set()
        except (Exception, SystemExit):
            if api is not None and service_operation is not None:
                events = EventWriter(
                    api.logging, channels.events, service_operation=service_operation,
                    propagate_trace_context=api.propagate_trace_context,
                )
                try:
                    events.diagnostic(ApiDiagnosticData(
                        component="api", action="failed", level="ERROR", code="STARTUP_FAILED"
                    ))
                finally:
                    events.close()
            else:
                report_startup_failure("STARTUP_FAILED", channels.events)
            if packet is not None and service_operation is not None and not announced.is_set():
                with contextlib.suppress(OSError):
                    emit_control(
                        ScorerStartFailed(
                            version=SCORER_CONTROL_VERSION,
                            kind="failed",
                            service="api",
                            scorer=packet.scorer,
                            startup_id=packet.startup_id,
                            launch_operation_metadata=packet.operation_metadata,
                            operation_metadata=service_operation,
                            pid=os.getpid(),
                            error_code="STARTUP_FAILED",
                        ),
                        channels.control,
                        manual.control_max_bytes,
                    )
            os._exit(1)


if __name__ == "__main__":
    main()
