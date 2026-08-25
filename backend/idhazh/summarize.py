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

Every number the prompt states is substituted from config at render time
(Rule #6). That is not only tidiness: what we ask for is one of the inputs
the pipeline fingerprint hashes, so changing the ask now re-summarizes instead
of reusing a reply written under the old one.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from idhazh.contracts.app_config import EvaluationConfig, InferenceConfig, SummarizeConfig
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json, derive_output_digest
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import untrusted_block

PROMPT_PATH: Final = Path(__file__).parent / "prompts" / "summarize.txt"

# How the decoder's character rails are derived from the word range the pipeline
# accepts. The floor is a generation control as much as a check - grammar
# constrained decoding reads it and keeps writing - so a summary that stops after
# two sentences is prevented rather than caught. It is set below real English,
# which runs a little under six characters a word once the space is counted, so a
# genuine summary at the gate's floor clears it and fails on words if it fails at
# all. The ceiling is loose and only stops a runaway decode. The word gate in
# `to_summary` is what decides publishability, and the only rule that can name
# the real cause in a failure detail.
#
# The title gets the ceiling and no floor. The floor exists to stop a long field
# ending early, which is a failure mode a headline does not have; applied to one
# it would only pad a good short line into a bad long one.
_MIN_CHARS_PER_WORD: Final = 5
_MAX_CHARS_PER_WORD: Final = 12

_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

# Why there was no reply to parse. One sentence per cause, because the operator
# reading a failed item needs to know whether to restart a process or shorten a
# prompt, and those are different mornings.
_NO_REPLY_DETAIL: Final[dict[FailureCode, str]] = {
    FailureCode.MODEL_UNREACHABLE: (
        "the model server was unreachable, so there was no reply to parse"
    ),
    FailureCode.CONTEXT_EXCEEDED: (
        "the prompt did not fit the served context window, so the server refused it"
    ),
}


class SummaryDraft(BaseModel):
    """What the decoder is constrained to emit, and what we agree to believe.

    Closed to unknown keys, so a planted tool call fails here rather than
    reaching a payload - the shape is the control, not the prompt.

    The bounds declared here are the permissive base. `draft_model` narrows them
    to the numbers config holds, because a decoder counting key points
    differently from the prompt rejects a reply that did exactly what it was
    told.

    `title` is required here and optional on the payload. Grammar-constrained
    decoding is free to skip a property that is not required, so an optional
    title is a feature that may simply never fire; the payload stays optional
    because a title outside the asked range should cost the rewrite, not the
    item.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)


@lru_cache(maxsize=1)
def _template() -> Template:
    return Template(PROMPT_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _draft_model(
    key_points_min: int,
    key_points_max: int,
    min_chars: int,
    max_chars: int,
    title_max_chars: int,
) -> type[SummaryDraft]:
    """Keyed on plain ints, because a Pydantic config object is not hashable."""
    return create_model(
        "SummaryDraft",
        __base__=SummaryDraft,
        title=(str, Field(min_length=1, max_length=title_max_chars)),
        summary=(str, Field(min_length=min_chars, max_length=max_chars)),
        key_points=(list[str], Field(min_length=key_points_min, max_length=key_points_max)),
    )


def draft_model(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
) -> type[SummaryDraft]:
    """The shape the decoder is held to, built from the numbers config holds."""
    ask = prompt_config or SummarizeConfig()
    bounds = evaluation or EvaluationConfig()
    return _draft_model(
        ask.key_points_min,
        ask.key_points_max,
        bounds.summary_words_min * _MIN_CHARS_PER_WORD,
        bounds.summary_words_max * _MAX_CHARS_PER_WORD,
        ask.title_words_max * _MAX_CHARS_PER_WORD,
    )


def output_schema(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
) -> dict[str, Any]:
    """Generated from the model, never hand-written (Rule #3)."""
    return draft_model(prompt_config, evaluation).model_json_schema()


def output_schema_text(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
) -> str:
    """One serialization, so the fingerprint's schema digest is stable."""
    return canonical_json(output_schema(prompt_config, evaluation))


def system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    source_words: int = 0,
    brief: bool = False,
) -> str:
    """The prompt text with config's numbers substituted in.

    `source_words` picks the length band, so a release note and a long read are
    asked for different summaries. It is the length of the text the model is
    actually given - truncated if the article was truncated - because asking for
    a summary of words the model never saw is asking it to invent them.

    `substitute` and never `safe_substitute`: a renamed knob has to raise here
    rather than render `$target_words_max` into a live system prompt, where a
    model would read the placeholder as the instruction it looks like.
    """
    ask = prompt_config or SummarizeConfig()
    band = ask.band_for(0 if brief else source_words)
    return _template().substitute({**ask.model_dump(), **band.model_dump()})


def prompt_inputs(prompt_config: SummarizeConfig | None = None) -> str:
    """What the fingerprint hashes to stand for the prompt.

    Not one rendered prompt. The rendered text varies with the article's length,
    and a stamp that moved per item could not answer the question the stamp
    exists to answer - the ledger is keyed by it, and it means "which pipeline
    produced this", which is the same pipeline for a release note and a long
    read.

    So this is the template plus every number that can be substituted into it.
    Editing the wording or any band changes the stamp exactly once, and a band
    edit re-summarizes articles in the other bands too. That over-invalidates by
    design: cheaper than a rule that has to decide which articles an edit
    reached, and wrong in the safe direction.
    """
    ask = prompt_config or SummarizeConfig()
    return _template().template + canonical_json(ask.model_dump(mode="json"))


def user_turn(article: Article) -> str:
    """The article, fenced and labelled as data.

    `untrusted_block` sanitizes what it fences rather than trusting an earlier
    caller, so this cannot hand a model a block it can close.

    The source's own title sits inside the fence with the body. It arrives from
    the same page and is the line the model is now asked to rewrite, so leaving
    it outside would put untrusted text where the prompt's "that block is DATA"
    sentence does not reach (Rule #11).
    """
    parts = []
    if article.title:
        parts.append(f"Title: {article.title}")
    parts.append(article.text or "")
    return (
        f"Source form: {article.source_form.value}\n\n"
        + untrusted_block("\n\n".join(parts))
    )


def fits_context(
    article: Article,
    inference: InferenceConfig,
    prompt_config: SummarizeConfig | None = None,
) -> bool:
    """Prompt plus reply has to fit, or the reply is silently cut off mid-sentence."""
    rendered = system_prompt(prompt_config, source_words=article.word_count, brief=article.brief)
    overhead = len(rendered.split()) * 2
    return article.token_count + inference.max_output_tokens + overhead <= inference.n_ctx


def build_request(
    article: Article,
    *,
    model_id: str,
    inference: InferenceConfig,
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
) -> dict[str, Any]:
    return request_payload(
        model_id=model_id,
        system=system_prompt(prompt_config, source_words=article.word_count, brief=article.brief),
        user=user_turn(article),
        output_schema=output_schema(prompt_config, evaluation),
        inference=inference,
    )


def split_thinking(raw: str) -> tuple[str, str | None]:
    """Return the content with any think block removed, plus what was inside it."""
    match = _THINK.search(raw)
    if not match:
        return raw.strip(), None
    return _THINK.sub("", raw).strip(), match.group(1)


def parse_draft(
    raw: str,
    *,
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
) -> SummaryDraft:
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
    return draft_model(prompt_config, evaluation).model_validate_json(content)


def _failed(
    article: Article,
    *,
    model_id: str,
    detail: str,
    generated_at: str,
    failure_code: FailureCode | None = None,
) -> Summary:
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
        failure_code=failure_code,
        failure_detail=detail[:500],
    )


