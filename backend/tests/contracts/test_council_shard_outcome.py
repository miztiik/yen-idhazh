"""Does the council's own record say what happened, and can anything find it?

Two questions and they are separate. The row has to survive the trip to a CSV
day file and back with every cell intact, and the day file has to sit where the
instrument's own reader looks - a store one directory too deep is invisible to
that reader and the miss is silent.

What it cannot settle is whether the figures are true. Nothing writes this row
yet; the step that fills it is what proves the numbers.

Nothing here reads a committed file. The day tree is built under `tmp_path`, so
what this costs does not move as the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import ast
import csv
import inspect
import io
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import day_partition, ledger
from idhazh.contracts import council_shard_outcome
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome, ShardOutcome
from idhazh.telemetry import inventory

pytestmark = pytest.mark.contract

#: The package a contract may reach. The council's own record sits at the bottom
#: of the graph with the other shapes, and a judge lives outside it - so "names
#: no judge" is checked as "imports nothing but contracts", which stays true on
#: the day a second judge lands.
CONTRACTS_PACKAGE = "idhazh.contracts"

FIXTURES = CONTRACT_FIXTURES_DIR / "council-shard-outcome"

#: The night these tests are drawn on, and a date in another month so the
#: directory arithmetic has two answers to disagree about.
A_NIGHT = "2026-09-20"
ANOTHER_NIGHT = "2026-10-01"


def a_unit(name: str) -> CouncilShardOutcome:
    """One recorded unit of work, read inside the test that asks for it."""
    return CouncilShardOutcome.from_json(read_text(FIXTURES / f"{name}.json"))


def test_a_recorded_unit_round_trips_through_a_day_file() -> None:
    """Write it, read it back through the contract, get the same row."""
    row = a_unit("a-unit-that-stopped-on-its-own-clock")

    document = ledger.render_file(CouncilShardOutcome.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(read_back) == 1
    assert CouncilShardOutcome.from_csv_row(read_back[0]) == row
    assert len(document.splitlines()) == 2, "a cell put a line break in the row"


def test_a_tenant_that_ran_no_model_files_empty_cells_and_never_zeros() -> None:
    """Zero would read as a model that answered nothing, which is a different fact."""
    row = a_unit("a-unit-that-ran-no-model")

    assert row.outcome is ShardOutcome.NOTHING_TO_DO
    assert (row.model_calls, row.tokens_in, row.tokens_out, row.model_seconds) == (
        None,
        None,
        None,
        None,
    )

    cells = row.csv_row()
    assert [cells[name] for name in ("model_calls", "tokens_in", "tokens_out")] == ["", "", ""]
    assert CouncilShardOutcome.from_csv_row(cells) == row


def test_a_count_of_the_units_is_on_the_row_so_a_missing_one_can_be_seen() -> None:
    """A unit killed by the platform writes nothing, so absence is the only signal.

    The pair of cells is what makes absence readable: four rows saying `shards`
    is four is a whole night, and three of them is a night with a unit missing.
    """
    row = a_unit("a-unit-that-stopped-on-its-own-clock")

    assert (row.shard, row.shards) == (2, 4)
    with pytest.raises(ValidationError, match="shards"):
        CouncilShardOutcome.model_validate(row.model_dump(mode="json") | {"shards": 0})


def test_the_outcome_is_one_of_three_words_and_nothing_else() -> None:
    """A free-text outcome splits silently on a typo."""
    payload = a_unit("a-unit-that-ran-no-model").model_dump(mode="json")

    assert {member.value for member in ShardOutcome} == {
        "completed",
        "stopped_on_deadline",
        "nothing_to_do",
    }
    with pytest.raises(ValidationError, match="outcome"):
        CouncilShardOutcome.model_validate(payload | {"outcome": "Completed"})


def test_the_slug_is_recorded_rather_than_checked_against_a_roster() -> None:
    """The council writes down who ran and never declares who may exist.

    A tenant nobody has written yet has to be recordable, or the venue's own
    contract moves every time a tenant moves in.
    """
    payload = a_unit("a-unit-that-ran-no-model").model_dump(mode="json")

    assert CouncilShardOutcome.model_validate(
        payload | {"judge_id": "a-judge-nobody-has-written-yet"}
    ).judge_id
    with pytest.raises(ValidationError, match="judge_id"):
        CouncilShardOutcome.model_validate(payload | {"judge_id": "Not A Slug"})


def test_the_day_file_a_date_resolves_to_is_two_levels_under_state() -> None:
    """A third level is invisible to the day inventory and the miss is silent."""
    relpath = ledger.council_shard_outcomes_relpath(A_NIGHT)

    assert relpath == "state/llm-council/shard-outcomes/2026/09/20.csv"
    assert ledger.council_shard_outcomes_path(Path("state"), A_NIGHT).as_posix() == relpath

    segments = relpath.removeprefix(f"{ledger.STATE_DIRNAME}/").split("/")
    assert segments[:2] == [ledger.COUNCIL_DIRNAME, ledger.SHARD_OUTCOMES_DIRNAME]
    assert segments[2:] == ["2026", "09", "20.csv"], "the day tree gained a directory level"


def test_the_instrument_reader_finds_the_day_this_store_wrote(tmp_path: Path) -> None:
    """The oracle: a store this row creates is visible rather than silently absent.

    The inventory globs one directory level and two, so a nested store is found
    and a store nested deeper would not be. Asked through the public report,
    because that is what an operator reads.
    """
    state_root = tmp_path / ledger.STATE_DIRNAME
    for night in (A_NIGHT, ANOTHER_NIGHT):
        path = ledger.council_shard_outcomes_path(state_root, night)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            ledger.render_file(
                CouncilShardOutcome.csv_columns(),
                [a_unit("a-unit-that-ran-no-model").csv_row()],
            ),
            encoding="utf-8",
            newline="",
        )

    report = inventory.files(state_root, date=A_NIGHT)

    assert any("llm-council/shard-outcomes/2026/09/20.csv" in line for line in report), report
    assert not any(ANOTHER_NIGHT.replace("-", "/") in line for line in report), (
        "the inventory reported a day it was not asked about"
    )
    assert [day_partition.date_of(found) for found in day_partition.day_files(
        state_root / ledger.COUNCIL_DIRNAME / ledger.SHARD_OUTCOMES_DIRNAME
    )] == [A_NIGHT, ANOTHER_NIGHT]


def test_the_module_reaches_nothing_outside_the_contracts_package() -> None:
    """The council's own contract must be declarable with no judge in the tree.

    A judge imported here would put one tenant's vocabulary into the venue's
    published contract, and the venue would stop importing the day that tenant
    left.
    """
    tree = ast.parse(inspect.getsource(council_shard_outcome))

    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reached.append(node.module)
        elif isinstance(node, ast.Import):
            reached += [alias.name for alias in node.names]

    strayed = sorted(
        name
        for name in reached
        if name.split(".")[0] == "idhazh" and not name.startswith(f"{CONTRACTS_PACKAGE}.")
    )
    assert not strayed, f"the council's record reaches {strayed}, outside {CONTRACTS_PACKAGE}"
