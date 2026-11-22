"""Build and read the digest model's one summary-and-chart call."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from string import Template
from typing import Annotated, Any, Final, NamedTuple

from pydantic import BaseModel, Field

from idhazh import summarize
from idhazh.classify.chart_reply import ChartProposal
from idhazh.classify.plan_visual_request import chart_capabilities
from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import Article
from idhazh.contracts.base import Model as ContractModel
from idhazh.contracts.base import canonical_json
from idhazh.contracts.element import Element
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.elements import SpanDriftError
from idhazh.llm.server import Completion, TurnMarkers, completion_payload, render_prompt
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import sanitize, untrusted_block

LOG = logging.getLogger(__name__)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
#: The literal Markdown emphasis delimiter, shared by the prompt and its rendering.
_QUANTITY_MARK: Final = "**"


# Decode the summary first so it is complete even if the visual reply gets cut.
class SummarizeAndPlanDraft(ContractModel):
    summary: summarize.SummaryDraft
    visual: Annotated[ChartProposal, Field(discriminator="type")] | None


def summarize_and_plan_model(*, plan: bool = True) -> type[BaseModel]:
    """A summary-only reply has no chart field."""
    return SummarizeAndPlanDraft if plan else summarize.SummaryDraft


def _inline_refs(node: Any, definitions: Mapping[str, Any]) -> Any:
    """The chart grammar has no recursive references; expand just the selected branches."""
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline_refs(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
        return {key: _inline_refs(value, definitions) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline_refs(value, definitions) for value in node]
    return node


def summarize_and_plan_schema(
    *,
    plan: bool = True,
    visuals: VisualsConfig | None = None,
    forms: tuple[VisualType, ...] | None = None,
) -> dict[str, Any]:
    """Constrain row shapes by the enabled form, never by an article's vocabulary."""
    if not plan:
        return summarize_and_plan_model(plan=False).model_json_schema()
    offered = chart_capabilities(visuals or VisualsConfig()) if forms is None else forms
    if not offered:
        return summarize_and_plan_model(plan=False).model_json_schema()
    schema = summarize_and_plan_model().model_json_schema()
    definitions = schema.pop("$defs")
    tagged = schema["properties"]["visual"]["anyOf"][0]
    names = tagged["discriminator"]["mapping"]
    branches: list[dict[str, Any]] = [{"type": "null"}]
    for form in offered:
        shape = _inline_refs({"$ref": names[form.value]}, definitions)
        fields = shape["properties"]
        fields.pop("type")
        shape["properties"] = {"type": {"const": form.value}, **fields}
        shape["required"] = ["type", *(name for name in shape["required"] if name != "type")]
        branches.append(shape)
    schema["properties"]["visual"] = {"anyOf": branches}
    schema["properties"]["summary"] = _inline_refs(schema["properties"]["summary"], definitions)
    return schema


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
        quantity_mark=_QUANTITY_MARK,
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


def chart_highlight_bytes(quantities: Sequence[Element]) -> int:
    """Budget for the two ASCII marks around each quantity."""
    return len(quantities) * 2 * len(_QUANTITY_MARK)


def _highlight_quantities(article: Article, quantities: Sequence[Element]) -> str:
    text = article.text or ""
    if not quantities:
        return text
    # Do not split a sequence the sanitizer would otherwise remove, or use
    # offsets against text that sanitization has moved.
    if sanitize(text) != text:
        LOG.warning("chart highlights omitted: article needs sanitizing id=%s", article.item_id)
        return text
    parts: list[str] = []
    cursor = 0
    for quantity in quantities:
        start, end = quantity.span_start, quantity.span_end
        excerpt = text[start:end]
        if start < cursor or end > len(text) or excerpt != quantity.span_excerpt:
            raise SpanDriftError(f"{article.item_id}: invalid quantity span for chart highlights")
        parts.extend((text[cursor:start], _QUANTITY_MARK, excerpt, _QUANTITY_MARK))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def build_summary_request(
    article: Article,
    forms: tuple[VisualType, ...],
    *,
    model_id: str,
    server: Mapping[str, Any],
    sampling: Mapping[str, Any],
    markers: TurnMarkers,
    chart_quantities: Sequence[Element] = (),
    prompt_config: SummarizeConfig | None = None,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """Use the declared model budget and the reply shape for this specific item."""
    text = _highlight_quantities(article, chart_quantities) if forms else article.text or ""
    return completion_payload(
        model_id=model_id,
        system=summary_system_prompt(
            prompt_config, forms=forms, prompt_files=prompt_files, config_dir=config_dir
        ),
        user=summary_user_turn(article.title or "(untitled)", text),
        output_schema=summarize_and_plan_schema(forms=forms),
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
                user=summary_user_turn("", ""),
                markers=markers,
            )
            for variant in (((), forms) if forms else ((),))
        ]
    )


def output_schema_text(visuals: VisualsConfig) -> str:
    """Fingerprint the two declared reply variants."""
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
