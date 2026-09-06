"""Does this feed address actually work, all the way through to prose?

Read-only, never a stage, and never on the daily pipeline's critical path. It
runs when somebody is about to add a feed to `config/sources.json`, or wants to
re-check one already in it.

**Why it exists.** On 2026-08-29 forty feeds were retired at once. Twenty-four
of them had never published a single item while consuming 43 of every run's 160
slots, and three were configured with the address of a web page rather than a
feed - every read returned HTTP 200 and zero items, so feed health recorded a
healthy feed for weeks and the candidate pool gained nothing. A feed read can
succeed and still be worthless, and no gate noticed. This is that gate, run by
hand before the config changes rather than by the ledger six weeks after.

**The bar it checks** is the one `docs/architecture/sources/discovery.md` states:
a feed must parse cleanly, and one article behind it must return readable prose
through the production path. Both halves matter and the second is the one that
fails - `openai-news` served a perfect feed whose articles answered 4xx, and
`venturebeat-ai` rate-limited every article request.

**It uses the production path, not an imitation.** The configured user agent,
the public-address check, the `robots.txt` policy, the bounded retries,
`feedparser`, the publisher-declared paywall check and the prose extractor are
the pipeline's own, reached through `cli.live_fetcher` and `extract.to_article`.
A verdict here is a `FailureCode` from the same vocabulary an item-health row
carries, so a result drops straight into the reasons table in `discovery.md`.

**This touches the network, which is why it is a utility and not a test**
(Rule #7). It is also why a result is evidence about the machine it ran on and
not qualification on the runner: several publishers serve a developer machine
and refuse a GitHub address. The report says which host it ran from so nobody
mistakes one for the other.

Usage, from the root of a checkout:

    # Ad hoc, before editing the config.
    python backend/utilities/probe_feeds.py https://example.com/feed.xml

    # Everything currently live, or one vertical of it.
    python backend/utilities/probe_feeds.py --from-config feeds
    python backend/utilities/probe_feeds.py --from-config feeds --vertical ai

    # Re-test a tombstone before un-retiring it.
    python backend/utilities/probe_feeds.py --from-config retired --id openai-news

Spans go to `backend/var/probes/` by default, and to Langfuse as well when the
environment names a host - the same rule the pipeline follows, so the trace of a
probe opens in the same viewer as the trace of a run. `--report` writes one JSON
object per feed for a later diff.

Exit code 0 when every probed feed cleared the bar, 1 when any did not, and 2
when there was nothing to probe.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import socket
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import feedparser

from idhazh import assemble, cli, config, discover, extract, telemetry
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.taxonomy import SourceTier
from idhazh.fetch import FetchResult

LOG: Final = logging.getLogger("idhazh.probe_feeds")

#: Where a probe's spans land when nobody names a path. Under `backend/var/`,
#: which is gitignored: a probe is a question somebody asked once, not a record
#: of the pipeline, so it does not belong in the committed trace window.
DEFAULT_TRACE_DIR: Final = Path("backend/var/probes")

#: Vertical and tier stand in for the config row an ad-hoc address does not have
#: yet. Neither changes the verdict - they exist because `PlannedItem` needs an
#: address of the form `<vertical>-NN` and `Candidate` carries a tier.
ADHOC_VERTICAL: Final = "ai"
ADHOC_TIER: Final = SourceTier.TRADE_PRESS

#: Host labels that name no publisher, dropped when an address is turned into a
#: readable id.
_HOST_NOISE: Final = frozenset({"www", "com", "org", "net", "io", "co", "feeds", "rss"})

#: A feed that parses but offers nothing linkable is the failure this tool was
#: written for, and no existing code names it, so it is named here. Everything
#: else reuses the pipeline's own vocabulary.
NOT_A_FEED: Final = "not_a_feed"
NO_DATED_ENTRIES: Final = "no_dated_entries"


@dataclass(slots=True)
class Phase:
    """One timed step, and what it returned. Absent until it is attempted."""

    ms: int | None = None
    outcome: str | None = None
    status: int | None = None
    detail: str | None = None


@dataclass(slots=True)
class ArticleProbe:
    """One page behind a feed, and whether the extractor got prose out of it."""

    url: str
    fetch_ms: int
    extract_ms: int
    http_status: int | None
    outcome: str
    words: int
    verdict: str
    detail: str | None

    @property
    def ms(self) -> int:
        return self.fetch_ms + self.extract_ms

    @property
    def read(self) -> bool:
        return self.verdict == ArticleStatus.OK.value


@dataclass(slots=True)
class ProbeRow:
    """One feed, one verdict, and every number the verdict was taken from."""

    id: str
    url: str
    vertical: str
    probed_at: str
    robots: str | None = None
    feed: Phase = field(default_factory=Phase)
    parse: Phase = field(default_factory=Phase)
    feed_title: str | None = None
    entries: int = 0
    linkable: int = 0
    dated: int = 0
    malformed: str | None = None
    articles: list[ArticleProbe] = field(default_factory=list)
    verdict: str = FailureCode.NOT_ATTEMPTED.value
    passed: bool = False

    @property
    def total_ms(self) -> int:
        spent = [self.feed.ms, self.parse.ms, *(article.ms for article in self.articles)]
        return sum(ms for ms in spent if ms)

    @property
    def words(self) -> int:
        return max((article.words for article in self.articles), default=0)


def _failure_of(result: FetchResult) -> str:
    """A fetch outcome as the failure vocabulary an item-health row would carry."""
    if result.robots is RobotsOutcome.DENIED:
        return FailureCode.ROBOTS_DENIED.value
    if result.robots is RobotsOutcome.UNREACHABLE:
        return FailureCode.ROBOTS_UNREACHABLE.value
    if result.outcome is FetchOutcome.BLOCKED:
        return FailureCode.BLOCKED_ADDRESS.value
    if result.status == 429:
        return FailureCode.HTTP_RATE_LIMITED.value
    if result.status and 400 <= result.status < 500:
        return FailureCode.HTTP_CLIENT_ERROR.value
    if result.status and result.status >= 500:
        return FailureCode.HTTP_SERVER_ERROR.value
    return FailureCode.NETWORK_ERROR.value


def _timed[T](call: Callable[[], T]) -> tuple[T, int]:
    started = time.monotonic()
    value = call()
    return value, int((time.monotonic() - started) * 1000)


def probe_feed(
    feed: FeedDef,
    *,
    fetcher: cli.Fetcher,
    settings: config.Settings,
    tracer: telemetry.Tracer,
    articles: int,
) -> ProbeRow:
    """Read one feed, then read up to `articles` of the pages behind it.

    More than one article is worth asking for on a publisher that mixes free and
    paywalled pages: one sample can condemn a feed that mostly works, or clear
    one that mostly does not. The feed passes if any sampled article yields
    prose, and the row keeps every attempt so the ratio is visible.
    """
    row = ProbeRow(
        id=feed.id,
        url=feed.url,
        vertical=feed.vertical,
        probed_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    with tracer.trace(f"probe-{feed.id}"):
        with tracer.span(telemetry.SpanName.FETCH) as span:
            result, row.feed.ms = _timed(lambda: fetcher(feed.url))
            span.set(telemetry.AttrKey.SOURCE_ID, feed.id)
            span.set(telemetry.AttrKey.OUTCOME, result.outcome.value)
            span.set(telemetry.AttrKey.HTTP_STATUS, result.status)
            span.set(telemetry.AttrKey.BODY_BYTES, len(result.body))
            span.set(
                telemetry.AttrKey.ROBOTS_OUTCOME,
                result.robots.value if result.robots else None,
            )
        row.robots = result.robots.value if result.robots else None
        row.feed.outcome = result.outcome.value
        row.feed.status = result.status
        row.feed.detail = result.detail
        if not result.ok:
            row.verdict = _failure_of(result)
            return row

        parsed, row.parse.ms = _timed(lambda: feedparser.parse(result.body))
        row.feed_title = (getattr(parsed, "feed", None) or {}).get("title")
        row.entries = len(parsed.entries)
        if getattr(parsed, "bozo", 0):
            row.malformed = f"{type(getattr(parsed, 'bozo_exception', '')).__name__}"

        candidates = discover.candidates_from_feed(feed, result.body)
        row.linkable = len(candidates)
        row.dated = sum(1 for candidate in candidates if candidate.published_at)
        if not candidates:
            row.verdict = NOT_A_FEED
            return row

        for index, candidate in enumerate(candidates[:articles], start=1):
            row.articles.append(
                _probe_article(
                    candidate,
                    feed=feed,
                    index=index,
                    fetcher=fetcher,
                    settings=settings,
                    tracer=tracer,
                )
            )

    if any(article.read for article in row.articles):
        row.passed = True
        # An undated feed still works - freshness falls back to first sight - so
        # this is reported beside the verdict and never fails the feed for it.
        row.verdict = ArticleStatus.OK.value if row.dated else NO_DATED_ENTRIES
        return row
    row.verdict = row.articles[0].verdict
    return row


def _probe_article(
    candidate: discover.Candidate,
    *,
    feed: FeedDef,
    index: int,
    fetcher: cli.Fetcher,
    settings: config.Settings,
    tracer: telemetry.Tracer,
) -> ArticleProbe:
    """One page behind the feed, through the real extractor."""
    item = PlannedItem(
        item_id=f"{feed.vertical}-{index:02d}",
        url_key=derive_url_key(candidate.canonical_url),
        source_url=candidate.source_url,
        canonical_url=candidate.canonical_url,
        source_id=feed.id,
        tier=feed.tier,
        source_form=feed.form,
        vertical=feed.vertical,
        title=candidate.title,
        rank_score=0.0,
    )
    with tracer.span(telemetry.SpanName.FETCH) as span:
        result, fetch_ms = _timed(lambda: fetcher(candidate.canonical_url))
        span.set(telemetry.AttrKey.URL_KEY, item.url_key)
        span.set(telemetry.AttrKey.OUTCOME, result.outcome.value)
        span.set(telemetry.AttrKey.HTTP_STATUS, result.status)
        span.set(telemetry.AttrKey.BODY_BYTES, len(result.body))

    with tracer.span(telemetry.SpanName.EXTRACT) as span:
        extracted, extract_ms = _timed(
            lambda: extract.to_article_with_source(
                item,
                result,
                config=settings.app.extract,
                fetched_at=assemble.utc_now(),
            )
        )
        span.set(telemetry.AttrKey.STATUS, extracted.article.status.value)
        span.set(
            telemetry.AttrKey.FAILURE_CODE,
            extracted.article.failure_code.value if extracted.article.failure_code else None,
        )
        span.set(telemetry.AttrKey.SOURCE_WORDS, len(extracted.source_text.split()))

    article = extracted.article
    verdict = article.status.value
    if article.status is not ArticleStatus.OK:
        verdict = article.failure_code.value if article.failure_code else _failure_of(result)
    return ArticleProbe(
        url=candidate.canonical_url,
        fetch_ms=fetch_ms,
        extract_ms=extract_ms,
        http_status=result.status,
        outcome=result.outcome.value,
        words=len(extracted.source_text.split()),
        verdict=verdict,
        detail=article.failure_detail,
    )


def adhoc_id(url: str, taken: set[str]) -> str:
    """A readable slug for an address that has no config row yet.

    The host, minus the parts every host shares, so a table of fourteen probes
    reads as names rather than as `adhoc-07`. Uniqueness is settled with a
    counter because two feeds from one publisher is the normal case.
    """
    host = urlsplit(url).netloc.lower().split(":")[0]
    parts = [part for part in host.split(".") if part not in _HOST_NOISE]
    stem = "-".join(re.sub(r"[^a-z0-9]+", "-", part).strip("-") for part in parts) or "feed"
    candidate, suffix = stem, 2
    while candidate in taken:
        candidate, suffix = f"{stem}-{suffix}", suffix + 1
    taken.add(candidate)
    return candidate


def targets(args: argparse.Namespace, settings: config.Settings) -> list[FeedDef]:
    """The feeds to probe: the addresses named, or a slice of the config."""
    if args.url:
        taken: set[str] = set()
        return [
            FeedDef(
                id=adhoc_id(url, taken),
                vertical=args.vertical or ADHOC_VERTICAL,
                title=url,
                url=url,
                tier=ADHOC_TIER,
            )
            for url in args.url
        ]

    sources = settings.sources
    chosen: list[FeedDef] = []
    if args.from_config in {"feeds", "all"}:
        chosen.extend(sources.feeds)
    if args.from_config in {"retired", "all"}:
        chosen.extend(sources.retired)
    if args.vertical:
        chosen = [feed for feed in chosen if feed.vertical == args.vertical]
    if args.id:
        wanted = set(args.id)
        chosen = [feed for feed in chosen if feed.id in wanted]
    return chosen


def _tracer(path: Path | None) -> tuple[telemetry.Tracer, Path | None]:
    """Spans to a file, and to a host when the environment names one.

    Same rule as the pipeline's `trace_sink` (owner decision, 2026-08-30): the
    host is added to the file and never used instead of it, so the record a
    reader opens locally and the record a host received are the same record.
    """
    if path is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = DEFAULT_TRACE_DIR / f"{stamp}.jsonl"
    sink: telemetry.SpanSink = telemetry.FileSink(path)
    host = os.environ.get("LANGFUSE_HOST", "").strip()
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if host and public_key and secret_key:
        remote = telemetry.langfuse_sink(host=host, public_key=public_key, secret_key=secret_key)
        if remote is not None:
            sink = telemetry.FanOut((sink, remote))
    return telemetry.Tracer(sink=sink, now=assemble.utc_now), path


def report(rows: Sequence[ProbeRow], *, where: str, trace: Path | None) -> None:
    """The table a person reads. One line per feed, then what it adds up to."""
    width = max((len(row.id) for row in rows), default=2)
    print(f"\nProbed {len(rows)} feed(s) from {where}", file=sys.stderr)
    print(
        f"{'feed':<{width}}  {'HTTP':>4}  {'entries':>7}  {'dated':>5}  "
        f"{'words':>5}  {'ms':>6}  verdict",
        file=sys.stderr,
    )
    for row in rows:
        mark = " " if row.passed else "!"
        print(
            f"{row.id:<{width}}  {row.feed.status or '-'!s:>4}  {row.linkable:>7}  "
            f"{row.dated:>5}  {row.words:>5}  {row.total_ms:>6}  {mark}{row.verdict}",
            file=sys.stderr,
        )

    failed = [row for row in rows if not row.passed]
    tally: dict[str, int] = {}
    for row in failed:
        tally[row.verdict] = tally.get(row.verdict, 0) + 1
    print(
        f"\n{len(rows) - len(failed)} of {len(rows)} cleared the bar"
        f" - a feed that parses and an article that yields prose.",
        file=sys.stderr,
    )
    for verdict, count in sorted(tally.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {count:>3}  {verdict}", file=sys.stderr)
    if trace is not None:
        print(f"\nSpans: {trace.as_posix()}", file=sys.stderr)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="probe_feeds",
        description=(
            "Ask whether a feed address works through the production path: "
            "robots, the feed, the parse, and prose behind one of its articles."
        ),
    )
    parser.add_argument("url", nargs="*", help="Feed addresses to probe.")
    parser.add_argument(
        "--from-config",
        choices=("feeds", "retired", "all"),
        help="Probe what config/sources.json already holds instead of an address.",
    )
    parser.add_argument("--vertical", help="Only this vertical.")
    parser.add_argument("--id", action="append", help="Only this feed id. Repeatable.")
    parser.add_argument(
        "--articles",
        type=int,
        default=1,
        help="Articles to sample behind each feed. The feed passes if any yields prose.",
    )
    parser.add_argument("--report", type=Path, help="Write one JSON object per feed here.")
    parser.add_argument(
        "--trace", type=Path, help="Write spans here instead of backend/var/probes/."
    )
    parser.add_argument(
        "--log-level", default="INFO", help="Root log level for this run. Default INFO."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    if not args.url and not args.from_config:
        LOG.error("name at least one address, or --from-config")
        return 2

    settings = config.load()
    chosen = targets(args, settings)
    if not chosen:
        LOG.error("nothing matched: no feed to probe")
        return 2

    tracer, trace_path = _tracer(args.trace)
    fetcher = cli.live_fetcher(settings, tracer=tracer)
    LOG.info(
        "probing %d feed(s) as %s from %s",
        len(chosen),
        settings.app.extract.user_agent,
        socket.gethostname(),
    )

    rows: list[ProbeRow] = []
    for feed in chosen:
        row = probe_feed(
            feed,
            fetcher=fetcher,
            settings=settings,
            tracer=tracer,
            articles=max(1, args.articles),
        )
        rows.append(row)
        LOG.info(
            "%s %s verdict=%s entries=%d dated=%d ms=%d",
            "pass" if row.passed else "FAIL",
            row.id,
            row.verdict,
            row.linkable,
            row.dated,
            row.total_ms,
        )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")
        LOG.info("wrote %s", args.report.as_posix())

    where = " ".join(args.url) if args.url else f"config/sources.json ({args.from_config})"
    report(rows, where=where, trace=trace_path)
    return 0 if all(row.passed for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
