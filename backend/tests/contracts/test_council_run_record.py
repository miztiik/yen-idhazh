"""Does the council's run record name its step, and read every row the first shape filed?

The record names a step and a part where the first shape filed one `shard`
number, because the ledger door writes its own `shard` cell on every row. Each
row the first shape filed has to read into the new shape with no cell lost, and
a row that cannot be placed has to be refused rather than read as a guess.

What it cannot settle is whether a committed file holds a value outside the set
read here. The migration's plan pass reads every committed row; these tests read
rows they build, so what they cost does not move as the archive grows (CLAUDE.md
Guardrail #12).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import Any, Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import ledger
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep
from idhazh.contracts.file_envelope import RowIdentity

from ._fixtures import FIXTURE_FILES

pytestmark = pytest.mark.contract

FIXTURES = CONTRACT_FIXTURES_DIR / "council-run-record"

#: The stamp on every row the first shape filed, which a migrated row keeps.
FIRST_SHAPE_STAMP: Final = "2026-09-21T12:00"

#: One part, and four: the count on every row the first shape filed.
WIDTHS: Final = (1, 4)

#: The first shape read backwards: the number each once-a-date step was filed
#: under. A part was filed under its own number.
OLD_NUMBER_OF: Final = {
    EvaluationStep.SELECT_JUDGE_WORK: -1,
    EvaluationStep.COMBINE_JUDGE_RESULTS: -2,
}

#: The cells a step that ran no model, and has no part, leaves empty.
ABSENT: Final = ("work_part_index", "model_calls", "tokens_in", "tokens_out", "model_seconds")

#: One row the first shape really filed, copied out of its committed day file
#: rather than read from it: the heading line and the row, `host_model` included.
A_FILED_COUNT: Final = (
    "version,date,run_id,judge_id,shard,shards,outcome,started_at,seconds_spent,"
    "model_calls,tokens_in,tokens_out,model_seconds,host_model\n"
    "2026-09-21T12:00,2026-10-03,2026-10-04-37164837568,content-similarity-judge,"
    "-2,4,nothing_to_do,2026-10-04T00:25:29Z,0.0108935409999944,,,,,\n"
)


def a_record(name: str) -> CouncilRunRecord:
    """One recorded step, read inside the test that asks for it."""
    return CouncilRunRecord.from_json(read_text(FIXTURES / f"{name}.json"))


def an_old_row(**cells: str) -> dict[str, str]:
    """One row the first shape filed, as the migrator hands it over.

    Every heading that shape wrote except `host_model`: the migrator drops that
    heading while it is empty, and refuses the row when it is not.
    """
    return {
        "version": FIRST_SHAPE_STAMP,
        "date": "2026-09-20",
        "run_id": "2026-09-22-35672856221",
        "judge_id": "content-similarity-judge",
        "shard": "0",
        "shards": "4",
        "outcome": "completed",
        "started_at": "2026-09-22T00:40:13Z",
        "seconds_spent": "2.203906669999995",
        "model_calls": "",
        "tokens_in": "",
        "tokens_out": "",
        "model_seconds": "",
    } | cells


def the_old_number(record: CouncilRunRecord) -> int:
    """A step and its part, mapped back to the one number the first shape filed them under."""
    if record.evaluation_step is EvaluationStep.EVALUATE_WORK_PART:
        assert record.work_part_index is not None
        return record.work_part_index
    assert record.work_part_index is None
    return OLD_NUMBER_OF[record.evaluation_step]


@pytest.mark.parametrize("width", WIDTHS)
def test_every_old_number_reads_as_its_own_step_and_part_and_maps_back(width: int) -> None:
    """The oracle: each number the first shape filed names one step and part, and no other.

    It fails if an old value is lost, merged with another, or read as the wrong
    step.
    """
    numbers = [-1, -2, *range(width)]

    read = {
        number: CouncilRunRecord.from_csv_row(an_old_row(shard=str(number), shards=str(width)))
        for number in numbers
    }

    pairs = [(record.evaluation_step, record.work_part_index) for record in read.values()]
    assert len(set(pairs)) == len(numbers), f"two old numbers read as one step and part: {pairs}"
    assert {record.work_part_count for record in read.values()} == {width}
    assert {number: the_old_number(record) for number, record in read.items()} == {
        number: number for number in numbers
    }


@pytest.mark.parametrize(
    ("cells", "named"),
    [
        ({"shard": "-3"}, "shard"),
        ({"shard": ""}, "shard"),
        ({"shard": "first"}, "shard"),
        ({"shard": "4"}, "work_part_index"),
        ({"shard": "1", "evaluation_step": "evaluate_work_part"}, "two shapes"),
        ({"shard": "1", "work_part_index": "1"}, "two shapes"),
        ({"work_part_count": "4"}, "two shapes"),
    ],
    ids=[
        "below-the-two-steps",
        "empty",
        "not-a-number",
        "the-count-itself",
        "beside-a-named-step",
        "beside-a-part-index",
        "beside-a-part-count",
    ],
)
def test_an_old_row_the_reader_cannot_place_is_refused_by_name(
    cells: dict[str, str], named: str
) -> None:
    """A row read as its nearest guess is a night recorded wrong, so it stops the read."""
    with pytest.raises(ValueError, match=named):
        CouncilRunRecord.from_csv_row(an_old_row(**cells))


@pytest.mark.parametrize(
    "refused",
    [
        lambda row: {"evaluation_step": EvaluationStep.SELECT_JUDGE_WORK.value},
        lambda row: {"work_part_index": None},
        lambda row: {"work_part_index": row["work_part_count"]},
        lambda row: {"work_part_count": 0},
    ],
    ids=[
        "a-part-on-a-once-a-date-step",
        "a-part-step-with-no-part",
        "outside-the-count",
        "no-count",
    ],
)
def test_a_part_is_named_exactly_where_the_work_was_split(
    refused: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    """A once-a-date step has no part, and a part sits inside the count its row carries."""
    payload = a_record("a-part-that-ran-the-model").model_dump(mode="json")

    with pytest.raises(ValidationError, match="work_part"):
        CouncilRunRecord.model_validate(payload | refused(payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evaluation_step", "select-judge-work"),
        ("outcome", "Completed"),
        ("judge_id", "Not A Slug"),
    ],
)
def test_a_cell_outside_its_column_is_refused_by_name(field: str, value: str) -> None:
    """A free-text step or outcome splits a group-by silently on one typo."""
    payload = a_record("a-selection-that-ran-no-model").model_dump(mode="json")

    with pytest.raises(ValidationError, match=field):
        CouncilRunRecord.model_validate(payload | {field: value})


def test_every_recorded_step_round_trips_through_one_csv_file() -> None:
    """The council ships its rows between jobs as CSV, so the trip has to lose nothing.

    An absent value is an empty cell and comes back absent. Zero would read as a
    model that answered nothing, which is a different fact.
    """
    names = [
        name.removeprefix("council-run-record/").removesuffix(".json")
        for name in FIXTURE_FILES
        if name.startswith("council-run-record/")
    ]
    rows = [a_record(name) for name in names]

    document = ledger.render_file(CouncilRunRecord.csv_columns(), [row.csv_row() for row in rows])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(document.splitlines()) == len(rows) + 1, "a cell put a line break in a row"
    assert [CouncilRunRecord.from_csv_row(cells) for cells in read_back] == rows
    selection = read_back[names.index("a-selection-that-ran-no-model")]
    assert {name: selection[name] for name in ABSENT} == dict.fromkeys(ABSENT, "")


def test_a_row_the_first_shape_filed_reads_as_the_migrated_row() -> None:
    """Every cell of a real filed row survives the read, its stamp included."""
    [filed] = csv.DictReader(io.StringIO(A_FILED_COUNT))
    assert filed.pop("host_model") == "", "the migrator refuses a filled host_model"

    migrated = CouncilRunRecord.from_csv_row(filed)

    assert migrated == a_record("a-migrated-count-that-had-nothing-to-do")
    assert migrated.version == FIRST_SHAPE_STAMP


def test_a_heading_no_field_declares_is_refused_rather_than_dropped() -> None:
    """A dropped heading is a cell lost without a word, so the model refuses it by name."""
    current = a_record("a-part-that-ran-the-model").csv_row()

    for row in (an_old_row(host_model=""), current | {"host_model": ""}):
        with pytest.raises(ValidationError, match="host_model"):
            CouncilRunRecord.from_csv_row(row)


def test_a_migrated_row_keeps_a_stamp_the_changelog_describes() -> None:
    """A migrated row keeps the first shape's stamp, so the changelog keeps that shape's entries."""
    stamps = [entry.version for entry in CouncilRunRecord.__changelog__]

    assert FIRST_SHAPE_STAMP in stamps[1:], "the first shape's stamp is not an older entry"


def test_the_row_shares_one_name_with_the_ledger_door_and_it_means_the_council_run() -> None:
    """The door stamps its own cells on every row, and a row field of one of those names
    takes the place of the door's cell. So the row declares none of them but `run_id`,
    which is the council run on both sides.
    """
    assert set(CouncilRunRecord.model_fields) & set(RowIdentity.model_fields) == {"run_id"}
