"""What did tonight's pairs say about both thresholds, and where do they stand tomorrow?

One stage, one module. The router does not name it: the council reaches it through the
tenant that owns this judge (CLAUDE.md section 1a, "A router is the sharpest case").

It calls no model and opens no socket. It runs in the collecting job right after
`file_pair_verdicts`, reads the last few nights of `pair-verdicts`, finds where each
threshold's same-story share crosses its level, decides what the night may do about it, and
files one `threshold-history` row holding every number of that computation. The next night's
draw reads the row's `threshold_after` columns.

The arithmetic is four small modules, and this one only joins them: which pairs are
evidence (`threshold_evidence`), where the curve through them crosses a level
(`threshold_curve`), what the gap lets the night do (`threshold_move`), and what the night's
lightly sampled ends and runners add up to (`night_totals`). `build_threshold_row` is the whole
of the joining, over rows already read, so a night can be worked again from the rows it read
and nothing else.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

from idhazh import ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_pair_verdicts_filed_on,
    load_threshold_history,
    review_days,
)
from idhazh.contracts.base import StalePayloadError
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.content_similarity_judge import ThresholdsConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_diagnostics import ScorePoolHistogram
from idhazh.contracts.story_similarity_pair_verdict import (
    RECOMPUTED_TOLERANCE,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_runner_report import StorySimilarityRunnerReport
from idhazh.contracts.story_similarity_score_pool import ContentSimilarityScorePool
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.council import metrics_sink
from idhazh.similarity.canary_diagnostics import canary_columns
from idhazh.similarity.night_totals import end_columns, pool_sizes, runner_columns
from idhazh.similarity.sample_diagnostics import sample_columns
from idhazh.similarity.score_pool_drift import drift_columns
from idhazh.similarity.threshold_curve import (
    Curve,
    fit_pulled_curve,
    pull_centre,
    steepness_by_night,
)
from idhazh.similarity.threshold_evidence import (
    Evidence,
    MeaningStamp,
    Side,
    current_pairs,
    evidence_near,
    tonights_stamp,
)
from idhazh.similarity.threshold_move import PreviousNight, ThresholdMove, decide_move
from idhazh.similarity.thresholds_in_force import ThresholdsInForce, thresholds_in_force
from idhazh.stages.common import LOG

#: What every file this stage files names as the module that wrote it.
PRODUCER: Final = __name__.partition(".")[2]


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """What the stage did, for the caller to log or ignore."""

    date: str
    run_id: str
    #: The night's row, or none when the night dealt no pair at all.
    row: StorySimilarityThresholdHistoryRow | None
    #: Whether the ledger door took the row.
    filed: bool


def _draw_rows(draw_path: Path) -> list[StorySimilarityPairVerdict]:
    """The draw file's rows through the contract.

    The planning job writes the file for every night it prepares, with a header and no rows
    when the day drew nothing, so a missing file is an incomplete artifact and not a quiet
    night: the pool of a lightly sampled end whose rows were all lost would be filed as zero.
    """
    if not draw_path.is_file():
        raise FileNotFoundError(
            f"{draw_path} does not exist, so the pairs the night drew are unknown and the "
            "pool of each lightly sampled end would be filed as empty"
        )
    with draw_path.open("r", encoding="utf-8", newline="") as handle:
        return [StorySimilarityPairVerdict.from_csv_row(cells) for cells in csv.DictReader(handle)]


def _prepared_histogram(
    path: Path | None, *, date: str, run_id: str, attempt: int
) -> ScorePoolHistogram | None:
    """Read only the sidecar the Council already checked against its receipt."""
    if path is None:
        return None
    try:
        pool = ContentSimilarityScorePool.read(path)
        if (pool.date, pool.run_id, pool.attempt) == (date, run_id, attempt):
            return pool.histogram
        reason = "digest, run or attempt did not match"
    except (OSError, ValueError, StalePayloadError) as error:
        reason = type(error).__name__
    LOG.warning(
        "review-thresholds found no usable score pool date=%s run=%s attempt=%s reason=%s",
        date,
        run_id,
        attempt,
        reason,
    )
    return None


def _readings_of_this_night(
    shipped_root: Path, *, judge_id: str, date: str, run_id: str
) -> list[StorySimilarityRunnerReport]:
    """The runners' readings of their own instrument, each one this night's and this run's."""
    if not shipped_root.exists():
        return []
    readings = metrics_sink.shipped_rows(
        shipped_root, judge_id=judge_id, contract=StorySimilarityRunnerReport
    )
    strays = sorted({(one.date, one.run_id) for one in readings} - {(date, run_id)})
    if strays:
        raise ValueError(
            f"the units shipped readings naming {strays}, and this stage settles "
            f"{(date, run_id)}, so they came from another night's artifact and no row is filed"
        )
    return readings


