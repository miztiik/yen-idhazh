"""Which gardener control runners own one native opening fingerprint?"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.telemetry import machine_evidence, silicon


class Job(StrEnum):
    PLAN = "plan"
    HISTORY = "history"
    APPEND = "publish-fingerprints"


def expected(
    job: Job, *, run_id: str, attempt: int, revision: str,
) -> machine_evidence.ExpectedFile:
    day = date.fromisoformat(run_id[:10]).isoformat()
    return machine_evidence.ExpectedFile(
        WriterIdentity(
            job=f"gardener-{job}", shard=0, run_id=run_id, attempt=attempt,
            git_sha=revision, producer=silicon.PRODUCER,
        ),
        day, native=True,
    )


def artifact(job: Job, run_id: str, attempt: int) -> str:
    return f"gardener-fingerprint-{job}-{run_id}-{attempt}"
