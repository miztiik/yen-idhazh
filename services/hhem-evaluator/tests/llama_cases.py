"""Replay a named native model response at the external HTTPX boundary only."""

import asyncio

import httpx
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from hhem_evaluator.contracts.llama_settings import LlamaSettings
from hhem_evaluator.forward_llama import LLAMA_COMPLETIONS_PATH
from hhem_evaluator.load_llama_settings import load_llama_settings

from .contract_examples import REPOSITORY


class RecordedLlama:
    """Leave validation, forwarding, admission and cancellation in the real API."""

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


def llama_settings(timeout_ms: float = 5000) -> LlamaSettings:
    selected = load_llama_settings(REPOSITORY / "config" / "idhazh.json")
    return LlamaSettings.model_validate_json(
        selected.model_copy(update={"request_timeout_ms": timeout_ms}).model_dump_json()
    )


def generation_body() -> bytes:
    return (
        b'{"model":"selected-native-model","messages":['
        b'{"role":"system","content":"Summarize the supplied text."},'
        b'{"role":"user","content":" PrivateSourceCanary\\nunchanged. "}],'
        b'"stream":false,"temperature":0.2,"max_tokens":4096,'
        b'"chat_template_kwargs":{"enable_thinking":false},"response_format":{"type":"json_object"}}'
    )
