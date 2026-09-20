"""The compaction: what it folds, where it puts it, and what it refuses.

Driven by a built segment store, never by the committed one. A built store
carries the cases the archive has never produced - a re-run's second attempt, a
day three days old, a directory nobody declared - and it costs the same on a
five-year archive as on a fresh clone (CLAUDE.md section 13).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import Contract, ServerJob, derive_url_key
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.contracts.validation_row import (
    LeaderboardProvenance,
    ValidationRow,
    ValidationVerdict,
)
from idhazh.stages import compact

pytestmark = pytest.mark.contract

TODAY = "2026-09-17"
THREE_DAYS_OLD = "2026-09-14"
RUN = f"{TODAY}-900000001"
OLD_RUN = f"{THREE_DAYS_OLD}-900000002"

#: Every job of one full digest run that draws its own machine and records it:
#: one plan, eight work shards, one assemble. Ten writers, ten machines, and on
#: 2026-09-16 the day file they all appended to came back header-only.
WRITERS: Final[tuple[tuple[ServerJob, int], ...]] = (
    (ServerJob.PLAN, 0),
    *tuple((ServerJob.WORK, shard) for shard in range(8)),
    (ServerJob.ASSEMBLE, 0),
)

def _fingerprint(date: str, run_id: str, *, job: ServerJob, shard: int, **cells: object) -> str:
    """One host row rendered as a segment file's whole body."""
    return _fingerprints(_host_row(date, run_id, job=job, shard=shard, **cells))


def _host_model(
    date: str, run_id: str, *, job: ServerJob, shard: int, **cells: object
) -> HostFingerprintRow:
    return HostFingerprintRow.model_validate(
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


def _host_row(
    date: str, run_id: str, *, job: ServerJob, shard: int, **cells: object
) -> dict[str, str]:
    return _host_model(date, run_id, job=job, shard=shard, **cells).csv_row()


def _fingerprints(*rows: dict[str, str]) -> str:
    return ledger.render_file(HostFingerprintRow.csv_columns(), rows)


def _rollup_row(
    date: str, run_id: str, *, shard: int, span: RollupSpan, total_ms: int
) -> dict[str, str]:
    return SpanRollupRow.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "shard": shard,
            "span_name": span,
            "count": 1,
            "total_ms": total_ms,
        }
    ).csv_row()


def _rollups(*rows: dict[str, str]) -> str:
    return ledger.render_file(SpanRollupRow.csv_columns(), rows)


def _rollup(date: str, run_id: str, *, shard: int, span: RollupSpan, total_ms: int) -> str:
    """One fold rendered as a segment file's whole body."""
    return _rollups(_rollup_row(date, run_id, shard=shard, span=span, total_ms=total_ms))


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


