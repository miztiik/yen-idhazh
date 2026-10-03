"""Resolve only the files and UTC days an operator named."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path


def day_files(root: Path, days: Sequence[str], filename: str = "digest.json") -> list[Path]:
    """Build one address per named UTC day, without discovering neighbours."""
    if not days:
        raise ValueError("name at least one UTC day")
    paths: list[Path] = []
    for named in sorted(set(days)):
        parsed = date.fromisoformat(named)
        if parsed.isoformat() != named:
            raise ValueError(f"UTC day must be YYYY-MM-DD: {named!r}")
        paths.append(
            root / f"{parsed.year:04}" / f"{parsed.month:02}" / f"{parsed.day:02}" / filename
        )
    return paths


def named_files(root: Path, names: Sequence[str]) -> list[Path]:
    """Resolve an explicit non-empty list inside its declared root."""
    if not names:
        raise ValueError("name at least one input file")
    root = root.resolve()
    paths: list[Path] = []
    for name in sorted(set(names)):
        path = (root / name).resolve()
        path.relative_to(root)
        paths.append(path)
    return paths
