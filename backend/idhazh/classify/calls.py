"""Build and read the digest model's one summary-and-chart call."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from string import Template
from typing import Any, NamedTuple

from pydantic import BaseModel

from idhazh import summarize
from idhazh.classify.plan_visual_request import VisualInput, chart_capabilities, example_data
from idhazh.classify.resolve_visual_choice import (
    COMPARISONS,
    NO_CHART,
    ChartReferences,
    ComparisonPoint,
    PlanChoice,
)
from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import Article
from idhazh.contracts.base import Model as ContractModel
from idhazh.contracts.base import canonical_json
from idhazh.contracts.element import ElementKind
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.llm.server import Completion, TurnMarkers, completion_payload, render_prompt
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import untrusted_block
from idhazh.visual_vocabulary import TYPE_RULES, VALUE_ROLES

_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


# Decode the summary first so it is complete even if the visual reply gets cut.
class SummarizeAndPlanDraft(ContractModel):
    summary: summarize.SummaryDraft
    visual: PlanChoice


def summarize_and_plan_model(*, plan: bool = True) -> type[BaseModel]:
    """Without data references, the grammar leaves no place for a chart answer."""
    return SummarizeAndPlanDraft if plan else summarize.SummaryDraft


def _words_only(schema: dict[str, Any]) -> dict[str, Any]:
    # The native decoder uses the pattern instead of maxLength. Bound the
    # repeat and keep it within one JSON string, excluding digits and escapes.
    length = schema["maxLength"]
    return {"type": "string", "pattern": rf'^[^"\\\r\n<>0-9]{{1,{length}}}$'}


def _chart_reply_schema(
    form: VisualType | None,
    answer: dict[str, Any],
    roles: dict[str, Any],
) -> dict[str, Any]:
    null = {"type": "null"}
    fields = answer["properties"] | {"why": _words_only(answer["properties"]["why"])}
    fields["type"] = {"const": form.value if form is not None else NO_CHART}
    required: list[str] = answer["required"].copy()
    composition = form in {VisualType.PIE, VisualType.STACKED_BAR}
    if form is not None:
        rules = TYPE_RULES[form]
        # A stacked row is labelled by its whole, which the resolver puts in
        # the category role; the model cites it only once.
        needed = rules.required - ({EncodingRole.CATEGORY} if form is VisualType.STACKED_BAR
                                   else set())
        allowed = {role.value for role in needed | rules.optional}
        required_roles = [key for key in roles if key in {role.value for role in needed}]
        if form in COMPARISONS:
            allowed.difference_update({"category", "quantity"})
            allowed.add("points")
            required_roles = ["points"]
        fields["encodings"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {key: value for key, value in roles.items() if key in allowed},
            "required": required_roles,
        }
        fields["focus"] = fields["focus"]["anyOf"][0]
        fields["title"] = fields["title"]["anyOf"][0]
    else:
        fields["encodings"] = {"type": "object", "properties": {}, "additionalProperties": False}
        fields["focus"] = fields["title"] = fields["caption"] = null
    fields["whole"] = fields["whole"]["anyOf"][0] if composition else null
    if form is VisualType.STACKED_BAR:
        fields["measure"] = fields["measure"]["anyOf"][0]
        required.append("measure")
    else:
        del fields["measure"]
    return answer | {"properties": fields, "required": required}


def summarize_and_plan_schema(
    *,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    data: VisualInput | None = None,
) -> dict[str, Any]:
    """Keep all capabilities selectable and constrain the roles after type is chosen."""
    schema = summarize_and_plan_model(plan=plan).model_json_schema()
    if not plan:
        return schema
    definitions = schema["$defs"]
    answer = definitions[PlanChoice.__name__]
    answer_fields = answer["properties"]
    roles = definitions.pop(ChartReferences.__name__)["properties"]
    roles["points"]["minItems"] = 2
    forms = data.forms if data is not None else chart_capabilities(visuals or VisualsConfig())
    if data is not None:
        quantities = [code for code, e in data.refs.items() if e.kind is ElementKind.QUANTITY]
        dates = [code for code, e in data.refs.items() if e.kind is ElementKind.DATE]
        quantity = {"type": "string", "enum": quantities}
        for role in VALUE_ROLES:
            roles[role.value]["items"] = quantity
        point = definitions[ComparisonPoint.__name__]
        groups: dict[tuple[str, ...], list[str]] = {}
        for code, labels in data.labels.items():
            groups.setdefault(tuple(labels), []).append(code)
        if groups:
            definitions[ComparisonPoint.__name__] = {"anyOf": [
                point | {"properties": {
                    "quantity": {"type": "string", "enum": readings},
                    "category": {"type": "string", "enum": list(labels)},
                }}
                for labels, readings in groups.items()
            ]}
        else:
            roles["points"].update(minItems=0, maxItems=0)
        if dates:
            roles["time"]["items"] = {"type": "string", "enum": dates}
        else:
            roles["time"]["maxItems"] = 0
        for field in ("focus", "whole"):
            answer_fields[field]["anyOf"] = [quantity, {"type": "null"}]
    definitions[PlanChoice.__name__] = {
        "anyOf": [_chart_reply_schema(form, answer, roles) for form in (None, *forms)]
    }
    return schema


def summary_system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """Keep summary and chart instructions fixed so items share a cached prefix."""
    ask = prompt_config or SummarizeConfig()
    files = prompt_files or PromptFilesConfig()
    return "\n".join(
        (
            Template(load_prompt_text(config_dir, files.write_digest_summary)).substitute(
                max_verbatim_words=ask.max_verbatim_words,
            ),
            Template(load_prompt_text(config_dir, files.plan_visual)).substitute(),
        )
    )


def summary_user_turn(
    title: str,
    text: str,
    *,
    data: VisualInput | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """Fence both source fields and keep the data behind, not inside, instructions."""
    shape = summarize_and_plan_model(plan=data is not None)
    files = prompt_files or PromptFilesConfig()
    question = Template(load_prompt_text(config_dir, files.continue_summary)).substitute(
        write="Write " + ", then ".join(f'"{name}"' for name in shape.model_fields) + ".",
    )
    return (
        "Title:\n" + untrusted_block(title)
        + "\n\nThe item:\n" + untrusted_block(text) + "\n\n"
        + (data.prompt + "\n\n" if data is not None else "")
        + question
    )


def build_summary_request(
    article: Article,
    data: VisualInput | None,
    *,
    model_id: str,
    server: Mapping[str, Any],
    sampling: Mapping[str, Any],
    markers: TurnMarkers,
    prompt_config: SummarizeConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """Use the declared model budget and the reply shape for this specific item."""
    return completion_payload(
        model_id=model_id,
        system=summary_system_prompt(
            prompt_config, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn(
            article.title or "(untitled)", article.text or "",
            data=data, prompt_files=prompt_files, config_dir=config_dir,
        ),
        output_schema=summarize_and_plan_schema(plan=data is not None, data=data),
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
    shown = visuals or VisualsConfig()
    data = VisualInput(chart_capabilities(shown), {}, example_data(shown))
    system = summary_system_prompt(prompt_config, prompt_files=prompt_files, config_dir=config_dir)
    return canonical_json(
        [
            render_prompt(
                system=system,
                user=summary_user_turn(
                    "", "", data=variant, prompt_files=prompt_files, config_dir=config_dir
                ),
                markers=markers,
            )
            for variant in (None, data) if variant is None or variant.forms
        ]
    )


def output_schema_text(visuals: VisualsConfig) -> str:
    """Fingerprint the reply variants before article-specific code binding."""
    schemas = [summarize_and_plan_schema(plan=False)]
    if chart_capabilities(visuals):
        schemas.append(summarize_and_plan_schema(visuals=visuals))
    return canonical_json(schemas)


def parse_summarize_and_plan(raw: str) -> SummarizeAndPlanDraft:
    """Read the chart-bearing reply shape; the caller separately recovers the summary."""
    content = raw.strip()
    if fenced := _FENCED_JSON.match(content):
        content = fenced.group(1)
    return SummarizeAndPlanDraft.model_validate_json(content)


def _summary_bounds(raw: str) -> tuple[str, int, int] | None:
    """The decoded summary object and its bounds within the completion."""
    content = raw.strip()
    if fenced := _FENCED_JSON.match(content):
        content = fenced.group(1)
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
