"""How does a request to a server this run controls leave with no proxy the environment names?

`urllib` follows `http_proxy` and its relatives for every address, a loopback one
included, so by default the body of a request to a server on this machine goes first to
whatever those settings name. An environment value is the one setting that moves a
destination with nobody reading a diff, and article text goes only where committed config
sends it (`CLAUDE.md` Guardrail #11). The two clients that send article text to a process
the run controls, the model server's and the text-analysis service's, open their requests
here.
"""

from __future__ import annotations

import http.client
import urllib.request


def open_without_proxy(
    request: urllib.request.Request | str, *, timeout: float
) -> http.client.HTTPResponse:
    """Send `request` and return the open response, whatever proxy the environment names.

    The opener is built on every call, so the environment of the call is the one a test
    can set, and no process-wide opener kept from an earlier request can stand in for this
    one. Failures are `urllib`'s own: `URLError` for a connection that did not complete and
    `HTTPError` for a status of 400 or more.
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    response: http.client.HTTPResponse = opener.open(request, timeout=timeout)
    return response
