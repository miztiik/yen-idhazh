"""How does a path, alone or in a filesystem error, leave this process relative and POSIX?"""

from __future__ import annotations

from os.path import relpath
from pathlib import Path

from idhazh import config


def label_path(path: Path) -> str:
    """Render a checkout-relative POSIX path, or its folder name on another drive."""
    try:
        return Path(relpath(path.resolve(), config.DEFAULT_CONFIG_DIR.parent)).as_posix()
    except ValueError:
        return path.name


def describe_error(error: ValueError | OSError) -> str:
    """Render filesystem failures without absolute paths or platform separators."""
    if not isinstance(error, OSError):
        return str(error)
    paths = [
        label_path(Path(name)) for name in (error.filename, error.filename2) if name is not None
    ]
    return ": ".join([error.strerror or "filesystem operation failed", *paths])
