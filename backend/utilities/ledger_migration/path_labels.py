"""How does a path, alone or in a filesystem error, leave this process relative and POSIX?"""

from __future__ import annotations

from pathlib import Path

from idhazh import config


def label_path(path: Path) -> str:
    """Render a path inside the checkout relative to it, and any other path by its name alone."""
    resolved = path.resolve()
    checkout = config.DEFAULT_CONFIG_DIR.parent.resolve()
    if resolved.is_relative_to(checkout):
        return resolved.relative_to(checkout).as_posix()
    return path.name


def describe_error(error: ValueError | OSError) -> str:
    """Render filesystem failures without absolute paths or platform separators."""
    if not isinstance(error, OSError):
        return str(error)
    paths = [
        label_path(Path(name)) for name in (error.filename, error.filename2) if name is not None
    ]
    return ": ".join([error.strerror or "filesystem operation failed", *paths])
