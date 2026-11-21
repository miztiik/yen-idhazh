"""Do threshold history readings agree with their evidence, including after compaction?"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError, create_model
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ChangelogEntry, Contract, ServerJob, compact_json
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_diagnostics import (
    MAX_FIT_PAIRS,
    MAX_SAFE_INTEGER,
    SliceOutcomes,
    diagnostic_text,
)
from idhazh.contracts.story_similarity_score_pool import ContentSimilarityScorePool
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
    ThresholdMoveLimit,
)
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.period_inputs import paths_for_task
from idhazh.gardener.tasks import compaction
from idhazh.ledger.parquet import read_footer_schema

pytestmark = pytest.mark.contract

FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-threshold-history-row"
    / "a-night-that-held-both-thresholds.json"
)

SIDES = ("lower", "upper")

#: Where each bound stood in the fixture, and why it held: the lower gap sat inside the ignore
#: range, and the upper gap sat beyond it for the first night of two.
BEFORE = {"lower": 0.7, "upper": 0.93}
HELD_FOR = {"lower": "within_ignore_range", "upper": "waiting_for_second_night"}

#: The night's own columns when nothing was judged: no model, no readings, no evidence.
NOTHING_JUDGED: dict[str, Any] = {
    "judge_model": None,
    "judge_policy_version": None,
    "above_upper_pairs_available": 0,
    "above_upper_pairs_usable": 0,
    "above_upper_same_story_estimated": None,
    "below_lower_pairs_available": 0,
    "below_lower_pairs_usable": 0,
    "below_lower_different_story_estimated": None,
    "runners_reported": 0,
    "pairs_dealt": 0,
    "pairs_valid": 0,
    "pairs_agreed": 0,
    "pairs_unreadable": 0,
    "pairs_refused": 0,
    "pairs_abandoned": 0,
    "disagreement_rate": None,
    "unclear_rate": None,
    "decode_seconds_total": None,
    "decode_seconds_slowest_runner": None,
    "canary_answers": None,
}


def a_night(**changes: Any) -> dict[str, Any]:
    """The committed night, where both thresholds held, as a payload with some cells changed."""
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    return payload | changes


def on(side: str, **changes: Any) -> dict[str, Any]:
    """These per-threshold cells, named for one bound."""
    return {f"{side}_{name}": value for name, value in changes.items()}


def without_a_fit(side: str) -> dict[str, Any]:
    """One bound with no evidence read and no curve fitted, as a night with no data leaves it."""
    return on(
        side,
        nights_used=0,
        usable_pairs_used=0,
        window_first_date=None,
        curve_intercept=None,
        curve_steepness=None,
        estimate=None,
        gap=None,
        nights_beyond_ignore_range=0,
        held_because="not_enough_evidence",
        move=0.0,
        move_limited_by="none",
    )


def a_move(side: str, **changes: Any) -> dict[str, Any]:
    """One bound that moved inward by the narrowing step, with the gap and nights behind it."""
    before = BEFORE[side]
    sign = 1 if side == "lower" else -1
    moved = on(
        side,
        estimate=round(before + sign * 0.0135, 4),
        gap=sign * 0.0135,
        nights_beyond_ignore_range=2,
        held_because="none",
        move_limited_by="narrowing_step",
        move=sign * 0.005,
        threshold_after=round(before + sign * 0.005, 3),
    )
    return moved | on(side, **changes)


def refused(**changes: Any) -> str:
    """The refusal a payload with these cells changed draws, as one string."""
    with pytest.raises(ValidationError) as refusal:
        StorySimilarityThresholdHistoryRow.model_validate(a_night(**changes))
    return str(refusal.value)


def accepted(**changes: Any) -> StorySimilarityThresholdHistoryRow:
    return StorySimilarityThresholdHistoryRow.model_validate(a_night(**changes))


@pytest.mark.parametrize("side", SIDES)
def test_a_held_threshold_has_not_moved(side: str) -> None:
    """A move, a different threshold after, or a limit on a held bound is a row that lies."""
    before = BEFORE[side]
    refusals = {
        f"was held ({HELD_FOR[side]})": on(side, move=0.01, threshold_after=before + 0.01),
        "move is 0.0, and the threshold went from": on(side, threshold_after=before + 0.01),
        "no move was made": on(side, move_limited_by="widening_step"),
    }

    for message, changes in refusals.items():
        assert message in refused(**changes)


@pytest.mark.parametrize("side", SIDES)
def test_a_threshold_that_moved_shows_its_move_or_the_limit_that_cut_it_to_nothing(
    side: str,
) -> None:
    moved = accepted(**a_move(side))
    clamped = accepted(
        **a_move(side, move=0.0, move_limited_by="lowest_allowed", threshold_after=BEFORE[side])
    )

    assert getattr(moved, f"{side}_held_because") is ThresholdHoldReason.NONE
    assert getattr(clamped, f"{side}_move_limited_by") is ThresholdMoveLimit.LOWEST_ALLOWED
    assert "the row carries a move" in refused(
        **a_move(side, move=0.0, move_limited_by="none", threshold_after=BEFORE[side])
    )


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"gap": 0.02}, "gap is 0.02"),
        ({"curve_intercept": None}, "all on the row or all absent"),
        ({"curve_steepness": 0.0}, "greater than 0"),
        ({"curve_steepness": -3.0}, "greater than 0"),
        ({"held_because": "fit_failed"}, "fit failed, so the row carries no curve from it"),
    ],
)
def test_the_curve_is_all_present_or_all_absent_and_a_failed_fit_leaves_none(
    side: str, changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**on(side, **changes))


@pytest.mark.parametrize("side", SIDES)
def test_a_hold_for_a_gap_needs_a_curve_and_a_hold_for_thin_evidence_does_not(side: str) -> None:
    no_curve = on(
        side,
        curve_intercept=None,
        curve_steepness=None,
        estimate=None,
        gap=None,
        nights_beyond_ignore_range=0,
    )

    assert "comes from a gap" in refused(**no_curve)
    for reason in ("not_enough_evidence", "fit_failed"):
        row = accepted(**no_curve | on(side, held_because=reason))
        assert getattr(row, f"{side}_estimate") is None
    thin_but_fitted = accepted(**on(side, held_because="not_enough_evidence"))
    assert getattr(thin_but_fitted, f"{side}_estimate") is not None


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize(
    "changes", [{"window_first_date": None}, {"nights_used": 0, "usable_pairs_used": 0}]
)
def test_the_evidence_window_names_a_date_exactly_when_something_was_read(
    side: str, changes: dict[str, Any]
) -> None:
    assert "starts on a date exactly when" in refused(**on(side, **changes))
    assert getattr(accepted(**without_a_fit(side)), f"{side}_window_first_date") is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (on("lower", nights_beyond_ignore_range=1), "no night stands beyond it"),
        (on("upper", nights_beyond_ignore_range=0), "at least tonight stands beyond it"),
        (
            without_a_fit("lower") | on("lower", nights_beyond_ignore_range=2),
            "no gap, so no night stands beyond",
        ),
    ],
)
def test_the_nights_beyond_the_ignore_range_follow_the_hold(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"lower_share_level": 0.9, "upper_share_level": 0.05},
        on("upper", threshold_before=0.7, threshold_after=0.7, estimate=0.6895),
    ],
)
def test_the_lower_bound_stays_below_the_upper_one(changes: dict[str, Any]) -> None:
    """Two sets of columns filed the wrong way round are refused rather than read."""
    assert "is not below the upper bound's" in refused(**changes)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pairs_dealt": 151}, "the runners account for 150"),
        ({"pairs_agreed": 148}, "pairs_agreed is 148 over 147 valid"),
        ({"runners_reported": 6}, "6 runners reported of 5 expected"),
        ({"disagreement_rate": 0.5}, "disagreement_rate is the share of valid pairs"),
        ({"unclear_rate": None}, "unclear_rate is empty exactly when no pair agreed"),
        ({"above_upper_pairs_usable": 413}, "only 412 were available"),
        ({"above_upper_same_story_estimated": None}, "empty exactly when no pair there"),
        ({"below_lower_different_story_estimated": 1531.0}, "only 1530 pairs were available"),
        ({"below_lower_pairs_usable": 0}, "empty exactly when no pair there"),
    ],
)
def test_the_night_s_counts_close_and_its_rates_follow_them(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


def test_a_night_that_lost_a_runner_still_closes_over_the_runners_that_reported() -> None:
    row = accepted(
        runners_reported=4,
        pairs_dealt=120,
        pairs_valid=118,
        pairs_agreed=111,
        pairs_refused=2,
        disagreement_rate=7 / 118,
    )

    assert (row.runners_expected, row.runners_reported) == (5, 4)


def test_a_night_that_judged_nothing_is_still_a_row() -> None:
    """A night with no model and no evidence degrades to a row of nothing, and is not refused."""
    row = accepted(**NOTHING_JUDGED | without_a_fit("lower") | without_a_fit("upper"))

    assert row.judge_model is None and row.pairs_dealt == 0
    assert row.lower_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "{}",
        '[["NO","NO",0.9,0.9,800,0]]',
        '{"same-1": ["YES","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812]}',
        '{"same-1":["MAYBE","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",1.5,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,-1,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812,null]}',
        '{"same-1":["YES","YES",0.98,0.99,812,5]}',
        '{"Same One":["YES","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812,2],"different-1":["NO","NO",0.9,0.9,800,3]}',
    ],
)
def test_canary_answers_are_compact_json_of_six_typed_cells_from_an_expected_runner(
    text: str,
) -> None:
    assert "canary_answers" in refused(canary_answers=text)


def test_a_missing_reading_is_a_null_cell_and_no_canary_is_none() -> None:
    refused_pair = '{"unclear-1":[null,null,null,null,null,1]}'

    assert accepted(canary_answers=refused_pair).canary_answers == refused_pair
    assert accepted(canary_answers=None).canary_answers is None


@pytest.mark.parametrize(
    "text", ["not json", "{}", '{"judges/content-similarity-judge.json": "2026-11-18"}']
)
def test_config_versions_is_one_compact_json_object(text: str) -> None:
    assert "config_versions" in refused(config_versions=text)


def _sample(**changes: object) -> dict[str, Any]:
    section = {
        "bucket": "fully_dissimilar",
        "low": -1,
        "high": 0.7,
        "available": 5,
        "drawn": 4,
        "yes": 1,
        "no": 1,
        "unclear": 0,
        "split": 1,
        "refused": 0,
    } | changes
    return {
        "sample_status": "measured",
        "pairs_drawn": 4,
        "pairs_returned": 3,
        "slice_outcomes": compact_json({"slices": [section]}).removesuffix("\n"),
        "evaluated_cutoff": 0.87,
        "sample_tp": 0,
        "sample_fp": 0,
        "sample_fn": 1,
        "sample_tn": 1,
    }


def test_sample_records_a_real_zero_separately_from_an_unavailable_join() -> None:
    assert accepted(**_sample()).sample_fn == 1
    outcomes = SliceOutcomes.model_validate_json(_sample(yes=0, no=0, split=0)["slice_outcomes"])
    measured = accepted(
        **(
            _sample()
            | {
                "pairs_returned": 0,
                "sample_fn": 0,
                "sample_tn": 0,
                "slice_outcomes": diagnostic_text(outcomes),
            }
        )
    )
    assert measured.pairs_returned == 0 and measured.cutoff_brier_score is None
    for status in ("not_filed", "draw_mismatch"):
        assert accepted(sample_status=status).pairs_drawn is None
        row = accepted(sample_status=status, pairs_drawn=4)
        assert row.pairs_drawn == 4 and row.pairs_returned is None and row.slice_outcomes is None
        assert "sample_status" in refused(sample_status=status, pairs_returned=0)


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"pairs_returned": 2}, "drawn and returned totals"),
        ({"sample_tn": 0, "sample_tp": 1}, "YES and NO totals"),
        ({"sample_precision": 0}, "supporting pairs"),
        ({"pairs_drawn": True}, "pairs_drawn"),
        ({"sample_tp": MAX_SAFE_INTEGER + 1}, "sample_tp"),
        ({"evaluated_cutoff": float("nan")}, "evaluated_cutoff"),
    ],
)
def test_sample_counts_and_scores_need_matching_evidence(
    change: dict[str, object], problem: str
) -> None:
    assert problem in refused(**(_sample() | change))


def test_slice_text_refuses_extra_cells_bad_counts_and_overlapping_edges() -> None:
    sample = _sample()
    text = sample["slice_outcomes"]
    section = json.loads(text)["slices"][0]
    assert "compact JSON" in refused(**(sample | {"slice_outcomes": text + "\n"}))
    assert "article" in refused(**_sample(article="not a diagnostic field"))
    assert "returned <= drawn" in refused(**_sample(yes=5))
    overlap = compact_json({"slices": [section, section | {"low": 0.6, "high": 0.8}]})
    assert "must not overlap" in refused(**(sample | {"slice_outcomes": overlap.rstrip()}))


def _histogram(*counts: int) -> str:
    return compact_json(
        {
            "stamp": "b" * 64,
            "edges": [-1.0, 0.0, 1.0],
            "counts": list(counts),
        }
    ).removesuffix("\n")


def _baseline(*dates: str, required_days: int = 1) -> str:
    return compact_json(
        {
            "sources": [
                {"date": day, "run_id": f"{day}-1", "histogram_sha256": "a" * 64} for day in dates
            ],
            "required_days": required_days,
            "share_floor": 1e-6,
        }
    ).removesuffix("\n")


def _drift(**changes: object) -> dict[str, Any]:
    return {
        "score_drift_status": "measured",
        "score_pool_histogram": _histogram(3, 5),
        "score_drift_baseline": _baseline("2026-11-16"),
        "score_psi": 0.0,
        "score_wasserstein_distance": 0.0,
        "score_ks_distance": 0.0,
    } | changes


def test_only_a_supported_drift_comparison_can_record_zero_distances() -> None:
    assert accepted(score_drift_status="no_histogram").score_pool_histogram is None
    assert (
        accepted(score_drift_status="empty_pool", score_pool_histogram=_histogram(0, 0)).score_psi
        is None
    )
    assert accepted(**_drift()).score_psi == 0.0
    assert "all three drift distances" in refused(**_drift(score_ks_distance=None))
    assert "baseline source coverage" in refused(**_drift(score_drift_baseline=_baseline()))
    assert "distinct UTC digest dates" in refused(
        **_drift(score_drift_baseline=_baseline("2026-11-16", "2026-11-16", required_days=2))
    )
    assert "precede the digest date" in refused(
        **_drift(score_drift_baseline=_baseline("2026-11-17"))
    )
    assert "histogram's total" in refused(**_drift(score_pool_histogram=_histogram(0, 0)))
    assert "score_wasserstein_distance" in refused(**_drift(score_wasserstein_distance=2.1))


def test_score_pool_transport_checks_the_attempt_and_histogram_shape() -> None:
    pool = {
        "date": "2026-11-17",
        "run_id": "2026-11-18-1",
        "attempt": 2,
        "histogram": json.loads(_histogram(3, 5)),
    }
    assert ContentSimilarityScorePool.model_validate(pool).histogram.counts == (3, 5)
    with pytest.raises(ValidationError, match="attempt"):
        ContentSimilarityScorePool.model_validate(pool | {"attempt": 0})
    with pytest.raises(ValidationError, match="one count per edge interval"):
        ContentSimilarityScorePool.model_validate(pool | {"histogram": json.loads(_histogram(3))})
    with pytest.raises(ValidationError, match="increase strictly"):
        ContentSimilarityScorePool.model_validate(
            pool | {"histogram": pool["histogram"] | {"edges": [-1, -1, 1]}}
        )


def test_upper_fit_needs_the_exact_membership_of_a_recorded_curve() -> None:
    fit = {
        "meaning_stamp": {
            "judge_model": "test-judge",
            "prompt_digest": "1" * 64,
            "grammar_digest": "2" * 64,
            "scorer_model": "test-scorer",
            "cosine_weight": 1,
            "judge_policy_version": "2026-11-05",
        },
        "judge_temperature": 0,
        "pair_keys": ["a" * 64, "b" * 64],
        "low": 0.8,
        "high": 0.8,
        "yes": 1,
    }
    text = compact_json(fit).removesuffix("\n")
    assert accepted(upper_usable_pairs_used=2, upper_fit_evidence=text).upper_fit_evidence == text
    assert "curve and its usable pairs" in refused(upper_fit_evidence=text)
    for keys, problem in (
        (["a" * 64] * 2, "sorted and unique"),
        ([f"{i:064x}" for i in range(MAX_FIT_PAIRS + 1)], "pair_keys"),
    ):
        assert problem in refused(
            upper_fit_evidence=compact_json(fit | {"pair_keys": keys}).removesuffix("\n")
        )


def test_probability_keeps_the_reference_but_no_scores_when_no_pair_qualified() -> None:
    reference = {
        "source_date": "2026-11-16",
        "source_run_id": "2026-11-17-1",
        "fit_sha256": "a" * 64,
        "pairs": 0,
        "yes": 0,
        "bins": 10,
    }
    text = compact_json(reference).removesuffix("\n")
    no_pairs = {"judge_probability_status": "no_eligible_pairs", "judge_probability_evidence": text}
    assert accepted(judge_probability_status="no_reference_fit").judge_probability_evidence is None
    assert accepted(**no_pairs).judge_probability_evidence == text
    assert "for measured probability" in refused(**no_pairs, judge_probability_ece=0)
    assert "evaluation pair count" in refused(
        **(no_pairs | {"judge_probability_status": "measured"})
    )
    scores = {
        "judge_probability_status": "measured",
        "judge_probability_brier_score": 0.2,
        "judge_probability_baseline_brier_score": 0.25,
        "judge_probability_ece": 0.1,
    }
    measured = compact_json(reference | {"pairs": 2, "yes": 1}).removesuffix("\n")
    assert accepted(**scores, judge_probability_evidence=measured).judge_probability_ece == 0.1
    later = compact_json(reference | {"source_date": "2026-11-18"}).removesuffix("\n")
    assert "earlier digest" in refused(**(no_pairs | {"judge_probability_evidence": later}))


def test_canary_kappa_needs_every_expected_pair_and_a_nonzero_chance_denominator() -> None:
    expected = '{"different-1":"NO","same-1":"YES"}'
    complete = accepted(canary_expectations=expected, canary_kappa_pairs=2, canary_kappa=1)
    assert complete.canary_kappa == 1
    missing = '{"different-1":"NO","same-1":"YES","unreturned-1":"UNCLEAR"}'
    assert accepted(canary_expectations=missing, canary_kappa_pairs=2).canary_kappa is None
    assert "must count expected pairs" in refused(canary_expectations=missing, canary_kappa_pairs=3)
    assert "complete agreeing answers" in refused(
        canary_expectations=missing, canary_kappa_pairs=2, canary_kappa=1
    )
    assert "nonzero denominator" in refused(
        canary_expectations='{"same-1":"YES"}', canary_kappa_pairs=1, canary_kappa=1
    )


class _LegacyHistoryShape(Contract):
    """Base stamp for the projected Parquet writer, with columns taken from the legacy fixture."""

    __schema_stem__: ClassVar[str] = "story-similarity-threshold-history-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-18",
            change="Read the original night.",
            why="Write one Parquet file with no diagnostic columns.",
        ),
    )


def _file_history(state: Path, row: Contract, *, day: str, run_id: str, attempt: int) -> Path:
    (path,) = ledger.persist(
        state,
        [row],
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
        covers=day,
        identity=WriterIdentity(
            run_id=run_id,
            attempt=attempt,
            job=ServerJob.SAVE_COUNCIL_RESULTS,
            shard=0,
            producer="tests.threshold_history",
            git_sha="a" * 40,
        ),
        fmt=Format.PARQUET,
    )
    return path


def _compact_history_day(root: Path, day: str) -> Path:
    task = "compact-content-similarity-judge-threshold-history"
    policy = CompactionPolicy.model_validate_json(
        read_text(CONFIG_DIR / "gardener" / f"{task}.json")
    )
    # This new test tree has no established yearly index to expire.
    policy = policy.model_copy(update={"yearly_prune_enable": False})
    today = date.fromisoformat(day) + timedelta(days=policy.compact_after_days + 1)
    state = root / ledger.STATE_DIRNAME
    outcome = compaction.run(
        TaskContext(
            state_dir=state,
            repo_root=root,
            today=today,
            policy=policy,
            run_id=f"{today}-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            git_sha="a" * 40,
            owned_folders=tuple(policy.owns),
            listing=FileListing.from_disk(
                root, policy.owns, paths=paths_for_task(root, task, policy, None, today=today)
            ),
            first_ledger_year=day[:4],
        )
    )
    compact = ledger.compact_path(state, policy.ledger, Period.DAILY, day, fmt=Format.PARQUET)
    assert compact.relative_to(root) in {Path(path) for path in outcome.written}
    return compact


def test_the_real_ledger_compacts_pre_diagnostics_and_populated_parquet_together(
    tmp_path: Path,
) -> None:
    row_type = StorySimilarityThresholdHistoryRow
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY
    state = tmp_path / ledger.STATE_DIRNAME
    legacy = a_night()
    day, first_run = legacy["date"], legacy["run_id"]
    old_fields: dict[str, Any] = {
        name: (field.annotation, field)
        for name, field in row_type.model_fields.items()
        if name in legacy
    }
    old_shape = create_model("PreDiagnosticsHistory", __base__=_LegacyHistoryShape, **old_fields)
    old_path = _file_history(
        state, old_shape.model_validate(legacy), day=day, run_id=first_run, attempt=1
    )
    _, old_schema = read_footer_schema(old_path)
    assert set(legacy) <= set(old_schema.names)

    readings = {
        "score_pool_histogram": _histogram(3, 5),
        "score_drift_baseline": _baseline(required_days=7),
        "score_drift_status": "insufficient_baseline",
    }
    assert not set(readings).intersection(old_schema.names)
    second_run = "2026-11-19-2"
    current = {name: value for name, value in legacy.items() if name != "version"}
    added = row_type.model_fields.keys() - legacy
    shape_only = row_type.model_validate(current)
    assert shape_only.version == row_type.schema_version()
    assert shape_only.model_dump(include=added) == dict.fromkeys(added)
    populated = row_type.model_validate(current | readings | {"run_id": second_run})
    new_path = _file_history(state, populated, day=day, run_id=second_run, attempt=2)
    _, new_schema = read_footer_schema(new_path)
    assert set(new_schema.names) - set(old_schema.names) == added
    assert all(new_schema.field(name) == old_schema.field(name) for name in old_schema.names)
    assert all(new_schema.field(name).nullable for name in added)
    assert set(readings) <= set(new_schema.names)
    assert all(str(new_schema.field(name).type) == "string" for name in readings)
    assert ledger.door_key(which) == ("date", "run_id")
    before = ledger.load_stored([old_path, new_path], model=row_type)
    by_run = {held.row.run_id: held for held in before}
    assert by_run[first_run].identity.attempt == 1
    assert by_run[second_run].identity.attempt == 2

    compact = _compact_history_day(tmp_path, day)

    assert not old_path.exists() and not new_path.exists()
    footer = ledger.read_footer(compact)
    assert footer.envelope.built_from == footer.rows == 2
    assert footer.envelope.row_schema_version == row_type.schema_version() != legacy["version"]
    packed = ledger.load_stored([compact], model=row_type)
    assert len(packed) == 2
    assert {held.row.run_id: held for held in packed} == by_run
    bounded = ledger.load_days(state, which, [day], model=row_type)
    assert len(bounded) == 2
    rows = {row.run_id: row.model_dump(mode="json") for row in bounded}
    assert rows[first_run] == legacy | dict.fromkeys(added)
    assert rows[second_run] == populated.model_dump(mode="json")
