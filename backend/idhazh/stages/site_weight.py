"""Measure the built bundle against the alarm point and the Pages cap.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    retention,
)
from idhazh.contracts.app_config import (
    RetentionConfig,
)
from idhazh.stages.common import LOG


def _report_site_growth(
    size: retention.SiteSize,
    config: RetentionConfig,
    *,
    items_per_day: int,
) -> None:
    """The rate, the runway, and which directory is holding the bytes.

    Reporting only, and deliberately: `npm run bundle-gate` already fails a build
    on a crossed per-route ceiling and `cap_breach` above fails one past the
    configured cap, so a third gate here would be a third thing to keep green for
    no coverage it does not already have.

    The runway is the point of the whole step. A megabyte figure and a headroom
    figure are both levels, and no level yields a date - only a rate does.
    """
    named = retention.heaviest_directories(size, limit=6)
    if named:
        LOG.info(
            "site-weight by directory: %s",
            ", ".join(f"{name} {count / retention.BYTES_PER_MB:.1f} MB" for name, count in named),
        )

    if size.published_items <= 0 or items_per_day <= 0:
        LOG.info(
            "site-weight runway: unknown - %s published items in the measured tree at a "
            "%s item day ceiling. The size above is a level, and a level has no date in it",
            size.published_items,
            items_per_day,
        )
        return

    LOG.info(
        "site-weight rate: %.0f B per published item over %s items, so %.2f MB a "
        "published day at the %s item ceiling",
        size.bytes_per_published_item,
        size.published_items,
        retention.daily_growth_bytes(size, items_per_day) / retention.BYTES_PER_MB,
        items_per_day,
    )
    LOG.info(
        "site-weight runway: %.0f published days to the %s MB alarm point, %.0f to the "
        "%s MB Pages cap",
        retention.days_to_alarm(size, config, items_per_day),
        config.site_budget_mb,
        retention.days_to_cap(size, items_per_day, cap_mb=config.pages_hard_cap_mb),
        config.pages_hard_cap_mb,
    )


def stage_site_weight(
    tree: Path,
    config: RetentionConfig,
    *,
    items_per_day: int = 0,
) -> int:
    """Measure the built bundle against the alarm point and the Pages cap.

    `tree` is the directory the Pages deploy uploads, and it only exists after
    the site is built - so this runs as its own step after `npm run build`, in
    every job that builds. It is deliberately not part of `assemble`: that stage
    runs before the build and can only see the committed payloads, which are a
    different tree eighteen times smaller.

    There is no default tree. A default is how this pointed at the wrong one.

    The cap comes from `retention.pages_hard_cap_mb` and not from a flag. A flag
    is a per-invocation override, which is the one shape a ceiling must not have -
    the job that is about to breach it is the job that would pass the flag. The
    config field is bounded, so the only edit that reaches this line is one that
    makes the gate stricter.

    Three outcomes: an empty tree fails, because a measurement of nothing reads
    exactly like a site inside budget; over the cap fails, because those bytes
    cannot be published; over the alarm point reports and passes, because they
    still can. Both outcomes that pass also print the rate and the runway, and
    not only the one over the alarm point - the day the alarm fires is not the
    day anybody wanted to first learn the date.
    """
    cap_mb = config.pages_hard_cap_mb
    size = retention.measure(tree, published_items=retention.count_published_items(tree))
    if size.files == 0:
        LOG.error(
            "site-weight measured 0 files under %s - build the site first. "
            "A measurement of nothing passes every ceiling",
            tree.as_posix(),
        )
        return 1

    breach = retention.cap_breach(size, cap_mb=cap_mb)
    if breach is not None:
        LOG.error("%s", breach)
        return 1

    LOG.info(
        "site-weight %s: %.1f MB in %s files, %.0f MB left to the %s MB Pages cap",
        tree.as_posix(),
        size.megabytes,
        size.files,
        retention.headroom_mb(size, cap_mb=cap_mb),
        cap_mb,
    )
    _report_site_growth(size, config, items_per_day=items_per_day)

    alarm = retention.budget_alarm(size, config)
    if alarm is not None:
        # An Actions workflow command, so the line lands on the run's summary
        # rather than three thousand lines into a log nobody opens. Outside
        # Actions it is one more printed line and costs nothing.
        print(f"::warning title=Published site approaching the Pages cap::{alarm}")
        LOG.warning("%s", alarm)
    return 0
