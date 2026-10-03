"""Look up incoming evaluation IDs without opening unrelated historical partitions."""

from __future__ import annotations

import hashlib
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from idhazh.atomic_write import write_atomic, write_atomic_bytes
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.observation_lookup import (
    ObservationLookupEntry,
    ObservationLookupNode,
    ObservationLookupPage,
    ObservationLookupReceipt,
    ObservationLookupRoot,
    ObservationLookupSettings,
    ObservationLookupTransaction,
)
from idhazh.evals.lookup_nodes import leaf_bytes, leaf_entries, node_path, read_node, read_page

ROOT_NAME = "root.json"
TRANSACTION_NAME = ".transaction.json"
LOCK_NAME = ".observation-lookup-lock"


class ObservationLookup:
    """One locally serialized update; Git serializes complete generations across jobs."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.changed: set[Path] = set()
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> Self:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.root / LOCK_NAME)
        try:
            connection.execute("BEGIN EXCLUSIVE")
            self._connection = connection
            self._recover()
        except BaseException:
            connection.close()
            self._connection = None
            raise
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            self._connection.rollback()
            self._connection.close()
            self._connection = None

    def manifest(self) -> ObservationLookupRoot:
        if self._connection is None:
            raise RuntimeError("an observation lookup must be opened as a context manager")
        path = self.root / ROOT_NAME
        if not path.is_file():
            raise FileNotFoundError(
                "the observation lookup is missing; migrate it explicitly before recording"
            )
        return ObservationLookupRoot.read(path)

    def initialize(self, key_fields: tuple[str, ...], settings: ObservationLookupSettings) -> None:
        if (self.root / ROOT_NAME).exists():
            raise FileExistsError("the observation lookup already exists")
        data = leaf_bytes([], settings)
        node = ObservationLookupNode(kind="leaf", sha256=hashlib.sha256(data).hexdigest())
        root = ObservationLookupRoot.model_validate(
            {
                "generation": derive_text_digest(canonical_json([key_fields, node.sha256])),
                "key_fields": key_fields,
                "node": node,
                "settings": settings,
            }
        )
        self._publish(None, root, {node_path(self.root, node): (node, data)}, [])

    def find(
        self, namespace: Literal["observation", "batch"], identities: Iterable[str]
    ) -> dict[str, ObservationLookupEntry]:
        wanted = {
            derive_text_digest(canonical_json([namespace, identity])): identity
            for identity in identities
        }
        if not wanted:
            return {}
        root = self.manifest()
        found = self._find_node(root.node, "", set(wanted), root.settings.max_leaf_bytes)
        return {wanted[key]: entry for key, entry in found.items()}

    def recorded(self, identities: Iterable[str]) -> set[str]:
        return set(self.find("observation", identities))

    def receipt(self, batch_id: str) -> ObservationLookupReceipt | None:
        entry = self.find("batch", [batch_id]).get(batch_id)
        return None if entry is None else entry.receipt

    def put(self, entries: Iterable[ObservationLookupEntry], *, generation: str) -> None:
        root = self.manifest()
        updates = {entry.key: entry for entry in entries}
        if not updates:
            return
        created: dict[Path, tuple[ObservationLookupNode, bytes]] = {}
        superseded: list[ObservationLookupNode] = []
        node = self._update(root.node, "", updates, root.settings, created, superseded)
        if node == root.node:
            return
        if generation == root.generation:
            raise ValueError("a changed observation lookup needs a new generation")
        after = ObservationLookupRoot.model_validate(
            {**root.model_dump(mode="json"), "generation": generation, "node": node}
        )
        self._publish(root.generation, after, created, superseded)

    def _find_node(
        self, node: ObservationLookupNode, prefix: str, keys: set[str], limit: int
    ) -> dict[str, ObservationLookupEntry]:
        if node.kind == "leaf":
            return leaf_entries(read_node(self.root, node, limit), keys)
        page = read_page(self.root, node, prefix, limit)
        groups: dict[str, set[str]] = defaultdict(set)
        for key in keys:
            groups[key[len(prefix)]].add(key)
        found: dict[str, ObservationLookupEntry] = {}
        for digit, selected in groups.items():
            child = page.children.get(digit)
            if child is not None:
                found.update(self._find_node(child, prefix + digit, selected, limit))
        return found

    def _save(
        self,
        kind: Literal["leaf", "page"],
        data: bytes,
        created: dict[Path, tuple[ObservationLookupNode, bytes]],
    ) -> ObservationLookupNode:
        node = ObservationLookupNode(kind=kind, sha256=hashlib.sha256(data).hexdigest())
        created[node_path(self.root, node)] = (node, data)
        return node

    def _pack(
        self,
        prefix: str,
        entries: Mapping[str, ObservationLookupEntry],
        settings: ObservationLookupSettings,
        created: dict[Path, tuple[ObservationLookupNode, bytes]],
    ) -> ObservationLookupNode:
        data = leaf_bytes(entries.values(), settings)
        if len(data) <= settings.max_leaf_bytes:
            return self._save("leaf", data, created)
        if len(entries) <= 1 or len(prefix) >= 64:
            raise ValueError("max_leaf_bytes cannot hold one observation lookup entry")
        groups: dict[str, dict[str, ObservationLookupEntry]] = defaultdict(dict)
        for key, entry in entries.items():
            groups[key[len(prefix)]][key] = entry
        children = {
            digit: self._pack(prefix + digit, group, settings, created)
            for digit, group in sorted(groups.items())
        }
        page = ObservationLookupPage.model_validate({"prefix": prefix, "children": children})
        return self._save("page", page.to_json().encode("utf-8"), created)

    def _update(
        self,
        node: ObservationLookupNode,
        prefix: str,
        updates: Mapping[str, ObservationLookupEntry],
        settings: ObservationLookupSettings,
        created: dict[Path, tuple[ObservationLookupNode, bytes]],
        superseded: list[ObservationLookupNode],
    ) -> ObservationLookupNode:
        if node.kind == "leaf":
            held = leaf_entries(read_node(self.root, node, settings.max_leaf_bytes))
            for key, entry in updates.items():
                previous = held.get(key)
                if previous is not None and previous != entry:
                    raise ValueError("an applied observation lookup entry cannot be replaced")
                held[key] = entry
            after = self._pack(prefix, held, settings, created)
        else:
            page = read_page(self.root, node, prefix, settings.max_leaf_bytes)
            children = dict(page.children)
            groups: dict[str, dict[str, ObservationLookupEntry]] = defaultdict(dict)
            for key, entry in updates.items():
                groups[key[len(prefix)]][key] = entry
            for digit, group in groups.items():
                child = children.get(digit)
                children[digit] = (
                    self._pack(prefix + digit, group, settings, created)
                    if child is None
                    else self._update(child, prefix + digit, group, settings, created, superseded)
                )
            after_page = ObservationLookupPage.model_validate(
                {"prefix": prefix, "children": children}
            )
            after = self._save("page", after_page.to_json().encode("utf-8"), created)
        if node != after:
            superseded.append(node)
        else:
            created.pop(node_path(self.root, after), None)
        return after

    def _publish(
        self,
        before: str | None,
        after: ObservationLookupRoot,
        created: dict[Path, tuple[ObservationLookupNode, bytes]],
        superseded: list[ObservationLookupNode],
    ) -> None:
        transaction = ObservationLookupTransaction.model_validate(
            {
                "before": before,
                "after": after.generation,
                "created": [node for node, _ in created.values()],
                "superseded": superseded,
            }
        )
        write_atomic(self.root / TRANSACTION_NAME, transaction.to_json())
        for path, (_, data) in created.items():
            write_atomic_bytes(path, data)
            self.changed.add(path)
        write_atomic(self.root / ROOT_NAME, after.to_json())
        self.changed.add(self.root / ROOT_NAME)
        self._recover()

    def _recover(self) -> None:
        path = self.root / TRANSACTION_NAME
        if not path.exists():
            return
        transaction = ObservationLookupTransaction.read(path)
        root_path = self.root / ROOT_NAME
        current = ObservationLookupRoot.read(root_path).generation if root_path.exists() else None
        if current == transaction.after:
            retained = {(node.kind, node.sha256) for node in transaction.created}
            obsolete = [
                node for node in transaction.superseded
                if (node.kind, node.sha256) not in retained
            ]
        elif current == transaction.before:
            retained = {(node.kind, node.sha256) for node in transaction.superseded}
            obsolete = [
                node for node in transaction.created
                if (node.kind, node.sha256) not in retained
            ]
        else:
            raise ValueError("the interrupted observation update belongs to another generation")
        for node in obsolete:
            target = node_path(self.root, node)
            target.unlink(missing_ok=True)
            self.changed.add(target)
        path.unlink()
