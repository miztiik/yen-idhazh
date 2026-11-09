"""Verify the direct native caller's transport bounds and fresh request boundary."""

import asyncio
import json
import math
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import GeneratedAnswer
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.generation import generate_summary
from summary_eval_pipeline.llama import OwnedLlama
from summary_eval_pipeline.model_selection import NativeGenerationSettings, select_model
from summary_eval_pipeline.native_response import NativeCompletion, NativeReply
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator_cases.contract_examples import REPOSITORY

from idhazh.llm.server import request_payload
from summary_eval_tests.generation_cases import chat_markers, native_generation_case
from summary_eval_tests.native_cases import RecordedLlama


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:8080",
        "http://example.test:8080",
        "http://127.0.0.1",
        "http://user:password@127.0.0.1:8080",
        "http://127.0.0.1:8080/completions",
        "http://127.0.0.1:8080?destination=another",
        "http://127.0.0.1:8080#fragment",
    ],
)
def test_native_destination_stays_a_committed_loopback_origin(origin: str) -> None:
    with pytest.raises(ValidationError):
        NativeGenerationSettings(base_url=origin, request_timeout_ms=5000)


def test_native_response_retains_reasoning_usage_and_open_json_extensions() -> None:
    payload = {
        "object": "chat.completion",
        "model": "selected-native-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": " Exact answer.\n",
                    "reasoning_content": "Separate reasoning.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 12},
        "future_native_field": {"values": [0.2, None, False]},
    }
    result = NativeCompletion.model_validate_json(json.dumps(payload))
    assert result.model_dump(mode="json") == payload
    assert result.choices[0].message.reasoning_content == "Separate reasoning."


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_nonfinite_native_response_extensions_are_refused_at_every_json_depth(
    number: float,
) -> None:
    for value in (number, {"values": [{"score": number}]}):
        for payload in (
            {
                "object": "chat.completion",
                "model": "native",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": value,
            },
            {
                "error": {"code": 503, "type": "server_error", "message": "PrivateErrorCanary"},
                "native_detail": value,
            },
        ):
            with pytest.raises(ValidationError, match="finite"):
                NativeReply.model_validate_json(json.dumps(payload))


def test_native_process_owner_and_log_need_no_evaluator_configuration(tmp_path: Path) -> None:
    _, prepared, selected, _ = native_generation_case(tmp_path)
    for name in (
        "summary-evals/api.json",
        "summary-evals/hhem-evaluator/settings.json",
        "summary-evals/unieval-evaluator/settings.json",
    ):
        (tmp_path / "config" / name).unlink()
    path = tmp_path / "config" / "summary-evals" / "workflow.json"
    settings = json.loads(path.read_bytes())
    settings["native_log_directory"] = "backend/var/independent-native-logs"
    path.write_text(json.dumps(settings), encoding="utf-8")
    pipeline = load_pipeline_settings(tmp_path)
    native = OwnedLlama(tmp_path, prepared, selected, pipeline)
    try:
        assert native.process is None and native.loaded is None
        outcome = native.outcome()
        assert outcome.startup == outcome.shutdown == "not_started"
        assert outcome.startup_ms is None and outcome.exit_code is None
        assert (tmp_path / pipeline.native_log_directory / native.log.filename).is_file()
    finally:
        native.close()


