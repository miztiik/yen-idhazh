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

from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import ValidationError
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ServerEvent
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.service_settings import WorkerSettings
from summary_evaluator.shared.read_process_identity import read_owned_process_identity

from .control import (
    HostReady,
    MachineStartupPacket,
    ServiceControl,
    ServiceStartFailed,
    ServiceStopped,
    StartupPacket,
    encode_control_packet,
)
from .failures import WorkflowError
from .scorer_control import (
    ScorerControl,
    ScorerReady,
    ScorerStartFailed,
    ScorerStartupPacket,
    ScorerStopped,
)
from .settings import PipelineSettings

# The private protocol emits ready or failed, then stopped and EOF.
CONTROL_PACKET_CAPACITY = 3


class OwnedService:
    def __init__(
        self,
        service: Literal["api", "host"],
        command: list[str],
        root: Path,
        packet: StartupPacket | ScorerStartupPacket | MachineStartupPacket,
        settings: WorkerSettings | None,
        manual: PipelineSettings,
        *,
        api_settings: ApiSettings | None = None,
    ) -> None:
        self.service, self.packet, self.settings, self.manual = service, packet, settings, manual
        self.scorer = packet.scorer if isinstance(packet, ScorerStartupPacket) else None
        self.api_settings = api_settings
        self.expected_process: ProcessIdentity | None = None
        self.observed_service_operation: OperationMetadata | None = None
        self.stop_grace_ms = manual.host_stop_grace_ms
        self.forced_stop_ms = manual.host_forced_stop_ms
        self.max_event_bytes: int | None = None
        if service == "api":
            if (
                settings is None
                or not isinstance(packet, ScorerStartupPacket)
                or api_settings is None
                or api_settings.enabled_routes != (packet.scorer,)
            ):
                raise ValueError("An evaluator child requires its validated service settings")
            self.stop_grace_ms = settings.stop_grace_ms
            self.forced_stop_ms = settings.forced_stop_ms
            self.max_event_bytes = api_settings.logging.max_event_bytes
        elif not isinstance(packet, StartupPacket | MachineStartupPacket):
            raise ValueError("A machine child requires its declared startup contract")
        try:
            encoded_startup = encode_control_packet(packet, manual.control_max_bytes)
        except (ValueError, UnicodeError):
            raise WorkflowError("CHILD_PROTOCOL_FAILED", "startup", service) from None
        self.messages: queue.Queue[ServiceControl | ScorerControl | None] = queue.Queue(
            CONTROL_PACKET_CAPACITY
        )
        self.protocol_failed = threading.Event()
        self.events_failed = threading.Event()
        self.ready: ScorerReady | HostReady | None = None
        self.stopped: ScorerStopped | ServiceStopped | None = None
        self.closed = False
        self.finish_sent = False
        self.startup_failure: ScorerStartFailed | ServiceStartFailed | None = None
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
        if service == "api" and settings is not None:
            self.expected_process = read_owned_process_identity(
                self.process.pid, settings.max_proc_identity_bytes
            )
        self.readers = [threading.Thread(target=self._read_control, daemon=True)]
        if service == "api":
            self.readers.append(threading.Thread(target=self._read_events, daemon=True))
        for reader in self.readers:
            reader.start()
        try:
            if self.process.stdin is None:
                raise OSError("Missing owned startup pipe")
            self.process.stdin.write(encoded_startup)
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
                self.messages.put_nowait(
                    ScorerControl.model_validate_json(line)
                    if self.service == "api"
                    else ServiceControl.model_validate_json(line)
                )
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
            limit = self.max_event_bytes
            if limit is None:
                self.events_failed.set()
                return
            while line := stream.readline(limit + 1):
                if self.service != "api" or len(line) > limit or not line.endswith(b"\n"):
                    self.events_failed.set()
                    return
                event = ServerEvent.model_validate_json(line)
                sys.stderr.write(event.encode_json_line(limit).decode("utf-8"))
                sys.stderr.flush()
        except (OSError, ValueError, ValidationError):
            self.events_failed.set()

    def _matches_scorer_operation(
        self, packet: ScorerReady | ScorerStopped | ScorerStartFailed
    ) -> bool:
        return (
            isinstance(self.packet, ScorerStartupPacket)
            and packet.launch_operation_metadata == self.packet.operation_metadata
            and (
                self.observed_service_operation is None
                or packet.operation_metadata == self.observed_service_operation
            )
        )

    def wait_ready(self, timeout_ms: int) -> ScorerReady | HostReady:
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
                    self.readers[0].join(timeout=self.forced_stop_ms / 1000)
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
            or (
                self.service == "api"
                and (
                    not isinstance(packet, ScorerReady | ScorerStopped | ScorerStartFailed)
                    or packet.scorer != self.scorer
                    or not self._matches_scorer_operation(packet)
                )
            )
        ):
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", self.service)
        if isinstance(packet, ServiceStartFailed | ScorerStartFailed):
            if isinstance(packet, ScorerStartFailed):
                self.observed_service_operation = packet.operation_metadata
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
        if not isinstance(packet, ScorerReady | HostReady):
            raise WorkflowError("STARTUP_FAILED", "startup", self.service)
        if isinstance(packet, ScorerReady) and packet.process != self.expected_process:
            raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", self.service)
        if isinstance(packet, ScorerReady):
            self.observed_service_operation = packet.operation_metadata
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

    def close(self, timeout_ms: int) -> ServiceStopped | ScorerStopped:
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
                self.process.wait(timeout=self.stop_grace_ms / 1000)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=self.forced_stop_ms / 1000)
                except subprocess.TimeoutExpired:
                    raise WorkflowError("SERVICE_STOP_FAILED", "cleanup", self.service) from None
        for reader in self.readers:
            reader.join(timeout=self.forced_stop_ms / 1000)
        while not self.messages.empty():
            message = self.messages.get_nowait()
            if self.service == "api" and message is not None and (
                not isinstance(message.root, ScorerReady | ScorerStopped | ScorerStartFailed)
                or not self._matches_scorer_operation(message.root)
            ):
                self.protocol_failed.set()
                continue
            if message is not None and isinstance(message.root, ScorerReady):
                ready = message.root
                if (
                    ready.startup_id != self.packet.startup_id
                    or ready.pid != self.process.pid
                    or ready.service != self.service
                    or ready.scorer != self.scorer
                    or ready.process != self.expected_process
                ):
                    self.protocol_failed.set()
                else:
                    self.observed_service_operation = ready.operation_metadata
            if message is not None and isinstance(
                message.root, ServiceStartFailed | ScorerStartFailed
            ):
                failed = message.root
                if (
                    failed.startup_id != self.packet.startup_id
                    or failed.pid != self.process.pid
                    or failed.service != self.service
                    or (
                        isinstance(failed, ScorerStartFailed) and failed.scorer != self.scorer
                    )
                ):
                    self.protocol_failed.set()
                else:
                    if isinstance(failed, ScorerStartFailed):
                        self.observed_service_operation = failed.operation_metadata
                    self.startup_failure = failed
            if message is not None and isinstance(message.root, ServiceStopped | ScorerStopped):
                observed = message.root
                if (
                    observed.startup_id != self.packet.startup_id
                    or observed.pid != self.process.pid
                    or observed.service != self.service
                    or self.stopped is not None
                    or (
                        isinstance(observed, ScorerStopped)
                        and (
                            observed.scorer != self.scorer
                            or observed.process != self.expected_process
                        )
                    )
                ):
                    self.protocol_failed.set()
                else:
                    if isinstance(observed, ScorerStopped):
                        self.observed_service_operation = observed.operation_metadata
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
                and (
                    not isinstance(stopped, ScorerStopped)
                    or stopped.worker_exit.confirmed is False
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
