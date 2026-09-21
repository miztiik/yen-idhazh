"""Where the merge line stands against the marked holdout, and when it refuses to say.

Unit tier for the two rules a reading rests on - which side of the line a pair
falls and how much of the marked file has to be counted - and integration tier
for the verb writing a row the contract reads back.

**The oracle has two arms and both are checked.** The four cells plus the
unresolved count add up to the marked population, AND the count that was
resolved clears the floor. The first arm on its own is satisfied by four zeros
and a full unresolved count, which is a run that scored nothing reading as a
line that merged nothing.

**No test here walks committed data** (CLAUDE.md section 13). Every reading is
taken over a marked file and two published days this test writes into its own
tree. That tree is fixed in size, it cannot be moved by a run, and it carries
the case the committed archive has never produced: a marked pair whose day
retention has deleted.

Nothing calls a model and nothing opens a socket, because the step does neither.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR

from idhazh import assemble, config, ledger
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestEmbeddings,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
)
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.knobs.placement import HOLDOUT_RESOLVED_SHARE_MIN
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, to_base64
from idhazh.similarity import holdout
from idhazh.stages.score_merge_line_holdout import stage_score_merge_line_holdout

#: The two days this test publishes. Two rather than one, so a marked pair can
#: straddle midnight and so one day can be taken away without taking both.
A_DAY: Final = "2026-09-17"
ANOTHER_DAY: Final = "2026-09-18"

#: The day the reading is filed under, which is neither of the published days.
#: The marked row names its own two dates, so the reading's date is the day it
#: was taken and nothing else.
SCORED_ON: Final = "2026-09-20"

A_RUN: Final = "2026-09-20-35534060762"

A_LABELLER: Final = "claude-opus-4.6"

#: Digits spelled as letters, so a built headline carries no figure. Two
#: headlines around two different numbers are vetoed before they are scored, and
#: every pair here has to reach the score.
_NO_FIGURES: Final = str.maketrans("0123456789", "abcdefghij")


def unit(degrees: float) -> str:
    """A real quantised vector at a chosen angle, through the encoder's wire format.

    Two components carry the whole vector, so the angle between two of these is
    the angle between their arguments and a test names the score it wants
    instead of discovering it.
    """
    radians = math.radians(degrees)
    return to_base64([math.cos(radians), math.sin(radians)] + [0.0] * (DIMENSIONS - 2))


def item(item_id: str, *, outlet: str) -> DigestItem:
    """One published story, with the cells a pair score reads filled in."""
    return DigestItem(
        item_id=item_id,
        vertical="world",
        title=f"Story {item_id.translate(_NO_FIGURES)}",
        source_url=f"https://{outlet}.test/{item_id}",
        source_id=outlet,
        source_name=outlet.title(),
        summary="A summary long enough to be a summary.",
        key_points=["One point."],
        band=ConfidenceBand.HIGH,
        rank_score=1.0,
        introduced_by_run=1,
    )


def publish(root: Path, date: str, items: list[DigestItem], angles: list[float]) -> None:
    """Write one published day into the test's own tree."""
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{date}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(Counter(one.vertical for one in items).items())
        ],
        items=items,
        embeddings=DigestEmbeddings(
            model_id=EMBEDDER_ID,
            dimensions=DIMENSIONS,
            dtype=DTYPE,
            vectors={
                one.item_id: unit(angle) for one, angle in zip(items, angles, strict=True)
            },
        ),
    )
    target = assemble.day_dir(root, date)
    target.mkdir(parents=True, exist_ok=True)
    (target / "digest.json").write_text(day.to_json(), encoding="utf-8", newline="")


def mark(
    left: DigestItem, right: DigestItem, *, left_date: str, right_date: str, same: bool
) -> SimilarityHoldoutPair:
    return SimilarityHoldoutPair(
        version=SimilarityHoldoutPair.schema_version(),
        left_url=left.source_url,
        right_url=right.source_url,
        left_date=left_date,
        right_date=right_date,
        left_title=left.title,
        right_title=right.title,
        same_story=same,
        marked_on="2026-09-19",
        note=f"{A_LABELLER} at score 0.9403",
    )


def write_marks(state: Path, marks: list[SimilarityHoldoutPair]) -> Path:
    path = ledger.similarity_holdout_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = SimilarityHoldoutPair.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for one in marks:
            writer.writerow(one.csv_row())
    return path


def committed_rows(state: Path, date: str) -> list[MergeLineHoldoutScore]:
    """The rows one day file holds, read back through the contract that wrote them."""
    path = ledger.merge_line_holdout_scores_path(state, date)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [MergeLineHoldoutScore.from_csv_row(row) for row in csv.DictReader(handle)]


