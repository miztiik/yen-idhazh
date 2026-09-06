"""The pipeline, as three stages a person can run one at a time.

Each stage takes a file and writes a file, which is the whole reason the
pipeline can be sharded across disposable machines and re-run cheaply. A stage
that only works as part of the whole is a stage nobody can debug.

    idhazh plan       read feeds, rank, record      -> run/<date>/plan.json
    idhazh work       fetch, extract, summarize, score -> run/<date>/items/*
    idhazh record     commit what one shard settled -> state/
    idhazh counters   commit what one shard's model server counted -> state/
    idhazh assemble   collect what finished        -> frontend/public/... + state/

`idhazh run` is the three in order, which is what a developer wants and what
the daily workflow calls. `record` and `counters` are not among the three: the
daily workflow runs both inside the worker job so a run that dies before it
publishes still keeps what it measured.

    idhazh backfill-vectors   re-encode closed days whose vectors are short

That last one is a repair, not a stage. Nothing schedules it.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date as date_type
from pathlib import Path
from typing import Final, NamedTuple
from urllib.error import HTTPError

from pydantic import ValidationError

from idhazh import (
    assemble,
    config,
    corpus,
    discover,
    extract,
    fetch,
    ledger,
    publish_source_health,
    publish_telemetry,
    rank,
    retention,
    source_health,
    summarize,
    tag,
    telemetry,
    visual_planner,
)
from idhazh.contracts.app_config import (
    CollectConfig,
    EvaluationConfig,
    ExtractConfig,
    InferenceConfig,
    ObservabilityConfig,
    RetentionConfig,
    RunConfig,
)
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import canonical_json, derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import (
    FeedHealthRow,
    FetchOutcome,
    RobotsOutcome,
    derive_endpoint_key,
)
from idhazh.contracts.fingerprint import FingerprintRow, PipelineInputs
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemStage
from idhazh.contracts.qualification import (
    CanaryObservation,
    CandidateIdentity,
    CorpusItem,
    GateStatus,
    ItemObservation,
    ItemScore,
    QualificationReport,
    QualificationShard,
    ScorerIdentity,
    corpus_digest,
)
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest
from idhazh.contracts.run_plan import PlannedItem, RunPlan, VerticalPlan
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind, SourceTier
from idhazh.contracts.validation_row import (
    LeaderboardProvenance,
    ValidationRow,
    ValidationVerdict,
)
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, ONNX_RELPATH, Embedder, text_for
from idhazh.evals import archive as score_archive
from idhazh.evals import evidence, golden, metrics, qualify, sampling, score, validation, writer
from idhazh.evals.hhem import (
    HHEM_REVISION,
    HHEM_SCORER_ID,
    HhemScorer,
    dual_score,
    is_pinned,
    score_over_chunks,
    weights_digest,
)
from idhazh.fingerprint import (
    LEDGER_RELPATH as FINGERPRINT_RELPATH,
)
from idhazh.fingerprint import (
    UNRECORDED_TEMPLATE,
    append_new,
    build_inputs,
    file_digest,
    host_cpu,
    runner_class,
    runtime_build,
    text_digest,
)
from idhazh.llm.server import DEFAULT_ENDPOINT, Completion, is_context_exceeded, post, props
from idhazh.render import asset_relpath, render_visual
from idhazh.render.write import assets_in_day
from idhazh.sanitize import SANITIZER_VERSION, sanitize

LOG: Final = logging.getLogger("idhazh")
#: Why a feed was not asked, in the one cell a later reader has. A rest ends on
#: its own and a retirement does not, so the two sentences are different.
RESTING_DETAIL: Final = "resting after repeated failures"
RETIRED_DETAIL: Final = "address retired after repeated 410 Gone"
#: Outcomes that never sent a request to the feed address itself: permission was
#: refused or unknown, the feed was resting, or the address was one we refuse to
#: dial. Only the rows outside this set are evidence about the feed.
_NEVER_ASKED: Final[frozenset[FetchOutcome]] = frozenset(
    {FetchOutcome.ROBOTS_DENIED, FetchOutcome.SKIPPED, FetchOutcome.BLOCKED}
)
VAR_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "run"
VALIDATION_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "validation"
QUALIFICATION_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "qualification"
#: A sibling of `VAR_ROOT` rather than a child, because the run never reads it
#: back and no downstream job downloads it. A test redirects it the same way.
EVIDENCE_ROOT: Final = config.REPO_ROOT / evidence.EVIDENCE_ROOT_RELPATH
#: The planted attacks, run live against a candidate before it is adopted.
CANARY_DIR: Final = config.REPO_ROOT / "tests" / "fixtures" / "canaries"
PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "digest"
CORPUS_ROOT: Final = config.REPO_ROOT / corpus.CORPUS_ROOT_RELPATH
STATE_ROOT: Final = config.REPO_ROOT / ledger.STATE_DIRNAME
FINGERPRINTS: Final = config.REPO_ROOT / FINGERPRINT_RELPATH


def _index_root() -> Path:
    """Where a month's search index goes, derived from the digest root it projects.

    Derived rather than a constant of its own, because a constant does not move
    when a caller moves the days. A test that redirects `PUBLIC_ROOT` at a
    temporary tree used to leave this pointing at the repository, so the suite
    rebuilt the committed shard out of fixture days - which is how the shard on
    `main` came to name one item no published day holds. `publish_telemetry` is
    passed its root the same way and for the same reason.
    """
    return PUBLIC_ROOT.parent / "assist" / "index"


def _run_dir(date: str) -> Path:
    return VAR_ROOT / date


def _evidence_dir(date: str) -> Path:
    return EVIDENCE_ROOT / date


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


def _trace_id(run_id: str, item: PlannedItem) -> str:
    """One item on one run. The work stage opens it twice and the planner opens it again."""
    return f"{run_id}-{item.item_id}"


def silent_tracer() -> telemetry.Tracer:
    """A tracer that records nothing, so no call site has to branch on a toggle.

    Built fresh rather than shared, because a tracer holds the open stack and a
    shared one would let two callers pop each other's spans.
    """
    return telemetry.Tracer(sink=telemetry.NullSink(), now=assemble.utc_now)


def trace_sink(
    settings: config.Settings, *, run_id: str, shard: int
) -> telemetry.SpanSink:
    """Where this shard's spans go: nowhere, a committed file, or a file and a host.

    A file by default and a host only when the environment names one, with its
    key pair (owner decision, 2026-08-30). No workflow sets those, so a daily
    run reaches no third party and needs no secret; a developer who wants the
    hosted view exports three variables and gets both. The host is added to the
    file and never instead of it, so the record a test reads and the record a
    host receives are the same record.

    The file is the committed trace under `state/traces/`, not a gitignored one,
    so a recent run stays openable from the repository; `retention.prune_traces`
    bounds the rolling window (CLAUDE.md section 1b, docs/concepts/telemetry.md).
    """
    if not settings.app.observability.tracing_enabled:
        return telemetry.NullSink()
    local = telemetry.FileSink(telemetry.committed_trace_path(STATE_ROOT, run_id, shard))
    host = os.environ.get("LANGFUSE_HOST", "").strip()
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not (host and public_key and secret_key):
        return local
    remote = telemetry.langfuse_sink(host=host, public_key=public_key, secret_key=secret_key)
    if remote is None:
        LOG.warning("a langfuse host is named but the package is absent; tracing to the file")
        return local
    return telemetry.FanOut((local, remote))


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
    (Rule #7).

    `tracer` is what makes the robots read visible, and it is the sub-step no
    ledger column can hold. `fetch_ms` is one number covering both reads, so the
    first item from a host with a slow robots.txt reads as a slow article and
    the next twenty from that host read as fast ones for no stated reason.
    """
    rules: dict[str, fetch.RobotsRules] = {}
    trace = tracer if tracer is not None else silent_tracer()
    agent = settings.app.extract.user_agent
    read_one = read_address if read_address is not None else _permitted_reader(settings)

    def read(url: str) -> fetch.FetchResult:
        where = fetch.origin(url)
        with trace.span(telemetry.SpanName.ROBOTS) as span:
            span.set(telemetry.AttrKey.ROBOTS_CACHED, where in rules)
            if where not in rules:
                # A host that answered "no such file" publishes no rules; a host
                # that did not answer at all stays a refusal (RFC 9309 sec 2.3.1).
                rules[where] = fetch.robots_rules(read_one(fetch.robots_url(url)))
            permission = rules[where].permits(agent, url)
            span.set(telemetry.AttrKey.ROBOTS_OUTCOME, permission.value)
        if permission is not RobotsOutcome.ALLOWED:
            return fetch.refused(permission)
        return read_one(url)

    return read


def _permitted_reader(settings: config.Settings) -> Fetcher:
    """Read one address we already have permission for. The socket edge."""

    def read(url: str) -> fetch.FetchResult:
        return fetch.fetch(url, config=settings.app.extract, permission=RobotsOutcome.ALLOWED)

    return read


# --- plan -------------------------------------------------------------------


def stage_plan(
    date: str,
    *,
    settings: config.Settings,
    fetcher: Fetcher | None = None,
    now: Clock | None = None,
    execution: int | None = None,
    state_dir: Path | None = None,
    cap: int | None = None,
) -> RunPlan:
    """Read every live feed, rank the pool, and write down what it saw. No model.

    Four committed ledgers bound the day. The seen store gives an article whose
    feed carried no date a real age - first sight is the only honest one there
    is. The published store is what stops a repeat, which a freshness rule
    cannot do on its own: an article published at 23:00 is seven hours old at
    06:00 the next morning. The item-health store stops the *other* repeat: an
    address that failed today behind a paywall or a 404 is not planned again
    today, because that answer will not change before tomorrow. The feed-health
    store records what every feed did, so a source that has gone quiet can be
    quarantined from evidence instead of from somebody's memory. Quarantine only
    ever holds a feed back for a few runs; it never edits `config/sources.json`,
    because retiring a source is a person's decision.

    Nothing is dropped for being old. `run.safety_ceiling_per_run` is a crash
    guard against a mis-parsed feed, not a reading budget.

    The item-health store answers a second question as well: how much of today
    each feed has already put in front of a reader. `collect.max_per_source`
    bounds a feed inside one desk in one run, and a feed sits on one desk, so
    its ceiling for a whole day is that count times the runs the day had - a
    fixed number whose share of the day moves with the day's size.
    `collect.max_source_share_per_day` is the share.

    `cap` takes the best `cap` stories of each vertical and is for a validation
    run that must not plan a whole day. It is a different knob from the crash
    guard: it works per vertical, before the day is deduplicated, and a run that
    does not ask for it plans exactly what it planned before.
    """
    read_url = fetcher or live_fetcher(settings)
    clock = now or assemble.utc_now
    state = state_dir if state_dir is not None else STATE_ROOT
    collect = settings.app.collect
    generated_at = clock()
    # Named by the execution that made it, not by a count of what is committed.
    # See `_next_run_n` for what the count could not do.
    run_id = _run_id(date, execution)

    candidates: list[discover.Candidate] = []
    health: list[FeedHealthRow] = []
    history = ledger.load_health(state, today=date, within_days=ledger.HEALTH_WINDOW_DAYS)
    asleep = discover.resting(history, after_failures=collect.availability_strikes_before_rest)
    # Retirement outranks rest, so it is decided first and from its own evidence:
    # five distinct runs reading `410 Gone` from one address. The ledger is read
    # before the row is filed and the two are joined, so the run that decides is
    # also the first run that does not ask.
    endpoints = source_health.endpoint_records(history)
    gone = {row.endpoint_key for row in ledger.load_retirements(state)}
    filed = source_health.retirements(
        settings.sources.feeds,
        records=endpoints,
        already=gone,
        after_runs=collect.feed_http_410_runs_before_retirement,
        date=date,
        run_id=run_id,
    )
    if filed:
        ledger.append_retirements(state, filed)
        gone |= {row.endpoint_key for row in filed}
        for row in filed:
            LOG.warning(
                "feed endpoint retired id=%s cause=%s runs=%s file=%s",
                row.feed_id,
                row.cause.value,
                len(row.evidence_run_ids),
                ledger.feed_retirements_relpath(),
            )
    retired = source_health.retired(settings.sources.feeds, gone)
    read = failed = skipped = 0
    for feed in settings.sources.feeds:
        if feed.id in retired:
            skipped += 1
            LOG.info("feed endpoint retired, not asked id=%s", feed.id)
            health.append(_rest_row(feed, at=generated_at, run_id=run_id, why=RETIRED_DETAIL))
            continue
        if feed.id in asleep:
            skipped += 1
            LOG.info("feed resting id=%s", feed.id)
            health.append(_rest_row(feed, at=generated_at, run_id=run_id, why=RESTING_DETAIL))
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
    settled_today = frozenset(
        ledger.load_settled_failures(state, date, codes=collect.settled_failure_codes)
    )
    LOG.info(
        "addresses this run will not plan published=%s settled_today=%s",
        len(already_published),
        len(settled_today),
    )

    # The bonus is decided on the feed title, because that is all a plan has: the
    # page has not been fetched yet. An article whose body names an entity its
    # title does not still earns the published tag at Extract - the tag says what
    # the item is about, the bonus says what we were already watching for.
    entity_terms = settings.watchlist.entity_terms()
    watchlist_keys = frozenset(
        candidate.url_key for candidate in candidates if tag.tags(entity_terms, candidate.title)
    )
    LOG.info(
        "watchlist matched candidates=%s of %s entities=%s",
        len(watchlist_keys),
        len(candidates),
        len(entity_terms),
    )
    # A theme is read from the headline for the same reason, and only the lenses
    # config gives a weight to are asked. One story takes the largest weight it
    # earned: two themes in one headline is not twice the story.
    lens_weights = settings.taxonomy.lens_weights()
    lens_terms = settings.taxonomy.lens_terms()
    lens_bonuses = {
        candidate.url_key: bonus
        for candidate in candidates
        if (
            bonus := max(
                (
                    lens_weights[name]
                    for name in tag.tags(
                        {name: lens_terms[name] for name in lens_weights}, candidate.title
                    )
                ),
                default=0.0,
            )
        )
    }
    LOG.info(
        "themes matched candidates=%s of %s lenses=%s",
        len(lens_bonuses),
        len(candidates),
        sorted(lens_weights),
    )
    day_carried = ledger.load_source_counts(state, date)
    # A feed that has published badly over the trailing window - failed reads, or
    # reads that parsed to nothing - scores below a dependable feed of the same
    # tier. The factor is built once here off the committed health record and read
    # inside rank.authority; a feed with no evidence in the window reads 1.0.
    reliability_by_feed = ledger.reliability(
        state,
        today=date,
        within_days=collect.reliability_window_days,
        floor=collect.reliability_floor,
    )
    # The day's own encoder, built once and loaded only if the duplicate pass
    # finds work. Each story's lead is joined by address so the pass reads the
    # same headline-and-lead the design embeds; the first non-empty lead wins,
    # because feeds carrying one story carry one story's lead.
    embedder = Embedder(config.REPO_ROOT, settings.app.assist)
    leads: dict[str, str] = {}
    for candidate in candidates:
        if candidate.lead is not None and candidate.url_key not in leads:
            leads[candidate.url_key] = candidate.lead
    verticals, items = _plan_desks(
        settings,
        candidates,
        now=generated_at,
        first_seen=first_seen,
        already_published=already_published,
        settled_today=settled_today,
        watchlist_keys=watchlist_keys,
        front_page_keys=frozenset(front_page),
        lens_bonuses=lens_bonuses,
        cap=cap,
        retired_keys=gone,
        endpoints=endpoints,
        reliability=reliability_by_feed,
    )

    items = _dedupe_planned_items(items)
    items = _record_plan_duplicates(items, embedder=embedder, leads=leads, collect=collect)
    items = _within_ceiling(items, ceiling=settings.app.run.safety_ceiling_per_run)

    # How much of the day one feed may hold is a share, and a share needs the
    # day's size. The day is what earlier runs published plus what this run is
    # about to plan, and the second half is only knowable once the desks have
    # been planned - so they are planned once to size the day, and again only
    # when the ceiling that size gives can actually bind on somebody.
    per_source = rank.day_source_ceiling(
        collect.max_source_share_per_day,
        sum(day_carried.values()) + len(items),
        max_per_source=collect.max_per_source,
    )
    crowding = sorted(
        source_id
        for source_id, held in day_carried.items()
        if per_source - held < collect.max_per_source
    )
    if crowding:
        LOG.info(
            "day source ceiling binds ceiling=%s carried=%s planning=%s feeds=%s",
            per_source,
            sum(day_carried.values()),
            len(items),
            crowding,
        )
        verticals, capped = _plan_desks(
            settings,
            candidates,
            now=generated_at,
            first_seen=first_seen,
            already_published=already_published,
            settled_today=settled_today,
            watchlist_keys=watchlist_keys,
            front_page_keys=frozenset(front_page),
            lens_bonuses=lens_bonuses,
            cap=cap,
            retired_keys=gone,
            endpoints=endpoints,
            day_ceiling=rank.DayCeiling(per_source=per_source, carried=dict(day_carried)),
            reliability=reliability_by_feed,
        )
        capped = _dedupe_planned_items(capped)
        capped = _record_plan_duplicates(capped, embedder=embedder, leads=leads, collect=collect)
        capped = _within_ceiling(capped, ceiling=settings.app.run.safety_ceiling_per_run)
        if len(capped) < len(items):
            LOG.warning(
                "day source ceiling cost the day a story short=%s planned=%s ceiling=%s",
                len(items) - len(capped),
                len(items),
                per_source,
            )
        items = capped

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


