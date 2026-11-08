"""How are native worker packets bounded and encoded without object pickle?"""

import sys

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity, RuntimeVersions
from summary_evaluator.hhem.contracts.worker_contract import HHEM_WORKER_VERSION
from summary_evaluator.hhem.contracts.worker_message import (
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerFailed,
    WorkerReady,
    WorkerStarted,
)
from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.shared.exchange_packets import (
    JSON_ESCAPE_MAX_BYTES,
    RUNTIME_VERSION_MAX_CHARS,
    UUID4_EXAMPLE,
)


def command_byte_limit(bootstrap: WorkerBootstrap, generation: int) -> int:
    settings = bootstrap.settings
    largest_index = settings.listener.max_body_bytes
    example = ScoreWindow(
        version=HHEM_WORKER_VERSION,
        operation_metadata=maximum_worker_operation_metadata(),
        kind="score_window",
        execution_id=UUID4_EXAMPLE,
        generation=generation,
        comparison="primary",
        window_index=largest_index,
        start_word=largest_index,
        end_word=largest_index + 1,
        source_text="x",
        summary_text="x",
    )
    metadata_bytes = len(example.model_dump_json().encode("utf-8")) - (
        len(example.source_text.encode("utf-8")) + len(example.summary_text.encode("utf-8"))
    )
    return max(
        len(bootstrap.model_dump_json().encode("utf-8")),
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes + metadata_bytes,
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
        version=HHEM_WORKER_VERSION,
        operation_metadata=maximum_worker_operation_metadata(),
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
            version=HHEM_WORKER_VERSION,
            operation_metadata=maximum_worker_operation_metadata(),
            kind="window_failed",
            execution_id=UUID4_EXAMPLE,
            generation=generation,
            comparison="primary",
            window_index=largest_index,
            start_word=largest_index,
            end_word=largest_index + 1,
            score=None,
            scoring_ms=sys.float_info.min,
            error=ErrorDetail.from_code(code, "primary", window_index=largest_index),
        )
        for code in ERROR_POLICIES
    ]
    startup_codes: tuple[ErrorCode, ...] = (
        "MODEL_LOAD_FAILED",
        "MODEL_IDENTITY_CHANGED",
        "WORKER_PROTOCOL_FAILED",
        "INTERNAL_ERROR",
    )
    startup_failures = [
        WorkerFailed(
            version=HHEM_WORKER_VERSION,
            operation_metadata=maximum_worker_operation_metadata(),
            kind="worker_failed",
            worker=worker,
            error=ErrorDetail.from_code(code, "worker"),
        )
        for code in startup_codes
    ]
    started = WorkerStarted(
        version=HHEM_WORKER_VERSION,
        operation_metadata=maximum_worker_operation_metadata(),
        kind="worker_started",
        worker=worker,
    )
    return max(
        len(packet.model_dump_json().encode("utf-8"))
        for packet in (started, ready, *startup_failures, *outcomes)
    )
