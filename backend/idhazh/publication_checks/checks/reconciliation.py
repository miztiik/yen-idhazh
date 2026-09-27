"""A day whose planned stories are neither published nor counted as failed.

**An empty day is not a fault, and two of them are normal.** A day that planned
nothing published nothing: the pipeline found no new article, so `partial` is
false and the console paints it amber, which is the correct reading
(`backend/utilities/build_canary_day.py::quiet_day`). A day where everything
failed publishes empty and says `partial`, because a run that publishes nothing
on a bad day is a run whose bad days are invisible (`idhazh.stages.assemble`).
2026-09-14 is the second kind and stays published - refusing it would delete
the only record that the day went wrong.

The third empty day is the one nothing can write honestly: stories were
planned, none failed, and none came out. `ItemOutcome` has two members, so
every story the pipeline touched is `ok` or `failed`, and `items_planned` is
never below `len(items) + items_failed` - a day holding neither has lost its
whole plan with nothing recording where it went. On a reader's page and on the
console it is indistinguishable from a quiet day, which is what makes it worth
refusing rather than merely counting.

`DigestDay` pins `partial` to `items_failed > 0` on its own. It cannot pin this
one: what makes the day wrong is a plan the day itself is silent about, so the
arithmetic only closes once, here, over the whole payload.

**This reports a fault and files nothing.** What a day planned against what it
published is already a column of `day_metrics`, which the console reads; a
second record of the same arithmetic would be a second number to keep in step.
"""

from __future__ import annotations

from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, DayContext


def _run(ctx: DayContext) -> CheckResult:
    faults = [
        f"{committed.date} planned {committed.day.items_planned} stories and accounts for "
        f"none of them: nothing published and nothing failed"
        for committed in ctx.days
        if committed.day is not None
        and committed.day.items_planned
        and not committed.day.items
        and not committed.day.items_failed
    ]
    return CheckResult(faults=tuple(faults))


CHECK = Check(name="planned-items-reconciliation", scope=CheckScope.DAY, run=_run)
