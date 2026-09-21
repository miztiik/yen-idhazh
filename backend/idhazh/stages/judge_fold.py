"""The day's verdict files in, the day's committed rows and the record out.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").

It calls no model and opens no socket. The counting arithmetic is in
`idhazh.similarity.fold`; this module reads the legs' files, appends the day's
rows, and decides whether the record can be folded at all.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from idhazh import assemble, config, ledger
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.similarity import fold
from idhazh.similarity.stamps import judge_inputs, scorer_inputs
from idhazh.stages import common
from idhazh.stages.common import LOG
from idhazh.stages.judge_shard import VERDICTS_DIRNAME


@dataclass(frozen=True, slots=True)
class FoldReport:
    """What the fold did, for the caller to log and for row 8 to write a reason from."""

    date: str
    legs_expected: int
    legs_present: int
    rows_appended: int
    folded: bool
    held_reason: str | None
    archived: str | None


def _verdict_rows(path: Path) -> list[StorySimilarityPair]:
    """One leg's verdict file, every row through the contract.

    A row that no longer parses stops the read. This is evidence going into a
    record that is rewritten whole, so a silently short count cannot be told from
    a leg that had little to say.
    """
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    return [StorySimilarityPair.from_csv_row(raw) for raw in reader]


def stage_judge_fold(
    date: str,
    *,
    settings: config.Settings,
    state_dir: Path | None = None,
    judge_root: Path | None = None,
) -> FoldReport:
    """Append the day's verdicts, then count them into the record if every leg reported.

    **A day with a missing leg is not folded at all.** Every row that did arrive
    is still appended, so nothing a leg produced is lost, but the date stays out
    of `folded_dates`. Folding three legs of four cannot be repaired later: the
    record counts a date once and refuses a second fold, so the fourth leg's
    verdicts would be unreachable for ever. Refusing costs one day of evidence
    until somebody re-dispatches the date; folding a partial day costs a quarter
    of it permanently, with nothing saying so.
    """
    knobs = settings.app.assemble.same_story.judging_knobs()
    shards = settings.app.council.shards
    state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME
    root = judge_root if judge_root is not None else common.JUDGE_ROOT
    verdicts = root / date / VERDICTS_DIRNAME

    present = sorted(path for path in verdicts.glob("*.csv") if path.is_file())
    rows = [row for path in present for row in _verdict_rows(path)]
    appended = ledger.append_story_similarity_pairs(state, date, rows)

    scorer, judge = scorer_inputs(settings), judge_inputs(settings)
    record_path = ledger.score_distribution_path(state)
    record = (
        StorySimilarityDistribution.from_json(record_path.read_text(encoding="utf-8"))
        if record_path.exists()
        else fold.empty_record(knobs, scorer=scorer, judge=judge)
    )

    archived: str | None = None
    moved = fold.inputs_changed(record, knobs=knobs, scorer=scorer, judge=judge)
    if moved is not None:
        stem = fold.archive_stem(record)
        assemble.write_atomic(
            ledger.score_distribution_archive_path(state, stem), record.to_json()
        )
        archived = stem
        record = fold.empty_record(knobs, scorer=scorer, judge=judge)
        LOG.info("judge fold date=%s archived=%s was=%s now=%s", date, stem, *moved)

    if len(present) < shards:
        report = FoldReport(
            date=date,
            legs_expected=shards,
            legs_present=len(present),
            rows_appended=appended,
            folded=False,
            held_reason="legs_missing",
            archived=archived,
        )
    else:
        assemble.write_atomic(record_path, fold.fold_day(record, rows, date=date).to_json())
        report = FoldReport(
            date=date,
            legs_expected=shards,
            legs_present=len(present),
            rows_appended=appended,
            folded=True,
            held_reason="inputs_changed" if archived else None,
            archived=archived,
        )

    LOG.info(
        "judge fold date=%s legs=%s/%s appended=%s folded=%s held=%s",
        report.date,
        report.legs_present,
        report.legs_expected,
        report.rows_appended,
        report.folded,
        report.held_reason,
    )
    return report
