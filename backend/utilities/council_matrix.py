"""What shape does tonight's council run take, and what will it commit?

One answer in four key-value lines, read once in the planning job and published
to every later job: the cells to fan out over, how many may run at once, the
dates the night covers, and the ledger paths the collecting job stages.

A cell is flat - a tenant, a date, a shard and that tenant's own width. Not a
cross product of three vectors: a per-tenant width is not a third axis, and a
product would hand every tenant the widest tenant's width and pay a weights
restore for work that runs no model.

One date crosses today. The list shape is what lets a night that also repairs an
older date add one without the workflow changing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from idhazh import config
from idhazh.contracts.council_events import CouncilProgram, JudgeDeclared, NightPlanned
from idhazh.council import event_log, outcome
from idhazh.council.night_plan import a_date
from idhazh.council.registry import tenants
from idhazh.council.selection import Selection, for_dates, from_environment
from idhazh.council.session import VENUE_LEDGERS as VENUE_LEDGER_NAMES
from idhazh.council.session import publication_paths, shard_width
from idhazh.ledger import staging

#: How many jobs one repository may have running at once. GitHub's number, not
#: ours: past it a job waits its turn, and lowering it would be a throttle
#: nobody asked for (CLAUDE.md Guardrail #2).
PLATFORM_JOB_CEILING: Final = 20

#: The venue's own ledgers, staged by the collecting job alongside whatever the
#: tenants named. Built from each ledger's registry prefix rather than spelled,
#: so a move of the tree moves these with it. The record says which units ran;
#: the host row says which machine ran them, and neither belongs to a tenant -
#: a list of one tenant's paths would commit neither.
VENUE_LEDGERS: Final = tuple(staging.staged_path(which) for which in VENUE_LEDGER_NAMES)
COUNCIL_LEDGER: Final = VENUE_LEDGERS[0]


def cells(
    config_dir: Path,
    *,
    dates: tuple[str, ...] = (),
    selection: Selection | None = None,
) -> list[dict[str, object]]:
    """Every unit of work the night fans out to, tenant by tenant, date by date.

    A tenant narrows the venue's width downward through its own `shard_count`,
    so a tenant that runs no model takes one job rather than four.
    """
    council = config.load_council(config_dir)
    selected = for_dates(council, dates) if selection is None else selection.check(council)
    found: list[dict[str, object]] = []
    for name in council.judge_names:
        declaration = council.declaration(name)
        event_log.emit(
            JudgeDeclared(
                judge_id=name,
                status=declaration.lifecycle_status,
                runs_model=declaration.runs_model,
            )
        )
    for host in tenants(selected.names(), council=council, trials=selected.trials):
        width = shard_width(council, host)
        own_dates = next(judge.dates for judge in selected.judges if judge.tenant == host.judge_id)
        for date in own_dates:
            found += [
                {
                    "tenant": host.judge_id,
                    "date": date,
                    "shard": shard,
                    "shards": width,
                    "runs_model": council.declaration(host.judge_id).runs_model,
                }
                for shard in range(width)
            ]
    return found


def committed_paths(config_dir: Path, *, selection: Selection | None = None) -> tuple[str, ...]:
    """Every ledger path tonight's night writes, for the collecting job to stage.

    Asked of the tenants rather than spelled in the workflow. A second tenant's
    output was never going to be committed by a list of one tenant's four paths.

    The venue's own ledgers lead, because the venue records every unit it ran and
    the machine it ran them on whatever the tenant inside it wrote. A night with
    no tenant writes nothing at all and names nothing, which is what keeps the
    commit step skipped.
    """
    return publication_paths(config.load_council(config_dir), selection=selection)


def _parallel(count: int) -> int:
    """How many cells may run at once.

    The cell count, capped by the platform. Never the shard width: two tenants
    over two dates is sixteen cells, and a width of four would run them in four
    waves finishing across two other schedules.

    At least one, because a strategy with no parallelism at all is not a shape
    Actions can run. A night with no cells never reaches it - the judging job
    carries a guard that stops an empty matrix reaching the strategy evaluator.
    """
    return max(min(count, PLATFORM_JOB_CEILING), 1)


def main(argv: list[str] | None = None) -> int:
    return outcome.run(CouncilProgram.MATRIX, lambda: _main(argv))


def _main(argv: list[str] | None = None) -> int:
    parser = outcome.Parser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--date",
        action="append",
        default=[],
        metavar="YYYY-MM-DD",
        help=(
            "A date this night covers, repeatable. Required and never defaulted: the "
            "planning job decides which day it judges, and a second answer here could "
            "send the cells to one date while the artifacts were named for another."
        ),
    )
    args = parser.parse_args(argv)
    event_log.install(config.load(args.config_root).app.logging.level.value)

    council = config.load_council(args.config_root)
    selected = from_environment(council)
    dates = tuple(dict.fromkeys(a_date(str(date), what="--date") for date in args.date))
    if selected is None:
        if not dates:
            raise SystemExit(outcome.CouncilExit.REFUSED)
        selected = for_dates(council, dates)
    elif dates and dates != selected.dates:
        raise SystemExit(outcome.CouncilExit.REFUSED)
    else:
        dates = selected.dates
    matrix = cells(args.config_root, selection=selected)
    paths = committed_paths(args.config_root, selection=selected)
    event_log.emit(
        NightPlanned(
            dates=dates,
            judges=len({cell["tenant"] for cell in matrix}),
            units=len(matrix),
        )
    )
    print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")
    print(f"max_parallel={_parallel(len(matrix))}")
    print(f"dates={json.dumps(list(dates), separators=(',', ':'))}")
    print(f"committed_paths={' '.join(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
