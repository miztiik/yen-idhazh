"""A loopback stand-in for the text-analysis service, owned by the test that starts it."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from idhazh import config
from idhazh.contracts.knobs.text_analysis import TextAnalysisConfig

#: A label the service gave one stretch of the text, and where it starts and ends.
Span = tuple[str, int, int]


def entities_reply(text: str, spans: Iterable[Span]) -> bytes:
    """The service's result for the `entities` feature, in the shape its API reference gives.

    Each mention carries the exact words at its offsets, which is what the real service
    returns and what the client checks before it believes an offset.
    """
    mentions = [
        {
            "text": text[start:end],
            "start_char": start,
            "end_char": end,
            "sentence_index": 0,
            "label": label,
        }
        for label, start, end in spans
    ]
    return json.dumps(
        {
            "status": "complete",
            "language": "en",
            "model": {
                "profile": "lg",
                "package": "en_core_web_lg",
                "model_version": "3.8.0",
                "spacy_version": "3.8.18",
            },
            "features": [
                {
                    "feature": "entities",
                    "status": "complete",
                    "data": {"mentions": mentions},
                    "error": None,
                }
            ],
        }
    ).encode("utf-8")


class RecordedAnalysis:
    """One loopback port that answers the analysis route the way a test asks it to.

    By default it answers every request with the spans `spans_of` finds for the text it
    was sent. `status` and `body` make it answer something else, `hold` makes it read the
    request and then say nothing until the test ends, `drop` closes the line without a
    word, and `location` sends a redirect.
    """

    def __init__(
        self,
        spans_of: Callable[[str], Iterable[Span]] | None = None,
        *,
        status: int = 200,
        body: bytes | None = None,
        hold: bool = False,
        drop: bool = False,
        location: str | None = None,
    ) -> None:
        stop = threading.Event()
        sent: list[dict[str, Any]] = []
        paths: list[str] = []
        content_types: list[str | None] = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                request = json.loads(raw)
                sent.append(request)
                paths.append(self.path)
                content_types.append(self.headers.get("Content-Type"))
                if hold:
                    stop.wait()
                if hold or drop:
                    self.close_connection = True
                    return
                if location is not None:
                    self.send_response(307)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                answer = (
                    body
                    if body is not None
                    else entities_reply(request["text"], (spans_of or (lambda _: ()))(request["text"]))
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(answer)))
                self.end_headers()
                self.wfile.write(answer)

            def log_message(self, *_args: object) -> None:
                return None

        self._stop = stop
        self._sent = sent
        self._paths = paths
        self._content_types = content_types
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    @property
    def sent(self) -> list[dict[str, Any]]:
        """Every request body this port received, parsed."""
        return list(self._sent)

    @property
    def paths(self) -> list[str]:
        return list(self._paths)

    @property
    def content_types(self) -> list[str | None]:
        return list(self._content_types)

    def __enter__(self) -> RecordedAnalysis:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


def closed_base_url() -> str:
    """An address on this machine that nothing listens on, because the port was just released."""
    with RecordedAnalysis() as service:
        return service.base_url


def pointed_at(
    settings: config.Settings, base_url: str, *, request_timeout_seconds: float | None = None
) -> config.Settings:
    """The same settings with the analysis service at `base_url`, and nothing else moved."""
    current = settings.app.text_analysis
    named = TextAnalysisConfig(
        base_url=base_url,
        language=current.language,
        request_timeout_seconds=(
            current.request_timeout_seconds
            if request_timeout_seconds is None
            else request_timeout_seconds
        ),
    )
    return replace(
        settings, app=settings.app.model_copy(update={"text_analysis": named})
    )
