"""Fetch one URL, or record exactly why not.

Every decision here is a pure function over a status code, a robots file or an
address, and only the last few lines touch a socket. That split is deliberate:
the policy is what can be wrong, so the policy is what the tests drive, and no
test needs the network (Guardrail #7).

A feed is a stranger's list of addresses, which makes every URL here an
instruction from an untrusted source about where to send a request from inside
CI. So an address is validated before it is dialled, and the loopback, private
and link-local ranges are refused - a cloud metadata endpoint is one feed entry
away otherwise (Guardrail #11).

A read also says where its milliseconds went, because `fetch_ms` alone cannot
tell a slow host from a slow handshake from three retries, and unattributed
time is what hides a regression. The split is taken from `http.client`'s own
`connect`, reached through `urllib.request`'s documented injection point -
`AbstractHTTPHandler.do_open` takes the connection class to dial - rather than
from a stopwatch wrapped round the whole call (Guardrail #8). Only numbers come
back: no header, no redirect chain and no server string crosses the boundary
with them.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import time
from contextvars import ContextVar
from dataclasses import dataclass, field, fields, replace
from functools import cache
from http.client import HTTPResponse
from typing import Final, Protocol
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from protego import Protego

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome

#: Bumped when fetch policy changes. `-2` reads robots.txt with `protego`
#: rather than `urllib.robotparser`, which changes what some files mean - see
#: `robots_allows`. Nothing records this yet: `PipelineInputs` carries the
#: extractor and the sanitizer versions and not this one, so a fetch-policy
#: change leaves the run's recorded inputs where they were.
FETCHER_VERSION: Final = "idhazh-fetch-2"

#: Why a target was not asked for, written once. `telemetry` reads these back to
#: type the failure, so a reworded reason cannot quietly become an untyped one.
ROBOTS_REFUSALS: Final[dict[RobotsOutcome, str]] = {
    RobotsOutcome.DENIED: "robots.txt disallows this path",
    RobotsOutcome.UNREACHABLE: "robots.txt could not be reached",
}

ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
#: The port each scheme means when an address does not spell one.
DEFAULT_PORTS: Final[dict[str, int]] = {"http": 80, "https": 443}
# Names that resolve inward on almost every host, and the suffixes that do the
# same on a corporate or container network.
_LOOPBACK_NAMES: Final[frozenset[str]] = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})
_INTERNAL_SUFFIXES: Final[tuple[str, ...]] = (".localhost", ".local", ".internal", ".localdomain")
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class FetchTimings:
    """Where one read's milliseconds went, under the census row's own names.

    **The field names ARE `ItemHealthRow`'s column names and this shape mints
    none of its own**, so a cell called one thing here and another in the ledger
    is a drift that cannot start. `ItemRecorder.note` refuses a key no column
    declares, which is what turns a typo into a failure rather than a cell
    nobody reads.

    Every field is nullable because a reading that was never taken is not a
    zero. A blocked address opened no connection, so a `0` there would claim a
    handshake that never happened, and an attempt nothing answered has no first
    byte to time.
    """

    #: DNS, TCP and - on https - the TLS handshake, before a byte of the answer.
    #: Summed over the connections one attempt opened, because a host that
    #: redirects opens more than one and every one of them is before the answer.
    fetch_connect_ms: int | None = None
    #: From the end of the handshake to the first byte of the response. That is
    #: the host thinking, and it is the half a slow server shows up in.
    fetch_ttfb_ms: int | None = None
    #: What establishing permission cost this read. Zero on the second and every
    #: later article from one host, because the document is read once a run.
    robots_ms: int | None = None
    #: How many attempts this address needed beyond the first.
    retry_count: int | None = None
    #: Everything before the attempt that produced this result - the failed
    #: attempts and the backoff between them.
    retry_total_ms: int | None = None

    def cells(self) -> dict[str, int | None]:
        """These numbers as census cells, ready for `ItemRecorder.note`."""
        return {declared.name: getattr(self, declared.name) for declared in fields(self)}


@dataclass(frozen=True, slots=True)
class FetchResult:
    outcome: FetchOutcome
    status: int | None = None
    body: bytes = b""
    detail: str | None = None
    body_truncated: bool = False
    #: The permission this read was made under, as a value rather than a
    #: sentence. `None` on a result nobody established permission for.
    robots: RobotsOutcome | None = None
    #: Where this read's time went. Empty on a result that reached no socket.
    timings: FetchTimings = FetchTimings()

    @property
    def ok(self) -> bool:
        return self.outcome is FetchOutcome.OK

    def with_robots_ms(self, elapsed_ms: int) -> FetchResult:
        """The same result, saying what its permission check cost.

        The robots read belongs to the caller that owns the per-origin cache, so
        it is the caller that fills this cell - a refusal and a success both
        paid for it and both carry it.
        """
        return replace(self, timings=replace(self.timings, robots_ms=elapsed_ms))


#: Every reason this module refuses an address outright. `telemetry` types the
#: failure from this set, so a new reason cannot arrive as an untyped one.
BLOCKED_REASONS: Final[frozenset[str]] = frozenset(
    {
        "no host in address",
        "port is not a number",
        "address resolves inward",
        "address is not on the public internet",
    }
)


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
    try:
        _ = parts.port
    except ValueError:
        # `urlsplit` parses the port lazily, so a feed entry spelling one
        # nobody can read raises the first time anything asks - which used to
        # be inside `origin`, several frames from here and after the address
        # had already been accepted.
        return False, "port is not a number"
    if host in _LOOPBACK_NAMES or host.endswith(_INTERNAL_SUFFIXES):
        return False, "address resolves inward"
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        return True, None
    if not literal.is_global:
        return False, "address is not on the public internet"
    return True, None


def origin(url: str) -> str:
    """The scheme, host and port that one robots.txt governs, spelled one way.

    RFC 9309 section 2.3 scopes a robots file to its own authority, so
    `HTTPS://Example.COM:443/a` and `https://example.com/b` are one document and
    `https://example.com:8443/c` is a different one. Lower-casing and dropping
    the default port is what stops a run asking one host twice.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if ":" in host:  # an IPv6 literal, which `hostname` hands back unbracketed
        host = f"[{host}]"
    port = parts.port
    if port is None or port == DEFAULT_PORTS.get(scheme):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def resolves_to_public(host: str) -> bool:
    """The half of the check that needs DNS, kept separate so the rest is pure."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


def robots_allows(robots_txt: str, user_agent: str, url: str) -> bool:
    """Read the host's own answer, the same way on every Python we support.

    `protego` rather than `urllib.robotparser`, because the standard library
    disagrees with itself across the supported range: 3.12 takes the first
    matching group and the first matching rule, 3.14 merges repeated groups and
    applies longest-match with `*` and `$`. One file can therefore be read as
    allowed on one runner and refused on another, which makes our own crawling
    unreproducible. `protego` is one implementation of RFC 9309 for both.

    `Protego.can_fetch` takes the URL first and the agent second, the opposite
    order to the standard library's `RobotFileParser.can_fetch`. A swap is
    silent - it answers every question the same way - so the fixtures assert an
    allowance and a denial rather than only exercising the call.
    """
    return bool(Protego.parse(robots_txt).can_fetch(url, user_agent))


@dataclass(frozen=True, slots=True)
class RobotsRules:
    """One host's rules, parsed once and asked about every path separately.

    A document of `None` is "nobody answered", which is not the same fact as
    "the host publishes no rules" - that one parses to an empty document that
    permits everything (RFC 9309 section 2.3.1.3).
    """

    document: Protego | None

    def permits(self, user_agent: str, url: str) -> RobotsOutcome:
        """What this host said about this exact path. Unknown fails closed."""
        if self.document is None:
            return RobotsOutcome.UNREACHABLE
        if self.document.can_fetch(url, user_agent):
            return RobotsOutcome.ALLOWED
        return RobotsOutcome.DENIED


def robots_url(url: str) -> str:
    return f"{origin(url)}/robots.txt"


def robots_rules(result: FetchResult) -> RobotsRules:
    """Read what one robots.txt response means, per RFC 9309 section 2.3.1.

    The standard splits the failures in two, and so do we:

    - **Unavailable** (4xx other than 429). The host answered, and the answer is
      that it publishes no rules for this path. That is a definite reply, not
      silence, and the standard reads it as no restrictions. Ten of our feeds
      sit on hosts that serve no robots.txt at all; refusing them was us
      inventing a rule the host never wrote.
    - **Unreachable** (429, 5xx, a timeout, a reset, a blocked address). Nobody
      answered, so the rules are unknown and stay unknown. Silence remains a
      refusal - assuming consent from silence is how a polite crawler becomes
      an impolite one.

    `classify_status` already draws that line: 429 and 5xx are TRANSIENT
    because they are worth asking again, and the other 4xx are PERMANENT
    because they are not.

    The document is parsed here and kept, rather than the text being kept and
    re-parsed per path, because a host is asked once and its pages are asked
    about many times.
    """
    if result.ok:
        return RobotsRules(Protego.parse(result.body.decode("utf-8", "replace")))
    if result.outcome is FetchOutcome.PERMANENT:
        return RobotsRules(Protego.parse(""))
    return RobotsRules(None)


def refused(permission: RobotsOutcome) -> FetchResult:
    """The answer for a target the host did not permit. No request is made.

    A refusal and an unestablished permission are different facts and become
    different `robots` values, but neither is evidence about the address: we
    never asked it anything.
    """
    return FetchResult(
        FetchOutcome.ROBOTS_DENIED, detail=ROBOTS_REFUSALS[permission], robots=permission
    )


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


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


@dataclass(slots=True)
class _Handshakes:
    """How long one attempt's connections took to open, and how many opened.

    The count is what separates "the handshake was instant" from "there was no
    handshake": a connect that raised recorded nothing, and reporting zero
    milliseconds for it would claim a connection that never existed.
    """

    seconds: float = 0.0
    opened: int = 0

    def record(self, seconds: float) -> None:
        self.seconds += seconds
        self.opened += 1


#: The attempt in flight on this context, so the connection class can report a
#: handshake without the handler having to thread an object through
#: `do_open`'s keyword arguments. Per-context rather than a module global,
#: because two callers fetching at once must not read each other's clocks.
_HANDSHAKES: Final[ContextVar[_Handshakes | None]] = ContextVar(
    "idhazh_fetch_handshakes", default=None
)


def _record_handshake(seconds: float) -> None:
    clock = _HANDSHAKES.get()
    if clock is not None:
        clock.record(seconds)


class _TimedHTTPConnection(http.client.HTTPConnection):
    """`http.client`'s own connection, saying how long opening it took."""

    def connect(self) -> None:
        started = time.monotonic()
        super().connect()
        _record_handshake(time.monotonic() - started)


