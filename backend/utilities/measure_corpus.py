"""Measure the corpus, so the length buckets stop being invented.

Every per-article cost figure in this design multiplies a throughput number by
an article length, and until this runs those lengths are a guess. The tool
fetches real links, extracts them the way the pipeline will, counts words, and
reports the distribution against the bucket edges the cost model assumes.

It stores counts and links only - never article text. Robots are honoured, one
request at a time with a delay, because a measurement is not a licence to
hammer somebody's server.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import feedparser
import trafilatura

# Midpoints between the bucket centres the cost model assumes (400 / 1200 /
# 3500 words, see backend/utilities/summarise_bench.py). Overridable, because
# the whole point of this tool is to find out whether they are right.
DEFAULT_EDGES = (650, 1850)
DEFAULT_FEEDS = (
    "https://hnrss.org/frontpage",
    "https://hnrss.org/newest?points=100",
)


def feed_links(feeds: list[str], limit: int) -> list[str]:
    seen: dict[str, None] = {}
    for feed in feeds:
        parsed = feedparser.parse(feed)
        for entry in parsed.entries:
            link = str(getattr(entry, "link", "") or "")
            if link.startswith("http") and link not in seen:
                seen[link] = None
            if len(seen) >= limit:
                return list(seen)
    return list(seen)


class Robots:
    """One robots.txt per host, read once. Unreadable means skip, not assume."""

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._cache:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"{host}/robots.txt")
            try:
                parser.read()
            except Exception:
                # Any failure means we do not know what the host permits.
                self._cache[host] = None
            else:
                self._cache[host] = parser
        parser_or_none = self._cache[host]
        if parser_or_none is None:
            return False
        return parser_or_none.can_fetch(self.user_agent, url)


def measure_one(url: str) -> dict[str, Any]:
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        return {"url": url, "status": "fetch_failed", "word_count": 0}
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        return {"url": url, "status": "extract_failed", "word_count": 0}
    return {"url": url, "status": "ok", "word_count": len(text.split())}


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def summarise(items: list[dict[str, Any]], edges: tuple[int, int]) -> dict[str, Any]:
    counts = [int(item["word_count"]) for item in items if item["status"] == "ok"]
    short = [c for c in counts if c < edges[0]]
    medium = [c for c in counts if edges[0] <= c < edges[1]]
    long = [c for c in counts if c >= edges[1]]
    total = len(counts)

    def bucket(name: str, values: list[int]) -> dict[str, Any]:
        return {
            "bucket": name,
            "n": len(values),
            "share": round(len(values) / total, 3) if total else 0.0,
            "median_words": percentile(values, 0.5),
        }

    return {
        "n_attempted": len(items),
        "n_extracted": total,
        "n_failed": len(items) - total,
        "edges_words": list(edges),
        "mean_words": round(statistics.fmean(counts), 1) if counts else 0.0,
        "stddev_words": round(statistics.stdev(counts), 1) if len(counts) > 1 else 0.0,
        "p10_words": percentile(counts, 0.10),
        "p50_words": percentile(counts, 0.50),
        "p90_words": percentile(counts, 0.90),
        "max_words": max(counts) if counts else 0,
        "buckets": [
            bucket("short", short),
            bucket("medium", medium),
            bucket("long", long),
        ],
    }


def hardware() -> dict[str, Any]:
    """Holy Law #10: a number without its hardware and date is not a measurement."""
    return {
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feed", action="append", default=None, help="Repeatable. Defaults to HN.")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between requests.")
    ap.add_argument("--edges", default=",".join(str(e) for e in DEFAULT_EDGES))
    ap.add_argument("--user-agent", default="yen-idhazh-measure/1.0")
    ap.add_argument("--out", type=Path, default=Path("backend/var/corpus.json"))
    args = ap.parse_args()

    low, high = (int(part) for part in args.edges.split(","))
    feeds = args.feed or list(DEFAULT_FEEDS)
    links = feed_links(feeds, args.limit)
    print(f"{len(links)} candidate links from {len(feeds)} feed(s)", flush=True)

    robots = Robots(args.user_agent)
    items: list[dict[str, Any]] = []
    for index, link in enumerate(links, start=1):
        if not robots.allows(link):
            items.append({"url": link, "status": "robots_denied", "word_count": 0})
        else:
            items.append(measure_one(link))
            time.sleep(args.sleep)
        if index % 25 == 0:
            print(f"  {index}/{len(links)}", flush=True)

    summary = summarise(items, (low, high))
    payload = {
        "hardware": hardware(),
        "feeds": feeds,
        "summary": summary,
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(
        f"\nextracted {summary['n_extracted']} of {summary['n_attempted']} "
        f"({summary['n_failed']} failed)"
    )
    print(
        f"words: mean {summary['mean_words']} +/- {summary['stddev_words']}, "
        f"p10 {summary['p10_words']}, p50 {summary['p50_words']}, "
        f"p90 {summary['p90_words']}, max {summary['max_words']}"
    )
    for entry in summary["buckets"]:
        print(
            f"  {entry['bucket']:<7} n={entry['n']:>4}  "
            f"share={entry['share']:<6} median={entry['median_words']}"
        )
    print(f"\nwrote {args.out.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
