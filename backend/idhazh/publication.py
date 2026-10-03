"""Maintain a named publication inventory from the day and file names a writer already holds."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from idhazh.atomic_write import write_atomic
from idhazh.contracts.base import DateStamp, RelPath, StalePayloadError
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.publication_inventory import (
    LegacyPublicationInventory,
    PublicationEntry,
    PublicationInventory,
)
from idhazh.publication_lock import serialize_update

# A published protocol filename, shared with the static build's reader.
PUBLICATION_FILENAME: Final = "publication.json"
_RELATIVE_PATH: Final = TypeAdapter(RelPath)
_DATE_STAMP: Final = TypeAdapter(DateStamp)


def read_inventory(public_root: Path) -> PublicationInventory:
    """Read one named file; never infer missing history from a directory."""
    path = public_root / PUBLICATION_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            "publication.json is missing; initialize it with "
            "python -m utilities.publication_inventory --public-root <root> "
            "--seed <named-inventory.json>. Use --empty only for a new fixture tree."
        )
    try:
        return PublicationInventory.read(path)
    except StalePayloadError as error:
        raise ValueError(
            "publication.json needs a named-file migration; run "
            "python -m utilities.publication_inventory --public-root <root> --upgrade"
        ) from error


@serialize_update
def initialize_inventory(
    public_root: Path, *, seed: PublicationInventory, state_root: Path | None = None
) -> PublicationInventory:
    """Install an explicit named-input migration, refusing to overwrite an inventory."""
    target = public_root / PUBLICATION_FILENAME
    if target.exists():
        raise FileExistsError("publication.json already exists; update it through its writer")
    missing = [
        entry.path
        for entry in seed.entries
        if entry.root == "public" and not (public_root / entry.path).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"seed names missing public files: {', '.join(missing)}")
    state_names = [entry.path for entry in seed.entries if entry.root == "state"]
    if state_names:
        if state_root is None:
            raise ValueError("state_root is required for named state files")
        missing_state = [name for name in state_names if not (state_root / name).is_file()]
        if missing_state:
            raise FileNotFoundError(f"seed names missing state files: {', '.join(missing_state)}")
    write_atomic(target, seed.to_json())
    return seed


def initialize_from_paths(
    public_root: Path,
    *,
    paths: Iterable[str],
    state_root: Path | None = None,
    state_paths: Iterable[str] = (),
) -> PublicationInventory:
    """Measure an explicit public-root-relative list to seed every named historical day."""
    names = sorted({_RELATIVE_PATH.validate_python(name) for name in paths})
    days: set[str] = set()
    entries = []
    for name in names:
        if name == PUBLICATION_FILENAME:
            raise ValueError("publication.json cannot inventory itself")
        path = public_root / name
        count = 0
        if name.startswith("digest/") and name.endswith("/digest.json"):
            day = DigestDay.read(path)
            if name != f"digest/{day.date.replace('-', '/')}/digest.json":
                raise ValueError(f"named digest path does not match its UTC day: {name}")
            days.add(day.date)
            count = len(day.items)
        entries.append(PublicationEntry(path=name, bytes=path.stat().st_size, items=count))
    state_names = sorted({_RELATIVE_PATH.validate_python(name) for name in state_paths})
    if state_names and state_root is None:
        raise ValueError("state_root is required for named state files")
    if state_root is not None:
        entries.extend(
            PublicationEntry(
                root="state", path=name, bytes=(state_root / name).stat().st_size, items=0
            )
            for name in state_names
        )
    seed = PublicationInventory(
        version=PublicationInventory.schema_version(),
        dates=sorted(days, reverse=True),
        entries=entries,
        total_bytes=sum(entry.bytes for entry in entries if entry.root == "public"),
        total_items=sum(entry.items for entry in entries if entry.root == "public"),
    )
    return initialize_inventory(public_root, seed=seed, state_root=state_root)


@serialize_update
def record_files(
    public_root: Path,
    *,
    dates: Iterable[str] = (),
    paths: Iterable[str],
    item_counts: Mapping[str, int] | None = None,
    remove_dates: Iterable[str] = (),
) -> PublicationInventory:
    """Refresh only named files, preserving all other inventory entries.

    Reads one named manifest and checks the caller's named list. No data tree
    is listed. The manifest's bytes grow with its entries; that named-file read
    is explicit, rather than an implicit archive scan.
    """
    previous = read_inventory(public_root)
    added_days = {_DATE_STAMP.validate_python(day) for day in dates}
    removed_days = {_DATE_STAMP.validate_python(day) for day in remove_dates}
    if added_days & removed_days:
        raise ValueError("dates and remove_dates must be disjoint")
    days = set(previous.dates).union(added_days)
    digests = {f"digest/{day.replace('-', '/')}/digest.json" for day in days}
    named = {_RELATIVE_PATH.validate_python(name) for name in paths}
    counts = dict(item_counts or {})
    if set(counts).difference(named):
        raise ValueError("item_counts must name files in this update")
    entries = {entry.path: entry for entry in previous.entries if entry.root == "public"}
    state_entries = [entry for entry in previous.entries if entry.root == "state"]
    total_bytes, total_items = previous.total_bytes, previous.total_items
    for name in sorted(named):
        old = entries.pop(name, None)
        if old is not None:
            total_bytes -= old.bytes
            total_items -= old.items
        path = public_root / name
        if not path.is_file():
            continue
        if name in digests and old is None and name not in counts:
            raise ValueError(f"new digest entry {name} requires its item_counts value")
        entry = PublicationEntry(
            path=name,
            bytes=path.stat().st_size,
            items=counts.get(name, old.items if old is not None else 0),
        )
        entries[name] = entry
        total_bytes += entry.bytes
        total_items += entry.items
    # A concurrent origin entry for this day wins if its digest still exists.
    days.difference_update(removed_days)
    days.update(
        day
        for day in removed_days
        if f"digest/{day.replace('-', '/')}/digest.json" in entries
    )
    inventory = PublicationInventory(
        version=PublicationInventory.schema_version(),
        dates=sorted(days, reverse=True),
        entries=[entries[name] for name in sorted(entries)] + state_entries,
        total_bytes=total_bytes,
        total_items=total_items,
    )
    if inventory.to_json() != previous.to_json():
        write_atomic(public_root / PUBLICATION_FILENAME, inventory.to_json())
    return inventory


@serialize_update
def record_state_files(
    public_root: Path, state_root: Path, *, paths: Iterable[str]
) -> PublicationInventory:
    """Register only caller-named state files, keeping public totals unchanged."""
    previous = read_inventory(public_root)
    entries = {(entry.root, entry.path): entry for entry in previous.entries}
    for name in {_RELATIVE_PATH.validate_python(name) for name in paths}:
        entries.pop(("state", name), None)
        path = state_root / name
        if path.is_file():
            entries[("state", name)] = PublicationEntry(
                root="state", path=name, bytes=path.stat().st_size, items=0
            )
    inventory = PublicationInventory(
        version=PublicationInventory.schema_version(),
        dates=previous.dates,
        entries=[entries[key] for key in sorted(entries)],
        total_bytes=previous.total_bytes,
        total_items=previous.total_items,
    )
    if inventory.to_json() != previous.to_json():
        write_atomic(public_root / PUBLICATION_FILENAME, inventory.to_json())
    return inventory


def record_feed_health(
    public_root: Path,
    state_root: Path,
    *,
    dates: Iterable[str],
    run_id: str,
    attempt: int,
    job: str,
    shard: int,
) -> PublicationInventory:
    """Register this feed-health writer's paths, derived only from its known UTC days."""
    from idhazh.contracts.base import ServerJob
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.ledger.rows import day_shard_path

    paths = [
        day_shard_path(
            state_root,
            LedgerName.FEED_HEALTH,
            date=day,
            run_id=run_id,
            attempt=attempt,
            job=ServerJob(job),
            shard=shard,
        )
        .relative_to(state_root)
        .as_posix()
        for day in sorted(set(dates))
    ]
    return record_state_files(public_root, state_root, paths=paths)


