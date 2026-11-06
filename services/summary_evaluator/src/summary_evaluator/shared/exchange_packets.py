"""Which byte-channel operations and fixed encoding bounds can workers share?"""

from typing import Protocol

RUNTIME_VERSION_MAX_CHARS = 128

JSON_ESCAPE_MAX_BYTES = 6

UUID4_EXAMPLE = "00000000-0000-4000-8000-000000000000"


class ByteChannel(Protocol):
    """Share only the byte operations implemented by POSIX and Windows pipes."""

    def send_bytes(self, buf: bytes) -> None: ...
    def recv_bytes(self, maxlength: int | None = None) -> bytes: ...
    def close(self) -> None: ...
