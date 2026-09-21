"""What does the record hold after a day is counted into it, and what is refused?

The arithmetic, and the collecting job that applies it: what it appends beside
the record is part of what a counted day leaves behind.

Every record and every row here is built in the test that uses it. Nothing walks
the committed day tree: the arithmetic is about one record and a handful of rows,
and a fixture that grows with the archive would make these slower every week
(CLAUDE.md section 13).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import assemble, config, ledger
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.council import metrics_sink
from idhazh.similarity import counting
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp
from idhazh.similarity.tenant import JUDGE_ID
from idhazh.stages import count_verdicts
from idhazh.stages.judge_item_pairs import VERDICTS_DIRNAME

DATE: Final = "2026-09-18"

#: The name the council night these tests settle files its rows under.
A_COUNCIL_RUN: Final = f"{DATE}-9"

#: A twelve-slot band, wide enough to tell an edge from a middle and small enough
#: that a failing assertion names a slot a reader can count to.
KNOBS: Final = SimilarityThresholdConfig(band_low=0.50, band_high=0.62, bin_width=0.01)


def a_scorer() -> ScorerStamp:
    return ScorerStamp(scorer_model="all-minilm-l6-v2-quantized", cosine_weight=1.0,
                       key_point_weight=0.0)


def a_judge() -> JudgeStamp:
    return JudgeStamp(judge_model="qwen3-5-9b-q4-k-m", prompt_digest="a" * 64,
                      grammar_digest="b" * 64, judge_temperature=0.0,
                      decode_digest="c" * 64, thinks=False)


def a_record() -> StorySimilarityDistribution:
    return counting.empty_record(KNOBS, scorer=a_scorer(), judge=a_judge())


def a_row(
    *,
    score: float,
    verdict: SameStoryVerdict = SameStoryVerdict.NO,
    usable: bool = True,
    pair_key: str | None = None,
    run_id: str = f"{DATE}-1",
    judged_by_run_id: str | None = None,
) -> StorySimilarityPair:
    """One judged pair, re-cast from the committed contract fixture.

    Read inside the helper rather than at module scope, so a fixture that stops
    parsing fails the test that asked for a row instead of every test here.
    """
    raw = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR / "story-similarity-pair" / "judged-the-same-in-both-orders.json"
        )
    )
    return StorySimilarityPair.model_validate(
        raw
        | {
            "version": StorySimilarityPair.schema_version(),
            "date": DATE,
            "run_id": run_id,
            "judged_by_run_id": judged_by_run_id,
            "composite_score": score,
            "cosine": score,
            "verdict": verdict.value,
            "verdict_swapped": verdict.value,
            "usable": usable,
            "pair_key": pair_key or raw["pair_key"],
        }
    )


def test_a_score_lands_in_the_slot_whose_lower_edge_it_clears() -> None:
    """A pair scoring a slot's lower edge is in that slot, not the one below."""
    record = a_record()

    assert counting.slot_index(0.50, record=record) == 0
    assert counting.slot_index(0.5099, record=record) == 0
    assert counting.slot_index(0.51, record=record) == 1


def test_a_score_at_the_top_of_the_band_lands_in_the_last_slot() -> None:
    """`band_high` has no next slot to fall into, so it closes the last one."""
    record = a_record()

    assert counting.slot_index(0.62, record=record) == len(record.slots) - 1


def test_a_score_outside_the_band_lands_nowhere() -> None:
    """Below the band nothing was ever judged, so the record can say nothing."""
    record = a_record()

    assert counting.slot_index(0.499, record=record) is None
    assert counting.slot_index(0.621, record=record) is None


def test_an_exact_slot_edge_on_the_shipped_band_is_that_slot() -> None:
    """`(0.950 - 0.88) / 0.001` is 69.99999999999995, and an untoleranced walk files 69.

    Driven on the band the pipeline actually ships rather than this module's
    twelve-slot one, because the defect only appears at edges where the division
    lands a hair short - and the shipped band has 120 of them. The fit reads the
    merge line off a slot edge, so filing one slot low is a whole bin of error on
    the one number this feature exists to set.
    """
    record = counting.empty_record(
        SimilarityThresholdConfig(), scorer=a_scorer(), judge=a_judge()
    )

    for score in (0.900, 0.930, 0.950, 0.970, 0.990):
        index = counting.slot_index(score, record=record)
        assert index is not None
        assert record.slots[index].bin_low == pytest.approx(score), (
            f"{score} is a slot's own lower edge and belongs in that slot"
        )


