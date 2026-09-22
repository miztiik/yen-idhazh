"""What every stage needs: where things live, and the plumbing they share.

A stage reads a root through this module rather than importing the value, so a
test that redirects one root here redirects it for every reader. An imported
copy would be a second binding the redirect never reaches, and the failure mode
is a test quietly writing into the committed tree.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Final, NamedTuple
from urllib.error import HTTPError

from pydantic import ValidationError

from idhazh import (
    assemble,
    config,
    corpus,
    elements,
    extract,
    fetch,
    ledger,
    summarize,
    tag,
    telemetry,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.feed_health import (
    RobotsOutcome,
)
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemStage
from idhazh.contracts.knobs.extract import ExtractConfig
from idhazh.contracts.knobs.turns import TurnsConfig
from idhazh.contracts.qualification import (
    CanaryObservation,
)
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceTier
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX
from idhazh.evals import evidence
from idhazh.fingerprint import (
    text_digest,
)
from idhazh.llm.server import (
    Completion,
    answer_span,
    is_context_exceeded,
    one_reply,
    post,
    request_timeout_seconds,
    thinking_span,
)
from idhazh.sanitize import SANITIZER_VERSION, sanitize
from idhazh.telemetry.record import recorded_row

LOG: Final = logging.getLogger("idhazh")


VAR_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "run"


VALIDATION_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "validation"


QUALIFICATION_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "qualification"


#: Where a day's judging leaves its draw and its verdicts. A sibling of
#: `VAR_ROOT` rather than a child: judging is not part of the digest run, it
#: downloads none of the run artifacts, and the two trees are uploaded and
#: retained separately. Nothing here is ever committed - a drawn row carries no
#: verdict yet and the shards rewrite it, while a row reaches `state/` once,
#: already judged, and is never edited afterwards. `state/**/*.csv` merges by
#: union, so committing a row that is later rewritten would stack both versions
#: with nothing to say which is current. The relative spelling is the one a log
#: line prints, so the path written and the path reported cannot drift apart.
JUDGE_ROOT_RELPATH: Final = "backend/var/judge"
JUDGE_ROOT: Final = config.REPO_ROOT / JUDGE_ROOT_RELPATH


#: A sibling of `VAR_ROOT` rather than a child, because the run never reads it
#: back and no downstream job downloads it. A test redirects it the same way.
EVIDENCE_ROOT: Final = config.REPO_ROOT / evidence.EVIDENCE_ROOT_RELPATH


#: Where one run's model-call captures go: beside its items rather than inside
#: them. Inside would put every rendered prompt in the `items-<shard>` artifact
#: that `assemble` downloads whole, which is a different retention window and a
#: job that has no use for the text. Derived from the run directory rather than
#: from the repository root, so redirecting `VAR_ROOT` redirects this too - a
#: capture root a test could not move wrote prompts into the working tree on
#: every suite run (2026-09-15).
CAPTURES_DIRNAME: Final = "captures"


#: The planted attacks, run live against a candidate before it is adopted.
CANARY_DIR: Final = config.REPO_ROOT / "tests" / "fixtures" / "canaries"


PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "digest"


CORPUS_ROOT: Final = config.REPO_ROOT / corpus.CORPUS_ROOT_RELPATH


#: Not `Final`: `cli` points it at `state/<run.trial_state_dirname>/` before any
#: stage opens a ledger, and the suite has always redirected it the same way so
#: a test cannot write a committed file.
STATE_ROOT: Path = config.REPO_ROOT / ledger.STATE_DIRNAME


#: Where a shard leaves its recorded input manifest for the assemble stage.
#: One name for every shard of a run: they all observe one configuration, so
#: they all write the same bytes and the atomic rename settles it.
INPUTS_PAYLOAD: Final = "inputs.json"


def _run_dir(date: str) -> Path:
    return VAR_ROOT / date


Fetcher = Callable[[str], fetch.FetchResult]


def silent_tracer() -> telemetry.Tracer:
    """A tracer that records nothing, so no call site has to branch on a toggle.

    Built fresh rather than shared, because a tracer holds the open stack and a
    shared one would let two callers pop each other's spans.
    """
    return telemetry.Tracer(sink=telemetry.NullSink(), now=assemble.utc_now)


def live_fetcher(
    settings: config.Settings,
    *,
    tracer: telemetry.Tracer | None = None,
    read_address: Fetcher | None = None,
) -> Fetcher:
    """The real thing: one robots read per origin, honoured on every later read.

    The cache lives in the closure rather than in a module global, so a caller
    decides its lifetime instead of the interpreter deciding it. One of these
    lives for one run, which is also the recheck cadence a refusal gets: nothing
    about a refusal is persisted, so the next run asks the host again. That is
    `collect.robots_denied_recheck_runs` and `robots_unreachable_recheck_runs`
    at their configured value of one run.

    The document is cached per normalised origin rather than per `netloc`, so
    one host is asked once however it is spelled across a feed's addresses.

    A target the host refused, or one whose rules nobody could establish, is
    never requested. The refusal is built here and no address is read.

    `read_address` is how one address is read, and it is injectable because the
    socket is the one thing here a fixture cannot stand in for. The order - the
    host's rules first, the target only if they allow it - is the policy this
    function exists for, and policy is what a test has to be able to get wrong
    (Guardrail #7).

    `tracer` is what makes the robots read visible, and the same reading now
    lands on the result as `robots_ms`, so the ledger carries the split the
    span was already drawing. `fetch_ms` is one number covering both reads, so
    the first item from a host with a slow robots.txt reads as a slow article
    and the next twenty from that host read as fast ones for no stated reason.
    """
    rules: dict[str, fetch.RobotsRules] = {}
    trace = tracer if tracer is not None else silent_tracer()
    agent = settings.app.extract.user_agent
    read_one = read_address if read_address is not None else _permitted_reader(settings)

    def read(url: str) -> fetch.FetchResult:
        where = fetch.origin(url)
        asking = time.monotonic()
        with trace.span(telemetry.SpanName.ROBOTS) as span:
            span.set(telemetry.AttrKey.ROBOTS_CACHED, where in rules)
            if where not in rules:
                # A host that answered "no such file" publishes no rules; a host
                # that did not answer at all stays a refusal (RFC 9309 sec 2.3.1).
                rules[where] = fetch.robots_rules(read_one(fetch.robots_url(url)))
            permission = rules[where].permits(agent, url)
            span.set(telemetry.AttrKey.ROBOTS_OUTCOME, permission.value)
        robots_ms = int((time.monotonic() - asking) * 1000)
        if permission is not RobotsOutcome.ALLOWED:
            return fetch.refused(permission).with_robots_ms(robots_ms)
        return read_one(url).with_robots_ms(robots_ms)

    return read


def _permitted_reader(settings: config.Settings) -> Fetcher:
    """Read one address we already have permission for. The socket edge."""

    def read(url: str) -> fetch.FetchResult:
        return fetch.fetch(url, config=settings.app.extract, permission=RobotsOutcome.ALLOWED)

    return read


def shard_of(plan: RunPlan, *, shard: int, shards: int) -> list[PlannedItem]:
    """One worker's share, by position rather than by hash.

    Round-robin rather than contiguous blocks, so the verticals - and therefore
    the article lengths - spread evenly instead of one worker drawing every long
    piece and timing out alone.
    """
    if shards <= 1:
        return list(plan.items)
    return [item for index, item in enumerate(plan.items) if index % shards == shard]


class FetchedItem(NamedTuple):
    """One item's article, the body it was cut from, and where the time went.

    A shape rather than a widening tuple, because the two stages that want only
    the article should not have to count placeholders to reach it.
    """

    article: Article
    source_text: str
    fetch_ms: int
    extract_ms: int
    #: The fetch's own split - handshake, first byte, robots, retries. Empty on
    #: a read that reached no socket, which is a state the census can hold.
    timings: fetch.FetchTimings


def _fetch_one(
    item: PlannedItem,
    settings: config.Settings,
    read_url: Fetcher,
    tracer: telemetry.Tracer | None = None,
) -> FetchedItem:
    """The article, the body it was cut from, and how long each step took.

    The timings are separated because a slow item is either a slow host or a
    slow extractor, and only one of those is ours to fix. The untruncated body
    travels beside the payload rather than inside it: the scorer needs it, and
    nothing persists it (Guardrail #1).

    The two spans carry the same split and one thing the columns do not: the
    tagger nests inside the extract span, so a taxonomy that grew a hundred
    patterns shows up as its own step rather than as the extractor getting
    slower.

    `timings` is the fetch half broken down further still, and it rides on the
    result rather than being re-timed here: the handshake and the first byte are
    facts only the socket knows, and a second stopwatch round this call could
    only ever restate `fetch_ms`.
    """
    trace = tracer if tracer is not None else silent_tracer()
    started = time.monotonic()
    with trace.span(telemetry.SpanName.FETCH) as span:
        result = read_url(item.canonical_url)
        span.set(telemetry.AttrKey.OUTCOME, result.outcome.value)
        span.set(telemetry.AttrKey.HTTP_STATUS, result.status)
        span.set(telemetry.AttrKey.BODY_BYTES, len(result.body))
        span.set(telemetry.AttrKey.BODY_TRUNCATED, result.body_truncated)
    fetch_ms = int((time.monotonic() - started) * 1000)

    started = time.monotonic()
    with trace.span(telemetry.SpanName.EXTRACT) as span:
        article, source_text = extract.to_article_with_source(
            item, result, config=settings.app.extract, fetched_at=assemble.utc_now()
        )
        with trace.span(telemetry.SpanName.TAG) as tag_span:
            article = tag.tagged(article, taxonomy=settings.taxonomy, watchlist=settings.watchlist)
            tag_span.set(telemetry.AttrKey.LENS_COUNT, len(article.lenses))
            tag_span.set(telemetry.AttrKey.ENTITY_COUNT, len(article.entities))
            tag_span.set(telemetry.AttrKey.EVENT_COUNT, len(article.events))
        telemetry.article_attributes(
            span, article, source_digest=text_digest(source_text) if source_text else None
        )
    return FetchedItem(
        article=article,
        source_text=source_text,
        fetch_ms=fetch_ms,
        extract_ms=int((time.monotonic() - started) * 1000),
        timings=result.timings,
    )


def _log_no_reply(
    article: Article, *, model_id: str, code: FailureCode, error: OSError, run_id: str | None
) -> None:
    LOG.warning(
        "%s",
        telemetry.event(
            ts=assemble.utc_now(),
            src=ItemStage.SUMMARIZE,
            run=run_id,
            name=telemetry.EventName.ITEM_SUMMARIZE_FAILED,
            level=telemetry.EventLevel.WARNING,
            ctx={
                "item_id": article.item_id,
                "source_id": article.source_id,
                "model_id": model_id,
            },
            data={
                "failure_code": code.value,
                "error_type": type(error).__name__,
            },
        ),
    )


def _two_spans(
    payload: dict[str, Any],
    *,
    article: Article,
    turns: TurnsConfig,
    endpoint: str,
    timeout: float,
) -> Completion:
    """One call, decoded as an unconstrained think and then the constrained answer.

    **Span one is the same body with the grammar off, no budget and a stop at
    the entry's closing marker.** It is derived from the answer body rather
    than rendered again, so both spans open on one string object and the KV slot
    span one filled is the slot span two continues - the prompt cache is asked
    for in `completion_payload` and this is what makes asking worth anything.

    **What span one wrote is spliced into span two's prompt and goes nowhere
    else.** It is discarded here: it is not returned, not persisted, not
    replayed into the next call and not shown to anybody. It is model-written
    text, and a prompt is exactly the channel Guardrail #11 keeps that out of -
    so the one place it is allowed to reach is the request body of the span it
    was thought for, where the schema binds the decode from the first token and
    nothing written in span one can change the shape that comes back.

    An uncapped span ends on the marker or on the window, and the window is a
    request error rather than a length stop - so a span one that runs long is a
    failure with a code rather than a silent truncation.
    """
    thought = post(
        thinking_span(payload, turns=turns),
        endpoint=endpoint,
        timeout=timeout,
    )
    if thought.hit_the_budget:
        LOG.warning(
            "the thinking span stopped on a length limit id=%s tokens=%s",
            article.item_id,
            thought.completion_tokens,
        )
    answer = post(
        answer_span(payload, thought=thought.content, turns=turns),
        endpoint=endpoint,
        timeout=timeout,
    )
    # What the answer span really had to prefill. It is the one reading that
    # settles whether the slot held the thinking or re-read it, which is an
    # estimate until a run prints this (Guardrail #10).
    LOG.info(
        "two spans id=%s think_tokens=%s answer_tokens=%s answer_prefilled=%s cached=%s",
        article.item_id,
        thought.completion_tokens,
        answer.completion_tokens,
        answer.prompt_tokens - answer.cached_tokens,
        answer.cached_tokens,
    )
    return one_reply(thought=thought, answer=answer)


def _ask_the_model(
    payload: dict[str, Any],
    article: Article,
    *,
    model_id: str,
    endpoint: str,
    timeout: float,
    prompt_digest: str,
    run_id: str | None,
    trace: telemetry.Tracer,
    turns: TurnsConfig | None = None,
) -> tuple[Completion | None, FailureCode]:
    """One request, its reply, and the code that says why there is none.

    Shared by the single call and by both halves of the two-call pair, because
    what a caller does with a reply differs and how a reply is asked for does
    not. The generation span is opened here so a run that makes two calls an
    item draws two spans rather than one covering both.

    `turns` decides whether that request is one decode or two. An envelope that
    declares a closing marker gets a thinking span in front of the answer, and
    what comes back is the pair's cost carrying the answer's words. It is
    optional because a caller that has already rendered a chat body has no
    second span to run: the model's own template wrote those bytes, so there is
    no prompt to continue.
    """
    completion: Completion | None
    no_reply = FailureCode.MODEL_UNREACHABLE
    with trace.generation() as span:
        span.set(telemetry.AttrKey.MODEL_ID, model_id)
        span.set(telemetry.AttrKey.PROMPT_DIGEST, prompt_digest)
        try:
            completion = (
                _two_spans(
                    payload,
                    article=article,
                    turns=turns,
                    endpoint=endpoint,
                    timeout=timeout,
                )
                if turns is not None and turns.thinks
                else post(payload, endpoint=endpoint, timeout=timeout)
            )
        except HTTPError as error:
            # Before OSError, which HTTPError subclasses. A server that answered is
            # not an unreachable one, and the body is the only place it says why it
            # refused. It is a stream, so read it once.
            completion = None
            with error:
                body = error.read().decode("utf-8", errors="replace")
            no_reply = (
                FailureCode.CONTEXT_EXCEEDED
                if is_context_exceeded(body)
                else FailureCode.MODEL_REFUSED
            )
            _log_no_reply(article, model_id=model_id, code=no_reply, error=error, run_id=run_id)
        except TimeoutError as error:
            # Before OSError, which TimeoutError also subclasses. A server that ran
            # out of clock was serving, and filing it as unreachable sends an
            # operator to the process instead of to the output budget.
            completion = None
            no_reply = FailureCode.MODEL_TIMED_OUT
            _log_no_reply(article, model_id=model_id, code=no_reply, error=error, run_id=run_id)
        except OSError as error:
            completion = None
            _log_no_reply(article, model_id=model_id, code=no_reply, error=error, run_id=run_id)
        if completion is None:
            span.set(telemetry.AttrKey.FAILURE_CODE, no_reply.value)
        else:
            # Prefill and decode are totals the server reports after the call
            # returned, so they are attributes and cannot be child spans. A
            # span drawn around a duration nobody timed is a shape we invented.
            span.set(telemetry.AttrKey.INPUT_TOKENS, completion.prompt_tokens)
            span.set(telemetry.AttrKey.OUTPUT_TOKENS, completion.completion_tokens)
            span.set(telemetry.AttrKey.CACHED_TOKENS, completion.cached_tokens)
            span.set(telemetry.AttrKey.PREFILL_MS, completion.prefill_ms)
            span.set(telemetry.AttrKey.DECODE_MS, completion.decode_ms)
            span.set(telemetry.AttrKey.HIT_THE_BUDGET, completion.hit_the_budget)
            span.set(telemetry.AttrKey.REASONED, completion.reasoned)
    return completion, no_reply


def _canary_article(
    payload: dict[str, object], *, extract_config: ExtractConfig, fetched_at: str
) -> Article:
    """One planted attack, shaped like the article `extract` would have built.

    The raw text is handed on unsanitized on purpose: `user_turn` fences and
    sanitizes what it is given, so this exercises the boundary instead of
    stepping around it (Guardrail #11). Every count is taken from the sanitized body
    all the same, because those are the words the model is shown, and because a
    count of the raw text can exceed the count of the body it survives into -
    which the payload refuses. The earlier version counted the raw text and
    hardcoded `brief=False`, so a 41-word canary took the long prompt band no
    page of that length is ever given.
    """
    url = str(payload["source_url"])
    raw = str(payload["raw_text"])
    body = sanitize(raw)
    seen, truncated, cut_at = extract.truncate_to_tokens(
        body, extract_config.truncation_cap_tokens
    )
    words = len(seen.split())
    source_words = len(body.split())
    # `extract` reads three shape signals here. The third compares an item
    # against its siblings from the same host, and a canary has none.
    signal: FailureCode | None = None
    if extract.is_not_prose(body, extract_config):
        signal = FailureCode.NOT_PROSE
    elif source_words < extract_config.min_source_words:
        signal = FailureCode.TOO_SHORT
    return Article(
        version=Article.schema_version(),
        item_id="canary-01",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="canary",
        tier=SourceTier.INSTITUTION,
        vertical="canary",
        rank_score=0.0,
        title=str(payload["raw_title"]),
        text=raw,
        word_count=words,
        source_word_count=source_words,
        token_count=extract.approx_tokens(words),
        brief=source_words < extract_config.min_source_words or signal is not None,
        truncated=truncated,
        truncated_at_tokens=cut_at,
        fetched_at=fetched_at,
        status=ArticleStatus.OK,
        failure_code=signal,
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )


def _one_call(
    article: Article, settings: config.Settings, *, endpoint: str
) -> tuple[Summary, Completion | None, float]:
    """One live inference call, timed, with the reply kept for the gates.

    The chat route, so the model's own template writes the prompt and the
    runtime owns the split between thinking and answer. That is why this path
    runs one decode where the digest's runs two: there is no prompt of ours to
    stop at a marker and continue under a grammar.
    """
    request = settings.models.summarize.request
    turns = settings.models.summarize.turns
    model_id = settings.models.summarize.id
    payload = summarize.build_request(
        article,
        model_id=model_id,
        request=request,
        turns=turns,
        prompt_config=settings.app.summarize,
    )
    started = time.monotonic()
    completion: Completion | None
    no_reply = FailureCode.MODEL_UNREACHABLE
    try:
        completion = post(
            payload, endpoint=endpoint, timeout=request_timeout_seconds(request)
        )
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        completion = None
        no_reply = (
            FailureCode.CONTEXT_EXCEEDED
            if is_context_exceeded(body)
            else FailureCode.MODEL_REFUSED
        )
    except TimeoutError:
        completion = None
        no_reply = FailureCode.MODEL_TIMED_OUT
    except OSError:
        completion = None
    seconds = time.monotonic() - started
    summary = summarize.to_summary(
        article,
        completion,
        model_id=model_id,
        generated_at=assemble.utc_now(),
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
        no_reply=no_reply,
        thinking=turns.thinks,
    )
    return summary, completion, seconds


def _run_canaries(
    settings: config.Settings, *, endpoint: str
) -> list[CanaryObservation]:
    """Every planted attack, through the live candidate.

    The unit suite proves these against recorded completions. It cannot prove
    that a model nobody has served before honours this chat template, so the
    attacks run again on real calls before the model is adopted.
    """
    observations: list[CanaryObservation] = []
    for path in sorted(CANARY_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        article = _canary_article(
            payload, extract_config=settings.app.extract, fetched_at=assemble.utc_now()
        )
        summary, completion, _ = _one_call(article, settings, endpoint=endpoint)
        reply = " ".join([summary.title or "", summary.summary or "", *(summary.key_points or [])])
        cleaned = sanitize(str(payload["raw_text"]))
        raw = completion.content if completion else ""
        observations.append(
            CanaryObservation(
                name=str(payload["name"]),
                replied=summary.status is SummaryStatus.OK and bool(summary.summary),
                # The summary already classified why it failed and said it in
                # words. Dropping them here is what left a run recording only
                # `replied: false`, with nothing to read but the canary's name.
                failure_code=summary.failure_code.value if summary.failure_code else None,
                failure_detail=summary.failure_detail,
                markers_present=[m for m in payload["must_not_survive"] if str(m) in reply],
                facts_missing=[f for f in payload["must_survive"] if str(f) not in cleaned],
                forbidden_keys_present=[k for k in payload["forbidden_output"] if str(k) in raw],
            )
        )
        LOG.info(
            "canary run name=%s replied=%s failure_code=%s",
            payload["name"],
            observations[-1].replied,
            observations[-1].failure_code,
        )
    return observations


class _ItemPayload(NamedTuple):
    planned: PlannedItem
    article: Article | None
    summary: Summary | None
    recorded: ItemHealthRow | None
    eval_path: Path
    decision_path: Path


def _item_payloads(
    plan: RunPlan, items_dir: Path, *, require_summary: bool = False
) -> Iterable[_ItemPayload]:
    for item in plan.items:
        article_path = items_dir / f"{item.item_id}.article.json"
        summary_path = items_dir / f"{item.item_id}.summary.json"
        article_exists = article_path.exists()
        summary_exists = summary_path.exists()
        if require_summary and not (article_exists and summary_exists):
            continue
        yield _ItemPayload(
            planned=item,
            article=(
                Article.read(article_path)
                if article_exists
                else None
            ),
            summary=(
                Summary.read(summary_path)
                if summary_exists
                else None
            ),
            # The row the shard sealed for this item, which the census prefers to
            # rebuilding one (`telemetry.census_row`). Read here rather than at
            # each census call site so one place knows where an item's payloads
            # live, which is the same reason the three paths above are here.
            recorded=recorded_row(items_dir, item.item_id),
            eval_path=items_dir / f"{item.item_id}.eval.json",
            decision_path=items_dir / f"{item.item_id}{PAYLOAD_SUFFIX}",
        )


def _extraction_health(
    article: Article | None, settings: config.Settings
) -> elements.ExtractionHealth | None:
    """What the candidate pass got out of one article, for its census row.

    Both writers of the item-health ledger call it, and they have to: the `work`
    job records a row the moment an item settles, hours before the `visuals` job
    runs, and `append_item_health` keeps the first row for a key. A cell only
    assemble could fill would be empty for every item a shard had already
    recorded.

    One article in, three cells out, so the cost is the item and not the archive
    (Guardrail #12).
    """
    if article is None:
        return None
    return elements.extraction_health(
        article,
        config=settings.app.elements,
        min_chart_points=settings.app.visuals.min_chart_points,
    )


def _load_day(path: Path) -> DigestDay | None:
    return DigestDay.from_json(path.read_text(encoding="utf-8")) if path.exists() else None


def _load_manifest(path: Path, *, day: DigestDay | None = None) -> RunManifest | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        manifest = RunManifest.from_json(text)
    except ValidationError:
        if day is None:
            raise
        return _manifest_with_run_vertical_counts(json.loads(text), day)
    if day is None or manifest.version == RunManifest.schema_version():
        return manifest
    return _manifest_with_run_vertical_counts(json.loads(text), day)


def _manifest_with_run_vertical_counts(payload: object, day: DigestDay) -> RunManifest:
    if not isinstance(payload, dict):
        return RunManifest.model_validate(payload)

    counts: Counter[tuple[int, str]] = Counter(
        (item.introduced_by_run, item.vertical) for item in day.items
    )
    migrated_runs = []
    for run in payload.get("runs", []):
        if not isinstance(run, dict):
            migrated_runs.append(run)
            continue
        run_n = int(run.get("n", 0) or 0)
        verticals = []
        for vertical in run.get("verticals", []):
            if not isinstance(vertical, dict):
                verticals.append(vertical)
                continue
            vertical_id = str(vertical.get("id", ""))
            verticals.append({**vertical, "published": counts[(run_n, vertical_id)]})
        migrated_runs.append({**run, "verticals": verticals})
    migrated = {**payload, "version": RunManifest.schema_version(), "runs": migrated_runs}
    return RunManifest.model_validate(migrated)


def published_days(root: Path) -> list[Path]:
    """Every committed day payload under `frontend/public/digest/`, oldest first."""
    return sorted(root.glob("*/*/*/digest.json"))


def _plan_path(date: str) -> Path:
    return _run_dir(date) / "plan.json"


def _load_plan(date: str) -> RunPlan:
    return RunPlan.read(_plan_path(date))
