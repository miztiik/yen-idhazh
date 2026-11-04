"""How are only this phase's shared service children identified and joined?"""

import contextlib
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Literal

from hhem_evaluator.contracts.server_event import ServerEvent
from hhem_evaluator.contracts.service_settings import ServiceSettings
from pydantic import ValidationError

from .control import (
    ApiReady,
    HostReady,
    ServiceControl,
    ServiceStartFailed,
    ServiceStopped,
    StartupPacket,
)
from .failures import WorkflowError
from .settings import PipelineSettings

# The private protocol emits ready or failed, then stopped and EOF.
CONTROL_PACKET_CAPACITY = 3


class OwnedService:
    def __init__(
        self,
        service: Literal["api", "host"],
        command: list[str],
        root: Path,
        packet: StartupPacket,
        settings: ServiceSettings,
        manual: PipelineSettings,
    ) -> None:
        self.service, self.packet, self.settings, self.manual = service, packet, settings, manual
        self.messages: queue.Queue[ServiceControl | None] = queue.Queue(CONTROL_PACKET_CAPACITY)
        self.protocol_failed = threading.Event()
        self.events_failed = threading.Event()
        self.ready: ApiReady | HostReady | None = None
        self.stopped: ServiceStopped | None = None
        self.closed = False
        self.finish_sent = False
        self.startup_failure: ServiceStartFailed | None = None
        try:
            self.process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if service == "api" else None,
            )
        except OSError:
            raise WorkflowError("STARTUP_FAILED", "startup", service) from None
        self.readers = [threading.Thread(target=self._read_control, daemon=True)]
        if service == "api":
            self.readers.append(threading.Thread(target=self._read_events, daemon=True))
        for reader in self.readers:
            reader.start()
        try:
            if self.process.stdin is None:
                raise OSError("Missing owned startup pipe")
            self.process.stdin.write(packet.model_dump_json().encode() + b"\n")
            self.process.stdin.flush()
        except OSError:
            # The object already owns a child; the caller must still close it.
            self.protocol_failed.set()

    def _read_control(self) -> None:
        stream = self.process.stdout
        if stream is None:
            self.protocol_failed.set()
            return
        try:
            while True:
                line = stream.readline(self.manual.control_max_bytes + 1)
                if not line:
                    return
                if len(line) > self.manual.control_max_bytes or not line.endswith(b"\n"):
                    self.protocol_failed.set()
                    return
                self.messages.put_nowait(ServiceControl.model_validate_json(line))
        except (OSError, ValueError, ValidationError, queue.Full):
            self.protocol_failed.set()
        finally:
            with contextlib.suppress(queue.Full):
                self.messages.put_nowait(None)

    def _read_events(self) -> None:
        stream = self.process.stderr
        if stream is None:
            self.events_failed.set()
            return
        try:
            while line := stream.readline(self.settings.logging.max_event_bytes + 1):
                if (
                    self.service != "api"
                    or len(line) > self.settings.logging.max_event_bytes
                    or not line.endswith(b"\n")
                ):
                    self.events_failed.set()
                    return
                event = ServerEvent.model_validate_json(line)
                sys.stderr.write(event.model_dump_json() + "\n")
                sys.stderr.flush()
        except (OSError, ValueError, ValidationError):
            self.events_failed.set()

    def wait_ready(self, timeout_ms: int) -> ApiReady | HostReady:
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            if self.protocol_failed.is_set():
                raise WorkflowError("CHILD_PROTOCOL_FAILED", "startup", self.service)
            if self.events_failed.is_set():
                raise WorkflowError("EVENT_STREAM_FAILED", "startup", self.service)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkflowError("STARTUP_FAILED", "startup", self.service)
            try:
                message = self.messages.get(
                    timeout=min(remaining, self.manual.poll_interval_ms / 1000)
                )
                break
            except queue.Empty:
                if self.process.poll() is not None:
                    self.readers[0].join(timeout=self.settings.worker.forced_stop_ms / 1000)
                    try:
                        message = self.messages.get_nowait()
                    except queue.Empty:
                        raise WorkflowError("CHILD_EXITED", "startup", self.service) from None
                    break
        if self.protocol_failed.is_set():
            raise WorkflowError("CHILD_PROTOCOL_FAILED", "startup", self.service)
        if self.events_failed.is_set():
            raise WorkflowError("EVENT_STREAM_FAILED", "startup", self.service)
        packet = message.root if message is not None else None
        if packet is None:
            raise WorkflowError("CHILD_EXITED", "startup", self.service)
        if (
            packet.startup_id != self.packet.startup_id
            or packet.pid != self.process.pid
            or packet.service != self.service
        ):
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", self.service)
        if isinstance(packet, ServiceStartFailed):
            self.startup_failure = packet
            raise WorkflowError(
                "STARTUP_FAILED",
                "startup",
                self.service,
                packet.http_status,
                source_code=packet.error_code,
            )
        if self.process.poll() is not None:
            raise WorkflowError("CHILD_EXITED", "startup", self.service)
        if not isinstance(packet, ApiReady | HostReady):
            raise WorkflowError("STARTUP_FAILED", "startup", self.service)
        self.ready = packet
        return packet

    def check_alive(self) -> None:
        if self.process.poll() is not None:
            raise WorkflowError("CHILD_EXITED", self.packet.phase, self.service)
        if self.protocol_failed.is_set():
            raise WorkflowError("CHILD_PROTOCOL_FAILED", self.packet.phase, self.service)
        if self.events_failed.is_set():
            raise WorkflowError("EVENT_STREAM_FAILED", self.packet.phase, self.service)

    def finish_measurement(self, outcome: str) -> None:
        """Send an explicit closing outcome; EOF alone is cancellation."""
        if self.service != "host" or self.finish_sent or outcome not in ("success", "error"):
            raise WorkflowError("CHILD_PROTOCOL_FAILED", "cleanup", self.service)
        if self.process.stdin is None:
            raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", self.service)
        try:
            self.process.stdin.write(
                json.dumps({"kind": "stop", "outcome": outcome}).encode() + b"\n"
            )
            self.process.stdin.flush()
            self.finish_sent = True
        except OSError:
            raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", self.service) from None

    def close(self, timeout_ms: int) -> ServiceStopped:
        if self.closed:
            raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", self.service)
        self.closed = True
        escalated = False
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                self.protocol_failed.set()
        try:
            self.process.wait(timeout=timeout_ms / 1000)
        except subprocess.TimeoutExpired:
            escalated = True
            self.process.terminate()
            try:
                self.process.wait(timeout=self.settings.worker.stop_grace_ms / 1000)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=self.settings.worker.forced_stop_ms / 1000)
                except subprocess.TimeoutExpired:
                    raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", self.service) from None
        for reader in self.readers:
            reader.join(timeout=self.settings.worker.forced_stop_ms / 1000)
        while not self.messages.empty():
            message = self.messages.get_nowait()
            if message is not None and isinstance(message.root, ServiceStartFailed):
                failed = message.root
                if (
                    failed.startup_id != self.packet.startup_id
                    or failed.pid != self.process.pid
                    or failed.service != self.service
                ):
                    self.protocol_failed.set()
                else:
                    self.startup_failure = failed
            if message is not None and isinstance(message.root, ServiceStopped):
                observed = message.root
                if (
                    observed.startup_id != self.packet.startup_id
                    or observed.pid != self.process.pid
                    or observed.service != self.service
                    or self.stopped is not None
                ):
                    self.protocol_failed.set()
                else:
                    self.stopped = observed
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        stopped = self.stopped
        startup_code = self.startup_failure.error_code if self.startup_failure is not None else None
        if (
            escalated
            or self.process.returncode != 0
            or stopped is None
            or not stopped.clean
            or stopped.startup_id != self.packet.startup_id
            or stopped.pid != self.process.pid
            or stopped.service != self.service
            or (
                self.service == "api"
                and self.packet.phase == "evaluation"
                and (
                    stopped.worker_exit_confirmed is not True
                    or stopped.unieval_worker_exit_confirmed is not True
                )
            )
            or self.protocol_failed.is_set()
            or self.events_failed.is_set()
            or any(reader.is_alive() for reader in self.readers)
        ):
            source_code = (
                stopped.cleanup_error_code or stopped.error_code or startup_code
                if stopped is not None
                else startup_code
            )
            raise WorkflowError(
                "SERVICE_STOP_FAILED",
                "cleanup",
                self.service,
                stopped.http_status
                if stopped is not None and not stopped.cleanup_error_code
                else None,
                source_code=source_code,
            )
        return stopped
