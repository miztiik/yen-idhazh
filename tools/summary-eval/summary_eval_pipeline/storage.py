"""How are named same-run results bounded, validated and atomically replaced?"""

import hashlib
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .failures import WorkflowError
from .phase_contracts import PhaseDocument, PhaseResult
from .report_contracts import PipelineDocument, PipelineResult
from .run_contracts import (
    GenerationDocument,
    GenerationResult,
    PreparedDocument,
    PreparedResult,
)


def write_result(path: Path, value: BaseModel) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = value.model_dump_json().encode("utf-8")
    temporary.write_bytes(encoded)
    temporary.replace(path)
    return hashlib.sha256(encoded).hexdigest()


def read_result_bytes(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            encoded = stream.read(limit + 1)
        if len(encoded) > limit:
            raise ValueError("Oversized same-run result")
        return encoded
    except (OSError, ValueError, ValidationError):
        raise WorkflowError("RECEIPT_INVALID", "input") from None


def read_result[Result: BaseModel](path: Path, contract: type[Result], limit: int) -> Result:
    try:
        return contract.model_validate_json(read_result_bytes(path, limit))
    except (ValueError, ValidationError):
        raise WorkflowError("RECEIPT_INVALID", "input") from None


def read_prepared_result(path: Path, limit: int) -> PreparedResult:
    return read_result(path, PreparedDocument, limit).root


def read_generation_result(path: Path, limit: int) -> tuple[GenerationResult, str]:
    encoded = read_result_bytes(path, limit)
    try:
        receipt = GenerationDocument.model_validate_json(encoded).root
    except (ValueError, ValidationError):
        raise WorkflowError("RECEIPT_INVALID", "input") from None
    return receipt, hashlib.sha256(encoded).hexdigest()


def read_phase_result(path: Path, limit: int) -> PhaseResult:
    return read_result(path, PhaseDocument, limit).root


def read_pipeline_result(path: Path, limit: int) -> PipelineResult:
    return read_result(path, PipelineDocument, limit).root
