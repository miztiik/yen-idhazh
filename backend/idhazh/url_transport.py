"""How does an international URL become the ASCII request target HTTP expects?

The returned URL is also suitable for identity: equivalent raw Unicode and
already percent-encoded addresses serialize the same way.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import SplitResult, quote, urlsplit, urlunsplit

_PATH_SAFE: Final = "/:@!$&'()*+,;=-._~%"
_QUERY_SAFE: Final = "/?:@!$&'()*+,;=[]-._~%"
_USERINFO_SAFE: Final = "!$&'()*+,;=:%-._~"
_PERCENT_ESCAPE: Final = re.compile(r"%[0-9A-Fa-f]{2}")


class InvalidTransportUrlError(ValueError):
    """A URL that cannot be represented as an ASCII HTTP request target."""


def encode_url_for_transport(url: str) -> str:
    """Return a URL with IDNA hosts and UTF-8 percent-encoded components."""
    try:
        parts = urlsplit(url.strip())
    except (UnicodeError, ValueError) as error:
        raise InvalidTransportUrlError("address is not valid") from error
    try:
        port = parts.port
    except ValueError as error:
        raise InvalidTransportUrlError("port is not a number") from error
    try:
        authority = _ascii_authority(parts, port)
        return urlunsplit(
            (
                parts.scheme,
                authority,
                _encode_component(parts.path, _PATH_SAFE),
                _encode_component(parts.query, _QUERY_SAFE),
                _encode_component(parts.fragment, _QUERY_SAFE),
            )
        )
    except (UnicodeError, ValueError) as error:
        raise InvalidTransportUrlError("address is not valid") from error


def _encode_component(value: str, safe: str) -> str:
    quoted = quote(value, safe=safe)
    return _PERCENT_ESCAPE.sub(lambda match: match.group().upper(), quoted)


def _ascii_authority(parts: SplitResult, port: int | None) -> str:
    host = parts.hostname
    if host is None:
        return quote(parts.netloc, safe=":@!$&'()*+,;=[]%-._~")

    ascii_host = f"[{host}]" if ":" in host else host.encode("idna").decode("ascii")
    userinfo, separator, _host_and_port = parts.netloc.rpartition("@")
    prefix = f"{quote(userinfo, safe=_USERINFO_SAFE)}@" if separator else ""
    suffix = f":{port}" if port is not None else ""
    return f"{prefix}{ascii_host}{suffix}"
