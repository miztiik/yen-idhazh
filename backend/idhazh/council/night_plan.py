"""Which dates does tonight's council judge?

Tonight, plus the older nights its tenants say they are behind on. The council
owns the window, its floor and how many older nights one night may repair,
because all three price a runner: every extra date is another job a tenant a
shard. What counts as behind is the tenant's, because only the tenant knows what
it has read.

**The council asks; it does not look.** It calls `nights_outstanding` on every
registered tenant and unions what comes back, so the venue knows nothing about
any tenant's storage layout - and with nobody registered the union is empty and
tonight is the whole plan.

Nothing here repairs anything and nothing here needs an operator. The plan names
the dates; the night's own three verbs do the work on each of them, and the next
run finds a gap because finding the gap is how it picks its work.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from idhazh import config
from idhazh.contracts.base import DateStamp
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council.registry import tenants
from idhazh.council.tenancy import Tenant

#: The one check that a date is a date every contract will accept. Held against
#: the annotated type rather than a second copy of its pattern, so a contract
#: that tightens the shape tightens this with it.
_A_DATE: Final = TypeAdapter(DateStamp)


def a_date(given: str, *, what: str) -> DateStamp:
    """`given` as a date the contracts accept, or a refusal naming what was wrong.

    Refused here rather than traced later. A date nothing accepts still reaches
    a matrix, names an artifact and addresses a store, so the run finds out
    about two hours of model time in.

    The calendar is checked as well as the shape, because `DateStamp` counts
    digits and bounds neither the month nor the day - `2026-13-45` passes it.
    The window arithmetic below would then raise a `ValueError` from inside
    `datetime`, which reads like a broken planner rather than a bad date.
    """
    try:
        stamped = str(_A_DATE.validate_python(given))
        date.fromisoformat(stamped)
    except (ValidationError, ValueError) as error:
        raise SystemExit(
            f"{what} must be a YYYY-MM-DD date, and '{given}' is not: {error}"
        ) from error
    return stamped


def window_before(council: CouncilConfig, *, tonight: DateStamp) -> tuple[DateStamp, ...]:
    """The nights the council asks its tenants about, oldest first.

    At most `repair_window_nights` of them, ending the night before `tonight` and
    never reaching past `council.first_night`.

    **Tonight is not in it.** A tenant is not behind on a night nothing has
    judged yet, and a tenant that named it would spend a repair slot on the date
    the night is already for.

    This tuple is the whole of what any tenant is handed, so it bounds the
    tenant's read as well as the council's own matrix (CLAUDE.md Guardrail #12).
    """
    last = date.fromisoformat(tonight) - timedelta(days=1)
    floor = max(
        date.fromisoformat(council.first_night),
        last - timedelta(days=council.repair_window_nights - 1),
    )
    return tuple(
        (floor + timedelta(days=offset)).isoformat()
        for offset in range((last - floor).days + 1)
    )


def plan_the_night(
    council: CouncilConfig, *, tonight: DateStamp, hosted: Sequence[Tenant]
) -> tuple[DateStamp, ...]:
    """Tonight, and the older nights this run repairs with it. Newest first.

    The union of what the tenants answered and never the intersection: one tenant
    behind on a night is a night with a gap in it, whatever the others managed.

    Cut to `repair_dates_a_night`, newest first. A date that can never succeed
    then holds the ones behind it out only until the window slides past it;
    oldest first, that one date would keep every newer date waiting for as long
    as it stayed in the window.

    A tenant that names a date the council did not ask about is refused by name.
    The council is what prices a window, so a date from outside one is a job
    nobody budgeted for - and it would reach a runner as silently as a date that
    was asked for.
    """
    window = window_before(council, tonight=tonight)
    asked = set(window)
    behind: set[str] = set()
    for host in hosted:
        for night in host.nights_outstanding(window=window):
            if night not in asked:
                raise SystemExit(
                    f"'{host.judge_id}' says it is behind on {night}, which is not one of "
                    f"the {len(window)} nights the council asked it about. A tenant answers "
                    "inside the window it was handed."
                )
            behind.add(night)
    return (tonight, *sorted(behind, reverse=True)[: council.repair_dates_a_night])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--tonight",
        required=True,
        metavar="YYYY-MM-DD",
        help=(
            "The date this night is for. Required and never defaulted: the planning job "
            "decides which day the council opens on, and a second answer here could plan "
            "one date while the artifacts were named for another."
        ),
    )
    parser.add_argument(
        "--dispatched",
        default="",
        metavar="YYYY-MM-DD",
        help=(
            "A date a person named, which replaces the plan outright. Somebody naming a "
            "date is asserting something the plan cannot know, so no tenant is asked and "
            "no older night rides along. Empty is the scheduled night."
        ),
    )
    args = parser.parse_args(argv)

    planned: tuple[DateStamp, ...]
    if str(args.dispatched):
        planned = (a_date(str(args.dispatched), what="the dispatched date"),)
    else:
        app = config.load(args.config_root).app
        planned = plan_the_night(
            app.council,
            tonight=a_date(str(args.tonight), what="--tonight"),
            hosted=tenants(app.council.tenants, app=app),
        )
    print(f"dates={json.dumps(list(planned), separators=(',', ':'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
