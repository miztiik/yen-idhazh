"""Which independent digest serving totals belong to a recorded work host?"""

from __future__ import annotations

import logging
import math
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.base import WORK_JOB
from idhazh.contracts.file_envelope import RowIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.llm.serving_metrics import PromptTotals

logger = logging.getLogger(__name__)

# Writer identities, not tunables. No other serving scope measures this model.
DIGEST_PIPELINE: Final = "digest"
SERVE_SUMMARIZER: Final = "serve-summarizer"


@dataclass(frozen=True, slots=True)
class HostPromptReading:
    host: HostFingerprintRow
    totals: PromptTotals | None


def _pair(tokens: int | None, seconds: float | None) -> PromptTotals | None:
    if tokens is None or seconds is None or not math.isfinite(seconds) or seconds <= 0:
        return None
    return PromptTotals(tokens, seconds)


def _is_digest_work(identity: RowIdentity) -> bool:
    if identity.pipeline_name is None:
        return identity.job == WORK_JOB
    return identity.pipeline_name == DIGEST_PIPELINE and identity.task_name == WORK_JOB


def read_host_prompt_totals(
    state: Path, days: Collection[str], *, run_id: str | None = None
) -> list[HostPromptReading]:
    """Keep each host and prefer its exact packed serving row, even if incomplete."""
    recorded: dict[tuple[str, str, int], PromptTotals | None] = {}
    serving = ledger.load_stored_days(
        state, LedgerName.TASK_PERFORMANCE, days, model=TaskPerformanceRow, packed_only=True
    )
    for held in serving:
        row, identity = held.row, held.identity
        if not isinstance(row, TaskPerformanceRow):
            raise TypeError("stored task performance differs from its declared model")
        if (
            row.pipeline_name != DIGEST_PIPELINE
            or row.task_name != SERVE_SUMMARIZER
            or row.task_kind != "model-serving"
            or row.host_unit_id is None
            or (run_id is not None and identity.run_id != run_id)
        ):
            continue
        key = (row.host_unit_id, identity.run_id, identity.attempt)
        if key in recorded:
            logger.warning("multiple digest serving rows name the same host and attempt")
            recorded[key] = None
        else:
            recorded[key] = _pair(row.server_prompt_tokens, row.server_prompt_seconds)

    result: list[HostPromptReading] = []
    for held in ledger.load_stored_days(
        state, LedgerName.HOST_FINGERPRINT, days, model=HostFingerprintRow
    ):
        host, identity = held.row, held.identity
        if not isinstance(host, HostFingerprintRow):
            raise TypeError("stored host fingerprint differs from its declared model")
        if not _is_digest_work(identity) or (run_id is not None and identity.run_id != run_id):
            continue
        key = (identity.unit_id, identity.run_id, identity.attempt)
        totals = (
            recorded[key]
            if key in recorded
            else _pair(host.server_prompt_tokens, host.server_prompt_seconds)
        )
        result.append(HostPromptReading(host, totals))
    return result
