"""Build bounded handoff inputs and use saved native replies at model boundaries."""

import json
from datetime import UTC, datetime
from pathlib import Path
from string import Template

from idhazh.llm.server import SystemPlacement, TurnMarkers
from summary_eval_pipeline.contracts import (
    WORKFLOW_VERSION,
    GenerationReceipt,
    LoadedModel,
    PreparedRun,
    RunIdentity,
    text_sha256,
)
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.model_selection import SelectedModel, select_model

from .contract_examples import REPOSITORY
from .replay_predictions import read_recordings


def example_run() -> RunIdentity:
    return RunIdentity(
        run_id="123456",
        attempt=1,
        git_sha="a" * 40,
        started_at=datetime(2026, 11, 4, 17, tzinfo=UTC),
    )


def selected_root(directory: Path) -> None:
    config = directory / "config"
    (config / "models").mkdir(parents=True)
    for name in (
        "idhazh.json",
        "models/ornith-1.5-9b-q5km.json",
        "models/qwen3.5-9b-q4km.json",
        "summary-eval-tests.json",
        "fastapi-server.json",
        "hhem-evaluator/settings.json",
        "unieval-evaluator.json",
    ):
        (config / name).parent.mkdir(parents=True, exist_ok=True)
        (config / name).write_bytes((REPOSITORY / "config" / name).read_bytes())


def handoff_case() -> tuple[ManualInputs, PreparedRun, GenerationReceipt]:
    cases, _, _ = read_recordings(REPOSITORY)
    case = cases.cases[0]
    inputs = ManualInputs(
        source_text=case.source_text,
        reference_summary_text=(
            "The library opened a reading room on Monday, with twelve desks and no booking."
        ),
    )
    selected = select_model(REPOSITORY, "")
    prepared = PreparedRun(
        version=WORKFLOW_VERSION,
        run=example_run(),
        selected=selected.identity,
        source_sha256=text_sha256(inputs.source_text),
        reference_summary_sha256=text_sha256(inputs.reference_summary_text),
        status="complete",
        errors=(),
    )
    receipt = GenerationReceipt(
        version=WORKFLOW_VERSION,
        run=prepared.run,
        selected=prepared.selected,
        loaded=LoadedModel(
            model_id=prepared.selected.model_id,
            pid=123,
            weights_path=f"backend/models/{prepared.selected.filename}",
            sha256=prepared.selected.sha256,
        ),
        source_sha256=prepared.source_sha256,
        reference_summary_sha256=prepared.reference_summary_sha256,
        summary_text=case.summary_text,
        summary_sha256=text_sha256(case.summary_text),
        status="complete",
        errors=(),
    )
    return inputs, prepared, receipt


def recorded_selection(directory: Path) -> SelectedModel:
    """Declare the response's captured alias; no runtime or weights are simulated."""
    selected_root(directory)
    name = "models/ornith-1.5-9b-q5km.json"
    path = directory / "config" / name
    declaration = json.loads(path.read_bytes())
    response = json.loads(
        (REPOSITORY / "tests" / "fixtures" / "completions" / "reasoning-channel.json").read_bytes()
    )
    declaration["summarizer"]["id"] = response["model"]
    path.write_text(json.dumps(declaration), encoding="utf-8")
    return select_model(directory, name)


def chat_markers(selected: SelectedModel) -> TurnMarkers:
    # These are request-builder inputs, not a simulated template API or model.
    return TurnMarkers(
        turn_opening=Template("<|im_start|>$role\n"),
        turn_closing="<|im_end|>\n",
        reply_opening="<|im_start|>assistant\n",
        reply_opening_thinking="<|im_start|>assistant\n<think>\n",
        system_role=SystemPlacement.OWN_TURN,
        system_joiner="",
        thinking_close=selected.entry.thinking_close,
        thinking_kwarg=selected.entry.thinking_kwarg,
        chat_template_kwargs=selected.entry.chat_template_kwargs,
        reasoning_delimiters=selected.entry.reasoning_delimiters,
    )
