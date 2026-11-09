"""Which selected-score phases retain their original API and unmeasured error evidence?"""

from typing import Literal, Self

from pydantic import ConfigDict, StrictBool, model_validator
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.shared.contracts.base import OutcomeStatus, Sha256, Uuid4
from summary_evaluator.unieval.contracts.previous_selected_unieval_result import (
    PreviousSelectedUnievalResult,
)

from .contracts import Hardware, PhaseName, PipelineError, RunIdentity, ServerOutcome
from .host_reader import HonoServerReader, MachineUsage, measurement_complete
from .scorer_evidence import EvidenceContract, ScorerApiEvidence


class PhaseShutdown(EvidenceContract):
    host_stopped: bool | None
    llama_stopped: bool | None = None


class PhaseEvidence(EvidenceContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-08",
            "readCompatibility": "read frozen phases by exact version without inventing selection",
            "changelog": [
                {
                    "version": "2026-11-08",
                    "change": "Bind optional reference and relevance selection.",
                },
                {"version": "2026-11-07", "change": "Record independent API lifetimes."},
            ],
        }
    )

    version: Literal["2026-11-08"]
    run: RunIdentity
    phase: PhaseName
    status: OutcomeStatus
    evaluation: EvaluationResult | None
    unieval: PreviousSelectedUnievalResult | None = None
    scorer_apis: tuple[ScorerApiEvidence, ...] = ()
    evaluation_request_id: Uuid4 | None = None
    evaluation_correlation_id: Uuid4 | None = None
    reference_summary_sha256: Sha256 | None
    evaluate_relevance: StrictBool
    hardware: Hardware | None
    machine: MachineUsage | None
    shutdown: PhaseShutdown
    servers: tuple[HonoServerReader | ServerOutcome, ...]
    errors: tuple[PipelineError, ...]
    generation_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def require_consistent_observations(self) -> Self:
        work = (
            self.evaluation is not None
            and self.evaluation.status == "complete"
            and self.unieval is not None
            and self.unieval.status == "complete"
            and {api.scorer for api in self.scorer_apis} == {"hhem", "unieval"}
            and all(
                api.health is not None
                and api.health.status == "ready"
                and api.outcome.startup == "ready"
                and api.outcome.shutdown == "stopped"
                and api.worker_exit.confirmed is True
                and api.worker_exit.pid == getattr(api.health, api.scorer).worker.pid
                and not api.errors
                for api in self.scorer_apis
            )
            if self.phase == "evaluation"
            else self.shutdown.llama_stopped is True and not self.scorer_apis
        )
        score = (
            self.evaluation is not None and self.evaluation.hhem is not None
        ) or (
            self.unieval is not None
            and any(value is not None for value in self.unieval.scores.model_dump().values())
        )
        complete = (
            work
            and self.shutdown.host_stopped is True
            and self.hardware is not None
            and self.hardware.status == "collected"
            and measurement_complete(self.machine)
            and not self.errors
        )
        if self.status != ("complete" if complete else "partial" if score else "failed"):
            raise ValueError("Status must describe actual work, measurements and cleanup")
        names = [api.scorer for api in self.scorer_apis]
        processes = [api.process.pid for api in self.scorer_apis if api.process is not None]
        instances = [
            api.service_instance_id for api in self.scorer_apis
            if api.service_instance_id is not None
        ]
        listeners = [(api.listener.host, api.listener.port) for api in self.scorer_apis]
        if (
            len(set(names)) != len(names)
            or len(set(processes)) != len(processes)
            or len(set(instances)) != len(instances)
            or len(set(listeners)) != len(listeners)
        ):
            raise ValueError("Scorers require distinct API process and application identities")
        if any(server.server_name == "fastapi-server" for server in self.servers):
            raise ValueError("API outcomes belong only in their scorer records")
        if any(
            error.service == "api"
            or (
                error.service in ("hhem", "unieval")
                and error.phase in ("startup", "health", "cleanup")
            )
            for error in self.errors
        ) or any(error in self.errors for api in self.scorer_apis for error in api.errors):
            raise ValueError("Scorer lifecycle errors belong only in their scorer records")
        if self.phase == "generation" and (
            self.evaluation is not None or self.unieval is not None or self.scorer_apis
        ):
            raise ValueError("Generation starts and scores no evaluator")
        if (
            self.phase == "generation"
            and self.status == "complete"
            and self.generation_sha256 is None
        ):
            raise ValueError("Complete generation requires the saved receipt's byte identity")
        workers: list[int] = []
        for api in self.scorer_apis:
            if api.health is not None:
                worker = getattr(api.health, api.scorer).worker
                if worker is not None:
                    workers.append(worker.pid)
        for name, result in (("hhem", self.evaluation), ("unieval", self.unieval)):
            if result is None:
                continue
            owner_record = next((api for api in self.scorer_apis if api.scorer == name), None)
            if (
                owner_record is None or owner_record.health is None
                or self.generation_sha256 is None
                or self.evaluation_request_id != result.request_id
                or self.evaluation_correlation_id != result.correlation_id
            ):
                raise ValueError("Scoring requires its owned API and bound request/receipt")
            observed = getattr(owner_record.health, name)
            if (
                (result.model is not None and result.model != observed.model)
                or (result.worker is not None and result.worker != observed.worker)
            ):
                raise ValueError("Scoring must retain its observed model and worker identity")
        if len(set(workers)) != len(workers) or set(workers) & set(processes):
            raise ValueError("Each model worker must be independently owned")
        if self.unieval is not None and (
            self.unieval.reference_summary_sha256 != self.reference_summary_sha256
            or (
                self.unieval.effective_settings is not None
                and self.unieval.effective_settings.evaluate_relevance != self.evaluate_relevance
            )
        ):
            raise ValueError("UniEval must retain the exact reference and relevance selection")
        return self
