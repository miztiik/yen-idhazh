"""Fetch one URL, or record exactly why not.

Every decision here is a pure function over a status code, a robots file or an
address, and only the last few lines touch a socket. That split is deliberate:
the policy is what can be wrong, so the policy is what the tests drive, and no
test needs the network (Rule #7).

A feed is a stranger's list of addresses, which makes every URL here an
instruction from an untrusted source about where to send a request from inside
CI. So an address is validated before it is dialled, and the loopback, private
and link-local ranges are refused - a cloud metadata endpoint is one feed entry
away otherwise (Rule #11).
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Final, Protocol
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from protego import Protego

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome

#: Bumped when fetch policy changes. `-2` reads robots.txt with `protego`
#: rather than `urllib.robotparser`, which changes what some files mean - see
#: `robots_allows`. Nothing digests this yet: `PipelineInputs` carries the
#: extractor and the sanitizer versions and not this one, so a fetch-policy
#: change does not move `pipeline_fingerprint`.
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
class FetchResult:
    outcome: FetchOutcome
    status: int | None = None
    body: bytes = b""
    detail: str | None = None
    body_truncated: bool = False
    #: The permission this read was made under, as a value rather than a
    #: sentence. `None` on a result nobody established permission for.
    robots: RobotsOutcome | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is FetchOutcome.OK


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
    last: FetchResult = FetchResult(
        FetchOutcome.TRANSIENT, detail="never attempted", robots=permission
    )
    for delay in [0.0, *backoff_delays(config)]:
        if delay:
            _sleep(delay)
        try:
            with request.urlopen(outbound, timeout=config.request_timeout_seconds) as response:
                body, truncated = read_capped(response, config.max_body_bytes)
                return FetchResult(
                    FetchOutcome.OK,
                    status=response.status,
                    body=body,
                    body_truncated=truncated,
                    robots=permission,
                )
        except HTTPError as error:
            outcome = classify_status(error.code)
            last = FetchResult(
                outcome, status=error.code, detail=f"HTTP {error.code}", robots=permission
            )
            if outcome is FetchOutcome.PERMANENT:
                return last
        except (URLError, TimeoutError, OSError) as error:
            last = FetchResult(
                FetchOutcome.TRANSIENT, detail=type(error).__name__, robots=permission
            )
    return last


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
