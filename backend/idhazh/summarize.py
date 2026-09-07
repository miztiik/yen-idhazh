"""Turn one article payload into one summary payload, deterministically.

Five things here are controls rather than preferences, and each one is the
reason a specific failure cannot happen:

- The article text goes in the user turn, fenced and labelled, and never in the
  system prompt. An instruction inside it is data about a web page.
- The response shape is enforced by the decoder, so an injection can change the
  words and cannot change the shape.
- Every `<think>` block is asserted empty rather than assumed. A flag that
  silently stopped taking effect would otherwise cost faithfulness for months
  before anyone noticed.
- A reply that copies the source instead of summarizing it is refused, because
  republishing an article body is a non-goal (CLAUDE.md section 0a) and not a
  quality score to be tuned.
- A reply that carries an address into our own words is refused. The sanitizer
  runs before the model; this runs after it, so an address a page asked for has
  to survive two controls rather than one (Rule #11).

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
from idhazh.evals.metrics import restates_summary, verbatim_run
from idhazh.llm.server import Completion, request_payload
from idhazh.sanitize import LINK_PLACEHOLDER, sanitize, untrusted_block

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

    # Field order is decode order: key points before the summary, so the model
    # finds the facts first and then writes prose that connects them.
    title: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)


@lru_cache(maxsize=1)
def _template() -> Template:
    return Template(PROMPT_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
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
        key_points=(list[str], Field(min_length=key_points_min, max_length=key_points_max)),
        summary=(str, Field(min_length=min_chars, max_length=max_chars)),
    )


def _key_point_rail(
    ask: SummarizeConfig, source_words: int | None, brief: bool
) -> tuple[int, int]:
    """The key-point floor and ceiling the decoder is held to.

    When an article is named - the production path, through `build_request` and
    the matching `parse_draft` - the rail is the chosen band's own range, so the
    band's ceiling is a control the decoder enforces rather than a request the
    prompt makes: a note is held to one key point, an investigation to five.

    When no article is named - the fingerprint, an offline harness, a schema
    check - the rail is the union across every band, the permissive envelope any
    band's valid reply fits inside.
    """
    if brief:
        band = ask.band_for(0)
        return band.key_points_min, band.key_points_max
    if source_words is not None:
        band = ask.band_for(source_words)
        return band.key_points_min, band.key_points_max
    return (
        min(band.key_points_min for band in ask.bands),
        max(band.key_points_max for band in ask.bands),
    )


def draft_model(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
    *,
    source_words: int | None = None,
    brief: bool = False,
) -> type[SummaryDraft]:
    """The shape the decoder is held to, built from the numbers config holds.

    `source_words` and `brief` pick the band, so the key-point count the decoder
    enforces is the one that band asks for. With neither, the rail is the union
    across every band - the envelope the fingerprint and the offline harnesses
    hold a reply to when no single article applies.
    """
    ask = prompt_config or SummarizeConfig()
    bounds = evaluation or EvaluationConfig()
    key_points_min, key_points_max = _key_point_rail(ask, source_words, brief)
    return _draft_model(
        key_points_min,
        key_points_max,
        bounds.summary_words_min * _MIN_CHARS_PER_WORD,
        bounds.summary_words_max * _MAX_CHARS_PER_WORD,
        ask.title_words_max * _MAX_CHARS_PER_WORD,
    )


def output_schema(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
    *,
    source_words: int | None = None,
    brief: bool = False,
) -> dict[str, Any]:
    """Generated from the model, never hand-written (Rule #3)."""
    return draft_model(
        prompt_config, evaluation, source_words=source_words, brief=brief
    ).model_json_schema()


def output_schema_text(
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
    *,
    source_words: int | None = None,
    brief: bool = False,
) -> str:
    """One serialization, so the fingerprint's schema digest is stable.

    The fingerprint calls this with no article, so it hashes the union rail: a
    stable value that still moves when any band's key-point envelope moves, while
    `prompt_inputs` hashes every band's exact numbers besides.
    """
    return canonical_json(
        output_schema(prompt_config, evaluation, source_words=source_words, brief=brief)
    )


def system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    source_words: int = 0,
    brief: bool = False,
) -> str:
    """The prompt text with config's numbers substituted in.

    `source_words` picks the length band, so a release note and a long read are
    asked for different summaries. It is the length of the SOURCE BODY, before
    `extract.truncation_cap_tokens` cut it - which is what the knob's own name,
    `min_source_words`, says, and what `extract.min_source_words` has always
    compared against.

    It used to be the post-cap length, on the argument that asking about words
    the model never saw invites invention. That argument is about content, and
    a band sets only the target LENGTH: the fenced block still holds the visible
    text and nothing else. The rule also could not work. The post-cap count
    cannot pass `int(truncation_cap_tokens / TOKENS_PER_WORD)`, which at the
    committed cap of 2500 is 1923 words, so the 2000-word band never once fired
    and its longer target range was dead configuration.

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
    rendered = system_prompt(
        prompt_config, source_words=article.band_source_words, brief=article.brief
    )
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
        system=system_prompt(
            prompt_config, source_words=article.band_source_words, brief=article.brief
        ),
        user=user_turn(article),
        output_schema=output_schema(
            prompt_config,
            evaluation,
            source_words=article.band_source_words,
            brief=article.brief,
        ),
        inference=inference,
    )


def split_thinking(raw: str) -> tuple[str, str | None]:
    """Return the content with every think block removed, plus what was inside them.

    Every block is read, not the first. The caller asserts the absence of
    reasoning, so one unread block defeats the assertion: an empty opening block
    in front of a block that reasoned used to pass, and every block was stripped
    afterwards, so nothing downstream could see it either.
    """
    blocks: list[str] = _THINK.findall(raw)
    if not blocks:
        return raw.strip(), None
    return _THINK.sub("", raw).strip(), "\n".join(blocks)


def parse_draft(
    raw: str,
    *,
    prompt_config: SummarizeConfig | None = None,
    evaluation: EvaluationConfig | None = None,
    source_words: int | None = None,
    brief: bool = False,
) -> SummaryDraft:
    """Believe the response only after it has proved its shape.

    A thinking block with content in it is a failure, not a curiosity: the flag
    that was supposed to disable reasoning did not take, and reasoning
    measurably costs faithfulness when summarizing.

    `source_words` and `brief` pick the same band the reply was asked under, so
    the decoder validates a key-point count against the band that requested it.
    """
    content, thought = split_thinking(raw)
    if thought is not None and thought.strip():
        raise ValueError("thinking was disabled and the model reasoned anyway")
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    return draft_model(
        prompt_config, evaluation, source_words=source_words, brief=brief
    ).model_validate_json(content)


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


def _leaked_address(text: str) -> str | None:
    """Why these words may not be published, or nothing.

    `sanitize` owns what an address looks like, and it replaces one with
    `LINK_PLACEHOLDER`. So one pass over our own text answers both questions at
    once: a placeholder already there was lifted out of the fenced source, and a
    placeholder that appears only after the pass was a live address.
    """
    if LINK_PLACEHOLDER in text:
        return "it carries the marker left where the source's address was taken out"
    if LINK_PLACEHOLDER in sanitize(text):
        return "it carries an address, and the item's own link is the only one we publish"
    return None


def _publishable_title(raw: str, ask: SummarizeConfig) -> str | None:
    """The drafted title, or nothing if it missed the range it was asked for.

    Nothing, and not a failure. A title is the one part of the payload with a
    working fallback - the source's own headline - so a bad one costs the
    rewrite and not the item (section 1a). The summary has no such fallback,
    which is why the same miss there is fatal. An address in the title takes the
    same route out for the same reason: dropping it removes the address from the
    page, and the summary is checked on its own.
    """
    title = " ".join(raw.split())
    if not ask.title_words_min <= len(title.split()) <= ask.title_words_max:
        return None
    if _leaked_address(title) is not None:
        return None
    return title


def _distinct_key_points(
    points: list[str], summary: str, *, ceiling: float, floor: int
) -> list[str]:
    """Drop each key point that restates the summary, and keep the item.

    `restates_summary` is the measure the prompt could only ask for: the share of
    a key point's four-word phrases already in the summary. Above `ceiling` the
    key point carries more of the summary's phrasing than a fact of its own, so
    it is dropped - a restating key point is a thin line, not a wrong one, so the
    item degrades and never fails (section 1a).

    The drop never falls below `floor`, the band's own `key_points_min`, which is
    never below one because the published payload requires at least one key point
    (`DigestItem.key_points`). When every key point restates, the least-restating
    up to the floor stay and the item still publishes. Order is preserved for the
    survivors, so the payload reads in the order the model wrote them.
    """
    scored = [(restates_summary(point, summary), index) for index, point in enumerate(points)]
    distinct = sum(1 for score, _ in scored if score <= ceiling)
    keep = max(floor, distinct)
    kept = {index for _, index in sorted(scored)[:keep]}
    return [point for index, point in enumerate(points) if index in kept]


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
        draft = parse_draft(
            completion.content,
            prompt_config=prompt_config,
            evaluation=bounds,
            source_words=article.band_source_words,
            brief=article.brief,
        )
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

    # Read against `article.text`, which is the text the model was shown. For a
    # brief that is the whole article; on a truncated item it is less, so a run
    # measured here can only under-report the copying.
    copied = verbatim_run(draft.summary, article.text or "")
    if copied > bounds.verbatim_reject_ceiling:
        return _failed(
            article,
            model_id=model_id,
            detail=(
                f"{copied:.3f} of the summary is one unbroken run copied from the source, "
                "which republishes the article instead of summarizing it"
            ),
            generated_at=generated_at,
            failure_code=FailureCode.COPIED_SOURCE,
        )

    # A key point that only restates the summary is dropped, not failed, and the
    # drop never removes the last one, so the item always keeps a publishable
    # floor of key points. The address check below then reads what we will
    # actually publish.
    band = ask.band_for(article.band_source_words)
    key_points = _distinct_key_points(
        draft.key_points,
        draft.summary,
        ceiling=ask.key_point_restatement_ceiling,
        floor=band.key_points_min,
    )

    published: list[tuple[str, str]] = [("summary", draft.summary)]
    published += [("key point", point) for point in key_points]
    for field, text in published:
        leaked = _leaked_address(text)
        if leaked is not None:
            return _failed(
                article,
                model_id=model_id,
                detail=f"the {field} may not be published: {leaked}",
                generated_at=generated_at,
                failure_code=FailureCode.LEAKED_ADDRESS,
            )

    title = _publishable_title(draft.title, ask)
    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        title=title,
        summary=draft.summary,
        key_points=key_points,
        pipeline_fingerprint=pipeline_fingerprint,
        output_digest=derive_output_digest(draft.summary, key_points, title=title),
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
