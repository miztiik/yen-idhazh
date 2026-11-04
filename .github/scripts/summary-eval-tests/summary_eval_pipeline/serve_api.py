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
from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.configure_server import create_server_config, report_startup_failure
from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.server_event import ApiDiagnosticData
from hhem_evaluator.emit_events import EventWriter
from hhem_evaluator.load_llama_settings import load_llama_settings
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.run_server import has_clean_lifespan
from hhem_evaluator.serve_api import create_app

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
    shared = load_api_settings(root / "config" / "fastapi-server.json")
    api = ApiSettings.model_validate_json(
        shared.model_copy(
            update={"enabled_routes": ("llama",) if packet.phase == "generation" else ("hhem",)}
        ).model_dump_json()
    )
    settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json", api)
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
        settings if packet.phase == "evaluation" else None,
        root,
        packet.context,
        writer=events,
        llama_settings=(
            load_llama_settings(
                root / load_pipeline_settings(root).output_directory / "config" / "idhazh.json"
            )
            if packet.phase == "generation"
            else None
        ),
    )
    controller = app.state.controller
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
            settings.worker.shutdown_timeout_ms + settings.worker.forced_stop_ms,
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
        clean = (confirmed is not False) and has_clean_lifespan(server)
        emit_control(
            ServiceStopped(
                version=WORKFLOW_VERSION,
                kind="stopped",
                service="api",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                clean=clean,
                worker_exit_confirmed=confirmed,
                log_available=events.log_available,
            ),
            channels.control,
        )
        if not clean:
            raise RuntimeError("Owned service shutdown was not clean")
    finally:
        try:
            if controller is not None and not controller.stopping:
                await controller.shutdown()
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
