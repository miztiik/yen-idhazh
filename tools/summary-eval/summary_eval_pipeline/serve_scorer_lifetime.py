"""How does one owned Uvicorn lifespan report its selected worker and parent-loss exit?"""

import asyncio
import contextlib
import os
import socket
import sys
import threading
from collections.abc import Callable
from typing import BinaryIO, TextIO

import uvicorn
from fastapi import FastAPI
from summary_evaluator.serve_http.configure_server import create_server_config
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.run_server import has_clean_lifespan
from summary_evaluator.shared.create_api_component import ApiComponentRuntime
from summary_evaluator.shared.read_process_identity import read_owned_process_identity

from .channels import OwnedChannels
from .control import encode_control_packet
from .scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerReady,
    ScorerStartFailed,
    ScorerStartupPacket,
    ScorerStopped,
)


def emit_control(
    packet: ScorerReady | ScorerStopped | ScorerStartFailed, stream: TextIO, max_bytes: int
) -> None:
    stream.write(encode_control_packet(packet, max_bytes).decode("utf-8"))
    stream.flush()


def watch_parent_lifetime(
    stream: BinaryIO,
    request_stop: Callable[[], None],
    finished: threading.Event,
    timeout_ms: int,
) -> None:
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


async def serve_scorer_lifetime(
    app: FastAPI,
    api: ApiSettings,
    packet: ScorerStartupPacket,
    finished: threading.Event,
    channels: OwnedChannels,
    sockets: list[socket.socket],
    announced: threading.Event,
    *,
    control_max_bytes: int,
    parent_stream: BinaryIO | None = None,
) -> None:
    if api.enabled_routes != (packet.scorer,) or len(app.state.components) != 1:
        raise ValueError("An owned API must start exactly its selected scorer")
    runtime = app.state.components[packet.scorer]
    if not isinstance(runtime, ApiComponentRuntime):
        raise ValueError("The selected scorer requires its native component adapter")
    process = read_owned_process_identity(
        os.getpid(), runtime.worker_settings.max_proc_identity_bytes
    )
    server = uvicorn.Server(create_server_config(app, api))
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(setattr, server, "should_exit", True)

    threading.Thread(
        target=watch_parent_lifetime,
        args=(
            parent_stream if parent_stream is not None else sys.stdin.buffer,
            request_stop,
            finished,
            api.shutdown_timeout_ms
            + runtime.worker_settings.shutdown_timeout_ms
            + runtime.worker_settings.forced_stop_ms,
        ),
        daemon=True,
    ).start()
    serving = asyncio.create_task(server.serve(sockets=sockets))
    failure: BaseException | None = None
    try:
        while not server.started and not serving.done():
            await asyncio.sleep(0)
        if server.started and not serving.done():
            emit_control(
                ScorerReady(
                    version=SCORER_CONTROL_VERSION,
                    kind="ready",
                    service="api",
                    scorer=packet.scorer,
                    startup_id=packet.startup_id,
                    launch_operation_metadata=packet.operation_metadata,
                    operation_metadata=app.state.events.service_operation,
                    process=process,
                    service_instance_id=app.state.service_instance_id,
                    log_file=app.state.events.log_file,
                    log_available=app.state.events.log_available,
                ),
                channels.control,
                control_max_bytes,
            )
            announced.set()
        await serving
    except BaseException as error:
        failure = error
    cleanup: BaseException | None = None
    try:
        if not runtime.is_stopping():
            await runtime.shutdown()
    except BaseException as error:
        cleanup = error
    if not announced.is_set():
        emit_control(
            ScorerStartFailed(
                version=SCORER_CONTROL_VERSION,
                kind="failed",
                service="api",
                scorer=packet.scorer,
                startup_id=packet.startup_id,
                launch_operation_metadata=packet.operation_metadata,
                operation_metadata=app.state.events.service_operation,
                pid=process.pid,
                error_code="STARTUP_FAILED",
            ),
            channels.control,
            control_max_bytes,
        )
        announced.set()
    worker_exit = runtime.observe_exit()
    clean = (
        failure is None and cleanup is None
        and worker_exit.confirmed is not False and has_clean_lifespan(server)
    )
    emit_control(
        ScorerStopped(
            version=SCORER_CONTROL_VERSION,
            kind="stopped",
            service="api",
            scorer=packet.scorer,
            startup_id=packet.startup_id,
            launch_operation_metadata=packet.operation_metadata,
            operation_metadata=app.state.events.service_operation,
            process=process,
            clean=clean,
            worker_exit=worker_exit,
            log_file=app.state.events.log_file,
            log_available=app.state.events.log_available,
            cleanup_error_code="SERVICE_STOP_FAILED" if not clean else None,
        ),
        channels.control,
        control_max_bytes,
    )
    if failure is not None and cleanup is not None:
        raise BaseExceptionGroup("Owned scorer cleanup failed", [failure, cleanup])
    if failure is not None:
        raise failure
    if cleanup is not None:
        raise cleanup
    if not clean:
        raise RuntimeError("Owned scorer lifespan did not close cleanly")
