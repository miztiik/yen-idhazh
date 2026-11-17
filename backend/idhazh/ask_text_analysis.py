"""Which people and places does the text-analysis service find in one article?

One synchronous POST of `Article.text` to the service the digest job started on this
runner, answered by the labelled spans it found. The address is the committed
`text_analysis.base_url`, which the schema holds to this machine, so article text goes
nowhere else (`CLAUDE.md` Guardrail #11). Two more things keep it there. The request
is sent without any proxy named by the environment, because an environment value is the
one setting that moves a destination with nobody reading a diff, and a redirect is
never followed with the text.

**Nothing the service returns becomes anything but a number and a lookup key.** A
mention comes back as a label, two offsets and the words it covers. The words are only
compared with what the offsets cut out of `Article.text` and then thrown away, so a
mention that does not point at the words it names is dropped, and every excerpt the
pipeline later shows a model is re-sliced from the article itself. The label is a key
into `elements.label_kinds` and reaches no prompt, path, URL or command.

**The service failing costs the item its names and nothing else.** A closed port, a
service that never answers, a refusal and a reply this build cannot read each return no
mentions, name the reason, and log one warning that carries the item's id and no text.
There is no retry: a second try against a hung service would double the time a bad
runner can spend on one item.
"""

from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from enum import StrEnum
from typing import Final, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from idhazh.anchor_mentions import Mention
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.text_analysis import TextAnalysisConfig

LOG: Final = logging.getLogger("idhazh")

#: The analysis operation of the service's dated route family. A protocol constant: a
#: new family is a new request and a new reply, so this line and the reader below move
#: together or not at all. `test_text_analysis_client.py` holds it to the service's own
#: declaration.
ANALYZE_PATH: Final = "/api/2026-11-08/run-ner-spacy"

#: The one feature asked for. Its result is the raw mention list this module reads.
FEATURE: Final = "entities"

#: No proxy, whatever the environment says. `urllib` otherwise honours `http_proxy` for
#: a loopback address too, which would send the text wherever that value points.
_OPENER: Final = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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


class _Read(BaseModel):
    """The only fields of a mention this module reads. The rest of the reply is ignored."""

    model_config = ConfigDict(extra="ignore", strict=True)

    text: StrictStr
    label: StrictStr
    start_char: StrictInt
    end_char: StrictInt


class _Mentions(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    mentions: list[_Read]


class _EntitiesFeature(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    feature: Literal["entities"]
    status: Literal["complete"]
    data: _Mentions


class _Reply(BaseModel):
    """A reply that carries exactly the one complete feature that was asked for."""

    model_config = ConfigDict(extra="ignore", strict=True)

    features: tuple[_EntitiesFeature]


def _failed(
    article: Article, outcome: Outcome, *, started: float, status: int | None = None
) -> Answer:
    elapsed_ms = int((time.monotonic() - started) * 1000)
    LOG.warning(
        "text analysis gave no mentions id=%s outcome=%s http_status=%s elapsed_ms=%s",
        article.item_id,
        outcome.value,
        status if status is not None else "-",
        elapsed_ms,
    )
    return Answer((), outcome, elapsed_ms, status)


def _anchored(text: str, read: _Read) -> bool:
    """Whether the offsets cut out of the article the very words the service returned."""
    return 0 <= read.start_char < read.end_char <= len(text) and (
        text[read.start_char : read.end_char] == read.text
    )


def ask_for_mentions(article: Article, config: TextAnalysisConfig) -> Answer:
    """Every labelled span the service finds in `Article.text`, or why it found none.

    **Every label comes back, mapped or not.** What a label becomes is
    `elements.label_kinds`' to say, so a new use of a label is a config line here too.
    """
    text = article.text or ""
    started = time.monotonic()
    request = urllib.request.Request(
        config.base_url + ANALYZE_PATH,
        data=json.dumps({"text": text, "language": config.language, "features": [FEATURE]}).encode(
            "utf-8"
        ),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with _OPENER.open(request, timeout=config.request_timeout_seconds) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        # Before URLError and OSError, which it subclasses: a service that answered
        # is not an unreachable one.
        with error:
            return _failed(article, Outcome.REFUSED, started=started, status=error.code)
    except TimeoutError:
        return _failed(article, Outcome.TIMED_OUT, started=started)
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, TimeoutError)
        return _failed(
            article, Outcome.TIMED_OUT if timed_out else Outcome.UNREACHABLE, started=started
        )
    except OSError:
        return _failed(article, Outcome.UNREACHABLE, started=started)
    except http.client.HTTPException:
        return _failed(article, Outcome.MALFORMED, started=started)

    try:
        reply = _Reply.model_validate_json(body)
    except ValidationError:
        return _failed(article, Outcome.MALFORMED, started=started)

    reads = reply.features[0].data.mentions
    kept = tuple(
        Mention(read.label, read.start_char, read.end_char)
        for read in reads
        if _anchored(text, read)
    )
    if len(kept) != len(reads):
        LOG.warning(
            "text analysis mentions dropped id=%s dropped=%s kept=%s",
            article.item_id,
            len(reads) - len(kept),
            len(kept),
        )
    return Answer(kept, Outcome.OK, int((time.monotonic() - started) * 1000))