def _plan_desks(
    settings: config.Settings,
    candidates: list[discover.Candidate],
    *,
    now: str,
    first_seen: dict[str, str],
    already_published: frozenset[str],
    settled_today: frozenset[str],
    watchlist_keys: frozenset[str],
    front_page_keys: frozenset[str],
    lens_bonuses: dict[str, float],
    cap: int | None,
    retired_keys: set[str],
    endpoints: dict[str, source_health.EndpointRecord],
    day_ceiling: rank.DayCeiling | None = None,
    reliability: dict[str, float] | None = None,
) -> tuple[list[VerticalPlan], list[PlannedItem]]:
    """Rank every desk once and return what they offered, desk by desk.

    Each desk is planned on its own: a vertical's candidates never compete with
    another's, which is what stops a busy desk emptying a quiet one. What comes
    back is still per-desk, so the caller deduplicates the day and applies the
    run's own ceiling.

    `day_ceiling` is the one limit that crosses a desk boundary, so it is the
    one thing this loop carries forward: each desk's take is added to the count
    before the next desk is planned. A feed sits on one desk, so in practice
    only that desk ever sees the count move - but a day ceiling that only
    counted one desk would be a per-desk rule wearing a day's name.
    """
    summaries: list[VerticalPlan] = []
    items: list[PlannedItem] = []
    for vertical in settings.taxonomy.verticals:
        askable = source_health.eligible(
            settings.sources.feeds,
            vertical.id,
            retired_keys=retired_keys,
            records=endpoints,
        )
        summary, planned = rank.plan_vertical(
            vertical,
            [c for c in candidates if c.vertical == vertical.id],
            config=settings.app.collect,
            eligible_feeds=len(askable),
            now=now,
            first_seen=first_seen,
            already_published=already_published,
            settled_today=settled_today,
            watchlist_keys=watchlist_keys,
            front_page_keys=front_page_keys,
            lens_bonuses=lens_bonuses,
            day_ceiling=day_ceiling,
            reliability=reliability,
        )
        summaries.append(summary)
        if cap is not None and len(planned) > cap:
            LOG.info("cap applied vertical=%s planned=%s cap=%s", vertical.id, len(planned), cap)
            planned = planned[:cap]
        if day_ceiling is not None:
            for item in planned:
                day_ceiling.record(item.source_id)
        items.extend(planned)
    return summaries, items


def _rest_row(feed: FeedDef, *, at: str, run_id: str, why: str) -> FeedHealthRow:
    """The row a feed we chose not to ask gets. A record, not a measurement.

    Written rather than omitted so a rest can end: a run that left no trace
    would leave the old failures as the newest thing on record forever, and the
    feed would never be tried again. A retired address gets one for a different
    reason - the ledger has to stay one row per feed per run, or the console's
    denominator counts a desk it never asked.

    `why` is the difference between the two, because a rest lifts itself and a
    retirement does not.
    """
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=run_id,
        date=at[:10],
        feed_id=feed.id,
        checked_at=at,
        outcome=FetchOutcome.SKIPPED,
        items=0,
        detail=why,
        endpoint_key=derive_endpoint_key(feed.url),
        target_attempted=False,
    )


