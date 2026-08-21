"""Keep the published site inside the ceiling that arrives first.

The 1 GB Pages cap is the earliest hard limit this project meets, and it is met
by images rather than by text. So this does two separate things, and they are
deliberately not the same thing:

- **The alarm** measures the published site every run and says when it is
  approaching the ceiling. It is on from the first run, long before anything is
  ever deleted, because measuring the ceiling is what turns a policy into a
  decision rather than a reaction.
- **The prune** removes rendered visuals older than a configured window. It
  ships disabled, in dry-run, behind a per-run delete fuse.

Three rules the prune obeys, each one a way this goes wrong otherwise:

- **Age only, never size.** A size-triggered prune deletes most on the day the
  site is largest, which is the day the reader has most to read.
- **Visuals only, never a day.** The digest payload is the record that a day
  happened. Deleting text to save bytes trades the whole archive for a rounding
  error.
- **A fuse.** An off-by-one in a date parse must not eat the archive, so no run
  may delete more than a configured number of files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from idhazh.contracts.app_config import RetentionConfig

BYTES_PER_MB: Final = 1024 * 1024
#: The platform's own hard ceiling. Not a knob: it is a property of the host,
#: and making it editable would invite raising it instead of shrinking the site.
PAGES_HARD_CAP_MB: Final = 1024

_VISUAL_SUFFIXES: Final[frozenset[str]] = frozenset({".png", ".webp", ".jpg", ".jpeg", ".svg"})


@dataclass(frozen=True, slots=True)
class SiteSize:
    bytes_used: int
    files: int

    @property
    def megabytes(self) -> float:
        return self.bytes_used / BYTES_PER_MB


def measure(root: Path) -> SiteSize:
    """Recorded every run from the first one, long before any policy exists."""
    if not root.exists():
        return SiteSize(0, 0)
    files = [path for path in root.rglob("*") if path.is_file()]
    return SiteSize(sum(path.stat().st_size for path in files), len(files))


def over_budget(size: SiteSize, config: RetentionConfig) -> bool:
    """The alarm fires below the platform's ceiling, so there is room to act."""
    return size.megabytes > config.site_budget_mb


def headroom_mb(size: SiteSize) -> float:
    return PAGES_HARD_CAP_MB - size.megabytes


def cutoff(today: date, months: int) -> date | None:
    """None means retention is off, which is what ships."""
    if months < 0:
        return None
    return today - timedelta(days=months * 30)


def visuals_older_than(root: Path, limit: date) -> list[Path]:
    """Rendered visuals under dated directories older than the cutoff.

    A day's `digest.json` and `run.json` are never candidates: they are the
    record that the day happened, and they are text.
    """
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _VISUAL_SUFFIXES:
            continue
        published = _date_of(path, root)
        if published is not None and published < limit:
            found.append(path)
    return found


def _date_of(path: Path, root: Path) -> date | None:
    parts = path.relative_to(root).parts
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime("-".join(parts[:3]), "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class PruneResult:
    considered: int
    deleted: int
    dry_run: bool
    fuse_tripped: bool


def prune(root: Path, config: RetentionConfig, today: date) -> PruneResult:
    """Delete nothing unless configured to, and never more than the fuse allows."""
    limit = cutoff(today, config.image_months)
    if limit is None:
        return PruneResult(0, 0, config.dry_run, False)

    candidates = visuals_older_than(root, limit)
    fuse_tripped = len(candidates) > config.max_deletes_per_run
    allowed = candidates[: config.max_deletes_per_run]
    if config.dry_run:
        return PruneResult(len(candidates), 0, True, fuse_tripped)

    for path in allowed:
        path.unlink(missing_ok=True)
    return PruneResult(len(candidates), len(allowed), False, fuse_tripped)
