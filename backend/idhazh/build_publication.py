"""Record the files in one freshly generated adapter-static output directory."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

from idhazh.atomic_write import write_atomic
from idhazh.contracts.publication_inventory import PublicationEntry, PublicationInventory

# This sibling protocol file is never inside the directory uploaded to Pages.
BUILD_INVENTORY_SUFFIX: Final = ".publication.json"
_DIGEST_PATH: Final = re.compile(r"^digest/(\d{4})/(\d{2})/(\d{2})/digest\.json$")


def inventory_path(tree: Path) -> Path:
    """The build's inventory beside, not inside, its deployed output."""
    return tree.with_name(tree.name + BUILD_INVENTORY_SUFFIX)


def read_build_inventory(tree: Path) -> PublicationInventory:
    """Read the one build inventory; missing and invalid records stop the gate."""
    path = inventory_path(tree)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path.name} is missing; run npm run build, then idhazh site-weight"
        )
    inventory = PublicationInventory.read(path)
    if any(entry.root != "public" for entry in inventory.entries):
        raise ValueError("a build inventory must contain only deployed public files")
    return inventory


def record_build_inventory(tree: Path) -> PublicationInventory:
    """Inventory one generated tree, right before the site-weight step measures it."""
    inventory_path(tree).unlink(missing_ok=True)
    if not tree.is_dir():
        raise FileNotFoundError("adapter-static output is missing; run npm run build first")
    entries: list[PublicationEntry] = []
    dates: set[str] = set()
    for path in tree.rglob("*"):
        if path.is_symlink():
            raise ValueError("adapter-static output must not contain symlinks")
        if not path.is_file():
            continue
        name = path.relative_to(tree).as_posix()
        items = 0
        match = _DIGEST_PATH.fullmatch(name)
        if match:
            day = "-".join(match.groups())
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("date") != day:
                raise ValueError(f"built digest date does not match its path: {name}")
            held = payload.get("items")
            if not isinstance(held, list):
                raise ValueError(f"built digest has no items list: {name}")
            items = len(held)
            dates.add(day)
        entries.append(PublicationEntry(path=name, bytes=path.stat().st_size, items=items))
    inventory = PublicationInventory(
        version=PublicationInventory.schema_version(),
        dates=sorted(dates, reverse=True),
        entries=sorted(entries, key=lambda entry: entry.path),
        total_bytes=sum(entry.bytes for entry in entries),
        total_items=sum(entry.items for entry in entries),
    )
    write_atomic(inventory_path(tree), inventory.to_json())
    return inventory