def test_ten_writers_of_one_run_land_ten_rows_in_one_machine_day(tmp_path: Path) -> None:
    """A full run's ten machines, through the writer production calls, into one head.

    Driven through `ledger.write_segment` rather than through a built file,
    because what this asks is whether the ten jobs of one run can write at all
    without taking each other's path - and a hand-built name would answer a
    question about this test instead.

    `state/host-fingerprint/2026/09/16.csv` is header-only in this repository:
    ten runners appended to it, the pushes raced, and the day came back empty.
    Ten distinct `(job, shard)` pairs and no repeat is that failure made
    checkable.

    What it cannot settle is whether ten real runners racing produce this - the
    first live run is that check.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    for job, shard in WRITERS:
        ledger.write_segment(
            state,
            ledger.SegmentLedger.HOST_FINGERPRINT,
            [_host_model(TODAY, RUN, job=job, shard=shard, cpu_model=f"{job.value}-{shard}")],
            run_id=RUN,
            attempt=1,
            job=job,
            shard=shard,
        )

    waiting = ledger.segment_files(state, ledger.SegmentLedger.HOST_FINGERPRINT)
    assert len(waiting) == len(WRITERS), "one writer, one file, and no two writers share one"

    report = compact.stage_compact(state)

    head = ledger.host_fingerprint_path(state, TODAY)
    pairs = [(row["job"], int(row["shard"])) for row in _rows(head)]
    assert sorted(pairs) == sorted((job.value, shard) for job, shard in WRITERS)
    assert len(set(pairs)) == len(WRITERS), "a repeated pair is one machine counted twice"
    assert report.rows_superseded == 0, "ten distinct keys settle nothing against each other"
    assert report.segments_read == len(WRITERS)
    assert report.heads_written == (ledger.host_fingerprint_relpath(TODAY),)
    assert not ledger.segment_files(state), "a folded segment is removed, not left behind"


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


def test_two_dates_of_one_month_fold_into_one_head_carrying_both(tmp_path: Path) -> None:
    """The span fold files by month, so two dates share a head and must stay apart on it.

    A shard that runs across midnight leaves a segment dated yesterday for a
    compaction that runs today, and both dates are in the same month for all but
    one night a month. Every shard of both runs folds into `2026-09.csv`, so the
    head is the one file a whole month of runs reaches.

    Unique across `SPAN_ROLLUP_KEY` is the half that matters. A repeated key is
    one shard's spans counted twice, and the console divides that number, so a
    doubled row does not look like an error - it looks like a slower run.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    yesterday = "2026-09-16"
    overnight = f"{yesterday}-900000003"
    for shard in (0, 1):
        _write(
            state,
            ledger.SegmentLedger.SPAN_ROLLUP,
            f"{overnight}-1-{ServerJob.WORK.value}-{shard:02d}.csv",
            _rollup(
                yesterday, overnight, shard=shard, span=RollupSpan.ITEM, total_ms=90 + shard
            ),
        )
    _write(
        state,
        ledger.SegmentLedger.SPAN_ROLLUP,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _rollups(
            _rollup_row(TODAY, RUN, shard=0, span=RollupSpan.ITEM, total_ms=120),
            _rollup_row(TODAY, RUN, shard=0, span=RollupSpan.ROBOTS, total_ms=8),
        ),
    )

    report = compact.stage_compact(state)

    assert report.heads_written == (ledger.span_rollup_relpath(TODAY[:7]),)
    rows = _rows(ledger.span_rollup_path(state, TODAY[:7]))
    assert {row["date"] for row in rows} == {yesterday, TODAY}
    keys = [tuple(row[name] for name in ledger.SPAN_ROLLUP_KEY) for row in rows]
    assert len(keys) == 4, f"one fold went missing or arrived twice: {keys}"
    assert len(set(keys)) == len(keys), f"two rows share a key: {keys}"
    assert ledger.segment_files(state) == []


