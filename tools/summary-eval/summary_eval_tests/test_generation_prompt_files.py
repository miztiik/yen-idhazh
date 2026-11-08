"""Does the native caller receive exactly its configured generation instruction file?"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from summary_eval_pipeline.generation import generate_summary
from summary_eval_pipeline.settings import (
    AuthoredPipelineSettings,
    PipelineSettings,
    load_pipeline_settings,
)
from summary_evaluator_cases.contract_examples import REPOSITORY

from summary_eval_tests.generation_cases import chat_markers, native_generation_case
from summary_eval_tests.native_cases import RecordedLlama


def workflow_root(root: Path) -> tuple[Path, AuthoredPipelineSettings]:
    relative = "config/summary-evals/workflow.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_bytes((REPOSITORY / relative).read_bytes())
    authored = AuthoredPipelineSettings.model_validate_json(path.read_bytes())
    target = root / "config" / authored.generation_prompt_file
    target.parent.mkdir(parents=True)
    target.write_bytes((REPOSITORY / "config" / authored.generation_prompt_file).read_bytes())
    return path, authored


@pytest.mark.parametrize(
    "named",
    (
        "/prompts/a.txt",
        "C:/prompts/a.txt",
        "https://example.test/a.txt",
        "prompts\\a.txt",
        "prompts/../a.txt",
        "prompts/./a.txt",
        "prompts//a.txt",
        "models/a.txt",
        "prompts/a.json",
    ),
)
def test_workflow_prompt_paths_are_refused_at_the_authored_boundary(
    tmp_path: Path, named: str
) -> None:
    path, _ = workflow_root(tmp_path)
    raw = json.loads(path.read_bytes())
    raw["generation_prompt_file"] = named
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="generation_prompt_file"):
        load_pipeline_settings(tmp_path)


def test_resolved_workflow_keeps_transport_and_lifecycle_controls(tmp_path: Path) -> None:
    _, authored = workflow_root(tmp_path)
    resolved = load_pipeline_settings(tmp_path)
    assert resolved.model_dump(exclude={"generation_instruction"}) == authored.model_dump(
        exclude={"version", "generation_prompt_file"}
    )
    body = (tmp_path / "config" / authored.generation_prompt_file).read_bytes()
    assert resolved.generation_instruction == body.decode("utf-8")
    assert not body.endswith(b"\n")
    assert PipelineSettings.model_json_schema()["version"] == "2026-11-05"
    schema = AuthoredPipelineSettings.model_json_schema()
    assert schema["version"] == "2026-11-07"
    assert "current_only" in schema["readCompatibility"]


def test_old_inline_generation_settings_are_not_a_second_active_default(tmp_path: Path) -> None:
    path, authored = workflow_root(tmp_path)
    raw = authored.model_dump(mode="json")
    raw["generation_instruction"] = "An obsolete inline default."
    del raw["generation_prompt_file"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        AuthoredPipelineSettings.model_validate_json(path.read_bytes())


def test_workflow_roots_and_file_changes_preserve_all_whitespace(tmp_path: Path) -> None:
    for name in ("first", "second"):
        root = tmp_path / name
        _, authored = workflow_root(root)
        target = root / "config" / authored.generation_prompt_file
        text = f"  {name}\r\nLiteral {{summary}} and $not_a_placeholder. "
        target.write_bytes(text.encode("utf-8"))
        assert load_pipeline_settings(root).generation_instruction == text
        target.write_bytes(f"{text}\n".encode())
        assert load_pipeline_settings(root).generation_instruction == f"{text}\n"


@pytest.mark.parametrize("body", (None, b"\xff", b" \n"))
def test_bad_generation_files_fail_before_calling_a_model(
    tmp_path: Path, body: bytes | None
) -> None:
    _, authored = workflow_root(tmp_path)
    target = tmp_path / "config" / authored.generation_prompt_file
    if body is None:
        target.unlink()
        field = authored.generation_prompt_file
    else:
        target.write_bytes(body)
        field = authored.generation_prompt_file if body == b"\xff" else "generation_instruction"
    with pytest.raises(ValueError, match=field):
        load_pipeline_settings(tmp_path)


def test_native_generation_receives_the_selected_file_in_fresh_requests(tmp_path: Path) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        authored = AuthoredPipelineSettings.model_validate_json(
            (tmp_path / "config" / "summary-evals" / "workflow.json").read_bytes()
        )
        target = tmp_path / "config" / authored.generation_prompt_file
        text = "  Preserve this exact instruction.\r\nReturn a title and summary. "
        target.write_bytes(text.encode("utf-8"))
        recorded = RecordedLlama()
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            for _ in range(2):
                receipt = await generate_summary(
                    client,
                    inputs,
                    prepared,
                    selected,
                    loaded,
                    chat_markers(selected),
                    load_pipeline_settings(tmp_path),
                )
                assert receipt.status == "complete"
        assert recorded.requests[0][1] == recorded.requests[1][1]
        body = json.loads(recorded.requests[0][1])
        assert body["messages"] == [
            {"role": "system", "content": text},
            {"role": "user", "content": inputs.source_text},
        ]
        assert inputs.reference_summary_text not in recorded.requests[0][1].decode("utf-8")
        assert body["temperature"] == selected.entry.sampling["temperature"]

    asyncio.run(check())
