"""How does a private launcher bind the existing API to its caller's lifetime?"""

import argparse
import asyncio
import contextlib
import logging
import math
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, TextIO

import uvicorn
from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.emit_events import EventWriter
from hhem_evaluator.load_settings import load_settings
from hhem_evaluator.serve_api import create_app
from uvicorn.lifespan.on import LifespanOn

from .channels import OwnedChannels, open_owned_channels
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
    selected = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
    settings = type(selected).model_validate_json(
        selected.model_copy(update={"enabled": True}).model_dump_json()
    )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).disabled = True
    app = create_app(
        settings, root, packet.context, writer=EventWriter(settings.logging, channels.events)
    )
    controller = app.state.controller
    config = uvicorn.Config(
        app,
        host=settings.listener.host,
        port=settings.listener.port,
        workers=1,
        reload=False,
        access_log=False,
        log_config=None,
        proxy_headers=False,
        server_header=False,
        lifespan="on",
        timeout_graceful_shutdown=math.ceil(settings.worker.shutdown_timeout_ms / 1000),
    )
    # Bind before lifespan starts a model; an occupied listener owns no part of this run.
    listener = config.bind_socket()
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
                    version=SCHEMA_VERSION,
                    kind="ready",
                    service="hhem",
                    startup_id=packet.startup_id,
                    pid=os.getpid(),
                    service_instance_id=controller.instance_id,
                ),
                channels.control,
            )
        await serving
        confirmed = controller.worker.exit_confirmed
        clean = (
            confirmed
            and isinstance(server.lifespan, LifespanOn)
            and not server.lifespan.error_occurred
            and not server.lifespan.shutdown_failed
        )
        emit_control(
            ServiceStopped(
                version=SCHEMA_VERSION,
                kind="stopped",
                service="hhem",
                startup_id=packet.startup_id,
                pid=os.getpid(),
                clean=clean,
                worker_exit_confirmed=confirmed,
            ),
            channels.control,
        )
        if not clean:
            raise RuntimeError("Owned service shutdown was not clean")
    finally:
        try:
            if not controller.stopping:
                await controller.shutdown()
        finally:
            listener.close()


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
            if packet is not None:
                with contextlib.suppress(OSError):
                    emit_control(
                        ServiceStartFailed(
                            version=SCHEMA_VERSION,
                            kind="failed",
                            service="hhem",
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
