"""The console's own payloads, read back through the shapes that wrote them.

Data hygiene belongs here and not in pytest (`CLAUDE.md` section 13): this is
the producer's own gate on what it just wrote, and it runs where the payload is
- in CI, against the committed tree.

`ctx.months` names the months this run touched, which is what the day workflow
passes. None means every month still on disk, which is the sweep `ci.yml` takes
on a change that can move a contract - and reading everything is the point of
that case, because a contract change can invalidate any file.

Four of the five directories are trimmed on every assemble by
`series.prune_months`, so the sweep opens at most their own
`public_*_keep_months` files. `telemetry` is the exception and says so here
rather than in a sentence that would be wrong: its deletion lives in the
gardener's `telemetry-aggregate` task, which ships `dry_run: true` in its own
declaration, so its `public-copy` window is declared and not yet enforced and
that directory gains one file a month. The daily case is unaffected - it opens
only the months the run wrote.

The band is checked every time whatever `ctx.months` says. It is one small file
and it is the first thing the console asks for, so a band that will not load is
a console with no verdict at all.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.month_partition import months_between, oldest_month_kept
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, TreeContext
from idhazh.telemetry.publish import (
    console_band,
    day_metrics,
    machine,
    public_telemetry,
    run_days,
    series,
)


def _faults(root: Path, months: frozenset[str] | None) -> list[str]:
    if months is None:
        settings = config.load()
        today = datetime.now(UTC).date()
        count = months_a_window_can_touch(settings.appearance.console.max_window_days)
        months = frozenset(
            months_between(oldest_month_kept(today, count), today.isoformat()[:7])
        )
    faults: list[str] = []
    readers: tuple[tuple[str, str, Callable[[Path], object]], ...] = (
        (machine.DIRNAME, machine.SUFFIX, machine.read_shard),
        (
            day_metrics.PUBLIC_DIRNAME,
            day_metrics.PUBLIC_SUFFIX,
            day_metrics.read_public_shard,
        ),
        (run_days.DIRNAME, run_days.SUFFIX, run_days.read_shard),
        (public_telemetry.PUBLIC_TELEMETRY_DIRNAME, ".csv", public_telemetry.read_shard),
    )
    for dirname, suffix, read in readers:
        for month in series.published_months(root, dirname, suffix, months):
            path = series.month_path(root, dirname, month, suffix)
            try:
                read(path)
            except (ValueError, ValidationError, OSError) as fault:
                faults.append(f"{series.relpath(dirname, path.name)}: {fault}")
    band = console_band.band_path(root)
    if band.is_file():
        try:
            console_band.read_band(band)
        except (ValueError, ValidationError, OSError) as fault:
            faults.append(f"{console_band.BAND_RELPATH}: {fault}")
    elif band.parent.is_dir():
        # A console directory with no band in it is a producer that ran and
        # wrote nothing, which is a fault. No console directory at all is a tree
        # no producer has ever run over - a fixture, or a checkout mid-migration -
        # and this gate cannot tell that from broken, so it says nothing. What
        # guarantees the real tree has one is the committed seed, which
        # `test_every_path_the_day_stages_exists_in_a_fresh_checkout` asks for.
        faults.append(f"{console_band.BAND_RELPATH} is missing")
    return faults


def _run(ctx: TreeContext) -> CheckResult:
    return CheckResult(faults=tuple(_faults(ctx.root, ctx.months)))


CHECK = Check(name="console", scope=CheckScope.TREE, run=_run)
