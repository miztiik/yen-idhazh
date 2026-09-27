"""How rows and their envelope become one JSON-lines file, and how they come back.

The second format behind the ledger door, and a first-class one: a payload a
person reads in a pull request should not be binary. Line one is the envelope,
every value a string exactly as a parquet footer holds it; every line after it
is one row. Keys are sorted and the text is ASCII, so the same rows are the same
bytes on every machine.

The row rendering here is also what `content_sha256` is taken over for either
format, so two files holding the same rows carry the same digest whatever their
container.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Iterable, Mapping
from typing import Any, Final

#: What a JSON-lines ledger file starts with: the envelope's opening brace.
MAGIC: Final = b"{"


def engine_version() -> str:
    """The interpreter's version: its standard `json` module is the engine here."""
    return platform.python_version()


def row_line(row: Mapping[str, Any]) -> str:
    """One row as one line: sorted keys, ASCII, no spaces, a trailing newline."""
    return json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"


def rows_bytes(rows: Iterable[Mapping[str, Any]]) -> bytes:
    """Every row, one a line, as the bytes a file holds after its envelope line."""
    return "".join(row_line(row) for row in rows).encode("ascii")


def render(rows: Iterable[Mapping[str, Any]], *, envelope: Mapping[bytes, bytes]) -> bytes:
    """One whole file: the envelope on line one, then one row a line."""
    head = {key.decode("utf-8"): value.decode("utf-8") for key, value in envelope.items()}
    return row_line(head).encode("ascii") + rows_bytes(rows)


def read(data: bytes) -> tuple[dict[bytes, bytes], list[dict[str, Any]]]:
    """A whole file back as its envelope and its rows, in file order.

    A first line that is not an object of strings is refused: whatever wrote it,
    it was not this module, and guessing at it would read somebody else's rows.
    """
    lines = data.decode("utf-8").splitlines()
    head = json.loads(lines[0]) if lines else None
    if not isinstance(head, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in head.items()
    ):
        raise ValueError("the first line is not an envelope of string values")
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("a row line is not a JSON object")
        rows.append(row)
    envelope = {key.encode("utf-8"): value.encode("utf-8") for key, value in head.items()}
    return envelope, rows
