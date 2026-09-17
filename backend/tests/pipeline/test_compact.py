"""The compaction: what it folds, where it puts it, and what it refuses.

Driven by a built segment store, never by the committed one. A built store
carries the cases the archive has never produced - a re-run's second attempt, a
day three days old, a directory nobody declared - and it costs the same on a
five-year archive as on a fresh clone (CLAUDE.md section 13).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from idhazh import ledger
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.runtime_counters import ServerJob
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.stages import compact

pytestmark = pytest.mark.contract

TODAY = "2026-09-17"
THREE_DAYS_OLD = "2026-09-14"
RUN = f"{TODAY}-900000001"
OLD_RUN = f"{THREE_DAYS_OLD}-900000002"


def _fingerprint(date: str, run_id: str, *, job: ServerJob, shard: int, **cells: object) -> str:
    """One host row rendered as a segment file's whole body."""
    return _fingerprints(_host_row(date, run_id, job=job, shard=shard, **cells))


def _host_row(
    date: str, run_id: str, *, job: ServerJob, shard: int, **cells: object
) -> dict[str, str]:
    row = HostFingerprintRow.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "job": job,
            "shard": shard,
            "fingerprint": "0123456789abcdef",
            "measured_at": f"{date}T00:00:00Z",
            **cells,
        }
    )
    return row.csv_row()


def _fingerprints(*rows: dict[str, str]) -> str:
    return ledger.render_file(HostFingerprintRow.csv_columns(), rows)


def _rollup(date: str, run_id: str, *, shard: int, span: RollupSpan, total_ms: int) -> str:
    row = SpanRollupRow.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "shard": shard,
            "span_name": span,
            "count": 1,
            "total_ms": total_ms,
        }
    )
    return ledger.render_file(SpanRollupRow.csv_columns(), [row.csv_row()])


def _write(state: Path, which: ledger.SegmentLedger, name: str, body: str) -> Path:
    path = state / ledger.SEGMENTS_DIRNAME / which.value / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _oracle_store(state: Path) -> None:
    """The six cases the row's oracle names, minus the two that refuse.

    (a) two segments for one date, (b) a segment for a date no head holds,
    (c) two segments sharing a key at different attempts, and (d) a segment
    three days old. The two refusals are built by the tests that assert them, so
    a test of the happy path cannot fail for a reason it is not about.
    """
    # (a) two writers, one date, one head.
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.PLAN.value}-00.csv",
        _fingerprint(TODAY, RUN, job=ServerJob.PLAN, shard=0, cpu_model="a plan machine"),
    )
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.ASSEMBLE.value}-00.csv",
        _fingerprint(TODAY, RUN, job=ServerJob.ASSEMBLE, shard=0, cpu_model="an assemble machine"),
    )
    # (c) one writer, two attempts, one key. The second attempt read a faster
    # machine, and it is the attempt that finished.
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _fingerprint(TODAY, RUN, job=ServerJob.WORK, shard=0, cpu_model="the attempt that died"),
    )
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-2-{ServerJob.WORK.value}-00.csv",
        _fingerprint(
            TODAY, RUN, job=ServerJob.WORK, shard=0, cpu_model="the attempt that finished"
        ),
    )
    # (d) a run three days dead, whose assemble never drained the store. Its
    # rows belong to its own day and not to today.
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{OLD_RUN}-1-{ServerJob.WORK.value}-01.csv",
        _fingerprint(THREE_DAYS_OLD, OLD_RUN, job=ServerJob.WORK, shard=1),
    )
    # (b) a ledger whose head is a month file, and a month this state has never
    # written.
    _write(
        state,
        ledger.SegmentLedger.SPAN_ROLLUP,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _rollup(TODAY, RUN, shard=0, span=RollupSpan.ITEM, total_ms=120),
    )


def test_an_empty_store_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """The normal path. A run whose predecessor drained the store finds nothing.

    This is the shape the catch-up in the `plan` job takes on almost every run,
    so it is the one that has to cost nothing and report honestly rather than
    inventing a date for a segment that was never there.
    """
    report = compact.stage_compact(tmp_path / ledger.STATE_DIRNAME)

    assert report == compact.CompactionReport(0, 0, 0, (), None)