def _publishable_title(raw: str, ask: SummarizeConfig) -> str | None:
    """The drafted title, or nothing if it missed the range it was asked for.

    Nothing, and not a failure. A title is the one part of the payload with a
    working fallback - the source's own headline - so a bad one costs the
    rewrite and not the item (section 1a). The summary has no such fallback,
    which is why the same miss there is fatal.
    """
    title = " ".join(raw.split())
    if not ask.title_words_min <= len(title.split()) <= ask.title_words_max:
        return None
    return title


def to_summary(
    article: Article,
    completion: Completion | None,
    *,
    model_id: str,
    pipeline_fingerprint: str,
    generated_at: str,
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
    duration_ms: int = 0,
    attempt: int = 1,
    no_reply: FailureCode = FailureCode.MODEL_UNREACHABLE,
) -> Summary:
    """One article plus one completion becomes exactly one payload, valid or failed."""
    ask = prompt_config or SummarizeConfig()
    bounds = evaluation or EvaluationConfig()
    if article.status is not ArticleStatus.OK:
        return _failed(
            article,
            model_id=model_id,
            detail="the article did not extract, so there was nothing to summarize",
            generated_at=generated_at,
        )
    if completion is None:
        return _failed(
            article,
            model_id=model_id,
            detail=_NO_REPLY_DETAIL[no_reply],
            generated_at=generated_at,
            failure_code=no_reply,
        )
    if completion.hit_the_budget:
        return _failed(
            article,
            model_id=model_id,
            detail="the reply was cut off by the output budget, so it never closed its JSON",
            generated_at=generated_at,
            failure_code=FailureCode.OUTPUT_TRUNCATED,
        )
    if completion.reasoned:
        return _failed(
            article,
            model_id=model_id,
            detail=(
                "the runtime returned a reasoning channel and thinking was disabled; "
                "the flag did not take, or this build splits reasoning off the content"
            ),
            generated_at=generated_at,
            failure_code=FailureCode.BAD_SHAPE,
        )
    try:
        draft = parse_draft(completion.content, prompt_config=prompt_config, evaluation=bounds)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        return _failed(
            article,
            model_id=model_id,
            detail=f"the reply did not hold its shape: {type(error).__name__}",
            generated_at=generated_at,
            failure_code=FailureCode.BAD_SHAPE,
        )

    words = len(draft.summary.split())
    if not bounds.summary_words_min <= words <= bounds.summary_words_max:
        return _failed(
            article,
            model_id=model_id,
            detail=f"summary is {words} words, outside the publishable range",
            generated_at=generated_at,
            failure_code=FailureCode.LENGTH_OUT_OF_RANGE,
        )

    title = _publishable_title(draft.title, ask)
    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        title=title,
        summary=draft.summary,
        key_points=draft.key_points,
        pipeline_fingerprint=pipeline_fingerprint,
        output_digest=derive_output_digest(draft.summary, draft.key_points, title=title),
        model_id=model_id,
        attempt=attempt,
        source_truncated=article.truncated,
        input_tokens=completion.prompt_tokens,
        output_tokens=completion.completion_tokens,
        prefill_ms=completion.prefill_ms,
        decode_ms=completion.decode_ms,
        cached_tokens=min(completion.cached_tokens, completion.prompt_tokens),
        duration_ms=duration_ms,
        generated_at=generated_at,
        status=SummaryStatus.OK,
    )
