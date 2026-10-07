"""Does the council's run record name its step and refuse retired CSV headings?"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep
from idhazh.contracts.file_envelope import Format, Period, RowIdentity, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName

from ._fixtures import FIXTURE_FILES

pytestmark = pytest.mark.contract

FIXTURES = CONTRACT_FIXTURES_DIR / "council-run-record"

#: The stamp on every row the first shape filed, which a migrated row keeps.
FIRST_SHAPE_STAMP: Final = "2026-09-21T12:00"

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
    """One retired CSV shape without its unused host column."""
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


@pytest.mark.parametrize("number", ["-2", "-1", "0", "3", "", "-3", "first"])
def test_every_retired_shard_heading_is_refused(number: str) -> None:
    with pytest.raises(ValidationError, match="shard"):
        CouncilRunRecord.from_csv_row(an_old_row(shard=number))


@pytest.mark.parametrize("heading", ["shard", "shards"])
@pytest.mark.parametrize("value", ["", "0"])
def test_a_retired_heading_beside_a_current_row_is_refused(
    heading: str, value: str
) -> None:
    current = a_record("a-part-that-ran-the-model").csv_row()
    with pytest.raises(ValidationError, match=heading):
        CouncilRunRecord.from_csv_row(current | {heading: value})


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


def test_a_filed_legacy_csv_row_is_refused_without_changing_its_migrated_fixture() -> None:
    [filed] = csv.DictReader(io.StringIO(A_FILED_COUNT))
    with pytest.raises(ValidationError, match="shard"):
        CouncilRunRecord.from_csv_row(filed)
    migrated = a_record("a-migrated-count-that-had-nothing-to-do")
    assert CouncilRunRecord.from_csv_row(migrated.csv_row()) == migrated
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


@pytest.mark.parametrize("fmt", [Format.PARQUET, Format.JSON])
def test_a_migrated_old_stamp_round_trips_through_raw_and_compact(
    tmp_path: Path, fmt: Format,
) -> None:
    row = a_record("a-migrated-count-that-had-nothing-to-do")
    identity = WriterIdentity(
        run_id=row.run_id, attempt=1, job=ServerJob.SAVE_COUNCIL_RESULTS, shard=0,
        producer="council.session", git_sha="a" * 40,
    )
    raw = ledger.persist(
        tmp_path, [row], ledger=LedgerName.COUNCIL_RUN_RECORDS,
        covers=row.date, identity=identity, fmt=fmt,
    )
    assert ledger.load(raw, model=CouncilRunRecord) == [row]
    stored = ledger.load_stored(raw, model=CouncilRunRecord)
    compact = ledger.persist_period(
        tmp_path, stored, model=CouncilRunRecord, ledger=LedgerName.COUNCIL_RUN_RECORDS,
        period=Period.DAILY, covers=row.date, fmt=fmt,
        identity=identity.model_copy(update={"job": ServerJob.RUN_TASKS}), built_from=1,
    )
    assert ledger.load([compact], model=CouncilRunRecord) == [row]
    assert ledger.load_stored([compact], model=CouncilRunRecord) == stored


def test_the_row_shares_one_name_with_the_ledger_door_and_it_means_the_council_run() -> None:
    """The door stamps its own cells on every row, and a row field of one of those names
    takes the place of the door's cell. So the row declares none of them but `run_id`,
    which is the council run on both sides.
    """
    assert set(CouncilRunRecord.model_fields) & set(RowIdentity.model_fields) == {"run_id"}