def test_a_fold_left_over_a_month_boundary_reaches_the_month_its_own_rows_name(
    tmp_path: Path,
) -> None:
    """The case no real run can be asked to produce: the night the month changes.

    A shard that starts at 23:59 UTC on the last of the month writes its segment
    on one date and the compaction that reads it runs on another - and once a
    month those two dates are in different months. Routing is off each row's own
    `date` cell rather than off the clock the compaction runs on, so August's
    fold reaches August's head and September's reaches September's.

    Built here for the reason the file's own heading gives: the archive has never
    produced this night and cannot be made to, and a compaction that read its
    own clock would pass every other test in this file.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    last_of_august = "2026-08-31"
    first_of_september = "2026-09-01"
    before_midnight = f"{last_of_august}-900000004"
    after_midnight = f"{first_of_september}-900000005"
    _write(
        state,
        ledger.SegmentLedger.SPAN_ROLLUP,
        f"{before_midnight}-1-{ServerJob.WORK.value}-00.csv",
        _rollup(
            last_of_august, before_midnight, shard=0, span=RollupSpan.ITEM, total_ms=61
        ),
    )
    _write(
        state,
        ledger.SegmentLedger.SPAN_ROLLUP,
        f"{after_midnight}-1-{ServerJob.WORK.value}-00.csv",
        _rollup(
            first_of_september, after_midnight, shard=0, span=RollupSpan.ITEM, total_ms=59
        ),
    )

    report = compact.stage_compact(state)

    assert report.heads_written == tuple(
        sorted(
            (
                ledger.span_rollup_relpath(last_of_august[:7]),
                ledger.span_rollup_relpath(first_of_september[:7]),
            )
        )
    )
    august = _rows(ledger.span_rollup_path(state, last_of_august[:7]))
    september = _rows(ledger.span_rollup_path(state, first_of_september[:7]))
    assert [(row["date"], row["total_ms"]) for row in august] == [(last_of_august, "61")]
    assert [(row["date"], row["total_ms"]) for row in september] == [(first_of_september, "59")]
    assert report.oldest_segment_date == last_of_august


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

    A probe at job start and a job-clock read at job end fill different cells of
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


def test_a_segment_written_before_a_column_existed_still_folds(tmp_path: Path) -> None:
    """The widening, driven where it actually breaks: a segment, under its own header.

    A run that opened before a column was added leaves its segment behind, and
    the next run reads that file with the wider contract. A build that cannot
    place it is not widening the ledger, it is abandoning the rows already in it
    - and the rows it abandons are the ones a failed run left, which are the
    only reason the store has a catch-up at all.

    **The head is the wrong file to drive this with.** A head is re-filed under
    the current columns before anything reads it, and a short line under a wide
    header is padded by the CSV reader, so a head-driven case passes whether or
    not the contract can read a narrow row. A segment carries its own header and
    nothing pads it, so the cell count below is an assertion that can fail.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    added = ("server_prompt_tokens", "server_prompt_seconds")
    cells = _host_row(
        TODAY, RUN, job=ServerJob.WORK, shard=0, cpu_model="AMD EPYC 7763", job_seconds=5550
    )
    narrow = tuple(name for name in HostFingerprintRow.csv_columns() if name not in added)
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        ledger.render_file(narrow, [cells]),
    )

    report = compact.stage_compact(state)

    header, *body = (
        ledger.host_fingerprint_path(state, TODAY).read_text(encoding="utf-8").splitlines()
    )
    columns = header.split(",")
    assert columns == list(HostFingerprintRow.csv_columns())
    assert report.rows_merged == 1
    written = dict(zip(columns, next(csv.reader(body)), strict=True))
    assert [written[name] for name in added] == ["", ""], "a reading nobody took is empty"
    assert written["job_seconds"] == "5550", "the widening may not cost the cells already there"
    assert HostFingerprintRow.from_csv_row(written).server_prompt_tokens is None


def _a_column_that_may_be_missing(model: type[Contract]) -> str:
    """One cell this row can be without, derived so a rename cannot rot the case."""
    return next(name for name, field in model.model_fields.items() if field.default is None)


def _folds_without(
    state: Path,
    which: ledger.SegmentLedger,
    job: ServerJob,
    columns: tuple[str, ...],
    cells: dict[str, str],
    dropped: str,
) -> dict[str, str]:
    """Fold one segment written before `dropped` existed, and hand back the head's row."""
    narrow = tuple(name for name in columns if name != dropped)
    _write(state, which, f"{RUN}-1-{job.value}-00.csv", ledger.render_file(narrow, [cells]))

    compact.stage_compact(state)

    header, *body = (
        ledger.segment_head(state, which, TODAY).path.read_text(encoding="utf-8").splitlines()
    )
    return dict(zip(header.split(","), next(csv.reader(body)), strict=True))


def test_a_verdict_segment_written_before_a_column_existed_still_folds(tmp_path: Path) -> None:
    """And on the ledger a candidate's verdict lands in, which `validate.yml` writes."""
    written = _verdict(TODAY, RUN, model_id="gemma-4-e4b", qualified=True)
    dropped = _a_column_that_may_be_missing(ValidationRow)

    row = _folds_without(
        tmp_path / ledger.STATE_DIRNAME,
        ledger.SegmentLedger.VALIDATION,
        ServerJob.DECIDE,
        ValidationRow.csv_columns(),
        written.csv_row(),
        dropped,
    )

    assert row[dropped] == "", "a prior nobody published is empty, not zero"
    assert ValidationRow.from_csv_row(row).model_id == "gemma-4-e4b"


