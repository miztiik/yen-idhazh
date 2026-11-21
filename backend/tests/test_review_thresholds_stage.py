"""Does the stage that reviews the thresholds read what the night filed, and file one honest row?

Every night here is laid down the way the collecting job finds it: a draw file, a verdict file
and a shipped reading for each unit that came back. The pairs go through `file_pair_verdicts`
into a temporary ledger, and the review reads them back and files its history.
Threshold arithmetic is tested in memory in `test_review_thresholds.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import exp, log, nextafter
from pathlib import Path
from typing import Final

import pytest
from support.judged_pairs import (
    CONFIG_VERSIONS,
    DATE,
    a_night_of_pairs,
    a_reading,
    a_saver,
    a_verdict_file,
)
from support.ledger import seed_compact_index, seed_compact_period
from support.paths import CONFIG_DIR
from support.threshold_nights import LOOKBACK, RULES, a_day, pairs_beside
from test_content_similarity_judge_ledger_reads import a_night_with_pool

from idhazh import atomic_write, ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_threshold_history,
    review_days,
)
from idhazh.content_similarity_judge.tenant import JUDGE_ID
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityDiagnosticsConfig
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_diagnostics import (
    JudgeProbabilityEvidence,
    JudgeProbabilityStatus,
    SampleStatus,
    ScoreDriftBaseline,
    ScoreDriftSource,
    ScoreDriftStatus,
    ScorePoolHistogram,
    UpperFitEvidence,
    diagnostic_text,
    read_diagnostic_text,
)
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
)
from idhazh.council import metrics_sink
from idhazh.similarity.score_pool_drift import drift_columns, score_pool_histogram
from idhazh.similarity.thresholds_in_force import thresholds_in_force
from idhazh.stages import file_pair_verdicts, review_thresholds

PAIRS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
HISTORY: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY
JUDGE_CONFIG: Final = judge_settings.load(CONFIG_DIR)

#: Two pairs in the fully similar end and one in the fully dissimilar end, so each lightly
#: sampled end has a pool and a handful of answers. Every slice held three times what was drawn.
ENDS: Final = [(0.95, "YES"), (0.96, "YES"), (0.40, "NO")]
DRIFT_DATE: Final = "2026-11-20"
DRIFT_RUN: Final = "2026-11-21-10"
RECIPE: Final = "b" * 64
FIT_DAY: Final = "2026-11-18"
FIT_RUN: Final = "2026-11-19-9"
EVALUATION_DAY: Final = "2026-11-19"
EVALUATION_RUN: Final = "2026-11-20-10"
EVALUATION_PAIRS: Final = (
    (0.94, "NO"),  # The training pair at 0.965, drawn again at a different score.
    (0.89, "UNCLEAR"),
    (0.965, "YES"),
    (0.88999, "YES"),
    (0.96501, "NO"),
    (0.92, ("YES", "NO")),
    (0.89, "YES"),
)


def _pool(counts: tuple[int, ...]) -> ScorePoolHistogram:
    return ScorePoolHistogram(stamp=RECIPE, edges=(-1.0, -0.5, 0.0, 0.5, 1.0), counts=counts)


def _history(
    date: str, run_id: str, pool: ScorePoolHistogram | None
) -> StorySimilarityThresholdHistoryRow:
    row = review_thresholds.build_threshold_row(
        date,
        run_id=run_id,
        window=(),
        history=(),
        draw_rows=a_night_of_pairs([(0.97, "YES")], answered=False, date=date, run_id=run_id),
        readings=(),
        expected_shards=1,
        rules=RULES,
        lookback_days_of_the_draw=LOOKBACK,
        versions=CONFIG_VERSIONS,
    )
    assert row is not None
    return row if pool is None else a_night_with_pool(row, pool)


def test_the_fixed_score_bins_include_the_endpoints_and_put_an_edge_in_the_higher_bin() -> None:
    pool = score_pool_histogram(
        (-1.0, nextafter(0.1, 0.0), 0.1, 1.0), bins=20, stamp=RECIPE
    )
    assert {index: n for index, n in enumerate(pool.counts) if n} == {0: 1, 10: 1, 11: 1, 19: 1}


def test_drift_uses_smoothed_psi_and_unsmoothed_binned_distances() -> None:
    target = _pool((8, 0, 0, 0))
    history = [_history("2026-11-19", "2026-11-20-8", _pool((0, 0, 0, 2)))]
    rules = ContentSimilarityDiagnosticsConfig(
        score_bins=4, score_baseline_days=1, score_psi_share_floor=0.125
    )
    cells = drift_columns(target, history, date=DRIFT_DATE, run_id=DRIFT_RUN, rules=rules)

    # Flooring makes the two occupied-bin shares 8/11 versus 1/11 for PSI.
    # The unsmoothed CDFs differ by 1 across the 1.5 between the outer midpoints.
    assert cells["score_psi"] == pytest.approx((14 / 11) * log(8))
    assert cells["score_wasserstein_distance"] == 1.5
    assert cells["score_ks_distance"] == 1.0

    empty = _pool((0, 0, 0, 0))
    assert drift_columns(empty, history, date=DRIFT_DATE, run_id=DRIFT_RUN, rules=rules) == {
        "score_pool_histogram": diagnostic_text(empty),
        "score_drift_status": ScoreDriftStatus.EMPTY_POOL,
    }


def test_drift_names_only_the_latest_earlier_run_per_compatible_day_and_pools_counts() -> None:
    low = _pool((8, 0, 0, 0))
    high = _pool((0, 0, 0, 4))
    target = _pool((16, 0, 0, 8))
    other_scorer = ScorePoolHistogram(stamp="c" * 64, edges=low.edges, counts=low.counts)
    other_edges = ScorePoolHistogram(
        stamp=RECIPE, edges=(-1.0, -0.25, 0.0, 0.25, 1.0), counts=high.counts
    )
    history = [
        _history("2026-11-19", "2026-11-21-9", low),
        _history("2026-11-19", "2026-11-21-2", high),
        _history("2026-11-19", "2026-11-20-99", high),
        _history("2026-11-19", DRIFT_RUN, high),  # a repair from this run
        _history("2026-11-19", "2026-11-21-11", high),
        _history("2026-11-18", "2026-11-20-2", low),
        _history("2026-11-18", "2026-11-20-3", other_scorer),
        _history("2026-11-17", "2026-11-19-1", other_edges),
        _history("2026-11-16", "2026-11-19-1", high),
        _history("2026-11-15", "2026-11-19-1", None),
        _history("2026-11-14", "2026-11-19-1", _pool((0, 0, 0, 0))),
        _history("2026-11-13", "2026-11-19-1", low),  # outside the lookback
    ]
    rules = ContentSimilarityDiagnosticsConfig(
        score_bins=4, score_baseline_days=2, score_baseline_lookback_days=6
    )
    cells = drift_columns(target, history, date=DRIFT_DATE, run_id=DRIFT_RUN, rules=rules)
    sources = (
        ScoreDriftSource(
            date="2026-11-19",
            run_id="2026-11-21-9",
            histogram_sha256=derive_text_digest(diagnostic_text(low)),
        ),
        ScoreDriftSource(
            date="2026-11-16",
            run_id="2026-11-19-1",
            histogram_sha256=derive_text_digest(diagnostic_text(high)),
        ),
    )
    assert cells["score_drift_status"] == ScoreDriftStatus.MEASURED
    assert cells["score_drift_baseline"] == diagnostic_text(
        ScoreDriftBaseline(sources=sources, required_days=2, share_floor=rules.score_psi_share_floor)
    )
    assert cells["score_psi"] == cells["score_wasserstein_distance"] == cells["score_ks_distance"] == 0

    rules.score_baseline_days = 3
    assert drift_columns(target, history, date=DRIFT_DATE, run_id=DRIFT_RUN, rules=rules) == {
        "score_drift_status": ScoreDriftStatus.INSUFFICIENT_BASELINE,
        "score_pool_histogram": diagnostic_text(target),
        "score_drift_baseline": diagnostic_text(
            ScoreDriftBaseline(sources=sources, required_days=3, share_floor=rules.score_psi_share_floor)
        ),
    }


@dataclass(frozen=True, slots=True)
class Night:
    """Where a night's files are laid, for the stage that reads them."""

    date: str
    run_id: str
    draw: Path
    shipped: Path
    verdicts: Path
    units: int
    filed_rows: tuple[StorySimilarityPairVerdict, ...] | None = ()


