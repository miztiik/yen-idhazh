"""The pipeline, as three stages a person can run one at a time.

Each stage takes a file and writes a file, which is the whole reason the
pipeline can be sharded across disposable machines and re-run cheaply. A stage
that only works as part of the whole is a stage nobody can debug.

    idhazh plan       read feeds, rank, record      -> run/<date>/plan.json
    idhazh work       fetch, extract, summarize, score -> run/<date>/items/*
    idhazh assemble   collect what finished        -> frontend/public/... + state/

`idhazh run` is the three in order, which is what a developer wants and what
the daily workflow calls.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Final, NamedTuple
from urllib.error import HTTPError
from urllib.parse import urlsplit

from pydantic import ValidationError

from idhazh import (
    assemble,
    config,
    discover,
    extract,
    fetch,
    ledger,
    publish_telemetry,
    rank,
    route,
    summarize,
    telemetry,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.route import Route, VisualKind
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.validation_row import ValidationVerdict
from idhazh.embed import Embedder
from idhazh.evals import golden, metrics, score, validation, writer
from idhazh.evals.hhem import HHEM_SCORER_ID, HhemScorer, dual_score, weights_digest
from idhazh.fingerprint import build_inputs, text_digest
from idhazh.llm.server import DEFAULT_ENDPOINT, Completion, is_context_exceeded, post
from idhazh.render import asset_relpath, highest_ordinal, render_route
from idhazh.sanitize import SANITIZER_VERSION

LOG: Final = logging.getLogger("idhazh")
VAR_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "run"
VALIDATION_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "validation"
PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "digest"
STATE_ROOT: Final = config.REPO_ROOT / ledger.STATE_DIRNAME
LEDGER: Final = config.REPO_ROOT / writer.LEDGER_RELPATH


def _run_dir(date: str) -> Path:
    return VAR_ROOT / date


def _today() -> str:
    return assemble.utc_now()[:10]


# --- the two seams ------------------------------------------------------------

Fetcher = Callable[[str], fetch.FetchResult]
"""Read one address. The only edge of the pipeline that touches a socket.