def _side_columns(
    side: Side,
    *,
    before: float,
    share_level: float,
    evidence: Evidence,
    curve: Curve | None,
    pull: float,
    spread: float,
    move: ThresholdMove,
) -> dict[str, Any]:
    """One threshold's columns of the night's row, named `lower_` or `upper_`."""
    return {
        f"{side}_{name}": value
        for name, value in {
            "threshold_before": before,
            "share_level": share_level,
            "nights_used": evidence.nights_used,
            "usable_pairs_used": evidence.usable_pairs_used,
            "window_first_date": evidence.first_date,
            "curve_intercept": None if curve is None else curve.intercept,
            "curve_steepness": None if curve is None else curve.steepness,
            "pull_centre": pull,
            "pull_spread": spread,
            "estimate": move.estimate,
            "gap": move.gap,
            "nights_beyond_ignore_range": move.nights_beyond_ignore_range,
            "move": move.move,
            "move_limited_by": move.move_limited_by,
            "held_because": move.held_because,
            "threshold_after": move.threshold_after,
        }.items()
    }


def _previous_night(
    followed: ThresholdsInForce, side: Side, *, night: str
) -> PreviousNight | None:
    """What last night's row said about this threshold's gap, or none when there is no such row.

    Nights in a row are consecutive nights, so only a row dated the day before counts. A night
    the judge lost and a night nothing ran both break the run, and a hole in the history delays
    a move by a night and never brings one forward. The row is the one `thresholds_in_force`
    read the thresholds from, so the chain and the thresholds come from one answer to "which
    row is newest".
    """
    row = followed.row
    yesterday = (date_type.fromisoformat(night) - timedelta(days=1)).isoformat()
    if row is None or row.date != yesterday:
        return None
    return PreviousNight(
        gap=getattr(row, f"{side}_gap"),
        nights_beyond_ignore_range=getattr(row, f"{side}_nights_beyond_ignore_range"),
    )


def _one_threshold(
    side: Side,
    *,
    followed: ThresholdsInForce,
    pairs: Sequence[StorySimilarityPairVerdict],
    history: Sequence[StorySimilarityThresholdHistoryRow],
    night: str,
    nearest_other: float,
    rules: ThresholdsConfig,
) -> tuple[dict[str, Any], ThresholdMove]:
    """Evidence, curve and move for one threshold, and its columns of the night's row."""
    before = followed.lower if side == "lower" else followed.upper
    share = rules.lower_share_level if side == "lower" else rules.upper_share_level
    evidence = evidence_near(pairs, threshold=before, width=rules.near_threshold_width)
    pull = pull_centre(
        steepness_by_night(history, side=side, night=night, window_nights=rules.pull_window_nights),
        minimum_nights=rules.pull_minimum_nights,
        start=rules.pull_start_steepness,
    )
    curve = fit_pulled_curve(
        evidence.scores, evidence.answers, centre=pull, spread=rules.pull_spread
    )
    estimate = None if curve is None else curve.score_at(share)
    if estimate is None:
        if evidence.usable_pairs_used:
            reason = (
                "every answer was alike"
                if len(set(evidence.answers)) == 1
                else "the fit did not settle"
            )
            LOG.info(
                "review-thresholds night=%s side=%s found no curve in %s usable pairs: %s",
                night,
                side,
                evidence.usable_pairs_used,
                reason,
            )
        curve = None
    move = decide_move(
        side,
        before=before,
        estimate=estimate,
        usable_pairs_used=evidence.usable_pairs_used,
        previous=_previous_night(followed, side, night=night),
        nearest_other=nearest_other,
        settings=rules,
    )
    columns = _side_columns(
        side,
        before=before,
        share_level=share,
        evidence=evidence,
        curve=curve,
        pull=pull,
        spread=rules.pull_spread,
        move=move,
    )
    return columns, move


def _the_thresholds_the_draw_followed(
    rows: Sequence[StorySimilarityPairVerdict], followed: ThresholdsInForce
) -> None:
    """The rows say the draw followed the thresholds this stage reads from the history, or stop.

    Every row of a draw names the two thresholds the draw followed. This stage works them out
    again from the threshold history it read, by the same rule. They differ when the history
    it read is not the history the draw read, which is what a sparse checkout that was not told
    about a day looks like: the rule then falls back to the configured starts, and filing the
    night would reset both thresholds without a word. The loaders do not fail on a file that is
    absent, so this is what notices.
    """
    named = {(row.lower_threshold_in_force, row.upper_threshold_in_force) for row in rows}
    if len(named) > 1:
        raise ValueError(f"the night's rows name {len(named)} different pairs of thresholds")
    for lower, upper in named:
        if (
            abs(lower - followed.lower) > RECOMPUTED_TOLERANCE
            or abs(upper - followed.upper) > RECOMPUTED_TOLERANCE
        ):
            raise ValueError(
                f"the draw followed {lower} and {upper}, and the threshold history this stage "
                f"read puts them at {followed.lower} and {followed.upper}, so it is not the "
                "history the draw read and nothing is filed"
            )