def lay_down_a_night(
    root: Path,
    state: Path,
    step: int,
    *,
    thresholds: tuple[float, float] | None = None,
    units: int = 2,
    lost: Sequence[int] = (),
    extra: Sequence[tuple[float, str]] = (),
    attempt: int = 0,
) -> Night:
    """A night as the collecting job finds it, with its pairs filed and its review still to run.

    The draw follows the thresholds the history in `state` puts it at, as the real draw does,
    unless `thresholds` says what it followed. The pairs are dealt to the units in turn, a lost
    unit leaves no verdict file and no shipped reading, and the draw file names every pair either
    way. `attempt` gives another run of the same night its own run id and the same pairs.
    """
    date = a_day(step)
    run_id = f"{date}-{9 + attempt}"
    if thresholds is None:
        followed = thresholds_in_force(
            load_threshold_history(
                state, review_days(date, config=JUDGE_CONFIG).threshold_history
            ),
            night=date,
            within_days=LOOKBACK,
            lower_start=RULES.lower_start,
            upper_start=RULES.upper_start,
        )
        thresholds = (followed.lower, followed.upper)
    lower, upper = thresholds
    pairs = [*pairs_beside(lower, upper, shift=0.0, night=step), *extra]
    drawn = a_night_of_pairs(
        pairs,
        answered=False,
        date=date,
        run_id=run_id,
        first_index=step * 1000,
        lower=lower,
        upper=upper,
    )
    judged = a_night_of_pairs(
        pairs, date=date, run_id=run_id, first_index=step * 1000, lower=lower, upper=upper
    )

    night = Night(
        date=date,
        run_id=run_id,
        draw=root / date / f"draw-{attempt}.csv",
        shipped=root / date / f"shipped-{attempt}",
        verdicts=root / date / f"verdicts-{attempt}",
        units=units,
    )
    atomic_write.write_atomic(
        night.draw,
        a_verdict_file(
            [row.model_copy(update={"work_part_index": i % units}) for i, row in enumerate(drawn)]
        ),
    )
    for unit in range(units):
        if unit in lost:
            continue
        rows = [
            row.model_copy(update={"work_part_index": unit}) for row in judged[unit::units]
        ]
        metrics_sink.ship_judge_metrics(
            a_reading(shard=unit, dealt=len(rows), date=date, run_id=run_id),
            judge_id=JUDGE_ID,
            name=str(unit),
            out_dir=night.shipped,
        )
        atomic_write.write_atomic(
            night.verdicts / f"{date}-{JUDGE_ID}-{unit:02d}.csv", a_verdict_file(rows)
        )
    return _file_night(night, state)


