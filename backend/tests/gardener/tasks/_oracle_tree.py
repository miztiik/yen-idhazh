"""Which one tree do the old prune passes and the gardener's retention tasks both run over?

A fixed checkout, with files on both sides of every window the committed
config drew on `TODAY`, so the files a task takes can be held to the files the
pass it replaced took from the same tree. Every ledger file is written by that
ledger's own producer, so a task that read a file differently from the pass
would read a real file differently.

The pass side was recorded once, before the passes were deleted, into
`tests/fixtures/gardener/prune-oracle/removals.json`; this builder is what that
record was taken over, so changing a file here changes what the record means.

Since then six ledgers - item-health, scores, host-fingerprint, the
counterfactual scores, the first sights and feed health - moved off CSV onto
the ledger door, so this tree files their rows under `state/raw/`, the way
their writers file them now. The record's paths under their old trees name
files this tree no longer holds, and `test_every_task_takes_what_its_pass_took.py`
says what that leaves each task answering for.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Final

from conftest import (
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    read_text,
    seed_host_fingerprint,
    seed_item_health,
    seed_scores,
    writer_identity,
)
from retention._trees import TERMINAL_ORDER, health_row

from idhazh import ledger, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.seen import SeenRow
from idhazh.stages import plan

#: The day every window is measured from. Late enough that each fourteen-month
#: window has months on both sides of it, and the 390-day one days on both sides.
TODAY: Final = date(2027, 11, 15)

#: The run a task's own report row is filed under.
RUN_ID: Final = "2027-11-15-19000000001"

#: What each task's own removal set was recorded into, by the pass it replaced.
REMOVALS: Final = FIXTURES_DIR / "gardener" / "prune-oracle" / "removals.json"

#: Where the published tree and its copies sit, relative to the checkout.
DIGEST: Final = "frontend/public/digest"
TELEMETRY: Final = "frontend/public/telemetry"

#: The months the month-windowed ledgers hold: two past the fourteen-month
#: window, the oldest month it keeps, and the month `TODAY` sits in.
MONTHS: Final = ("2026-08", "2026-09", "2026-10", "2027-11")

SEEN_DAYS: Final = (
    "2026-01-01",
    "2027-08-15",
    "2027-08-16",
    "2027-08-17",
    "2027-11-15",
    "2027-11-20",
)
COUNTERFACTUAL_DAYS: Final = ("2027-10-14", "2027-10-15", "2027-10-16", "2027-11-15", "2027-11-18")
TRACE_RUNS: Final = ("2027-11-07-1", "2027-11-08-1", "2027-11-09-1", "2027-11-20-1")
FRAGMENT_DAYS: Final = ("2026-10-19", "2026-10-20", "2026-10-21", "2027-11-15")

#: Each published day and the visuals filed in it. The cutoff is 390 days back,
#: 2026-10-21, and a day before it is past the window.
VISUAL_DAYS: Final = {
    "2026-10-19": ("ai-0001.json", "ai-0002.json"),
    "2026-10-20": ("ai-0003.json",),
    "2026-10-21": ("ai-0004.json",),
    "2027-11-15": ("ai-0005.json",),
}

#: Trial traces under declared case roots. Each is dated by its path: a day
#: past the window is old, an undated name is kept, and a day ahead of `TODAY`
#: stays.
TRIAL_FILES: Final = (
    "raw/traces/pipeline-tests/production-settings/2027/08/17/old.jsonl",
    "raw/traces/pipeline-tests/production-settings/2027/08/18/kept.jsonl",
    "raw/traces/pipeline-tests/production-settings/2027/11/10/outside-range.jsonl",
    "raw/traces/pipeline-tests/production-settings/notes.txt",
    "raw/traces/pipeline-tests/production-settings/2027/12/01/future.jsonl",
    "raw/traces/pipeline-tests/no-visual-plan/2026/01/01/old.jsonl",
)

#: The browser's copies of the item-health months, and one whose source month is
#: already gone.
PUBLIC_MONTHS: Final = ("2026-07", *MONTHS)


def build(root: Path) -> Path:
    """The whole tree under `root`, a checkout. Returns `root`."""
    state = root / ledger.STATE_DIRNAME
    for day in SEEN_DAYS:
        _seen_day(state, day)
    for day in COUNTERFACTUAL_DAYS:
        _counterfactual_day(state, day)
    for run_id in TRACE_RUNS:
        _trace(state, run_id)
    for index, month in enumerate(MONTHS):
        _feed_health(state, month, index)
        _host_fingerprint(state, month, index)
    for index, month in enumerate(MONTHS[:3]):
        _score_month(state, month, index)
    for day in FRAGMENT_DAYS:
        fragment = state / "digest-fragments" / day[:4] / day[5:7] / day[8:] / f"{day}-1.json"
        _write(fragment, "{}\n")
    for day, visuals in VISUAL_DAYS.items():
        folder = root / DIGEST / day[:4] / day[5:7] / day[8:]
        _write(folder / "digest.json", json.dumps({"date": day}) + "\n")
        _write(folder / "run.json", "{}\n")
        for name in visuals:
            (folder / name).write_bytes(b"x" * 1000)
    for relative in TRIAL_FILES:
        _write(state / relative, "{}\n")
    for index, month in enumerate(MONTHS):
        _item_health_month(state, month, index)
    for month in PUBLIC_MONTHS:
        _write(root / TELEMETRY / f"{month}.csv", "version,date\n")
    return root


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _seen_day(state: Path, day: str) -> None:
    ledger.append_seen(
        state,
        day,
        [
            SeenRow(
                version=SeenRow.schema_version(),
                url_key=hashlib.sha256(day.encode()).hexdigest(),
                first_seen_at=f"{day}T06:00:00Z",
                first_seen_run=f"{day}-1",
            )
        ],
        identity=writer_identity(f"{day}-1", job=ServerJob.PLAN, producer=plan.PRODUCER),
    )


def _counterfactual_day(state: Path, day: str) -> None:
    ledger.persist(
        state,
        [
            CounterfactualScoreRow(
                version=CounterfactualScoreRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                vertical="ai",
                url_key=hashlib.sha256(day.encode()).hexdigest(),
                taken=True,
                lens_id="chips",
                lens_bonus=0.3,
                lens_multiplier=1.25,
                score_committed=1.2,
                score_counterfactual=1.275,
            )
        ],
        ledger=LedgerName.COUNTERFACTUAL_SCORES,
        covers=day,
        identity=writer_identity(f"{day}-1", job=ServerJob.PLAN, producer=plan.PRODUCER),
    )


def _trace(state: Path, run_id: str) -> None:
    path = telemetry.committed_trace_path(
        state, run_id=run_id, attempt=1, job=ServerJob.WORK, shard=0
    )
    record = telemetry.Span(
        trace_id="unattributed",
        span_id="item-000",
        parent_id=None,
        name=telemetry.SpanName.ITEM,
        kind=telemetry.SpanKind.SPAN,
        started_at=f"{run_id[:10]}T02:20:00Z",
        duration_ms=1234,
        attributes={"run_id": run_id, "shard": 0},
    ).as_record()
    _write(path, json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _feed_health(state: Path, month: str, index: int) -> None:
    day = f"{month}-11"
    ledger.persist(
        state,
        [
            FeedHealthRow(
                version=FeedHealthRow.schema_version(),
                run_id=f"{day}-1",
                date=day,
                feed_id=f"example-{index:02d}",
                checked_at=f"{day}T06:00:00Z",
                outcome=FetchOutcome.OK,
                status=200,
                items=3,
                detail=None,
            )
        ],
        ledger=LedgerName.FEED_HEALTH,
        covers=day,
        identity=writer_identity(f"{day}-1", job=ServerJob.PLAN, producer=plan.PRODUCER),
    )


def _host_fingerprint(state: Path, month: str, index: int) -> None:
    day = f"{month}-11"
    seed_host_fingerprint(
        state,
        [
            HostFingerprintRow(
                version=HostFingerprintRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                shard=index,
                cpu_model="AMD EPYC 7763 64-Core Processor",
            )
        ],
    )


def _score_row(*, day: str, number: int) -> EvalRow:
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.05 + (number % 10) / 10, 4)
    seed = f"{day}-{number}"
    band = (
        ConfidenceBand.HIGH
        if faithfulness >= 0.80
        else ConfidenceBand.MEDIUM
        if faithfulness >= 0.50
        else ConfidenceBand.LOW
    )
    return EvalRow.model_validate(
        {
            **base,
            "date": day,
            "run_id": f"{day}-1",
            "item_id": f"ai-{number:04d}",
            "url_key": hashlib.sha256(seed.encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{seed}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": band.value,
            "unsupported_numbers": number % 3,
            "hedge_dropped": number % 4 == 0,
            "extraction_suspect": number % 5 == 0,
            "source_words_before_cap": 1320,
            "source_words": 1320 - (number % 2) * 40,
            "score_ms": 1000 + number,
            "scored_at": f"{day}T06:18:02Z",
        }
    )


def _score_month(state: Path, month: str, index: int) -> None:
    for day_of_month in (4, 17):
        day = f"{month}-{day_of_month:02d}"
        seed_scores(
            state,
            [_score_row(day=day, number=index * 100 + offset) for offset in range(3)],
            run_id=f"{day}-1",
        )


def _item_health_month(state: Path, month: str, index: int) -> None:
    for day_of_month in (4, 17):
        day = f"{month}-{day_of_month:02d}"
        rows = [
            health_row(day=day, run=1, number=index * 100 + position, stage=stage)
            for position, stage in enumerate(TERMINAL_ORDER)
        ]
        rows.append(health_row(day=day, run=2, number=index * 100 + 50, stage=ItemStage.PUBLISH))
        seed_item_health(state, day, rows)


def files_under(root: Path) -> dict[str, bytes]:
    """Every file under the checkout, by its repository path, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
