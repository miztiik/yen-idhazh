"""Which run is this, when the council is the one asking?

A council night never drew a digest run, so it cannot honestly file rows under
one. It mints a name of its own from the day it opened and the identity the
platform gave the run - once, in the planning job, published as a job output
that every later verb reads.

Nothing here opens a store, resolves an ordinal or names a judge. The digest
pipeline's run id counts executions of a date by reading that run's own state;
this one is only a name, so it needs no state at all.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Final

from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.base import RunId

#: The one check that the minted name is a run id every contract will accept.
#: Held against the annotated type rather than against a second copy of its
#: pattern, so a contract that tightens the shape tightens this with it.
_A_RUN_ID: Final = TypeAdapter(RunId)


def opened_today() -> str:
    """The UTC day a council run starting now opened on."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def council_run_id(*, opened_on: str, platform_run_id: str) -> str:
    """The name this council run files every row it writes under.

    `opened_on` is the day the council RUNS and never the day it judges. A
    reader takes a run id's first ten characters as the day the run opened and
    measures the lag to publication from them, so a judged-date prefix would
    publish a standing two-day lag that nothing waited. The judged date is the
    `date` column, which is what routes a row to its store.

    `platform_run_id` is the platform's run id, which is unique across every
    workflow in the repository - never its run number, which starts again in
    the next workflow and would let a council name equal a digest run's in a
    column that already carries both meanings.

    The refusal is here rather than at the first append because a name that no
    contract accepts costs a whole night of model time before anything says so.
    """
    minted = f"{opened_on}-{platform_run_id}"
    try:
        return str(_A_RUN_ID.validate_python(minted))
    except ValidationError as error:
        raise SystemExit(
            f"'{minted}' is not a run id, so every row this night wrote would be "
            f"refused by its own contract: {error}"
        ) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform-run-id",
        required=True,
        help=(
            "The identity the platform gave this run, unique across every workflow "
            "in the repository. A run NUMBER is not one: it starts again per "
            "workflow, so it would collide with a digest run's id."
        ),
    )
    args = parser.parse_args(argv)
    minted = council_run_id(
        opened_on=opened_today(), platform_run_id=str(args.platform_run_id)
    )
    print(f"run_id={minted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
