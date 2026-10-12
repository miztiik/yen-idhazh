"""How are typed local artifacts committed atomically and replayed by identity?"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter
from pydantic_core import to_jsonable_python

from idhazh.contracts.base import Model


def canonical(value: object) -> bytes:
    if isinstance(value, Model):
        value = value.model_dump(mode="json")
    return (
        json.dumps(
            to_jsonable_python(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        + "\n"
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_model(path: Path, value: Model) -> None:
    """Publish one complete payload; an interrupted .part file is never read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"immutable artifact differs: {path}")
        return
    part = path.with_suffix(path.suffix + ".part")
    with part.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        import os

        os.fsync(stream.fileno())
    part.replace(path)


def read_model[T: Model](path: Path, model: type[T] | TypeAdapter[T]) -> T:
    if isinstance(model, TypeAdapter):
        return model.validate_json(path.read_bytes())
    return model.model_validate_json(path.read_bytes())


class Store:
    """Index typed records in one transaction; never edit an earlier payload."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "state.sqlite3", timeout=60)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS artifacts(
                kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS records(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, id TEXT NOT NULL UNIQUE, subject TEXT NOT NULL,
                payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS subject_records ON records(kind,subject,sequence);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def get[T: Model](self, kind: str, identity: str, model: type[T] | TypeAdapter[T]) -> T:
        row = self.db.execute(
            "SELECT payload FROM artifacts WHERE kind=? AND id=?", (kind, identity)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown {kind}: {identity}")
        if isinstance(model, TypeAdapter):
            return model.validate_json(row[0])
        return model.model_validate_json(row[0])

    def save(self, kind: str, identity: str, value: Model) -> None:
        raw = canonical(value).decode()
        row = self.db.execute(
            "SELECT payload FROM artifacts WHERE kind=? AND id=?", (kind, identity)
        ).fetchone()
        if row is not None and row[0] != raw:
            raise ValueError(f"immutable {kind} differs: {identity}")
        self.db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?)", (kind, identity, raw))

    def append(self, kind: str, identity: str, subject: str, value: Model) -> None:
        self.db.execute(
            "INSERT INTO records(kind,id,subject,payload) VALUES(?,?,?,?)",
            (kind, identity, subject, canonical(value).decode()),
        )

    def records[T: Model](self, kind: str, model: type[T]) -> list[T]:
        return [
            model.model_validate_json(row[0])
            for row in self.db.execute(
                "SELECT payload FROM records WHERE kind=? ORDER BY sequence", (kind,)
            )
        ]

    def setting(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
