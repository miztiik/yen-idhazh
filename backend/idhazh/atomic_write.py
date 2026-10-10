"""How a file is written so that it either exists complete or does not exist at all.

A temp file in the destination's own directory, written whole, then moved onto
the target. A reader that opens the path mid-write sees the old file or none,
never half of the new one.

It is a module of its own because the one rule should have one home that costs
nothing to import. `idhazh.assemble` loads the embedder, placement, ranking and
tagging stages when it loads, so a caller that borrowed these two from there
paid for all of that just to write a file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from idhazh import completed_writes


def write_atomic(path: Path, text: str) -> None:
    """Temp-then-rename, so a file either exists complete or does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    )
    try:
        with handle:
            handle.write(text)
        Path(handle.name).replace(path)
        completed_writes.record(path, text.encode("utf-8"))
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def write_atomic_bytes(path: Path, data: bytes) -> None:
    """The same guarantee for a file that is not text.

    The vector sibling is raw int8. Writing it through the text path would let a
    host's line-ending rules rewrite bytes inside a vector.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False)
    try:
        with handle:
            handle.write(data)
        Path(handle.name).replace(path)
        completed_writes.record(path, data)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
