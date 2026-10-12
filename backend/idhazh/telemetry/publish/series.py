"""Where is the console band written, and have its bytes changed?"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from idhazh.atomic_write import write_atomic_bytes

CONSOLE_DIRNAME: Final = "console"
BAND_FILENAME: Final = "band.json"
PUBLISHED_ROOTS: Final[tuple[str, ...]] = (CONSOLE_DIRNAME,)


def console_root(digest_root: Path) -> Path:
    """The public root derived from this run's digest root."""
    return digest_root.parent


def relpath(dirname: str, name: str) -> str:
    """The repository-relative public path for a log line."""
    return f"frontend/public/{dirname}/{name}"


def write_if_changed(path: Path, payload: bytes) -> bool:
    """Write only changed bytes, without treating a timestamp as content."""
    if path.exists() and path.read_bytes() == payload:
        return False
    write_atomic_bytes(path, payload)
    return True
