"""Can the council name its own run, with no judge and no state to read?

Nothing here imports a judge, a stage or a store. That is the point of the
module rather than a property of it: the name a council night files under has to
be mintable in a repository with no judge in it at all.
"""

from __future__ import annotations

from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.base import RunId
from idhazh.council.run_identity import council_run_id, main, opened_today

#: The two halves of a name, spelled once. The day is the day the council RUNS.
COUNCIL_DAY: Final = "2026-09-21"
PLATFORM_RUN: Final = "35534060762"

#: What a contract does to a run id cell it is handed.
A_RUN_ID: Final = TypeAdapter(RunId)


def test_the_minted_name_is_one_every_contract_accepts() -> None:
    """The whole point of the name is that a row carrying it can be written.

    Held against the annotated type the contracts use, not against a second copy
    of its pattern - a name refused here costs a night of model time that has
    already been spent by the time the first append raises.
    """
    minted = council_run_id(opened_on=COUNCIL_DAY, platform_run_id=PLATFORM_RUN)

    assert minted == f"{COUNCIL_DAY}-{PLATFORM_RUN}"
    assert A_RUN_ID.validate_python(minted) == minted


def test_the_prefix_is_the_day_the_council_runs_and_not_the_day_it_judges() -> None:
    """A reader takes a run id's first ten characters as the day its run opened.

    So a name prefixed with the judged date publishes a standing lag of a day or
    more that nothing actually waited. The judged date is the `date` column,
    which is what routes a row to its store.
    """
    minted = council_run_id(opened_on=COUNCIL_DAY, platform_run_id=PLATFORM_RUN)

    assert minted[:10] == COUNCIL_DAY


@pytest.mark.parametrize(
    "opened_on, platform_run_id",
    [
        ("2026-9-21", PLATFORM_RUN),
        ("21-09-2026", PLATFORM_RUN),
        ("2026-09-21", ""),
        ("2026-09-21", "35534060762-2"),
        ("2026-09-21", "attempt two"),
        ("", PLATFORM_RUN),
    ],
)
def test_a_name_no_contract_would_accept_is_refused_at_the_mint(
    opened_on: str, platform_run_id: str
) -> None:
    """The refusal is at the one step that runs before any model time is spent.

    Each case is a shape that reads as a plausible identity and is not one: a
    month with no leading zero, a day-first date, an empty platform id, an id
    carrying an attempt suffix, and a value with a space in it.
    """
    with pytest.raises(SystemExit):
        council_run_id(opened_on=opened_on, platform_run_id=platform_run_id)


def test_the_day_the_run_opened_is_a_day_a_contract_would_accept() -> None:
    """A clock reading is still a cell, so it is held to the shape a cell has."""
    assert A_RUN_ID.validate_python(f"{opened_today()}-1")


def test_the_command_line_prints_the_name_under_the_key_the_workflow_reads(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The step appends this line to the platform's output file and reads it back by key.

    One key, one value, no decoration - the file it lands in is parsed on `=`.
    A different key leaves the later jobs with an empty name, which reaches the
    verbs as a missing argument two hours in rather than here.
    """
    assert main(["--platform-run-id", PLATFORM_RUN]) == 0

    key, _, minted = capsys.readouterr().out.strip().partition("=")

    assert key == "run_id"
    assert minted.endswith(f"-{PLATFORM_RUN}")
    assert A_RUN_ID.validate_python(minted) == minted


def test_a_platform_that_handed_over_nothing_stops_the_step() -> None:
    """An empty platform id is a name every night would share.

    The step reads it through `env`, and an unset variable arrives as an empty
    string rather than as a missing argument - so this is the shape the runner
    actually produces when the expression resolves to nothing.
    """
    with pytest.raises(SystemExit):
        main(["--platform-run-id", ""])


def test_the_type_the_mint_is_held_against_is_the_one_the_contracts_use() -> None:
    """A second copy of the pattern would drift the day a contract tightened it."""
    with pytest.raises(ValidationError):
        A_RUN_ID.validate_python("2026-09-21-")
