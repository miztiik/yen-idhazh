"""How are native worker packets bounded and encoded without object pickle?"""

import sys

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity, RuntimeVersions
from summary_evaluator.hhem.contracts.worker_message import (
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerReady,
)
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.shared.exchange_packets import (
    JSON_ESCAPE_MAX_BYTES,
    RUNTIME_VERSION_MAX_CHARS,
    UUID4_EXAMPLE,
)


def command_byte_limit(bootstrap: WorkerBootstrap, generation: int) -> int:
    settings = bootstrap.settings
    largest_index = settings.listener.max_body_bytes
    metadata = ScoreWindow(
        version=SCHEMA_VERSION,
        kind="score_window",
        execution_id=UUID4_EXAMPLE,
        generation=generation,
        comparison="primary",
        window_index=largest_index,
        start_word=largest_index,
        end_word=largest_index + 1,
        source_text="x",
        summary_text="x",
    ).model_dump_json()
    return max(
        len(bootstrap.model_dump_json().encode("utf-8")),
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes + len(metadata),
    )


def reply_byte_limit(bootstrap: WorkerBootstrap, generation: int) -> int:
    """Account for finite replies plus the configured identity-read allowance."""
    settings = bootstrap.settings
    worker = WorkerIdentity(
        generation=generation,
        pid=sys.maxsize,
        start_ticks="9" * settings.worker.max_proc_identity_bytes,
        pin_unavailable_reason=None,
    )
    ready = WorkerReady(
        version=SCHEMA_VERSION,
        kind="ready",
        worker=worker,
        model=ModelIdentity(
            reference=settings.hhem.model.reference,
            configured_revision=settings.hhem.model.revision,
            loaded_revision=settings.hhem.model.revision,
            foundation_reference=settings.hhem.foundation.reference,
            foundation_revision=settings.hhem.foundation.revision,
            runtime_versions=RuntimeVersions(
                python="x" * RUNTIME_VERSION_MAX_CHARS,
                pytorch="x" * RUNTIME_VERSION_MAX_CHARS,
                transformers="x" * RUNTIME_VERSION_MAX_CHARS,
            ),
        ),
    )
    largest_index = settings.listener.max_body_bytes
    outcomes = [
        WindowOutcome(
            version=SCHEMA_VERSION,
            kind="window_failed",
            execution_id=UUID4_EXAMPLE,
            generation=generation,
            comparison="primary",
            window_index=largest_index,
            start_word=largest_index,
            end_word=largest_index + 1,
            score=None,
            scoring_ms=sys.float_info.max,
            error=ErrorDetail.from_code(code, "primary", window_index=largest_index),
        )
        for code in ERROR_POLICIES
    ]
    # A ready packet includes the larger worker/model identity; a failed outcome
    # includes more metadata than success and the longest closed error wording.
    return max(len(packet.model_dump_json().encode("utf-8")) for packet in (ready, *outcomes))
