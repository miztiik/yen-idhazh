"""The console's own payloads, read back through the shapes that wrote them.

Data hygiene belongs here and not in pytest (`CLAUDE.md` section 13): this is
the producer's own gate on what it just wrote, and it runs where the payload is
- in CI, against the committed tree.

The band is checked every time. It is one small file
and it is the first thing the console asks for, so a band that will not load is
a console with no verdict at all.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from idhazh.contracts.base import StalePayloadError
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, TreeContext
from idhazh.telemetry.publish import (
    console_band,
)


def _faults(root: Path, months: frozenset[str] | None) -> list[str]:
    faults: list[str] = []
    band = console_band.band_path(root)
    if band.is_file():
        try:
            console_band.read_band(band)
        except (ValueError, ValidationError, StalePayloadError, OSError) as fault:
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