def test_an_unusable_row_is_counted_nowhere() -> None:
    """A verdict nobody can vouch for still moves the line if it is counted."""
    record = a_record()

    counted = counting.count_day(record, [a_row(score=0.55, usable=False)], date=DATE)

    assert sum(slot.different_count for slot in counted.slots) == 0
    assert counted.counted_dates == (DATE,), "the day is still counted as read"


def test_an_unclear_verdict_is_counted_only_as_unclear() -> None:
    """Counted and never fitted on, so a rising share of them is visible."""
    record = a_record()

    counted = counting.count_day(
        record, [a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR)], date=DATE
    )

    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count, slot.unclear_count) == (0, 0, 1)


def test_folding_a_date_the_record_already_holds_raises() -> None:
    """A re-run of the count is free rather than a day counted twice."""
    record = counting.count_day(a_record(), [a_row(score=0.55)], date=DATE)

    with pytest.raises(ValueError, match=DATE):
        counting.count_day(record, [a_row(score=0.55)], date=DATE)


def test_a_changed_scorer_stamp_archives_and_starts_empty() -> None:
    """A different weight puts the same pair in a different slot."""
    record = a_record()
    moved = ScorerStamp(
        scorer_model="all-minilm-l6-v2-quantized", cosine_weight=0.8, key_point_weight=0.2
    )

    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) is None
    assert counting.inputs_changed(record, knobs=KNOBS, scorer=moved, judge=a_judge()) == ("1.0", "0.8")
    assert counting.archive_stem(record) != counting.archive_stem(
        counting.empty_record(KNOBS, scorer=moved, judge=a_judge())
    )


@pytest.mark.parametrize("field", ["judge_temperature", "decode_digest", "thinks"])
def test_every_value_the_record_stamps_is_a_value_the_detector_sees(field: str) -> None:
    """A stamp column the detector cannot see is a stamp that lies.

    The record would archive under a name nobody can explain: the counts move to
    a new file and the operator reading the held line is told nothing moved.
    """
    record = a_record()
    after = {
        "judge_temperature": dataclasses.replace(a_judge(), judge_temperature=0.2),
        "decode_digest": dataclasses.replace(a_judge(), decode_digest="d" * 64),
        "thinks": dataclasses.replace(a_judge(), thinks=True),
    }[field]

    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=after) is not None
    assert counting.archive_stem(record) != counting.archive_stem(
        counting.empty_record(KNOBS, scorer=a_scorer(), judge=after)
    )


def test_a_record_written_before_the_decode_columns_resets_once() -> None:
    """The read-side migration, and what it costs.

    A record written under the older shape carries the three decode values null,
    loads here, and stamps to a value it never stamped to - so the first day
    after the widening archives it and counts on from zero. That is the reset,
    it is by construction rather than by an input moving, and it happens once.
    """
    record = a_record()
    older = record.model_copy(
        update={"judge_temperature": None, "decode_digest": None, "judge_thinks": None}
    )

    assert older.record_stamp() != record.record_stamp()
    assert counting.inputs_changed(older, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) == (
        "None",
        "0.0",
    )
    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) is None


def test_one_pair_judged_twice_is_counted_once_at_the_newer_run() -> None:
    """The newer run read the day as it stands; counting both doubles one pair."""
    record = a_record()
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-1"),
        a_row(score=0.55, verdict=SameStoryVerdict.NO, run_id=f"{DATE}-2"),
    ]

    kept = counting.one_row_a_pair(rows)

    assert [row.run_id for row in kept] == [f"{DATE}-2"]
    counted = counting.count_day(record, rows, date=DATE)
    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count) == (0, 1)


def test_a_stamped_re_judge_beats_the_unstamped_rows_it_replaces() -> None:
    """Three rows, because two of them are what the old ordering decided between.

    `judged_by_run_id` is empty on every row written before the column existed,
    and an empty stamp sorts lowest - so a re-judge wins whichever digest run it
    is filed under. The two unstamped rows are still ordered by `run_id`, which
    is what this did before the column existed: drop that half of the pair and
    they would compare equal and the first one seen would win.
    """
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-2"),
        a_row(
            score=0.55,
            verdict=SameStoryVerdict.NO,
            run_id=f"{DATE}-1",
            judged_by_run_id=f"{DATE}-7",
        ),
        a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR, run_id=f"{DATE}-1"),
    ]

    kept = counting.one_row_a_pair(rows)

    assert [row.verdict for row in kept] == [SameStoryVerdict.NO]
    assert [row.run_id for row in counting.one_row_a_pair(rows[::2])] == [f"{DATE}-2"]


