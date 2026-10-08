"""Count one day's verdict files into the record, and file the rows they carry.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

It calls no model and opens no socket. The counting arithmetic is in
`idhazh.similarity.counting`; this module reads the shards' files, files the
day's rows through the ledger door, and decides whether the record can be
counted at all.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import atomic_write, config, ledger
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_distribution import StorySimilarityDistribution
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.council import metrics_sink
from idhazh.similarity import counting
from idhazh.similarity.stamps import judge_inputs, scorer_inputs
from idhazh.stages.common import LOG

#: What every file this stage files names as the module that wrote it.
PRODUCER: Final = __name__.partition(".")[2]


@dataclass(frozen=True, slots=True)
class CountReport:
    """What the collecting job did, for the caller to log and a later row to read."""

    date: str
    run_id: str
    shards_expected: int
    shards_present: int
    rows_appended: int

    #: How many instrument rows the units shipped landed in this judge's own
    #: ledger. Counted apart from the verdicts because a night whose units all
    #: judged nothing still files one row each, and a zero here on a night that
    #: appended verdicts is an upload that went missing.
    metrics_appended: int

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
    judge_id: str,
    shipped_root: Path,
    verdicts_dir: Path,
    settings: config.Settings,
    identity: WriterIdentity,
    state_dir: Path | None = None,
) -> CountReport:
    """File the day's verdicts, then count them into the record if every shard reported.

    **A day with a missing shard is not counted at all.** Every row that did arrive
    is still filed, so nothing a shard produced is lost, but the date stays out
    of `counted_dates`. Counting three shards of four cannot be repaired later: the
    record counts a date once and refuses the same date twice, so the fourth
    shard's verdicts would be unreachable for ever. Refusing costs one day of
    evidence until somebody re-dispatches the date; counting a partial day costs a
    quarter of it permanently, with nothing saying so.

    **The instrument rows land whatever the record decides.** A unit that ran and
    a day that could not be counted are two different facts, and holding the
    readings back would delete the evidence of the first to record the second.

    **An instrument move archives the counts and keeps the date memory.** The
    counts go because they answer a different question under the new instrument.
    The list of nights already read comes across, because that is not a count -
    and without it the council would be told every night in its window is
    outstanding the first time somebody changes the model, which is a week of
    runners re-judging days this judge has already read.

    **`shipped_root`, `verdicts_dir` and `judge_id` are handed in rather than
    resolved here.** The two directories the units uploaded into belong to the
    venue and the slug belongs to the tenant, so a stage that spelled any of them
    would be a stage that only runs inside one venue under one name. Both
    directories hold one tenant's files, so what this counts is never a second
    tenant's work.

    **`identity` is the council's own, for the job that saves the night's
    results.** The pairs and the instrument rows go through the ledger door under
    it, with this stage named as their producer, so each file says which run,
    which attempt and which commit filed it. The rows keep the cells the draw
    and the units stamped: `run_id` is the council run, and `work_part_index` the
    part that judged the row.

    **`run_id` is the council's own, and this verb writes it into no cell.** The
    rows it files were stamped by the draw and the record carries no run at
    all, so what the name buys here is that this job's own report and log line
    say which night counted the day. Without it a count cannot be tied to the run
    that produced it at all.
    """
    knobs = settings.app.assemble.same_story.judging_knobs()
    shards = settings.app.council.shards
    state = state_dir if state_dir is not None else config.REPO_ROOT / ledger.STATE_DIRNAME
    writer = WriterIdentity.model_validate(identity.model_dump() | {"producer": PRODUCER})

    present = sorted(path for path in verdicts_dir.glob("*.csv") if path.is_file())
    rows = [row for path in present for row in _verdict_rows(path)]
    filed = ledger.persist(
        state,
        rows,
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS,
        covers=date,
        identity=writer,
    )
    appended = len(rows) if filed else 0
    metrics = _collect_metrics(
        date, state=state, shipped_root=shipped_root, judge_id=judge_id, identity=writer
    )

    scorer, judge = scorer_inputs(settings), judge_inputs(settings)
    record_path = ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION)
    record = (
        StorySimilarityDistribution.from_json(record_path.read_text(encoding="utf-8"))
        if record_path.exists()
        else counting.empty_record(knobs, scorer=scorer, judge=judge)
    )

    archived: str | None = None
    moved = counting.inputs_changed(record, knobs=knobs, scorer=scorer, judge=judge)
    if moved is not None:
        stem = counting.archive_stem(record)
        if ledger.accepts_new_rows(LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE, 1):
            atomic_write.write_atomic(
                ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE, stem),
                record.to_json(),
            )
            archived = stem
        record = counting.empty_record(
            knobs, scorer=scorer, judge=judge, judged_dates=record.judged_dates
        )
        LOG.info("count-verdicts date=%s archived=%s was=%s now=%s", date, archived, *moved)

    counts = len(present) >= shards and ledger.accepts_new_rows(
        LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION, len(rows)
    )
    if not counts:
        report = CountReport(
            date=date,
            run_id=run_id,
            shards_expected=shards,
            shards_present=len(present),
            rows_appended=appended,
            metrics_appended=metrics,
            counted=False,
            held_reason="shards_missing" if len(present) < shards else "family_not_active",
            archived=archived,
        )
    else:
        atomic_write.write_atomic(
            record_path, counting.count_day(record, rows, date=date).to_json()
        )
        report = CountReport(
            date=date,
            run_id=run_id,
            shards_expected=shards,
            shards_present=len(present),
            rows_appended=appended,
            metrics_appended=metrics,
            counted=True,
            held_reason="inputs_changed" if archived else None,
            archived=archived,
        )

    LOG.info(
        "count-verdicts date=%s run=%s shards=%s/%s appended=%s metrics=%s counted=%s held=%s",
        report.date,
        report.run_id,
        report.shards_present,
        report.shards_expected,
        report.rows_appended,
        report.metrics_appended,
        report.counted,
        report.held_reason,
    )
    return report


def _collect_metrics(
    date: str, *, state: Path, shipped_root: Path, judge_id: str, identity: WriterIdentity
) -> int:
    """File what the units shipped into this judge's own metrics ledger.

    Through the council's shipping capability, which reads a row by the contract
    it is handed and files it through the ledger door - so the venue names no
    column of this ledger and this module opens no shipped file itself.

    What it reads is one file per unit of tonight's split, so it costs what the
    night fanned out to rather than what the archive has piled up (Guardrail
    #12). A run whose units shipped nothing files nothing and says so.
    """
    if not shipped_root.exists():
        return 0
    return metrics_sink.collect_judge_metrics(
        shipped_root,
        judge_id=judge_id,
        contract=ContentSimilarityJudgeMetrics,
        which=LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS,
        state_dir=state,
        covers=date,
        identity=identity,
    )