class _TimedHTTPSConnection(http.client.HTTPSConnection):
    """The same, where the reading also covers the TLS handshake."""

    def connect(self) -> None:
        started = time.monotonic()
        super().connect()
        _record_handshake(time.monotonic() - started)


class _TimedHTTPHandler(request.HTTPHandler):
    """The stock handler, dialling the connection class that times itself.

    `do_open` taking the connection class is `urllib.request`'s own extension
    point, which is why this is six lines rather than a second HTTP client.
    """

    def http_open(self, req: request.Request) -> HTTPResponse:
        return self.do_open(_TimedHTTPConnection, req)


class _TimedHTTPSHandler(request.HTTPSHandler):
    """The same for https, dialling with the context its parent built.

    The context is read back rather than rebuilt, so this handler negotiates
    exactly what the stock one would - same verification, same protocol list.
    `urllib.request` keeps it under a private name, which is why this reaches
    into the instance dictionary rather than naming the attribute.
    """

    def https_open(self, req: request.Request) -> HTTPResponse:
        return self.do_open(_TimedHTTPSConnection, req, context=self.__dict__["_context"])


@cache
def _timing_opener() -> request.OpenerDirector:
    """One opener for the process, exactly as `urlopen` keeps one.

    `build_opener` drops its own `HTTPHandler` and `HTTPSHandler` when it is
    handed subclasses of them, so this is the stock chain - proxies, redirects,
    error processing - with the connection class swapped and nothing else.
    Built once because the handlers hold no per-request state and an SSL
    context is the expensive part of building one.
    """
    return request.build_opener(_TimedHTTPHandler(), _TimedHTTPSHandler())


