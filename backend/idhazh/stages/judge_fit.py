"""The record and one day in, one fitted row out. Nothing reads the number yet.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").

It calls no model and opens no socket. The five steps are in
`idhazh.similarity.fit`; this module reads the record, the day and the written
rows, decides whether the gates let a fit run, and writes the row either way.

**A row goes down on a held day too.** A line that moves itself has to leave a
record on the days it stayed put, or a reader cannot tell a day the evidence
refused from a day nothing ran.
"""

from __future__ import annotations

from pathlib import Path

from idhazh import assemble, config, ledger
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.fitted_similarity_threshold import (
    ClampKind,
    FittedSimilarityThreshold,
    HeldReason,
)
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import SameStoryVerdict, ScorerModelId
from idhazh.similarity import fit, fold
from idhazh.similarity.stamps import ScorerStamp, judge_inputs, scorer_inputs
from idhazh.stages import common
from idhazh.stages.common import LOG, _load_day


def merge_count(day: DigestDay) -> int:
    """How many groups the day published, counted off the day's own items.

    A story naming itself is not a group. The grouping pass has never written
    one and the contract refuses it, so this is not a guard against the pass - it
    is what keeps this count and the console's reading of the same items from
    ever being two numbers.
    """
    anchors = {
        item.same_story_as
        for item in day.items
        if item.same_story_as is not None and item.same_story_as != item.item_id
    }
    return len(anchors)


def _ruler(
    record: StorySimilarityDistribution, scorer: ScorerStamp
) -> tuple[ScorerModelId, float, float]:
    """Which encoder and weights the counts being fitted were taken under.

    Off the record rather than off the config, because the row is a statement
    about evidence already counted. The config is only reached for a record that
    has never been stamped, which `fold.empty_record` does at birth - so this
    falls back on the first run of a fresh clone and never after it.
    """
    return (
        scorer.scorer_model if record.scorer_model is None else record.scorer_model,
        scorer.cosine_weight if record.cosine_weight is None else record.cosine_weight,
        (
            scorer.key_point_weight
            if record.key_point_weight is None
            else record.key_point_weight
        ),
    )


