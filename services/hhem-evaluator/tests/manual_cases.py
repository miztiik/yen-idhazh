"""Compose the actual HHEM ASGI handler and native host handler over bounded pipes."""

import asyncio
import json
import subprocess
import sys
import sysconfig
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

import httpx
from pydantic import ConfigDict

from hhem_evaluator.contracts.base import NativeContract, PositiveCount
from hhem_evaluator.contracts.worker_identity import WorkerIdentity
from hhem_evaluator.load_manual_settings import load_manual_settings

from .contract_examples import REPOSITORY
from .test_host_profile_reader_parity import bridge_path, mapping, required_bun


def owned_child_command(mode: str) -> list[str]:
    # A Windows venv redirector owns a different PID; launch its actual interpreter.
    interpreter = getattr(sys, "_base_executable", None)
    if not isinstance(interpreter, str):
        raise AssertionError("The lifetime case requires the actual CPython executable.")
    script = (
        "import runpy,site,sys; packages=sys.argv.pop(1); source=sys.argv.pop(1); "
        "sys.path[:0]=[source,packages]; site.addsitedir(packages); "
        "runpy.run_path(sys.argv.pop(1),run_name='__main__')"
    )
    return [
        interpreter,
        "-c",
        script,
        sysconfig.get_path("purelib"),
        str(REPOSITORY / "services" / "hhem-evaluator" / "src"),
        str(Path(__file__).with_name("owned_service_child.py")),
        mode,
    ]


class ProcInterval(NativeContract):
    model_config = ConfigDict(extra="ignore")
    closing_stat: str


class ProcInputs(NativeContract):
    model_config = ConfigDict(extra="ignore")
    pid: PositiveCount
    start_ticks: str
    stat: str
    status: str
    closing_status: str
    cpu_intervals: tuple[ProcInterval, ...]


def proc_inputs() -> ProcInputs:
    return ProcInputs.model_validate_json(
        (REPOSITORY / "tests" / "fixtures" / "host-probes" / "process-inputs.json").read_bytes()
    )


def prepare_proc(
    directory: Path,
    worker: WorkerIdentity,
    *,
    closing: bool = False,
    write_status: bool = True,
) -> None:
    recorded = proc_inputs()
    process = directory / str(worker.pid)
    process.mkdir(parents=True, exist_ok=True)
    ticks = worker.start_ticks or recorded.start_ticks
    stat = recorded.cpu_intervals[0].closing_stat if closing else recorded.stat
    (process / "stat").write_text(
        stat.replace(f"{recorded.pid} ", f"{worker.pid} ", 1).replace(recorded.start_ticks, ticks),
        encoding="utf-8",
    )
    if write_status:
        (process / "status").write_text(
            recorded.closing_status if closing else recorded.status, encoding="utf-8"
        )
    fixture = REPOSITORY / "tests" / "fixtures" / "runtime"
    (directory / "stat").write_bytes(
        (
            fixture
            / (
                "2026-08-30-probe-proc-stat-at-end.txt"
                if closing
                else "2026-08-30-probe-proc-stat-at-start.txt"
            )
        ).read_bytes()
    )


class NativeHostPipe:
    def __init__(
        self,
        proc_root: Path,
        *,
        platform: str = "linux",
        task_profile: dict[str, bool | int] | None = None,
        report_mode: Literal["normal", "pending"] = "normal",
    ) -> None:
        self.limit = load_manual_settings(REPOSITORY).max_response_bytes
        self.lock = threading.Lock()
        self.closed: dict[str, object] | None = None
        self.requests = 0
        self.process = subprocess.Popen(
            [required_bun(), "run", "--no-install", str(bridge_path())],
            cwd=REPOSITORY,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        response = self.exchange(
            {
                "proc_root": str(proc_root),
                "platform": platform,
                "task_profile": task_profile or {},
                "report_mode": report_mode,
            }
        )
        assert response == {"kind": "ready"}, response

    def exchange(self, payload: dict[str, object]) -> dict[str, object]:
        with self.lock:
            assert self.process.stdin is not None and self.process.stdout is not None
            self.process.stdin.write(json.dumps(payload).encode() + b"\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline(self.limit + 1)
            assert line and len(line) <= self.limit, "The native pipe must return bounded metadata"
            return mapping(json.loads(line))

    def request(self, path: str, body: bytes) -> dict[str, object]:
        self.requests += 1
        return self.exchange({"kind": "request", "path": path, "body": body.decode()})

    def close(self) -> dict[str, object]:
        if self.closed is not None:
            return self.closed
        assert self.process.stdin is not None and self.process.stdout is not None
        # EOF, not another request, must close the actual native handler and collector.
        self.process.stdin.close()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise AssertionError(
                "The native host bridge did not close after parent-pipe EOF"
            ) from None
        line = self.process.stdout.readline(self.limit + 1)
        self.closed = mapping(json.loads(line))
        assert self.closed["kind"] == "closed"
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        return self.closed


class NativeTransports(httpx.AsyncBaseTransport):
    def __init__(
        self,
        api: httpx.ASGITransport | None,
        host: NativeHostPipe,
        after_evaluation: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.api, self.host, self.after_evaluation = api, host, after_evaluation

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.port == 3011:
            reply = await asyncio.to_thread(
                self.host.request, request.url.path, await request.aread()
            )
            status, body = reply["status"], reply["body"]
            assert isinstance(status, int) and isinstance(body, str)
            return httpx.Response(status, content=body.encode(), request=request)
        assert request.url.port == 3010, "Offline composition must not use a network destination"
        assert self.api is not None, "A host-only case must never send an evaluator request"
        response = await self.api.handle_async_request(request)
        if request.url.path.endswith("/evaluate") and self.after_evaluation is not None:
            await self.after_evaluation()
        return response

    async def aclose(self) -> None:
        if self.api is not None:
            await self.api.aclose()
