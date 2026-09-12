from __future__ import annotations

import csv
import inspect
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from pydantic import ValidationError

from idhazh import cli
from idhazh.contracts.item_health import (
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.publish_telemetry import (
    DEFAULT_PUBLIC_ROOT,
    FORBIDDEN_COLUMNS,
    PUBLIC_COLUMNS,
    migrate,
    publish,
    read_shard,
    shard_path,
    shard_relpath,
)

COMMITTED_SHARDS = sorted((REPO_ROOT / "frontend" / "public" / "telemetry").glob("*.csv"))


def _row(**overrides: object) -> ItemHealthRow:
    payload: dict[str, object] = {
        "version": ItemHealthRow.schema_version(),
        "date": "2026-08-23",
        "run_id": "2026-08-23-1",
        "item_id": "ai-01",
        "url_key": "a" * 64,
        "canonical_url": "https://example.com/story",
        "vertical": "ai",
        "source_id": "example",
        "stage": ItemStage.PUBLISH,
        "outcome": ItemOutcome.OK,
        "code": None,
        "http_status": None,
        "source_chars": 1200,
        "source_words": 180,
        "summary_words": 65,
        "detail": None,
        "fetch_ms": 100,
        "extract_ms": 20,
        "summarize_ms": 600,
    }
    payload.update(overrides)
    return ItemHealthRow.model_validate(payload)


def _write_item_health(state: Path, rows: list[ItemHealthRow]) -> None:
    path = state / "item-health" / "2026-08.csv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ItemHealthRow.csv_columns(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.csv_row() for row in rows)


def test_publish_telemetry_drops_url_keys_urls_and_detail(tmp_path: Path) -> None:
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    _write_item_health(
        state,
        [
            _row(
                stage=ItemStage.EXTRACT,
                outcome=ItemOutcome.FAILED,
                code=FailureCode.UNKNOWN,
                detail="host returned a shape we do not classify yet",
            )
        ],
    )

    written = publish(state_root=state, public_root=public)

    assert [path.name for path in written] == ["2026-08.csv"]
    with written[0].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or []) == PUBLIC_COLUMNS
        projected = list(reader)
    assert not (FORBIDDEN_COLUMNS & set(projected[0]))
    assert projected == [
        {
            "date": "2026-08-23",
            "run_id": "2026-08-23-1",
            "item_id": "ai-01",
            "vertical": "ai",
            "source_id": "example",
            "stage": "extract",
            "outcome": "failed",
            "code": "unknown",
            "source_words": "180",
            "summary_words": "65",
            "source_words_before_cap": "",
            "fetch_ms": "100",
            "extract_ms": "20",
            "summarize_ms": "600",
            "prefill_ms": "",
            "decode_ms": "",
            "input_tokens": "",
            "output_tokens": "",
            "cached_tokens": "",
            "model_calls": "",
            "call_1_kind": "",
            "call_1_prefill_ms": "",
            "call_1_decode_ms": "",
            "call_1_input_tokens": "",
            "call_1_output_tokens": "",
            "call_1_cached_tokens": "",
        }
    ]


def test_publish_telemetry_can_seed_an_empty_month(tmp_path: Path) -> None:
    public = tmp_path / "frontend" / "public" / "telemetry"

    written = publish(state_root=tmp_path / "state", public_root=public, ensure_month="2026-08")

    assert [path.name for path in written] == ["2026-08.csv"]
    assert written[0].read_text(encoding="utf-8") == ",".join(PUBLIC_COLUMNS) + "\n"


