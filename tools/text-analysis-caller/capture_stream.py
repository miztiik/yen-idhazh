"""How are bounded JSONL records delivered without losing a valid file prefix?"""

import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import IO


@contextmanager
def open_event_stream(directory: Path) -> Iterator[IO[bytes]]:
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
        yield stream


class EventRecords:
    """Frame byte chunks without retaining an oversized or unterminated record."""

    def __init__(self, limit: int, receive: Callable[[bytes], None], errors: set[str]) -> None:
        self.limit = limit
        self.receive = receive
        self.errors = errors
        self.pending = bytearray()
        self.discarding = False

    def feed(self, chunk: bytes) -> None:
        for index, part in enumerate(chunk.split(b"\n")):
            if index:
                if not self.discarding:
                    self.receive(bytes(self.pending) + b"\n")
                self.pending.clear()
                self.discarding = False
            if len(self.pending) + len(part) >= self.limit:
                self.errors.add("An API stderr record exceeded the native event byte limit.")
                self.pending.clear()
                self.discarding = True
            elif not self.discarding:
                self.pending.extend(part)

    def finish(self) -> None:
        if self.pending or self.discarding:
            self.errors.add("The API stderr stream ended with an incomplete event record.")
        self.pending.clear()


class EventFile:
    """Atomically publish only complete records, including after a write failure."""

    def __init__(self, path: Path, provider: str, errors: set[str]) -> None:
        self.path = path
        self.provider = provider
        self.errors = errors
        self.resources = ExitStack()
        self.stream: IO[bytes] | None = None
        self.temporary: Path | None = None
        self.length = 0
        self.failed = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = self.resources.enter_context(open_event_stream(path.parent))
            self.stream = stream
            self.temporary = Path(stream.name)
        except OSError:
            self.failed = True
            self.errors.add(f"The {provider} event file could not be opened.")

    def write(self, record: bytes) -> None:
        if self.failed or self.stream is None:
            return
        try:
            if self.stream.write(record) != len(record):
                raise OSError("Incomplete event write.")
            self.stream.flush()
            self.length += len(record)
        except (OSError, ValueError):
            self.failed = True
            self.errors.add(f"The {self.provider} event file could not be written.")

    def finish(self) -> None:
        try:
            self.resources.close()
        except (OSError, ValueError):
            self.errors.add(f"The {self.provider} event file could not be closed.")
        if self.temporary is None:
            return
        try:
            with self.temporary.open("r+b") as stream:
                stream.truncate(self.length)
                stream.flush()
                os.fsync(stream.fileno())
            self.temporary.replace(self.path)
        except OSError:
            self.errors.add(f"The {self.provider} event file could not be finalized.")


def mirror_record(
    record: bytes, destination: EventFile, console: IO[bytes], errors: set[str]
) -> None:
    """Deliver an already validated record independently to both destinations."""
    destination.write(record)
    try:
        if console.write(record) != len(record):
            raise OSError("Incomplete console write.")
        console.flush()
    except (OSError, ValueError):
        errors.add("An API event could not be delivered to the workflow console.")