def _file_night(night: Night, state: Path, *, attempt: int = 1) -> Night:
    filed = file_pair_verdicts.stage_file_pair_verdicts(
        night.date,
        run_id=night.run_id,
        judge_id=JUDGE_ID,
        shipped_root=night.shipped,
        verdicts_dir=night.verdicts,
        identity=_saver(night.run_id, attempt=attempt),
        expected_shards=night.units,
        state_dir=state,
    )
    return replace(night, filed_rows=filed.filed_rows)


def _saver(run_id: str, *, attempt: int) -> WriterIdentity:
    return a_saver(run_id).model_copy(update={"attempt": attempt})


def review(night: Night, state: Path, *, attempt: int = 1) -> review_thresholds.ReviewReport:
    return review_thresholds.stage_review_thresholds(
        night.date,
        run_id=night.run_id,
        judge_id=JUDGE_ID,
        shipped_root=night.shipped,
        draw_path=night.draw,
        filed_rows=night.filed_rows,
        identity=_saver(night.run_id, attempt=attempt),
        expected_shards=night.units,
        state_dir=state,
        config_dir=CONFIG_DIR,
    )


def settle_a_night(
    root: Path,
    state: Path,
    step: int,
    *,
    units: int = 2,
    lost: Sequence[int] = (),
    extra: Sequence[tuple[float, str]] = (),
    attempt: int = 0,
) -> StorySimilarityThresholdHistoryRow:
    """Lay a night down and review it, and hand back the row it filed."""
    night = lay_down_a_night(
        root, state, step, units=units, lost=lost, extra=extra, attempt=attempt
    )
    report = review(night, state)
    assert report.row is not None and report.filed
    return report.row


def test_a_night_that_dealt_no_pair_files_no_row(tmp_path: Path) -> None:
    """No draw rows and no judged rows is a night nothing ran, and a missing row is how it reads."""
    state, draw = tmp_path / "state", tmp_path / "draw.csv"
    atomic_write.write_atomic(draw, a_verdict_file([]))
    night = Night(DATE, f"{DATE}-9", draw, tmp_path / "nothing-shipped", tmp_path / "none", 2)

    report = review(night, state)

    assert (report.row, report.filed) == (None, False)
    assert not ledger.raw_root(state, HISTORY).exists()


