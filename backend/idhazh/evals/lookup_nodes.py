"""How capped SQLite leaves and bounded JSON routing pages encode evaluation IDs."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from idhazh.contracts.observation_lookup import (
    ObservationLookupEntry,
    ObservationLookupNode,
    ObservationLookupPage,
    ObservationLookupSettings,
)


def node_path(root: Path, node: ObservationLookupNode) -> Path:
    """Derive a path solely from a checked content digest and the storage vocabulary."""
    suffix = "sqlite" if node.kind == "leaf" else "json"
    return root / "nodes" / node.sha256[:2] / f"{node.sha256}.{suffix}"


def read_node(root: Path, node: ObservationLookupNode, limit: int) -> bytes:
    path = node_path(root, node)
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("an observation lookup node exceeds its declared byte bound")
    if hashlib.sha256(data).hexdigest() != node.sha256:
        raise ValueError("an observation lookup node does not match its content digest")
    return data


def read_page(
    root: Path, node: ObservationLookupNode, prefix: str, limit: int
) -> ObservationLookupPage:
    page = ObservationLookupPage.model_validate_json(read_node(root, node, limit))
    if page.prefix != prefix:
        raise ValueError("an observation routing page does not match its digest prefix")
    return page


def leaf_bytes(
    entries: Iterable[ObservationLookupEntry], settings: ObservationLookupSettings
) -> bytes:
    """Use SQLite's native index and serialization, with deterministic insertion order."""
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute(f"PRAGMA page_size = {settings.sqlite_page_bytes}")
        connection.execute(
            "CREATE TABLE entries (key TEXT PRIMARY KEY, entry_json TEXT NOT NULL) WITHOUT ROWID"
        )
        connection.executemany(
            "INSERT INTO entries (key, entry_json) VALUES (?, ?)",
            [
                (entry.key, entry.model_dump_json())
                for entry in sorted(entries, key=lambda value: value.key)
            ],
        )
        connection.commit()
        return connection.serialize()


def leaf_entries(data: bytes, keys: set[str] | None = None) -> dict[str, ObservationLookupEntry]:
    """Read a bounded leaf; candidate queries use its primary key, not a historical scan."""
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.deserialize(data)
        connection.execute("PRAGMA query_only = ON")
        if keys is None:
            records = connection.execute("SELECT key, entry_json FROM entries").fetchall()
        else:
            records = []
            for key in sorted(keys):
                records.extend(
                    connection.execute(
                        "SELECT key, entry_json FROM entries WHERE key = ?", (key,)
                    ).fetchall()
                )
        found: dict[str, ObservationLookupEntry] = {}
        for key, encoded in records:
            entry = ObservationLookupEntry.model_validate_json(encoded)
            if entry.key != key:
                raise ValueError("an observation lookup row does not match its primary key")
            found[key] = entry
        return found
