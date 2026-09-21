"""Count one day's verdict files into the record, and commit the rows they carry.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

It calls no model and opens no socket. The counting arithmetic is in
`idhazh.similarity.counting`; this module reads the shards' files, appends the
day's rows, and decides whether the record can be counted at all.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from idhazh import assemble, config, ledger
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.similarity import counting
from idhazh.similarity.stamps import judge_inputs, scorer_inputs
from idhazh.stages import common
from idhazh.stages.common import LOG
from idhazh.stages.judge_item_pairs import VERDICTS_DIRNAME


@dataclass(frozen=True, slots=True)
class CountReport:
    """What the collecting job did, for the caller to log and a later row to read."""

    date: str
    run_id: str
    shards_expected: int
    shards_present: int
    rows_appended: int
    counted: bool
    held_reason: str | None
    archived: str | None


def _verdict_rows(path: Path) -> list[StorySimilarityPair]:
    """One shard's verdict file, every row through the contract.

    A row that no longer parses stops the read. This is evidence going into a
    record that is rewritten whole, so a silently short count cannot be told from
    a shard that had little to say.
    """
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    return [StorySimilarityPair.from_csv_row(raw) for raw in reader]


def stage_count_verdicts(
    date: str,
    *,
    run_id: str,
    settings: config.Settings,
    state_dir: Path | None = None,
    judge_root: Path | None = None,
) -> CountReport:
    """Append the day's verdicts, then count them into the record if every shard reported.

    **A day with a missing shard is not counted at all.** Every row that did arrive
    is still appended, so nothing a shard produced is lost, but the date stays out
    of `counted_dates`. Counting three shards of four cannot be repaired later: the
    record counts a date once and refuses the same date twice, so the fourth
    shard's verdicts would be unreachable for ever. Refusing costs one day of
    evidence until somebody re-dispatches the date; counting a partial day costs a
    quarter of it permanently, with nothing saying so.

    **`run_id` is the council's own, and this verb writes it into no cell.** The
    rows it appends were stamped by the draw and the record carries no run at
    all, so what the name buys here is that this job's own report and log line
    say which night counted the day. Without it a count cannot be tied to the run
    that produced it at all.
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
        else counting.empty_record(knobs, scorer=scorer, judge=judge)
    )

    archived: str | None = None
    moved = counting.inputs_changed(record, knobs=knobs, scorer=scorer, judge=judge)
    if moved is not None:
        stem = counting.archive_stem(record)
        assemble.write_atomic(
            ledger.score_distribution_archive_path(state, stem), record.to_json()
        )
        archived = stem
        record = counting.empty_record(knobs, scorer=scorer, judge=judge)
        LOG.info("count-verdicts date=%s archived=%s was=%s now=%s", date, stem, *moved)

    if len(present) < shards:
        report = CountReport(
            date=date,
            run_id=run_id,
            shards_expected=shards,
            shards_present=len(present),
            rows_appended=appended,
            counted=False,
            held_reason="shards_missing",
            archived=archived,
        )
    else:
        assemble.write_atomic(record_path, counting.count_day(record, rows, date=date).to_json())
        report = CountReport(
            date=date,
            run_id=run_id,
            shards_expected=shards,
            shards_present=len(present),
            rows_appended=appended,
            counted=True,
            held_reason="inputs_changed" if archived else None,
            archived=archived,
        )

    LOG.info(
        "count-verdicts date=%s run=%s shards=%s/%s appended=%s counted=%s held=%s",
        report.date,
        report.run_id,
        report.shards_present,
        report.shards_expected,
        report.rows_appended,
        report.counted,
        report.held_reason,
    )
    return report
