"""How are bounded named inputs materialized from one chosen data tree?"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.window_inputs import CompactLayoutChangedError, inputs_of_days
from utilities.publication_git import Repository
from utilities.publication_request import PLAIN_MODE, IntegrityError, relative, safe_file


def ledger_window(which: LedgerName, *, through: str, days: int) -> tuple[str, ...]:
    """Raw days, exact compact periods and three named indexes, never a ledger walk.

    The `days` days that end on `through`, named by `idhazh.ledger.window_inputs`. A layout
    that no longer matches is an integrity failure here, as it always was for the digest tool.
    """
    end = date.fromisoformat(through)
    try:
        return inputs_of_days(
            which, ((end - timedelta(days=offset)).isoformat() for offset in range(days))
        )
    except CompactLayoutChangedError as error:
        raise IntegrityError(str(error)) from error


def named_entries(
    git: Repository,
    tree: str,
    inputs: Sequence[str],
) -> dict[str, tuple[str, str, str]]:
    """Tree entries under concrete bounded inputs, batched below argv limits."""
    inputs = tuple(dict.fromkeys(inputs))
    for asked in inputs:
        relative(asked)
    entries: dict[str, tuple[str, str, str]] = {}
    batch: list[str] = []
    size = 0
    batches: list[list[str]] = []
    for asked in inputs:
        if size + len(asked) > 16000 and batch:
            batches.append(batch)
            batch, size = [], 0
        batch.append(asked)
        size += len(asked) + 1
    if batch:
        batches.append(batch)
    for batch in batches:
        for line in git.git("ls-tree", "-r", "-z", tree, "--", *batch).split("\0"):
            if not line:
                continue
            metadata, path = line.split("\t", 1)
            mode, kind, oid = metadata.split()
            entries[path] = mode, kind, oid
    git.prime(tree, set(inputs) | set(entries))
    for asked in inputs:
        git.parents_safe(tree, asked)
    return entries


def materialize(
    git: Repository,
    tree: str,
    inputs: Sequence[str],
    destination: Path,
    *,
    preserve_existing: bool = False,
) -> tuple[str, ...]:
    """Fetch only blobs named by bounded inputs; missing materialization is an error."""
    written: list[str] = []
    entries = named_entries(git, tree, inputs)
    for path, (mode, kind, oid) in entries.items():
        if mode != PLAIN_MODE or kind != "blob":
            raise IntegrityError("input is not a plain data file", (path,))
        git.parents_safe(tree, path)
        target = safe_file(destination, path, exists=False)
        data = git.blob(oid, fetches=True)
        if preserve_existing and target.exists() and target.read_bytes() != data:
            raise IntegrityError("named input has foreign local changes", (path,))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(path)
    return tuple(written)
