"""Does the evaluator's shared JSON formatter retain safe metadata and discard raw diagnostics?"""

import io
import json
import logging
from datetime import UTC, datetime

from idhazh import event_lines
from idhazh.content_similarity_judge.evaluation_events import (
    EvaluationCaptureStarted,
    EvaluationReadingRefused,
    configure_logging,
)
from idhazh.contracts.story_similarity_pair import ReadingRefusalReason


def test_progress_and_library_diagnostics_are_json_utc_and_text_free() -> None:
    output = io.StringIO()
    logger = logging.Logger("evaluation-boundary")
    configure_logging(logger, stream=output)
    assert isinstance(logger.handlers[0].formatter, event_lines.OneJsonLine)
    filename = f"run-{'a' * 64}.json"
    event_lines.emit(EvaluationCaptureStarted(file=filename), logger=logger)
    secret = "PRIVATE_SOURCE_AND_MODEL https://invalid.test/?token=do-not-log\nraw text"
    logger.warning("unstructured library text: %s", secret)
    try:
        raise ValueError(secret)
    except ValueError:
        logger.exception("unstructured failure: %s", secret)
    event_lines.emit(
        EvaluationReadingRefused(
            case_id="b" * 64, order="forward",
            reason=ReadingRefusalReason.INVALID_LITERAL,
        ),
        logger=logger, level=logging.WARNING,
    )
    rendered = output.getvalue()
    records = [json.loads(line) for line in rendered.splitlines()]
    assert [record["event"] for record in records] == [
        "evaluation-capture-started", "evaluation-diagnostic",
        "evaluation-diagnostic", "evaluation-reading-refused",
    ]
    assert records[0]["file"] == filename
    assert records[1]["kind"] == records[2]["kind"] == "log"
    assert records[2]["error"] == "ValueError"
    assert records[3]["reason"] == "invalid_literal"
    assert all(datetime.fromisoformat(record["at"]).tzinfo == UTC for record in records)
    assert [record["level"] for record in records] == ["info", "warning", "error", "warning"]
    assert not any(word in rendered for word in (
        "PRIVATE_SOURCE_AND_MODEL", "do-not-log", "unstructured library text",
        "unstructured failure", "Traceback",
    ))
