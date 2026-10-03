"""Reapply one commit's named publication changes after an inventory conflict."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.publication import record_files, record_state_files


@dataclass(frozen=True)
class PublicationDelta:
    """The entries and UTC days changed by one committed inventory update."""

    public_paths: tuple[str, ...]
    state_paths: tuple[str, ...]
    dates: tuple[str, ...]
    remove_dates: tuple[str, ...]


def capture_publication_delta(before: str, after: str) -> PublicationDelta:
    """Compare two validated inventories without discovering any data files."""
    previous = PublicationInventory.model_validate_json(before)
    current = PublicationInventory.model_validate_json(after)
    old_entries = {(entry.root, entry.path): entry for entry in previous.entries}
    new_entries = {(entry.root, entry.path): entry for entry in current.entries}
    changed = {
        key
        for key in old_entries.keys() | new_entries.keys()
        if old_entries.get(key) != new_entries.get(key)
    }
    return PublicationDelta(
        public_paths=tuple(sorted(path for root, path in changed if root == "public")),
        state_paths=tuple(sorted(path for root, path in changed if root == "state")),
        dates=tuple(sorted(set(current.dates) - set(previous.dates))),
        remove_dates=tuple(sorted(set(previous.dates) - set(current.dates))),
    )


def replay_publication_delta(
    public_root: Path, state_root: Path, delta: PublicationDelta
) -> None:
    """Measure only this commit's named files through the production writers."""
    item_counts: dict[str, int] = {}
    for name in delta.public_paths:
        parts = name.split("/")
        if (
            len(parts) == 5
            and parts[0] == "digest"
            and parts[4] == "digest.json"
            and (public_root / name).is_file()
        ):
            day = DigestDay.read(public_root / name)
            expected = f"digest/{day.date.replace('-', '/')}/digest.json"
            if name != expected:
                raise ValueError(f"named digest path does not match its UTC day: {name}")
            item_counts[name] = len(day.items)
    if delta.public_paths or delta.dates or delta.remove_dates:
        record_files(
            public_root,
            dates=delta.dates,
            paths=delta.public_paths,
            item_counts=item_counts,
            remove_dates=delta.remove_dates,
        )
    if delta.state_paths:
        record_state_files(public_root, state_root, paths=delta.state_paths)