def _what_scored_the_night(
    stamp: MeaningStamp | None, draw: Sequence[StorySimilarityPairVerdict]
) -> tuple[str, float]:
    """The encoder and the cosine weight the night's scores came from.

    The judged rows carry them in their stamp. A night nothing was judged on takes them from
    the draw's own rows, which were scored by the same run.
    """
    if stamp is not None:
        return stamp.scorer_model, stamp.cosine_weight
    scored = {(row.scorer_model, row.cosine_weight) for row in draw}
    if len(scored) != 1:
        raise ValueError(
            f"the draw's rows carry one scorer and weight, and these carry {len(scored)}"
        )
    return next(iter(scored))


def build_threshold_row(
    date: str,
    *,
    run_id: str,
    window: Sequence[StorySimilarityPairVerdict],
    history: Sequence[StorySimilarityThresholdHistoryRow],
    draw_rows: Sequence[StorySimilarityPairVerdict],
    readings: Sequence[StorySimilarityRunnerReport],
    expected_shards: int,
    rules: ThresholdsConfig,
    lookback_days_of_the_draw: int,
    versions: str,
) -> StorySimilarityThresholdHistoryRow | None:
    """The night's row, worked out from the rows the night read and from nothing else.

    `window` is the pair rows of the nights of evidence, oldest first and in the order they
    were filed, with this run's own rows last; `history` is the threshold rows of the days
    before the night. Both are read by the caller, so this is the same arithmetic whether the
    rows came off disk or out of a test.

    **A night that dealt no pair files no row.** With no draw rows and no judged rows of this
    run's own, nothing ran, and a missing row is how a reader tells that from a night that
    ran and lost everything. A night that dealt pairs files a row even when none came back
    judged: the evidence is then empty, both thresholds are held for want of it, and the row
    says how many runners reported.

    The thresholds the night starts from are the ones the draw followed, by the same rule
    (`thresholds_in_force`), and the rows are checked against it. The second threshold is
    limited by where the first ends up, so the two never close in on each other past the
    smallest gap.
    """
    tonight = list(
        {
            row.pair_key: row for row in window if row.date == date and row.run_id == run_id
        }.values()
    )
    if not tonight and not draw_rows:
        return None
    stamp = tonights_stamp(tonight)
    followed = thresholds_in_force(
        history,
        night=date,
        within_days=lookback_days_of_the_draw,
        lower_start=rules.lower_start,
        upper_start=rules.upper_start,
    )
    _the_thresholds_the_draw_followed(tonight or draw_rows, followed)
    pairs = current_pairs(window, stamp=stamp)
    lower_columns, lower = _one_threshold(
        "lower",
        followed=followed,
        pairs=pairs,
        history=history,
        night=date,
        nearest_other=followed.upper,
        rules=rules,
    )
    upper_columns, _ = _one_threshold(
        "upper",
        followed=followed,
        pairs=pairs,
        history=history,
        night=date,
        nearest_other=lower.threshold_after,
        rules=rules,
    )
    scorer_model, cosine_weight = _what_scored_the_night(stamp, draw_rows)
    return StorySimilarityThresholdHistoryRow.model_validate(
        {
            "version": StorySimilarityThresholdHistoryRow.schema_version(),
            "date": date,
            "run_id": run_id,
            "scorer_model": scorer_model,
            "cosine_weight": cosine_weight,
            "judge_model": None if stamp is None else stamp.judge_model,
            "judge_policy_version": None if stamp is None else stamp.judge_policy_version,
            "config_versions": versions,
        }
        | lower_columns
        | upper_columns
        | end_columns(tonight, pool_sizes(draw_rows, tonight))
        | runner_columns(readings, expected_shards=expected_shards)
    )


