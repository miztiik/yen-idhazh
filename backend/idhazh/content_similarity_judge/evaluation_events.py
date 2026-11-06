"""Which evaluator progress and diagnostics can reach structured stderr?"""

from __future__ import annotations

import logging
from typing import Literal, TextIO

from idhazh import event_lines
from idhazh.contracts.base import Model, RelPath, Sha256
from idhazh.contracts.story_similarity_pair import ReadingRefusalReason


class EvaluationCaptureStarted(Model):
    file: RelPath


class EvaluationReadingRefused(Model):
    case_id: Sha256
    order: Literal["forward", "reverse"]
    reason: ReadingRefusalReason


class EvaluationEvidenceRefused(Model):
    scope: Literal["set", "capture"]
    case_id: Sha256 | None = None
    reason: Literal["provenance_mismatch"] = "provenance_mismatch"


class EvaluationDiagnostic(Model):
    kind: Literal["log"] = "log"
    error: str | None = None
    where: str | None = None


def _without_text(record: logging.LogRecord) -> EvaluationDiagnostic:
    cause = event_lines.cause_of(None if record.exc_info is None else record.exc_info[1])
    return EvaluationDiagnostic(error=cause.error, where=cause.where)


def configure_logging(logger: logging.Logger, *, stream: TextIO | None = None) -> None:
    """Configure one process's JSON/UTC handler without exposing unstructured text."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(event_lines.OneJsonLine(_without_text))
    for previous in tuple(logger.handlers):
        logger.removeHandler(previous)
        previous.close()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
