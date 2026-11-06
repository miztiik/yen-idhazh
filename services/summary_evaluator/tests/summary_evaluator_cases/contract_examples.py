"""Build bounded native contract examples, not model prediction recordings."""

import json
from datetime import UTC, datetime
from pathlib import Path

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent, EventDetails
from summary_evaluator.hhem.contracts.evaluation_progress import (
    EvaluationTimings,
    EvaluationWindows,
    WindowCounts,
)
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity, RuntimeVersions
from summary_evaluator.hhem.contracts.worker_message import ScoreWindow, WindowOutcome
from summary_evaluator.hhem.resolve_ids import create_event_id
from summary_evaluator.hhem.resolve_request import resolve_request
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.shared.contracts.base import NativeContract
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult

REPOSITORY = Path(__file__).resolve().parents[4]
SETTINGS_FILE = REPOSITORY / "config" / "summary-evals" / "hhem-evaluator" / "settings.json"
API_SETTINGS_FILE = REPOSITORY / "config" / "summary-evals" / "api.json"
EXECUTION_ID = "11111111-2222-4333-8444-555555555555"
REQUEST_ID = "12345678-1234-4234-8234-123456789abc"
CORRELATION_ID = "87654321-4321-4321-8321-cba987654321"
OPERATION_ID = "99999999-8888-4777-8666-555555555555"


def read_contract[Contract: NativeContract](contract: type[Contract], payload: object) -> Contract:
    """Validate a JSON-shaped value through the real native JSON reader."""
    return contract.model_validate_json(json.dumps(payload))


def example_model() -> ModelIdentity:
    """Supply format examples, never evidence of loaded model bytes."""
    settings = load_settings(SETTINGS_FILE)
    return ModelIdentity(
        reference=settings.hhem.model.reference,
        configured_revision=settings.hhem.model.revision,
        loaded_revision=settings.hhem.model.revision,
        foundation_reference=settings.hhem.foundation.reference,
        foundation_revision=settings.hhem.foundation.revision,
        runtime_versions=RuntimeVersions(
            python="3.12.12", pytorch="2.8.0+cpu", transformers="4.57.6"
        ),
    )


def example_worker() -> WorkerIdentity:
    return WorkerIdentity(generation=1, pid=1234, start_ticks="5678", pin_unavailable_reason=None)


def example_result() -> EvaluationResult:
    settings = load_settings(SETTINGS_FILE)
    effective = resolve_request(
        EvaluateRequest(source_text="Project-authored source.", summary_text="Source summary."),
        settings,
    )
    return EvaluationResult(
        version=SCHEMA_VERSION,
        status="complete",
        execution_id=EXECUTION_ID,
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
        terminal_event_id=create_event_id(EXECUTION_ID, 4),
        hhem=0.75,
        hhem_full=None,
        hhem_delta=None,
        effective_settings=effective,
        windows=EvaluationWindows(
            primary=WindowCounts(planned=1, scored=1), full=None, full_reused_primary=False
        ),
        model=example_model(),
        worker=example_worker(),
        timings_ms=EvaluationTimings(queue_wait=0, primary_scoring=0, full_scoring=None, total=0),
        errors=(),
    )


def example_event() -> EvaluationEvent:
    return EvaluationEvent(
        version=SCHEMA_VERSION,
        event_id=create_event_id(EXECUTION_ID, 1),
        execution_id=EXECUTION_ID,
        sequence=1,
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
        caused_by_event_id=None,
        run_id=None,
        pipeline_name=None,
        task_name=None,
        operation_id=OPERATION_ID,
        operation="request",
        phase="started",
        occurred_at=datetime(2026, 11, 2, tzinfo=UTC),
        level="INFO",
        details=EventDetails(),
    )


def example_command() -> ScoreWindow:
    return ScoreWindow(
        version=SCHEMA_VERSION,
        kind="score_window",
        execution_id=EXECUTION_ID,
        generation=1,
        comparison="primary",
        window_index=0,
        start_word=0,
        end_word=4,
        source_text="A project-authored source canary.",
        summary_text="A project-authored summary canary.",
    )


def example_window_outcome() -> WindowOutcome:
    command = example_command()
    return WindowOutcome(
        version=command.version,
        kind="window_scored",
        execution_id=command.execution_id,
        generation=command.generation,
        comparison=command.comparison,
        window_index=command.window_index,
        start_word=command.start_word,
        end_word=command.end_word,
        score=0.75,
        scoring_ms=0,
        error=None,
    )


def example_unieval_result(reference_hash: str) -> UnievalResult:
    """Supply zero-valued contract examples, not model prediction evidence."""
    from summary_evaluator.serve_http.api_settings import load_api_settings
    from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
    from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
    from summary_evaluator.unieval.contracts.unieval_request import EffectiveUnievalControls
    from summary_evaluator.unieval.contracts.unieval_result import (
        DimensionWork,
        SourceSpan,
        UnievalModelIdentity,
        UnievalScores,
        UnievalTimings,
        UnievalWork,
    )

    api = load_api_settings(API_SETTINGS_FILE)
    settings = load_unieval_settings(REPOSITORY, api)
    model = UnievalModelIdentity.model_validate_json(
        (
            REPOSITORY / "tests" / "fixtures" / "unieval-evaluator" / "model-identity.json"
        ).read_bytes()
    )
    work = DimensionWork(planned=1, completed=1)
    return UnievalResult(
        version=UNIEVAL_VERSION,
        status="complete",
        execution_id=OPERATION_ID,
        request_id=REQUEST_ID,
        correlation_id=CORRELATION_ID,
        reference_summary_sha256=reference_hash,
        model=model,
        worker=example_worker().model_copy(update={"pid": 1235}),
        effective_settings=EffectiveUnievalControls(
            **settings.scoring.model_dump(),
            source_budget_tokens=settings.scoring.source_window_tokens,
        ),
        scores=UnievalScores(fluency=0.0, coherence=0.0, consistency=0.0, relevance=0.0),
        work=UnievalWork(
            fluency=work,
            coherence=work,
            consistency=work,
            relevance=work,
            summary_sentences=1,
            source_characters=1,
            source_spans=(SourceSpan(start=0, end=1),),
        ),
        timings_ms=UnievalTimings(queue_wait=0, scoring=0, total=0),
        errors=(),
    )