Every stage that reads the open web takes one of these. In a run it is
`live_fetcher`; in a test it is a function that reads `tests/fixtures/feeds/`.
That is not a mock - it is the same signature reading a real captured file, so
no test needs the network (Rule #7) and every fetch outcome, including the
ones a live run cannot be made to produce on demand, is reachable.
"""

Clock = Callable[[], str]
"""Now, as an ISO-8601 UTC stamp.

Injected for the same reason as the fetcher: a rule about how old an article is
cannot be tested against a real clock without the test changing its answer at
midnight.
"""


def live_fetcher(settings: config.Settings) -> Fetcher:
    """The real thing: one robots read per host, honoured on every later read.

    The cache lives in the closure rather than in a module global, so a caller
    decides its lifetime instead of the interpreter deciding it.
    """
    robots: dict[str, str | None] = {}

    def read(url: str) -> fetch.FetchResult:
        host = urlsplit(url).netloc
        if host not in robots:
            result = fetch.fetch(fetch.robots_url(url), config=settings.app.extract, robots_txt="")
            # A host that answered "no such file" publishes no rules; a host
            # that did not answer at all stays a refusal (RFC 9309 sec 2.3.1).
            robots[host] = fetch.robots_from_result(result)
        return fetch.fetch(url, config=settings.app.extract, robots_txt=robots[host])

    return read


# --- plan -------------------------------------------------------------------


def stage_plan(
    date: str,
    *,
    settings: config.Settings,
    fetcher: Fetcher | None = None,
    now: Clock | None = None,
    run_n: int | None = None,
    state_dir: Path | None = None,
) -> RunPlan:
    """Read every live feed, rank the pool, and write down what it saw. No model.

    Three committed ledgers bound the day. The seen store gives an article whose
    feed carried no date a real age - first sight is the only honest one there
    is. The published store is what stops a repeat, which a freshness rule
    cannot do on its own: an article published at 23:00 is seven hours old at
    06:00 the next morning. The health store records what every feed did, so a
    source that has gone quiet can be quarantined from evidence instead of from
    somebody's memory. Quarantine only ever holds a feed back for a few runs; it
    never edits `config/sources.json`, because retiring a source is a person's
    decision.

    Nothing is dropped for being old. `run.safety_ceiling_per_run` is a crash
    guard against a mis-parsed feed, not a reading budget.
    """
    read_url = fetcher or live_fetcher(settings)
    clock = now or assemble.utc_now
    state = state_dir if state_dir is not None else STATE_ROOT
    collect = settings.app.collect
    generated_at = clock()
    run_id = f"{date}-{run_n if run_n is not None else _next_run_n(date)}"

    candidates: list[discover.Candidate] = []
    health: list[FeedHealthRow] = []
    asleep = discover.resting(
        ledger.load_health(state, today=date, within_days=ledger.HEALTH_WINDOW_DAYS),
        after_failures=collect.quarantine_after_failures,
    )
    read = failed = skipped = 0
    for feed in settings.sources.feeds:
        if feed.id in asleep:
            skipped += 1
            LOG.info("feed resting id=%s", feed.id)
            health.append(_rest_row(feed, at=generated_at, run_id=run_id))
            continue
        result = read_url(feed.url)
        found = discover.candidates_from_feed(feed, result.body) if result.ok else []
        health.append(_health_row(feed, result, found=len(found), at=generated_at, run_id=run_id))
        if not result.ok:
            failed += 1
            LOG.warning("feed unavailable id=%s reason=%s", feed.id, result.detail)
            continue
        read += 1
        # What the feed offered is the health row's business; what we accept is
        # the pool's. A promotional page a healthy feed syndicated is not the
        # feed failing, so the two counts stay apart.
        kept, blocked = discover.split_blocked(found, markers=collect.blocked_url_markers)
        for candidate in blocked:
            LOG.info(
                "candidate blocked feed=%s reason=address_marker url=%s",
                feed.id,
                candidate.canonical_url,
            )
        candidates.extend(kept)

    front_page: set[str] = set()
    for salience in settings.sources.salience:
        result = read_url(salience.url)
        if result.ok:
            front_page |= discover.salience_urls(result.body)

    first_seen = ledger.load_seen(state, today=date, within_days=collect.seen_window_days)
    landed = ledger.append_seen(
        state, date, _first_sights(candidates, first_seen, generated_at, run_id)
    )
    ledger.append_health(state, date, health)
    already_published = frozenset(ledger.load_published(state))

    watchlist_keys: frozenset[str] = frozenset()
    verticals = []
    items: list[PlannedItem] = []
    for vertical in settings.taxonomy.verticals:
        live = discover.live(settings.sources.feeds, vertical.id)
        summary, planned = rank.plan_vertical(
            vertical,
            [c for c in candidates if c.vertical == vertical.id],
            config=collect,
            live_feeds=len(live),
            now=generated_at,
            first_seen=first_seen,
            already_published=already_published,
            watchlist_keys=watchlist_keys,
            front_page_keys=frozenset(front_page),
        )
        verticals.append(summary)
        items.extend(planned)

    items = _dedupe_planned_items(items)
    items = _within_ceiling(items, ceiling=settings.app.run.safety_ceiling_per_run)
    counts = Counter(item.vertical for item in items)
    verticals = [
        summary.model_copy(update={"planned": counts.get(summary.id, 0)}) for summary in verticals
    ]
    LOG.info("first sights recorded new=%s file=%s", landed, ledger.seen_relpath(date))

    return RunPlan(
        version=RunPlan.schema_version(),
        date=date,
        run_id=run_id,
        generated_at=generated_at,
        feeds_read=read,
        feeds_failed=failed,
        feeds_skipped=skipped,
        verticals=verticals,
        items=items,
    )


def _rest_row(feed: FeedDef, *, at: str, run_id: str) -> FeedHealthRow:
    """The row a quarantined feed gets. A record that we chose not to ask.

    Written rather than omitted so the rest can end: a run that left no trace
    would leave the old failures as the newest thing on record forever, and the
    feed would never be tried again.
    """
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=run_id,
        date=at[:10],
        feed_id=feed.id,
        checked_at=at,
        outcome=FetchOutcome.SKIPPED,
        items=0,
        detail="resting after repeated failures",
    )


def _health_row(
    feed: FeedDef,
    result: fetch.FetchResult,
    *,
    found: int,
    at: str,
    run_id: str,
) -> FeedHealthRow:
    """This run's verdict on one feed.

    `detail` is our own sentence about the failure - a status name or an
    exception class - and never the response body. A feed is a stranger's text
    and this row lands on a published page (Rule #11).
    """
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=run_id,
        date=at[:10],
        feed_id=feed.id,
        checked_at=at,
        outcome=result.outcome,
        status=result.status,
        items=found,
        detail=result.detail[:200] if result.detail else None,
    )


def _first_sights(
    candidates: Iterable[discover.Candidate],
    known: dict[str, str],
    at: str,
    run_id: str,
) -> list[SeenRow]:
    """The addresses this run met for the first time, in address order.

    Recorded before anything is ranked, so an article that never made the day
    still has an age the next run can use. `known` is updated in place, which
    is what lets the ranking read this run's own sightings without a re-read.
    """
    fresh: dict[str, SeenRow] = {}
    for candidate in candidates:
        if candidate.url_key in known or candidate.url_key in fresh:
            continue
        fresh[candidate.url_key] = SeenRow(
            version=SeenRow.schema_version(),
            url_key=candidate.url_key,
            canonical_url=candidate.canonical_url,
            first_seen_at=at,
            first_seen_run=run_id,
        )
    known.update({url_key: row.first_seen_at for url_key, row in fresh.items()})
    return [fresh[url_key] for url_key in sorted(fresh)]


def _within_ceiling(items: list[PlannedItem], *, ceiling: int) -> list[PlannedItem]:
    """The crash guard. A normal day never reaches it.

    It drops the lowest-scoring stories across every vertical rather than
    truncating the list, so a mis-parsed feed costs the weakest items and not
    whichever vertical happened to sort last.
    """
    if len(items) <= ceiling:
        return items
    ranked = sorted(items, key=lambda item: (-item.rank_score, item.item_id))[:ceiling]
    keep = {item.item_id for item in ranked}
    LOG.warning("safety ceiling reached planned=%s ceiling=%s", len(items), ceiling)
    return [item for item in items if item.item_id in keep]


def _dedupe_planned_items(items: list[PlannedItem]) -> list[PlannedItem]:
    """Keep one planned item per address before the crash guard counts slots."""
    by_key: dict[str, list[PlannedItem]] = {}
    for item in items:
        by_key.setdefault(item.url_key, []).append(item)

    duplicate_keys = [url_key for url_key, carried in by_key.items() if len(carried) > 1]
    if not duplicate_keys:
        return items

    winners = {
        url_key: min(
            carried,
            key=lambda item: (-item.rank_score, item.vertical, item.item_id, item.source_id),
        )
        for url_key, carried in by_key.items()
    }
    dropped = [item for item in items if winners[item.url_key] is not item]
    LOG.info(
        "plan duplicates dropped count=%s url_keys=%s source_ids=%s",
        len(dropped),
        ",".join(sorted(duplicate_keys)),
        ",".join(sorted({item.source_id for item in dropped})),
    )
    return [item for item in items if winners[item.url_key] is item]


def _next_run_n(date: str) -> int:
    """Which run of the day this is, read from what the last one committed.

    The schedule runs several times a day, so `-1` is no longer a safe
    constant: two runs claiming one run id put two different work lists under
    the same address in the manifest.
    """
    target = assemble.day_dir(PUBLIC_ROOT, date)
    manifest = _load_manifest(target / "run.json", day=_load_day(target / "digest.json"))
    return manifest.runs[-1].n + 1 if manifest else 1


# --- work -------------------------------------------------------------------


def shard_of(plan: RunPlan, *, shard: int, shards: int) -> list[PlannedItem]:
    """One worker's share, by position rather than by hash.

    Round-robin rather than contiguous blocks, so the verticals - and therefore
    the article lengths - spread evenly instead of one worker drawing every long
    piece and timing out alone.
    """
    if shards <= 1:
        return list(plan.items)
    return [item for index, item in enumerate(plan.items) if index % shards == shard]


class _FetchedWorkItem(NamedTuple):
    item: PlannedItem
    article: Article
    fetch_ms: int
    extract_ms: int
    started: float
    original_index: int


def _summarize_band_sort_key(
    work: _FetchedWorkItem, settings: config.Settings
) -> tuple[int, int]:
    band = settings.app.summarize.band_for(work.article.word_count)
    return band.min_source_words, work.original_index


def stage_work(
    plan: RunPlan,
    *,
    settings: config.Settings,
    scorer: object | None,
    shard: int = 0,
    shards: int = 1,
    fetcher: Fetcher | None = None,
    model_endpoint: str = DEFAULT_ENDPOINT,
) -> None:
    """Fetch, extract, summarize and score one item at a time, writing as it goes."""
    read_url = fetcher or live_fetcher(settings)
    inference = settings.app.models.inference
    model = settings.app.models.summarize
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256 or "0" * 64,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build="llama-server-local",
        chat_template=model.id,
        prompt=summarize.prompt_inputs(settings.app.summarize),
        output_schema=summarize.output_schema_text(settings.app.summarize, settings.app.evaluation),
        runner_class="local",
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )
    fingerprint = inputs.fingerprint()
    scorer_version = metrics.scorer_version(
        scorer_id=HHEM_SCORER_ID,
        scorer_revision=text_digest(HHEM_SCORER_ID),
        weights_sha256=weights_digest(scorer) if isinstance(scorer, HhemScorer) else "0" * 64,
        evaluation=settings.app.evaluation,
    )

    items_dir = _run_dir(plan.date) / "items"
    mine = shard_of(plan, shard=shard, shards=shards)
    LOG.info("working shard=%s/%s items=%s", shard, shards, len(mine))
    ready: list[_FetchedWorkItem] = []
    for original_index, item in enumerate(mine):
        started = time.monotonic()
        article, fetch_ms, extract_ms = _fetch_one(item, settings, read_url)
        assemble.write_atomic(items_dir / f"{item.item_id}.article.json", article.to_json())
        if article.status is not ArticleStatus.OK:
            LOG.info("item degraded id=%s reason=%s", item.item_id, article.failure_detail)
            continue
        ready.append(
            _FetchedWorkItem(
                item=item,
                article=article,
                fetch_ms=fetch_ms,
                extract_ms=extract_ms,
                started=started,
                original_index=original_index,
            )
        )

    for work in sorted(ready, key=lambda candidate: _summarize_band_sort_key(candidate, settings)):
        item = work.item
        article = work.article
        model_started = time.monotonic()
        summary = _summarize_one(
            article, settings, fingerprint, endpoint=model_endpoint, run_id=plan.run_id
        )
        summarize_ms = int((time.monotonic() - model_started) * 1000)
        summary = summary.model_copy(
            update={
                "duration_ms": int((time.monotonic() - work.started) * 1000),
                "fetch_ms": work.fetch_ms,
                "extract_ms": work.extract_ms,
                "summarize_ms": summarize_ms,
            }
        )
        assemble.write_atomic(items_dir / f"{item.item_id}.summary.json", summary.to_json())
        if summary.status is not SummaryStatus.OK or scorer is None:
            continue

        seen = article.text or ""
        score_started = time.monotonic()
        hhem, hhem_full = dual_score(
            scorer,  # type: ignore[arg-type]
            seen_text=seen,
            full_text=seen,
            summary=summary.summary or "",
        )
        score_ms = int((time.monotonic() - score_started) * 1000)
        row = score.to_eval_row(
            item=item,
            article=article,
            summary=summary,
            full_text=seen,
            hhem=hhem,
            hhem_full=hhem_full,
            config=settings.app.evaluation,
            date=plan.date,
            run_id=plan.run_id,
            scorer_version=scorer_version,
            scored_at=assemble.utc_now(),
        )
        row = row.model_copy(update={"score_ms": score_ms})
        assemble.write_atomic(items_dir / f"{item.item_id}.eval.json", row.to_json())
        LOG.info(
            "item scored id=%s band=%s fetch=%sms extract=%sms model=%sms score=%sms",
            item.item_id,
            row.band.value,
            work.fetch_ms,
            work.extract_ms,
            summarize_ms,
            score_ms,
        )


def _fetch_one(
    item: PlannedItem, settings: config.Settings, read_url: Fetcher
) -> tuple[Article, int, int]:
    """The article plus how long the network and the extractor each took.

    Separated because a slow item is either a slow host or a slow extractor, and
    only one of those is ours to fix.
    """
    started = time.monotonic()
    result = read_url(item.canonical_url)
    fetch_ms = int((time.monotonic() - started) * 1000)

    started = time.monotonic()
    article = extract.to_article(
        item, result, config=settings.app.extract, fetched_at=assemble.utc_now()
    )
    return article, fetch_ms, int((time.monotonic() - started) * 1000)


def _log_no_reply(
    article: Article, *, model_id: str, code: FailureCode, error: OSError, run_id: str | None
) -> None:
    event = {
        "ts": assemble.utc_now(),
        "src": "summarize",
        "v": "1",
        "run": run_id,
        "name": "item.summarize.failed",
        "level": "warning",
        "ctx": {
            "item_id": article.item_id,
            "source_id": article.source_id,
            "model_id": model_id,
        },
        "data": {
            "failure_code": code.value,
            "error_type": type(error).__name__,
        },
    }
    LOG.warning("%s", json.dumps(event, sort_keys=True, separators=(",", ":")))


def _summarize_one(
    article: Article,
    settings: config.Settings,
    fingerprint: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    run_id: str | None = None,
) -> Summary:
    inference = settings.app.models.inference
    model_id = settings.app.models.summarize.id
    payload = summarize.build_request(
        article,
        model_id=model_id,
        inference=inference,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    completion: Completion | None
    no_reply = FailureCode.MODEL_UNREACHABLE
    try:
        request_timeout_seconds = settings.app.models.inference.request_timeout_minutes * 60
        completion = post(
            payload,
            endpoint=endpoint,
            timeout=request_timeout_seconds,
        )
    except HTTPError as error:
        # Before OSError, which HTTPError subclasses. A server that answered is
        # not an unreachable one, and the body is the only place it says why it
        # refused. It is a stream, so read it once.
        completion = None
        with error:
            if is_context_exceeded(error.read().decode("utf-8", errors="replace")):
                no_reply = FailureCode.CONTEXT_EXCEEDED
        _log_no_reply(article, model_id=model_id, code=no_reply, error=error, run_id=run_id)
    except OSError as error:
        completion = None
        _log_no_reply(article, model_id=model_id, code=no_reply, error=error, run_id=run_id)
    return summarize.to_summary(
        article,
        completion,
        model_id=model_id,
        pipeline_fingerprint=fingerprint,
        generated_at=assemble.utc_now(),
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
        no_reply=no_reply,
    )


# --- route -------------------------------------------------------------------


class _RoutableItem(NamedTuple):
    item: PlannedItem
    article_path: Path
    summary: Summary


def already_published(date: str) -> frozenset[str]:
    """The item ids the day's committed digest already carries.

    `assemble.build_day` keeps an already-published item and discards the new
    run's copy of it, because the reading order is part of what a shared link
    shows. So a later run's routing decision for one of those items can never
    reach a reader: it is computed, written, read back, and thrown away.

    A day runs five times. Without this the second run spends its whole budget
    re-deciding the first run's items at 20 to 40 measured seconds each, and the
    items it actually introduced queue behind them.
    """
    day = _load_day(assemble.day_dir(PUBLIC_ROOT, date) / "digest.json")
    return frozenset(item.item_id for item in day.items) if day else frozenset()


def routable_items(
    plan: RunPlan, items_dir: Path, *, published: frozenset[str]
) -> list[_RoutableItem]:
    """The items this run could still decide, best story first.

    Rank order, not plan order. The plan is vertical-major, so stopping part-way
    down it would cost whole verticals their pictures while the weakest story in
    the first vertical kept one. This is the rule the safety ceiling already
    follows: drop the weakest stories across every vertical, never a suffix.

    The article stays on disk until the item is actually routed. Building this
    list is what lets the stage know its own denominator before it spends
    anything on the first item.
    """
    routable: list[_RoutableItem] = []
    for item in plan.items:
        if item.item_id in published:
            continue
        article_path = items_dir / f"{item.item_id}.article.json"
        summary_path = items_dir / f"{item.item_id}.summary.json"
        if not (article_path.exists() and summary_path.exists()):
            continue
        summary = Summary.from_json(summary_path.read_text(encoding="utf-8"))
        if summary.status is not SummaryStatus.OK:
            continue
        routable.append(_RoutableItem(item, article_path, summary))
    routable.sort(key=lambda entry: (-entry.item.rank_score, entry.item.item_id))
    return routable


def stage_route(
    plan: RunPlan,
    *,
    settings: config.Settings,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Decide and draw the visuals, one item at a time.

    A separate stage from `work` because it runs a different, smaller model, and
    one llama-server serves one set of weights. Splitting it also means a run
    that never starts a router still publishes - every item simply carries no
    picture, which is already the common and correct answer.

    **The stage stops itself at `run.route_budget_minutes`.** It used to run
    until the job's own timeout killed it, and a killed job uploads no artifact,
    so a day that overran by one item threw away every decision the whole hour
    had bought. Measured on `ubuntu-latest`: five of the eight runs since the
    daily size moved to 200 items were cancelled that way, and each one published
    a full day with zero visuals. Stopping early is the difference between
    publishing the charts the run made and publishing none of them (Rule #2 -
    the feature fits the runner, the runner is not raised to fit the feature).

    **It also skips what the day already published**, because the assembler keeps
    the published copy and discards the new one. That is what makes the stage
    resumable in the sense the rest of the pipeline already is: a re-run costs
    only the items the earlier run did not introduce.

    `clock` is injected so the bound can be tested without spending it.
    """
    items_dir = _run_dir(plan.date) / "items"
    visuals = settings.app.visuals
    ordinals: dict[str, int] = {}
    spent: list[int] = []
    skipped = 0
    drafted = 0
    kept = 0
    unrouted = 0

    published = already_published(plan.date)
    routable = routable_items(plan, items_dir, published=published)
    budget_ms = settings.app.run.route_budget_minutes * 60_000
    stage_started = clock()
    LOG.info(
        "routing start items=%s already_published=%s budget_minutes=%s",
        len(routable),
        len(published),
        settings.app.run.route_budget_minutes,
    )

    for index, entry in enumerate(routable):
        if (clock() - stage_started) * 1000 >= budget_ms:
            unrouted = len(routable) - index
            break
        item, summary = entry.item, entry.summary
        article = Article.from_json(entry.article_path.read_text(encoding="utf-8"))

        started = clock()
        decision, asked = _route_one(article, summary, settings)
        if not asked:
            skipped += 1
        if decision.drafted_chart:
            drafted += 1
        if decision.kind is not VisualKind.NONE:
            # Numbering continues from what this day already holds. A day runs
            # several times, and starting from one in each process overwrote the
            # earlier run's file while the digest still referenced both items.
            if article.vertical not in ordinals:
                ordinals[article.vertical] = highest_ordinal(
                    PUBLIC_ROOT.parent, plan.date, article.vertical
                )
            ordinals[article.vertical] += 1
            decision = render_route(
                decision,
                public_root=PUBLIC_ROOT.parent,
                relpath=asset_relpath(plan.date, article.vertical, ordinals[article.vertical]),
                canvas_width=visuals.canvas_width,
                canvas_height=visuals.canvas_height,
            )
        if decision.kind is VisualKind.CHART:
            kept += 1
        route_ms = int((clock() - started) * 1000)
        spent.append(route_ms)
        decision = decision.model_copy(update={"route_ms": route_ms})
        assemble.write_atomic(items_dir / f"{item.item_id}.route.json", decision.to_json())
        LOG.info(
            "item routed id=%s kind=%s state=%s asked=%s route_ms=%s",
            item.item_id,
            decision.kind.value,
            decision.visual_state.value,
            asked,
            route_ms,
        )

    # The job's own wall-clock is in the run log; this is what the stage inside
    # it spent. The gap between the two is the fixed cost - checkout, weights,
    # install, model start - and separating them is the whole point of the
    # measurement (Rule #10).
    total_ms = sum(spent)
    # `drafted` minus `kept` is what the post-model checks refused. Without both
    # numbers a model that stopped asking for charts reads the same as checks
    # that started refusing them.
    LOG.info(
        "routing done items=%s asked=%s prefiltered=%s unrouted=%s "
        "charts_drafted=%s charts_kept=%s "
        "total_ms=%s median_ms=%s slowest_ms=%s",
        len(spent),
        len(spent) - skipped,
        skipped,
        unrouted,
        drafted,
        kept,
        total_ms,
        sorted(spent)[len(spent) // 2] if spent else 0,
        max(spent, default=0),
    )
    if unrouted:
        # An unrouted item is one the run never decided, which is what
        # `items_routed` in the manifest already reports. This says it in the run
        # log too, with the rate that would have to change for it to fit.
        LOG.warning(
            "route stage stopped at its budget minutes=%s routed=%s unrouted=%s mean_ms=%s",
            settings.app.run.route_budget_minutes,
            len(spent),
            unrouted,
            total_ms // len(spent) if spent else 0,
        )


def _route_one(
    article: Article, summary: Summary, settings: config.Settings
) -> tuple[Route, bool]:
    """One routing decision, and whether the model was asked for it.

    The model is skipped when no enabled visual kind could survive `to_route`'s
    own checks - a chart's bars are indices into these facts and must share one
    unit, so an article whose numbers hold no unit group wide enough cannot
    produce one whatever the model answers. Measured at 21.0 s an item on
    `ubuntu-latest` (2026-08-24), asking anyway is that long spent proving a
    settled question.

    A skipped item still writes a `Route`. Silence is what turns a skip into a
    quiet descope of the feature.
    """
    visuals = settings.app.visuals
    facts = route.numeric_facts(article.text or "", limit=visuals.max_facts)
    model_id = settings.app.models.route.id
    if not route.reachable_kinds(facts, visuals=visuals):
        return (
            route.decided_without_the_model(
                summary,
                model_id=model_id,
                routed_at=assemble.utc_now(),
                facts_found=len(facts),
            ),
            False,
        )
    payload = route.build_request(
        article,
        summary,
        facts,
        model_id=model_id,
        inference=settings.app.models.inference,
        visuals=visuals,
    )
    try:
        completion = post(payload, timeout=visuals.request_timeout_minutes * 60)
    except OSError as error:
        completion = Completion(content="")
        LOG.warning("router unreachable id=%s reason=%s", article.item_id, type(error).__name__)
    return (
        route.to_route(
            article,
            summary,
            completion,
            model_id=model_id,
            routed_at=assemble.utc_now(),
            visuals=visuals,
            facts=facts,
        ),
        True,
    )


# --- validate (Row #7) --------------------------------------------------------


def stage_validate(
    *,
    settings: config.Settings,
    date: str,
    leaderboard: float,
    scorer: object,
    fetcher: Fetcher | None = None,
) -> None:
    """Score the day's own planned articles with whichever model is served.

    The corpus is the run plan, not a curated list. A hand-picked set of
    addresses decays the moment it is written - the first one this project had
    lost three of twenty within hours, and the gate correctly refused to judge on
    seventeen. The plan is regenerated per validation, so it never rots, needs no
    curation, and is the real corpus rather than a proxy for it.

    Both models read the same committed plan file, so the only thing differing
    between their two numbers is the weights.
    """
    if scorer is None:
        raise SystemExit("validation without a faithfulness scorer measures nothing")

    read_url = fetcher or live_fetcher(settings)
    plan = _load_plan(date)
    model_id = settings.app.models.summarize.id
    scores: list[float] = []

    for index, item in enumerate(plan.items, start=1):
        article, _, _ = _fetch_one(item, settings, read_url)
        if article.status is not ArticleStatus.OK:
            LOG.warning("validation article unavailable url=%s", item.canonical_url)
            continue
        summary = _summarize_one(article, settings, "0" * 64)
        if summary.status is not SummaryStatus.OK:
            LOG.warning("validation article did not summarize url=%s", item.canonical_url)
            continue
        text = article.text or ""
        hhem, _ = dual_score(
            scorer,  # type: ignore[arg-type]
            seen_text=text,
            full_text=text,
            summary=summary.summary or "",
        )
        scores.append(hhem)
        LOG.info("validation scored %s/%s hhem=%.3f", index, len(plan.items), hhem)

    result = golden.GoldenResult(
        model_id=model_id,
        leaderboard_hhem=leaderboard,
        scores=scores,
        attempted=len(plan.items),
    )
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    assemble.write_atomic(VALIDATION_ROOT / f"{model_id}.json", result.to_json())
    LOG.info(
        "validated model=%s scored=%s/%s mean_hhem=%.4f",
        model_id,
        result.articles,
        result.attempted,
        result.measured_hhem,
    )


def stage_decide(*, settings: config.Settings, date: str, commit_sha: str, runner: str) -> int:
    """Apply the Row #7 rule to whatever was measured, and record it.

    Returns non-zero on a switch. That verdict is an ESCALATE, and a green build
    would let it pass unread.
    """
    results = golden.results_in(VALIDATION_ROOT)
    if not results:
        raise SystemExit("no model was validated, so there is nothing to decide")

    incumbent_id = settings.app.models.summarize.id
    measurements = [
        validation.Measurement(
            model_id=result.model_id,
            leaderboard_hhem=result.leaderboard_hhem,
            measured_hhem=result.measured_hhem,
            articles=result.articles,
        )
        for result in results
    ]
    incumbent = next((m for m in measurements if m.model_id == incumbent_id), None)
    if incumbent is None:
        raise SystemExit(f"the configured model {incumbent_id} was never validated")
    challengers = [m for m in measurements if m.model_id != incumbent_id]

    decision = validation.decide(incumbent, challengers, evaluation=settings.app.evaluation)
    rows = validation.to_rows(
        incumbent,
        challengers,
        decision,
        measured_on=date,
        commit_sha=commit_sha,
        runner=runner,
    )
    writer.append_validation(config.REPO_ROOT / golden.ledger_relpath(date), rows)

    LOG.info("verdict=%s winner=%s", decision.verdict.value, decision.winner)
    LOG.info("%s", decision.detail)
    if decision.verdict is ValidationVerdict.SWITCH_AND_PAUSE:
        LOG.error("ESCALATE: a model switch changes a persisted contract and needs sign-off")
        return 2
    return 0


# --- assemble ----------------------------------------------------------------


class _ItemPayload(NamedTuple):
    planned: PlannedItem
    article: Article | None
    summary: Summary | None
    eval_path: Path
    route_path: Path


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
                Article.from_json(article_path.read_text(encoding="utf-8"))
                if article_exists
                else None
            ),
            summary=(
                Summary.from_json(summary_path.read_text(encoding="utf-8"))
                if summary_exists
                else None
            ),
            eval_path=items_dir / f"{item.item_id}.eval.json",
            route_path=items_dir / f"{item.item_id}.route.json",
        )


def stage_assemble(
    plan: RunPlan, *, settings: config.Settings, commit_sha: str, runner: str = "local"
) -> DigestDay:
    """Collect whatever finished, publish it, and append the ledger."""
    items_dir = _run_dir(plan.date) / "items"
    names = assemble.source_names(settings.sources)
    kinds = assemble.source_kinds(settings.sources)
    target = assemble.day_dir(PUBLIC_ROOT, plan.date)
    previous_day = _load_day(target / "digest.json")
    previous_manifest = _load_manifest(target / "run.json", day=previous_day)
    run_n = (previous_manifest.runs[-1].n + 1) if previous_manifest else 1
    run_id = f"{plan.date}-{run_n}"
    digest_items = []
    summaries: list[Summary] = []
    rows = []
    routes: list[Route] = []
    item_health_rows = [
        telemetry.classify_item(
            planned=payload.planned,
            article=payload.article,
            summary=payload.summary,
            date=plan.date,
            run_id=run_id,
        )
        for payload in _item_payloads(plan, items_dir)
    ]

    for payload in _item_payloads(plan, items_dir, require_summary=True):
        article = payload.article
        summary = payload.summary
        if article is None or summary is None:
            continue
        summaries.append(summary)
        if summary.status is not SummaryStatus.OK:
            continue

        # An item publishes with a band whether or not the faithfulness scorer
        # ran. The counterweights are free and always available, and they never
        # claim the top band on their own.
        if payload.eval_path.exists():
            row = EvalRow.from_json(payload.eval_path.read_text(encoding="utf-8"))
            rows.append(row)
            decided = score.verdict(
                row.hhem,
                unsupported_numbers=row.unsupported_numbers,
                lead_coverage=row.coverage,
                hedge_dropped=row.hedge_dropped,
                config=settings.app.evaluation,
            )
        else:
            text = summary.summary or ""
            full_text = article.text or ""
            decided = score.verdict(
                None,
                unsupported_numbers=metrics.unsupported_numbers(text, full_text),
                lead_coverage=metrics.lead_coverage(text, full_text),
                hedge_dropped=metrics.hedge_dropped(text, full_text),
                config=settings.app.evaluation,
            )
        decision = (
            Route.from_json(payload.route_path.read_text(encoding="utf-8"))
            if payload.route_path.exists()
            else None
        )
        if decision is not None:
            routes.append(decision)
        digest_items.append(
            assemble.to_digest_item(
                article=article,
                summary=summary,
                band=decided.band,
                band_reason=decided.reason,
                source_name=names.get(article.source_id, article.source_id),
                source_kind=kinds.get(article.source_id, SourceKind.REPORTING),
                run_n=1,
                route=decision,
            )
        )

    digest_items = [item.model_copy(update={"introduced_by_run": run_n}) for item in digest_items]

    generated_at = assemble.utc_now()
    day = assemble.build_day(
        plan=plan,
        items=digest_items,
        previous=previous_day,
        taxonomy=settings.taxonomy,
        run_n=run_n,
        generated_at=generated_at,
        retention_window_months=settings.app.retention.image_months,
        embeddings=assemble.build_embeddings(digest_items, Embedder(config.REPO_ROOT)),
        item_health_rows=item_health_rows,
    )
    assemble.write_atomic(target / "digest.json", day.to_json())

    site_bytes, site_files = assemble.site_size(PUBLIC_ROOT)
    manifest = assemble.build_manifest(
        plan=plan,
        day=day,
        previous=previous_manifest,
        summaries=summaries,
        models=[
            ModelUse(role=ModelRole.SUMMARIZE, model_ref=settings.app.models.summarize),
        ],
        commit_sha=commit_sha,
        runner=runner,
        started_at=plan.generated_at,
        completed_at=generated_at,
        config_digests=settings.digests,
        site_bytes=site_bytes,
        site_files=site_files,
        item_health_rows=item_health_rows,
        routes=routes,
    )
    assemble.write_atomic(target / "run.json", manifest.to_json())
    landed = writer.append(LEDGER, rows)
    published = ledger.append_published(STATE_ROOT, _published_rows(day, plan))
    item_health = ledger.append_item_health(STATE_ROOT, plan.date, item_health_rows)
    publish_telemetry.publish(
        state_root=STATE_ROOT, public_root=PUBLIC_ROOT.parent / "telemetry"
    )
    LOG.info(
        "published date=%s items=%s partial=%s eval_rows=%s addresses=%s item_health_rows=%s",
        plan.date,
        len(day.items),
        day.partial,
        landed,
        published,
        item_health,
    )
    return day


def _published_rows(day: DigestDay, plan: RunPlan) -> list[PublishedRow]:
    """What this digest actually carried, as addresses a later run can skip.

    The digest item knows the item id and the plan knows the address, so the
    two are joined here rather than widening the published payload with a hash
    no reader will ever look at. Only what this run introduced is recorded: a
    day carries yesterday's items forward, and re-recording them would move
    their published date every morning.
    """
    addresses = {item.item_id: item for item in plan.items}
    rows: list[PublishedRow] = []
    for item in day.items:
        planned = addresses.get(item.item_id)
        if planned is None:
            continue
        rows.append(
            PublishedRow(
                version=PublishedRow.schema_version(),
                url_key=planned.url_key,
                canonical_url=planned.canonical_url,
                published_on=day.date,
                item_id=item.item_id,
            )
        )
    return rows


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


# --- entry point --------------------------------------------------------------


def _plan_path(date: str) -> Path:
    return _run_dir(date) / "plan.json"


def _load_plan(date: str) -> RunPlan:
    return RunPlan.from_json(_plan_path(date).read_text(encoding="utf-8"))


def _scorer(enabled: bool) -> object | None:
    """The faithfulness scorer, or nothing at all.

    A scorer that will not load costs the run its eval rows. It must never cost
    the run its digest: `stage_assemble` already bands every item from the
    model-free counterweights when no row exists. The first real runner attempt
    died here - a transformers upgrade broke the checkpoint's own modelling code
    and all four workers exited before summarizing a single article.
    """
    if not enabled:
        LOG.warning("faithfulness scoring disabled - no eval rows will be written")
        return None
    scorer = HhemScorer()
    try:
        scorer.load()
    except Exception as error:
        LOG.error(
            "the faithfulness scorer did not load, so this run writes no eval rows: %s: %s",
            type(error).__name__,
            error,
        )
        return None
    return scorer


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idhazh", description=__doc__)
    parser.add_argument(
        "stage", choices=("plan", "work", "route", "assemble", "run", "validate", "decide")
    )
    parser.add_argument("--date", default=None, help="Defaults to today, UTC.")
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    parser.add_argument("--commit", default="0" * 40)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument(
        "--no-faithfulness",
        action="store_true",
        help="Skip the scorer. The digest still publishes; the ledger stays empty.",
    )
    parser.add_argument(
        "--visuals",
        action="store_true",
        help="Include the route stage in a full run. It needs the router model served.",
    )
    parser.add_argument(
        "--leaderboard",
        type=float,
        default=0.0,
        help="The published faithfulness score for the model being validated. A prior only.",
    )
    parser.add_argument(
        "--runner",
        default="local",
        help="Where the run happened. A laptop number is not a gate.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=None,
        help=(
            "Override each vertical's daily cap when planning. For validation only: "
            "the daily cap is how much a reader wants, not how much a measurement needs."
        ),
    )
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    logging.basicConfig(
        level=settings.app.logging.level.value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    date = args.date or _today()
    # One fetcher for the whole invocation, so `idhazh run` reads each host's
    # robots.txt once across all three stages rather than once per stage.
    read_url = live_fetcher(settings)

    if args.stage == "validate":
        stage_validate(
            settings=settings,
            date=date,
            leaderboard=args.leaderboard,
            scorer=_scorer(not args.no_faithfulness),
            fetcher=read_url,
        )
        return 0

    if args.stage == "decide":
        return stage_decide(
            settings=settings, date=date, commit_sha=args.commit, runner=args.runner
        )

    if args.stage in ("plan", "run"):
        plan = stage_plan(date, settings=settings, fetcher=read_url)
        assemble.write_atomic(_plan_path(date), plan.to_json())
        LOG.info("planned date=%s items=%s feeds=%s", date, len(plan.items), plan.feeds_read)

    if args.stage in ("work", "run"):
        stage_work(
            _load_plan(date),
            settings=settings,
            scorer=_scorer(not args.no_faithfulness),
            shard=args.shard,
            shards=args.shards,
            fetcher=read_url,
        )

    if args.stage == "route" or (args.stage == "run" and args.visuals):
        stage_route(_load_plan(date), settings=settings)

    if args.stage in ("assemble", "run"):
        stage_assemble(
            _load_plan(date), settings=settings, commit_sha=args.commit, runner=args.runner
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