def test_every_waiting_row_reaches_the_head_its_own_date_names(tmp_path: Path) -> None:
    """Cases (a) to (d), and the store is empty of them afterwards."""
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)

    report = compact.stage_compact(state)

    today_head = ledger.host_fingerprint_path(state, TODAY)
    old_head = ledger.host_fingerprint_path(state, THREE_DAYS_OLD)
    month_head = ledger.span_rollup_path(state, TODAY[:7])
    assert {row["job"] for row in _rows(today_head)} == {
        ServerJob.PLAN.value,
        ServerJob.ASSEMBLE.value,
        ServerJob.WORK.value,
    }
    assert [row["shard"] for row in _rows(old_head)] == ["1"]
    assert [row["span_name"] for row in _rows(month_head)] == [RollupSpan.ITEM.value]
    assert ledger.segment_files(state) == []
    assert report.segments_read == 6
    assert report.rows_merged == 6
    assert report.heads_written == tuple(
        sorted(
            (
                ledger.host_fingerprint_relpath(TODAY),
                ledger.host_fingerprint_relpath(THREE_DAYS_OLD),
                ledger.span_rollup_relpath(TODAY[:7]),
            )
        )
    )
    assert report.oldest_segment_date == THREE_DAYS_OLD


def test_the_higher_attempt_wins_the_cell_the_two_disagree_on(tmp_path: Path) -> None:
    """Case (c). Attempt 2 exists because attempt 1 did not finish.

    The ledger's own settlement keeps the first row it sees, which is right for
    two accounts of one attempt and exactly wrong for two attempts - it keeps
    the numbers from the job that died.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)

    report = compact.stage_compact(state)

    work = [
        row
        for row in _rows(ledger.host_fingerprint_path(state, TODAY))
        if row["job"] == ServerJob.WORK.value
    ]
    assert [row["cpu_model"] for row in work] == ["the attempt that finished"]
    assert report.rows_superseded == 1


def test_a_cell_only_the_earlier_attempt_filled_survives_the_later_one(tmp_path: Path) -> None:
    """A longer-lived first attempt can record something the second never reached.

    Whole-row replacement would throw that reading away, so the rule is per cell:
    the higher attempt wins what the two disagree on and nothing else.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _fingerprint(
            TODAY,
            RUN,
            job=ServerJob.WORK,
            shard=0,
            cpu_model="the attempt that died",
            memcpy_gib_s=11.5,
        ),
    )
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-2-{ServerJob.WORK.value}-00.csv",
        _fingerprint(
            TODAY, RUN, job=ServerJob.WORK, shard=0, cpu_model="the attempt that finished"
        ),
    )

    compact.stage_compact(state)

    (row,) = _rows(ledger.host_fingerprint_path(state, TODAY))
    assert row["cpu_model"] == "the attempt that finished"
    assert row["memcpy_gib_s"] == "11.5"


def test_a_cell_the_first_row_left_empty_is_filled_by_the_second(tmp_path: Path) -> None:
    """Two halves of one record, written by two steps, end as one row.

    A probe at job start and a counters read at job end fill different cells of
    the same record, so neither step has to read the other's file and neither
    row becomes mutable. The two rows do contest the cells they both fill -
    `fingerprint` and `measured_at` are required, so every pair of host rows
    contests something - and that is counted. What must not happen is the second
    row's own cell being counted away with it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _fingerprints(
            _host_row(TODAY, RUN, job=ServerJob.WORK, shard=0, cpu_model="one machine"),
            _host_row(TODAY, RUN, job=ServerJob.WORK, shard=0, memcpy_gib_s=9.25),
        ),
    )

    report = compact.stage_compact(state)

    (row,) = _rows(ledger.host_fingerprint_path(state, TODAY))
    assert row["cpu_model"] == "one machine"
    assert row["memcpy_gib_s"] == "9.25"
    assert report.rows_merged == 2
    assert report.rows_superseded == 1


def test_a_second_compaction_leaves_every_head_byte_identical(tmp_path: Path) -> None:
    """Idempotence is the contract, and a byte comparison is the only honest check."""
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)

    compact.stage_compact(state)
    heads = {
        path: path.read_bytes()
        for path in sorted(state.rglob("*.csv"))
        if ledger.SEGMENTS_DIRNAME not in path.parts
    }
    again = compact.stage_compact(state)

    assert {path: path.read_bytes() for path in heads} == heads
    assert again == compact.CompactionReport(0, 0, 0, (), None)


def test_folding_the_same_segments_twice_changes_nothing(tmp_path: Path) -> None:
    """The recovery path: a pass that wrote its heads and then lost the push.

    The segments are still there on the next run, so they are folded onto a head
    that already holds them. Same key, same attempt, so the incumbent stays.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)
    compact.stage_compact(state)
    once = ledger.host_fingerprint_path(state, TODAY).read_bytes()
    _oracle_store(state)

    report = compact.stage_compact(state)

    assert ledger.host_fingerprint_path(state, TODAY).read_bytes() == once
    assert report.rows_merged == report.rows_superseded == 6


