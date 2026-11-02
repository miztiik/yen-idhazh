"""How does one existing host handle measure the original scoring worker only?"""

import json
from dataclasses import dataclass

import httpx

from .call_local_api import call_local_api
from .contracts.host_profile_reader import (
    DisabledProfile,
    ProcessPin,
    StartedProfile,
    StartProfileResponse,
    StoppedProfile,
    StopProfileResponse,
    TaskIdentity,
    TaskOutcome,
    TaskProfile,
)
from .contracts.worker_identity import WorkerIdentity
from .contracts.workflow_report import ResourceReason, ResourceStatus, WorkflowError
from .fail_manual_evaluation import WorkflowFailure
from .load_manual_settings import ManualSettings

# These are the existing host API's calendar-versioned protocol routes.
START_PROFILE_PATH = "/api/2026-10-24/start-task-profile"
STOP_PROFILE_PATH = "/api/2026-10-24/stop-task-profile"


@dataclass
class TaskMeasurement:
    initial_worker: WorkerIdentity
    identity: TaskIdentity
    started: StartedProfile | None = None
    profile: TaskProfile | None = None
    reason: ResourceReason | None = None
    stop_attempted: bool = False

    async def start(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        manual: ManualSettings,
        timeout_ms: int,
    ) -> WorkflowError | None:
        worker = self.initial_worker
        if worker.start_ticks is None:
            self.reason = "pin_unavailable"
            return None
        target = ProcessPin(pid=worker.pid, start_ticks=worker.start_ticks)
        body = json.dumps(
            {
                "identity": self.identity.model_dump(mode="json"),
                "target": target.model_dump(mode="json"),
            }
        ).encode()
        try:
            status, response = await call_local_api(
                client,
                "POST",
                base_url + START_PROFILE_PATH,
                StartProfileResponse,
                manual,
                timeout_ms,
                service="host",
                phase="profile",
                body=body,
            )
            result = response.root
            if status != 200:
                raise WorkflowFailure("PROFILE_START_FAILED", "profile", "host", status)
            if isinstance(result, DisabledProfile):
                self.reason = "configured_off"
            elif result.target != target:
                raise WorkflowFailure("STARTUP_IDENTITY_MISMATCH", "profile", "host", status)
            else:
                self.started = result
        except WorkflowFailure as failure:
            self.reason = "profile_start_failed"
            return failure.error
        return None

    async def stop(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        manual: ManualSettings,
        timeout_ms: int,
        outcome: TaskOutcome,
    ) -> WorkflowError | None:
        if self.started is None or self.stop_attempted:
            return None
        self.stop_attempted = True
        body = json.dumps({"handle": self.started.handle, "outcome": outcome}).encode()
        try:
            status, response = await call_local_api(
                client,
                "POST",
                base_url + STOP_PROFILE_PATH,
                StopProfileResponse,
                manual,
                timeout_ms,
                service="host",
                phase="cleanup",
                body=body,
            )
            result = response.root
            if (
                status != 200
                or not isinstance(result, StoppedProfile)
                or result.handle != self.started.handle
                or result.profile.identity != self.identity
            ):
                raise WorkflowFailure("PROFILE_STOP_FAILED", "cleanup", "host", status)
            self.profile = result.profile
        except WorkflowFailure as failure:
            self.reason = "profile_stop_failed"
            return failure.error
        return None

    def coverage(
        self,
        final_worker: WorkerIdentity | None,
    ) -> tuple[ResourceStatus, ResourceReason | None]:
        if (
            self.started is not None
            and final_worker is not None
            and final_worker != self.initial_worker
        ):
            return "incomplete", "worker_replaced"
        if self.reason is not None:
            status: ResourceStatus = "incomplete" if self.started is not None else "unavailable"
            return status, self.reason
        profile = self.profile
        if profile is None:
            return "unavailable", "measurement_unavailable"
        if profile.end_reason != "explicit_stop" or profile.outcome == "cancelled":
            return "incomplete", "profile_interrupted"
        if final_worker is None:
            return "incomplete", "measurement_unavailable"
        worker = profile.processes.worker
        if worker.cpu.reason is not None or worker.sampled_rss_max_kb is None:
            return "incomplete", "measurement_unavailable"
        return "complete", None
