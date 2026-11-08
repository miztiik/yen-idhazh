"""How does the generation task own, identify and reap its actual native model process?"""

import asyncio
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict
from summary_evaluator.shared.contracts.base import NonblankText

from idhazh.llm.server import server_argv
from utilities.model_runtime import BIN_DIR, SERVER_BINARY, verify_model_files

from .contracts import LoadedModel, ServerOutcome
from .failures import WorkflowError
from .http import call_local_api
from .launch_native import parent_bound_command
from .model_selection import SelectedModel
from .native_log import NativeDiagnosticData, NativeLog
from .native_response import NativeHealth, NativeHealthReply
from .run_contracts import PreparedRun
from .settings import PipelineSettings


class NativeProps(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    model_path: NonblankText
    model_alias: NonblankText


def owns_listener(pid: int, port: int, limit: int) -> bool:
    """Inspect one owned process, never adopt a listener found by port alone."""
    inodes: set[str] = set()
    with os.scandir(f"/proc/{pid}/fd") as entries:
        for entry in entries:
            try:
                target = str(Path(entry.path).readlink())
            except FileNotFoundError:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                inodes.add(target[8:-1])
    for name in ("tcp", "tcp6"):
        with Path(f"/proc/{pid}/net/{name}").open("rb") as stream:
            encoded = stream.read(limit + 1)
        if len(encoded) > limit:
            raise WorkflowError("RESPONSE_TOO_LARGE", "health", "llama")
        for row in encoded.decode("ascii").splitlines()[1:]:
            fields = row.split()
            if (
                len(fields) > 9
                and fields[3] == "0A"
                and int(fields[1].rsplit(":", 1)[1], 16) == port
                and fields[9] in inodes
            ):
                return True
    return False


class OwnedLlama:
    def __init__(
        self,
        root: Path,
        prepared: PreparedRun,
        selected: SelectedModel,
        pipeline: PipelineSettings,
    ) -> None:
        self.root, self.selected, self.pipeline = root, selected, pipeline
        self.process: subprocess.Popen[bytes] | None = None
        self.loaded: LoadedModel | None = None
        self.log = NativeLog(
            root / pipeline.native_log_directory,
            prepared.run,
            pipeline.native_logging,
        )
        self.started = time.monotonic()
        self.startup: str = "not_started"
        self.startup_ms: float | None = None
        self.shutdown: str = "not_started"
        self.error_code: str | None = None
        self.cleanup_error_code: str | None = None

    def start(self) -> None:
        try:
            parts = urlsplit(self.selected.native.base_url)
            host, port = parts.hostname, parts.port
            if host is None or port is None:
                raise WorkflowError("MODEL_INVALID", "input", "llama")
            # Refuse an occupied destination before loading any owned weights.
            with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as probe:
                probe.bind((host, port))
            verify_model_files(Path(self.pipeline.output_directory) / "config")
            argv = server_argv(
                binary=SERVER_BINARY,
                weights=Path("backend/models") / self.selected.identity.filename,
                model=self.selected.entry,
                server=self.selected.entry.server,
                port=port,
            )
            # Quiet protocol switches prevent bodies and raw model diagnostics reaching logs.
            argv += ["--host", host, *self.pipeline.native_quiet_flags]
            self.log.event(NativeDiagnosticData(component="llama", action="started", level="INFO"))
            self.process = subprocess.Popen(
                parent_bound_command(argv),
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "LD_LIBRARY_PATH": BIN_DIR.as_posix()},
            )
        except (OSError, ValueError, SystemExit, WorkflowError):
            self.startup = "failed"
            self.error_code = "STARTUP_FAILED"
            raise WorkflowError("STARTUP_FAILED", "startup", "llama") from None

    def check_alive(self) -> None:
        if self.process is None or self.process.poll() is not None:
            raise WorkflowError("CHILD_EXITED", "generation", "llama")

    async def wait_ready(self, client: httpx.AsyncClient) -> LoadedModel:
        deadline = time.monotonic() + self.pipeline.native_startup_timeout_ms / 1000
        last: WorkflowError | None = None
        try:
            while time.monotonic() < deadline:
                self.check_alive()
                try:
                    health_status, health = await call_local_api(
                        client,
                        "GET",
                        self.selected.native.base_url + "/health",
                        NativeHealthReply,
                        self.pipeline,
                        self.pipeline.http_connect_timeout_ms,
                        service="llama",
                        phase="health",
                        max_response_bytes=self.pipeline.max_generation_response_bytes,
                    )
                    if (
                        health_status != 200
                        or not isinstance(health.root, NativeHealth)
                        or health.root.status != "ok"
                    ):
                        raise WorkflowError("HEALTH_FAILED", "health", "llama", health_status)
                    status, props = await call_local_api(
                        client,
                        "GET",
                        self.selected.native.base_url + "/props",
                        NativeProps,
                        self.pipeline,
                        self.pipeline.http_connect_timeout_ms,
                        service="llama",
                        phase="health",
                        max_response_bytes=self.pipeline.native_max_metadata_bytes,
                    )
                    if status == 200:
                        self.check_alive()
                        assert self.process is not None
                        expected = (
                            self.root / "backend" / "models" / self.selected.identity.filename
                        )
                        port = urlsplit(self.selected.native.base_url).port
                        if (
                            props.model_path
                            not in (expected.relative_to(self.root).as_posix(), str(expected))
                            or props.model_alias != self.selected.identity.model_id
                            or port is None
                            or not owns_listener(
                                self.process.pid, port, self.pipeline.native_max_metadata_bytes
                            )
                        ):
                            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "health", "llama")
                        self.loaded = LoadedModel(
                            model_id=props.model_alias,
                            weights_path=expected.relative_to(self.root).as_posix(),
                            sha256=self.selected.identity.sha256,
                            pid=self.process.pid,
                        )
                        self.startup = "ready"
                        self.startup_ms = (time.monotonic() - self.started) * 1000
                        self.log.event(
                            NativeDiagnosticData(
                                component="llama",
                                action="ready",
                                level="INFO",
                                duration_ms=self.startup_ms,
                            )
                        )
                        return self.loaded
                except WorkflowError as error:
                    if error.error.code not in ("HTTP_FAILED", "RESPONSE_INVALID") and not (
                        error.error.code == "HEALTH_FAILED" and error.error.http_status == 503
                    ):
                        raise
                    last = error
                await asyncio.sleep(
                    min(
                        self.pipeline.poll_interval_ms / 1000,
                        max(0, deadline - time.monotonic()),
                    )
                )
            raise last or WorkflowError("HEALTH_FAILED", "health", "llama")
        except WorkflowError as error:
            self.startup = "failed"
            self.startup_ms = (time.monotonic() - self.started) * 1000
            self.error_code = error.error.code
            self.log.event(
                NativeDiagnosticData(
                    component="llama",
                    action="failed",
                    level="ERROR",
                    code=error.error.code,
                )
            )
            raise

    def close(self) -> None:
        try:
            if self.process is not None:
                early = self.process.poll() is not None
                if not early:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=self.pipeline.native_shutdown_timeout_ms / 1000)
                except subprocess.TimeoutExpired:
                    self.shutdown = "forced"
                    self.process.kill()
                    self.process.wait(timeout=self.pipeline.native_forced_stop_ms / 1000)
                if early or self.shutdown == "forced" or self.process.returncode not in (0, -15):
                    raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", "llama")
                self.shutdown = "stopped"
                self.log.event(
                    NativeDiagnosticData(component="llama", action="stopped", level="INFO")
                )
        except (OSError, subprocess.TimeoutExpired, WorkflowError):
            if self.shutdown != "forced":
                self.shutdown = "failed"
            self.cleanup_error_code = "SERVICE_STOP_FAILED"
            raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", "llama") from None
        finally:
            self.log.close()

    def outcome(self) -> ServerOutcome:
        return ServerOutcome.model_validate(
            {
                "server_name": "llama-server",
                "startup": self.startup,
                "startup_ms": self.startup_ms,
                "shutdown": self.shutdown,
                "exit_code": self.process.returncode if self.process is not None else None,
                "log_filename": self.log.filename,
                "log_available": self.log.available,
                "error_code": self.error_code,
                "cleanup_error_code": self.cleanup_error_code,
            }
        )