def stage_review_thresholds(
    date: str,
    *,
    run_id: str,
    judge_id: str,
    shipped_root: Path,
    draw_path: Path,
    filed_rows: tuple[StorySimilarityPairVerdict, ...] | None,
    identity: WriterIdentity,
    expected_shards: int,
    state_dir: Path,
    config_dir: Path,
    score_pool_path: Path | None = None,
) -> ReviewReport:
    """Read the last nights of pair-verdicts, move or hold both thresholds, and file the night.

    **Tonight's pairs are read as raw files, and the earlier nights through the door.** The
    collecting job has just filed tonight's rows, and the door would serve a night the gardener
    already recorded as quiet from that record and never open them. A night the judge repairs is
    such a night. The nights before it are read the ordinary way, and its own rows go last, so
    they are the newest of each pair.

    **The sample diagnostics do not reread those rows.** A retry that filed no verdicts can
    still see an earlier attempt in the fit window. Only `filed_rows` says what this attempt
    actually returned. The known-answer readings come from the reports of this attempt.

    **The read is bounded by named settings and never by the archive** (Guardrail #12): the days
    `review_days` names, which the collecting job's sparse checkout is told too. The loaders do
    not fail on a day that checkout lacks, and `build_threshold_row` checks the history it
    read against the thresholds the draw followed instead. Only the drift reading sees any
    history outside the original fit window.

    **`shipped_root`, `draw_path` and `judge_id` are handed in rather than resolved here**, for
    the reason the filing stage gives. The draw file is read for how many pairs each lightly
    sampled end held, because an end whose rows were all lost leaves none in the ledger, and
    for what scored the night when none came back. A reading that names another night or run
    stops the stage before anything is filed.

    **If this stage fails, the night keeps its pair rows and has no threshold row.** The
    scheduler reads `pair-verdicts` only, so the night is not named again, and the runners'
    readings it would have folded in are artifacts that expire. Only the threshold columns can
    be worked out again from the ledger.
    """
    execution = judge_settings.load(config_dir)
    days = review_days(date, config=execution)
    window = [
        *load_pair_verdicts(state_dir, days.pair_verdicts),
        *load_pair_verdicts_filed_on(state_dir, date),
    ]
    history = load_threshold_history(state_dir, days.threshold_history)
    fit_dates = set(days.fit_history)
    draw_rows = _draw_rows(draw_path)
    row = build_threshold_row(
        date,
        run_id=run_id,
        window=window,
        history=[prior for prior in history if prior.date in fit_dates],
        draw_rows=draw_rows,
        readings=_readings_of_this_night(
            shipped_root, judge_id=judge_id, date=date, run_id=run_id
        ),
        expected_shards=expected_shards,
        rules=execution.thresholds,
        lookback_days_of_the_draw=execution.draw.thresholds_lookback_days,
        versions=judge_settings.config_versions(config_dir),
    )
    if row is None:
        LOG.info("review-thresholds date=%s run=%s dealt no pair, so no row is filed", date, run_id)
        return ReviewReport(date=date, run_id=run_id, row=None, filed=False)
    row = StorySimilarityThresholdHistoryRow.model_validate(
        row.model_dump()
        | sample_columns(
            draw_rows,
            filed_rows,
            date=date,
            run_id=run_id,
            cutoff=execution.diagnostics.cutoff,
            upper_cutoff=row.upper_threshold_before,
        )
        | canary_columns(judge_settings.load_canaries(config_dir).pairs, row.canary_answers)
        | drift_columns(
            _prepared_histogram(
                score_pool_path, date=date, run_id=run_id, attempt=identity.attempt
            ),
            history,
            date=date,
            run_id=run_id,
            rules=execution.diagnostics,
        )
    )
    filed = ledger.persist(
        state_dir,
        [row],
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
        covers=date,
        identity=WriterIdentity.model_validate(identity.model_dump() | {"producer": PRODUCER}),
    )
    LOG.info(
        "review-thresholds date=%s run=%s filed=%s lower=%s->%s (%s) upper=%s->%s (%s) "
        "usable_pairs=%s/%s runners=%s/%s dealt=%s valid=%s agreed=%s score_drift_status=%s",
        date,
        run_id,
        bool(filed),
        row.lower_threshold_before,
        row.lower_threshold_after,
        _what_happened(row.lower_held_because.value, row.lower_move_limited_by.value),
        row.upper_threshold_before,
        row.upper_threshold_after,
        _what_happened(row.upper_held_because.value, row.upper_move_limited_by.value),
        row.lower_usable_pairs_used,
        row.upper_usable_pairs_used,
        row.runners_reported,
        row.runners_expected,
        row.pairs_dealt,
        row.pairs_valid,
        row.pairs_agreed,
        row.score_drift_status,
    )
    return ReviewReport(date=date, run_id=run_id, row=row, filed=bool(filed))


def _what_happened(held_because: str, move_limited_by: str) -> str:
    """One phrase for a threshold's night in the log: why it held, else how it moved."""
    if held_because != "none":
        return held_because
    return "moved" if move_limited_by == "none" else f"moved, limited by {move_limited_by}"
