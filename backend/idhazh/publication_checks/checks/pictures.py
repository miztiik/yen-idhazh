"""Where a day's payload and its picture directory disagree.

The defect this exists for shipped on 2026-08-24. A per-process counter that
restarted at 1 let a later run of the day overwrite an earlier run's
`india-01.svg` while the payload still named both items, so 32 declared
visuals sat over 18 files and 14 files were each claimed by two stories. 28
readers saw a picture and 14 of those were drawn from another article's
numbers, under alt text describing figures that were not in the image.
Nothing failed: every file existed, every item validated, the page rendered.

Three disagreements, three different faults. Two stories on one path means one
of them shows the other's chart. A path with no file is a broken image. A file
no story names is weight against the 1 GB Pages cap (Guardrail #2) that renders
nowhere, and it is what a repaired collision leaves behind.

**A visual's data file is held to the same three** now that it is the only file
a visual publishes: it is filed under the item's id in the day directory and
fetched by the reader's browser, so every way a drawing and its payload could
disagree is a way these can (2026-09-13).

It is checked here rather than by a test per committed day because the day that
can still be wrong is the one being written. A day already published is frozen,
and re-checking every one of them costs more every day the pipeline runs
(Guardrail #12).

**The 24 days published before the browser drew anything declare no data file
at all**, so they report nothing here and that is the correct reading: their
drawings are deleted and no payload names one.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from idhazh.contracts.digest_day import DigestDay
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, DayContext
from idhazh.render.write import assets_in_day


def _faults(public_root: Path, day: DigestDay) -> list[str]:
    """The three disagreements, in sentences, or an empty list."""
    declared = [
        item.visual.data_path
        for item in day.items
        if item.visual is not None and item.visual.data_path is not None
    ]
    faults: list[str] = []
    shared = sorted(name for name, claims in Counter(declared).items() if claims > 1)
    if shared:
        faults.append(f"names one picture on two stories: {shared}")
    absent = sorted(name for name in declared if not (public_root / name).is_file())
    if absent:
        faults.append(f"names a picture file that is not there: {absent}")
    orphans = sorted(assets_in_day(public_root, day.date) - set(declared))
    if orphans:
        faults.append(f"carries picture files no story names: {orphans}")
    return faults


def _run(ctx: DayContext) -> CheckResult:
    faults = [
        f"{committed.date} {fault}"
        for committed in ctx.days
        if committed.day is not None
        for fault in _faults(ctx.public_root, committed.day)
    ]
    return CheckResult(faults=tuple(faults))


CHECK = Check(name="pictures", scope=CheckScope.DAY, run=_run)
