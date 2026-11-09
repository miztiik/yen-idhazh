"""How does the caller mirror every native API stderr event until confirmed EOF?"""

import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from capture_stream import EventFile, EventRecords, mirror_record
from gliner_api.declare_event_contracts import EVENT_SOURCE as GLINER_SOURCE
from gliner_api.declare_event_contracts import GlinerEvent
from gliner_api.load_settings import GlinerSettings
from text_analysis.declare_api_contracts import EVENT_SOURCE as SPACY_SOURCE
from text_analysis.declare_api_contracts import TextAnalysisEvent
from text_analysis.declare_service_settings import ServiceSettings


@dataclass(frozen=True)
class EventRoute:
    limit: int
    validate: Callable[[bytes], object]
    destination: EventFile


class ApiEventCapture:
    """Own the two fixed provider sinks and one nonblocking stderr reader."""

    def __init__(self, directory: Path, console: IO[bytes]) -> None:
        spacy = ServiceSettings.model_validate_json(
            (directory / "spacy" / "settings.json").read_bytes()
        )
        gliner = GlinerSettings.model_validate_json(
            (directory / "gliner" / "settings.json").read_bytes()
        )
        self.errors: set[str] = set()
        self.console = console
        self.routes = {
            SPACY_SOURCE: EventRoute(
                spacy.logging.max_event_bytes,
                TextAnalysisEvent.model_validate_json,
                EventFile(directory / "spacy" / "events.jsonl", "spaCy", self.errors),
            ),
            GLINER_SOURCE: EventRoute(
                gliner.logging.max_event_bytes,
                GlinerEvent.model_validate_json,
                EventFile(directory / "gliner" / "events.jsonl", "GLiNER", self.errors),
            ),
        }
        self.records = EventRecords(
            max(route.limit for route in self.routes.values()), self.receive, self.errors
        )
        self.pipe: IO[bytes] | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.eof: asyncio.Future[None] | None = None

    def receive(self, record: bytes) -> None:
        try:
            payload = json.loads(record.decode("utf-8"))
            source = payload.get("source") if isinstance(payload, dict) else None
            if not isinstance(source, str) or source not in self.routes:
                raise ValueError("Unrecognized native event source.")
            route = self.routes[source]
            if len(record) > route.limit:
                self.errors.add("An API stderr record exceeded its provider event byte limit.")
                return
            route.validate(record)
        except (ValueError, RecursionError):
            self.errors.add("An API stderr record was malformed or not a recognized native event.")
            return
        mirror_record(record, route.destination, self.console, self.errors)

    def start(self, pipe: IO[bytes] | None) -> None:
        if pipe is None:
            raise ValueError("The API stderr pipe is unavailable.")
        self.pipe = pipe
        self.loop = asyncio.get_running_loop()
        self.eof = self.loop.create_future()
        os.set_blocking(pipe.fileno(), False)
        self.loop.add_reader(pipe.fileno(), self.read_ready)

    def read_ready(self) -> None:
        if self.pipe is None:
            return
        try:
            chunk = os.read(self.pipe.fileno(), self.records.limit)
        except BlockingIOError:
            return
        except OSError:
            self.errors.add("The API stderr stream could not be drained.")
            self.close_pipe()
            return
        if chunk:
            self.records.feed(chunk)
        else:
            self.close_pipe()

    def close_pipe(self) -> None:
        if self.pipe is not None:
            if self.loop is not None:
                self.loop.remove_reader(self.pipe.fileno())
            try:
                self.pipe.close()
            except OSError:
                self.errors.add("The API stderr stream could not be closed.")
            self.pipe = None
        if self.eof is not None and not self.eof.done():
            self.eof.set_result(None)

    async def finish(self, timeout: float) -> str | None:
        if self.eof is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.eof), timeout=timeout)
            except TimeoutError:
                self.errors.add("The API stderr stream did not reach EOF after process cleanup.")
        self.close_pipe()
        self.records.finish()
        for route in self.routes.values():
            route.destination.finish()
        return " ".join(sorted(self.errors)) or None
