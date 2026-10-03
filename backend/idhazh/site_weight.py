"""Measure the built site and say when it reaches the alarm point and the Pages cap.

Nothing here deletes a file; the cleanup passes are in `idhazh.retention`.

**The alarm and the cap are two instruments and they stay apart.**
`retention.site_budget_mb` is the alarm: it prints and stops nothing.
`retention.pages_hard_cap_mb` is the cap: past it the step fails, because past
it the bytes cannot be published at all. Merging them would leave one number
doing a job it can only do badly - a warning nobody can ignore, or a failure
that arrives with no notice. The cap is a knob in one direction only. Its field
is bounded by `PAGES_HARD_CAP_MB`, the platform's own ceiling, so a config edit
can make this gate stricter and can never make it looser (Guardrail #2).

**The alarm measures the built bundle and never the committed payload tree.**
Those are two different trees and they grow at different rates, so one cannot
stand in for the other. Measured 2026-08-27 on this checkout: the payload tree
under `frontend/public/digest/` was 7,027,075 bytes while the built site was
128,064,853 - eighteen times larger, and the eighteen was twenty-one the day
before. The alarm used to watch the payload tree, so it could not have fired
until the site was already six times past the cap. A green light on the wrong
tree is worse than no light, because a green light gets read as safety.

**A level is not a date, and only a date answers the ceiling question.** The
alarm used to print one megabyte figure and one headroom figure, and neither is
a rate, so neither says when. What says when is bytes per published item times
the items a day may publish, divided into the headroom. Three things follow from
that and they are the rest of this module: `by_directory`, so a directory that
grew can be named rather than inferred from one moving sum;
`bytes_per_published_item`, because a rate over whole days moves when the item
mix moves and a rate over items does not; and `days_to_alarm` and `days_to_cap`,
which are the answer the question was always asking for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from idhazh.build_publication import read_build_inventory
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB, RetentionConfig

BYTES_PER_MB: Final = 1024 * 1024

@dataclass(frozen=True, slots=True)
class SiteSize:
    bytes_used: int
    files: int
    #: Bytes under each top-level child of the measured tree, largest first when
    #: read back through `heaviest_directories`. One sum cannot say whether the
    #: visuals grew or the telemetry did; this can.
    by_directory: dict[str, int] = field(default_factory=dict)
    #: Items the same tree carries. Counted from the measured tree and never
    #: from a second one - that pairing is the whole lesson of this module.
    published_items: int = 0

    @property
    def megabytes(self) -> float:
        return self.bytes_used / BYTES_PER_MB

    @property
    def bytes_per_published_item(self) -> float:
        """The stable unit. A day rate moves when the item mix moves; this does not.

        Measured 2026-08-29 over seven mature days: 24,378 bytes an item, spread
        23,066 to 26,538, while the day rate moved by a factor of six across the
        same days because two of them published 117 and 212 items where the ones
        behind them published 731.

        It raises on nothing published rather than returning zero. Zero is the
        number that makes an empty tree read as a site that will never grow.
        """
        if self.published_items <= 0:
            raise ValueError(
                "no published items in the measured tree, so there is no rate and "
                "no runway. A rate of zero reads as a site that never grows"
            )
        return self.bytes_used / self.published_items

    def minus(self, root: Path, removed: Mapping[Path, int]) -> SiteSize:
        """This total once those files have left the tree. It reads no file.

        The maintained total (Guardrail #12). A pass that deletes already knows what it
        removed and how big each one was, so asking the whole tree again is a walk
        that grows with the archive to learn a number the caller is holding.

        Each entry names a file and the bytes it held. The caller reads the size
        while the file is still there, because a file that has gone cannot be
        asked, and passes only the files that really went - a total that subtracts
        a deletion which did not happen has nothing to disagree with it.

        A new inventory over a generated fixture checks the retracted total.
        """
        by_directory = dict(self.by_directory)
        files = self.files
        for path, size in removed.items():
            parts = path.relative_to(root).parts
            if len(parts) == 1:
                # A file directly under the root is its own entry, so the entry
                # goes with the file - which is what a fresh walk would report.
                by_directory.pop(parts[0], None)
            else:
                # `unlink` never removes the directory, so its entry survives at
                # whatever is left, down to zero.
                by_directory[parts[0]] = by_directory.get(parts[0], 0) - size
            files -= 1
        return SiteSize(sum(by_directory.values()), files, by_directory, self.published_items)


def measure(root: Path) -> SiteSize:
    """Read deployed bytes and item counts from the build's one named inventory."""
    inventory = read_build_inventory(root)
    by_directory: dict[str, int] = {}
    for entry in inventory.entries:
        name = entry.path.split("/", 1)[0]
        by_directory[name] = by_directory.get(name, 0) + entry.bytes
    return SiteSize(
        inventory.total_bytes, len(inventory.entries), by_directory, inventory.total_items
    )


def count_published_items(root: Path) -> int:
    """Read the item total for the same deployed tree as its byte measurement."""
    return read_build_inventory(root).total_items


def heaviest_directories(size: SiteSize, limit: int = 0) -> list[tuple[str, int]]:
    """Top-level children largest first, so the line names what grew."""
    ordered = sorted(size.by_directory.items(), key=lambda entry: (-entry[1], entry[0]))
    return ordered if limit <= 0 else ordered[:limit]


def over_budget(size: SiteSize, config: RetentionConfig) -> bool:
    """The alarm fires below the platform's ceiling, so there is room to act."""
    return size.megabytes > config.site_budget_mb


def over_cap(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> bool:
    """Past the cap in force, which is where reporting stops being enough.

    `cap_mb` is a parameter for the same reason `prune` takes `today`: a test has
    to be able to cross the line without building a one-gigabyte fixture. The
    step passes `retention.pages_hard_cap_mb` down from config, and the default
    here is the platform's own ceiling, which is the most that knob may name.
    """
    return size.megabytes > cap_mb


def headroom_mb(size: SiteSize, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    return cap_mb - size.megabytes


def daily_growth_bytes(size: SiteSize, items_per_day: int) -> float:
    """What one more published day costs, at the item ceiling in force.

    `items_per_day` is `run.safety_ceiling_per_run` and not an average of the
    days on disk. A day that published 117 items is not evidence that the next
    one will; the ceiling is the most a day is allowed to cost, which is the
    figure a worst-case runway needs (Guardrail #10).
    """
    if items_per_day <= 0:
        raise ValueError("a day that may publish no items has no growth rate and no runway")
    return size.bytes_per_published_item * items_per_day


def days_to_alarm(size: SiteSize, config: RetentionConfig, items_per_day: int) -> float:
    """Published days from here to the alarm point. Negative once it is behind us."""
    left = (config.site_budget_mb - size.megabytes) * BYTES_PER_MB
    return left / daily_growth_bytes(size, items_per_day)


def days_to_cap(size: SiteSize, items_per_day: int, *, cap_mb: int = PAGES_HARD_CAP_MB) -> float:
    """Published days from here to the platform ceiling. The runway."""
    return headroom_mb(size, cap_mb=cap_mb) * BYTES_PER_MB / daily_growth_bytes(size, items_per_day)


def budget_alarm(size: SiteSize, config: RetentionConfig) -> str | None:
    """The alarm's words, or None when the built site is inside budget.

    Below the cap the alarm only reports - it fails no build and deletes nothing -
    so the run that meets it needs a line it can act on: the size, the alarm point
    it crossed, and the headroom left to the cap. Both numbers come from the same
    config, so an operator who lowers the cap sees the shorter headroom here too.
    """
    if not over_budget(size, config):
        return None
    cap_mb = config.pages_hard_cap_mb
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
    still had room. Past the cap the site is outside what Guardrail #2 allows, and
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