def test_a_segment_missing_the_cell_that_would_read_as_a_reading_is_refused(
    tmp_path: Path,
) -> None:
    """`flags` is the one column an absent cell may not stand in for.

    An empty `flags` is a reading - it says the host reported none of the watched
    instruction-set flags - so a file that never carried the column would arrive
    as that reading and nothing downstream could tell the two apart. Every other
    cell here either comes back absent or fails its own field parser.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    columns = tuple(name for name in HostFingerprintRow.csv_columns() if name != "flags")
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        ledger.render_file(columns, [_host_row(TODAY, RUN, job=ServerJob.WORK, shard=0)]),
    )

    with pytest.raises(ValueError, match="flags"):
        compact.stage_compact(state)


def test_a_segment_carrying_a_column_this_build_cannot_place_is_refused(tmp_path: Path) -> None:
    """A file wider than the contract is a writer this build has not met.

    Reading it onto the columns we know would drop that cell and fold on, which
    is how a ledger loses a column with nothing printed and exit 0.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    unplaceable = "server_decode_tokens"
    cells = _host_row(TODAY, RUN, job=ServerJob.WORK, shard=0) | {unplaceable: "12"}
    _write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        ledger.render_file((*HostFingerprintRow.csv_columns(), unplaceable), [cells]),
    )

    with pytest.raises(ValueError, match=unplaceable):
        compact.stage_compact(state)


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

def _census(
    date: str, run_id: str, *, item: str, job: ServerJob | None = None, **cells: object
) -> str:
    """One item-census row rendered as a segment file's whole body."""
    url = f"https://example.com/{item}"
    row = ItemHealthRow.model_validate(
        {
            "version": ItemHealthRow.schema_version(),
            "date": date,
            "run_id": run_id,
            "item_id": item,
            "source_id": "wire",
            "url_key": derive_url_key(url),
            "canonical_url": url,
            "vertical": "ai",
            "stage": ItemStage.PUBLISH,
            "outcome": ItemOutcome.OK,
            **({"job": job, "shard": 0} if job is not None else {}),
            **cells,
        }
    )
    return ledger.render_file(ItemHealthRow.csv_columns(), [row.csv_row()])


def _digests(*digests: str) -> str:
    """Score-index rows rendered as a segment file's whole body."""
    rows = [
        ObservationIndexRow.model_validate(
            {"version": ObservationIndexRow.schema_version(), "observation_digest": digest}
        ).csv_row()
        for digest in digests
    ]
    return ledger.render_file(ObservationIndexRow.csv_columns(), rows)


def test_two_jobs_that_recorded_one_item_leave_one_census_row(tmp_path: Path) -> None:
    """The reason the item census moved onto segments at all.

    A work shard records an item as it settles and `assemble` records the whole
    day afterwards, so two writers describe one item on one run. They used to
    append to one day file, and the count of rows in that file feeds a feed's
    share of the day and the day's own metrics - so a repeat there is a number a
    reader sees, not an untidy file.
    """
    state = tmp_path / "state"
    _write(
        state,
        ledger.SegmentLedger.ITEM_HEALTH,
        f"{RUN}-1-{ServerJob.WORK.value}-03.csv",
        _census(TODAY, RUN, item="ai-01", job=ServerJob.WORK),
    )
    _write(
        state,
        ledger.SegmentLedger.ITEM_HEALTH,
        f"{RUN}-1-{ServerJob.ASSEMBLE.value}-00.csv",
        _census(TODAY, RUN, item="ai-01"),
    )

    report = compact.stage_compact(state)

    rows = _rows(ledger.item_health_path(state, TODAY))
    assert len(rows) == 1, "one item, one run, one row"
    assert report.rows_superseded == 1
    assert ledger.segment_files(state) == []


