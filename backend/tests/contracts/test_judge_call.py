"""Does a row that inherits the stamp still write and read every cell?

The mixin is columns and nothing else, so the only claims worth making about it
are structural: a contract that inherits it carries all seven cells through a CSV
file and back, the seven arrive after the base's own and before the row's own,
nothing generates a schema for the mixin itself, and the module reaches no judge.

Every payload here is declared in this file, so the whole module runs in a
repository with no judge in it.
"""

from __future__ import annotations

import ast
import csv
import inspect
import io
from typing import Any, ClassVar, Self

import pytest
from pydantic import Field, ValidationError

from idhazh import ledger
from idhazh.contracts import judge_call
from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp
from idhazh.contracts.export import CONTRACTS
from idhazh.contracts.judge_call import JudgeConfigStamp

pytestmark = pytest.mark.contract

#: The package a contract may reach. The mixin sits at the bottom of the graph
#: with the shapes, and a judge lives outside it - so "imports no judge" is
#: checked as "imports nothing but contracts", which stays true on the day a
#: second judge lands.
CONTRACTS_PACKAGE = "idhazh.contracts"


class StampedReading(JudgeConfigStamp, Contract):
    """A reading that carries the stamp and one cell of its own.

    **A fixture, not a mock** (Guardrail #7). It stands in for nobody: it holds
    the columns it declares and computes its own row. It exists so the mixin is
    gated on a contract this file owns rather than on a judge's contract, which
    would make the gate go red the day that judge moved a column and would make
    this module unrunnable with no judge in the tree.

    Deliberately absent from `contracts.export.CONTRACTS`, so no schema is
    generated for it and the drift gate reports no orphan. It declares one
    changelog entry because the base class refuses a subclass without one, and it
    hand-declares the three CSV members like every other row under `state/`.
    """

    __schema_stem__: ClassVar[str] = "stamped-reading"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the stamp, the date and one reading of its own.",
            why="The mixin needs an inheritor that names no judge.",
        ),
    )

    date: DateStamp = Field(description="The date this reading is about.")
    reading: float = Field(description="The one number this row exists to carry.")

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        return cls.model_validate({name: value or None for name, value in payload.items()})


def a_reading(**overrides: Any) -> StampedReading:
    """One row with every cell filled, so a dropped cell has somewhere to show."""
    cells: dict[str, Any] = {
        "date": "2026-09-20",
        "reading": 0.75,
        "judge_id": "paper-judge",
        "judge_model": "paper/weights-4B-Q4_K_M.gguf",
        "judge_temperature": 0.2,
        "thinking_spans": 1,
        "prompt_digest": "c" * 64,
        "grammar_digest": "d" * 64,
    }
    return StampedReading.model_validate(cells | overrides)


def test_every_stamped_cell_survives_a_csv_round_trip() -> None:
    """Write it, read it back through the contract, get the same model."""
    row = a_reading()

    document = ledger.render_file(StampedReading.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(read_back) == 1
    assert StampedReading.from_csv_row(read_back[0]) == row
    assert len(document.splitlines()) == 2, "a stamped cell put a line break in the row"


def test_the_stamp_columns_sit_between_the_base_and_the_row() -> None:
    """Base fields are collected first, which is why a committed row may not inherit.

    A row with committed rows behind it that inherited this would gain six
    columns in the middle of its header, and a store whose header moved in the
    middle cannot be appended to. Asserting the order makes that a checked fact
    rather than a claim in a docstring.
    """
    columns = StampedReading.csv_columns()

    assert columns == (
        "version",
        "judge_id",
        "judge_model",
        "judge_temperature",
        "thinking_spans",
        "prompt_digest",
        "grammar_digest",
        "date",
        "reading",
    )


def test_a_reading_taken_without_a_model_leaves_the_model_cells_empty() -> None:
    """Six of the seven are nullable, so a caller fills what it knows."""
    row = StampedReading.model_validate(
        {"date": "2026-09-20", "reading": 0.5, "judge_id": "paper-judge"}
    )

    assert row.judge_model is None
    assert row.judge_temperature is None
    assert row.thinking_spans is None
    assert row.csv_row()["judge_model"] == ""
    assert StampedReading.from_csv_row(row.csv_row()) == row


def test_the_slug_column_takes_any_slug_and_refuses_anything_else() -> None:
    """No roster, so the rule is the shape of the cell and nothing more.

    A judge that has not been written yet must be recordable, and a value that
    would break the cell must not be.
    """
    assert a_reading(judge_id="a-judge-nobody-has-written-yet").judge_id
    assert a_reading(judge_id="x" * judge_call.SLUG_MAX_LENGTH).judge_id

    with pytest.raises(ValidationError, match="judge_id"):
        a_reading(judge_id="Not A Slug")
    with pytest.raises(ValidationError, match="judge_id"):
        a_reading(judge_id="x" * (judge_call.SLUG_MAX_LENGTH + 1))


def test_the_model_cell_stays_one_printable_line() -> None:
    """`state/**/*.csv` merges by union, which resolves one physical line at a time."""
    with pytest.raises(ValidationError, match="judge_model"):
        a_reading(judge_model="first line\nsecond line")
    with pytest.raises(ValidationError, match="judge_model"):
        a_reading(judge_model="w" * 97)


def test_nothing_generates_a_schema_for_the_mixin() -> None:
    """It is a `Model`, so it has no stem and the exporter never reaches it.

    `export()` calls `schema_filename()` on every member of the tuple, so a
    stem-less mixin registered there would stop the export rather than produce a
    stray file.
    """
    assert not issubclass(JudgeConfigStamp, Contract)
    assert not hasattr(JudgeConfigStamp, "__schema_stem__")

    exported = [
        contract.__name__
        for contract in CONTRACTS
        if contract.__module__ == judge_call.__name__
    ]
    assert not exported, f"{exported} is in the export tuple and this module declares no stem"


def test_the_module_reaches_nothing_outside_the_contracts_package() -> None:
    """Seam 1, as a property of the import list rather than as a sentence.

    A judge imported here would reach every row that inherits the stamp, and one
    tenant's vocabulary would arrive in another tenant's contract.
    """
    tree = ast.parse(inspect.getsource(judge_call))

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
    assert not strayed, f"the stamp reaches {strayed}, which is outside {CONTRACTS_PACKAGE}"
