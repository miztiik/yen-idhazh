"""Observe one exact child exit after its parent vanishes during a blocked prediction."""

import asyncio
import json
import multiprocessing
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass

from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.contracts.worker_message import ScoreWindow
from hhem_evaluator.shared.create_execution_id import create_execution_id
from hhem_evaluator.shared.exchange_packets import ByteChannel

from .contract_examples import REPOSITORY
from .replay_predictions import Scenario, read_recordings
from .service_cases import RecordedSupervisor, service_settings


@dataclass
class ExitObservation:
    wait: Callable[[float], bool]
    stop: Callable[[], None]
    close: Callable[[], None]


def observe_exit(pid: int) -> ExitObservation:
    """Retain an OS handle, so even failure cleanup cannot target a reused PID."""
    if sys.platform == "win32":
        import ctypes
        import math
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        # Windows handle rights: SYNCHRONIZE and PROCESS_TERMINATE.
        handle = kernel.OpenProcess(0x00100000 | 0x0001, False, pid)
        if not handle:
            raise OSError("Could not observe the owned child.")

        def wait(timeout: float) -> bool:
            return int(kernel.WaitForSingleObject(handle, math.ceil(timeout * 1000))) == 0

        def stop() -> None:
            if not kernel.TerminateProcess(handle, 1):
                raise OSError("Could not stop the owned child.")

        def close() -> None:
            if not kernel.CloseHandle(handle):
                raise OSError("Could not close the owned child observation.")

        return ExitObservation(wait, stop, close)
    if sys.platform == "linux":
        import select
        import signal

        descriptor = os.pidfd_open(pid)

        def wait(timeout: float) -> bool:
            return bool(select.select([descriptor], [], [], timeout)[0])

        def stop() -> None:
            signal.pidfd_send_signal(descriptor, signal.SIGKILL)

        def close() -> None:
            os.close(descriptor)

        return ExitObservation(wait, stop, close)
    raise AssertionError("The process-exit proof requires the supported Linux or Windows host.")


def _vanishing_parent(control: ByteChannel, encoded_settings: bytes) -> None:
    async def own_worker() -> None:
        settings = ServiceSettings.model_validate_json(encoded_settings)
        worker = RecordedSupervisor(settings, (Scenario(actions=("block",)),))
        try:
            await worker.start()
            await worker.handshake()
            inputs, _, _ = read_recordings(REPOSITORY)
            case = inputs.cases[0]
            command = ScoreWindow(
                version=SCHEMA_VERSION,
                kind="score_window",
                execution_id=create_execution_id(),
                generation=1,
                comparison="primary",
                window_index=0,
                start_word=0,
                end_word=len(case.source_text.split()),
                source_text=case.source_text,
                summary_text=case.summary_text,
            )
            scoring = asyncio.create_task(worker.score(command))
            await worker.handshake()
            assert worker.worker is not None
            control.send_bytes(json.dumps({"pid": worker.worker.pid}).encode())
            await asyncio.to_thread(control.recv_bytes, 1)
            assert not scoring.done()
            os._exit(0)
        finally:
            await worker.stop()
            worker.close_controls()

    asyncio.run(own_worker())


def prove_parent_loss() -> None:
    """Use a real parent death and OS exit signal, not a daemon flag or pipe EOF in predict."""
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    process = context.Process(
        target=_vanishing_parent,
        args=(child, service_settings().model_dump_json().encode()),
        daemon=False,
    )
    observation: ExitObservation | None = None
    process.start()
    child.close()
    try:
        if not parent.poll(15):
            raise AssertionError("The owned parent did not report blocked prediction.")
        pid = json.loads(parent.recv_bytes(1024))["pid"]
        observation = observe_exit(pid)
        parent.send_bytes(b"1")
        process.join(5)
        assert not process.is_alive() and process.exitcode == 0
        assert observation.wait(5), "The blocked scoring child survived its parent."
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
        if observation is not None:
            if not observation.wait(0):
                observation.stop()
                assert observation.wait(5)
            observation.close()
        parent.close()
        process.close()