def a_marked_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Two published days and six marked pairs over them, in this test's own tree.

    The angles put three pairs above a 0.94 line and three below it, and the
    marks disagree with the line on one pair in each direction - so all four
    cells are non-zero and a swapped cell fails rather than reading as a zero.
    """
    state, digest = tmp_path / "state", tmp_path / "digest"
    first = [item(f"world-0{n}", outlet=f"paper-{n}") for n in range(1, 5)]
    second = [item(f"world-0{n}", outlet=f"paper-{n}") for n in range(5, 9)]
    # 0 degrees against 15 degrees is a cosine of 0.9659, and against 25 degrees
    # 0.9063 - one clear of a 0.94 line and one clear below it.
    publish(digest, A_DAY, first, [0.0, 15.0, 0.0, 25.0])
    publish(digest, ANOTHER_DAY, second, [0.0, 15.0, 0.0, 25.0])

    marks = [
        mark(first[0], first[1], left_date=A_DAY, right_date=A_DAY, same=True),
        mark(first[2], first[3], left_date=A_DAY, right_date=A_DAY, same=True),
        mark(second[0], second[1], left_date=ANOTHER_DAY, right_date=ANOTHER_DAY, same=False),
        mark(second[2], second[3], left_date=ANOTHER_DAY, right_date=ANOTHER_DAY, same=False),
        mark(first[0], second[1], left_date=A_DAY, right_date=ANOTHER_DAY, same=True),
        mark(first[2], second[3], left_date=A_DAY, right_date=ANOTHER_DAY, same=False),
    ]
    write_marks(state, marks)
    return state, digest


def committed_settings() -> config.Settings:
    """The committed config, read inside a test rather than at module scope."""
    return config.load(CONFIG_DIR)


# --- which side of the line a pair falls --------------------------------------


def a_reading(
    *scores: tuple[bool, float], unresolved: int = 0, marked: int | None = None
) -> holdout.Reading:
    """A reading built from written-down scores, so no day file is needed."""
    scored = tuple(holdout.ScoredMark(same_story=same, score=score) for same, score in scores)
    return holdout.Reading(
        scored=scored,
        marked=len(scored) + unresolved if marked is None else marked,
        unresolved=unresolved,
        two_story_marks=sum(1 for same, _ in scores if not same),
        days_opened=1,
    )


def test_a_pair_scoring_exactly_the_line_is_counted_as_a_merge() -> None:
    """`collapse_same_story` refuses on `score < floor_min`, so the boundary merges.

    Counted the other way, the one pair the line is closest to is filed on the
    safe side of the reading - which is the pair the whole comparison is about.
    """
    cells = holdout.count_cells(a_reading((False, 0.94)), line=0.94)

    assert cells.merged_and_two_stories == 1
    assert cells.apart_and_two_stories == 0


def test_the_two_directions_of_a_mistake_are_counted_apart() -> None:
    """A line that joins two stories hides one; a line that splits one shows it twice.

    Added together they would be one error count, and the two are not the same
    error - which is why the shape carries four cells rather than three.
    """
    cells = holdout.count_cells(
        a_reading((True, 0.99), (True, 0.50), (False, 0.99), (False, 0.50)), line=0.94
    )

    assert (cells.merged_and_one_story, cells.merged_and_two_stories) == (1, 1)
    assert (cells.apart_and_one_story, cells.apart_and_two_stories) == (1, 1)


def test_the_negative_population_counts_marks_the_line_never_reached() -> None:
    """The denominator is the marked file, not the part of it that could be scored.

    A rate read against the pairs that happened to survive retention is a rate
    that improves every time a day is deleted.
    """
    reading = holdout.Reading(
        scored=(holdout.ScoredMark(same_story=False, score=0.99),),
        marked=4,
        unresolved=3,
        two_story_marks=3,
        days_opened=1,
    )

    cells = holdout.count_cells(reading, line=0.94)

    assert cells.two_story_marks == 3, "two marks were never scored and still count"
    assert cells.merged_and_two_stories + cells.apart_and_two_stories == 1


# --- how much of the file has to be counted ------------------------------------


@pytest.mark.parametrize(
    ("marked", "floor"), [(0, 0), (1, 1), (200, 100), (201, 101), (3, 2)]
)
def test_the_floor_is_half_the_marked_file_rounded_up(marked: int, floor: int) -> None:
    """Half, and never half minus one: an odd file rounds towards the stricter answer."""
    assert holdout.resolved_floor(marked) == floor


def test_the_floor_is_a_constant_and_not_a_knob() -> None:
    """It says what makes a reading mean anything, so it is not something to tune.

    A share read from `config/` is a share somebody lowers on the morning the
    reading goes red, which is the one morning it has to hold.
    """
    assert HOLDOUT_RESOLVED_SHARE_MIN == 0.5
    settings = config.load(CONFIG_DIR)
    knobs = settings.app.assemble.same_story.model_dump()
    assert not [name for name in knobs if "holdout" in name], (
        "a holdout knob has appeared in the same_story block, and the floor this "
        "row rests on is a constant on purpose"
    )


# --- the verb, end to end ------------------------------------------------------


def test_the_four_cells_and_the_unresolved_count_add_up_to_the_marked_file(
    tmp_path: Path,
) -> None:
    """The first arm of the oracle: every marked pair lands in exactly one count.

    A pair counted twice, or one dropped on its way past, would leave the row
    describing a file that is not the one on disk.
    """
    state, digest = a_marked_tree(tmp_path)

    row = stage_score_merge_line_holdout(
        SCORED_ON,
        run_id=A_RUN,
        labeller=A_LABELLER,
        settings=committed_settings(),
        state_dir=state,
        digest_root=digest,
    )

    assert row is not None
    counted = (
        row.merged_and_one_story
        + row.merged_and_two_stories
        + row.apart_and_one_story
        + row.apart_and_two_stories
        + row.pairs_unresolved
    )
    assert counted == 6, "six marks were written and six have to be counted"
    assert row.labelled_two_story_pairs == 3
    assert (row.merged_and_one_story, row.apart_and_one_story) == (2, 1)
    assert (row.merged_and_two_stories, row.apart_and_two_stories) == (1, 2)


def test_the_row_is_written_where_the_ledger_says_and_reads_back(tmp_path: Path) -> None:
    """The store the path helper already declared, filled by the verb that names it."""
    state, digest = a_marked_tree(tmp_path)

    row = stage_score_merge_line_holdout(
        SCORED_ON,
        run_id=A_RUN,
        labeller=A_LABELLER,
        settings=committed_settings(),
        state_dir=state,
        digest_root=digest,
    )

    assert row is not None
    written = committed_rows(state, SCORED_ON)
    assert written == [row]
    assert ledger.merge_line_holdout_scores_path(state, SCORED_ON).is_file()


def test_a_second_attempt_at_one_run_leaves_one_row(tmp_path: Path) -> None:
    """Date and run are what make two rows the same record, so a repeat settles away.

    Both attempts count the same marks over the same committed days, so there is
    nothing to choose between them and the first row wins.
    """
    state, digest = a_marked_tree(tmp_path)
    settings = committed_settings()

    for _ in range(2):
        stage_score_merge_line_holdout(
            SCORED_ON,
            run_id=A_RUN,
            labeller=A_LABELLER,
            settings=settings,
            state_dir=state,
            digest_root=digest,
        )

    assert len(committed_rows(state, SCORED_ON)) == 1


def test_a_pair_whose_day_is_gone_is_counted_unresolved_rather_than_dropped(
    tmp_path: Path,
) -> None:
    """Retention deletes days the marked file still names, and that has to be visible.

    Dropped instead, the comparison would look complete at whatever size
    retention had left it.
    """
    state, digest = a_marked_tree(tmp_path)
    for path in sorted(assemble.day_dir(digest, ANOTHER_DAY).glob("*")):
        path.unlink()

    reading = holdout.score_marks(
        holdout.marked_pairs(state),
        digest_root=digest,
        cosine_weight=1.0,
        key_point_weight=0.0,
    )

    assert reading.marked == 6
    assert reading.unresolved == 4, "two pairs sat on that day and two straddled it"
    assert len(reading.scored) == 2


def test_a_reading_below_the_floor_writes_no_row_at_all(tmp_path: Path) -> None:
    """The second arm of the oracle, and the one the first arm cannot stand in for.

    Four zeros and a full unresolved count satisfy the sum. The floor is what
    makes that a refusal rather than a row saying the line merged nothing.
    """
    state, digest = a_marked_tree(tmp_path)
    for date in (A_DAY, ANOTHER_DAY):
        for path in sorted(assemble.day_dir(digest, date).glob("*")):
            path.unlink()

    row = stage_score_merge_line_holdout(
        SCORED_ON,
        run_id=A_RUN,
        labeller=A_LABELLER,
        settings=committed_settings(),
        state_dir=state,
        digest_root=digest,
    )

    assert row is None
    assert not ledger.merge_line_holdout_scores_path(state, SCORED_ON).exists()


def test_a_marked_file_that_is_not_there_writes_no_row(tmp_path: Path) -> None:
    """A fresh clone has no marks, which is an ordinary state rather than a failure."""
    state, digest = tmp_path / "state", tmp_path / "digest"

    row = stage_score_merge_line_holdout(
        SCORED_ON,
        run_id=A_RUN,
        labeller=A_LABELLER,
        settings=committed_settings(),
        state_dir=state,
        digest_root=digest,
    )

    assert row is None


def test_the_row_records_the_ruler_the_cells_were_counted_under(tmp_path: Path) -> None:
    """Two rows counted under two encoders answer two different questions.

    The weights and the encoder travel on the row so a later reader comparing
    two of them can tell whether both were asked the same thing.
    """
    state, digest = a_marked_tree(tmp_path)
    settings = committed_settings()

    row = stage_score_merge_line_holdout(
        SCORED_ON,
        run_id=A_RUN,
        labeller=A_LABELLER,
        settings=settings,
        state_dir=state,
        digest_root=digest,
    )

    assert row is not None
    same_story = settings.app.assemble.same_story
    assert row.applied_line == same_story.floor_min
    assert row.cosine_weight == same_story.cosine_weight
    assert row.key_point_weight == same_story.key_point_weight
    assert row.labeller == A_LABELLER