def _health_row(
    feed: FeedDef,
    result: fetch.FetchResult,
    *,
    found: int,
    at: str,
    run_id: str,
) -> FeedHealthRow:
    """This run's verdict on one feed, and on the address it was configured with.

    `detail` is our own sentence about the failure - a status name or an
    exception class - and never the response body. A feed is a stranger's text
    and this row lands on a published page (Rule #11).

    `endpoint_key` is what makes a later retirement possible at all: `feed_id`
    names a line of curated config, so an address that changed and an address
    that died read identically without it.

    `target_attempted` separates evidence about the feed from evidence about
    permission. A robots refusal, a rest and an address we refused to dial each
    left the feed itself un-asked, and only the rows that did ask say anything
    about whether it still works.
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
        endpoint_key=derive_endpoint_key(feed.url),
        robots_outcome=result.robots,
        target_attempted=result.outcome not in _NEVER_ASKED,
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
            first_seen_at=at,
            first_seen_run=run_id,
        )
    known.update({url_key: row.first_seen_at for url_key, row in fresh.items()})
    return [fresh[url_key] for url_key in sorted(fresh)]


def _within_ceiling(items: list[PlannedItem], *, ceiling: int) -> list[PlannedItem]:
    """What sizes a run. Measured 2026-08-25 and since, it fires on every one.

    It drops the lowest-scoring stories across every vertical rather than
    truncating the list, so a mis-parsed feed costs the weakest items and not
    whichever vertical happened to sort last.

    It was written as a crash guard and supply overtook it: `items_planned` has
    equalled the ceiling on every run since, first at 200 and now at 160. It is
    the cap whatever it is called, and
    `docs/architecture/sources/freshness.md` says so rather than leaving the
    name to imply otherwise.
    """
    if len(items) <= ceiling:
        return items
    ranked = sorted(items, key=lambda item: (-item.rank_score, item.item_id))[:ceiling]
    keep = {item.item_id for item in ranked}
    LOG.warning("safety ceiling reached planned=%s ceiling=%s", len(items), ceiling)
    return [item for item in items if item.item_id in keep]


def _record_plan_duplicates(
    items: list[PlannedItem],
    *,
    embedder: Embedder,
    leads: Mapping[str, str],
    collect: CollectConfig,
) -> list[PlannedItem]:
    """Write down the day's same-story repeats, and cut them only when enforcing.

    Record-only by default (`collect.dedup_enforce` is false): the pass computes
    what it WOULD collapse - a story an earlier, stronger telling already
    covers - logs each one against what it matched, and removes nothing. Turning
    the flag on cuts the weaker telling before the safety ceiling and changes
    nothing else, so enforcing is a config edit rather than a code change.

    A record pass never stops a run (`degrade, do not fail`): an encoder that
    will not load costs the run its duplicate record, never its plan.
    """
    if len(items) < 2 or not embedder.available:
        return items
    try:
        embedder.load()
        ids: list[str] = []
        texts: list[str] = []
        for item in items:
            text = rank.dedup_text(item.title, leads.get(item.url_key))
            if text is None:
                continue
            ids.append(item.item_id)
            texts.append(text)
        if len(ids) < 2:
            return items
        vectors = dict(zip(ids, embedder.encode(texts), strict=True))
        findings = rank.duplicates_within_plan(
            items, vectors, similarity_min=collect.dedup_similarity_min
        )
    except Exception as error:  # degrade, do not fail: a record pass never stops a run
        LOG.warning("plan dedup skipped reason=%s: %s", type(error).__name__, error)
        return items
    for finding in findings:
        LOG.info(
            "plan duplicate would-collapse item=%s vertical=%s source=%s of=%s "
            "matched_source=%s similarity=%.4f enforce=%s",
            finding.item.item_id,
            finding.item.vertical,
            finding.item.source_id,
            finding.duplicate_of.item_id,
            finding.duplicate_of.source_id,
            finding.similarity,
            collect.dedup_enforce,
        )
    LOG.info(
        "plan duplicates recorded count=%s enforce=%s",
        len(findings),
        collect.dedup_enforce,
    )
    if not collect.dedup_enforce:
        return items
    cut = {finding.item.item_id for finding in findings}
    return [item for item in items if item.item_id not in cut]


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
    """A run id for a machine with no CI run to name it. Local and test use only.

    Reading the count off the last committed manifest cannot make an identifier
    two executions are unable to share, and on 2026-08-29 two of them did share
    one. `actions/checkout` pins a job to the commit its run was triggered at, so
    the manifest a second run reads is the manifest as it stood before the first
    run published - and both count the same number. Runs 33270983446 (dispatched
    19:29) and 33274853468 (scheduled 20:58) both derived `2026-08-29-3`, and the
    ledgers keyed on it then held six counter rows for four shards.

    CI passes `--execution ${{ github.run_id }}` instead. GitHub allocates that
    number, it is unique across every run of every workflow in the repository,
    and nothing a second execution can read will reproduce it. This is what is
    left: a developer machine has no such number, and a laptop cannot race
    itself.
    """
    target = assemble.day_dir(PUBLIC_ROOT, date)
    manifest = _load_manifest(target / "run.json", day=_load_day(target / "digest.json"))
    return manifest.runs[-1].n + 1 if manifest else 1


def _run_id(date: str, execution: int | None) -> str:
    """The run address every ledger row of this execution is filed under.

    Written once because two stages now need it - the plan, which opens the run,
    and the cleanup, which closes it - and a second spelling of it would file
    one run's rows under two names.
    """
    return f"{date}-{execution if execution is not None else _next_run_n(date)}"


# --- work -------------------------------------------------------------------


def shard_count(items: int, *, run: RunConfig) -> int:
    """How many worker jobs a day of `items` earns.

    `run.shard_size` is what one worker is sized to carry, so a day that needs
    fewer workers gets fewer. Every extra job restores the weights again, and
    that restore is the largest fixed cost in the pipeline (Rule #2). The count
    never passes `run.max_parallel` and never falls below one, so an empty day
    still runs a worker that exits cleanly rather than an empty matrix.

    This is what a run derives for itself. An operator dispatching `digest.yml`
    names a count instead, and may name a larger one than this will ever return.

    The bound this has to clear is the worst case, not the day in hand: at
    `run.safety_ceiling_per_run` items the shard each worker draws must still
    finish inside the `work` job's timeout.
    """
    return max(1, min(-(-items // run.shard_size), run.max_parallel))


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
    source_text: str
    fetch_ms: int
    extract_ms: int
    started: float
    original_index: int


def _summarize_band_sort_key(work: _FetchedWorkItem, settings: config.Settings) -> tuple[int, int]:
    band = settings.app.summarize.band_for(work.article.band_source_words)
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
    shard_started = time.monotonic()
    tracing = settings.app.observability.tracing_enabled
    collector = telemetry.CollectingSink()
    base_sink = trace_sink(settings, run_id=plan.run_id, shard=shard)
    tracer = telemetry.Tracer(
        sink=telemetry.FanOut((base_sink, collector)) if tracing else base_sink,
        now=assemble.utc_now,
    )
    read_url = fetcher or live_fetcher(settings, tracer=tracer)
    inference = settings.app.models.inference
    model = settings.app.models.summarize
    observed = props(model_endpoint, timeout=inference.request_timeout_minutes * 60)
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=runtime_build(),
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        prompt=summarize.prompt_inputs(settings.app.summarize),
        output_schema=summarize.output_schema_text(settings.app.summarize, settings.app.evaluation),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )
    fingerprint = inputs.fingerprint()
    scorer_version = metrics.scorer_version(
        scorer_id=HHEM_SCORER_ID,
        scorer_revision=HHEM_REVISION,
        weights_sha256=weights_digest(scorer) if isinstance(scorer, HhemScorer) else "0" * 64,
        evaluation=settings.app.evaluation,
    )

    items_dir = _run_dir(plan.date) / "items"
    _write_stamp(items_dir, inputs=inputs, run_id=plan.run_id)
    mine = shard_of(plan, shard=shard, shards=shards)
    LOG.info(
        "working shard=%s/%s items=%s fingerprint=%s",
        shard,
        shards,
        len(mine),
        fingerprint[:12],
    )
    ready: list[_FetchedWorkItem] = []
    for original_index, item in enumerate(mine):
        started = time.monotonic()
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.ITEM) as span,
        ):
            telemetry.item_attributes(span, item, run_id=plan.run_id, shard=shard)
            article, source_text, fetch_ms, extract_ms = _fetch_one(
                item, settings, read_url, tracer
            )
        assemble.write_atomic(items_dir / f"{item.item_id}.article.json", article.to_json())
        if article.status is not ArticleStatus.OK:
            LOG.info("item degraded id=%s reason=%s", item.item_id, article.failure_detail)
            continue
        ready.append(
            _FetchedWorkItem(
                item=item,
                article=article,
                source_text=source_text,
                fetch_ms=fetch_ms,
                extract_ms=extract_ms,
                started=started,
                original_index=original_index,
            )
        )

    for work in sorted(ready, key=lambda candidate: _summarize_band_sort_key(candidate, settings)):
        item = work.item
        article = work.article
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.ITEM) as item_span,
        ):
            telemetry.item_attributes(item_span, item, run_id=plan.run_id, shard=shard)
            model_started = time.monotonic()
            summary = _summarize_one(
                article,
                settings,
                fingerprint,
                endpoint=model_endpoint,
                run_id=plan.run_id,
                tracer=tracer,
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
            # The article before the cap, so hhem_full answers a different question
            # from hhem. Falls back to the cut text when nothing was cut away.
            whole = work.source_text or seen
            with tracer.span(telemetry.SpanName.SCORE) as score_span:
                score_started = time.monotonic()
                hhem, hhem_full = dual_score(
                    scorer,  # type: ignore[arg-type]
                    seen_text=seen,
                    full_text=whole,
                    summary=summary.summary or "",
                    evaluation=settings.app.evaluation,
                )
                score_ms = int((time.monotonic() - score_started) * 1000)
                row = score.to_eval_row(
                    item=item,
                    article=article,
                    summary=summary,
                    full_text=whole,
                    premise=seen,
                    hhem=hhem,
                    hhem_full=hhem_full,
                    config=settings.app.evaluation,
                    date=plan.date,
                    run_id=plan.run_id,
                    scorer_version=scorer_version,
                    scored_at=assemble.utc_now(),
                )
                row = row.model_copy(update={"score_ms": score_ms})
                score_span.set(telemetry.AttrKey.BAND, row.band.value)
            assemble.write_atomic(items_dir / f"{item.item_id}.eval.json", row.to_json())
            _write_evidence(row, premise=seen, summary=summary.summary or "")
            LOG.info(
                "item scored id=%s band=%s fetch=%sms extract=%sms model=%sms score=%sms",
                item.item_id,
                row.band.value,
                work.fetch_ms,
                work.extract_ms,
                summarize_ms,
                score_ms,
            )
    tracer.flush()
    if tracing:
        # Fed by every span (the CollectingSink saw them all), reconciled to the
        # shard's own monotonic wall clock so the item spans plus the residual it
        # leaves add up to it - the invariant roll_up_spans enforces.
        rows = telemetry.roll_up_spans(
            collector.spans(),
            date=plan.date,
            run_id=plan.run_id,
            shard=shard,
            wall_clock_ms=int((time.monotonic() - shard_started) * 1000),
        )
        landed = ledger.append_span_rollup(STATE_ROOT, plan.date, rows)
        LOG.info("rolled up spans shard=%s span_rows=%s", shard, landed)


def _write_evidence(row: EvalRow, *, premise: str, summary: str) -> Path:
    """Leave the two texts this row was judged on where a person can read them.

    Outside `items/` on purpose. That directory is downloaded whole by the visual
    planner and by assemble and kept for a day; this one is read by nobody in the
    run, is never committed, and needs to outlive the day so a labeller has time
    to work (`docs/how-to/label-the-faithfulness-queue.md`).
    """
    item = evidence.of(row, premise=premise, summary=summary)
    path = evidence.path_for(_evidence_dir(row.date), item)
    assemble.write_atomic(path, item.to_json())
    return path


def _write_stamp(items_dir: Path, *, inputs: PipelineInputs, run_id: str) -> FingerprintRow:
    """Leave the expansion of this run's stamp beside the items it produced.

    The work stage is the only one that can observe these inputs, and its
    checkout is thrown away when the shard ends - the artifact it uploads is
    this directory. So the stamp travels as a payload and `stage_assemble`,
    which owns every committed ledger, is what appends it (section 1a).

    Named by the stamp, so eight shards observing one configuration leave one
    file rather than eight that have to be reconciled.
    """
    row = FingerprintRow(
        version=FingerprintRow.schema_version(),
        pipeline_fingerprint=inputs.fingerprint(),
        first_seen_run=run_id,
        first_seen_at=assemble.utc_now(),
        inputs=inputs,
        host_cpu=host_cpu(),
    )
    assemble.write_atomic(items_dir / f"{row.pipeline_fingerprint}.fingerprint.json", row.to_json())
    return row


def _stamps(items_dir: Path) -> list[FingerprintRow]:
    """Every stamp the shards left behind, in a stable order."""
    return [
        FingerprintRow.read(path)
        for path in sorted(items_dir.glob("*.fingerprint.json"))
    ]


def _fetch_one(
    item: PlannedItem,
    settings: config.Settings,
    read_url: Fetcher,
    tracer: telemetry.Tracer | None = None,
) -> tuple[Article, str, int, int]:
    """The article, the body it was cut from, and how long each step took.

    The timings are separated because a slow item is either a slow host or a
    slow extractor, and only one of those is ours to fix. The untruncated body
    travels beside the payload rather than inside it: the scorer needs it, and
    nothing persists it (Rule #1).

    The two spans carry the same split and one thing the columns do not: the
    tagger nests inside the extract span, so a taxonomy that grew a hundred
    patterns shows up as its own step rather than as the extractor getting
    slower.
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
    return article, source_text, fetch_ms, int((time.monotonic() - started) * 1000)


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


def _summarize_one(
    article: Article,
    settings: config.Settings,
    fingerprint: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    run_id: str | None = None,
    tracer: telemetry.Tracer | None = None,
) -> Summary:
    """One article becomes one summary, in three steps a single column hides.

    `summarize_ms` covers all three. Rendering the prompt builds a JSON schema
    from a Pydantic model; parsing the reply validates it back and then runs the
    verbatim check over the whole source, which is the longest string comparison
    in the pipeline. So an item that got slow is either the model, our schema
    work or our own checking, and until these spans existed the three were one
    number.
    """
    trace = tracer if tracer is not None else silent_tracer()
    inference = settings.app.models.inference
    model_id = settings.app.models.summarize.id
    with trace.span(telemetry.SpanName.SUMMARIZE) as stage_span:
        stage_span.set(telemetry.AttrKey.MODEL_ID, model_id)
        with trace.span(telemetry.SpanName.RENDER_PROMPT) as span:
            payload = summarize.build_request(
                article,
                model_id=model_id,
                inference=inference,
                prompt_config=settings.app.summarize,
                evaluation=settings.app.evaluation,
            )
            rendered = canonical_json(payload)
            prompt_digest = text_digest(rendered)
            span.set(telemetry.AttrKey.PROMPT_DIGEST, prompt_digest)
            span.set(telemetry.AttrKey.PROMPT_CHARS, len(rendered))
        completion: Completion | None
        no_reply = FailureCode.MODEL_UNREACHABLE
        with trace.generation() as span:
            span.set(telemetry.AttrKey.MODEL_ID, model_id)
            span.set(telemetry.AttrKey.PROMPT_DIGEST, prompt_digest)
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
        with trace.span(telemetry.SpanName.PARSE_REPLY) as span:
            summary = summarize.to_summary(
                article,
                completion,
                model_id=model_id,
                pipeline_fingerprint=fingerprint,
                generated_at=assemble.utc_now(),
                prompt_config=settings.app.summarize,
                evaluation=settings.app.evaluation,
                no_reply=no_reply,
            )
            telemetry.summary_attributes(span, summary)
        telemetry.summary_attributes(stage_span, summary)
    return summary


# --- visual planner ----------------------------------------------------------


class _PlannableItem(NamedTuple):
    item: PlannedItem
    article_path: Path
    summary: Summary


def already_published(date: str) -> frozenset[str]:
    """The item ids the day's committed digest already carries.

    `assemble.build_day` keeps an already-published item and discards the new
    run's copy of it, because the reading order is part of what a shared link
    shows. So a later run's visual decision for one of those items can never
    reach a reader: it is computed, written, read back, and thrown away.

    A day runs five times. Without this the second run spends its whole budget
    re-deciding the first run's items at 20 to 40 measured seconds each, and the
    items it actually introduced queue behind them.
    """
    day = _load_day(assemble.day_dir(PUBLIC_ROOT, date) / "digest.json")
    return frozenset(item.item_id for item in day.items) if day else frozenset()


def plannable_items(
    plan: RunPlan, items_dir: Path, *, published: frozenset[str]
) -> list[_PlannableItem]:
    """The items this run could still decide, best story first.

    Rank order, not plan order. The plan is vertical-major, so stopping part-way
    down it would cost whole verticals their pictures while the weakest story in
    the first vertical kept one. This is the rule the safety ceiling already
    follows: drop the weakest stories across every vertical, never a suffix.

    The article stays on disk until the item is actually decided. Building this
    list is what lets the stage know its own denominator before it spends
    anything on the first item.
    """
    plannable: list[_PlannableItem] = []
    for item in plan.items:
        if item.item_id in published:
            continue
        article_path = items_dir / f"{item.item_id}.article.json"
        summary_path = items_dir / f"{item.item_id}.summary.json"
        if not (article_path.exists() and summary_path.exists()):
            continue
        summary = Summary.read(summary_path)
        if summary.status is not SummaryStatus.OK:
            continue
        plannable.append(_PlannableItem(item, article_path, summary))
    plannable.sort(key=lambda entry: (-entry.item.rank_score, entry.item.item_id))
    return plannable


def stage_visual_planner(
    plan: RunPlan,
    *,
    settings: config.Settings,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Decide and draw the visuals, one item at a time.

    A separate stage from `work` because it runs a different, smaller model, and
    one llama-server serves one set of weights. Splitting it also means a run
    that never starts a planner still publishes - every item simply carries no
    picture, which is already the common and correct answer.

    **The stage stops itself at `run.visual_planner_budget_minutes`.** It used to run
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
    tracer = telemetry.Tracer(
        sink=trace_sink(settings, run_id=plan.run_id, shard=0),
        now=assemble.utc_now,
    )
    spent: list[int] = []
    skipped = 0
    drafted = 0
    kept = 0
    undecided = 0

    published = already_published(plan.date)
    plannable = plannable_items(plan, items_dir, published=published)
    budget_ms = settings.app.run.visual_planner_budget_minutes * 60_000
    stage_started = clock()
    LOG.info(
        "planning start items=%s already_published=%s budget_minutes=%s",
        len(plannable),
        len(published),
        settings.app.run.visual_planner_budget_minutes,
    )

    for index, entry in enumerate(plannable):
        if (clock() - stage_started) * 1000 >= budget_ms:
            undecided = len(plannable) - index
            break
        item, summary = entry.item, entry.summary
        article = Article.read(entry.article_path)

        started = clock()
        with (
            tracer.trace(_trace_id(plan.run_id, item)),
            tracer.span(telemetry.SpanName.VISUAL_PLANNER) as span,
        ):
            telemetry.item_attributes(span, item, run_id=plan.run_id, shard=0)
            decision, asked = _plan_one_visual(article, summary, settings)
            if not asked:
                skipped += 1
            if decision.drafted_chart:
                drafted += 1
            if decision.kind is not VisualKind.NONE:
                decision = render_visual(
                    decision,
                    public_root=PUBLIC_ROOT.parent,
                    relpath=asset_relpath(plan.date, item.item_id),
                )
            if decision.kind is VisualKind.CHART:
                kept += 1
            span.set(telemetry.AttrKey.MODEL_ASKED, asked)
            span.set(telemetry.AttrKey.DRAFTED_CHART, decision.drafted_chart)
            span.set(telemetry.AttrKey.VISUAL_KIND, decision.kind.value)
            span.set(telemetry.AttrKey.VISUAL_STATE, decision.visual_state.value)
        decision_ms = int((clock() - started) * 1000)
        spent.append(decision_ms)
        decision = decision.model_copy(update={"decision_ms": decision_ms})
        assemble.write_atomic(items_dir / f"{item.item_id}{PAYLOAD_SUFFIX}", decision.to_json())
        LOG.info(
            "item decided id=%s kind=%s state=%s asked=%s decision_ms=%s",
            item.item_id,
            decision.kind.value,
            decision.visual_state.value,
            asked,
            decision_ms,
        )

    # The job's own wall-clock is in the run log; this is what the stage inside
    # it spent. The gap between the two is the fixed cost - checkout, weights,
    # install, model start - and separating them is the whole point of the
    # measurement (Rule #10).
    tracer.flush()
    total_ms = sum(spent)
    # `drafted` minus `kept` is what the post-model checks refused. Without both
    # numbers a model that stopped asking for charts reads the same as checks
    # that started refusing them.
    LOG.info(
        "planning done items=%s asked=%s prefiltered=%s undecided=%s "
        "charts_drafted=%s charts_kept=%s "
        "total_ms=%s median_ms=%s slowest_ms=%s",
        len(spent),
        len(spent) - skipped,
        skipped,
        undecided,
        drafted,
        kept,
        total_ms,
        sorted(spent)[len(spent) // 2] if spent else 0,
        max(spent, default=0),
    )
    if undecided:
        # An undecided item is one the run never decided, which is what
        # `items_routed` in the manifest already reports. This says it in the run
        # log too, with the rate that would have to change for it to fit.
        LOG.warning(
            "visual planner stopped at its budget minutes=%s decided=%s undecided=%s mean_ms=%s",
            settings.app.run.visual_planner_budget_minutes,
            len(spent),
            undecided,
            total_ms // len(spent) if spent else 0,
        )


def _plan_one_visual(
    article: Article,
    summary: Summary,
    settings: config.Settings,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
) -> tuple[VisualDecision, bool]:
    """One visual decision, and whether the model was asked for it.

    The model is skipped when no enabled visual kind could survive `to_decision`'s
    own checks - a chart's bars are indices into these facts and must share one
    unit, so an article whose numbers hold no unit group wide enough cannot
    produce one whatever the model answers. Measured at 21.0 s an item on
    `ubuntu-latest` (2026-08-24), asking anyway is that long spent proving a
    settled question.

    A skipped item still writes a `VisualDecision`. Silence is what turns a skip into a
    quiet descope of the feature. So does an item the model never answered for,
    and the two ways it can go unanswered are logged apart: a server that
    refused the prompt for length is running, and a run log that calls it
    unreachable sends whoever reads it to look for a process that never died.
    """
    visuals = settings.app.visuals
    facts = visual_planner.numeric_facts(article.text or "", limit=visuals.max_facts)
    model_id = settings.app.models.visual_planner.id
    if not visual_planner.reachable_kinds(facts, visuals=visuals):
        return (
            visual_planner.decided_without_the_model(
                summary,
                model_id=model_id,
                decided_at=assemble.utc_now(),
                facts_found=len(facts),
            ),
            False,
        )
    payload = visual_planner.build_request(
        article,
        summary,
        facts,
        model_id=model_id,
        inference=settings.app.models.inference,
        visuals=visuals,
    )
    completion: Completion
    cause = "visual planner unreachable"
    try:
        completion = post(payload, endpoint=endpoint, timeout=visuals.request_timeout_minutes * 60)
    except HTTPError as error:
        # Before OSError, which HTTPError subclasses. A server that answered is
        # not an unreachable one, and the body is the only place it says why it
        # refused. It is a stream, so read it once.
        completion = Completion(content="")
        with error:
            if is_context_exceeded(error.read().decode("utf-8", errors="replace")):
                cause = "visual planner prompt did not fit the context window"
        LOG.warning("%s id=%s reason=%s", cause, article.item_id, type(error).__name__)
    except OSError as error:
        completion = Completion(content="")
        LOG.warning("%s id=%s reason=%s", cause, article.item_id, type(error).__name__)
    return (
        visual_planner.to_decision(
            article,
            summary,
            completion,
            model_id=model_id,
            decided_at=assemble.utc_now(),
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
        article, _, _, _ = _fetch_one(item, settings, read_url)
        if article.status is not ArticleStatus.OK:
            LOG.warning("validation article unavailable url=%s", item.canonical_url)
            continue
        summary = _summarize_one(article, settings, "0" * 64)
        if summary.status is not SummaryStatus.OK:
            LOG.warning("validation article did not summarize url=%s", item.canonical_url)
            continue
        text = article.text or ""
        # One score, asked for as one score. Validation compares against a
        # leaderboard number and has no use for a truncation gap.
        hhem = score_over_chunks(
            scorer,  # type: ignore[arg-type]
            text,
            summary.summary or "",
            evaluation=settings.app.evaluation,
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


# --- qualify (Row #10) --------------------------------------------------------


def _candidate_identity(settings: config.Settings, args: argparse.Namespace) -> CandidateIdentity:
    """Which bytes are about to run, read off the disk rather than off config.

    Config states an expectation and the file states a fact. The identity gate
    exists because those two can disagree - a mirror can serve a same-named file
    with different bytes - so the digest here is taken from the file the runtime
    will open (Rule #10).
    """
    model = settings.app.models.summarize
    weights = args.weights or (config.REPO_ROOT / "backend" / "models" / model.file)
    if not weights.exists():
        raise SystemExit(f"the candidate weights are not on disk: {model.file}")
    if not model.sha256:
        raise SystemExit(f"{model.id} declares no sha256, so nothing can verify what ran")
    return CandidateIdentity(
        model_id=model.id,
        repo=model.repo,
        revision=args.candidate_revision or "revision-not-recorded",
        file=model.file,
        quantisation=model.quantisation,
        sha256_expected=model.sha256,
        sha256_observed=file_digest(weights),
        bytes_expected=args.candidate_bytes or weights.stat().st_size,
        bytes_observed=weights.stat().st_size,
        runtime_build=runtime_build(),
    )


class _Frozen(NamedTuple):
    """One captured article and the row that describes it."""

    row: CorpusItem
    item: PlannedItem
    article: Article
    seen_text: str
    full_text: str


class _Share(NamedTuple):
    """What ONE shard tries to find, so the shards together meet the definition.

    Every shard runs in its own job and cannot see a sibling's corpus, so each
    one aims at the whole requirement rather than at a fraction of it. Aiming at
    a fraction is what loses a tier: a shard that stopped at its 1-in-3 share
    would walk away from the second long read in its slice, and a sibling whose
    slice held none could not make it up. Aiming high costs nothing - the corpus
    is still `corpus_per_shard` articles, and a tier nobody found is named
    rather than replaced.
    """

    per_band: int
    over_cap: int
    brief: int


def corpus_share() -> _Share:
    """The registered definition, as one shard's target."""
    return _Share(
        per_band=qualify.MIN_PER_BAND,
        over_cap=qualify.MIN_OVER_CAP,
        brief=qualify.MIN_BRIEF,
    )


def _unmet(offered: Sequence[_Frozen], *, share: _Share, bands: int) -> list[str]:
    """Which tiers this slice could not offer. The union is decided elsewhere."""
    short = []
    for index in range(bands):
        found = sum(1 for entry in offered if entry.row.band_index == index)
        if found < share.per_band:
            short.append(f"band {index}: {found}, the definition asks for {share.per_band}")
    over_cap = sum(1 for entry in offered if entry.row.truncated)
    if over_cap < share.over_cap:
        short.append(
            f"over the truncation cap: {over_cap}, the definition asks for {share.over_cap}"
        )
    briefs = sum(1 for entry in offered if entry.row.brief)
    if briefs < share.brief:
        short.append(f"brief-path items: {briefs}, the definition asks for {share.brief}")
    return short


def _freeze(
    items: Sequence[PlannedItem],
    settings: config.Settings,
    read_url: Fetcher,
    *,
    keep: int,
    share: _Share,
) -> tuple[list[_Frozen], int, list[str]]:
    """Fetch, extract and sanitize once, then hash what came back.

    Once, and never again: the three deterministic repeats have to see identical
    bytes, and a publisher rewriting a page between two of them would read as a
    decoding drift. The bytes stay on this job's own disk - only the hashes and
    the measurements travel, because an article body is not ours to move
    (`CLAUDE.md` section 0a).

    The walk stops at the LATER of two floors: a pool wide enough to choose from
    at all, and a pool that already holds every tier the definition asks for.
    Otherwise it walks the whole slice. A long read is the scarce shape -
    measured on 2026-08-26 at 3 of 109 extracted articles, under 3 in 100 - so a
    walk that stopped at the first floor met its item count every time while the
    tier that decides whether the corpus can speak at all stayed empty. Walking
    further costs fetch seconds and never model minutes: the model still sees
    `keep` articles, and one address measured 2.1 s over 150 of them.

    Returns the selected corpus, how many addresses were consumed, and the tiers
    this slice could not offer. The second number is the honest attempted
    denominator: an address that would not fetch measured nothing, and dropping
    it from the record would let a bad day look like a good one.
    """
    bands = len(settings.app.summarize.bands)
    floor = keep * settings.app.evaluation.qualification_pool_multiple
    pool: list[_Frozen] = []
    attempted = 0
    for item in items:
        if len(pool) >= floor and not _unmet(pool, share=share, bands=bands):
            break
        attempted += 1
        article, source_text, _, _ = _fetch_one(item, settings, read_url)
        if article.status is not ArticleStatus.OK or not article.text:
            LOG.info("corpus item unavailable url=%s", item.canonical_url)
            continue
        seen = article.text
        whole = source_text or seen
        pool.append(
            _Frozen(
                row=CorpusItem(
                    item_id=item.item_id,
                    url_key=item.url_key,
                    canonical_url=item.canonical_url,
                    source_id=item.source_id,
                    vertical=item.vertical,
                    band_index=qualify.band_index(
                        article.band_source_words, settings.app.summarize
                    ),
                    brief=article.brief,
                    truncated=article.truncated,
                    source_word_count=article.band_source_words,
                    seen_word_count=len(seen.split()),
                    seen_token_count=article.token_count,
                    seen_text_sha256=text_digest(seen),
                    full_text_sha256=text_digest(whole),
                ),
                item=item,
                article=article,
                seen_text=seen,
                full_text=whole,
            )
        )
    chosen = _stratified(pool, keep=keep, bands=bands, share=share)
    return chosen, attempted, _unmet(pool, share=share, bands=bands)


def _stratified(
    pool: Sequence[_Frozen], *, keep: int, bands: int, share: _Share
) -> list[_Frozen]:
    """Reserve the scarce tiers first, then fill the rest in turn.

    Deterministic, and it needs to be: the corpus is registered by hash before
    any output is looked at, so a selection that varied would let somebody
    re-roll a corpus until the answer improved.

    Scarcest tier first, and one at a time. A plain round-robin spends its early
    slots on whichever tier the index order reaches first, and taking a whole
    tier's quota before moving on starves the last tier when `keep` is smaller
    than every tier's quota added up. Measured on 2026-08-26 over 109 extracted
    articles, the long-read tier held 3 and the 60-to-699-word tier held 67, so
    the order is not a detail. Ties break on the band index, so two tiers of
    equal size always resolve the same way.

    Within a tier the scarce shapes go first: a brief item and an over-cap item
    each exercise a path nothing else reaches, and both are rarer than an
    ordinary article.
    """
    buckets: dict[int, list[_Frozen]] = {index: [] for index in range(bands)}
    for entry in pool:
        buckets.setdefault(entry.row.band_index, []).append(entry)
    for bucket in buckets.values():
        bucket.sort(key=lambda entry: (not entry.row.brief, not entry.row.truncated))
    scarcest = sorted(buckets, key=lambda key: (len(buckets[key]), key))
    chosen: list[_Frozen] = []
    for _ in range(share.per_band):
        for index in scarcest:
            if len(chosen) < keep and buckets[index]:
                chosen.append(buckets[index].pop(0))
    while len(chosen) < keep and any(buckets.values()):
        for index in sorted(buckets):
            if len(chosen) >= keep:
                break
            if buckets[index]:
                chosen.append(buckets[index].pop(0))
    return chosen


def _canary_article(
    payload: dict[str, object], *, extract_config: ExtractConfig, fetched_at: str
) -> Article:
    """One planted attack, shaped like the article `extract` would have built.

    The raw text is handed on unsanitized on purpose: `user_turn` fences and
    sanitizes what it is given, so this exercises the boundary instead of
    stepping around it (Rule #11). Every count is taken from the sanitized body
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


def _observe(
    article: Article,
    summary: Summary,
    completion: Completion | None,
    *,
    repeat: int,
    inference: InferenceConfig,
    seconds: float,
) -> ItemObservation:
    reply = completion or Completion(content="")
    inline = summarize.split_thinking(reply.content)[1] or ""
    return ItemObservation(
        item_id=article.item_id,
        repeat=repeat,
        ok=summary.status is SummaryStatus.OK,
        failure_code=summary.failure_code.value if summary.failure_code else None,
        finish_reason=reply.finish_reason,
        reasoning_channel_used=bool(reply.reasoning.strip()),
        think_block_words=len(inline.split()),
        schema_valid=summary.status is SummaryStatus.OK,
        # One call, one reply. The gate wants zero repair attempts, so the
        # column exists to be asserted rather than to be filled in later.
        repaired=summary.attempt > 1,
        output_digest=summary.output_digest,
        summary_word_count=len((summary.summary or "").split()),
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        fits_context_predicted=summarize.fits_context(article, inference),
        summarize_seconds=seconds,
    )


def _score_item(
    frozen: _Frozen, summary: Summary, scorer: object, evaluation: EvaluationConfig
) -> ItemScore:
    text = summary.summary or ""
    hhem, hhem_full = dual_score(
        scorer,  # type: ignore[arg-type]
        seen_text=frozen.seen_text,
        full_text=frozen.full_text,
        summary=text,
        evaluation=evaluation,
    )
    return ItemScore(
        item_id=frozen.row.item_id,
        brief=frozen.article.brief,
        hhem=hhem,
        hhem_full=hhem_full,
        verbatim_run=metrics.verbatim_run(text, frozen.full_text),
        extractiveness=metrics.extractiveness(text, frozen.full_text),
        compression=metrics.compression(text, frozen.full_text),
        lead_coverage=metrics.lead_coverage(text, frozen.full_text),
        unsupported_numbers=metrics.unsupported_numbers(text, frozen.full_text),
        hedge_dropped=metrics.hedge_dropped(text, frozen.full_text),
        evidential_density=metrics.evidential_density(frozen.full_text),
        speculative_density=metrics.speculative_density(frozen.full_text),
        title_fell_back=summary.title is None,
    )


def _one_call(
    article: Article, settings: config.Settings, fingerprint: str, *, endpoint: str
) -> tuple[Summary, Completion | None, float]:
    """One live inference call, timed, with the reply kept for the gates."""
    inference = settings.app.models.inference
    model_id = settings.app.models.summarize.id
    payload = summarize.build_request(
        article,
        model_id=model_id,
        inference=inference,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    started = time.monotonic()
    completion: Completion | None
    no_reply = FailureCode.MODEL_UNREACHABLE
    try:
        completion = post(
            payload, endpoint=endpoint, timeout=inference.request_timeout_minutes * 60
        )
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        completion = None
        no_reply = (
            FailureCode.CONTEXT_EXCEEDED
            if is_context_exceeded(body)
            else FailureCode.MODEL_UNREACHABLE
        )
    except OSError:
        completion = None
    seconds = time.monotonic() - started
    summary = summarize.to_summary(
        article,
        completion,
        model_id=model_id,
        pipeline_fingerprint=fingerprint,
        generated_at=assemble.utc_now(),
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
        no_reply=no_reply,
    )
    return summary, completion, seconds


def _run_canaries(
    settings: config.Settings, fingerprint: str, *, endpoint: str
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
        summary, completion, _ = _one_call(article, settings, fingerprint, endpoint=endpoint)
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


def _canary_report(
    observations: Sequence[CanaryObservation], *, root: Path, required: int
) -> int:
    """Write what the attacks did, then say whether the gate holds.

    Split from the calls so the file-out half is reachable without a served
    model. Fail-closed: a gate that cannot speak for every planted attack
    returns non-zero.
    """
    assemble.write_atomic(
        root / "canaries.json",
        canonical_json([observation.model_dump(mode="json") for observation in observations]),
    )
    outcome = qualify.injection_canaries(observations, required=required)
    LOG.info("canary gate %s: %s", outcome.status.value, outcome.measured)
    LOG.info("canary detail: %s", outcome.detail)
    return 0 if outcome.status is GateStatus.PASSED else 1


def stage_qualify_canaries(
    *, settings: config.Settings, date: str, model_endpoint: str = DEFAULT_ENDPOINT
) -> int:
    """The five planted attacks alone, against the configured model.

    The arm was reachable only from inside `stage_qualify` at shard zero, so the
    only way to see what a canary did was a whole qualification (`CLAUDE.md`
    section 4). The fixtures are the file in, `canaries.json` is the file out,
    and the exit code is the gate.
    """
    inference = settings.app.models.inference
    model = settings.app.models.summarize
    observed = props(model_endpoint, timeout=inference.request_timeout_minutes * 60)
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=runtime_build(),
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        prompt=summarize.prompt_inputs(settings.app.summarize),
        output_schema=summarize.output_schema_text(settings.app.summarize, settings.app.evaluation),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )
    observations = _run_canaries(settings, inputs.fingerprint(), endpoint=model_endpoint)
    return _canary_report(
        observations,
        root=QUALIFICATION_ROOT / date,
        required=len(sorted(CANARY_DIR.glob("*.json"))),
    )


def stage_qualify(
    *,
    settings: config.Settings,
    date: str,
    shard: int,
    shards: int,
    repeats: int,
    corpus_per_shard: int,
    candidate: CandidateIdentity,
    scorer: object,
    commit_sha: str,
    runner: str,
    fetcher: Fetcher | None = None,
    model_endpoint: str = DEFAULT_ENDPOINT,
) -> QualificationShard:
    """Freeze this shard's slice of the corpus, then replay it N times.

    Capture once and replay is the whole design. The old validation arm replanned
    and refetched for every model it scored, so two numbers could differ because
    a publisher edited a page rather than because the weights differed. There is
    only one model here now, and the same argument still holds against the three
    repeats.
    """
    if scorer is None:
        raise SystemExit("a qualification without a faithfulness scorer measures nothing")
    if not isinstance(scorer, HhemScorer):
        raise SystemExit("the faithfulness gate needs the pinned HHEM scorer")

    started = time.monotonic()
    read_url = fetcher or live_fetcher(settings)
    inference = settings.app.models.inference
    model = settings.app.models.summarize
    observed = props(model_endpoint, timeout=inference.request_timeout_minutes * 60)
    inputs = build_inputs(
        model=model,
        model_sha256=candidate.sha256_observed,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build=candidate.runtime_build,
        chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
        prompt=summarize.prompt_inputs(settings.app.summarize),
        output_schema=summarize.output_schema_text(settings.app.summarize, settings.app.evaluation),
        runner_class=runner_class(),
        extractor_version=extract.EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )
    fingerprint = inputs.fingerprint()

    plan = _load_plan(date)
    mine = shard_of(plan, shard=shard, shards=shards)
    share = corpus_share()
    frozen, attempted, unmet = _freeze(mine, settings, read_url, keep=corpus_per_shard, share=share)

    root = QUALIFICATION_ROOT / date / f"shard-{shard}"
    for entry in frozen:
        assemble.write_atomic(
            root / "items" / f"{entry.row.item_id}.article.json", entry.article.to_json()
        )
    registered_at = assemble.utc_now()
    assemble.write_atomic(
        root / "corpus.json",
        canonical_json([entry.row.model_dump(mode="json") for entry in frozen]),
    )
    # Loud here, decided at `decide`. A shard cannot see its siblings, so it
    # never rules on the union - it only says which tier its own slice never
    # offered, while the addresses are still in this job's log.
    for shortfall in unmet:
        LOG.error("shard %s was offered no such tier: %s", shard, shortfall)
    LOG.info(
        "corpus frozen shard=%s items=%s attempted=%s handed=%s registered_at=%s",
        shard,
        len(frozen),
        attempted,
        len(mine),
        registered_at,
    )

    scorer_identity = ScorerIdentity(
        scorer_id=HHEM_SCORER_ID,
        revision=HHEM_REVISION,
        pinned=is_pinned(HHEM_REVISION),
        weights_sha256=weights_digest(scorer),
        scorer_version=metrics.scorer_version(
            scorer_id=HHEM_SCORER_ID,
            scorer_revision=HHEM_REVISION,
            weights_sha256=weights_digest(scorer),
            evaluation=settings.app.evaluation,
        ),
    )

    observations: list[ItemObservation] = []
    scores: list[ItemScore] = []
    # Repeats on the outside, items on the inside. The other order would let
    # each repeat land on a warm prompt cache, and an identical reply that
    # skipped its own prefill is weaker evidence of determinism than one that
    # did the arithmetic again.
    for repeat in range(1, repeats + 1):
        for entry in frozen:
            summary, completion, seconds = _one_call(
                entry.article, settings, fingerprint, endpoint=model_endpoint
            )
            observations.append(
                _observe(
                    entry.article,
                    summary,
                    completion,
                    repeat=repeat,
                    inference=inference,
                    seconds=seconds,
                )
            )
            LOG.info(
                "qualify call item=%s repeat=%s ok=%s seconds=%.1f",
                entry.row.item_id,
                repeat,
                summary.status is SummaryStatus.OK,
                seconds,
            )
            if repeat == 1 and summary.status is SummaryStatus.OK:
                scores.append(_score_item(entry, summary, scorer, settings.app.evaluation))

    canaries = _run_canaries(settings, fingerprint, endpoint=model_endpoint) if shard == 0 else []

    result = QualificationShard(
        version=QualificationShard.schema_version(),
        date=date,
        commit_sha=commit_sha,
        runner=runner,
        shard=shard,
        shards=shards,
        repeats=repeats,
        candidate=candidate,
        scorer=scorer_identity,
        pipeline_fingerprint=fingerprint,
        corpus_registered_at=registered_at,
        planned=attempted,
        corpus=[entry.row for entry in frozen],
        observations=observations,
        scores=scores,
        canaries=canaries,
        elapsed_seconds=time.monotonic() - started,
    )
    assemble.write_atomic(QUALIFICATION_ROOT / f"shard-{shard}.json", result.to_json())
    LOG.info(
        "qualification shard done shard=%s frozen=%s calls=%s scored=%s minutes=%.1f",
        shard,
        len(frozen),
        len(observations),
        len(scores),
        result.elapsed_seconds / 60.0,
    )
    return result


def stage_qualify_decide(
    *, settings: config.Settings, date: str, job_budget_minutes: float, runner: str
) -> int:
    """Merge the shards, run the eleven gates, and say which number failed.

    Returns non-zero when a gate fails. The verdict is an ESCALATE either way -
    adopting a model changes a persisted contract - so this writes the evidence
    and stops rather than switching anything itself.
    """
    paths = sorted(QUALIFICATION_ROOT.glob("shard-*.json"))
    shards = [QualificationShard.read(path) for path in paths]
    if not shards:
        raise SystemExit("no qualification shard was written, so there is nothing to decide")

    evaluation = settings.app.evaluation
    frozen, outcomes = qualify.gates(
        shards,
        evaluation=evaluation,
        inference=settings.app.models.inference,
        run=settings.app.run,
        budget_=qualify.Budget(
            job_budget_minutes=job_budget_minutes,
            slowest_shard_seconds=max(shard.elapsed_seconds for shard in shards),
            slowest_item_seconds=max(
                (o.summarize_seconds for shard in shards for o in shard.observations), default=0.0
            ),
        ),
        required_canaries=len(sorted(CANARY_DIR.glob("*.json"))),
    )
    shortfalls = qualify.corpus_shortfalls(frozen.items, summarize=settings.app.summarize)
    if shortfalls:
        # Not a gate. These describe the measuring stick, and a thin corpus is a
        # run to repeat rather than a model to reject.
        for shortfall in shortfalls:
            LOG.error("corpus is not adequate: %s", shortfall)
        raise SystemExit("the frozen corpus does not meet the registered definition")

    failed = [outcome for outcome in outcomes if outcome.status is GateStatus.FAILED]
    report = QualificationReport(
        version=QualificationReport.schema_version(),
        date=date,
        commit_sha=shards[0].commit_sha,
        runner=runner,
        candidate=shards[0].candidate,
        scorer=shards[0].scorer,
        pipeline_fingerprint=shards[0].pipeline_fingerprint,
        corpus_digest=corpus_digest(frozen.items),
        corpus_items=len(frozen.items),
        planned=frozen.planned,
        repeats=frozen.repeats,
        scored=len(frozen.scores),
        gates=outcomes,
        diagnostics=[
            *qualify.stratification(frozen.items, summarize=settings.app.summarize),
            *qualify.diagnostics(frozen, evaluation=evaluation),
        ],
        qualified=not failed,
        detail=(
            "; ".join(f"{o.gate.value} measured {o.measured} against {o.threshold}" for o in failed)
            or f"every gate passed on {len(frozen.items)} frozen articles"
        ),
    )
    assemble.write_atomic(QUALIFICATION_ROOT / "report.json", report.to_json())

    mean_hhem = (
        sum(score.hhem for score in frozen.scores) / len(frozen.scores) if frozen.scores else 0.0
    )
    writer.append_validation(
        config.REPO_ROOT / golden.ledger_relpath(date),
        [
            ValidationRow(
                version=ValidationRow.schema_version(),
                model_id=report.candidate.model_id,
                is_incumbent=report.candidate.model_id == settings.app.models.summarize.id,
                selected=report.qualified,
                leaderboard_hhem=None,
                leaderboard_provenance=LeaderboardProvenance.NOT_REPORTED,
                measured_hhem=mean_hhem,
                articles=max(len(frozen.scores), 1),
                measured_on=date,
                commit_sha=report.commit_sha,
                runner=runner,
                verdict=(
                    ValidationVerdict.QUALIFIED
                    if report.qualified
                    else ValidationVerdict.NOT_QUALIFIED
                ),
                detail=report.detail,
            )
        ],
    )

    for outcome in outcomes:
        LOG.info(
            "gate %s %s measured=%s threshold=%s source=%s",
            outcome.gate.value,
            outcome.status.value,
            outcome.measured,
            outcome.threshold,
            outcome.source,
        )
    for diagnostic in report.diagnostics:
        LOG.info("diagnostic %s=%s n=%s", diagnostic.name, diagnostic.value, diagnostic.denominator)
    if failed:
        LOG.error("ESCALATE: %s", report.detail)
        return 2
    LOG.info("qualified model=%s corpus=%s", report.candidate.model_id, report.corpus_digest[:12])
    return 0


# --- assemble ----------------------------------------------------------------


class _ItemPayload(NamedTuple):
    planned: PlannedItem
    article: Article | None
    summary: Summary | None
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
            eval_path=items_dir / f"{item.item_id}.eval.json",
            decision_path=items_dir / f"{item.item_id}{PAYLOAD_SUFFIX}",
        )


def stage_record(plan: RunPlan, *, shard: int = 0, shards: int = 1) -> tuple[int, int]:
    """Commit what one shard measured, before anything can throw it away.

    `stage_assemble` writes the whole day's census, and it runs in another job on
    another machine hours later. Until then a shard's verdicts exist only inside
    its `items-<shard>` artifact, which expires in a day and is not uploaded at
    all when the job is cancelled. So a run stopped between the workers and the
    publish had measured every item and recorded none of it.

    Only settled items are recorded, which is what `telemetry.is_final` decides.
    An item whose summary is not written yet was interrupted rather than failed,
    and this ledger has no way to correct a row once it is in.

    Each row is stamped with this worker's own `shard`, which is the only moment
    the number is known: `stage_assemble` runs once for the whole day and cannot
    say which machine an item was for, so the rows it adds leave the cell empty.
    `state/runtime-counters.csv` carries the same number at the run grain, and
    the pair is what lets a per-item rate be read against the host that ran it.

    Returns the item-health rows and the eval rows that landed.
    """
    items_dir = _run_dir(plan.date) / "items"
    mine = {item.item_id for item in shard_of(plan, shard=shard, shards=shards)}
    health: list[ItemHealthRow] = []
    rows: list[EvalRow] = []
    for payload in _item_payloads(plan, items_dir):
        if payload.planned.item_id not in mine:
            continue
        if not telemetry.is_final(payload.article, payload.summary):
            continue
        health.append(
            telemetry.classify_item(
                planned=payload.planned,
                article=payload.article,
                summary=payload.summary,
                date=plan.date,
                run_id=plan.run_id,
                shard=shard,
            )
        )
        if payload.eval_path.exists():
            rows.append(EvalRow.read(payload.eval_path))
    recorded = ledger.append_item_health(STATE_ROOT, plan.date, health)
    scored = writer.append(STATE_ROOT, rows)
    LOG.info(
        "recorded shard=%s/%s run=%s settled=%s item_health_rows=%s eval_rows=%s",
        shard,
        shards,
        plan.run_id,
        len(health),
        recorded,
        scored,
    )
    return recorded, scored


def stage_counters(
    plan: RunPlan,
    *,
    metrics_path: Path,
    shard: int = 0,
    shards: int = 1,
    job_started_at: int | None = None,
    cpu_model: str | None = None,
    cpu_stat_at_start: str | None = None,
    cpu_stat_at_end: str | None = None,
    rss_samples_path: Path | None = None,
    server_log_path: Path | None = None,
) -> RuntimeCountersRow:
    """Commit what this shard's model server counted, so the ledger can be checked.

    Every timing on the item-health ledger is a field the summarize stage copied
    out of one model reply. The server's own counters are the second instrument,
    and until now they reached only a job log that keeps them for two days - so
    the rates two published surfaces quote could not be reconciled with anything
    (Rule #10).

    Both counters are cumulative for the server process and a shard runs one
    server for its whole job, so this one read covers the shard entirely.

    The same row carries the job's own facts as well as the server's: the clock,
    the host, how busy that host was, the memory high point and what the weights
    cost to open. None of them is the server's to report, so each arrives as an
    argument. A stage reads a file and writes a file, so it does not go looking
    for `/proc` itself - that tree exists on the runner and on no developer
    machine this project is written on. What it does do is the arithmetic, so
    the derivation behind a cell is in the contract rather than in a shell.

    A missing or empty body still writes a row, with every counter null. A shard
    whose server was already gone and a shard that never ran are different facts,
    and pooling a run needs to see the shard that contributed nothing.
    """
    row = RuntimeCountersRow.from_metrics_text(
        _text_if_readable(metrics_path),
        date=plan.date,
        run_id=plan.run_id,
        shard=shard,
        shards=shards,
        scraped_at=assemble.utc_now(),
        job_started_at=job_started_at,
        cpu_model=cpu_model,
        cpu_stat_at_start=cpu_stat_at_start,
        cpu_stat_at_end=cpu_stat_at_end,
        rss_samples=_text_if_readable(rss_samples_path),
        server_log=_text_if_readable(server_log_path),
    )
    landed = ledger.append_runtime_counters(STATE_ROOT, [row])
    LOG.info(
        "counted shard=%s/%s run=%s read_tokens=%s read_seconds=%s job_seconds=%s cpu=%s "
        "cpu_busy_pct=%s peak_rss_bytes=%s model_load_ms=%s rows=%s",
        shard,
        shards,
        plan.run_id,
        row.prompt_tokens_total,
        row.prompt_seconds_total,
        row.job_seconds,
        row.cpu_model,
        row.cpu_busy_pct,
        row.peak_rss_bytes,
        row.model_load_ms,
        landed,
    )
    return row


def _text_if_readable(path: Path | None) -> str:
    """A file the job may not have written is absent text, never a failed stage."""
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def stage_harvest(
    date: str,
    *,
    settings: config.Settings,
    corpus_dir: Path,
    force: bool = False,
) -> int:
    """Add this run's accepted pairs to the training window, and roll it.

    A step in the digest run rather than a workflow of its own, because the only
    place the article text exists is the machine that just read it: `items/` is
    gitignored and travels as a one-day artifact, so a scheduled job with a fresh
    checkout would find an empty directory and harvest nothing, silently, forever.

    It is still a stage that runs alone with a file in and a file out (section 4),
    and it reads the items directory rather than the run plan - the directory is
    the record of what was worked, so the plan is a second artifact that has to be
    present and answers nothing the files do not. That is also what lets
    `data_wrangler.py backfill` replay a finished run from its artifacts alone.

    The cadence lives in `finetune.harvest_every_days` and is decided here rather
    than in a cron line, because `on.schedule` is parsed before any step runs and
    no config value can reach it. Returns the row count the window now holds, and
    zero when the harvest was not due.
    """
    finetune = settings.app.finetune
    meta = corpus.read_meta(corpus_dir)
    if not force and not corpus.harvest_is_due(
        meta, date=date, every_days=finetune.harvest_every_days
    ):
        LOG.info(
            "harvest not due date=%s last=%s every=%s rows=%s",
            date,
            meta.harvested_date,
            finetune.harvest_every_days,
            meta.rows,
        )
        return 0

    written = corpus.harvest(
        corpus_dir,
        corpus.scored_from_items(_run_dir(date) / "items"),
        date=date,
        finetune=finetune,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    return written.rows


def stage_prune_stamp(*, corpus_dir: Path, date: str) -> int:
    """Record that `prune.yml` ran today, so tomorrow's check does not fire again.

    Separate from the squash itself, which is git surgery and belongs in the
    workflow. What this owns is the one piece of durable state that turns a
    force-push a day into a force-push a month.
    """
    meta = corpus.stamp_prune(corpus_dir, date=date)
    LOG.info("prune stamped date=%s rows=%s", meta.pruned_date, meta.rows)
    return 0


def stage_dedupe_ledgers(*, state_dir: Path | None = None) -> int:
    """Settle every keyed ledger after a merge, and print what it dropped.

    The one thing an appending stage cannot do for itself. Each of those stages
    filters what it is about to write against the file it checked out, and
    `actions/checkout` pins a job to the commit its run was triggered at - so a
    second attempt at the same work cannot see the rows the first attempt pushed
    afterwards, appends them again, and `merge=union` concatenates both sides.
    The result is a file whose key repeats, which is the one shape every reader
    of it assumes cannot happen.

    So this runs where the frozen snapshot cannot reach: after the merge, on the
    merged file, which is the only artefact that has ever held both sides at
    once. `.github/scripts/commit-and-push.sh` calls it there through
    `DROP_REPEATED_ROWS_COMMAND`, between the rebase and the push.

    Every ledger that declares what makes two of its rows the same record is
    settled here. `state/seen/` declares nothing and is left alone - see
    `ledger.keyed_paths`. Feed-health is the one whose repeats can disagree, so
    it is the one settled by a rule rather than by arrival order; the rule is in
    `contracts.feed_health.supersedes` and travels with the key.

    It always returns 0. A repeat it drops is a repair, not a finding, and a
    non-zero exit here would abort the commit step that called it and cost the
    run every ledger row staged beside the one it just fixed.
    """
    state = state_dir if state_dir is not None else STATE_ROOT
    targets: list[tuple[Path, tuple[str, ...]]] = [
        *ledger.keyed_paths(state),
        *((shard, writer.OBSERVATION_KEY) for shard in writer.ledger_shards(state)),
    ]
    total = 0
    for path, key in targets:
        dropped = ledger.drop_repeated_rows(path, key)
        total += dropped
        if dropped:
            LOG.info(
                "dropped repeated rows file=%s key=%s rows=%s",
                path.name,
                "+".join(key),
                dropped,
            )
    LOG.info("ledgers settled files=%s repeated_rows_dropped=%s", len(targets), total)
    return 0


def stage_prune_state(
    *,
    observability: ObservabilityConfig,
    collect: CollectConfig,
    retention_config: RetentionConfig,
    run_id: str,
    today: date_type,
    state_dir: Path | None = None,
    public_root: Path | None = None,
    digest_root: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Retire what the ledgers no longer answer for: an item-health month and the
    browser's copy of it, a feed-health month, every seen shard outside the
    window the planner reads, every committed span trace past its short window,
    and every score month past its full-grain window. Then clean the rendered
    visuals the archive policy has aged out, and record what that pass found.

    Six stores, one step, because they share the one property that makes this
    safe: all of it runs after the day is committed, and none of it can cost a
    reader anything it has not already been given.

    **The visuals are the seventh thing here and they do not share that property.**
    Deleting a picture costs a reader the picture. They are in this step because
    it is the step that runs after the commit and because the pass is switched
    off - `retention.image_months` is -1 and the flag makes it report-only - so
    what runs today is a measurement of the backlog and nothing else. Switching
    the deletion on is a separate change, and it needs two more things this step
    does not have: the commit call below it has to stage
    `frontend/public/digest` as well, because `git add` records a removal only
    for a path it is handed, and the promise in
    `docs/architecture/publishing/layout.md` about a workflow of its own has to
    be met or re-decided.

    Runs after the day is committed, never before. A fold that ran first and then
    failed would leave a month deleted from a tree nothing pushed, and the next
    run would fold a shard that had already been folded - so it sits behind the
    commit that makes the day real, where the worst it can cost is one run's
    worth of bytes.

    It reports rather than fails. What this job owes a reader is the published
    day; a fold that will not run must never be the thing that stops one.

    **Every file a live run would remove is named, one line each.** A count says
    a deletion happened and nothing about what it took, and the workflow ships
    this in dry run precisely so a person can read that list before the deletion
    is switched on.
    """
    state = state_dir if state_dir is not None else STATE_ROOT
    # The published tree only defaults beside the default state tree. A caller
    # that named its own `state_dir` and left this out gets no browser copy
    # rather than the committed one - deleting a published shard out of a test
    # run is the failure this pairing exists to stop.
    public = public_root
    if public is None and state_dir is None:
        public = publish_telemetry.DEFAULT_PUBLIC_ROOT
    # The day payloads pair with the state tree the same way and for the same
    # reason: a test that named its own state must not have this one default to
    # the committed archive.
    digest = digest_root
    if digest is None and state_dir is None:
        digest = PUBLIC_ROOT

    removed: list[str] = []
    removed += _prune_seen_shards(state, collect, today, dry_run=dry_run)
    removed += _prune_trace_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_feed_health_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_score_shards(state, observability, today, dry_run=dry_run)

    result = retention.prune_telemetry(
        state, observability, today, public_root=public, dry_run=dry_run
    )
    if not result.changed:
        LOG.info(
            "telemetry fold: nothing older than %s months, so every month is still at "
            "full grain",
            observability.item_health_full_grain_months,
        )
    else:
        LOG.info(
            "telemetry fold%s: %s folded %s rows into %s, dropped the browser copy of %s, "
            "hard-deleted %s",
            " (dry run)" if result.dry_run else "",
            ", ".join(result.folded) or "no month",
            result.rows_folded,
            result.aggregate_rows,
            ", ".join(result.public_deleted) or "no month",
            ", ".join(result.hard_deleted) or "no month",
        )
        removed += [ledger.item_health_relpath(f"{stem}-01") for stem in result.folded]
        removed += [publish_telemetry.shard_relpath(stem) for stem in result.public_deleted]
        removed += [
            ledger.telemetry_aggregate_relpath(stem) for stem in result.hard_deleted
        ]

    if digest is not None:
        _clean_the_visuals(
            digest,
            retention_config,
            today,
            run_id=run_id,
            state_dir=state,
            dry_run=dry_run,
        )

    _report_removals(sorted(removed), dry_run=dry_run)
    return 0


def _clean_the_visuals(
    digest_root: Path,
    config: RetentionConfig,
    today: date_type,
    *,
    run_id: str,
    state_dir: Path,
    dry_run: bool,
) -> None:
    """Run the archive cleanup over the day payloads and commit what it found.

    The row lands whatever happened, including the run where the policy is off
    and nothing was a candidate. A ledger written only on the interesting runs
    cannot show that a backlog is shrinking, because the runs it skips are the
    ones that would have been the baseline.
    """
    result = retention.prune(digest_root, config, today, dry_run=dry_run)
    row = retention.prune_row(result, config, date_stamp=today.isoformat(), run_id=run_id)
    landed = ledger.append_visual_prunes(state_dir, [row])
    LOG.info(
        "visual cleanup%s: %s candidates older than %s, %s deleted, %s held back by the "
        "%s-file fuse, %s bytes reclaimed, oldest picture still kept %s (%s row)",
        " (dry run)" if result.dry_run else "",
        result.considered,
        row.cutoff_date or "no cutoff - the policy is off",
        result.deleted,
        result.skipped_by_fuse,
        config.max_deletes_per_run,
        result.bytes_reclaimed,
        row.oldest_kept or "none",
        landed,
    )


def _report_removals(paths: list[str], *, dry_run: bool) -> None:
    """Name every file, one line each, in the POSIX form section 2 asks for.

    This list is the deliverable of a dry run: it is what a person reads before
    turning the deletion on, so it is the paths themselves and never a count.
    """
    if not paths:
        LOG.info("prune-state removes no file today")
        return
    verb = "would remove" if dry_run else "removed"
    LOG.info("prune-state %s %s files:", verb, len(paths))
    for path in paths:
        LOG.info("prune-state %s %s", verb, path)


def _prune_feed_health_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the feed-health months no quarantine and no console read reaches.

    Deleted rather than folded: a row here is one feed's result on one run, and
    a total over a month fourteen months back answers nothing anybody asks.
    """
    feed = retention.prune_feed_health(state, observability, today, dry_run=dry_run)
    if not feed.changed:
        LOG.info(
            "feed-health prune: every shard is inside the %s-month window, so none was "
            "deleted",
            observability.feed_health_keep_months,
        )
        return []
    LOG.info(
        "feed-health prune%s: deleted %s, freed %s bytes, kept %s",
        " (dry run)" if feed.dry_run else "",
        ", ".join(feed.deleted),
        feed.bytes_freed,
        ", ".join(feed.kept) or "no shard",
    )
    return [ledger.health_relpath(f"{stem}-01") for stem in feed.deleted]


def _prune_seen_shards(
    state: Path, collect: CollectConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the seen shards `rank` will not read again, and say what went.

    Separate from the fold above so a shard that will not delete cannot stop a
    month being folded, and so the log line names one ledger at a time.
    """
    seen = retention.prune_seen(
        state,
        today=today.isoformat(),
        within_days=collect.seen_window_days,
        dry_run=dry_run,
    )
    if not seen.changed:
        LOG.info(
            "seen prune: every shard is inside the %s-day window, so none was deleted",
            collect.seen_window_days,
        )
        return []
    LOG.info(
        "seen prune%s: deleted %s, freed %s bytes, kept %s",
        " (dry run)" if seen.dry_run else "",
        ", ".join(seen.deleted),
        seen.bytes_freed,
        ", ".join(seen.kept) or "no shard",
    )
    return [ledger.seen_relpath(f"{stem}-01") for stem in seen.deleted]


def _prune_trace_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the committed span traces past their window, and say what went.

    A trace is a lookup an operator opens for a recent run, so it deletes rather
    than folds - the same shape as the seen prune above and for the same reason.
    `state/traces/` does not exist until tracing is switched on, so until then
    this names the window it measured against and removes nothing.
    """
    traces = retention.prune_traces(
        state,
        today=today,
        within_days=observability.trace_window_days,
        dry_run=dry_run,
    )
    if not traces.changed:
        LOG.info(
            "trace prune: every committed trace is inside the %s-day window, so none "
            "was deleted",
            observability.trace_window_days,
        )
        return []
    LOG.info(
        "trace prune%s: deleted %s files, freed %s bytes, kept %s inside the window",
        " (dry run)" if traces.dry_run else "",
        len(traces.deleted),
        traces.bytes_freed,
        traces.kept,
    )
    return list(traces.deleted)


def _prune_score_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Archive the score months past their full-grain window, then delete their shards.

    The one store here whose deletion is preceded by a summary that is written,
    read back and reconciled against the file it replaces. The log says what the
    archive weighs against what the shard weighed, because that ratio is the
    measurement this policy rests on and a dry run is where a person reads it.
    """
    scores = retention.prune_scores(state, observability, today, dry_run=dry_run)
    if not scores.changed:
        LOG.info(
            "score archive: every month is inside the %s-month window, so none was "
            "summarised",
            observability.scores_full_grain_months,
        )
        return []
    LOG.info(
        "score archive%s: summarised %s - %s rows and %s distinct measurements, "
        "%s bytes of shard into %s bytes of archive - and hard-deleted %s",
        " (dry run)" if scores.dry_run else "",
        ", ".join(scores.archived) or "no month",
        scores.rows_archived,
        scores.observations_indexed,
        scores.source_bytes,
        scores.archive_bytes,
        ", ".join(scores.hard_deleted) or "no month",
    )
    removed = [writer.ledger_relpath(f"{stem}-01") for stem in scores.archived]
    removed += [score_archive.archive_relpath(stem) for stem in scores.hard_deleted]
    return removed


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
    # The plan's own id, because the work shards filed their ledger rows under it
    # and this stage writes the day's census into the same files. Deriving a
    # second one here would key assemble's rows differently from the shards' and
    # land every item twice.
    run_id = plan.run_id
    run_n = assemble.run_n_for(previous_manifest, run_id)
    digest_items = []
    summaries: list[Summary] = []
    rows = []
    decisions: list[VisualDecision] = []
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
            row = EvalRow.read(payload.eval_path)
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
            VisualDecision.read(payload.decision_path)
            if payload.decision_path.exists()
            else None
        )
        if decision is not None:
            decisions.append(decision)
        digest_items.append(
            assemble.to_digest_item(
                article=article,
                summary=summary,
                band=decided.band,
                band_reason=decided.reason,
                source_name=names.get(article.source_id, article.source_id),
                source_kind=kinds.get(article.source_id, SourceKind.REPORTING),
                run_n=1,
                decision=decision,
                planned=payload.planned,
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
        embeddings=assemble.build_embeddings(
            digest_items, Embedder(config.REPO_ROOT, settings.app.assist)
        ),
        item_health_rows=item_health_rows,
        watchlist=settings.watchlist,
        ui=settings.app.ui,
        duplicate_similarity_min=settings.app.assemble.duplicate_similarity_min,
    )
    assemble.write_atomic(target / "digest.json", day.to_json())

    # The month shard is a projection of the days on disk, so it is rebuilt after
    # the day is written and never patched in place.
    index = assemble.rebuild_search_index(
        digest_root=PUBLIC_ROOT, index_root=_index_root(), month=assemble.month_of(plan.date)
    )

    # The committed payload tree, which is what this stage can see. It is not the
    # published site and the Pages cap is not measured here - the site is built
    # by a later step in this same job, and `idhazh site-weight` measures it
    # there. See docs/architecture/publishing/layout.md.
    site_bytes, site_files = assemble.site_size(PUBLIC_ROOT)
    observability = settings.app.observability
    # The instrument that actually wrote this run's rows. No rows means no
    # instrument, which is what tells a run that was switched off or not drawn
    # apart from one whose weights would not load.
    instruments = sorted({row.scorer_version for row in rows})
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
        decisions=decisions,
        evaluation_enabled=observability.evaluation_enabled,
        evaluation_sample_rate=observability.sample_rate,
        evaluation_sampled=sampling.run_is_sampled(run_id, observability.sample_rate),
        scorer_version=instruments[0] if len(instruments) == 1 else None,
        rank_version=rank.RANK_VERSION,
    )
    assemble.write_atomic(target / "run.json", manifest.to_json())
    landed = writer.append(STATE_ROOT, rows)
    stamps = append_new(FINGERPRINTS, _stamps(items_dir))
    published = ledger.append_published(STATE_ROOT, _published_rows(day, plan))
    item_health = ledger.append_item_health(STATE_ROOT, plan.date, item_health_rows)
    publish_telemetry.publish(state_root=STATE_ROOT, public_root=PUBLIC_ROOT.parent / "telemetry")
    # Written after the ledgers this run appended, and from those files rather
    # than from anything in memory here: the view is a projection of the
    # committed record, so a run that failed to append has to publish the record
    # as it stands rather than as it hoped.
    source_health = publish_source_health.publish(
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        collect=settings.app.collect,
        date=plan.date,
        run_id=run_id,
        generated_at=generated_at,
        state_root=STATE_ROOT,
        path=PUBLIC_ROOT.parent / publish_source_health.PUBLIC_FILENAME,
    )
    yield_alarm = publish_source_health.yield_alarm(
        source_health,
        alarm_point=settings.app.collect.source_yield_alarm_point,
        min_decisions=settings.app.collect.source_yield_alarm_min_decisions,
    )
    if yield_alarm is not None:
        # Same shape as the site-budget alarm below: an Actions workflow command,
        # so a person sees it on the run summary. The console has carried these
        # counts all along and nobody read them, which is why this speaks.
        print(f"::warning title=Sources answering but not reading::{yield_alarm}")
        LOG.warning("%s", yield_alarm)
    LOG.info(
        "published date=%s items=%s partial=%s eval_rows=%s addresses=%s item_health_rows=%s "
        "new_fingerprints=%s search_index=%s/%s",
        plan.date,
        len(day.items),
        day.partial,
        landed,
        published,
        item_health,
        [row.pipeline_fingerprint[:12] for row in stamps],
        len(index.entries),
        index.vector_bytes // index.dimensions,
    )
    return day


def _published_rows(day: DigestDay, plan: RunPlan) -> list[PublishedRow]:
    """What this digest actually carried, as addresses a later run can skip.

    The digest item knows the item id and the plan knows the key, so the two are
    joined here rather than widening the published payload with anything the
    skip read does not open.

    That join is also the filter, and it is load-bearing: `ledger._append`
    writes every row it is handed, so nothing downstream would collapse a
    repeat. A day carries yesterday's items forward, and re-recording them would
    move their published date every morning. They do not survive the join
    because `rank.plan_vertical` has already dropped every address
    `load_published` returned, and an item id comes from its address - so a
    carried item's id is absent from this run's plan and it is skipped. The
    filter reads as "everything the day holds" and behaves as "what this run
    added", and the two only agree while those upstream facts hold.
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


# --- backfill -----------------------------------------------------------------


def published_days(root: Path) -> list[Path]:
    """Every committed day payload under `frontend/public/digest/`, oldest first."""
    return sorted(root.glob("*/*/*/digest.json"))


def is_closed(date: str, *, today: str) -> bool:
    """True when no scheduled run will append to this day again.

    The current UTC day is the one exclusion and this is why: the pipeline
    appends to it several times an hour, and a day payload is one JSON file
    with no union merge. Two producers writing it at once do not interleave -
    one of them wins whole, and the other one's run is gone.
    """
    return date < today


def earns_a_vector(day: DigestDay, embedder: Embedder) -> set[str]:
    """The item ids this day should carry a vector for, and no others.

    Not every item earns one. An item written in a script the encoder's
    vocabulary does not hold gets a well-formed vector about its characters
    rather than its story, which no query a reader types will ever retrieve, so
    `assist.min_readable_letter_share` excludes it. The count to compare a day
    against is therefore this set and not `len(day.items)`.
    """
    return {item.item_id for item in day.items if embedder.readable(text_for(item))}


def needs_backfill(day: DigestDay, embedder: Embedder) -> bool:
    """Whether this day's vectors are not exactly the set its items earned.

    Short and surplus are one question. A day is short where a run never
    encoded an item, and it is surplus where it carries a vector for an item
    that no longer earns one - and either way the block is not what this
    encoder would write today. A day that already matches answers `False`,
    which is what makes the command safe to dispatch twice.
    """
    block = day.embeddings
    if block is None:
        return bool(earns_a_vector(day, embedder))
    if (block.model_id, block.dimensions, block.dtype) != (EMBEDDER_ID, DIMENSIONS, DTYPE):
        return True
    return set(block.vectors) != earns_a_vector(day, embedder)


def stage_backfill_vectors(
    *, root: Path, index_root: Path, today: str, embedder: Embedder
) -> int:
    """Re-encode every closed day whose vectors are not the set its items earned.

    `build_day` replaced a day's embeddings block instead of merging it, so a
    day that ran five times kept the last run's vectors alone. That is fixed
    forward, and nothing revisits a closed day - a scheduled run only ever
    appends to the current one. The days already committed therefore stay part
    searchable until something goes back for them, which is this.

    **A short day is re-encoded whole rather than topped up**, and that is the
    one decision here worth the words. Measured 2026-08-26 over the 439 vectors
    the five closed days already carried: a re-encode reproduces them at a
    median cosine of 0.9936, not 1.0, and 413 of the 439 items get a different
    top-10 neighbour list. The same measurement against the day CI wrote hours
    earlier returns a median cosine of exactly 1.0 with 54 of 80 vectors
    byte-identical. So the gap is the code and not the machine: every closed day
    was written before `embed.encode` stopped padding and stopped batching, and
    its vectors carry an arithmetic the browser's query encoder no longer uses.
    Topping such a day up would leave one block holding two arithmetics, and a
    reader's query would then rank two populations it cannot compare fairly.
    One block, one encoder - the same rule `assemble.merge_embeddings` already
    applies across model ids.

    A day whose vectors already match is left untouched, so this is safe to
    dispatch twice. A day it does rewrite is written whole, which also lifts an
    older payload to the current schema shape.

    Rewriting a day makes its month's search index stale, so every month this
    touched is rebuilt before it returns. That is the same obligation assemble
    carries, and this is the only other writer of a committed day payload.

    This one fails rather than degrades. `build_embeddings` returns nothing
    when the encoder is missing because a day that cannot be searched still
    publishes; here there is no digest at risk and the vectors are the entire
    point, so a silent no-op would report success for work that did not happen.
    """
    if not embedder.available:
        LOG.error("no encoder at %s - nothing to backfill with", ONNX_RELPATH)
        return 1

    repaired = 0
    months: set[str] = set()
    for path in published_days(root):
        day = DigestDay.from_json(path.read_text(encoding="utf-8"))
        if not is_closed(day.date, today=today):
            LOG.info("skipped date=%s reason=open items=%s", day.date, len(day.items))
            continue
        earned = earns_a_vector(day, embedder)
        if not needs_backfill(day, embedder):
            LOG.info("skipped date=%s reason=complete vectors=%s", day.date, len(earned))
            continue

        before = len(day.embeddings.vectors) if day.embeddings else 0
        fresh = assemble.build_embeddings(day.items, embedder)
        if fresh is None or set(fresh.vectors) != earned:
            LOG.error(
                "date=%s the encoder answered for %s of the %s items that earned a vector",
                day.date,
                0 if fresh is None else len(fresh.vectors),
                len(earned),
            )
            return 1
        repaired_day = day.model_copy(
            update={"version": DigestDay.schema_version(), "embeddings": fresh}
        )
        assemble.write_atomic(path, repaired_day.to_json())
        repaired += 1
        months.add(assemble.month_of(day.date))
        LOG.info(
            "backfilled date=%s items=%s earned=%s vectors_before=%s vectors_after=%s",
            day.date,
            len(day.items),
            len(earned),
            before,
            len(fresh.vectors),
        )

    for month in sorted(months):
        index = assemble.rebuild_search_index(
            digest_root=root, index_root=index_root, month=month
        )
        LOG.info(
            "rebuilt search index month=%s entries=%s vectors=%s",
            month,
            len(index.entries),
            index.vector_bytes // index.dimensions,
        )

    LOG.info("backfill complete days_rewritten=%s", repaired)
    return 0


def _report_site_growth(
    size: retention.SiteSize,
    config: RetentionConfig,
    *,
    items_per_day: int,
) -> None:
    """The rate, the runway, and which directory is holding the bytes.

    Reporting only, and deliberately: `npm run bundle-gate` already fails a build
    on a crossed per-route ceiling and `cap_breach` above fails one past the
    configured cap, so a third gate here would be a third thing to keep green for
    no coverage it does not already have.

    The runway is the point of the whole step. A megabyte figure and a headroom
    figure are both levels, and no level yields a date - only a rate does.
    """
    named = retention.heaviest_directories(size, limit=6)
    if named:
        LOG.info(
            "site-weight by directory: %s",
            ", ".join(f"{name} {count / retention.BYTES_PER_MB:.1f} MB" for name, count in named),
        )

    if size.published_items <= 0 or items_per_day <= 0:
        LOG.info(
            "site-weight runway: unknown - %s published items in the measured tree at a "
            "%s item day ceiling. The size above is a level, and a level has no date in it",
            size.published_items,
            items_per_day,
        )
        return

    LOG.info(
        "site-weight rate: %.0f B per published item over %s items, so %.2f MB a "
        "published day at the %s item ceiling",
        size.bytes_per_published_item,
        size.published_items,
        retention.daily_growth_bytes(size, items_per_day) / retention.BYTES_PER_MB,
        items_per_day,
    )
    LOG.info(
        "site-weight runway: %.0f published days to the %s MB alarm point, %.0f to the "
        "%s MB Pages cap",
        retention.days_to_alarm(size, config, items_per_day),
        config.site_budget_mb,
        retention.days_to_cap(size, items_per_day, cap_mb=config.pages_hard_cap_mb),
        config.pages_hard_cap_mb,
    )


def stage_site_weight(
    tree: Path,
    config: RetentionConfig,
    *,
    items_per_day: int = 0,
) -> int:
    """Measure the built bundle against the alarm point and the Pages cap.

    `tree` is the directory the Pages deploy uploads, and it only exists after
    the site is built - so this runs as its own step after `npm run build`, in
    every job that builds. It is deliberately not part of `assemble`: that stage
    runs before the build and can only see the committed payloads, which are a
    different tree eighteen times smaller.

    There is no default tree. A default is how this pointed at the wrong one.

    The cap comes from `retention.pages_hard_cap_mb` and not from a flag. A flag
    is a per-invocation override, which is the one shape a ceiling must not have -
    the job that is about to breach it is the job that would pass the flag. The
    config field is bounded, so the only edit that reaches this line is one that
    makes the gate stricter.

    Three outcomes: an empty tree fails, because a measurement of nothing reads
    exactly like a site inside budget; over the cap fails, because those bytes
    cannot be published; over the alarm point reports and passes, because they
    still can. Both outcomes that pass also print the rate and the runway, and
    not only the one over the alarm point - the day the alarm fires is not the
    day anybody wanted to first learn the date.
    """
    cap_mb = config.pages_hard_cap_mb
    size = retention.measure(tree, published_items=retention.count_published_items(tree))
    if size.files == 0:
        LOG.error(
            "site-weight measured 0 files under %s - build the site first. "
            "A measurement of nothing passes every ceiling",
            tree.as_posix(),
        )
        return 1

    breach = retention.cap_breach(size, cap_mb=cap_mb)
    if breach is not None:
        LOG.error("%s", breach)
        return 1

    LOG.info(
        "site-weight %s: %.1f MB in %s files, %.0f MB left to the %s MB Pages cap",
        tree.as_posix(),
        size.megabytes,
        size.files,
        retention.headroom_mb(size, cap_mb=cap_mb),
        cap_mb,
    )
    _report_site_growth(size, config, items_per_day=items_per_day)

    alarm = retention.budget_alarm(size, config)
    if alarm is not None:
        # An Actions workflow command, so the line lands on the run's summary
        # rather than three thousand lines into a log nobody opens. Outside
        # Actions it is one more printed line and costs nothing.
        print(f"::warning title=Published site approaching the Pages cap::{alarm}")
        LOG.warning("%s", alarm)
    return 0


# --- validate-days ------------------------------------------------------------


def _picture_faults(public_root: Path, day: DigestDay) -> list[str]:
    """Where a day's payload and its picture directory disagree.

    The defect this exists for shipped on 2026-08-24. A per-process counter that
    restarted at 1 let a later run of the day overwrite an earlier run's
    `india-01.svg` while the payload still named both items, so 32 declared
    visuals sat over 18 files and 14 files were each claimed by two stories. 28
    readers saw a picture and 14 of those were drawn from another article's
    numbers, under alt text describing figures that were not in the image.
    Nothing failed: every file existed, every item validated, the page rendered.

    Three disagreements, three different faults. Two stories on one path means
    one of them shows the other's chart. A path with no file is a broken image.
    A file no story names is weight against the 1 GB Pages cap (Rule #2) that
    renders nowhere, and it is what a repaired collision leaves behind.

    It is checked here rather than by a test per committed day because the day
    that can still be wrong is the one being written. A day already published is
    frozen, and re-checking every one of them costs more every day the pipeline
    runs (Rule #12).
    """
    declared = [
        item.visual.path
        for item in day.items
        if item.visual is not None and item.visual.path is not None
    ]
    faults: list[str] = []
    shared = sorted(name for name, claims in Counter(declared).items() if claims > 1)
    if shared:
        faults.append(f"names one picture on two stories: {shared}")
    absent = sorted(name for name in declared if not (public_root / name).is_file())
    if absent:
        faults.append(f"names a picture file that is not there: {absent}")
    orphans = sorted(assets_in_day(public_root, day.date) - set(declared))
    if orphans:
        faults.append(f"carries picture files no story names: {orphans}")
    return faults


def _day_faults(path: Path, public_root: Path) -> list[str]:
    """What is wrong with one committed day, in sentences, or an empty list.

    Both shapes are asked for, because a day has two readers and they read
    different files. `DigestDay` is what the build opens off disk. `DigestView`
    is the projection a reader's browser fetches, and a day that is fine on disk
    can still project to something the served contract refuses - a story with no
    key point, say, which the build never looked at because that story sits past
    the document's seed.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        return [f"cannot be read: {error.strerror or error}"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        return [f"is not JSON: {error}"]
    if not isinstance(parsed, dict):
        return [f"is a {type(parsed).__name__}, not a day"]

    faults: list[str] = []
    try:
        faults.extend(_picture_faults(public_root, DigestDay.model_validate(parsed)))
    except ValidationError as error:
        faults.append(f"fails digest-day.schema.json: {error.error_count()} problems\n{error}")
    try:
        DigestView.project(parsed)
    except ValidationError as error:
        faults.append(f"fails digest-view.schema.json: {error.error_count()} problems\n{error}")
    except (TypeError, AttributeError, ValueError) as error:
        # A shape nobody anticipated. It still fails, and it still names the day
        # - a stack trace on day three of twelve says neither which day nor why.
        faults.append(f"cannot be projected for serving: {type(error).__name__}: {error}")
    return faults


def stage_validate_days(root: Path, only: Sequence[str] = ()) -> int:
    """Committed days against the two contracts their readers hold.

    **This exists because prerendering stopped proving it.** Until the reading
    decisions were split on 2026-09-01, every story a day published was serialised
    into a document at build time, so a story the contract refused took the
    build down before it could be merged. A reading document now carries a seed
    and a browser fetches the rest, so the build never opens the stories past
    the seed and a broken one reaches a reader instead of a log. The guarantee
    is weaker than it was and it is written down rather than hidden: a broken
    day can no longer be built, it can only no longer be merged.

    `only` names the days to open, as `YYYY-MM-DD`. Empty means every committed
    day, which is what a contract change needs and nothing else does: a day
    already published is frozen, so the only thing that can invalidate it is a
    change to the shape it is read through. Measured 2026-09-05 on an i7-1265U,
    16 committed days took 6.6 s to 7.1 s - about 0.27 s a day on top of a fixed
    start, so a year of publishing is around 100 s every time this runs
    (Rule #12). A run that wrote one day names that day.

    An empty tree fails, and so does a named day that is not there. A validator
    that checked nothing prints the same line as one that checked every day,
    which is the failure `site-weight` already has a rule about.
    """
    days = published_days(root)
    if not days:
        LOG.error(
            "validate-days found no digest.json under %s - a run over nothing passes "
            "every contract",
            root.as_posix(),
        )
        return 1

    if only:
        wanted = set(only)
        days = [path for path in days if _day_of(path) in wanted]
        missing = sorted(wanted - {_day_of(path) for path in days})
        if missing:
            LOG.error("validate-days was asked for days that are not committed: %s", missing)
            return 1

    broken = 0
    for path in days:
        faults = _day_faults(path, root.parent)
        broken += bool(faults)
        for fault in faults:
            LOG.error("%s %s", _day_of(path), fault)

    if broken:
        LOG.error(
            "validate-days: %s of %s committed days do not match the contracts their "
            "readers hold. A reader's browser fetches this file and cannot be upgraded",
            broken,
            len(days),
        )
        return 1

    LOG.info("validate-days: %s committed days match both contracts", len(days))
    return 0


def _day_of(path: Path) -> str:
    """`2026-09-01` out of `.../2026/09/01/digest.json`, for a log line."""
    parts = path.parts[-4:-1]
    return "-".join(parts) if len(parts) == 3 else path.as_posix()


# --- entry point --------------------------------------------------------------


def _plan_path(date: str) -> Path:
    return _run_dir(date) / "plan.json"


def _load_plan(date: str) -> RunPlan:
    return RunPlan.read(_plan_path(date))


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


def _scores_this_run(
    observability: ObservabilityConfig, *, run_id: str, flag_allows: bool
) -> bool:
    """Whether the work stage should load a scorer for this run at all.

    Three things have to agree. `observability.evaluation_enabled` is the
    standing decision and is the default; `--no-faithfulness` overrides it for
    one invocation, because a flag beats a file and no flag turns the scorer
    back on; and at a rate below one the run has to be drawn.

    The draw is per run, so it is taken here rather than inside the item loop -
    a run scores everything or nothing (`evals/sampling.py`).
    """
    if not observability.evaluation_enabled:
        LOG.info("faithfulness scoring is off in config")
        return False
    if not flag_allows:
        return False
    if not sampling.run_is_sampled(run_id, observability.sample_rate):
        LOG.info(
            "run not drawn for scoring run_id=%s sample_rate=%s",
            run_id,
            observability.sample_rate,
        )
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idhazh", description=__doc__)
    parser.add_argument(
        "stage",
        choices=(
            "plan",
            "shards",
            "work",
            "record",
            "counters",
            "visuals",
            "assemble",
            "harvest",
            "dedupe-ledgers",
            "prune-stamp",
            "prune-state",
            "run",
            "validate",
            "decide",
            "qualify",
            "qualify-canaries",
            "qualify-decide",
            "backfill-vectors",
            "site-weight",
            "validate-days",
        ),
    )
    parser.add_argument("--date", default=None, help="Defaults to today, UTC.")
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    parser.add_argument("--commit", default="0" * 40)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument(
        "--execution",
        type=int,
        default=None,
        help=(
            "The identity of this execution, which becomes the run id after the date. "
            "CI passes the GitHub run id: GitHub allocates it, it is unique across "
            "every run of every workflow here, and no second execution can compute "
            "it. Left out, the run counts off the last committed manifest, which two "
            "overlapping runs were able to read the same answer from."
        ),
    )
    parser.add_argument(
        "--no-faithfulness",
        action="store_true",
        help="Skip the scorer. The digest still publishes; the ledger stays empty.",
    )
    parser.add_argument(
        "--visuals",
        action="store_true",
        help="Include the visuals stage in a full run. It needs the visual planner served.",
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
            "Take at most this many stories from each vertical when planning. For "
            "validation only: how big a day is is what a reader wants, not what a "
            "measurement needs."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Deterministic repeats per frozen article. The determinism gate reads them.",
    )
    parser.add_argument(
        "--corpus-per-shard",
        type=int,
        default=10,
        help="How many frozen articles one qualification shard replays.",
    )
    parser.add_argument(
        "--candidate-revision",
        default="",
        help="The immutable repository revision the candidate weights were taken from.",
    )
    parser.add_argument(
        "--candidate-bytes",
        type=int,
        default=0,
        help="The byte count the adoption target declares for the candidate GGUF.",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="The GGUF the runtime opened. Its bytes are digested, not the config's claim.",
    )
    parser.add_argument(
        "--job-budget-minutes",
        type=float,
        default=330.0,
        help="The dispatch's own per-job bound. The budget gate is measured against it.",
    )
    parser.add_argument(
        "--counters-file",
        type=Path,
        default=Path("llama-metrics.prom"),
        help=(
            "The GET /metrics body this shard's model server returned at job end. "
            "Not spelled --metrics: that is llama-server's own flag, and no workflow "
            "step may write one by hand."
        ),
    )
    parser.add_argument(
        "--job-started-at",
        default="",
        help=(
            "Epoch seconds stamped by the first step of the shard job. The counters "
            "row records the difference against its own scrape time. Empty means no "
            "stamp, and the cell then stays empty rather than reading zero."
        ),
    )
    parser.add_argument(
        "--cpu-model",
        default="",
        help=(
            "The host's /proc/cpuinfo `model name` line. `ubuntu-latest` names the "
            "runner image, not the processor, and this project has measured a 3.1x "
            "throughput swing between hosts."
        ),
    )
    parser.add_argument(
        "--cpu-stat-at-start",
        default="",
        help=(
            "The aggregate `cpu` line of /proc/stat, read by the first step of the shard "
            "job. Differenced against the reading at the scrape, it says what share of "
            "the host's processor seconds the job actually used."
        ),
    )
    parser.add_argument(
        "--cpu-stat-at-end",
        default="",
        help="The same /proc/stat line, read at the scrape. The other end of the window.",
    )
    parser.add_argument(
        "--rss-samples-file",
        type=Path,
        default=Path("rss-samples.tsv"),
        help=(
            "The memory sampler's own file. Its `llama_vmhwm_kb` column is the high-water "
            "mark that says whether a candidate model fits the runner's 16 GB."
        ),
    )
    parser.add_argument(
        "--server-log",
        type=Path,
        default=Path("llama-server.log"),
        help=(
            "llama-server's own log. The two lines it brackets a model load with give the "
            "fixed cost `run.shard_size` exists to amortise."
        ),
    )
    parser.add_argument(
        "--site-tree",
        type=Path,
        default=None,
        help=(
            "The built bundle `site-weight` measures - the directory the Pages deploy "
            "uploads. Required, and deliberately without a default: a default is how "
            "this came to measure the committed payloads instead of the site."
        ),
    )
    parser.add_argument(
        "--day",
        action="append",
        default=[],
        metavar="YYYY-MM-DD",
        help=(
            "A day for `validate-days` to open, repeatable. Every committed day when "
            "this is not given, which is what a contract change needs and nothing else "
            "does - a published day is frozen, so only the shape it is read through can "
            "invalidate it. A run that wrote one day names that day."
        ),
    )
    parser.add_argument(
        "--digest-root",
        type=Path,
        default=PUBLIC_ROOT,
        help=(
            "The committed day payloads `validate-days` reads. It defaults to the "
            "real tree, unlike --site-tree, because there is exactly one committed "
            "tree and a run against the wrong one cannot silently pass."
        ),
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=CORPUS_ROOT,
        help="The training window `harvest` rolls. Never the reference set.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Harvest even when finetune.harvest_every_days says it is not due yet.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what the telemetry fold would do and change nothing on disk.",
    )
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    logging.basicConfig(
        level=settings.app.logging.level.value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    if args.stage == "site-weight":
        # Placed above the fetcher because measuring a directory reads no socket,
        # and starting one to do it would read every host's robots.txt for nothing.
        if args.site_tree is None:
            parser.error("site-weight needs --site-tree: the built bundle to measure")
        return stage_site_weight(
            args.site_tree,
            settings.app.retention,
            items_per_day=settings.app.run.safety_ceiling_per_run,
        )

    if args.stage == "validate-days":
        # Above the fetcher for the same reason site-weight is: reading committed
        # files decides nothing about the open web, and starting a fetcher to do
        # it would read every host's robots.txt for nothing.
        return stage_validate_days(args.digest_root, args.day)

    if args.stage == "prune-stamp":
        # Above the fetcher for the same reason: it rewrites one committed field.
        return stage_prune_stamp(corpus_dir=args.corpus_dir, date=args.date or _today())

    if args.stage == "dedupe-ledgers":
        # Above the fetcher because it reads and rewrites committed files only.
        # It runs from inside a commit step, between a rebase and a push, and a
        # step that opened a socket there would read the open web to decide what
        # to keep.
        return stage_dedupe_ledgers()

    if args.stage == "prune-state":
        # And this one only reads and deletes committed files. A fold that opened
        # a socket would be reading the open web to decide what to delete.
        pruned_on = args.date or _today()
        return stage_prune_state(
            observability=settings.app.observability,
            collect=settings.app.collect,
            retention_config=settings.app.retention,
            run_id=_run_id(pruned_on, args.execution),
            today=date_type.fromisoformat(pruned_on),
            dry_run=args.dry_run,
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

    if args.stage == "qualify":
        stage_qualify(
            settings=settings,
            date=date,
            shard=args.shard,
            shards=args.shards,
            repeats=args.repeats,
            corpus_per_shard=args.corpus_per_shard,
            candidate=_candidate_identity(settings, args),
            scorer=_scorer(not args.no_faithfulness),
            commit_sha=args.commit,
            runner=args.runner,
            fetcher=read_url,
        )
        return 0

    if args.stage == "qualify-canaries":
        return stage_qualify_canaries(settings=settings, date=date)

    if args.stage == "backfill-vectors":
        # `--date` names the day this treats as still open, and it is clamped to
        # today so a future date cannot bring the live day into scope. The live
        # day is the one the scheduled pipeline is appending to.
        return stage_backfill_vectors(
            root=PUBLIC_ROOT,
            index_root=_index_root(),
            today=min(date, _today()),
            embedder=Embedder(config.REPO_ROOT, settings.app.assist),
        )

    if args.stage == "qualify-decide":
        return stage_qualify_decide(
            settings=settings,
            date=date,
            job_budget_minutes=args.job_budget_minutes,
            runner=args.runner,
        )

    if args.stage == "shards":
        # stdout carries the answer and stderr carries the logs, so a caller
        # reads one number without parsing a log line.
        print(shard_count(len(_load_plan(date).items), run=settings.app.run))
        return 0

    if args.stage in ("plan", "run"):
        plan = stage_plan(
            date, settings=settings, fetcher=read_url, cap=args.cap, execution=args.execution
        )
        assemble.write_atomic(_plan_path(date), plan.to_json())
        LOG.info("planned date=%s items=%s feeds=%s", date, len(plan.items), plan.feeds_read)

    if args.stage in ("work", "run"):
        work_plan = _load_plan(date)
        stage_work(
            work_plan,
            settings=settings,
            scorer=_scorer(
                _scores_this_run(
                    settings.app.observability,
                    run_id=work_plan.run_id,
                    flag_allows=not args.no_faithfulness,
                )
            ),
            shard=args.shard,
            shards=args.shards,
            fetcher=read_url,
        )

    if args.stage == "record":
        stage_record(_load_plan(date), shard=args.shard, shards=args.shards)
        return 0

    if args.stage == "counters":
        stage_counters(
            _load_plan(date),
            metrics_path=args.counters_file,
            shard=args.shard,
            shards=args.shards,
            job_started_at=int(args.job_started_at) if args.job_started_at else None,
            cpu_model=args.cpu_model,
            cpu_stat_at_start=args.cpu_stat_at_start,
            cpu_stat_at_end=args.cpu_stat_at_end,
            rss_samples_path=args.rss_samples_file,
            server_log_path=args.server_log,
        )
        return 0

    if args.stage == "visuals" or (args.stage == "run" and args.visuals):
        stage_visual_planner(_load_plan(date), settings=settings)

    if args.stage in ("assemble", "run"):
        stage_assemble(
            _load_plan(date), settings=settings, commit_sha=args.commit, runner=args.runner
        )

    if args.stage == "harvest":
        stage_harvest(
            date,
            settings=settings,
            corpus_dir=args.corpus_dir,
            force=args.force,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