def record_day(public_root: Path, day: DigestDay) -> PublicationInventory:
    """Record one day and recompute each visual filename from its validated item identity."""
    prefix = f"digest/{day.date.replace('-', '/')}"
    paths = [f"{prefix}/digest.json", f"{prefix}/run.json"]
    paths.extend(f"{prefix}/{item.item_id}.json" for item in day.items if item.visual is not None)
    return record_files(
        public_root,
        dates=[day.date],
        paths=paths,
        item_counts={f"{prefix}/digest.json": len(day.items)},
    )


@serialize_update
def upgrade_inventory(public_root: Path, *, state_root: Path | None = None) -> PublicationInventory:
    """Migrate the legacy named inventory by reading only its explicit file list."""
    target = public_root / PUBLICATION_FILENAME
    legacy = LegacyPublicationInventory.model_validate_json(target.read_text(encoding="utf-8"))
    entries = []
    digests = {f"digest/{day.replace('-', '/')}/digest.json" for day in legacy.dates}
    public_names = [name for name in legacy.files if not name.startswith("state/")]
    state_names = sorted(
        set(legacy.state_files).union(
            name.removeprefix("state/") for name in legacy.files if name.startswith("state/")
        )
    )
    for name in public_names:
        path = public_root / name
        count = 0
        if name in digests:
            count = len(DigestDay.read(path).items)
        entries.append(PublicationEntry(path=name, bytes=path.stat().st_size, items=count))
    if state_names and state_root is None:
        raise ValueError("state_root is required for named state files")
    if state_root is not None:
        entries.extend(
            PublicationEntry(
                root="state", path=name, bytes=(state_root / name).stat().st_size, items=0
            )
            for name in state_names
        )
    inventory = PublicationInventory(
        version=PublicationInventory.schema_version(),
        dates=legacy.dates,
        entries=entries,
        total_bytes=sum(entry.bytes for entry in entries if entry.root == "public"),
        total_items=sum(entry.items for entry in entries if entry.root == "public"),
    )
    write_atomic(target, inventory.to_json())
    return inventory


def record_month(public_root: Path, month: str) -> PublicationInventory:
    """Refresh the named month of each published series, without listing a directory."""
    from idhazh.contracts.base import MonthStamp
    from idhazh.telemetry.publish.public_telemetry import PUBLIC_TELEMETRY_DIRNAME
    from idhazh.telemetry.publish.series import BAND_FILENAME, CONSOLE_DIRNAME, MONTH_SERIES
    from idhazh.telemetry.publish.source_health import PUBLIC_FILENAME

    month = TypeAdapter(MonthStamp).validate_python(month)
    date.fromisoformat(f"{month}-01")
    paths = [
        f"assist/index/{month}.json",
        f"assist/index/{month}.bin",
        f"{PUBLIC_TELEMETRY_DIRNAME}/{month}.csv",
        *(f"{dirname}/{month}{suffix}" for dirname, suffix in MONTH_SERIES),
        f"{CONSOLE_DIRNAME}/{BAND_FILENAME}",
        PUBLIC_FILENAME,
    ]
    return record_files(public_root, paths=paths)
