"""Keep the published site inside the ceiling that arrives first.

The 1 GB Pages cap is the earliest hard limit this project meets, and it is met
by images rather than by text. So this does two separate things, and they are
deliberately not the same thing:

- **The alarm** measures the built bundle - the tree the deploy uploads - and
  says when it is approaching the ceiling. It is on from the first run, long
  before anything is ever deleted, because measuring the ceiling is what turns a
  policy into a decision rather than a reaction.
- **The prune** removes rendered visuals older than a configured window. It
  ships disabled, in dry-run, behind a per-run delete fuse.

**The alarm measures the built bundle and never the committed payload tree.**
Those are two different trees and they grow at different rates, so one cannot
stand in for the other. Measured 2026-08-27 on this checkout: the payload tree
under `frontend/public/digest/` was 7,027,075 bytes while the built site was
128,064,853 - eighteen times larger, and the eighteen was twenty-one the day
before. The alarm used to watch the payload tree, so it could not have fired
until the site was already six times past the cap. A green light on the wrong
tree is worse than no light, because a green light gets read as safety.

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


def over_cap(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> bool:
    """Past the platform's own ceiling, which is where reporting stops being enough.

    `cap_mb` is a parameter for the same reason `prune` takes `today`: a test has
    to be able to cross the line without building a one-gigabyte fixture. No
    caller passes it, and the CLI offers no flag for it.
    """
    return size.megabytes > cap_mb


def headroom_mb(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    return cap_mb - size.megabytes


def budget_alarm(
    size: SiteSize, config: RetentionConfig, *, cap_mb: int = PAGES_HARD_CAP_MB
) -> str | None:
    """The alarm's words, or None when the built site is inside budget.

    Below the platform cap the alarm only reports - it fails no build and deletes
    nothing - so the run that meets it needs a line it can act on: the size, the
    alarm point it crossed, and the headroom left to the cap.
    """
    if not over_budget(size, config):
        return None
    return (
        f"published site is {size.megabytes:.0f} MB, past the "
        f"{config.site_budget_mb} MB alarm point, with "
        f"{headroom_mb(size, cap_mb=cap_mb):.0f} MB left to the {cap_mb} MB Pages cap"
    )


def cap_breach(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> str | None:
    """The words for a site that can no longer be published, or None.

    This one fails the build, and the alarm above does not. The split is the
    whole point: 800 MB still deploys, so failing there would stop publishing
    weeks before it had to, and the reader loses a working site to a budget that
    still had room. Past the cap the site is outside what Rule #2 allows, and
    failing in the job that measured it names the cause - a deploy that refuses
    the bytes names nothing.
    """
    if not over_cap(size, cap_mb=cap_mb):
        return None
    return (
        f"built site is {size.megabytes:.0f} MB in {size.files} files, past the "
        f"{cap_mb} MB Pages cap. It cannot be published. Prune, or shrink what a "
        f"published day costs"
    )


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