def test_the_writer_and_the_deleter_name_one_file(tmp_path: Path) -> None:
    """`retention.prune_telemetry` deletes a copy through `shard_path`.

    Two spellings of `<month>.csv` would delete a shard nobody published and
    leave the one that was published behind, so the publish is asked what it
    wrote rather than told. `shard_relpath` is the POSIX form the log line and
    the workflow's staged path both use (`CLAUDE.md` section 2).
    """
    state = tmp_path / "state"
    public = tmp_path / "telemetry"
    _write_item_health(state, [_row()])

    written = publish(state_root=state, public_root=public)

    assert written == [shard_path(public, "2026-08")]
    assert shard_relpath("2026-08") == "frontend/public/telemetry/2026-08.csv"
    assert shard_path(DEFAULT_PUBLIC_ROOT, "2026-08").relative_to(
        REPO_ROOT
    ).as_posix() == shard_relpath("2026-08")


def test_publish_telemetry_carries_both_word_counts(tmp_path: Path) -> None:
    """The console needs the pre-cap count to say a body was cut.

    It is a word count of our own extraction, the same class as `source_words`,
    which the browser has always had. The three cells the browser never gets -
    canonical_url, url_key and detail - are untouched by this column.
    """
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    _write_item_health(
        state, [_row(source_words=1923, source_words_before_cap=2610), _row(item_id="ai-02")]
    )

    written = publish(state_root=state, public_root=public)

    with written[0].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert "source_words_before_cap" in (reader.fieldnames or [])
        projected = list(reader)
    assert not (FORBIDDEN_COLUMNS & set(projected[0]))
    assert projected[0]["source_words_before_cap"] == "2610"
    assert int(projected[0]["source_words_before_cap"]) > int(projected[0]["source_words"])
    assert projected[1]["source_words_before_cap"] == ""


def test_publish_telemetry_carries_the_stage_timings_and_the_token_counts(tmp_path: Path) -> None:
    """Every run since 2026-08-23 measured these eight and the projection dropped them.

    They are durations and counts of our own work, so they cross on the same
    terms the two word counts do, and the three cells a reader never gets are
    untouched. The pair that matters is the last two assertions: a server that
    cached nothing writes `0`, and an instrument that never ran writes nothing
    at all. Collapse those two and a skipped stage reads as a stage that took no
    time.
    """
    state = tmp_path / "state"
    public = tmp_path / "frontend" / "public" / "telemetry"
    _write_item_health(
        state,
        [
            _row(
                prefill_ms=180, decode_ms=420, input_tokens=1500, output_tokens=90, cached_tokens=0
            ),
            _row(item_id="ai-02", fetch_ms=None, extract_ms=None, summarize_ms=None),
        ],
    )

    written = publish(state_root=state, public_root=public)

    with written[0].open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or [])
        projected = list(reader)
    timings = ("fetch_ms", "extract_ms", "summarize_ms", "prefill_ms", "decode_ms")
    tokens = ("input_tokens", "output_tokens", "cached_tokens")
    assert set(timings + tokens) <= set(header)
    at = header.index(timings[0])
    assert header[at : at + len(timings + tokens)] == timings + tokens, (
        "one unbroken block, in the order it was appended in - a later column goes "
        "after it, never through it"
    )
    assert not (FORBIDDEN_COLUMNS & set(projected[0]))
    assert [projected[0][name] for name in timings] == ["100", "20", "600", "180", "420"]
    assert [projected[0][name] for name in tokens] == ["1500", "90", "0"]
    assert projected[0]["cached_tokens"] == "0", "a server that cached nothing measured zero"
    assert all(projected[1][name] == "" for name in timings + tokens), (
        "an instrument that did not run writes an empty cell, never a zero"
    )


def test_the_pipeline_never_writes_the_committed_telemetry_projection(tmp_path: Path) -> None:
    """A test run must not rewrite published bytes.

    `stage_assemble` used the module default for `public_root`, so driving the
    pipeline from a temporary tree still truncated the committed projection in
    `frontend/public/telemetry/`. A dirty tree is what aborts the publish push
    and discards a day, so the default must never reach a caller that passed
    its own roots.
    """
    source = inspect.getsource(cli.stage_assemble)

    assert "publish_telemetry.publish(" in source
    assert "public_root=" in source.split("publish_telemetry.publish(", 1)[1][:200]


