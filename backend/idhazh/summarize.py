"""Turn one article payload into one summary payload, deterministically.

Three things here are controls rather than preferences, and each one is the
reason a specific failure cannot happen:

- The article text goes in the user turn, fenced and labelled, and never in the
  system prompt. An instruction inside it is data about a web page.
- The response shape is enforced by the decoder, so an injection can change the
  words and cannot change the shape.
- The empty `<think>` block is asserted rather than assumed. A flag that
  silently stopped taking effect would otherwise cost faithfulness for months
  before anyone noticed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from idhazh.contracts.app_config import EvaluationConfig, InferenceConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json, derive_output_digest
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import untrusted_block

PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "summarize.txt"

_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class SummaryDraft(BaseModel):
    """What the decoder is constrained to emit, and what we agree to believe.

    Closed to unknown keys, so a planted tool call fails here rather than
    reaching a payload - the shape is the control, not the prompt.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=200, max_length=1600)
    key_points: list[str] = Field(min_length=2, max_length=5)


def output_schema() -> dict[str, Any]:
    """Generated from the model, never hand-written (Holy Law #3)."""
    return SummaryDraft.model_json_schema()


def output_schema_text() -> str:
    """One serialization, so the fingerprint's schema digest is stable."""
    return canonical_json(output_schema())


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def user_turn(article: Article) -> str:
    """The article, fenced and labelled as data.

    `untrusted_block` sanitizes what it fences rather than trusting an earlier
    caller, so this cannot hand a model a block it can close.
    """
    parts = []
    if article.title:
        parts.append(f"Title: {article.title}")
    parts.append(untrusted_block(article.text or ""))
    return "\n\n".join(parts)


def fits_context(article: Article, inference: InferenceConfig) -> bool:
    """Prompt plus reply has to fit, or the reply is silently cut off mid-sentence."""
    overhead = len(system_prompt().split()) * 2
    return article.token_count + inference.max_output_tokens + overhead <= inference.n_ctx


def build_request(article: Article, *, model_id: str, inference: InferenceConfig) -> dict[str, Any]:
    return request_payload(
        model_id=model_id,
        system=system_prompt(),
        user=user_turn(article),
        output_schema=output_schema(),
        inference=inference,
    )


def split_thinking(raw: str) -> tuple[str, str | None]:
    """Return the content with any think block removed, plus what was inside it."""
    match = _THINK.search(raw)
    if not match:
        return raw.strip(), None
    return _THINK.sub("", raw).strip(), match.group(1)


def parse_draft(raw: str) -> SummaryDraft:
    """Believe the response only after it has proved its shape.

    A thinking block with content in it is a failure, not a curiosity: the flag
    that was supposed to disable reasoning did not take, and reasoning
    measurably costs faithfulness when summarizing.
    """
    content, thought = split_thinking(raw)
    if thought is not None and thought.strip():
        raise ValueError("thinking was disabled and the model reasoned anyway")
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    return SummaryDraft.model_validate_json(content)


def _failed(article: Article, *, model_id: str, detail: str, generated_at: str) -> Summary:
    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        pipeline_fingerprint="0" * 64,
        output_digest=derive_output_digest(None, []),
        model_id=model_id,
        source_truncated=article.truncated,
        generated_at=generated_at,
        status=SummaryStatus.FAILED,
        failure_detail=detail[:500],
    )


def to_summary(
    article: Article,
    completion: Completion,
    *,
    model_id: str,
    pipeline_fingerprint: str,
    generated_at: str,
    evaluation: EvaluationConfig | None = None,
    duration_ms: int = 0,
    attempt: int = 1,
) -> Summary:
    """One article plus one completion becomes exactly one payload, valid or failed."""
    bounds = evaluation or EvaluationConfig()
    if article.status is not ArticleStatus.OK:
        return _failed(
            article,
            model_id=model_id,
            detail="the article did not extract, so there was nothing to summarize",
            generated_at=generated_at,
        )
    if completion.hit_the_budget:
        return _failed(
            article,
            model_id=model_id,
            detail="the reply was cut off by the output budget, so it never closed its JSON",
            generated_at=generated_at,
        )
    try:
        draft = parse_draft(completion.content)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        return _failed(
            article,
            model_id=model_id,
            detail=f"the reply did not hold its shape: {type(error).__name__}",
            generated_at=generated_at,
        )

    words = len(draft.summary.split())
    if not bounds.summary_words_min <= words <= bounds.summary_words_max:
        return _failed(
            article,
            model_id=model_id,
            detail=f"summary is {words} words, outside the publishable range",
            generated_at=generated_at,
        )

    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        summary=draft.summary,
        key_points=draft.key_points,
        pipeline_fingerprint=pipeline_fingerprint,
        output_digest=derive_output_digest(draft.summary, draft.key_points),
        model_id=model_id,
        attempt=attempt,
        source_truncated=article.truncated,
        input_tokens=completion.prompt_tokens,
        output_tokens=completion.completion_tokens,
        duration_ms=duration_ms,
        generated_at=generated_at,
        status=SummaryStatus.OK,
    )