def test_a_filename_the_grammar_cannot_place_stops_the_read(tmp_path: Path) -> None:
    """Case (e). A glob that passed over it would leave those rows unread.

    The store holds one kind of file written by one kind of writer, so a name
    outside the grammar means something else is writing there.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)
    stray = _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        "host-fingerprint.csv",
        _fingerprint(TODAY, RUN, job=ServerJob.WORK, shard=7),
    )

    with pytest.raises(ValueError, match=stray.name):
        compact.stage_compact(state)


def test_a_directory_naming_an_undeclared_ledger_stops_the_read(tmp_path: Path) -> None:
    """Case (f). A writer that arrived without anyone choosing it.

    That is the failure the whole segment store exists to stop, so it refuses
    the read rather than folding the four directories it does recognise.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    _oracle_store(state)
    (state / ledger.SEGMENTS_DIRNAME / "seen").mkdir(parents=True)

    with pytest.raises(ValueError, match="seen"):
        compact.stage_compact(state)


def test_the_store_top_may_hold_the_file_that_keeps_it_in_a_checkout(tmp_path: Path) -> None:
    """`state/segments/.gitkeep` is not a segment and must not be read as one.

    Git carries no empty directory, and `REFRESH_PATHS` hands this one back to
    the tip - so a clone without it would have nothing to hand back.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    (state / ledger.SEGMENTS_DIRNAME).mkdir(parents=True)
    (state / ledger.SEGMENTS_DIRNAME / ".gitkeep").write_text("", encoding="utf-8")

    assert ledger.segment_files(state) == []
    assert compact.stage_compact(state).segments_read == 0


def test_a_segment_row_the_contract_cannot_read_names_the_row(tmp_path: Path) -> None:
    """The one place this does not degrade, and the refusal has to be actionable.

    A segment is written from a validated model one step earlier, so a row that
    will not parse means the writer and the reader disagree about the shape -
    and folding past it is how a ledger quietly loses a column.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    body = _fingerprint(TODAY, RUN, job=ServerJob.WORK, shard=0)
    header, row = body.splitlines()
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        f"{header}\n{row.replace('0123456789abcdef', 'not-a-fingerprint')}\n",
    )

    with pytest.raises(ValueError, match="row 2"):
        compact.stage_compact(state)


def test_the_segment_name_carries_the_four_cells_that_make_it_unique(tmp_path: Path) -> None:
    """The path a writer uses and the name the compaction reads are one grammar.

    There is no date element: the run id opens on the date and the head is chosen
    by the row's own date cell, so a second date would be a cell filled for
    nothing.
    """
    path = ledger.segment_path(
        tmp_path / ledger.STATE_DIRNAME,
        ledger.SegmentLedger.ITEM_HEALTH,
        run_id=RUN,
        attempt=2,
        job=ServerJob.WORK,
        shard=3,
    )

    assert path.name == f"{RUN}-2-{ServerJob.WORK.value}-03.csv"
    assert path.parent.name == ledger.ITEM_HEALTH_DIRNAME
    assert ledger.parse_segment_name(path) == ledger.SegmentName(
        run_id=RUN, attempt=2, job=ServerJob.WORK, shard=3
    )
