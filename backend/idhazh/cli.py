"""The pipeline, as three stages a person can run one at a time.

Each stage takes a file and writes a file, which is the whole reason the
pipeline can be sharded across disposable machines and re-run cheaply. A stage
that only works as part of the whole is a stage nobody can debug.

    idhazh plan       read feeds, rank, cap        -> run/<date>/plan.json
    idhazh work       fetch, extract, summarize, score -> run/<date>/items/*
    idhazh assemble   collect what finished        -> frontend/public/... + evals/

`idhazh run` is the three in order, which is what a developer wants and what
the daily workflow calls.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from idhazh import assemble, config, discover, extract, fetch, rank, summarize
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals import metrics, score, writer
from idhazh.evals.hhem import HHEM_SCORER_ID, HhemScorer, dual_score, weights_digest
from idhazh.fingerprint import build_inputs, text_digest
from idhazh.llm.server import Completion, post
from idhazh.sanitize import SANITIZER_VERSION

LOG: Final = logging.getLogger("idhazh")
VAR_ROOT: Final = config.REPO_ROOT / "backend" / "var" / "run"
PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "digest"
LEDGER: Final = config.REPO_ROOT / writer.LEDGER_RELPATH


def _run_dir(date: str) -> Path:
    return VAR_ROOT / date


def _today() -> str:
    return assemble.utc_now()[:10]


# --- plan -------------------------------------------------------------------


def stage_plan(date: str, *, settings: config.Settings) -> RunPlan:
    """Read every live feed, rank the pool, take each vertical's cap. No model."""
    candidates: list[discover.Candidate] = []
    read = failed = 0
    for feed in settings.sources.feeds:
        robots = _robots_for(feed.url, settings)
        result = fetch.fetch(feed.url, config=settings.app.extract, robots_txt=robots)
        if not result.ok:
            failed += 1
            LOG.warning("feed unavailable id=%s reason=%s", feed.id, result.detail)
            continue
        read += 1
        candidates.extend(discover.candidates_from_feed(feed, result.body))

    front_page: set[str] = set()
    for salience in settings.sources.salience:
        robots = _robots_for(salience.url, settings)
        result = fetch.fetch(salience.url, config=settings.app.extract, robots_txt=robots)
        if result.ok:
            front_page |= discover.salience_urls(result.body)

    watchlist_keys: frozenset[str] = frozenset()
    verticals = []
    items: list[PlannedItem] = []
    for vertical in settings.taxonomy.verticals:
        live = discover.live(settings.sources.feeds, vertical.id)
        summary, planned = rank.plan_vertical(
            vertical,
            [c for c in candidates if c.vertical == vertical.id],
            config=settings.app.collect,
            live_feeds=len(live),
            watchlist_keys=watchlist_keys,
            front_page_keys=frozenset(front_page),
        )
        verticals.append(summary)
        items.extend(planned)

    return RunPlan(
        version=RunPlan.schema_version(),
        date=date,
        run_id=f"{date}-1",
        generated_at=assemble.utc_now(),
        feeds_read=read,
        feeds_failed=failed,
        verticals=verticals,
        items=items,
    )


_ROBOTS_CACHE: dict[str, str | None] = {}


def _robots_for(url: str, settings: config.Settings) -> str | None:
    """One robots read per host per run. An unreadable one stays a refusal."""
    from urllib.parse import urlsplit

    host = urlsplit(url).netloc
    if host not in _ROBOTS_CACHE:
        result = fetch.fetch(fetch.robots_url(url), config=settings.app.extract, robots_txt="")
        _ROBOTS_CACHE[host] = result.body.decode("utf-8", "replace") if result.ok else None
    return _ROBOTS_CACHE[host]


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


