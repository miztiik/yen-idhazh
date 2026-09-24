"""Score the merge line in force against the hand-marked holdout, and record it.

One stage, one module. A person types the verb; nothing in the daily pipeline
calls it, because the marked file changes when somebody labels more pairs rather
than when a day publishes.

It calls no model and opens no socket. The arithmetic is in
`idhazh.similarity.holdout`; this module reads the line, asks for the cells,
refuses a reading too thin to mean anything, and writes the row.

**A reading below the floor writes nothing and says so.** Four cells that add up
are not a measurement on their own: a run that could resolve no pair at all
satisfies the sum with four zeros and a full unresolved count, and the row would
read as a line that never merged anything.
"""

from __future__ import annotations

from pathlib import Path

from idhazh import config, ledger
from idhazh.contracts.knobs.placement import HOLDOUT_TWO_STORY_MAX
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.similarity import applied, holdout
from idhazh.similarity.stamps import scorer_inputs
from idhazh.stages import common
from idhazh.stages.common import LOG

#: How far the retaken two-story maximum may sit from the declared constant
#: before the operator is told. Wide enough that the fourth decimal the constant
#: is written to cannot fire it on its own rounding.
_MAX_DRIFT_TOLERANCE = 0.00005


def _append(state_dir: Path, date: str, row: MergeLineHoldoutScore) -> int:
    """Put the row in its day file, and settle the file after the write.

    The writer lives here rather than in `idhazh.ledger` because the ledger may
    not import a judge's contract: a council verb reaches that module for its own
    row types, and a judge contract arriving through it would put a judge in the
    council's import closure. The path and the settlement key are the ledger's,
    which is where a path belongs.

    **The day file is created even when nothing was scored**, the way every
    ledger beside it is: the commit step names this directory, `git add` runs
    under `set -euo pipefail`, and a path missing from the working tree aborts
    the step and costs the ledgers staged with it.
    """
    path = ledger.merge_line_holdout_scores_path(state_dir, date)
    columns = MergeLineHoldoutScore.csv_columns()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(columns) + "\n", encoding="utf-8", newline="")
    landed = ledger.extend_ledger_file(path, columns, [row])
    return landed - ledger.drop_repeated_rows(path, ledger.MERGE_LINE_HOLDOUT_SCORE_KEY)


def _warn_on_a_stale_maximum(reading: holdout.Reading) -> None:
    """Say so when the declared two-story maximum no longer matches the file.

    `HOLDOUT_TWO_STORY_MAX` is one declaration with one reading, and this verb is
    the instrument that retakes it (Guardrail #10). It is printed rather than
    stored: a committed copy would be the second source the constant is not
    allowed to have.
    """
    retaken = holdout.two_story_max(reading)
    if retaken is None or abs(retaken - HOLDOUT_TWO_STORY_MAX) <= _MAX_DRIFT_TOLERANCE:
        return
    LOG.warning(
        "the highest pair marked as two stories now scores %.4f and "
        "HOLDOUT_TWO_STORY_MAX declares %.4f. The band ceiling in "
        "backend/idhazh/contracts/knobs/placement.py is the number to retake",
        retaken,
        HOLDOUT_TWO_STORY_MAX,
    )


def _warn_on_an_unseen_labeller(marks: list[SimilarityHoldoutPair], labeller: str) -> None:
    """Say so when the name handed in appears on none of the marks' own notes.

    The column is free text because the committed labels name a model from
    outside this repository's registry, so nothing can refuse a wrong name. What
    this catches is the typo: a reading filed under a labeller the file has never
    heard of is a reading nobody can argue with later.
    """
    if any(labeller in mark.note for mark in marks):
        return
    LOG.warning(
        "labeller=%s appears in none of the %d marks' notes, so this row will "
        "name somebody the marked file does not",
        labeller,
        len(marks),
    )


def stage_score_merge_line_holdout(
    date: str,
    *,
    run_id: str,
    labeller: str,
    settings: config.Settings,
    state_dir: Path | None = None,
    digest_root: Path = common.PUBLIC_ROOT,
) -> MergeLineHoldoutScore | None:
    """Count the four cells at the line in force, and write the day's row.

    **Every read is bounded** (Guardrail #12). The hand-marked file, then one
    published day payload for each distinct date its rows name. Nothing walks a
    collection a run appends to, and another year of archive adds no read.

    **The line is the one the build would apply on this date**, which is the
    fitted line where a fit has run inside the lookback and the committed floor
    where none has. Reading the committed floor unconditionally would score a
    line the day was not grouped at.

    Returns the row it wrote, or `None` where there was nothing worth writing -
    an absent marked file, or a reading that resolved too few pairs to mean
    anything. Both print what they found.
    """
    state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME
    same_story = settings.app.assemble.same_story

    marks = holdout.marked_pairs(state)
    if not marks:
        LOG.warning(
            "score-merge-line-holdout found no marked pairs in %s, so there is "
            "nothing to score the line against",
            ledger.similarity_holdout_relpath(),
        )
        return None
    _warn_on_an_unseen_labeller(marks, labeller)

    line = applied.effective_same_story(same_story, state_dir=state, date=date).floor_min
    scorer = scorer_inputs(settings)
    reading = holdout.score_marks(
        marks,
        digest_root=digest_root,
        cosine_weight=scorer.cosine_weight,
    )
    cells = holdout.count_cells(reading, line=line)
    _warn_on_a_stale_maximum(reading)

    floor = holdout.resolved_floor(cells.marked)
    if cells.resolved < floor:
        LOG.error(
            "score-merge-line-holdout resolved %d of %d marked pairs, and a reading "
            "means nothing below %d. %d pairs name a day the tree no longer holds, "
            "so no row is written for date=%s",
            cells.resolved,
            cells.marked,
            floor,
            cells.unresolved,
            date,
        )
        return None

    row = MergeLineHoldoutScore(
        version=MergeLineHoldoutScore.schema_version(),
        date=date,
        run_id=run_id,
        applied_line=line,
        labeller=labeller,
        merged_and_one_story=cells.merged_and_one_story,
        merged_and_two_stories=cells.merged_and_two_stories,
        apart_and_one_story=cells.apart_and_one_story,
        apart_and_two_stories=cells.apart_and_two_stories,
        pairs_unresolved=cells.unresolved,
        labelled_two_story_pairs=cells.two_story_marks,
        scorer_model=scorer.scorer_model,
        cosine_weight=scorer.cosine_weight,
    )
    _append(state, date, row)
    LOG.info(
        "score-merge-line-holdout date=%s run=%s line=%s merged_one=%d merged_two=%d "
        "apart_one=%d apart_two=%d unresolved=%d marked=%d two_story_marks=%d days=%d",
        row.date,
        row.run_id,
        row.applied_line,
        row.merged_and_one_story,
        row.merged_and_two_stories,
        row.apart_and_one_story,
        row.apart_and_two_stories,
        row.pairs_unresolved,
        cells.marked,
        row.labelled_two_story_pairs,
        reading.days_opened,
    )
    return row
