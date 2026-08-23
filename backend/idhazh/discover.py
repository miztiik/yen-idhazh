"""Turn configured feeds into candidate links, and one address into one address.

Discovery reads feeds and nothing else. It does not fetch articles, it does not
rank, and it loads no weights - the plan job finishes in seconds, which is what
lets the expensive work be sharded across disposable machines afterwards.

Everything that arrives here came from someone else's server, so a title is
data and never instruction (Rule #11). Titles are sanitized on arrival and
bounded, because they reach a log line and a page.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import feedparser

from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.taxonomy import LifecycleStatus, SourceTier
from idhazh.sanitize import sanitize

#: Bumped when canonicalisation or title handling changes, because either moves
#: `url_key` and therefore what counts as the same story.
DISCOVERY_VERSION: Final = "idhazh-discover-1"

TITLE_MAX_CHARS: Final = 500

# Campaign and click identifiers. They differ per referrer for the same article,
# so leaving them in means the same story arrives as several distinct stories.
_TRACKING_PREFIXES: Final = ("utm_",)
_TRACKING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "cmpid",
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "mkt_tok",
        "msclkid",
        "ref",
        "referrer",
        "s",
        "src",
    }
)
_DEFAULT_PORTS: Final[dict[str, str]] = {"http": "80", "https": "443"}
_WWW = re.compile(r"^www\.")


def canonicalise(url: str) -> str:
    """One address per story, so deduplication is arithmetic rather than luck.

    Lowercases the scheme and host, drops the default port and a leading `www.`,
    strips campaign identifiers and the fragment, sorts what remains of the
    query, and removes a trailing slash from a non-root path.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = _WWW.sub("", parts.hostname or "")
    if parts.port and str(parts.port) != _DEFAULT_PORTS.get(scheme):
        host = f"{host}:{parts.port}"

    path = parts.path.rstrip("/") or "/"
    kept = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_KEYS and not key.lower().startswith(_TRACKING_PREFIXES)
    )
    query = "&".join(f"{key}={value}" for key, value in kept)
    return urlunsplit((scheme, host, path, query, ""))


def clean_title(raw: str | None) -> str | None:
    """A feed title is a stranger's text on its way to a page and a log line."""
    if not raw:
        return None
    cleaned = " ".join(sanitize(raw).split())[:TITLE_MAX_CHARS].strip()
    return cleaned or None


def _published_at(entry: Any) -> str | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    year, month, day, hour, minute, second = parsed[:6]
    stamp = datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class Candidate:
    """One link a feed offered, before anything has been decided about it."""

    canonical_url: str
    source_url: str
    url_key: str
    source_id: str
    vertical: str
    tier: SourceTier
    title: str | None
    published_at: str | None
    weight: float = 1.0
    """The feed's own weight, carried so ranking never has to look a feed up again."""


def candidates_from_feed(feed: FeedDef, body: str | bytes) -> list[Candidate]:
    """Parse one already-fetched feed body. Never touches the network itself.

    An entry without a usable link is dropped rather than guessed at, and a feed
    that fails to parse yields nothing rather than failing its siblings
    (`degrade, do not fail`).
    """
    parsed = feedparser.parse(body)
    found: list[Candidate] = []
    seen: set[str] = set()
    for entry in parsed.entries:
        link = (getattr(entry, "link", "") or "").strip()
        if not link.lower().startswith(("http://", "https://")):
            continue
        canonical = canonicalise(link)
        if canonical in seen:
            continue
        seen.add(canonical)
        found.append(
            Candidate(
                canonical_url=canonical,
                source_url=link,
                url_key=derive_url_key(canonical),
                source_id=feed.id,
                vertical=feed.vertical,
                tier=feed.tier,
                title=clean_title(getattr(entry, "title", None)),
                published_at=_published_at(entry),
                weight=feed.weight,
            )
        )
    return found


def salience_urls(body: str | bytes) -> set[str]:
    """Canonical URLs a salience feed voted for.

    A link aggregator is a vote, not a source: these add rank to a URL already
    in the pool and never introduce one.
    """
    parsed = feedparser.parse(body)
    return {
        canonicalise(link)
        for entry in parsed.entries
        if (link := (getattr(entry, "link", "") or "").strip()).lower().startswith("http")
    }


def live(feeds: list[FeedDef], vertical_id: str) -> list[FeedDef]:
    """Feeds a vertical may actually read: this vertical's, and not still a draft.

    A retired feed never reaches here. It lives in `Sources.retired`, which the
    plan stage does not loop, so retirement is enforced by the shape of the
    config rather than by a filter every caller has to remember to apply.
    """
    return [
        feed
        for feed in feeds
        if feed.vertical == vertical_id and feed.status is LifecycleStatus.ACTIVE
    ]


def resting(history: Iterable[FeedHealthRow], *, after_failures: int) -> frozenset[str]:
    """Feeds this run should not ask, decided only from what earlier runs recorded.

    Quarantine is a rest, not a retirement. Retirement is a person moving a feed
    into `Sources.retired`; nothing here ever edits `config/sources.json`, so a
    run can never delete a source somebody chose.

    The rest also has to end on its own, or a bad afternoon becomes a permanent
    removal. So a feed that has failed its last `after_failures` attempts is
    skipped, and once it has been skipped `after_failures` times it is asked
    again regardless. A source that came back is live on that very run; a source
    that is still dead costs one request per cycle instead of one per run.

    Both counters come from the same knob because there is only one question
    here: how much evidence is enough. Inventing a second number would mean
    inventing a second answer.
    """
    by_feed: dict[str, list[FeedHealthRow]] = {}
    for row in history:
        by_feed.setdefault(row.feed_id, []).append(row)
    return frozenset(feed_id for feed_id, rows in by_feed.items() if _rests(rows, after_failures))


def _rests(rows: list[FeedHealthRow], after_failures: int) -> bool:
    """`rows` are oldest run first, which is the order `load_health` returns."""
    skips = 0
    for row in reversed(rows):
        if row.attempted:
            break
        skips += 1
    if skips >= after_failures:
        return False

    strikes = 0
    for row in reversed(rows):
        if not row.attempted:
            continue  # A rest is transparent: it neither adds a strike nor clears one.
        if not row.failing:
            break
        strikes += 1
    return strikes >= after_failures
