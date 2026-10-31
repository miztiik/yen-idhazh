"""Serve captured article bytes with real interrupted HTTP body reads."""

from __future__ import annotations

import threading
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Literal

from pytest import MonkeyPatch

from idhazh import fetch as fetch_module


class InterruptedBodyEndpoint:
    """Interrupt a bounded number of reads, then serve the captured page."""

    def __init__(
        self,
        body: bytes,
        *,
        failure: Literal["timeout", "incomplete"],
        failures: int,
        status: int = 200,
        failed_path: str | None = None,
    ) -> None:
        self.served = 0
        self.responses: list[HTTPResponse] = []
        self.interrupted = 0
        stop = threading.Event()
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/robots.txt":
                    self.send_response(200)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                site.served += 1
                self.send_response(status)
                if (
                    status == 200
                    and (failed_path is None or self.path == failed_path)
                    and site.interrupted < failures
                ):
                    site.interrupted += 1
                    if failure == "timeout":
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body[:1])
                        self.wfile.flush()
                        stop.wait()
                    else:
                        self.send_header("Transfer-Encoding", "chunked")
                        self.end_headers()
                        self.wfile.write(b"10\r\n" + body[:1])
                        self.wfile.flush()
                    self.close_connection = True
                    return
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return

        self._stop = stop
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def allow_and_observe(self, monkeypatch: MonkeyPatch) -> None:
        """Use the existing loopback test boundary and retain real responses."""
        monkeypatch.setattr(fetch_module, "address_is_dialable", lambda url: (True, None))
        monkeypatch.setattr(fetch_module, "resolves_to_public", lambda host: True)
        getresponse = fetch_module._TimedHTTPConnection.getresponse

        def observe(connection: fetch_module._TimedHTTPConnection) -> HTTPResponse:
            response = getresponse(connection)
            self.responses.append(response)
            return response

        monkeypatch.setattr(fetch_module._TimedHTTPConnection, "getresponse", observe)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/article"

    def __enter__(self) -> InterruptedBodyEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)
