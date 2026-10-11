"""Which judges and own dates does this scheduled or manual invocation select?

Scheduled work asks each active judge about one bounded window and caps each
answer separately. Manual work validates the entire judge set and one date
before any selected package is imported, and asks about no outstanding dates.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from idhazh import config
from idhazh.contracts.base import DateStamp
from idhazh.contracts.council_events import CouncilProgram, NightPlanned
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council import event_log, outcome
from idhazh.council.registry import tenants
from idhazh.council.selection import SelectedJudge, Selection, manual
from idhazh.council.tenancy import Tenant

#: The one check that a date is a date every contract will accept. Held against
#: the annotated type rather than a second copy of its pattern, so a contract
#: that tightens the shape tightens this with it.
_A_DATE: Final = TypeAdapter(DateStamp)


def a_date(given: str, *, what: str) -> DateStamp:
    """`given` as a date the contracts accept, or a refusal naming what was wrong.

    Refused here rather than traced later. A date nothing accepts still reaches
    a matrix, names an artifact and addresses a ledger, so the run finds out
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
        event_log.failed(error, refused=True)
        raise SystemExit(outcome.CouncilExit.REFUSED) from error
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
        (floor + timedelta(days=offset)).isoformat() for offset in range((last - floor).days + 1)
    )


def plan_the_night(
    council: CouncilConfig, *, tonight: DateStamp, hosted: Sequence[Tenant]
) -> Selection:
    """Tonight and each judge's own newest outstanding nights, capped separately.

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
    selected: list[SelectedJudge] = []
    for host in hosted:
        behind: set[str] = set()
        for night in host.nights_outstanding(window=window):
            if night not in asked:
                raise SystemExit(
                    f"'{host.judge_id}' named a date outside "
                    f"the {len(window)} nights the council asked it about. A tenant answers "
                    "inside the window it was handed."
                )
            behind.add(night)
        selected.append(
            SelectedJudge(
                tenant=host.judge_id,
                status=council.declaration(host.judge_id).lifecycle_status,
                dates=(tonight, *sorted(behind, reverse=True)[: council.repair_dates_a_night]),
            )
        )
    return Selection(mode="scheduled", judges=tuple(selected)).check(council)


def main(argv: list[str] | None = None) -> int:
    return outcome.run(CouncilProgram.PLAN, lambda: _main(argv))


def _main(argv: list[str] | None = None) -> int:
    parser = outcome.Parser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--tonight",
        default=None,
        metavar="YYYY-MM-DD",
        help=("The scheduled digest date. Defaults here, once, to yesterday UTC."),
    )
    parser.add_argument(
        "--dispatched",
        default="",
        metavar="YYYY-MM-DD",
        help=("A manual run's required single date. No outstanding dates ride along."),
    )
    parser.add_argument("--mode", choices=("scheduled", "manual"), default="scheduled")
    parser.add_argument("--judges", default="", help="A manual run's JSON list of judge names.")
    args = parser.parse_args(argv)

    settings = config.load(args.config_root)
    event_log.install(settings.app.logging.level.value)
    if args.mode == "manual":
        tonight = a_date(str(args.dispatched), what="the dispatched date")
        selected = manual(settings.council, judges=args.judges, day=tonight)
        tenants(
            selected.names(),
            app=settings.app,
            council=settings.council,
            trials=selected.trials,
        )
    else:
        if args.dispatched or args.judges:
            raise SystemExit(outcome.CouncilExit.REFUSED)
        tonight = a_date(
            args.tonight or (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
            what="--tonight",
        )
        selected = plan_the_night(
            settings.council,
            tonight=tonight,
            hosted=tenants(settings.council.running(), app=settings.app, council=settings.council),
        )
    planned = selected.dates or (tonight,)
    event_log.emit(NightPlanned(dates=planned, judges=len(selected.judges)))
    print(f"date={tonight}")
    print(f"dates={json.dumps(list(planned), separators=(',', ':'))}")
    print(f"selection={selected.model_dump_json()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
