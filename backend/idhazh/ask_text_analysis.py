"""Which mention and sentence spans does the service find in one article?

One synchronous POST of `Article.text` to the service the digest job started on this
runner, answered by the labelled spans it found. The address is the committed
`text_analysis.base_url`, which the schema holds to this machine, so article text goes
nowhere else (`CLAUDE.md` Guardrail #11). Two more things keep it there. The request
is sent through `open_without_proxy`, so no proxy named by the environment sees it, because
an environment value is the one setting that moves a destination with nobody reading a diff,
and a redirect is never followed with the text.

**Nothing the service returns becomes anything but a number and a lookup key.** A
mention comes back as a label, two offsets and the words it covers. The words are only
compared with what the offsets cut out of `Article.text` and then thrown away, so a
mention that does not point at the words it names is dropped, and every excerpt the
pipeline later shows a model is re-sliced from the article itself. The label is a key
into `elements.label_kinds` and reaches no prompt, path, URL or command.

**The service failing leaves the summary-only path available.** A closed port,
timeout or refusal names the reason. Features and spans are checked independently,
so a malformed sentence never discards valid mentions. The caller logs each
returned mention range with its validation result and rejected sentence ranges,
keyed by the item's identity instead of the URL itself. A caller
with a capture directory keeps the same record there. There is no retry: a second try
against a hung service would double the time a bad runner can spend on one item.
"""

from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, NamedTuple

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from idhazh import atomic_write
from idhazh.anchor_mentions import Mention
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.text_analysis import TextAnalysisConfig
from idhazh.open_without_proxy import open_without_proxy

LOG: Final = logging.getLogger("idhazh")

#: The analysis operation of the service's dated route family. A protocol constant: a
#: new family is a new request and a new reply, so this line and the reader below move
#: together or not at all. `test_text_analysis_client.py` holds it to the service's own
#: declaration.
ANALYZE_PATH: Final = "/api/2026-11-08/run-ner-spacy"

#: Native feature names from the dated service protocol.
FEATURES: Final = ("entities", "sentences")


class Sentence(NamedTuple):
    text: str
    start_char: int
    end_char: int


class Outcome(StrEnum):
    """Why an answer holds the mentions it holds, as a name a span or a log line may carry."""

    OK = "ok"
    #: Nothing listened, or the line closed before an answer.
    UNREACHABLE = "unreachable"
    #: The service held the request past `text_analysis.request_timeout_seconds`.
    TIMED_OUT = "timed_out"
    #: The service answered with an error status, so it read the request and said no.
    REFUSED = "refused"
    #: The service answered 200 and the reply is not the shape this build reads.
    MALFORMED = "malformed"


class Answer(NamedTuple):
    """What the service said about one article, or why it said nothing."""

    mentions: tuple[Mention, ...]
    outcome: Outcome
    #: Wall time of the whole exchange on this process's clock, including a wait that
    #: ended in a timeout. It is what `analyze_ms` records.
    elapsed_ms: int
    http_status: int | None = None
    sentences: tuple[Sentence, ...] = ()


class _Span(BaseModel):
    """The only fields of a mention this module reads. The rest of the reply is ignored."""

    model_config = ConfigDict(extra="ignore", strict=True)

    text: StrictStr
    start_char: StrictInt
    end_char: StrictInt


class _Read(_Span):
    label: StrictStr


class _Reply(BaseModel):
    """Read each requested feature independently so valid siblings survive."""

    model_config = ConfigDict(extra="ignore", strict=True)

    features: list[dict[str, Any]]


class _SpanStatus(StrEnum):
    ACCEPTED = "accepted"
    INVALID_OFFSETS = "invalid_offsets"
    TEXT_MISMATCH = "text_mismatch"


