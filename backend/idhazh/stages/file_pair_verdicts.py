"""File one night's judged pairs into pair-verdicts, each with its sampling chance.

One stage, one module. The router does not name it: the council reaches it
through the tenant that owns this judge (CLAUDE.md section 1a, "A router is the
sharpest case").

It calls no model and opens no socket. The units' verdict files say what each pair
was judged to be. What only the whole night can say is how many pairs of each slice
came back usable, and so what chance a pair of that slice had of being taken and
usable (`idhazh.similarity.sampling_chance`). This module fills those two columns in
and files the rows through the ledger door.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.council import metrics_sink
from idhazh.similarity.sampling_chance import with_sampling_chance
from idhazh.stages.common import LOG

#: What every file this stage files names as the module that wrote it.
PRODUCER: Final = __name__.partition(".")[2]


@dataclass(frozen=True, slots=True)
class FileReport:
    """What the collecting job did, for the caller to log."""

    date: str
    run_id: str
    shards_expected: int
    shards_present: int
    #: How many pair rows landed in the ledger. Zero when the family takes no new rows.
    rows_filed: int
    #: How many units shipped a reading of their own instrument.
    runners_reported: int


def _verdict_rows(path: Path) -> list[StorySimilarityPairVerdict]:
    """One shard's verdict file, every row through the contract.

    A row that no longer parses stops the read. These rows are about to be filed
    for good, so a silently short night cannot be told from a shard that had
    little to say.
    """
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    return [StorySimilarityPairVerdict.from_csv_row(raw) for raw in reader]


def _refuse_what_is_not_this_nights_own(
    rows: Sequence[StorySimilarityPairVerdict],
    readings: Sequence[ContentSimilarityJudgeMetrics],
    *,
    date: str,
    run_id: str,
) -> None:
    """Every row and every reading names this night and this run, and no pair is in twice."""
    named = {(row.date, row.run_id) for row in rows} | {
        (reading.date, reading.run_id) for reading in readings
    }
    strays = sorted(named - {(date, run_id)})
    if strays:
        raise ValueError(
            f"the units left rows naming {strays}, and this job settles {(date, run_id)}, so "
            "they came from another night's artifact and nothing is filed"
        )
    twice = sorted(key for key, count in Counter(row.pair_key for row in rows).items() if count > 1)
    if twice:
        raise ValueError(
            f"{len(twice)} pair(s) came back twice, so a slice would count them twice and "
            f"nothing is filed. The first is {twice[0]}"
        )


def stage_file_pair_verdicts(
    date: str,
    *,
    run_id: str,
    judge_id: str,
    shipped_root: Path,
    verdicts_dir: Path,
    identity: WriterIdentity,
    expected_shards: int,
    state_dir: Path,
) -> FileReport:
    """File every pair the units judged, with the chance its slice gave it.

    **A partly judged night files what its units returned.** A pair that left no
    row is a pair that was not usable, so it lowers its slice's chance, and the
    pairs that did come back are weighed up to stand for it. Nothing about a
    missing unit holds the night back, and the scheduler reads a night as done once
    it has any row.

    **Every row has to be this night's own, once.** A verdict file or a shipped
    reading that names another date or another run is from another night's artifact,
    and the ledger door would file it under the date it names and let its own run id
    stand, so a foreign row would skew its slice's chance unseen. A pair that appears
    twice would be counted twice. The whole night is refused before the first row is
    written, and nothing is dropped, because a dropped file reads as a lost unit and
    the scheduler would name the night again.

    **The instrument rows the units shipped are checked and counted here, not summed.**
    Each must be this night's own, and how many arrived is `runners_reported`. Their
    totals - how many pairs the night was dealt, how many agreed, how many were lost -
    are filed on the night's threshold-history row by `review_thresholds`, which reads
    the same shipped files, so the totals have one home.

    **`shipped_root`, `verdicts_dir` and `judge_id` are handed in rather than
    resolved here.** The two directories the units uploaded into belong to the
    venue and the slug belongs to the tenant, so a stage that spelled any of them
    would be a stage that only runs inside one venue under one name. Both
    directories hold one tenant's files, so what this reads is bounded by how many
    units the night fanned out to and never by what the archive has piled up
    (Guardrail #12).

    **`identity` is the council's own, for the job that saves the night's
    results.** The pairs go through the ledger door under it, with this stage named
    as their producer, so each file says which run, which attempt and which commit
    filed it. `run_id` is the council's own too, and each row carries it.
    """
    if expected_shards < 0:
        raise ValueError("expected_shards must not be negative")
    writer = WriterIdentity.model_validate(identity.model_dump() | {"producer": PRODUCER})

    present = sorted(path for path in verdicts_dir.glob("*.csv") if path.is_file())
    rows = [row for path in present for row in _verdict_rows(path)]
    readings = (
        metrics_sink.shipped_rows(
            shipped_root, judge_id=judge_id, contract=ContentSimilarityJudgeMetrics
        )
        if shipped_root.exists()
        else []
    )
    _refuse_what_is_not_this_nights_own(rows, readings, date=date, run_id=run_id)

    filed = ledger.persist(
        state_dir,
        with_sampling_chance(rows),
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
        covers=date,
        identity=writer,
    )
    report = FileReport(
        date=date,
        run_id=run_id,
        shards_expected=expected_shards,
        shards_present=len(present),
        rows_filed=len(rows) if filed else 0,
        runners_reported=len(readings),
    )
    LOG.info(
        "file-pair-verdicts date=%s run=%s shards=%s/%s filed=%s runners_reported=%s",
        report.date,
        report.run_id,
        report.shards_present,
        report.shards_expected,
        report.rows_filed,
        report.runners_reported,
    )
    return report