def stage_work(
    plan: RunPlan,
    *,
    settings: config.Settings,
    scorer: object | None,
    shard: int = 0,
    shards: int = 1,
) -> None:
    """Fetch, extract, summarize and score one item at a time, writing as it goes."""
    inference = settings.app.models.inference
    model = settings.app.models.summarize
    inputs = build_inputs(
        model=model,
        model_sha256=model.sha256 or "0" * 64,
        inference=inference,
        truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
        runtime_build="llama-server-local",
        chat_template=model.id,
        prompt=summarize.system_prompt(),
        output_schema=summarize.output_schema_text(),
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
    for item in mine:
        started = time.monotonic()
        article = _fetch_one(item, settings)
        assemble.write_atomic(items_dir / f"{item.item_id}.article.json", article.to_json())
        if article.status is not ArticleStatus.OK:
            LOG.info("item degraded id=%s reason=%s", item.item_id, article.failure_detail)
            continue

        summary = _summarize_one(article, settings, fingerprint)
        summary = summary.model_copy(
            update={"duration_ms": int((time.monotonic() - started) * 1000)}
        )
        assemble.write_atomic(items_dir / f"{item.item_id}.summary.json", summary.to_json())
        if summary.status is not SummaryStatus.OK or scorer is None:
            continue

        seen = article.text or ""
        hhem, hhem_full = dual_score(
            scorer,  # type: ignore[arg-type]
            seen_text=seen,
            full_text=seen,
            summary=summary.summary or "",
        )
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
        assemble.write_atomic(items_dir / f"{item.item_id}.eval.json", row.to_json())
        LOG.info("item scored id=%s band=%s", item.item_id, row.band.value)


def _fetch_one(item: PlannedItem, settings: config.Settings) -> Article:
    robots = _robots_for(item.canonical_url, settings)
    result = fetch.fetch(item.canonical_url, config=settings.app.extract, robots_txt=robots)
    return extract.to_article(
        item, result, config=settings.app.extract, fetched_at=assemble.utc_now()
    )


def _summarize_one(article: Article, settings: config.Settings, fingerprint: str) -> Summary:
    inference = settings.app.models.inference
    model_id = settings.app.models.summarize.id
    payload = summarize.build_request(article, model_id=model_id, inference=inference)
    try:
        completion = post(payload, timeout=settings.app.run.shard_timeout_minutes * 60)
    except OSError as error:
        completion = Completion(content="")
        LOG.warning("model unreachable id=%s reason=%s", article.item_id, type(error).__name__)
    return summarize.to_summary(
        article,
        completion,
        model_id=model_id,
        pipeline_fingerprint=fingerprint,
        generated_at=assemble.utc_now(),
        evaluation=settings.app.evaluation,
    )


# --- assemble ----------------------------------------------------------------


def stage_assemble(plan: RunPlan, *, settings: config.Settings, commit_sha: str) -> DigestDay:
    """Collect whatever finished, publish it, and append the ledger."""
    items_dir = _run_dir(plan.date) / "items"
    names = assemble.source_names(settings.sources)
    digest_items = []
    summaries: list[Summary] = []
    rows = []

    for item in plan.items:
        article_path = items_dir / f"{item.item_id}.article.json"
        summary_path = items_dir / f"{item.item_id}.summary.json"
        eval_path = items_dir / f"{item.item_id}.eval.json"
        if not (article_path.exists() and summary_path.exists()):
            continue
        article = Article.from_json(article_path.read_text(encoding="utf-8"))
        summary = Summary.from_json(summary_path.read_text(encoding="utf-8"))
        summaries.append(summary)
        if summary.status is not SummaryStatus.OK:
            continue

        # An item publishes with a band whether or not the faithfulness scorer
        # ran. The counterweights are free and always available, and they never
        # claim the top band on their own.
        if eval_path.exists():
            row = EvalRow.from_json(eval_path.read_text(encoding="utf-8"))
            rows.append(row)
            band = row.band
        else:
            band = score.counterweight_band(
                summary.summary or "", article.text or "", settings.app.evaluation
            )
        digest_items.append(
            assemble.to_digest_item(
                article=article,
                summary=summary,
                band=band,
                source_name=names.get(article.source_id, article.source_id),
                run_n=1,
            )
        )

    target = assemble.day_dir(PUBLIC_ROOT, plan.date)
    previous_day = _load_day(target / "digest.json")
    previous_manifest = _load_manifest(target / "run.json")
    run_n = (previous_manifest.runs[-1].n + 1) if previous_manifest else 1
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
        runner="local",
        started_at=plan.generated_at,
        completed_at=generated_at,
        config_digests=settings.digests,
        site_bytes=site_bytes,
        site_files=site_files,
    )
    assemble.write_atomic(target / "run.json", manifest.to_json())
    landed = writer.append(LEDGER, rows)
    LOG.info(
        "published date=%s items=%s partial=%s eval_rows=%s",
        plan.date,
        len(day.items),
        day.partial,
        landed,
    )
    return day


def _load_day(path: Path) -> DigestDay | None:
    return DigestDay.from_json(path.read_text(encoding="utf-8")) if path.exists() else None


def _load_manifest(path: Path) -> RunManifest | None:
    return RunManifest.from_json(path.read_text(encoding="utf-8")) if path.exists() else None


# --- entry point --------------------------------------------------------------


def _plan_path(date: str) -> Path:
    return _run_dir(date) / "plan.json"


def _load_plan(date: str) -> RunPlan:
    return RunPlan.from_json(_plan_path(date).read_text(encoding="utf-8"))


def _scorer(enabled: bool) -> object | None:
    if not enabled:
        LOG.warning("faithfulness scoring disabled - no eval rows will be written")
        return None
    scorer = HhemScorer()
    scorer.load()
    return scorer


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="idhazh", description=__doc__)
    parser.add_argument("stage", choices=("plan", "work", "assemble", "run"))
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
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    logging.basicConfig(
        level=settings.app.logging.level.value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    date = args.date or _today()

    if args.stage in ("plan", "run"):
        plan = stage_plan(date, settings=settings)
        assemble.write_atomic(_plan_path(date), plan.to_json())
        LOG.info("planned date=%s items=%s feeds=%s", date, len(plan.items), plan.feeds_read)

    if args.stage in ("work", "run"):
        stage_work(
            _load_plan(date),
            settings=settings,
            scorer=_scorer(not args.no_faithfulness),
            shard=args.shard,
            shards=args.shards,
        )

    if args.stage in ("assemble", "run"):
        stage_assemble(_load_plan(date), settings=settings, commit_sha=args.commit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