def test_the_projection_carries_the_contract_header_and_no_version_cell() -> None:
    """`version` is a field of the shape and never a cell.

    The browser checks the header as a prefix, so a name at position zero would
    shift every position the console reads and blank its charts on every cached
    bundle.
    """
    assert PUBLIC_COLUMNS == PublicTelemetryRow.csv_columns()
    assert "version" in PublicTelemetryRow.model_fields
    assert "version" not in PUBLIC_COLUMNS
    assert not FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields)


def test_every_committed_shard_reads_back_through_the_contract() -> None:
    """The migration's oracle, on the published file itself.

    A published shard is the one artifact nobody can re-derive once its source
    month has been folded away, so "it still parses" is not the question - the
    question is whether every row loads through the shape that now owns it.

    The newest shard, not every one. An older shard is frozen: if it parsed when
    it was written it parses now, and the only thing that can change that is the
    contract - which `ci.yml` re-reads the whole tree for (Guardrail #12).
    """
    assert COMMITTED_SHARDS, "the committed projection has no shards to migrate"
    path = COMMITTED_SHARDS[-1]
    rows = read_shard(path)
    assert rows, f"{path.name} published no rows"
    assert all(isinstance(row, PublicTelemetryRow) for row in rows)
    assert b"\r" not in path.read_bytes(), f"{path.name} must be LF"


def test_migrating_the_committed_shards_changes_no_byte(tmp_path: Path) -> None:
    """The migration is a read-back, so it must be a no-op on bytes.

    Run against a copy rather than the committed tree: a dirty working tree is
    what aborts the publish push and discards a day.
    """
    public = tmp_path / "telemetry"
    public.mkdir()
    before = {path.name: path.read_bytes() for path in COMMITTED_SHARDS}
    for path in COMMITTED_SHARDS:
        (public / path.name).write_bytes(before[path.name])

    results = migrate(public)

    assert [path.name for path, _, _ in results] == [path.name for path in COMMITTED_SHARDS]
    for path, rows, unchanged in results:
        assert unchanged, f"{path.name} did not survive its own round trip"
        assert rows > 0
        assert path.read_bytes() == before[path.name]


def test_a_published_failure_without_a_reason_is_refused() -> None:
    """The console groups failures by code, so a bar it cannot label is not a row."""
    with pytest.raises(ValidationError, match="failure code"):
        PublicTelemetryRow.from_csv_row(
            {
                "date": "2026-09-01",
                "run_id": "2026-09-01-1",
                "item_id": "ai-01",
                "vertical": "ai",
                "source_id": "example",
                "stage": "fetch",
                "outcome": "failed",
                "code": "",
                "source_words": "",
                "summary_words": "",
                "source_words_before_cap": "",
            }
        )


def _month_shard(state: Path, month: str, rows: list[ItemHealthRow]) -> None:
    path = state / "item-health" / f"{month}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ItemHealthRow.csv_columns(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.csv_row() for row in rows)


_OPENED: list[str] = []
_WATCHING = False


def _audit(event: str, args: tuple[object, ...]) -> None:
    if _WATCHING and event == "open" and args and isinstance(args[0], str):
        _OPENED.append(args[0])


sys.addaudithook(_audit)


@contextmanager
def _partitions_opened(source_dir: Path) -> Iterator[list[str]]:
    """Every ledger partition opened inside the block, by name.

    An audit hook rather than a stopwatch, because a stopwatch on this box cannot
    tell one partition from twelve: a sibling row measured 16.6 percent
    run-to-run variance on identical work. What a read opens is arithmetic and
    has no spread at all (Guardrail #10).

    A deliberate copy of the hook in `test_console_payloads_producer.py` rather
    than a fixture the two share: an audit hook cannot be removed once
    installed, so lifting it into `conftest.py` would install it for every module
    in the suite to serve two. It counts `open` itself, not a call to any helper
    here, so it still answers after a refactor that reads the partitions some
    other way.
    """
    global _WATCHING
    names: list[str] = []
    _OPENED.clear()
    _WATCHING = True
    try:
        yield names
    finally:
        _WATCHING = False
        prefix = str(source_dir)
        names.extend(sorted(Path(path).name for path in _OPENED if path.startswith(prefix)))
        _OPENED.clear()