def test_a_night_whose_every_pair_was_lost_files_a_row_that_says_so(tmp_path: Path) -> None:
    """The draw dealt pairs and both units died: no evidence, both thresholds held, pools kept.

    The pair-verdicts ledger holds nothing of the night, so the size of each lightly sampled end
    comes from the draw file, and what scored the night comes from its rows. The row is what
    tells this night from one that dealt nothing.
    """
    state = tmp_path / "state"

    row = settle_a_night(tmp_path, state, 0, lost=(0, 1), extra=ENDS)

    assert (row.runners_expected, row.runners_reported, row.pairs_dealt) == (2, 0, 0)
    assert row.sample_status is SampleStatus.MEASURED
    assert (row.pairs_drawn, row.pairs_returned) == (83, 0)
    assert row.lower_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert row.upper_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert (row.lower_threshold_before, row.lower_threshold_after) == (0.70, 0.70)
    assert (row.lower_usable_pairs_used, row.lower_estimate, row.lower_curve_steepness) == (0, None, None)
    assert (row.above_upper_pairs_available, row.above_upper_pairs_usable) == (6, 0)
    assert (row.below_lower_pairs_available, row.below_lower_pairs_usable) == (3, 0)
    assert (row.above_upper_same_story_estimated, row.below_lower_different_story_estimated) == (
        None,
        None,
    )
    assert row.scorer_model == "all-minilm-l6-v2-quantized" and row.judge_model is None
    assert load_pair_verdicts(state, [a_day(0)]) == []


def test_a_night_whose_units_reported_files_the_totals_of_the_units_that_did(tmp_path: Path) -> None:
    """Both units back: the ends' pools and weighted totals, and every reading summed.

    The fully similar end held 6 pairs and the draw took 2, both judged the same story, so each
    stands for 3 and the end is estimated at 6. The fully dissimilar end held 3, took one, and
    is estimated at 3. One unit lost leaves its readings out of every sum, so the four endings
    still add up to the pairs dealt, and `runners_reported` says one was lost.
    """
    both = settle_a_night(tmp_path / "both", tmp_path / "both-state", 0, extra=ENDS)
    one = settle_a_night(tmp_path / "one", tmp_path / "one-state", 0, extra=ENDS, lost=(1,))

    assert (both.above_upper_pairs_available, both.above_upper_pairs_usable) == (6, 2)
    assert both.above_upper_same_story_estimated == pytest.approx(6.0)
    assert both.below_lower_different_story_estimated == pytest.approx(3.0)
    assert (both.runners_reported, both.pairs_dealt) == (2, 83)
    assert both.decode_seconds_total == pytest.approx(3.5 + 4.5)
    assert both.decode_seconds_slowest_runner == pytest.approx(4.5)
    assert (one.runners_expected, one.runners_reported, one.pairs_dealt) == (2, 1, 42)
    assert one.decode_seconds_total == pytest.approx(3.5)
    assert one.pairs_agreed == one.pairs_dealt


def test_a_sample_shard_mismatch_does_not_change_the_fit_or_runner_readings(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0)
    draw = review_thresholds._draw_rows(night.draw)
    draw[0] = draw[0].model_copy(update={"work_part_index": 1})
    atomic_write.write_atomic(night.draw, a_verdict_file(draw))

    report = review(night, state)

    (row,) = load_threshold_history(state, [night.date])
    assert report.filed and report.row == row
    assert row.sample_status is SampleStatus.DRAW_MISMATCH
    assert row.pairs_drawn == 80 and row.pairs_returned is None
    assert row.slice_outcomes is None
    assert row.evaluated_cutoff is row.cutoff_brier_score is None
    assert (row.lower_usable_pairs_used, row.upper_usable_pairs_used) == (40, 40)
    assert (row.runners_reported, row.pairs_dealt) == (2, 80)
    assert f"run={night.run_id} status=draw_mismatch reason=filed_shard_mismatch" in caplog.text


