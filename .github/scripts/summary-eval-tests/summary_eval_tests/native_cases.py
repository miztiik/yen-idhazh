"""Replay a named native model response at the external HTTPX boundary only."""

import asyncio
from typing import Final

import httpx
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from summary_evaluator_cases.contract_examples import REPOSITORY

# This operation belongs to the upstream native protocol, not the evaluation app.
LLAMA_COMPLETIONS_PATH: Final = "/v1/chat/completions"


class RecordedLlama:
    """Replay native HTTP responses while the real caller owns validation and transport."""

    def __init__(self) -> None:
        self.body = (
            REPOSITORY / "tests" / "fixtures" / "completions" / "reasoning-channel.json"
        ).read_bytes()
        self.status = 200
        self.health_status = 200
        self.health_body = b'{"status":"ok"}'
        self.response_headers = {"Location": "https://not-a-native-destination.invalid"}
        self.stream_body = False
        self.hold_generation = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.requests: list[tuple[str, bytes, dict[str, str]]] = []
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @self.app.get("/health")
        async def health() -> Response:
            return Response(
                self.health_body, status_code=self.health_status, media_type="application/json"
            )

        @self.app.post(LLAMA_COMPLETIONS_PATH)
        async def generation(request: Request) -> Response:
            self.requests.append((str(request.url), await request.body(), dict(request.headers)))
            self.started.set()
            try:
                if self.hold_generation:
                    await self.release.wait()
                if self.stream_body:
                    return StreamingResponse(
                        iter((self.body[: len(self.body) // 2], self.body[len(self.body) // 2 :])),
                        status_code=self.status,
                        media_type="application/json",
                        headers=self.response_headers,
                    )
                return Response(
                    self.body,
                    status_code=self.status,
                    media_type="application/json",
                    headers=self.response_headers,
                )
            except asyncio.CancelledError:
                self.cancelled.set()
                raise

    @property
    def transport(self) -> httpx.ASGITransport:
        return httpx.ASGITransport(app=self.app)