def test_the_cover_is_the_months_the_caller_names(tmp_path: Path) -> None:
    """The two arms of the cover, counted in file handles rather than timed.

    The daily caller passes the one month it appended to, so the ordinary pass
    opens one partition whatever the ledger holds - twelve here. `months=None`
    opens all twelve, which is the unbounded arm the module's own docstring
    declares, and it is unbounded on purpose: a fresh clone has to rebuild a
    mirror it never published.

    The backfill has to run first, because a month whose mirror is missing is
    read whatever the caller asked for. That is the same escape the fresh clone
    depends on, so the count here is the count after it has been satisfied.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    months = [f"2026-{month:02d}" for month in range(1, 13)]
    for month in months:
        _month_shard(state, month, [_row(date=f"{month}-05", run_id=f"{month}-05-1")])
    source_dir = state / "item-health"

    with _partitions_opened(source_dir) as backfill:
        publish(state_root=state, public_root=public)
    with _partitions_opened(source_dir) as daily:
        publish(state_root=state, public_root=public, months={"2026-09"})

    assert backfill == [f"{month}.csv" for month in months]
    assert daily == ["2026-09.csv"]


def test_a_frozen_month_is_not_rebuilt_once_it_has_been_published(tmp_path: Path) -> None:
    """A run that appends nothing new writes no shard at all.

    Two freezes compose here. The closed month (2026-08) the caller never names,
    so it is skipped without a read. The current month (2026-09) is read and
    re-derived, but its bytes match what is already published, so the write is
    skipped too. The earlier month filter still rewrote the current month every
    run; a partition now writes only when its bytes change (finding 11).

    The mechanism is a byte comparison, not a timestamp: the mtime checks below
    are evidence that an unchanged month was not touched, never how the skip is
    decided.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row()])
    _month_shard(state, "2026-09", [_row(date="2026-09-02", run_id="2026-09-02-1")])

    publish(state_root=state, public_root=public)
    august = public / "2026-08.csv"
    september = public / "2026-09.csv"
    mtimes = {path.name: path.stat().st_mtime_ns for path in (august, september)}
    payloads = {path.name: path.read_bytes() for path in (august, september)}

    written = publish(state_root=state, public_root=public, months={"2026-09"})

    assert written == []
    assert {path.name: path.stat().st_mtime_ns for path in (august, september)} == mtimes
    assert {path.name: path.read_bytes() for path in (august, september)} == payloads


def test_a_month_that_was_never_published_is_written_whatever_was_asked_for(
    tmp_path: Path,
) -> None:
    """The skip is an optimisation, so a missing shard overrides it.

    A fresh clone, a deleted file and a month the run did not touch all land
    here. Without this the projection would be permanently short of a month that
    no later run ever names again.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row()])
    _month_shard(state, "2026-09", [_row(date="2026-09-02", run_id="2026-09-02-1")])

    written = publish(state_root=state, public_root=public, months={"2026-09"})

    assert [path.name for path in written] == ["2026-08.csv", "2026-09.csv"]
    assert (public / "2026-08.csv").exists()


def test_seeding_an_empty_month_never_blanks_a_shard_that_holds_rows(tmp_path: Path) -> None:
    """`ensure_month` writes an empty shard; it must not empty a full one.

    Before the month filter every shard was rebuilt, so `ensure_month` could
    only fire for a month with no file. A skipped month is now absent from the
    returned list while its file is on disk, and blanking it would delete
    published telemetry the source can no longer re-derive.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row()])

    publish(state_root=state, public_root=public)
    full = (public / "2026-08.csv").read_text(encoding="utf-8")
    assert full.count("\n") == 2, "the fixture month should hold one row"

    publish(state_root=state, public_root=public, months={"2026-09"}, ensure_month="2026-08")

    assert (public / "2026-08.csv").read_text(encoding="utf-8") == full