def test_tonights_pairs_are_read_even_when_the_day_was_recorded_as_quiet(tmp_path: Path) -> None:
    """A night the judge repairs is a day the gardener already recorded as empty.

    The door serves such a day from the record and never opens the raw files filed after it, so
    the review reads tonight's rows raw and the nights before it through the door.
    """
    state = tmp_path / "state"
    day = a_day(3)
    seed_compact_index(
        state, PAIRS, Period.DAILY, [CompactEntry(covers=day, rows=0, bytes=0, state=EntryState.EMPTY)]
    )
    seed_compact_index(state, PAIRS, Period.MONTHLY, [])
    seed_compact_index(state, PAIRS, Period.YEARLY, [])

    row = settle_a_night(tmp_path, state, 3)

    assert load_pair_verdicts(state, [day]) == [], "the door still serves the day as empty"
    assert (row.lower_usable_pairs_used, row.upper_usable_pairs_used) == (40, 40)
    assert row.lower_nights_used == 1


def test_two_runs_of_one_night_start_from_the_same_thresholds_and_count_each_pair_once(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    for step in range(3):
        settle_a_night(tmp_path, state, step)

    first = settle_a_night(tmp_path, state, 3)
    again = settle_a_night(tmp_path, state, 3, attempt=1)

    assert (again.lower_threshold_before, again.upper_threshold_before) == (
        first.lower_threshold_before,
        first.upper_threshold_before,
    )
    assert (again.lower_usable_pairs_used, again.upper_usable_pairs_used) == (160, 160)
    assert again.lower_nights_used == first.lower_nights_used == 4
    assert [row.run_id for row in load_threshold_history(state, [a_day(3)])] == [
        first.run_id,
        again.run_id,
    ]


def test_a_reading_that_names_another_night_stops_the_review_and_files_nothing(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0)
    metrics_sink.ship_judge_metrics(
        a_reading(shard=5, dealt=1, date=a_day(9), run_id=f"{a_day(9)}-9"),
        judge_id=JUDGE_ID,
        name="5",
        out_dir=night.shipped,
    )

    with pytest.raises(ValueError, match="another night's artifact"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()


def test_a_draw_file_that_is_missing_stops_the_review_and_files_nothing(tmp_path: Path) -> None:
    """A missing draw is an incomplete artifact, and would file every pool as empty."""
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0)
    night.draw.unlink()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()
    assert len(load_pair_verdicts(state, [a_day(0)])) == 80


def test_a_draw_that_followed_thresholds_the_history_does_not_show_stops_the_review(
    tmp_path: Path,
) -> None:
    """A checkout missing the history would reset both thresholds to the starts without a word.

    The draw followed 0.66 and 0.93, and this checkout's history is empty, so it works them out
    as the starts. The review refuses, and the night keeps its pair rows and has no threshold
    row, which the scheduler reads as a night done.
    """
    state = tmp_path / "state"
    night = lay_down_a_night(tmp_path, state, 0, thresholds=(0.66, 0.93))

    with pytest.raises(ValueError, match="not the history the draw read"):
        review(night, state)

    assert not ledger.raw_root(state, HISTORY).exists()
    assert len(load_pair_verdicts(state, [a_day(0)])) == 80


def _file_calibration_night(
    root: Path,
    *,
    day: str,
    run_id: str,
    pairs: Sequence[tuple[float, str | tuple[str, str]]],
    first_index: int,
    attempt: int = 1,
    returned: tuple[int, ...] | None = None,
) -> Night:
    work = root / day / str(attempt)
    night = Night(day, run_id, work / "draw.csv", work / "shipped", work / "verdicts", 1)
    draw = a_night_of_pairs(
        pairs, date=day, run_id=run_id, first_index=first_index, answered=False
    )
    judged = a_night_of_pairs(pairs, date=day, run_id=run_id, first_index=first_index)
    atomic_write.write_atomic(night.draw, a_verdict_file(draw))
    returned_rows = judged if returned is None else [judged[index] for index in returned]
    if returned_rows:
        atomic_write.write_atomic(night.verdicts / "unit.csv", a_verdict_file(returned_rows))
    return _file_night(night, root / "state", attempt=attempt)


def prior_fit_replay(root: Path) -> tuple[Night, StorySimilarityThresholdHistoryRow, Night]:
    """File a real fit, pack its day, and file the pairs that the later run can evaluate."""
    state = root / "state"
    source = _file_calibration_night(
        root,
        day=FIT_DAY,
        run_id=FIT_RUN,
        pairs=((0.80, "YES"), (0.94, ("YES", "NO")), (0.89, "NO"), (0.92, "UNCLEAR"), (0.965, "YES")),
        first_index=0,
    )
    result = review(source, state)
    assert result.filed and result.row is not None
    source_row = result.row
    packed = seed_compact_period(
        state,
        HISTORY,
        StorySimilarityThresholdHistoryRow,
        Period.DAILY,
        FIT_DAY,
        [(FIT_DAY, FIT_RUN, source_row)],
        producer=review_thresholds.PRODUCER,
    )
    seed_compact_index(
        state,
        HISTORY,
        Period.DAILY,
        [CompactEntry(covers=FIT_DAY, state=EntryState.PACKED, rows=1, bytes=packed.stat().st_size)],
    )
    for period in (Period.MONTHLY, Period.YEARLY):
        seed_compact_index(state, HISTORY, period, [])
    target = _file_calibration_night(
        root, day=EVALUATION_DAY, run_id=EVALUATION_RUN, pairs=EVALUATION_PAIRS, first_index=4
    )
    return source, source_row, target


def test_a_packed_upper_fit_scores_only_fresh_agreed_pairs_in_the_exact_attempt(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    source, source_row, target = prior_fit_replay(tmp_path)
    result = review(target, state)
    assert result.filed and result.row is not None
    packed_source, evaluated = load_threshold_history(state, [FIT_DAY, EVALUATION_DAY])
    assert packed_source == source_row
    assert evaluated == result.row

    evidence = packed_source.upper_fit_evidence
    assert evidence is not None
    fit = read_diagnostic_text(evidence, column="upper_fit_evidence", model=UpperFitEvidence)
    assert source.filed_rows is not None and target.filed_rows is not None
    trained = source.filed_rows[2:]
    assert (fit.low, fit.high, fit.yes, fit.judge_temperature) == (0.89, 0.965, 1, 0.0)
    assert fit.meaning_stamp.prompt_digest == trained[0].prompt_digest
    assert fit.pair_keys == tuple(sorted(row.pair_key for row in trained))
    assert len(fit.pair_keys) == packed_source.upper_usable_pairs_used == 3
    overlap = target.filed_rows[0]
    assert overlap.pair_key == trained[-1].pair_key
    assert overlap.similarity_score != trained[-1].similarity_score
    assert packed_source.judge_probability_status is JudgeProbabilityStatus.NO_REFERENCE_FIT

    reference = evaluated.judge_probability_evidence
    assert reference is not None
    cohort = read_diagnostic_text(
        reference, column="judge_probability_evidence", model=JudgeProbabilityEvidence
    )
    assert (cohort.source_date, cohort.source_run_id) == (FIT_DAY, FIT_RUN)
    assert (cohort.pairs, cohort.yes, cohort.bins) == (3, 2, JUDGE_CONFIG.diagnostics.probability_bins)
    assert evaluated.judge_probability_status is JudgeProbabilityStatus.MEASURED
    intercept, slope = packed_source.upper_curve_intercept, packed_source.upper_curve_steepness
    assert intercept is not None and slope is not None
    low = 1 / (1 + exp(-(intercept + slope * 0.89)))
    high = 1 / (1 + exp(-(intercept + slope * 0.965)))
    assert high - low > 1 / cohort.bins  # Distinct bins; the two at low share a bin.
    assert evaluated.judge_probability_brier_score == pytest.approx(
        (low**2 + (1 - low)**2 + (1 - high)**2) / 3
    )
    assert evaluated.judge_probability_baseline_brier_score == pytest.approx(1 / 3)
    assert evaluated.judge_probability_ece == pytest.approx((2 * abs(low - 0.5) + 1 - high) / 3)

    retry = _file_calibration_night(
        tmp_path,
        day=EVALUATION_DAY,
        run_id=EVALUATION_RUN,
        pairs=EVALUATION_PAIRS,
        first_index=4,
        attempt=2,
        returned=(1,),
    )
    shorter = review(retry, state, attempt=2)
    assert shorter.filed and shorter.row is not None
    (saved,) = load_threshold_history(state, [EVALUATION_DAY])
    assert saved == shorter.row and saved.judge_probability_evidence is not None
    retried = read_diagnostic_text(
        saved.judge_probability_evidence, column="judge_probability_evidence",
        model=JudgeProbabilityEvidence,
    )
    assert (retried.fit_sha256, retried.pairs, retried.yes) == (cohort.fit_sha256, 1, 0)
    assert saved.judge_probability_brier_score == pytest.approx(low**2)
    assert saved.judge_probability_baseline_brier_score == pytest.approx(1 / 9)
