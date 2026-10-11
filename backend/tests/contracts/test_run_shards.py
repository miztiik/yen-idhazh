"""The narrow ledger preserves the manifest's count, including unknowns and corrections."""

from datetime import date
from pathlib import Path
from typing import cast

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_shards import RunShards
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from idhazh.telemetry import run_shards
from idhazh.telemetry.run_shards import backfill, record, rows_of

pytestmark = pytest.mark.contract


def test_no_manifest_or_plan_inputs_are_persisted() -> None:
    assert set(RunShards.model_fields) == {"version", "date", "run_id", "shards"}
    assert RunShards(version=RunShards.schema_version(), date="2026-10-11", run_id="2026-10-11-1").shards is None
    for invalid in (0, -1, True, 1.5, "3"):
        with pytest.raises(ValueError):
            RunShards.model_validate({
                "version": RunShards.schema_version(), "date": "2026-10-11",
                "run_id": "2026-10-11-1", "shards": invalid,
            })


def test_last_numeric_manifest_record_survives_a_later_unknown() -> None:
    from types import SimpleNamespace

    manifest = SimpleNamespace(date="2026-10-11", runs=[
        SimpleNamespace(run_id="2026-10-11-1", shards=1),
        SimpleNamespace(run_id="2026-10-11-1", shards=3),
        SimpleNamespace(run_id="2026-10-11-1", shards=None),
        SimpleNamespace(run_id="2026-10-11-2", shards=None),
    ])
    assert [(r.run_id, r.shards) for r in rows_of(cast(RunManifest, manifest))] == [
        ("2026-10-11-1", 3), ("2026-10-11-2", None)
    ]


def test_count_settlement_is_not_run_plan_first_wins(tmp_path: Path) -> None:
    writer = WriterIdentity(
        run_id="2026-10-11-1", attempt=1, job=ServerJob.ASSEMBLE,
        shard=0, producer="test", git_sha="0" * 40,
    )
    files = []
    for count, attempt in ((1, 1), (3, 2), (None, 3)):
        row = RunShards(version=RunShards.schema_version(), date="2026-10-11", run_id=writer.run_id, shards=count)
        path = ledger.persist(
            tmp_path, [row], ledger=LedgerName.RUN_SHARDS, covers=row.date,
            identity=writer.model_copy(update={"attempt": attempt}),
        )[0]
        files.append(ledger.load_stored([path], model=RunShards))
    assert [r.row.shards for r in ledger.settle_rows(files, ("date", "run_id"))] == [3]
    assert [r.row.shards for r in ledger.settle_rows(list(reversed(files)), ("date", "run_id"))] == [3]
    assert ledger.preference_for(("date", "run_id")) is None
    assert ledger.door_key(LedgerName.RUN_PLAN) == ("date", "run_id")


def writer(*, attempt: int = 1, producer: str = "test") -> WriterIdentity:
    return WriterIdentity(
        run_id="2026-10-11-1", attempt=attempt, job=ServerJob.OPERATOR,
        shard=0, producer=producer, git_sha="0" * 40,
    )


