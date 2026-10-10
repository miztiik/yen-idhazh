"""How are bounded named inputs materialized from one chosen data tree?"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths
from utilities.publication_git import Repository
from utilities.publication_request import PLAIN_MODE, IntegrityError, relative, safe_file


def ledger_window(which: LedgerName, *, through: str, days: int) -> tuple[str, ...]:
    """Raw days, exact compact periods and three named indexes, never a ledger walk."""
    state = Path("state")
    raw = paths.raw_root(state, which)
    asked: set[str] = {
        paths.compact_index_path(state, which, period).as_posix() for period in Period
    }
    coverage: dict[Period, set[str]] = {period: set() for period in Period}
    end = date.fromisoformat(through)
    for offset in range(days):
        stamp = (end - timedelta(days=offset)).isoformat()
        asked.add((raw / stamp.replace("-", "/")).as_posix())
        for period, covers in (
            (Period.DAILY, stamp),
            (Period.MONTHLY, stamp[:7]),
            (Period.YEARLY, stamp[:4]),
        ):
            coverage[period].add(covers)
    for period, periods in coverage.items():
        if not periods:
            continue
        sample_date = min(periods)
        sample = paths.compact_path(state, which, period, sample_date)
        sample_parts = (
            sample_date.split("-")
            if period is not Period.YEARLY
            else [
                sample_date,
                sample_date,
            ]
        )
        if sample.with_suffix("").parts[-len(sample_parts) :] != tuple(sample_parts):
            raise IntegrityError("compact period layout changed; update the bounded input policy")
        root = sample.parents[len(sample_parts) - 1]
        for covers in periods:
            parts = covers.split("-") if period is not Period.YEARLY else [covers, covers]
            held = root.joinpath(*parts)
            asked.update(held.with_suffix(suffix).as_posix() for suffix in (".parquet", ".json"))
    return tuple(sorted(asked))


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
