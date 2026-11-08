"""Do authored question paths preserve native prompts, controls and recorded comparisons?"""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.unieval_cases import read_unieval_recordings, recorded_unieval_request

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.unieval_request import UnievalControls
from summary_evaluator.unieval.contracts.unieval_settings import (
    AUTHORED_UNIEVAL_VERSION,
    AuthoredUnievalSettings,
    UnievalSettings,
)
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.score_unieval import prepare_unieval


def authored_root(root: Path) -> Path:
    relative = "config/summary-evals/unieval-evaluator/settings.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_bytes((REPOSITORY / relative).read_bytes())
    authored = AuthoredUnievalSettings.model_validate_json(path.read_bytes())
    for named in authored.prompt_files.model_dump().values():
        target = root / "config" / named
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY / "config" / named).read_bytes())
    return path


@pytest.mark.parametrize(
    "named",
    (
        "/prompts/question.txt",
        "C:/prompts/question.txt",
        "https://example.test/question.txt",
        "prompts\\question.txt",
        "prompts/../question.txt",
        "prompts/./question.txt",
        "prompts//question.txt",
        "models/question.txt",
        "prompts/question.json",
    ),
)
def test_authored_paths_are_validated_without_reading_question_files(named: str) -> None:
    path = REPOSITORY / "config" / "summary-evals" / "unieval-evaluator" / "settings.json"
    raw = json.loads(path.read_bytes())
    raw["prompt_files"]["fluency"] = named
    with pytest.raises(ValidationError, match="fluency"):
        AuthoredUnievalSettings.model_validate_json(json.dumps(raw))


def test_scoring_versions_advance_without_restamping_health_or_recordings() -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    schema = AuthoredUnievalSettings.model_json_schema()
    assert schema["version"] == AUTHORED_UNIEVAL_VERSION
    assert "current_only" in schema["readCompatibility"]
    assert settings.version == UnievalSettings.model_json_schema()["version"] == "2026-11-08"
    from summary_evaluator.unieval.contracts.unieval_recording import UnievalRecordingInputs
    from summary_evaluator.unieval.contracts.unieval_result import UnievalHealth

    assert UnievalHealth.model_json_schema()["version"] == "2026-11-04"
    assert UnievalRecordingInputs.model_json_schema()["version"] == "2026-11-04"
    assert "prompt_files" not in settings.model_dump()
    path = REPOSITORY / "config" / "summary-evals" / "unieval-evaluator" / "settings.json"
    raw = json.loads(path.read_bytes())
    raw["version"] = "2026-11-04"
    with pytest.raises(ValidationError, match="version"):
        AuthoredUnievalSettings.model_validate_json(json.dumps(raw))


def test_each_resolved_question_retains_exact_file_text_and_answer_tokens(tmp_path: Path) -> None:
    path = authored_root(tmp_path)
    authored = AuthoredUnievalSettings.model_validate_json(path.read_bytes())
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(tmp_path, api)
    assert settings.prompts.positive_answer == authored.prompts.positive_answer
    assert settings.prompts.negative_answer == authored.prompts.negative_answer
    for dimension, named in authored.prompt_files.model_dump().items():
        text = (tmp_path / "config" / named).read_bytes().decode("utf-8")
        assert getattr(settings.prompts, dimension) == text
        assert not text.endswith("\n")
    assert settings.model_dump(exclude={"prompts", "version", "listener", "logging"}) == (
        authored.model_dump(exclude={"prompts", "version", "prompt_files"})
    )


def test_selected_roots_and_file_edits_change_only_the_intended_dimension(tmp_path: Path) -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    original = load_unieval_settings(REPOSITORY, api)
    for label in ("first", "second"):
        root = tmp_path / label
        path = authored_root(root)
        authored = AuthoredUnievalSettings.model_validate_json(path.read_bytes())
        target = root / "config" / authored.prompt_files.coherence
        text = f" {label}\r\n{{summary}}\r{{source}} "
        target.write_bytes(text.encode("utf-8"))
        selected = load_unieval_settings(root, api)
        assert selected.prompts.coherence == text
        assert selected.prompts.fluency == original.prompts.fluency
        target.write_bytes(f"changed {text}".encode())
        changed = load_unieval_settings(root, api)
        assert changed.prompts.coherence == f"changed {text}"
        assert selected.model_dump(exclude={"prompts"}) == changed.model_dump(exclude={"prompts"})


@pytest.mark.parametrize(
    ("body", "field"),
    (
        (None, "prompts/evaluate-fluency.txt"),
        (b"\xff", "prompts/evaluate-fluency.txt"),
        (b"question {summary} {source}", "prompts"),
        (b"question {summary!r}", "prompts"),
        (b"question {summary:>8}", "prompts"),
        (b" \n", "prompts.fluency"),
    ),
)
def test_bad_named_question_fails_before_worker_handoff(
    tmp_path: Path, body: bytes | None, field: str
) -> None:
    path = authored_root(tmp_path)
    authored = AuthoredUnievalSettings.model_validate_json(path.read_bytes())
    target = tmp_path / "config" / authored.prompt_files.fluency
    if body is None:
        target.unlink()
    else:
        target.write_bytes(body)
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    with pytest.raises(ValueError, match=field):
        load_unieval_settings(tmp_path, api)


def test_actual_moved_questions_match_every_recorded_comparison() -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    selected = load_unieval_settings(REPOSITORY, api)
    resources = load_unieval_resources(selected, REPOSITORY)
    inputs, predictions, _ = read_unieval_recordings()
    for case, recorded in zip(inputs.cases, predictions.cases, strict=True):
        settings = UnievalSettings.model_validate_json(
            selected.model_copy(update={
                "scoring": UnievalControls(
                    **case.controls.model_dump(), evaluate_relevance=True
                ),
            }).model_dump_json()
        )
        plan = prepare_unieval(recorded_unieval_request(case.request), settings, resources)
        assert plan.work == recorded.work
        assert len(plan.comparisons) == len(recorded.comparisons)
        for comparison, captured in zip(plan.comparisons, recorded.comparisons, strict=True):
            assert hashlib.sha256(comparison.prompt.encode("utf-8")).hexdigest() == (
                captured.prompt_sha256
            )
            assert comparison.dimension == captured.dimension
