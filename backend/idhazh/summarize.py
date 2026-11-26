"""Turn one article payload into one summary payload, deterministically.

Four things here are controls rather than preferences, and each one is the
reason a specific failure cannot happen:

- The article text goes in the user turn, fenced and labelled, and never in the
  system prompt. An instruction inside it is data about a web page.
- The response shape is enforced by the decoder, so an injection can change the
  words and cannot change the shape.
- Every normalized reasoning channel is asserted empty where nothing asked for one, rather
  than assumed. A flag that silently stopped taking effect would otherwise cost
  faithfulness for months before anyone noticed. Where the entry DOES declare a
  closing marker, the block is what was asked for and is discarded here instead
  - a refusal that fires on the normal path is not a control.
- A reply that carries an address into our own words is refused. The sanitizer
  runs before the model; this runs after it, so an address a page asked for has
  to survive two controls rather than one (Guardrail #11).

Every number the prompt states is substituted from config at render time
(Guardrail #6). That is not only tidiness: what we ask for is one of the inputs
the run record names, so a reworded ask is visible in the data rather than only
in a commit message.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from string import Template
from typing import Annotated, Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from idhazh.config import DEFAULT_CONFIG_DIR
from idhazh.contracts.article import UNTRUSTED_LINE_MAX, Article, ArticleStatus
from idhazh.contracts.base import (
    PARAGRAPH_BREAK,
    canonical_json,
    derive_output_digest,
    normalize_prose,
    paragraphs_of,
)
from idhazh.contracts.call_cost import CallCost, CallKind
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.knobs.prompts import PromptFilesConfig
from idhazh.contracts.knobs.summarize import SummarizeConfig
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.llm.server import Completion
from idhazh.load_prompt_text import load_prompt_text
from idhazh.sanitize import LINK_PLACEHOLDER, sanitize, untrusted_block

_FENCED_JSON = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

# Why there was no reply to parse. One sentence per cause, because the operator
# reading a failed item needs to know whether to restart a process or shorten a
# prompt, and those are different mornings.
_NO_REPLY_DETAIL: Final[dict[FailureCode, str]] = {
    FailureCode.MODEL_UNREACHABLE: (
        "nothing answered at the model's address, so there was no reply to parse"
    ),
    FailureCode.MODEL_TIMED_OUT: (
        "the model server took the request and did not answer inside "
        "request_timeout_minutes, so the call was cut off mid-decode. It was "
        "serving; it was writing more tokens than the clock admits"
    ),
    FailureCode.SHARD_OUT_OF_TIME: (
        "the worker stopped starting items before it reached this one, so nothing "
        "was ever asked. The article was fetched and extracted; the shard ran out "
        "of its own clock"
    ),
    FailureCode.MODEL_REFUSED: (
        "the model server answered with an error, so there was no reply to parse"
    ),
    FailureCode.CONTEXT_EXCEEDED: (
        "the prompt did not fit the served context window, so the server refused it"
    ),
}


# What the decoder is constrained to emit, and what we agree to believe.
#
# Closed to unknown keys, so a planted tool call fails here rather than reaching
# a payload - the shape is the control, not the prompt.
#
# Each field keeps one bound: it is not empty. Nothing here limits how long a
# headline or a summary may be, so the words the model writes are the words that
# are published.
#
# `title` is required here and optional on the payload. Grammar-constrained
# decoding is free to skip a property that is not required, so an optional title
# is a feature that may simply never fire; the payload stays optional because a
# headline that cannot be published as written should cost the headline, not the
# item.
#
# The class has no docstring on purpose: pydantic copies one into the JSON
# schema, and this schema is the grammar the server is sent and the bytes the
# fingerprint hashes.
NonEmptyParagraph = Annotated[str, StringConstraints(min_length=1)]


class SummaryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Field order is decode order. A list of key points was decoded before the
    # summary until 2026-09-24, so the model found the facts first and then
    # wrote prose connecting them. Nothing read the points afterwards and the
    # extra decode cost about 21 seconds an item, so the scaffold went with
    # them: the title is now the facts-first step and the paragraphs follow it.
    title: str = Field(min_length=1)
    paragraphs: list[NonEmptyParagraph] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_summary(cls, data: Any) -> Any:
        if (
            isinstance(data, Mapping)
            and "paragraphs" not in data
            and isinstance(data.get("summary"), str)
        ):
            translated = dict(data)
            raw = translated.pop("summary")
            translated["paragraphs"] = [raw] if raw else []
            return translated
        return data

    @property
    def summary(self) -> str:
        return normalize_prose(PARAGRAPH_BREAK.join(self.paragraphs))


def _template(
    prompt_files: PromptFilesConfig | None = None, config_dir: Path = DEFAULT_CONFIG_DIR
) -> Template:
    files = prompt_files or PromptFilesConfig()
    return Template(load_prompt_text(config_dir, files.summarize_article))


def output_schema() -> dict[str, Any]:
    """Generated from the model, never hand-written (Guardrail #3)."""
    return SummaryDraft.model_json_schema()


def output_schema_text() -> str:
    """One serialization, so the fingerprint's schema digest is stable."""
    return canonical_json(output_schema())


def system_prompt(
    prompt_config: SummarizeConfig | None = None,
    *,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """The prompt text with config's numbers substituted in.

    `substitute` and never `safe_substitute`: a renamed knob has to raise here
    rather than render `$max_verbatim_words` into a live system prompt, where a
    model would read the placeholder as the instruction it looks like.
    """
    ask = prompt_config or SummarizeConfig()
    return _template(prompt_files, config_dir).substitute(ask.model_dump())


def prompt_inputs(
    prompt_config: SummarizeConfig | None = None,
    *,
    prompt_files: PromptFilesConfig | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> str:
    """What the fingerprint hashes to stand for the prompt.

    The template plus every number that can be substituted into it, so editing
    the wording or a number changes the stamp exactly once.
    """
    ask = prompt_config or SummarizeConfig()
    return _template(prompt_files, config_dir).template + canonical_json(
        ask.model_dump(mode="json")
    )


def user_turn(article: Article) -> str:
    """The article, fenced and labelled as data.

    `untrusted_block` sanitizes what it fences rather than trusting an earlier
    caller, so this cannot hand a model a block it can close.

    The source's own title sits inside the fence with the body. It comes from
    the same untrusted page, so it crosses the same sanitization boundary
    (Guardrail #11).
    """
    parts = []
    if article.title:
        parts.append(f"Title: {article.title}")
    parts.append(article.text or "")
    return (
        f"Source form: {article.source_form.value}\n\n"
        + untrusted_block("\n\n".join(parts))
    )


def parse_draft(raw: str, *, thinking: bool = False) -> SummaryDraft:
    """Believe the response only after it has proved its shape.

    The completion boundary has already separated reasoning using runtime
    channels or the selected entry's explicit delimiters. This parser reads
    only the answer; `to_summary` enforces the reasoning declaration.
    """
    content = raw.strip()
    fenced = _FENCED_JSON.match(content)
    if fenced:
        content = fenced.group(1)
    draft = SummaryDraft.model_validate_json(content)
    # Normalize paragraph separators and remove control characters before publication.
    normalized = draft.summary
    if not normalized:
        raise ValueError("the summary holds nothing once its whitespace and controls are folded")
    draft.paragraphs = paragraphs_of(normalized)
    return draft


def _cost_of(completion: Completion) -> CallCost:
    """One reply's five numbers, as the call that produced them.

    One builder for the ok path and the failed one, so a reply that was refused
    is sized by the same arithmetic as a reply that published.
    """
    return CallCost(
        kind=CallKind.SUMMARIZE,
        prefill_ms=completion.prefill_ms,
        decode_ms=completion.decode_ms,
        input_tokens=completion.prompt_tokens,
        output_tokens=completion.completion_tokens,
        cached_tokens=min(completion.cached_tokens, completion.prompt_tokens),
    )


def _failed(
    article: Article,
    *,
    model_id: str,
    detail: str,
    generated_at: str,
    completion: Completion | None = None,
    failure_code: FailureCode | None = None,
) -> Summary:
    """An item that did not land, carrying what the attempt really cost.

    **The reply is handed over wherever there was one.** Every gate below the
    first two refuses text the server had already read a prompt for and written
    an answer to, so the prefill and the decode were spent whatever the verdict
    was. Recording zero there made a day that failed many replies read as a
    cheap day, and `reconcile_prefill` absorbed the difference as drift.

    A call that never returned is the one failure that really was free. The slot
    stays empty rather than carrying an invented zero, which is what keeps a
    pooled read skipping it instead of averaging it in.
    """
    cost = None if completion is None else _cost_of(completion)
    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        output_digest=derive_output_digest(None),
        model_id=model_id,
        source_truncated=article.truncated,
        generated_at=generated_at,
        status=SummaryStatus.FAILED,
        failure_code=failure_code,
        failure_detail=detail[:500],
        call_1=cost,
        input_tokens=0 if cost is None else cost.input_tokens,
        output_tokens=0 if cost is None else cost.output_tokens,
        prefill_ms=0 if cost is None else cost.prefill_ms,
        decode_ms=0 if cost is None else cost.decode_ms,
        cached_tokens=0 if cost is None else cost.cached_tokens,
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


def _publishable_title(raw: str) -> str | None:
    """The drafted headline exactly as the model wrote it, or nothing.

    Only extra spaces are tidied; the words, their count and their length are the
    model's. Three headlines cannot be published and each one yields nothing
    rather than a failure: a blank one, one that carries an address, and one
    longer than the payload field holds. A title is the one part of the payload
    with a working fallback - the source's own headline - so a bad one costs the
    headline and not the item (section 1a). The summary has no such fallback,
    which is why an address there is fatal. An address in the title takes the
    same route out for the same reason: dropping it removes the address from the
    page, and the summary is checked on its own.
    """
    title = " ".join(raw.split())
    if not title or len(title) > UNTRUSTED_LINE_MAX:
        return None
    if _leaked_address(title) is not None:
        return None
    return title


def to_summary(
    article: Article,
    completion: Completion | None,
    *,
    model_id: str,
    generated_at: str,
    duration_ms: int = 0,
    attempt: int = 1,
    no_reply: FailureCode = FailureCode.MODEL_UNREACHABLE,
    thinking: bool = False,
) -> Summary:
    """One article plus one completion becomes exactly one payload, valid or failed.

    A reply that holds its shape is published exactly as the model wrote it: no
    length is counted against it and none is cut from it. The one rule on its
    words is the address check below.

    `thinking` is the entry's own declaration, and it decides two of the
    refusals below rather than softening them. Where nothing asked for
    reasoning, reasoning arriving by either route is the flag not taking and the
    item fails. Where the entry asked for it, the reasoning is discarded here
    and never reaches the payload - it is model-written text, so a summary that
    carried it would be publishing a stranger's page's influence in our own
    words (Guardrail #11).
    """
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
            completion=completion,
            failure_code=FailureCode.OUTPUT_TRUNCATED,
        )
    if not thinking and completion.reasoned:
        return _failed(
            article,
            model_id=model_id,
            detail=(
                "the runtime returned a reasoning channel and thinking was disabled; "
                "the flag did not take, or this build splits reasoning off the content"
            ),
            generated_at=generated_at,
            completion=completion,
            failure_code=FailureCode.BAD_SHAPE,
        )
    try:
        draft = parse_draft(completion.content, thinking=thinking)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        return _failed(
            article,
            model_id=model_id,
            detail=f"the reply did not hold its shape: {type(error).__name__}",
            generated_at=generated_at,
            completion=completion,
            failure_code=FailureCode.BAD_SHAPE,
        )

    leaked = _leaked_address(draft.summary)
    if leaked is not None:
        return _failed(
            article,
            model_id=model_id,
            detail=f"the summary may not be published: {leaked}",
            generated_at=generated_at,
            completion=completion,
            failure_code=FailureCode.LEAKED_ADDRESS,
        )

    title = _publishable_title(draft.title)
    # The stage makes one call today, so the item total is that call's numbers -
    # derived rather than transcribed, so a second call cannot be recorded in a
    # slot and left out of the total (`Summary` refuses that anyway).
    cost = _cost_of(completion)
    return Summary(
        version=Summary.schema_version(),
        item_id=article.item_id,
        url_key=article.url_key,
        title=title,
        summary=draft.summary,
        output_digest=derive_output_digest(draft.summary, title=title),
        model_id=model_id,
        attempt=attempt,
        source_truncated=article.truncated,
        call_1=cost,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        prefill_ms=cost.prefill_ms,
        decode_ms=cost.decode_ms,
        cached_tokens=cost.cached_tokens,
        duration_ms=duration_ms,
        generated_at=generated_at,
        status=SummaryStatus.OK,
    )
