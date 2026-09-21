"""What shape does tonight's council run take, and what will it commit?

One answer in four key-value lines, read once in the planning job and published
to every later job: the cells to fan out over, how many may run at once, the
dates the night covers, and the store paths the collecting job stages.

A cell is flat - a tenant, a date, a shard and that tenant's own width. Not a
cross product of three vectors: a per-tenant width is not a third axis, and a
product would hand every tenant the widest tenant's width and pay a weights
restore for work that runs no model.

One date crosses today. The list shape is what lets a night that also repairs an
older date add one without the workflow changing.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.council.registry import tenants
from idhazh.council.session import shard_width

#: How many jobs one repository may have running at once. GitHub's number, not
#: ours: past it a job waits its turn, and lowering it would be a throttle
#: nobody asked for (CLAUDE.md Guardrail #2).
PLATFORM_JOB_CEILING: Final = 20

#: The venue's own store, staged by the collecting job alongside whatever the
#: tenants named. Built from the constants the store is addressed by rather than
#: spelled, so a move of the tree moves this with it.
COUNCIL_STORE: Final = (
    f"{ledger.STATE_DIRNAME}/{ledger.COUNCIL_DIRNAME}/{ledger.SHARD_OUTCOMES_DIRNAME}"
)


def cells(config_dir: Path, *, dates: tuple[str, ...]) -> list[dict[str, object]]:
    """Every unit of work the night fans out to, tenant by tenant, date by date.

    A tenant narrows the venue's width downward through its own `shard_count`,
    so a tenant that runs no model takes one job rather than four.
    """
    council = config.load(config_dir).app.council
    found: list[dict[str, object]] = []
    for host in tenants(council.tenants):
        width = shard_width(council, host)
        for date in dates:
            found += [
                {"tenant": host.judge_id, "date": date, "shard": shard, "shards": width}
                for shard in range(width)
            ]
    return found


def committed_paths(config_dir: Path) -> tuple[str, ...]:
    """Every store path tonight's night writes, for the collecting job to stage.

    Asked of the tenants rather than spelled in the workflow. A second tenant's
    output was never going to be committed by a list of one tenant's four paths.

    The venue's own store leads, because the venue records every unit it ran
    whatever the tenant inside it wrote. A night with no tenant writes nothing at
    all and names nothing, which is what keeps the commit step skipped.
    """
    council = config.load(config_dir).app.council
    hosted = tenants(council.tenants)
    if not hosted:
        return ()
    staged = [COUNCIL_STORE]
    for host in hosted:
        staged += [path for path in host.committed_paths if path not in staged]
    return tuple(staged)


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument(
        "--date",
        action="append",
        default=[],
        metavar="YYYY-MM-DD",
        required=True,
        help=(
            "A date this night covers, repeatable. Required and never defaulted: the "
            "planning job decides which day it judges, and a second answer here could "
            "send the cells to one date while the artifacts were named for another."
        ),
    )
    args = parser.parse_args(argv)

    dates = tuple(dict.fromkeys(str(date) for date in args.date))
    matrix = cells(args.config_root, dates=dates)
    print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")
    print(f"max_parallel={_parallel(len(matrix))}")
    print(f"dates={json.dumps(list(dates), separators=(',', ':'))}")
    print(f"committed_paths={' '.join(committed_paths(args.config_root))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
