"""Recorded local HTTP model endpoints for backend tests."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .models import committed_renderings
from .paths import CONFIG_DIR


def render_template_response(body: dict[str, Any], config_dir: Path = CONFIG_DIR) -> bytes:
    """Render a template response with the active model's recorded markers."""
    recorded = committed_renderings(config_dir=config_dir)
    asks_to_think = any((body.get("chat_template_kwargs") or {}).values())
    if len(body.get("messages") or []) > 2:
        rendering = "history"
    else:
        rendering = "thinking" if asks_to_think else "plain"
    return json.dumps({"prompt": recorded[rendering]}).encode("utf-8")


class RecordedEndpoint:
    """Replay recorded llama-server replies over a local HTTP socket."""

    def __init__(
        self, status: int, *bodies: bytes, hold_s: float = 0.0, config_dir: Path = CONFIG_DIR
    ) -> None:
        if not bodies:
            raise ValueError("a recorded endpoint replays at least one body")
        served: list[int] = []
        sent: list[dict[str, Any]] = []
        replies = bodies

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                template = b'{"chat_template": "fixture-template"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(template)))
                self.end_headers()
                self.wfile.write(template)

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                payload = json.loads(raw)
                if self.path.endswith("/apply-template"):
                    self._answer(200, render_template_response(payload, config_dir=config_dir))
                    return
                sent.append(payload)
                body = replies[len(served) % len(replies)]
                served.append(1)
                if hold_s > 0:
                    time.sleep(hold_s)
                self._answer(status, body)

            def _answer(self, code: int, body: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return None

        self._served = served
        self._sent = sent
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def served(self) -> int:
        return len(self._served)

    @property
    def sent(self) -> list[dict[str, Any]]:
        return list(self._sent)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/v1/chat/completions"

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> RecordedEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)
