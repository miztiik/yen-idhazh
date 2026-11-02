"""How are only this caller's service children started, identified and joined?"""

import contextlib
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .contracts.evaluation_event import EvaluationEvent
from .contracts.service_settings import ServiceSettings
from .contracts.workflow_control import (
    ApiReady,
    HostReady,
    ServiceControl,
    ServiceStopped,
    StartupPacket,
)
from .fail_manual_evaluation import WorkflowFailure
from .load_manual_settings import ManualSettings

# The private protocol emits one ready packet and one stopped packet, then EOF.
CONTROL_PACKET_CAPACITY = 3


class OwnedService:
    def __init__(
        self,
        service: Literal["hhem", "host"],
        command: list[str],
        root: Path,
        packet: StartupPacket,
        settings: ServiceSettings,
        manual: ManualSettings,
    ) -> None:
        self.service, self.packet, self.settings, self.manual = service, packet, settings, manual
        self.messages: queue.Queue[ServiceControl | None] = queue.Queue(CONTROL_PACKET_CAPACITY)
        self.protocol_failed = threading.Event()
        self.events_failed = threading.Event()
        self.terminal_seen = threading.Event()
        self.terminal_event: EvaluationEvent | None = None
        self.ready: ApiReady | HostReady | None = None
        self.stopped: ServiceStopped | None = None
        self.closed = False
        try:
            self.process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if service == "hhem" else subprocess.DEVNULL,
            )
        except OSError:
            raise WorkflowFailure("STARTUP_FAILED", "startup", service) from None
        self.readers = [threading.Thread(target=self._read_control, daemon=True)]
        if service == "hhem":
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
                    self.service != "hhem"
                    or len(line) > self.settings.logging.max_event_bytes
                    or not line.endswith(b"\n")
                ):
                    self.events_failed.set()
                    return
                event = EvaluationEvent.model_validate_json(line)
                if event.operation == "request" and event.phase in (
                    "completed",
                    "failed",
                    "cancelled",
                ):
                    self.terminal_event = event
                    self.terminal_seen.set()
                sys.stderr.write(event.model_dump_json() + "\n")
                sys.stderr.flush()
        except (OSError, ValueError, ValidationError):
            self.events_failed.set()

    def wait_ready(self, timeout_ms: int) -> ApiReady | HostReady:
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            if self.protocol_failed.is_set():
                raise WorkflowFailure("CHILD_PROTOCOL_FAILED", "startup", self.service)
            if self.events_failed.is_set():
                raise WorkflowFailure("EVENT_STREAM_FAILED", "startup", self.service)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkflowFailure("STARTUP_FAILED", "startup", self.service)
            try:
                message = self.messages.get(
                    timeout=min(remaining, self.manual.poll_interval_ms / 1000)
                )
                break
            except queue.Empty:
                if self.process.poll() is not None:
                    raise WorkflowFailure("CHILD_EXITED", "startup", self.service) from None
        if self.protocol_failed.is_set():
            raise WorkflowFailure("CHILD_PROTOCOL_FAILED", "startup", self.service)
        packet = message.root if message is not None else None
        if packet is None or self.process.poll() is not None:
            raise WorkflowFailure("CHILD_EXITED", "startup", self.service)
        if not isinstance(packet, ApiReady | HostReady):
            raise WorkflowFailure("STARTUP_FAILED", "startup", self.service)
        if (
            packet.startup_id != self.packet.startup_id
            or packet.pid != self.process.pid
            or packet.service != self.service
        ):
            raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "startup", self.service)
        self.ready = packet
        return packet

    def check_alive(self) -> None:
        if self.process.poll() is not None:
            raise WorkflowFailure("CHILD_EXITED", "evaluation", self.service)
        if self.protocol_failed.is_set():
            raise WorkflowFailure("CHILD_PROTOCOL_FAILED", "evaluation", self.service)
        if self.events_failed.is_set():
            raise WorkflowFailure("EVENT_STREAM_FAILED", "evaluation", self.service)

    def confirm_terminal(self, event_id: str | None, execution_id: str) -> None:
        if not self.terminal_seen.wait(self.manual.http_connect_timeout_ms / 1000):
            raise WorkflowFailure("EVENT_STREAM_FAILED", "evaluation", self.service)
        event = self.terminal_event
        if (
            self.events_failed.is_set()
            or event is None
            or event.event_id != event_id
            or event.execution_id != execution_id
        ):
            raise WorkflowFailure("EVENT_STREAM_FAILED", "evaluation", self.service)

    def close(self, timeout_ms: int) -> ServiceStopped:
        if self.closed:
            raise WorkflowFailure("SERVICE_STOP_FAILED", "cleanup", self.service)
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
                    raise WorkflowFailure("SERVICE_STOP_FAILED", "cleanup", self.service) from None
        for reader in self.readers:
            reader.join(timeout=self.settings.worker.forced_stop_ms / 1000)
        while not self.messages.empty():
            message = self.messages.get_nowait()
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
        if (
            escalated
            or self.process.returncode != 0
            or stopped is None
            or not stopped.clean
            or stopped.startup_id != self.packet.startup_id
            or stopped.pid != self.process.pid
            or stopped.service != self.service
            or (self.service == "hhem" and stopped.worker_exit_confirmed is not True)
            or self.protocol_failed.is_set()
            or self.events_failed.is_set()
            or any(reader.is_alive() for reader in self.readers)
        ):
            raise WorkflowFailure("SERVICE_STOP_FAILED", "cleanup", self.service)
        return stopped
