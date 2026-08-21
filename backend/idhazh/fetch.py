"""Fetch one URL, or record exactly why not.

Every decision here is a pure function over a status code, a robots file or an
address, and only the last few lines touch a socket. That split is deliberate:
the policy is what can be wrong, so the policy is what the tests drive, and no
test needs the network (Holy Law #7).

A feed is a stranger's list of addresses, which makes every URL here an
instruction from an untrusted source about where to send a request from inside
CI. So an address is validated before it is dialled, and the loopback, private
and link-local ranges are refused - a cloud metadata endpoint is one feed entry
away otherwise (Holy Law #11).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from idhazh.contracts.app_config import ExtractConfig

#: Bumped when fetch policy changes. A body that arrived under different rules
#: is a different input, and the fingerprint has to be able to say so.
FETCHER_VERSION: Final = "idhazh-fetch-1"

ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
# Names that resolve inward on almost every host, and the suffixes that do the
# same on a corporate or container network.
_LOOPBACK_NAMES: Final[frozenset[str]] = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})
_INTERNAL_SUFFIXES: Final[tuple[str, ...]] = (".localhost", ".local", ".internal", ".localdomain")
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 425, 429, 500, 502, 503, 504})


class FetchOutcome(StrEnum):
    OK = "ok"
    ROBOTS_DENIED = "robots_denied"
    BLOCKED = "blocked"
    PERMANENT = "permanent"
    TRANSIENT = "transient"


@dataclass(frozen=True, slots=True)
class FetchResult:
    outcome: FetchOutcome
    status: int | None = None
    body: bytes = b""
    detail: str | None = None
    body_truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome is FetchOutcome.OK


def address_is_dialable(url: str) -> tuple[bool, str | None]:
    """Refuse an address before it is dialled, not after.

    A hostname still has to be checked once resolved - this catches the literal
    cases and the schemes, which is what a hostile feed reaches for first.
    """
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"scheme {parts.scheme!r} is not fetchable"
    host = (parts.hostname or "").lower()
    if not host:
        return False, "no host in address"
    if host in _LOOPBACK_NAMES or host.endswith(_INTERNAL_SUFFIXES):
        return False, "address resolves inward"
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return True, None
    if not literal.is_global:
        return False, "address is not on the public internet"
    return True, None


def resolves_to_public(host: str) -> bool:
    """The half of the check that needs DNS, kept separate so the rest is pure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


def robots_allows(robots_txt: str, user_agent: str, url: str) -> bool:
    """Read the host's own answer. An unreadable robots file is a no, decided by the caller."""
    parser = RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url)


def robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def backoff_delays(config: ExtractConfig) -> list[float]:
    """Exponential, and finite. A retry budget that never ends is an outage amplifier."""
    return [
        config.backoff_initial_seconds * (config.backoff_multiplier**attempt)
        for attempt in range(config.max_retries)
    ]


def classify_status(status: int) -> FetchOutcome:
    """A 404 is an answer; a 503 is a request to come back.

    Retrying a permanent failure burns the budget the transient ones need, and
    on a shared runner that budget is wall-clock the whole matrix is waiting on.
    """
    if 200 <= status < 300:
        return FetchOutcome.OK
    if status in _RETRYABLE_STATUS:
        return FetchOutcome.TRANSIENT
    return FetchOutcome.PERMANENT


class Readable(Protocol):
    def read(self, size: int, /) -> bytes: ...


def read_capped(response: Readable, limit: int) -> tuple[bytes, bool]:
    """Read at most `limit` bytes. A body without a ceiling is a memory ceiling."""
    body = response.read(limit + 1)
    if len(body) > limit:
        return body[:limit], True
    return body, False


def fetch(url: str, *, config: ExtractConfig, robots_txt: str | None) -> FetchResult:
    """The one function here that opens a socket.

    `robots_txt` of None means the host's robots file could not be read, which
    is a refusal rather than a permission - assuming consent from silence is
    how a polite crawler becomes an impolite one.
    """
    dialable, why = address_is_dialable(url)
    if not dialable:
        return FetchResult(FetchOutcome.BLOCKED, detail=why)
    if robots_txt is None:
        return FetchResult(FetchOutcome.ROBOTS_DENIED, detail="robots.txt could not be read")
    if not robots_allows(robots_txt, config.user_agent, url):
        return FetchResult(FetchOutcome.ROBOTS_DENIED, detail="robots.txt disallows this path")
    host = urlsplit(url).hostname or ""
    if not resolves_to_public(host):
        return FetchResult(FetchOutcome.BLOCKED, detail="address is not on the public internet")

    outbound = request.Request(url, headers={"User-Agent": config.user_agent})
    last: FetchResult = FetchResult(FetchOutcome.TRANSIENT, detail="never attempted")
    for delay in [0.0, *backoff_delays(config)]:
        if delay:
            _sleep(delay)
        try:
            with request.urlopen(outbound, timeout=config.request_timeout_seconds) as response:
                body, truncated = read_capped(response, config.max_body_bytes)
                return FetchResult(
                    FetchOutcome.OK, status=response.status, body=body, body_truncated=truncated
                )
        except HTTPError as error:
            outcome = classify_status(error.code)
            last = FetchResult(outcome, status=error.code, detail=f"HTTP {error.code}")
            if outcome is FetchOutcome.PERMANENT:
                return last
        except (URLError, TimeoutError, OSError) as error:
            last = FetchResult(FetchOutcome.TRANSIENT, detail=type(error).__name__)
    return last


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