def _record_result(
    article: Article,
    answer: Answer,
    spans: tuple[tuple[Mention, _SpanStatus], ...],
    *,
    capture_root: Path | None,
    sentence_spans: tuple[tuple[Sentence, _SpanStatus], ...] = (),
) -> None:
    dropped_mentions = len(spans) - len(answer.mentions)
    dropped_sentences = len(sentence_spans) - len(answer.sentences)
    level = logging.INFO
    if answer.outcome is not Outcome.OK or dropped_mentions or dropped_sentences:
        level = logging.WARNING
    if capture_root is None and not LOG.isEnabledFor(level):
        return
    line = "text analysis result " + json.dumps(
        {
            "item_id": article.item_id,
            "url_key": article.url_key,
            "outcome": answer.outcome.value,
            "http_status": answer.http_status,
            "elapsed_ms": answer.elapsed_ms,
            "dropped_mentions": dropped_mentions,
            "returned_spans": [
                mention._asdict() | {"status": status.value} for mention, status in spans
            ],
            **({
                "dropped_sentences": dropped_sentences,
                "returned_sentences": [
                    {"start_char": sentence.start_char, "end_char": sentence.end_char,
                     "status": status.value}
                    for sentence, status in sentence_spans
                ],
            } if dropped_sentences else {}),
        },
        separators=(",", ":"),
    )
    LOG.log(level, "%s", line)
    if capture_root is not None:
        try:
            atomic_write.write_atomic(
                capture_root / f"{article.item_id}.text-analysis.log", line + "\n"
            )
        except OSError as error:
            LOG.warning(
                "text analysis capture failed id=%s error=%s", article.item_id, type(error).__name__
            )


def _span_status(text: str, read: _Span) -> _SpanStatus:
    if not 0 <= read.start_char < read.end_char <= len(text):
        return _SpanStatus.INVALID_OFFSETS
    if text[read.start_char : read.end_char] != read.text:
        return _SpanStatus.TEXT_MISMATCH
    return _SpanStatus.ACCEPTED


def _read_mentions(
    text: str, config: TextAnalysisConfig
) -> tuple[list[_Read], list[_Span], Outcome, int | None]:
    request = urllib.request.Request(
        config.base_url + ANALYZE_PATH,
        data=json.dumps({"text": text, "language": config.language, "features": FEATURES}).encode(
            "utf-8"
        ),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with open_without_proxy(request, timeout=config.request_timeout_seconds) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        # Before URLError and OSError, which it subclasses: a service that answered
        # is not an unreachable one.
        with error:
            return [], [], Outcome.REFUSED, error.code
    except TimeoutError:
        return [], [], Outcome.TIMED_OUT, None
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, TimeoutError)
        return [], [], Outcome.TIMED_OUT if timed_out else Outcome.UNREACHABLE, None
    except OSError:
        return [], [], Outcome.UNREACHABLE, None
    except http.client.HTTPException:
        return [], [], Outcome.MALFORMED, None

    try:
        reply = _Reply.model_validate_json(body)
    except ValidationError:
        return [], [], Outcome.MALFORMED, None
    mentions: list[_Read] = []
    sentences: list[_Span] = []
    malformed = False
    for name, field in (
        ("entities", "mentions"),
        ("sentences", "sentences"),
    ):
        matching = [feature for feature in reply.features if feature.get("feature") == name]
        if len(matching) != 1:
            malformed = True
            continue
        feature = matching[0]
        data = feature.get("data")
        if feature.get("status") != "complete" or not isinstance(data, dict):
            malformed = True
            continue
        rows = data.get(field)
        if not isinstance(rows, list):
            malformed = True
            continue
        for row in rows:
            try:
                if name == "entities":
                    mentions.append(_Read.model_validate(row))
                else:
                    sentences.append(_Span.model_validate(row))
            except ValidationError:
                malformed = True
    return mentions, sentences, Outcome.MALFORMED if malformed else Outcome.OK, None


def ask_for_mentions(
    article: Article, config: TextAnalysisConfig, *, capture_root: Path | None = None
) -> Answer:
    """Every valid span the service finds in `Article.text`, or why it found none.

    **Every label comes back, mapped or not.** What a label becomes is
    `elements.label_kinds`' to say, so a new use of a label is a config line here too.
    """
    text = article.text or ""
    started = time.monotonic()
    reads, sentence_reads, outcome, status = _read_mentions(text, config)
    spans = tuple(
        (Mention(read.label, read.start_char, read.end_char), _span_status(text, read))
        for read in reads
    )
    kept = tuple(mention for mention, check in spans if check is _SpanStatus.ACCEPTED)
    sentence_spans = tuple(
        (Sentence(read.text, read.start_char, read.end_char), _span_status(text, read))
        for read in sentence_reads
    )
    sentences = tuple(
        Sentence(
            text[sentence.start_char:sentence.end_char], sentence.start_char, sentence.end_char,
        )
        for sentence, check in sentence_spans if check is _SpanStatus.ACCEPTED
    )
    answer = Answer(kept, outcome, int((time.monotonic() - started) * 1000), status, sentences)
    _record_result(
        article, answer, spans, capture_root=capture_root, sentence_spans=sentence_spans,
    )
    return answer
