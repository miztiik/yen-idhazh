"""Build and read the digest model's one summary-and-chart call."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from string import Template
from typing import Annotated, Any, NamedTuple

from pydantic import BaseModel, Field, ValidationError, ValidatorFunctionWrapHandler, WrapValidator

from idhazh import summarize
from idhazh.classify.chart_candidates import (
    ChartCandidate,
    candidate_block,
    evidence_forms,
    time_candidates,
)
from idhazh.classify.chart_reply import ChartProposal
from idhazh.classify.plan_visual_request import chart_capabilities
from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import Article
from idhazh.contracts.base import Model as ContractModel
from idhazh.contracts.base import canonical_json
from idhazh.contracts.element import ElementKind
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.contracts.visual_decision import MODEL_REASON_MAX_WORDS, ModelReason
from idhazh.llm.server import Completion, TurnMarkers, completion_payload, render_prompt
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import BLOB_PLACEHOLDER, LINK_PLACEHOLDER, sanitize, untrusted_block

_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_JSON_SPACE = " \t\r\n"
_SUMMARY_FIRST = re.compile(r'\{[ \t\r\n]*"summary"[ \t\r\n]*:[ \t\r\n]*')
_VISUAL_NEXT = re.compile(r'[ \t\r\n]*,[ \t\r\n]*"visual"[ \t\r\n]*:[ \t\r\n]*')


def _read_model_reason(value: object, check: ValidatorFunctionWrapHandler) -> str | None:
    """Refuse this optional field, never the summary or chart beside it."""
    try:
        reason = check(value)
    except ValidationError:
        return None
    if not isinstance(reason, str) or (
        LINK_PLACEHOLDER in reason
        or BLOB_PLACEHOLDER in reason
        or sanitize(reason) != " ".join(reason.split())
    ):
        return None
    return reason


# Finish the summary and visual before spending any budget on the optional reason.
class SummarizeAndPlanDraft(ContractModel):
    summary: summarize.SummaryDraft
    visual: Annotated[ChartProposal, Field(discriminator="type")] | None
    model_reason: Annotated[ModelReason | None, WrapValidator(_read_model_reason)] = None


def summarize_and_plan_model(*, plan: bool = True) -> type[BaseModel]:
    """A summary-only reply has no chart field."""
    return SummarizeAndPlanDraft if plan else summarize.SummaryDraft


def _inline_refs(node: Any, definitions: Mapping[str, Any], *, share_reading: bool) -> Any:
    """Keep the bounded reading choices shared across the selected form branches."""
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if share_reading and name == "Reading":
                return node
            return _inline_refs(definitions[name], definitions, share_reading=share_reading)
        return {
            key: _inline_refs(value, definitions, share_reading=share_reading)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_inline_refs(value, definitions, share_reading=share_reading) for value in node]
    return node


def summarize_and_plan_schema(
    *,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    forms: tuple[VisualType, ...] | None = None,
    readings: Sequence[ChartCandidate] = (),
) -> dict[str, Any]:
    """Constrain occurrence IDs and roles, never put article strings in the grammar."""
    if not plan:
        return summarize_and_plan_model(plan=False).model_json_schema()
    offered = chart_capabilities(visuals or VisualsConfig()) if forms is None else forms
    if readings:
        offered = evidence_forms(offered, readings)
    if not offered:
        return summarize_and_plan_model(plan=False).model_json_schema()
    schema = summarize_and_plan_model().model_json_schema()
    definitions = schema.pop("$defs")
    tagged = schema["properties"]["visual"]["anyOf"][0]
    names = tagged["discriminator"]["mapping"]
    branches: list[dict[str, Any]] = [{"type": "null"}]
    quantities = [
        entry.evidence_id for entry in readings if entry.element.kind is ElementKind.QUANTITY
    ]
    dates = [entry.evidence_id for entry in time_candidates(readings)]
    for form in offered:
        shape = _inline_refs({"$ref": names[form.value]}, definitions, share_reading=bool(readings))
        fields = shape["properties"]
        fields.pop("type")
        if "axis_titles" in fields:
            axes = fields["axis_titles"]["anyOf"][0]
            axes["properties"].pop("size")
            fields["axis_titles"] = axes
            shape["required"].append("axis_titles")
        shape["properties"] = {"type": {"const": form.value}, **fields}
        shape["required"] = ["type", *(name for name in shape["required"] if name != "type")]
        if readings:
            _bind_date_ids(shape)
        if form is VisualType.HISTOGRAM:
            if readings:
                fields["rows"]["items"] = {"$ref": "#/$defs/AsStatedReading"}
            else:
                fields["rows"]["items"]["properties"]["interpretation"] = {"const": "as_stated"}
        branches.append(shape)
    schema["properties"]["visual"] = {"anyOf": branches}
    schema["properties"]["summary"] = _inline_refs(
        schema["properties"]["summary"], definitions, share_reading=False,
    )
    if readings:
        schema["$defs"] = {
            "QuantityEvidenceId": {"type": "string", "enum": quantities},
            "Reading": {
                "type": "object",
                "properties": {
                    "evidence_id": {"$ref": "#/$defs/QuantityEvidenceId"},
                    "interpretation": {
                        "enum": ["as_stated", "negative_magnitude"], "type": "string",
                    },
                },
                "required": ["evidence_id", "interpretation"],
                "additionalProperties": False,
            },
        }
        if len(dates) >= 2:
            schema["$defs"]["DateEvidenceId"] = {"type": "string", "enum": dates}
        if VisualType.HISTOGRAM in offered:
            schema["$defs"]["AsStatedReading"] = {
                **schema["$defs"]["Reading"],
                "properties": {
                    **schema["$defs"]["Reading"]["properties"],
                    "interpretation": {"const": "as_stated"},
                },
            }
    return schema


def _bind_date_ids(node: Any) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties":
                for name in ("date", "start_date", "end_date"):
                    if name in value:
                        value[name] = {"$ref": "#/$defs/DateEvidenceId"}
            _bind_date_ids(value)
    elif isinstance(node, list):
        for value in node:
            _bind_date_ids(value)


def chart_addendum(
    forms: tuple[VisualType, ...],
    *,
    prompt_files: PromptFilesConfig,
    config_dir: Path,
) -> str:
    """No chart instructions are read for a summary-only request."""
    if not forms:
        return ""
    return "\n" + Template(load_prompt_text(config_dir, prompt_files.plan_visual)).substitute(
        chart_types=", ".join(form.value for form in forms),
        model_reason_max_words=MODEL_REASON_MAX_WORDS,
    )


def summary_system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    forms: tuple[VisualType, ...] = (),
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """Keep summary and chart instructions fixed so items share a cached prefix."""
    ask = prompt_config or SummarizeConfig()
    files = prompt_files or PromptFilesConfig()
    return Template(load_prompt_text(config_dir, files.write_digest_summary)).substitute(
        max_verbatim_words=ask.max_verbatim_words,
    ) + chart_addendum(
        forms, prompt_files=files, config_dir=config_dir,
    )


def summary_user_turn(title: str, text: str) -> str:
    """Send just the sanitized title and article body in a single untrusted block."""
    return untrusted_block(f"Title:\n{title}\n\nThe item:\n{text}")


def build_summary_request(
    article: Article,
    forms: tuple[VisualType, ...],
    *,
    model_id: str,
    server: Mapping[str, Any],
    sampling: Mapping[str, Any],
    markers: TurnMarkers,
    candidates: Sequence[ChartCandidate] = (),
    prompt_config: SummarizeConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """Use the declared model budget and the reply shape for this specific item."""
    if forms and sum(entry.element.kind is ElementKind.QUANTITY for entry in candidates) < 2:
        raise ValueError("a chart request needs at least two supplied readings")
    forms = evidence_forms(forms, candidates)
    return completion_payload(
        model_id=model_id,
        system=summary_system_prompt(
            prompt_config, forms=forms, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn(article.title or "(untitled)", article.text or "") + (
            candidate_block(candidates) if forms else ""
        ),
        output_schema=summarize_and_plan_schema(
            forms=forms, readings=candidates,
        ),
        server=server,
        sampling=sampling,
        markers=markers,
    )


def prompt_inputs(
    prompt_config: SummarizeConfig | None = None,
    *,
    markers: TurnMarkers,
    visuals: VisualsConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """Fingerprint both prompt variants and their envelope without an article."""
    forms = chart_capabilities(visuals or VisualsConfig())
    return canonical_json(
        [
            render_prompt(
                system=summary_system_prompt(
                    prompt_config, forms=variant, prompt_files=prompt_files, config_dir=config_dir
                ),
                user=summary_user_turn("", "") + (candidate_block(()) if variant else ""),
                markers=markers,
            )
            for variant in (((), forms) if forms else ((),))
        ]
    )


def output_schema_text(visuals: VisualsConfig) -> str:
    """Fingerprint both reply variants, including the per-item reading shape."""
    schemas = [summarize_and_plan_schema(plan=False)]
    if chart_capabilities(visuals):
        schemas.append(summarize_and_plan_schema(visuals=visuals))
    return canonical_json(schemas)


def _reply_content(raw: str) -> str:
    content = raw.strip()
    if fenced := _FENCED_JSON.match(content):
        return fenced.group(1)
    return content


def parse_summarize_and_plan(raw: str) -> SummarizeAndPlanDraft:
    """Read the chart-bearing reply shape; the caller separately recovers the summary."""
    return SummarizeAndPlanDraft.model_validate_json(_reply_content(raw))


def _reason_tail_was_cut(tail: str, decoder: json.JSONDecoder) -> bool:
    """Recognize the final member, including a cut key, not an unknown member."""
    tail = tail.lstrip(_JSON_SPACE)
    if not tail.startswith(","):
        return False
    tail = tail[1:].lstrip(_JSON_SPACE)
    name = '"model_reason"'
    if name.startswith(tail):
        return True
    member, colon, tail = tail.partition(":")
    if not colon or member.rstrip(_JSON_SPACE) != name:
        return False
    value = tail.lstrip(_JSON_SPACE)
    if "null".startswith(value):
        return True
    if not value.startswith('"'):
        return False
    try:
        _, end = decoder.raw_decode(value)
    except json.JSONDecodeError:
        return True
    return not value[end:].strip(_JSON_SPACE)


def recover_visual_before_reason_cut(raw: str) -> SummarizeAndPlanDraft | None:
    """Read a length-stopped reply, repairing only a cut after its closed visual."""
    content = _reply_content(raw)
    if (first := _SUMMARY_FIRST.match(content)) is None:
        return None
    decoder = json.JSONDecoder()
    try:
        _, after_summary = decoder.raw_decode(content, first.end())
        if (next_member := _VISUAL_NEXT.match(content, after_summary)) is None:
            return None
        _, after_visual = decoder.raw_decode(content, next_member.end())
    except (ValueError, RecursionError):
        return None
    tail = content[after_visual:]
    if not tail.strip(_JSON_SPACE) or _reason_tail_was_cut(tail, decoder):
        content = content[:after_visual] + "}"
    try:
        return SummarizeAndPlanDraft.model_validate_json(content)
    except ValidationError:
        return None


def _summary_bounds(raw: str) -> tuple[str, int, int] | None:
    """The decoded summary object and its bounds within the completion."""
    content = _reply_content(raw)
    key = content.find('"summary"')
    if key < 0:
        return None
    colon = content.find(":", key + len('"summary"'))
    if colon < 0:
        return None
    start = colon + 1
    while start < len(content) and content[start].isspace():
        start += 1
    try:
        body, end = json.JSONDecoder().raw_decode(content, start)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    return json.dumps(body), start, end


def summary_object(raw: str) -> str | None:
    """Recover only a complete summary object, even if the following visual was cut."""
    found = _summary_bounds(raw)
    return None if found is None else found[0]


class DecodeSplit(NamedTuple):
    """The estimated split in a single decode, not separately timed calls."""

    summary_ms: int
    plan_ms: int
    summary_tokens: int
    plan_tokens: int
    is_estimate: bool = True


def split_the_decode(completion: Completion) -> DecodeSplit | None:
    """Apportion output tokens and decode time by the two halves' character counts."""
    found = _summary_bounds(completion.content)
    if found is None or completion.completion_tokens <= 0:
        return None
    _, start, end = found
    whole = len(completion.content.strip())
    summary_chars = max(end - start, 0)
    plan_chars = max(whole - end, 0)
    if summary_chars + plan_chars <= 0:
        return None
    plan_tokens = round(completion.completion_tokens * plan_chars / (summary_chars + plan_chars))
    summary_tokens = completion.completion_tokens - plan_tokens
    plan_ms = round(completion.decode_ms * plan_tokens / completion.completion_tokens)
    return DecodeSplit(
        summary_ms=completion.decode_ms - plan_ms,
        plan_ms=plan_ms,
        summary_tokens=summary_tokens,
        plan_tokens=plan_tokens,
    )


def recovered_completion(completion: Completion) -> Completion | None:
    """Pass the intact summary through the normal summary gates with its real token costs.

    A summary-only reply already has that shape. On a combined reply, a length
    stop after the summary is normalized to a completed summary, not a visual.
    """
    body = summary_object(completion.content)
    if body is None:
        return None
    if not completion.hit_the_budget:
        return replace(completion, content=body)
    return replace(completion, content=body, finish_reason="stop")
