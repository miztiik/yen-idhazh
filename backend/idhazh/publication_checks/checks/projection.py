"""Would a reader's browser refuse the day the build was happy with?

A day has two readers and they read different files. `DigestDay` is what the
build opens off disk, and the runner parses it. `DigestView` is the projection
a reader's browser fetches, and a day that is fine on disk can still project to
something the served contract refuses - a story with no key point, say, which
the build never looked at because that story sits past the document's seed.

The projection is asked of the JSON object rather than the model, so a day that
already failed `DigestDay` is still asked this question. Reporting both in one
run is the difference between one fix and two.
"""

from __future__ import annotations

from pydantic import ValidationError

from idhazh.contracts.digest_view import DigestView
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope, DayContext


def _fault(day_date: str, raw: dict[str, object]) -> str | None:
    """What the served contract says about one day's payload, or nothing."""
    try:
        DigestView.project(raw)
    except ValidationError as error:
        return f"{day_date} fails digest-view.schema.json: {error.error_count()} problems\n{error}"
    except (TypeError, AttributeError, ValueError) as error:
        # A shape nobody anticipated. It still fails, and it still names the day
        # - a stack trace on day three of twelve says neither which day nor why.
        return f"{day_date} cannot be projected for serving: {type(error).__name__}: {error}"
    return None


def _run(ctx: DayContext) -> CheckResult:
    faults = [fault for day in ctx.days if (fault := _fault(day.date, day.raw)) is not None]
    return CheckResult(faults=tuple(faults))


CHECK = Check(name="projection", scope=CheckScope.DAY, run=_run)