@dataclass(slots=True)
class _Attempt:
    """One pass round the retry loop, and what it can say about its own time."""

    #: How many attempts came before this one. Zero on the first.
    retries: int
    #: When this attempt began, after any backoff it waited out.
    started: float
    #: When the first attempt began, so the retries can be priced together.
    loop_started: float
    handshakes: _Handshakes = field(default_factory=_Handshakes)

    def answered(self) -> FetchTimings:
        """The reading for an attempt whose response headers arrived."""
        waited = time.monotonic() - self.started - self.handshakes.seconds
        return self._reading(_ms(max(waited, 0.0)))

    def unanswered(self) -> FetchTimings:
        """The reading for an attempt nothing answered - no first byte to time."""
        return self._reading(None)

    def _reading(self, ttfb_ms: int | None) -> FetchTimings:
        return FetchTimings(
            fetch_connect_ms=_ms(self.handshakes.seconds) if self.handshakes.opened else None,
            fetch_ttfb_ms=ttfb_ms,
            retry_count=self.retries,
            retry_total_ms=_ms(self.started - self.loop_started),
        )


def fetch(url: str, *, config: ExtractConfig, permission: RobotsOutcome) -> FetchResult:
    """The one function here that opens a socket, and only with permission.

    `permission` is what the host's own robots.txt said about this exact path,
    established by the caller from a document it read once for the whole origin
    (`RobotsRules.permits`). Anything but `allowed` returns before a socket
    exists. The caller normally stops earlier still and never calls this at all
    for a target it may not have; the branch is here so that a caller which
    forgets cannot turn a refusal into a request.

    Reading `/robots.txt` itself is always permitted, so the caller passes
    `allowed` for that read.

    The result says where its own time went. The retry cells come from this
    loop rather than from a counter kept beside it, so a budget change moves
    them by construction: `retry_count` is the index of the attempt that
    produced the result, and `retry_total_ms` is everything before that attempt
    started - the failed attempts and the backoff they earned.
    """
    dialable, why = address_is_dialable(url)
    if not dialable:
        return FetchResult(FetchOutcome.BLOCKED, detail=why, robots=permission)
    if permission is not RobotsOutcome.ALLOWED:
        return refused(permission)
    host = urlsplit(url).hostname or ""
    if not resolves_to_public(host):
        return FetchResult(
            FetchOutcome.BLOCKED,
            detail="address is not on the public internet",
            robots=permission,
        )

    outbound = request.Request(url, headers={"User-Agent": config.user_agent})
    opener = _timing_opener()
    last: FetchResult = FetchResult(
        FetchOutcome.TRANSIENT, detail="never attempted", robots=permission
    )
    loop_started = time.monotonic()
    for retries, delay in enumerate([0.0, *backoff_delays(config)]):
        if delay:
            _sleep(delay)
        attempt = _Attempt(
            retries=retries, started=time.monotonic(), loop_started=loop_started
        )
        token = _HANDSHAKES.set(attempt.handshakes)
        try:
            response = opener.open(outbound, timeout=config.request_timeout_seconds)
        except HTTPError as error:
            outcome = classify_status(error.code)
            last = FetchResult(
                outcome,
                status=error.code,
                detail=f"HTTP {error.code}",
                robots=permission,
                timings=attempt.answered(),
            )
            if outcome is FetchOutcome.PERMANENT:
                return last
        except (URLError, TimeoutError, OSError) as error:
            last = FetchResult(
                FetchOutcome.TRANSIENT,
                detail=type(error).__name__,
                robots=permission,
                timings=attempt.unanswered(),
            )
        else:
            # Read the clock before the body, or the whole download lands in
            # the cell that is supposed to hold the host's thinking time.
            timings = attempt.answered()
            with response:
                body, truncated = read_capped(response, config.max_body_bytes)
            return FetchResult(
                FetchOutcome.OK,
                status=response.status,
                body=body,
                body_truncated=truncated,
                robots=permission,
                timings=timings,
            )
        finally:
            _HANDSHAKES.reset(token)
    return last


def _sleep(seconds: float) -> None:
    time.sleep(seconds)