def a_metrics_row(*, shard: int, dealt: int = 2) -> ContentSimilarityJudgeMetrics:
    """One unit's instrument reading, with a funnel that closes."""
    return ContentSimilarityJudgeMetrics.model_validate(
        {
            "date": DATE,
            "run_id": A_COUNCIL_RUN,
            "shard": shard,
            "pairs_dealt": dealt,
            "pairs_read": dealt,
            "pairs_agreed": dealt,
            "pairs_unreadable": 0,
            "pairs_refused": 0,
            "pairs_abandoned": 0,
            "disagreement_rate": 0.0,
            "unclear_rate": 0.0,
            "first_token_margin_median": 0.5,
            "decode_seconds_total": 3.5 + shard,
            "decode_seconds_max": 2.0,
        }
    )


def a_night(root: Path, *, units: int) -> tuple[Path, Path, list[ContentSimilarityJudgeMetrics]]:
    """A night's units as they leave a runner: a verdict file and a shipped row each.

    The verdict files carry a header and no rows, because what these ask is what
    the collecting job does with what the units shipped rather than how a verdict
    is counted.
    """
    shipped = root / "shipped"
    judge_root = root / "judge"
    written = [a_metrics_row(shard=unit) for unit in range(units)]
    for unit, row in enumerate(written):
        metrics_sink.ship_judge_metrics(row, judge_id=JUDGE_ID, shard=unit, out_dir=shipped)
        assemble.write_atomic(
            judge_root / DATE / VERDICTS_DIRNAME / f"{unit}.csv",
            ",".join(StorySimilarityPair.csv_columns()) + "\n",
        )
    return shipped, judge_root, written


def test_the_row_the_collecting_job_lands_is_the_row_the_unit_shipped(tmp_path: Path) -> None:
    """Cell for cell, and the whole file is compared rather than a column of it.

    Both ends render through the contract's own columns, so a column one side
    knows about and the other does not shows up here as a line that is no longer
    the line the unit wrote - which is the one failure a spot check of two cells
    would walk straight past.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shipped, judge_root, written = a_night(tmp_path, units=settings.app.council.shards)

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        settings=settings,
        state_dir=state,
        judge_root=judge_root,
    )

    landed = read_text(ledger.content_similarity_judge_metrics_path(state, DATE)).splitlines()
    out_of_the_units = [
        read_text(shipped / JUDGE_ID / f"{unit}.csv").splitlines()
        for unit in range(len(written))
    ]

    assert report.metrics_appended == len(written)
    assert report.counted is True, "every unit reported, so the day is counted"
    assert landed[0] == ",".join(ContentSimilarityJudgeMetrics.csv_columns())
    assert landed[1:] == [unit[1] for unit in out_of_the_units]
    assert all(unit[0] == landed[0] for unit in out_of_the_units), (
        "the units and the store name their columns differently, so a row moved "
        "between them would be read one cell out of place"
    )


def test_the_readings_land_on_a_night_the_record_refused_to_count(tmp_path: Path) -> None:
    """A unit that ran and a day that cannot be counted are two different facts.

    Holding the readings back until the record accepts the day would delete the
    evidence of the first to record the second - and the night a unit dies is
    exactly the night an operator opens this store to find out why.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shipped, judge_root, written = a_night(tmp_path, units=1)

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        settings=settings,
        state_dir=state,
        judge_root=judge_root,
    )

    assert settings.app.council.shards > len(written), "a night short of a unit"
    assert (report.counted, report.held_reason) == (False, "shards_missing")
    assert report.metrics_appended == 1
    assert ledger.content_similarity_judge_metrics_path(state, DATE).exists()


def test_a_night_whose_units_shipped_nothing_appends_nothing(tmp_path: Path) -> None:
    """An empty upload is a night with no tenant, never a run to fail."""
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=tmp_path / "nothing-was-uploaded",
        settings=settings,
        state_dir=state,
        judge_root=tmp_path / "judge",
    )

    assert report.metrics_appended == 0
    assert not ledger.content_similarity_judge_metrics_path(state, DATE).exists()
