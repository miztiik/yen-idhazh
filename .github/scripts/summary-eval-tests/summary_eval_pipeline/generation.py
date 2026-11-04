"""How is one final answer generated through FastAPI and bound to the same-run receipt?"""

import json

import httpx
from hhem_evaluator.contracts.llama_result import LlamaErrorResult, LlamaResult
from pydantic import BaseModel, ConfigDict, RootModel

from idhazh.llm.server import (
    PROBE_FOLLOW_UP,
    PROBE_REPLY,
    PROBE_SYSTEM,
    PROBE_USER,
    ProbeRefusedError,
    TurnMarkers,
    parse_completion,
    request_payload,
    template_kwargs,
    turn_markers_from_renderings,
)

from .contracts import (
    WORKFLOW_VERSION,
    GeneratedAnswer,
    GenerationReceipt,
    LoadedModel,
    PreparedRun,
    text_sha256,
)
from .failures import WorkflowError
from .http import call_local_api
from .inputs import ManualInputs
from .model_selection import SelectedModel
from .settings import PipelineSettings


class TemplateResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    prompt: str


class GenerationReply(RootModel[LlamaResult | LlamaErrorResult]):
    pass


async def read_turn_markers(
    client: httpx.AsyncClient,
    selected: SelectedModel,
    pipeline: PipelineSettings,
) -> TurnMarkers:
    entry = selected.entry
    two_turns = [
        {"role": "system", "content": PROBE_SYSTEM},
        {"role": "user", "content": PROBE_USER},
    ]

    async def render(messages: list[dict[str, str]], thinking: bool) -> str:
        body: dict[str, object] = {"messages": messages}
        kwargs = template_kwargs(
            entry.chat_template_kwargs, keyword=entry.thinking_kwarg, thinking=thinking
        )
        if kwargs:
            body["chat_template_kwargs"] = kwargs
        status, result = await call_local_api(
            client,
            "POST",
            selected.native.base_url + "/apply-template",
            TemplateResult,
            pipeline,
            pipeline.http_connect_timeout_ms,
            service="llama",
            phase="health",
            body=json.dumps(body).encode("utf-8"),
        )
        if status != 200:
            raise WorkflowError("HEALTH_FAILED", "health", "llama", status)
        return result.prompt

    plain = await render(two_turns, False)
    thinking = await render(two_turns, True) if entry.thinking_kwarg is not None else plain
    history = await render(
        [
            {"role": "user", "content": PROBE_USER},
            {"role": "assistant", "content": PROBE_REPLY},
            {"role": "user", "content": PROBE_FOLLOW_UP},
        ],
        False,
    )
    try:
        return turn_markers_from_renderings(
            model_id=entry.id,
            plain=plain,
            thinking=thinking,
            history=history,
            thinking_close=entry.thinking_close,
            thinking_kwarg=entry.thinking_kwarg,
            chat_template_kwargs=entry.chat_template_kwargs,
            reasoning_delimiters=entry.reasoning_delimiters,
        )
    except (ValueError, ProbeRefusedError):
        raise WorkflowError("MODEL_INVALID", "health", "llama") from None


async def generate_summary(
    client: httpx.AsyncClient,
    api_origin: str,
    inputs: ManualInputs,
    prepared: PreparedRun,
    selected: SelectedModel,
    loaded: LoadedModel,
    markers: TurnMarkers,
    pipeline: PipelineSettings,
    max_body_bytes: int,
) -> GenerationReceipt:
    if (
        selected.identity != prepared.selected
        or text_sha256(inputs.source_text) != prepared.source_sha256
        or loaded.sha256 != selected.identity.sha256
        or loaded.model_id != selected.identity.model_id
    ):
        raise WorkflowError("RECEIPT_INVALID", "generation")
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
    if len(body) > max_body_bytes:
        raise WorkflowError("INPUT_TOO_LARGE", "generation")
    status, reply = await call_local_api(
        client,
        "POST",
        api_origin + "/v1/chat/completions",
        GenerationReply,
        pipeline,
        selected.native.request_timeout_ms + pipeline.http_connect_timeout_ms,
        service="llama",
        phase="generation",
        body=body,
    )
    result = reply.root
    if status != 200 or not isinstance(result, LlamaResult):
        raise WorkflowError("GENERATION_FAILED", "generation", "llama", status)
    if len(result.choices) != 1 or result.choices[0].index != 0:
        raise WorkflowError("GENERATION_FAILED", "generation", "llama", status)
    if result.choices[0].finish_reason != "stop":
        raise WorkflowError("GENERATION_INCOMPLETE", "generation", "llama", status)
    if result.model != loaded.model_id:
        raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "generation", "llama", status)
    try:
        completion = parse_completion(
            result.model_dump_json(), reasoning_delimiters=selected.entry.reasoning_delimiters
        )
        answer = GeneratedAnswer.model_validate_json(completion.content)
    except (ValueError, KeyError, TypeError):
        raise WorkflowError("GENERATION_FAILED", "generation", "llama", status) from None
    return GenerationReceipt(
        version=WORKFLOW_VERSION,
        run=prepared.run,
        selected=prepared.selected,
        loaded=loaded,
        source_sha256=prepared.source_sha256,
        summary_sha256=text_sha256(answer.summary),
        summary_text=answer.summary,
        status="complete",
        errors=(),
    )
