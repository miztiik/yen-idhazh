"""Which server does this run send an article to?

One value. `CLAUDE.md` Guardrail #11 says article text goes only to a model
process this run's operator controls, and that the address is a committed config
value rather than an environment one - an environment value is the one kind of
setting that moves with nobody reading a diff.

The grammar sits here rather than in the loader, so every path that validates
this config refuses a bad address and the rule has one home. Nothing in
`idhazh.llm` reads config; it takes the resolved address from its caller.
"""

from __future__ import annotations

import ipaddress
from typing import Final, Self
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, model_validator

from idhazh.contracts.base import Model

#: The address this repository ships. Loopback, because every job under
#: `.github/` starts its own server on the machine its stage runs on.
DEFAULT_BASE_URL: Final = "http://127.0.0.1:8080"


def resolve_base_url(declared: str) -> str:
    """Scheme, host and port of the server this run talks to.

    A path, query or fragment is refused rather than dropped: every other route
    is built by replacing the whole path, so a prefix would hold on one route and
    vanish from four, and a wrong answer is worse than an error. A missing port is
    refused because the server command reads the port back out of this value, and
    `http://host` parses cleanly while yielding no port at all.

    The host is read as a host rather than as the whole authority: `http://:8080`
    leaves an authority that is not empty and a host that is.
    """
    parts = urlsplit(declared.rstrip("/"))
    if not parts.scheme or not parts.hostname or parts.path or parts.query or parts.fragment:
        raise ValueError(
            "model_server.base_url must be a scheme, a host and a port and nothing "
            f"else, not {declared!r}"
        )
    try:
        port = parts.port
    except ValueError as error:
        raise ValueError(f"model_server.base_url names no usable port: {declared!r}") from error
    if port is None:
        raise ValueError(f"model_server.base_url must name a port, not {declared!r}")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def port_of_base_url(declared: str) -> int:
    """The port the server command binds, read back out of the address.

    It is here rather than at each caller because it is a fact about this
    field's grammar: `resolve_base_url` above is what guarantees the port is
    there, and `urlsplit(...).port` is `int | None` whatever that guarantee
    says. One narrowing, beside the rule it relies on.
    """
    port = urlsplit(resolve_base_url(declared)).port
    if port is None:  # pragma: no cover - resolve_base_url has already refused this
        raise ValueError(f"model_server.base_url must name a port, not {declared!r}")
    return port


def is_loopback(base_url: str) -> bool:
    """Is the model server on the machine this process is running on?

    A loopback IP literal - `127.0.0.0/8` or `::1` - or the name `localhost`,
    which RFC 6761 reserves to mean this host. Nothing else, and never a name
    lookup: a resolver answer would make a caller's reading depend on something
    nobody wrote down, and a hosts entry can point `127.0.0.1` at a tunnel to a
    second machine, so the lookup buys false confidence rather than truth.

    This is not `fetch.py`'s inward-address check and must not share its set.
    That one errs wide, because a wrong yes lets a stranger's feed reach inside
    the runner. This one errs narrow, because its caller writes what it answers
    into a run record. An address this cannot place answers no rather than
    raising: `resolve_base_url` already refuses a malformed address at config
    load, where a person reads the error against the file they just edited.
    """
    host = (urlsplit(base_url).hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class ModelServerConfig(Model):
    """The one address every stage posts an article to."""

    base_url: str = Field(
        default=DEFAULT_BASE_URL,
        description=(
            "Scheme, host and port of the model server, and nothing else. A trailing "
            "slash is accepted and dropped; a path, a query or a fragment is refused, "
            "because the other four routes are derived by replacing the whole path and "
            "a prefix would survive on one of them and vanish from the rest. The port "
            "is required: the server command binds the port it reads back out of this "
            "value. Committed rather than set from the environment, so moving where "
            "article text goes is a diff a person reads (CLAUDE.md Guardrail #11)."
        ),
    )

    @model_validator(mode="after")
    def _the_address_is_a_scheme_a_host_and_a_port(self) -> Self:
        self.base_url = resolve_base_url(self.base_url)
        return self