def test_the_row_that_names_a_job_beats_the_row_that_does_not(tmp_path: Path) -> None:
    """Which of two writers wins has to be the one that knows more, not the one sorted first.

    `ITEM_HEALTH_KEY` has no `job` cell, so both rows are the same record and
    the fold has to choose. A work shard stamps the job and the shard it ran as
    - the one moment either is known - and `assemble` runs once for the whole
    day and leaves both empty. Segment files are read in filename order, and
    `assemble` sorts before `work`, so without a rule the emptier row would win
    every time and the pair that takes an item to the machine that read it would
    be gone.
    """
    state = tmp_path / "state"
    _write(
        state,
        ledger.SegmentLedger.ITEM_HEALTH,
        f"{RUN}-1-{ServerJob.ASSEMBLE.value}-00.csv",
        _census(TODAY, RUN, item="ai-01"),
    )
    _write(
        state,
        ledger.SegmentLedger.ITEM_HEALTH,
        f"{RUN}-1-{ServerJob.WORK.value}-03.csv",
        _census(TODAY, RUN, item="ai-01", job=ServerJob.WORK),
    )

    compact.stage_compact(state)

    kept = _rows(ledger.item_health_path(state, TODAY))[0]
    assert kept["job"] == ServerJob.WORK.value
    assert kept["shard"] == "0"


def test_a_score_index_row_is_filed_by_the_run_that_carried_it(tmp_path: Path) -> None:
    """The index has no date of its own, so the segment's run id is where the date comes from.

    Every other ledger here reads the date off the row. `ObservationIndexRow` is
    a stamp and a digest - it is filed beside the scores it describes and never
    says which day that is - so the fold takes the date from the run that wrote
    the segment. A run id opens on its own date, and the only writer of an eval
    row files it under the run's date too, so the two always agree.
    """
    state = tmp_path / "state"
    _write(
        state,
        ledger.SegmentLedger.SCORE_INDEX,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _digests("a" * 64),
    )
    _write(
        state,
        ledger.SegmentLedger.SCORE_INDEX,
        f"{OLD_RUN}-1-{ServerJob.WORK.value}-00.csv",
        _digests("b" * 64),
    )

    compact.stage_compact(state)

    today = _rows(ledger.score_index_path(state, TODAY))
    older = _rows(ledger.score_index_path(state, THREE_DAYS_OLD))
    assert [row["observation_digest"] for row in today] == ["a" * 64]
    assert [row["observation_digest"] for row in older] == ["b" * 64]


def test_one_digest_written_by_two_jobs_is_indexed_once(tmp_path: Path) -> None:
    """The index is what the eval writer reads to know a measurement is already held.

    A digest listed twice would cost nothing but bytes today. It is settled
    anyway because `OBSERVATION_INDEX_KEY` is the whole row: two index rows for
    one digest carry no cell that can disagree, so the fold has nothing to weigh
    and keeping both would only make the file grow with the runs.
    """
    state = tmp_path / "state"
    _write(
        state,
        ledger.SegmentLedger.SCORE_INDEX,
        f"{RUN}-1-{ServerJob.WORK.value}-00.csv",
        _digests("a" * 64),
    )
    _write(
        state,
        ledger.SegmentLedger.SCORE_INDEX,
        f"{RUN}-1-{ServerJob.ASSEMBLE.value}-00.csv",
        _digests("a" * 64),
    )

    compact.stage_compact(state)

    rows = _rows(ledger.score_index_path(state, TODAY))
    assert [row["observation_digest"] for row in rows] == ["a" * 64]


def _verdict(
    date: str, run_id: str, *, model_id: str, qualified: bool, **cells: object
) -> ValidationRow:
    return ValidationRow.model_validate(
        {
            "version": ValidationRow.schema_version(),
            "model_id": model_id,
            "is_incumbent": False,
            "selected": qualified,
            "leaderboard_hhem": None,
            "leaderboard_provenance": LeaderboardProvenance.NOT_REPORTED,
            "measured_hhem": 0.9,
            "articles": 30,
            "date": date,
            "run_id": run_id,
            "commit_sha": "c" * 40,
            "runner": "ubuntu-latest",
            "verdict": (
                ValidationVerdict.QUALIFIED if qualified else ValidationVerdict.NOT_QUALIFIED
            ),
            "detail": f"every gate passed on 30 frozen articles for {model_id}",
            **cells,
        }
    )