@pytest.mark.parametrize("overflow", [0, 1])
def test_native_request_limit_is_exact_and_checked_before_transport(
    tmp_path: Path, overflow: int
) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        markers = chat_markers(selected)
        pipeline = load_pipeline_settings(REPOSITORY)
        body = json.dumps(
            request_payload(
                model_id=selected.entry.id,
                system=pipeline.generation_instruction,
                user=inputs.source_text,
                output_schema=GeneratedAnswer.model_json_schema(),
                sampling=selected.entry.sampling,
                markers=markers,
            ),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        pipeline = pipeline.model_copy(
            update={"max_generation_request_bytes": len(body) - overflow}
        )
        recorded = RecordedLlama()
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            call = generate_summary(client, inputs, prepared, selected, loaded, markers, pipeline)
            if overflow:
                with pytest.raises(WorkflowError) as failure:
                    await call
                assert failure.value.error.code == "INPUT_TOO_LARGE"
                assert recorded.requests == []
            else:
                assert (await call).status == "complete"
                assert recorded.requests[0][1] == body

    asyncio.run(check())


@pytest.mark.parametrize("overflow", [0, 1])
@pytest.mark.parametrize("streamed", [False, True])
def test_native_response_limit_is_exact_instead_of_borrowing_the_evaluator_limit(
    tmp_path: Path, overflow: int, streamed: bool
) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        recorded = RecordedLlama()
        response = json.loads(recorded.body)
        response["choices"][0]["message"]["content"] = json.dumps(
            {"title": "Title.", "summary": "Exact summary \u00e9."}, ensure_ascii=False
        )
        recorded.body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        recorded.stream_body = streamed
        pipeline = load_pipeline_settings(REPOSITORY).model_copy(
            update={"max_generation_response_bytes": len(recorded.body) - overflow}
        )
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            call = generate_summary(
                client, inputs, prepared, selected, loaded, chat_markers(selected), pipeline
            )
            if overflow:
                with pytest.raises(WorkflowError) as failure:
                    await call
                assert failure.value.error.code == "RESPONSE_TOO_LARGE"
            else:
                assert (await call).status == "complete"

    asyncio.run(check())


@pytest.mark.parametrize(
    "damage",
    ["redirect", "encoding", "length", "utf8", "native_error", "malformed", "choices", "nonfinite"],
)
def test_direct_native_transport_refuses_unsafe_or_invalid_responses_without_echoing_bodies(
    tmp_path: Path, damage: str
) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        recorded = RecordedLlama()
        if damage == "redirect":
            recorded.status = 307
        elif damage == "encoding":
            recorded.response_headers["Content-Encoding"] = "gzip"
        elif damage == "length":
            recorded.response_headers["Content-Length"] = "1.5"
        elif damage == "utf8":
            recorded.body = b'{"model":"\xff"}'
        elif damage == "native_error":
            recorded.status = 503
            recorded.body = (
                b'{"error":{"code":503,"message":"PrivateNativeErrorCanary","type":"api_error"}}'
            )
        elif damage == "malformed":
            recorded.body = b"PrivateInvalidJsonCanary"
        elif damage == "choices":
            recorded.body = b'{"object":"chat.completion","model":"native","choices":[]}'
        else:
            payload = json.loads(recorded.body)
            payload["usage"]["total_tokens"] = math.nan
            recorded.body = json.dumps(payload).encode()
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            with pytest.raises(WorkflowError) as failure:
                await generate_summary(
                    client,
                    inputs,
                    prepared,
                    selected,
                    loaded,
                    chat_markers(selected),
                    load_pipeline_settings(REPOSITORY),
                )
            assert failure.value.error.code == (
                "HTTP_FAILED"
                if damage == "redirect"
                else "GENERATION_FAILED"
                if damage == "native_error"
                else "RESPONSE_INVALID"
            )
            assert "PrivateNativeErrorCanary" not in str(failure.value)
            assert "PrivateInvalidJsonCanary" not in str(failure.value)
            assert len(recorded.requests) == 1

    asyncio.run(check())


@pytest.mark.parametrize("cancel", [False, True])
def test_stalled_native_request_is_cancelled_at_the_boundary(tmp_path: Path, cancel: bool) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        selected = replace(
            selected, native=selected.native.model_copy(update={"request_timeout_ms": 100})
        )
        pipeline = load_pipeline_settings(REPOSITORY).model_copy(
            update={"http_connect_timeout_ms": 10}
        )
        recorded = RecordedLlama()
        recorded.hold_generation = True
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            task = asyncio.create_task(
                generate_summary(
                    client, inputs, prepared, selected, loaded, chat_markers(selected), pipeline
                )
            )
            try:
                await asyncio.wait_for(recorded.started.wait(), 1)
                if cancel:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    with pytest.raises(WorkflowError) as failure:
                        await task
                    assert failure.value.error.code == "HTTP_FAILED"
                assert recorded.cancelled.is_set()
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(check())


def test_repeated_generation_calls_are_fresh_and_keep_native_sampling_open(tmp_path: Path) -> None:
    async def check() -> None:
        inputs, prepared, selected, loaded = native_generation_case(tmp_path)
        path = tmp_path / "config" / selected.identity.models_file
        declaration = json.loads(path.read_bytes())
        declaration["summarizer"]["sampling"]["typical_p"] = 0.95
        path.write_text(json.dumps(declaration), encoding="utf-8")
        selected = select_model(tmp_path, selected.identity.models_file)
        prepared = prepared.model_copy(update={"selected": selected.identity})
        recorded = RecordedLlama()
        async with httpx.AsyncClient(
            transport=recorded.transport, trust_env=False, follow_redirects=False
        ) as client:
            for _ in range(2):
                result = await generate_summary(
                    client,
                    inputs,
                    prepared,
                    selected,
                    loaded,
                    chat_markers(selected),
                    load_pipeline_settings(REPOSITORY),
                )
                assert result.status == "complete"
        assert len(recorded.requests) == 2
        assert recorded.requests[0][1] == recorded.requests[1][1]
        body = json.loads(recorded.requests[0][1])
        assert body["typical_p"] == declaration["summarizer"]["sampling"]["typical_p"]
        assert [message["role"] for message in body["messages"]] == ["system", "user"]
        assert inputs.reference_summary_text is not None
        assert inputs.reference_summary_text not in recorded.requests[0][1].decode("utf-8")

    asyncio.run(check())