def stage_judge_fit(
    date: str,
    *,
    run_id: str,
    settings: config.Settings,
    state_dir: Path | None = None,
    digest_root: Path = common.PUBLIC_ROOT,
) -> FittedSimilarityThreshold | None:
    """Walk the record, damp the move, clamp what is left, and write the day's row.

    **Every read is bounded** (Guardrail #12). One published day, the fixed-size
    record, the one day file the date names, and the fitted rows inside a window
    two knobs set. Nothing walks a collection a run appends to.

    **`run_id` is the council's own and is handed in.** The run that fitted the
    line is the council night, not the digest run that published the day it read
    - and the digest run's id carries a date prefix a day stale, which a reader
    takes for the day this row's run opened.

    **Today's own row is excluded from every look backwards.** A second attempt
    at one date would otherwise read its own first attempt as yesterday's line
    and damp against it, so a re-run would move the line a second time. Excluding
    it makes a re-run write the same row it wrote the first time.

    A date with no published day writes nothing and says so. There are no merges
    to count on it, which is a day that never happened rather than a run to fail.
    """
    same_story = settings.app.assemble.same_story
    knobs = same_story.judging_knobs()
    state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME

    day = _load_day(assemble.day_dir(digest_root, date) / "digest.json")
    if day is None:
        LOG.warning("judge fit found no published day to fit for date=%s", date)
        return None

    record_path = ledger.score_distribution_path(state)
    scorer, judge = scorer_inputs(settings), judge_inputs(settings)
    record = (
        StorySimilarityDistribution.from_json(record_path.read_text(encoding="utf-8"))
        if record_path.exists()
        else fold.empty_record(knobs, scorer=scorer, judge=judge)
    )

    window = max(knobs.settled_window_days, knobs.step_change_window_rows * 2)
    earlier = [
        row
        for row in ledger.load_fitted_thresholds(state, today=date, within_days=window)
        if row.date < date
    ]
    previous = earlier[-1].applied if earlier else same_story.floor_min

    day_rows = fold.one_row_a_pair(ledger.load_story_similarity_pairs(state, date))
    judged = [row for row in day_rows if row.verdict is not None]
    usable = [row for row in judged if row.usable]
    disagreement = (
        sum(row.verdict is not row.verdict_swapped for row in judged) / len(judged)
        if judged
        else 0.0
    )
    unclear = (
        sum(row.verdict is SameStoryVerdict.UNCLEAR for row in usable) / len(usable)
        if usable
        else 0.0
    )

    # `inputs_changed` first: a record taken under a different encoder, weight or
    # ask is not evidence about the question today is asking, whoever folded it.
    # Then the fold's own refusal, which this re-derives rather than receives -
    # the two verbs are two processes, and `folded_dates` is where the fold wrote
    # its answer down.
    moved = fold.inputs_changed(record, knobs=knobs, scorer=scorer, judge=judge)
    if moved is not None:
        fold_held: HeldReason | None = HeldReason.INPUTS_CHANGED
    elif date not in record.folded_dates:
        fold_held = HeldReason.LEGS_MISSING
    else:
        fold_held = None

    held = fit.gates(
        record,
        knobs=knobs,
        above_line=fit.judged_at_or_above(record, previous),
        days=len(record.folded_dates),
        disagreement_rate=disagreement,
        unclear_rate=unclear,
        fold_held=fold_held,
    )
    proposal = fit.fit_line(record, discard_share=knobs.discard_share)
    shift = fit.daily_shift(
        record, fold.day_counts(day_rows, record=record), discard_share=knobs.discard_share
    )
    typical = fit.typical_shift(earlier, window_rows=knobs.step_change_window_rows)

    if held is not None or proposal is None:
        shaped = fit.Clamped(applied=previous, kind=ClampKind.NONE, movement=0.0)
        after_damping: float | None = None
        is_settled = False
    else:
        after_damping = (
            fit.damp(
                proposal,
                previous,
                fall_weight=knobs.fall_weight,
                rise_weight=knobs.rise_weight,
            )
            if fit.is_a_move(proposal, previous, dead_zone=knobs.dead_zone)
            else previous
        )
        guard_fires = (
            knobs.step_change_guard_enforced
            and shift is not None
            and typical is not None
            and shift > typical * knobs.step_change_multiple
        )
        shaped = (
            fit.held_at(previous, after_damping)
            if guard_fires
            else fit.clamp(
                after_damping,
                previous,
                max_down_step=knobs.max_down_step,
                max_up_step=knobs.max_up_step,
                band_low=knobs.band_low,
                band_high=knobs.band_high,
            )
        )
        is_settled = fit.settled(
            earlier,
            proposed=proposal,
            date=date,
            window_days=knobs.settled_window_days,
            delta=knobs.settled_delta,
        )

    scorer_model, cosine_weight, key_point_weight = _ruler(record, scorer)
    row = FittedSimilarityThreshold(
        version=FittedSimilarityThreshold.schema_version(),
        date=date,
        run_id=run_id,
        record_stamp=record.record_stamp(),
        previous=previous,
        proposed=None if held is not None else proposal,
        after_damping=after_damping,
        applied=shaped.applied,
        clamp_kind=shaped.kind,
        clamp_movement=shaped.movement,
        held_reason=HeldReason.NONE if held is None else held,
        settled=is_settled,
        discard_share=knobs.discard_share,
        fall_weight=knobs.fall_weight,
        rise_weight=knobs.rise_weight,
        max_down_step=knobs.max_down_step,
        max_up_step=knobs.max_up_step,
        step_change_multiple=knobs.step_change_multiple,
        daily_shift=shift,
        typical_shift=typical,
        pairs_in_band=len(day_rows),
        pairs_judged=len(judged),
        pairs_usable=len(usable),
        disagreement_rate=disagreement,
        unclear_rate=unclear,
        negatives_on_record=fit.negatives_on(record),
        above_line_on_record=fit.judged_at_or_above(record, shaped.applied),
        days_on_record=len(record.folded_dates),
        merge_count=merge_count(day),
        scorer_model=scorer_model,
        cosine_weight=cosine_weight,
        key_point_weight=key_point_weight,
        judge_model=record.judge_model,
        prompt_digest=record.prompt_digest,
        grammar_digest=record.grammar_digest,
    )
    ledger.append_fitted_thresholds(state, date, [row])
    LOG.info(
        "judge fit date=%s run=%s previous=%s proposed=%s applied=%s clamp=%s held=%s "
        "settled=%s shift=%s typical=%s",
        row.date,
        row.run_id,
        row.previous,
        row.proposed,
        row.applied,
        row.clamp_kind.value,
        row.held_reason.value,
        row.settled,
        row.daily_shift,
        row.typical_shift,
    )
    return row
