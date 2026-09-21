"""Does the merge line's reading survive a day file, and does it carry no rate?

Three questions. The row has to make the trip to a CSV day file and back with
every cell intact; the two cells drawn from the labelled negatives cannot
outnumber the negatives; and no column may hold a precision, a recall or an
accuracy, because a stored rate is a rate somebody reads without its denominator.

What none of this can settle is whether the line is any good. Nothing writes this
row yet; the step that scores it is what proves the numbers.

Nothing here reads a committed file. The day tree is built under `tmp_path`, so
what this costs does not move as the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import day_partition, ledger
from idhazh.contracts.judge_call import JudgeConfigStamp
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.telemetry import inventory

pytestmark = pytest.mark.contract

FIXTURES = CONTRACT_FIXTURES_DIR / "content-similarity-judge-merge-line-holdout-score"

#: The day these tests are drawn on, and a date in another month so the
#: directory arithmetic has two answers to disagree about.
A_DAY = "2026-09-20"
ANOTHER_DAY = "2026-10-01"

#: Words that would name a derived rate. A column spelled any of these is a rate
#: stored away from the counts it came from, which is the one thing this row is
#: built to prevent.
RATE_WORDS = ("rate", "precision", "recall", "accuracy", "f1", "percent", "share")


def a_scoring(name: str) -> MergeLineHoldoutScore:
    """One recorded scoring run, read inside the test that asks for it."""
    return MergeLineHoldoutScore.from_json(read_text(FIXTURES / f"{name}.json"))


def test_a_scoring_round_trips_through_a_day_file() -> None:
    """Write it, read it back through the contract, get the same row."""
    row = a_scoring("a-line-scored-against-the-holdout")

    document = ledger.render_file(MergeLineHoldoutScore.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(read_back) == 1
    assert MergeLineHoldoutScore.from_csv_row(read_back[0]) == row
    assert len(document.splitlines()) == 2, "a cell put a line break in the row"
    assert "" not in row.csv_row().values(), "nothing on this row is optional, so nothing is empty"


@pytest.mark.parametrize("cell", ("merged_and_two_stories", "apart_and_two_stories"))
def test_the_negative_cells_cannot_outnumber_the_labelled_negatives(cell: str) -> None:
    """The oracle: both cells are drawn from the pairs the label calls two stories.

    A pair marked two stories lands in exactly one of them, or in neither when
    retention has taken one of its days - so together they are at or below the
    population. A row where they are not would give a false-merge rate above one.
    Driven once per cell, because a check that added only one of them would pass
    a test that moved only the other.
    """
    payload: dict[str, Any] = a_scoring("a-line-scored-against-the-holdout").model_dump(
        mode="json"
    )

    assert (
        payload["merged_and_two_stories"] + payload["apart_and_two_stories"]
        == payload["labelled_two_story_pairs"]
    )
    with pytest.raises(ValidationError, match="labelled two-story pairs"):
        MergeLineHoldoutScore.model_validate(payload | {cell: payload[cell] + 1})


def test_a_day_retention_has_eaten_into_is_recorded_rather_than_refused() -> None:
    """Fewer pairs than the holdout carries is a shrinking comparison, not an error.

    The pairs nothing could be counted for get their own cell, so a reader sees
    the comparison narrowing instead of reading a better-looking row.
    """
    row = a_scoring("a-holdout-retention-has-eaten-into")

    counted = row.merged_and_two_stories + row.apart_and_two_stories
    assert counted < row.labelled_two_story_pairs
    assert row.pairs_unresolved > 0


def test_the_row_stores_counts_and_leaves_every_rate_to_be_derived() -> None:
    """A stored rate is a rate read without its denominator (Guardrail #10)."""
    columns = MergeLineHoldoutScore.csv_columns()

    named = sorted(
        column for column in columns if any(word in column.lower() for word in RATE_WORDS)
    )
    assert not named, f"{named} would store a rate away from the counts it came from"
    assert "labelled_two_story_pairs" in columns, (
        "the population the false-merge cell is drawn from left the row, so every rate a "
        "reader derives is derived without its denominator in view"
    )


def test_the_row_carries_no_call_stamp_because_no_model_runs_in_it() -> None:
    """The shipped line calls no model, so five empty cells would be a false claim."""
    columns = set(MergeLineHoldoutScore.csv_columns())

    assert not columns & set(JudgeConfigStamp.model_fields), (
        "this row inherited a judge's call stamp, which asserts an instrument that "
        "never ran in it"
    )
    assert {"applied_line", "scorer_model", "cosine_weight", "key_point_weight"} <= columns, (
        "the row stopped saying what the line was made of, so two runs cannot be compared"
    )


def test_the_labeller_is_recorded_rather_than_checked_against_a_roster() -> None:
    """The marks came from outside this pipeline, so the column has to hold that.

    One printable line, because a newline splits the row for any reader that
    takes a day file a line at a time.
    """
    payload: dict[str, Any] = a_scoring("a-line-scored-against-the-holdout").model_dump(
        mode="json"
    )

    assert MergeLineHoldoutScore.model_validate(
        payload | {"labeller": "a-model-this-repository-does-not-ship"}
    ).labeller
    with pytest.raises(ValidationError, match="labeller"):
        MergeLineHoldoutScore.model_validate(payload | {"labeller": "two\nlines"})


def test_the_day_file_a_date_resolves_to_is_two_levels_under_state() -> None:
    """A third level is invisible to the day inventory and the miss is silent."""
    relpath = ledger.merge_line_holdout_scores_relpath(A_DAY)

    assert relpath == "state/content-similarity-judge/merge-line-holdout-scores/2026/09/20.csv"
    assert ledger.merge_line_holdout_scores_path(Path("state"), A_DAY).as_posix() == relpath

    segments = relpath.removeprefix(f"{ledger.STATE_DIRNAME}/").split("/")
    assert segments[:2] == [
        ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME,
        ledger.MERGE_LINE_HOLDOUT_SCORES_DIRNAME,
    ]
    assert segments[2:] == ["2026", "09", "20.csv"], "the day tree gained a directory level"


def test_the_instrument_reader_finds_the_day_this_store_wrote(tmp_path: Path) -> None:
    """A store this row creates is visible rather than silently absent."""
    state_root = tmp_path / ledger.STATE_DIRNAME
    for day in (A_DAY, ANOTHER_DAY):
        path = ledger.merge_line_holdout_scores_path(state_root, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            ledger.render_file(
                MergeLineHoldoutScore.csv_columns(),
                [a_scoring("a-line-scored-against-the-holdout").csv_row()],
            ),
            encoding="utf-8",
            newline="",
        )

    report = inventory.files(state_root, date=A_DAY)

    assert any(
        "content-similarity-judge/merge-line-holdout-scores/2026/09/20.csv" in line
        for line in report
    ), report

    root = (
        state_root
        / ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME
        / ledger.MERGE_LINE_HOLDOUT_SCORES_DIRNAME
    )
    assert [day_partition.date_of(found) for found in day_partition.day_files(root)] == [
        A_DAY,
        ANOTHER_DAY,
    ]
