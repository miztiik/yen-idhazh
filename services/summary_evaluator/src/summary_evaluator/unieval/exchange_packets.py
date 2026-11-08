"""How does a UniEval command account for complete metadata and generated caller UUIDs?"""

from typing import get_args

from summary_evaluator.shared.bound_operation_metadata import maximum_worker_operation_metadata
from summary_evaluator.shared.exchange_packets import JSON_ESCAPE_MAX_BYTES, UUID4_EXAMPLE
from summary_evaluator.unieval.contracts.unieval_contract import SourceMode
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    UnievalBootstrap,
    UnievalCommand,
)


def command_byte_limit(settings: UnievalSettings, generation: int) -> int:
    """Derive the existing body allowance plus every private field and JSON escape."""
    bootstrap = UnievalBootstrap(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=maximum_worker_operation_metadata(),
        settings=settings,
    )
    modes: tuple[SourceMode, ...] = get_args(SourceMode)
    mode: SourceMode = max(modes, key=len)
    request = UnievalRequest(
        source_text="x",
        summary_text="x",
        reference_summary_text="x",
        evaluate_relevance=False,
        consistency_source_mode=mode,
        request_id=UUID4_EXAMPLE,
        correlation_id=UUID4_EXAMPLE,
    )
    example = UnievalCommand(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=maximum_worker_operation_metadata(),
        execution_id=UUID4_EXAMPLE,
        generation=generation,
        request=request,
    )
    metadata_bytes = len(example.model_dump_json().encode("utf-8")) - sum(
        len(text.encode("utf-8"))
        for text in (request.source_text, request.summary_text, request.reference_summary_text)
        if text is not None
    )
    return max(
        len(bootstrap.model_dump_json().encode("utf-8")),
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes + metadata_bytes,
    )