def manifest(on: str, counts: list[int | None]) -> RunManifest:
    sample = RunManifest.read(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    run = sample.runs[0]
    return sample.model_copy(update={
        "date": on,
        "runs": [run.model_copy(update={"run_id": f"{on}-1", "shards": count}) for count in counts],
    })


def test_backfill_reads_only_the_named_day_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    digest = tmp_path / "digest"
    for on in ("2026-08-01", "2026-08-03", "2026-08-04"):
        sample = manifest(on, [1, 3, None])
        target = digest.joinpath(*on.split("-"), "run.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sample.to_json(), encoding="utf-8", newline="\n")
    read = run_shards.historical_rows
    opened: list[Path] = []

    def named(path: Path, on: str) -> list[RunShards]:
        opened.append(path)
        return read(path, on)

    monkeypatch.setattr(run_shards, "historical_rows", named)
    state = tmp_path / "state"
    assert backfill(digest, state, first="2026-08-01", through="2026-08-03", identity=writer()) == 2
    assert opened == [
        digest / "2026" / "08" / "01" / "run.json",
        digest / "2026" / "08" / "03" / "run.json",
    ]
    assert [(row.date, row.shards) for row in ledger.load_days(
        state, LedgerName.RUN_SHARDS, ["2026-08-01", "2026-08-03"], model=RunShards,
    )] == [("2026-08-01", 3), ("2026-08-03", 3)]
    with pytest.raises(ValueError, match="first"):
        backfill(digest, state, first="2026-08-04", through="2026-08-03", identity=writer())
    assert len(opened) == 2


def test_count_business_identity_is_not_the_backfill_writer_identity(tmp_path: Path) -> None:
    sample = manifest("2026-08-01", [None])
    assert record(tmp_path, sample, identity=writer()) == 1
    paths = ledger.list_raw_files(tmp_path, LedgerName.RUN_SHARDS, days=["2026-08-01"])
    held = ledger.load_stored([paths[0].path], model=RunShards)[0]
    assert held.row.run_id == "2026-08-01-1"
    assert held.row.shards is None
    assert held.identity.ledger is LedgerName.RUN_SHARDS
    assert held.identity.unit_id
    assert paths[0].envelope.identity.producer == "test"


def test_repeated_backfill_leaves_raw_files_immutable_and_packed_rows_unchanged(tmp_path: Path) -> None:
    digest = tmp_path / "digest"
    sample = manifest("2026-08-01", [1, 3, None])
    target = digest / "2026" / "08" / "01" / "run.json"
    target.parent.mkdir(parents=True)
    target.write_text(sample.to_json(), encoding="utf-8", newline="\n")
    state = tmp_path / "state"
    def repeat() -> int:
        return backfill(digest, state, first=sample.date, through=sample.date, identity=writer())

    assert repeat() == 1
    original = {
        held.path: held.path.read_bytes()
        for held in ledger.list_raw_files(state, LedgerName.RUN_SHARDS, days=[sample.date])
    }
    assert repeat() == 0
    assert {
        held.path: held.path.read_bytes()
        for held in ledger.list_raw_files(state, LedgerName.RUN_SHARDS, days=[sample.date])
    } == original
    pack(tmp_path, date(2026, 10, 11))
    assert repeat() == 0
    assert ledger.list_raw_files(state, LedgerName.RUN_SHARDS, days=[sample.date]) == []
    assert [row.shards for row in ledger.load_days(
        state, LedgerName.RUN_SHARDS, [sample.date], model=RunShards,
    )] == [3]


def test_interleaved_writers_settle_the_latest_numeric_record(tmp_path: Path) -> None:
    files = []
    for count, attempt, producer in (
        (1, 1, "backfill"), (2, 1, "assemble"), (3, 2, "backfill"),
        (None, 3, "backfill"), (4, 2, "assemble"), (None, 3, "assemble"),
    ):
        row = RunShards(version=RunShards.schema_version(), date="2026-08-01", run_id="2026-08-01-1", shards=count)
        paths = ledger.persist(
            tmp_path, [row], ledger=LedgerName.RUN_SHARDS, covers=row.date,
            identity=writer(attempt=attempt, producer=producer),
        )
        files.append(ledger.load_stored(paths, model=RunShards))
    assert [held.row.shards for held in ledger.settle_rows(files, ("date", "run_id"))] == [4]
    assert [held.row.shards for held in ledger.settle_rows(list(reversed(files)), ("date", "run_id"))] == [4]
    for cut in range(1, len(files)):
        packed = ledger.settle_rows(files[:cut], ("date", "run_id"))
        assert [held.row.shards for held in ledger.settle_rows([packed, *files[cut:]], ("date", "run_id"))] == [4]


def test_same_clock_counts_use_original_file_identity_through_packing(tmp_path: Path) -> None:
    from idhazh.contracts.run_shards import RunShardsProvenance
    from idhazh.ledger.persist import StoredRow

    row = RunShards(version=RunShards.schema_version(), date="2026-08-01", run_id="2026-08-01-1", shards=1)
    path = ledger.persist(tmp_path, [row], ledger=LedgerName.RUN_SHARDS, covers=row.date, identity=writer())[0]
    original = ledger.load_stored([path], model=RunShards)[0]
    files = [
        [StoredRow(
            original.identity, row.model_copy(update={"shards": count}),
            RunShardsProvenance(written_at_ms=1000, file_id=file_id),
        )]
        for count, file_id in (
            (1, "00000000-0000-0000-0000-000000000001"),
            (3, "00000000-0000-0000-0000-000000000003"),
            (None, "00000000-0000-0000-0000-000000000004"),
        )
    ]
    key = ("date", "run_id")
    assert [held.row.shards for held in ledger.settle_rows(files, key)] == [3]
    assert [held.row.shards for held in ledger.settle_rows(list(reversed(files)), key)] == [3]
    packed = ledger.settle_rows(files[:2], key)
    assert [held.row.shards for held in ledger.settle_rows([packed, files[2]], key)] == [3]


def pack(root: Path, today: date) -> None:
    policy = config.load_gardener().tasks["compact-run-shards"]
    result = compaction.run(TaskContext(
        state_dir=root / "state", repo_root=root, today=today,
        policy=policy.model_copy(update={"max_periods_per_run": 200, "compact_after_days": 0}),
        run_id=writer().run_id, attempt=1, job=ServerJob.OPERATOR, shard=0, git_sha="0" * 40,
        owned_folders=tuple(name for name in policy.owns if (root / name).is_dir()),
        listing=FileListing.from_disk(root, policy.owns, paths=(root / name for name in policy.owns)),
        first_ledger_year="2026",
    ))
    assert result.resume_from is None


def test_daily_and_reopened_month_keep_numeric_corrections(tmp_path: Path) -> None:
    state = tmp_path / "state"
    sample = manifest("2026-08-01", [1])
    record(state, sample, identity=writer())
    pack(tmp_path, date(2026, 8, 2))
    record(state, manifest(sample.date, [3]), identity=writer(attempt=2))
    pack(tmp_path, date(2026, 8, 3))
    assert [row.shards for row in ledger.load_days(
        state, LedgerName.RUN_SHARDS, [sample.date], model=RunShards,
    )] == [3]
    pack(tmp_path, date(2026, 10, 11))
    record(state, manifest(sample.date, [4]), identity=writer(producer="assemble-correction"))
    pack(tmp_path, date(2026, 10, 11))
    record(state, manifest(sample.date, [None]), identity=writer(attempt=3, producer="assemble-correction"))
    pack(tmp_path, date(2026, 10, 11))
    assert [row.shards for row in ledger.load_days(
        state, LedgerName.RUN_SHARDS, [sample.date], model=RunShards,
    )] == [4]


@pytest.mark.parametrize(("on", "today"), [
    ("2026-10-01", date(2026, 10, 2)),
    ("2026-08-01", date(2026, 10, 11)),
])
@pytest.mark.parametrize("via_backfill", [False, True])
@pytest.mark.parametrize("latest", [1, 3, None])
def test_pending_correction_is_part_of_the_manifest_comparison(
    tmp_path: Path, on: str, today: date, via_backfill: bool, latest: int | None,
) -> None:
    state = tmp_path / "state"
    target = tmp_path / "digest"
    named = target.joinpath(*on.split("-"), "run.json")

    def file_count(count: int | None, attempt: int) -> int:
        sample = manifest(on, [count])
        identity = writer(attempt=attempt)
        if not via_backfill:
            return record(state, sample, identity=identity)
        named.parent.mkdir(parents=True, exist_ok=True)
        named.write_text(sample.to_json(), encoding="utf-8", newline="\n")
        return backfill(target, state, first=on, through=on, identity=identity)

    assert file_count(1, 1) == 1
    pack(tmp_path, today)
    assert file_count(3, 2) == 1
    pending = {
        held.path: held.path.read_bytes()
        for held in ledger.list_raw_files(state, LedgerName.RUN_SHARDS, days=[on])
    }
    assert file_count(latest, 3) == (1 if latest == 1 else 0)
    assert all(path.read_bytes() == contents for path, contents in pending.items())
    if latest != 1:
        assert {
            held.path: held.path.read_bytes()
            for held in ledger.list_raw_files(state, LedgerName.RUN_SHARDS, days=[on])
        } == pending

    pack(tmp_path, today)
    assert [row.shards for row in ledger.load_days(
        state, LedgerName.RUN_SHARDS, [on], model=RunShards,
    )] == [1 if latest == 1 else 3]
    assert file_count(latest, 4) == 0