def test_two_candidates_of_one_date_land_two_rows_in_one_verdict_day(tmp_path: Path) -> None:
    """The row's oracle. Two dispatches, two filenames, one day head, both verdicts.

    Driven through `ledger.write_segment`, the call both decide stages make,
    because what this asks is whether two candidates dispatched at once can
    record their verdicts without taking each other's path. They shared
    `state/validation-<date>.csv` until 2026-09-18, and `merge=union` was the
    only thing keeping the two apart - which Row #12 deletes.

    What it cannot settle is whether two real dispatches on two runners produce
    this; the first live pair is that check.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    other_run = f"{TODAY}-900000003"
    for run_id, model_id, qualified in (
        (RUN, "gemma-4-e4b", True),
        (other_run, "qwen3-9b", False),
    ):
        ledger.write_segment(
            state,
            ledger.SegmentLedger.VALIDATION,
            [_verdict(TODAY, run_id, model_id=model_id, qualified=qualified)],
            run_id=run_id,
            attempt=1,
            job=ServerJob.DECIDE,
            shard=0,
        )

    waiting = ledger.segment_files(state, ledger.SegmentLedger.VALIDATION)
    assert len({path.name for path in waiting}) == 2, "two candidates, two filenames"

    report = compact.stage_compact(state)

    head = ledger.validation_path(state, TODAY)
    assert head == state / "validation" / "2026" / "09" / "17.csv"
    rows = _rows(head)
    assert sorted((row["run_id"], row["model_id"]) for row in rows) == sorted(
        [(RUN, "gemma-4-e4b"), (other_run, "qwen3-9b")]
    )
    assert report.rows_superseded == 0, "two candidates settle nothing against each other"
    assert report.heads_written == (ledger.validation_relpath(TODAY),)
    assert not ledger.segment_files(state), "a folded segment is removed, not left behind"


def test_two_dispatches_of_one_candidate_stay_two_verdicts(tmp_path: Path) -> None:
    """One model judged twice in a day is two facts, so the run id is in the key.

    The ledger this replaced held exactly that pair: four rows on 2026-08-22,
    two models judged by two runs against two trees. A key of date and model
    alone would keep one of each and lose the other tree's answer.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    later_run = f"{TODAY}-900000004"
    for run_id in (RUN, later_run):
        ledger.write_segment(
            state,
            ledger.SegmentLedger.VALIDATION,
            [_verdict(TODAY, run_id, model_id="gemma-4-e4b", qualified=True)],
            run_id=run_id,
            attempt=1,
            job=ServerJob.DECIDE,
            shard=0,
        )

    compact.stage_compact(state)

    rows = _rows(ledger.validation_path(state, TODAY))
    assert sorted(row["run_id"] for row in rows) == sorted([RUN, later_run])


def test_a_second_attempt_at_one_dispatch_corrects_the_first(tmp_path: Path) -> None:
    """A re-run keeps the run id, so without the attempt element it takes its own path.

    The two attempts judge the same candidate under the same run, so they hold
    one key and the later one wins the cells they disagree on.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    for attempt, qualified in ((1, False), (2, True)):
        ledger.write_segment(
            state,
            ledger.SegmentLedger.VALIDATION,
            [_verdict(TODAY, RUN, model_id="gemma-4-e4b", qualified=qualified)],
            run_id=RUN,
            attempt=attempt,
            job=ServerJob.DECIDE,
            shard=0,
        )

    report = compact.stage_compact(state)

    rows = _rows(ledger.validation_path(state, TODAY))
    assert [row["verdict"] for row in rows] == [ValidationVerdict.QUALIFIED.value]
    assert report.rows_superseded == 1