def test_a_rerun_with_no_new_data_writes_no_shard(tmp_path: Path) -> None:
    """The oracle for finding 11: a no-op run must publish nothing.

    A full rebuild (`months=None`) and a caller-hinted run (`months={...}`) both
    re-derive the current month, and both leave it alone when the bytes already
    on disk are the bytes they would write. The comparison is the shard's own
    bytes; the mtime check is a witness that the file was never opened for
    writing.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row()])
    _month_shard(state, "2026-09", [_row(date="2026-09-02", run_id="2026-09-02-1")])

    publish(state_root=state, public_root=public)
    shards = sorted(public.glob("*.csv"))
    payloads = {path.name: path.read_bytes() for path in shards}
    mtimes = {path.name: path.stat().st_mtime_ns for path in shards}

    assert publish(state_root=state, public_root=public) == []
    assert publish(state_root=state, public_root=public, months={"2026-09"}) == []

    after = sorted(public.glob("*.csv"))
    assert {path.name: path.read_bytes() for path in after} == payloads
    assert {path.name: path.stat().st_mtime_ns for path in after} == mtimes


def test_adding_a_day_rewrites_only_that_month(tmp_path: Path) -> None:
    """The second half of the oracle: one changed month, one file written.

    The changed month costs its full output bytes - a projection is a whole-file
    rewrite, not an append (the shard is deliberately not `merge=union`). The
    saving is the month that did not change, which is neither read nor written.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row()])
    _month_shard(state, "2026-09", [_row(date="2026-09-02", run_id="2026-09-02-1")])

    publish(state_root=state, public_root=public)
    august = public / "2026-08.csv"
    september = public / "2026-09.csv"
    august_bytes = august.read_bytes()
    august_mtime = august.stat().st_mtime_ns
    september_bytes = september.read_bytes()

    _month_shard(
        state,
        "2026-09",
        [
            _row(date="2026-09-02", run_id="2026-09-02-1"),
            _row(date="2026-09-03", run_id="2026-09-03-1", item_id="ai-02"),
        ],
    )
    written = publish(state_root=state, public_root=public, months={"2026-09"})

    assert [path.name for path in written] == ["2026-09.csv"]
    assert august.read_bytes() == august_bytes
    assert august.stat().st_mtime_ns == august_mtime, "the unchanged month was rewritten"
    assert september.read_bytes() != september_bytes


def test_a_correction_to_a_closed_month_rewrites_only_that_month(tmp_path: Path) -> None:
    """The freeze rule permits one write to a closed month: a correction.

    The caller decides a closed month changed by naming it in `months`; the
    publish then re-derives it, sees the bytes differ, and rewrites that month
    alone. The current month, unnamed, is left untouched.
    """
    state = tmp_path / "state"
    public = tmp_path / "public"
    _month_shard(state, "2026-08", [_row(summary_words=65)])
    _month_shard(state, "2026-09", [_row(date="2026-09-02", run_id="2026-09-02-1")])

    publish(state_root=state, public_root=public)
    august = public / "2026-08.csv"
    september = public / "2026-09.csv"
    september_bytes = september.read_bytes()
    september_mtime = september.stat().st_mtime_ns

    _month_shard(state, "2026-08", [_row(summary_words=41)])
    written = publish(state_root=state, public_root=public, months={"2026-08"})

    assert [path.name for path in written] == ["2026-08.csv"]
    assert september.read_bytes() == september_bytes
    assert september.stat().st_mtime_ns == september_mtime, "an untargeted month was rewritten"
    corrected = read_shard(august)
    assert len(corrected) == 1
    assert corrected[0].csv_row()["summary_words"] == "41", "the correction did not land"
