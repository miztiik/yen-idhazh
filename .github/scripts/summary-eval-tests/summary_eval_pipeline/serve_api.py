"""How does the selected API component stay bound to its phase's private pipe?"""

import argparse
import asyncio
import contextlib
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, TextIO

import uvicorn
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.configure_server import (
    create_server_config,
    report_startup_failure,
)
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.serve_http.run_server import has_clean_lifespan
from summary_evaluator.serve_http.serve_api import create_app

from .channels import OwnedChannels, open_owned_channels
from .contracts import WORKFLOW_VERSION
from .control import ApiReady, ServiceStartFailed, ServiceStopped, StartupPacket
from .settings import load_pipeline_settings


def emit_control(
    packet: ApiReady | ServiceStopped | ServiceStartFailed,
    stream: TextIO,
) -> None:
    stream.write(packet.model_dump_json() + "\n")
    stream.flush()


def watch_parent_lifetime(
    stream: BinaryIO,
    request_stop: Callable[[], None],
    finished: threading.Event,
    timeout_ms: int,
) -> None:
    # Either EOF or a broken private pipe means that the caller is gone.
    with contextlib.suppress(OSError):
        stream.read(1)
    deadline = threading.Timer(timeout_ms / 1000, lambda: os._exit(1))
    deadline.daemon = True
    deadline.start()
    try:
        request_stop()
        finished.wait(timeout_ms / 1000)
    finally:
        if finished.is_set():
            deadline.cancel()


async def serve_owned_api(
    root: Path,
    packet: StartupPacket,
    finished: threading.Event,
    channels: OwnedChannels,
) -> None:
    if packet.phase != "evaluation":
        raise ValueError("Only evaluation starts the shared evaluation application")
    shared = load_api_settings(root / "config" / "summary-evals" / "api.json")
    api = ApiSettings.model_validate_json(
        shared.model_copy(update={"enabled_routes": ("hhem", "unieval")}).model_dump_json()
    )
    settings = load_settings(
        root / "config" / "summary-evals" / "hhem-evaluator" / "settings.json", api
    )
    unieval_settings = load_unieval_settings(root, api)
    events = EventWriter(
        api.logging,
        channels.events,
        directory=root / load_pipeline_settings(root).output_directory / "logs",
        run_id=packet.run.run_id if packet.run is not None else packet.startup_id,
        attempt=packet.attempt,
        started_at=packet.run.started_at if packet.run is not None else None,
    )
    app = create_app(
        api,
        settings,
        root,
        packet.context,
        writer=events,
        unieval_settings=unieval_settings,
    )
    controller, unieval = app.state.controller, app.state.unieval
    config = create_server_config(app, api)
    # Bind before lifespan starts a model; an occupied listener owns no part of this run.
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
    server = uvicorn.Server(config)
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(setattr, server, "should_exit", True)

    threading.Thread(
        target=watch_parent_lifetime,
        args=(
            sys.stdin.buffer,
            request_stop,
            finished,
            max(
                settings.worker.shutdown_timeout_ms + settings.worker.forced_stop_ms,
                unieval_settings.worker.shutdown_timeout_ms
                + unieval_settings.worker.forced_stop_ms,
            ),
        ),
        daemon=True,
    ).start()
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started and not serving.done():
            await asyncio.sleep(0)
        if server.started and not serving.done():
            emit_control(
                ApiReady(
                    version=WORKFLOW_VERSION,
                    kind="ready",
                    service="api",
                    startup_id=packet.startup_id,
                    pid=os.getpid(),
                    service_instance_id=app.state.service_instance_id,
                ),
                channels.control,
            )
        await serving
        confirmed = controller.worker.exit_confirmed if controller is not None else None
        unieval_confirmed = unieval.worker.exit_confirmed if unieval is not None else None
        clean = (
            confirmed is not False and unieval_confirmed is not False and has_clean_lifespan(server)
        )
        emit_control(
            ServiceStopped(
                version=WORKFLOW_VERSION,
                kind="stopped",
                service="api",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                clean=clean,
                worker_exit_confirmed=confirmed,
                unieval_worker_exit_confirmed=unieval_confirmed,
                log_available=events.log_available,
            ),
            channels.control,
        )
        if not clean:
            raise RuntimeError("Owned service shutdown was not clean")
    finally:
        try:
            closing = []
            if controller is not None and not controller.stopping:
                closing.append(controller.shutdown())
            if unieval is not None and not unieval.stopping:
                closing.append(unieval.shutdown())
            outcomes = await asyncio.gather(*closing, return_exceptions=True)
            failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
            if failures:
                raise BaseExceptionGroup("Owned evaluator cleanup failed", failures)
        finally:
            listener.close()
            events.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    with open_owned_channels() as channels:
        packet: StartupPacket | None = None
        try:
            root = args.root.resolve()
            manual = load_pipeline_settings(root)
            line = sys.stdin.buffer.readline(manual.control_max_bytes + 1)
            if len(line) > manual.control_max_bytes or not line.endswith(b"\n"):
                raise ValueError("Invalid private startup packet")
            packet = StartupPacket.model_validate_json(line)
            finished = threading.Event()
            asyncio.run(serve_owned_api(root, packet, finished, channels))
            # Executor shutdown also belongs inside the parent-loss deadline.
            finished.set()
        except (Exception, SystemExit):
            report_startup_failure("STARTUP_FAILED", channels.events)
            if packet is not None:
                with contextlib.suppress(OSError):
                    emit_control(
                        ServiceStartFailed(
                            version=WORKFLOW_VERSION,
                            kind="failed",
                            service="api",
                            startup_id=packet.startup_id,
                            pid=os.getpid(),
                        ),
                        channels.control,
                    )
            # Native library and server failures cannot print raw diagnostics.
            # Do not let Python's finalizers wait on an unconfirmed model child.
            os._exit(1)


if __name__ == "__main__":
    main()
