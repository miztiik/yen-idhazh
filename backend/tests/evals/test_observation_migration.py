"""Can explicit migration preserve legacy identities and every evaluation file?"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, writer_identity

from idhazh import ledger
from idhazh.config import load_observation_lookup
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_index import ObservationIndexRow
from idhazh.contracts.observation_lookup import ObservationLookupEntry
from idhazh.evals import writer
from idhazh.evals.observation_batches import lookup_root, row_digest
from idhazh.evals.observation_lookup import ROOT_NAME, ObservationLookup
from idhazh.evals.observation_migration import migrate

pytestmark = pytest.mark.contract

DAILY_SEGMENT = "2026/08/20/2026-08-20-1-1-work-00.csv"


def recorded(state: Path, candidates: set[str]) -> set[str]:
    """The supplied measurement IDs the migrated lookup holds."""
    with ObservationLookup(lookup_root(state)) as lookup:
        return lookup.recorded(candidates)


def a_row(day: str = "2026-08-20", *, number: int = 0) -> EvalRow:
    payload = json.loads((CONTRACT_FIXTURES_DIR / "eval-row" / "high.json").read_text("utf-8"))
    return EvalRow.model_validate({
        **payload,
        "date": day,
        "run_id": f"{day}-1",
        "scored_at": f"{day}T06:00:00Z",
        "url_key": derive_text_digest(f"migration-{number}"),
    })


def file_rows(state: Path, rows: list[EvalRow], *, fmt: Format = Format.PARQUET) -> list[Path]:
    return ledger.persist(
        state,
        rows,
        ledger=LedgerName.SUMMARY_QUALITY_EVALS,
        covers=rows[0].date,
        identity=writer_identity(rows[0].run_id, producer="tests.observation-migration"),
        fmt=fmt,
    )


def legacy_file(state: Path, relative: str, identities: list[str]) -> Path:
    path = lookup_root(state).parent / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        rows = csv.DictWriter(handle, ObservationIndexRow.csv_columns(), lineterminator="\n")
        rows.writeheader()
        rows.writerows(
            ObservationIndexRow.model_validate({"observation_digest": identity}).csv_row()
            for identity in identities
        )
    return path


def bytes_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("fmt", [Format.JSON, Format.PARQUET])
def test_migration_keeps_old_key_ids_and_current_ids_without_rewriting_rows(
    tmp_path: Path, fmt: Format
) -> None:
    state = tmp_path / "state"
    row = a_row()
    evaluation_files = file_rows(state, [row], fmt=fmt)
    old = derive_text_digest(canonical_json([
        row.url_key, "legacy-pipeline", row.output_digest, row.scorer_version
    ]))
    historical_only = derive_text_digest("a measurement only its historical index still names")
    daily = legacy_file(state, DAILY_SEGMENT, [old, old])
    monthly = legacy_file(state, "2026/07/settled.csv", [historical_only])
    before = {path: path.read_bytes() for path in evaluation_files}
    semantics = list(writer.records(state))

    result = migrate(state, load_observation_lookup())

    required = {old, historical_only, row_digest(row)}
    with ObservationLookup(lookup_root(state)) as lookup:
        assert lookup.recorded(required | {"f" * 64}) == required
        assert lookup.manifest().key_fields == ledger.OBSERVATION_KEY
    assert {path: path.read_bytes() for path in evaluation_files} == before
    assert list(writer.records(state)) == semantics
    assert not daily.exists() and not monthly.exists()
    assert (result.legacy_rows_read, result.legacy_ids) == (3, 2)
    assert (result.evaluation_rows_read, result.current_ids, result.required_ids) == (1, 1, 3)
    assert set(result.removed_paths) == {path.relative_to(state).as_posix() for path in (daily, monthly)}
    assert result.written_paths and all((state / path).is_file() for path in result.written_paths)
    assert not result.existing_verified


def test_unknown_legacy_shape_refuses_before_creating_a_lookup(tmp_path: Path) -> None:
    state = tmp_path / "state"
    file_rows(state, [a_row()])
    legacy_file(state, DAILY_SEGMENT, ["a" * 64])
    unknown = lookup_root(state).parent / "unknown.json"
    unknown.write_text("{}\n", encoding="utf-8", newline="\n")
    before = bytes_under(state)

    with pytest.raises(ValueError, match="unknown legacy index path"):
        migrate(state, load_observation_lookup())

    assert bytes_under(state) == before
    assert not lookup_root(state).exists()


def test_an_empty_input_does_not_become_an_empty_success(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    with pytest.raises(ValueError, match="empty migration"):
        migrate(state, load_observation_lookup())
    assert bytes_under(state) == {}


def seed_lookup(state: Path, identities: set[str]) -> None:
    with ObservationLookup(lookup_root(state)) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, load_observation_lookup())
        lookup.put(
            [ObservationLookupEntry(namespace="observation", identity=held) for held in identities],
            generation="d" * 64,
        )


@pytest.mark.parametrize("period", [Period.DAILY, Period.MONTHLY, Period.YEARLY])
def test_every_compact_row_and_late_raw_row_contributes_its_current_id(
    tmp_path: Path, period: Period
) -> None:
    state = tmp_path / "state"
    packed_row = a_row(number=0)
    late_row = a_row(number=1)
    original = file_rows(state, [packed_row])
    covers = {
        Period.DAILY: packed_row.date,
        Period.MONTHLY: packed_row.date[:7],
        Period.YEARLY: packed_row.date[:4],
    }[period]
    packed = ledger.persist_period(
        state,
        ledger.load_stored(original, model=EvalRow),
        model=EvalRow,
        ledger=LedgerName.SUMMARY_QUALITY_EVALS,
        period=period,
        covers=covers,
        identity=writer_identity("2026-09-28-1", producer="tests.observation-compaction"),
        built_from=len(original),
    )
    for path in original:
        path.unlink()
    for which in Period:
        index = CompactIndex.model_validate({
            "ledger": LedgerName.SUMMARY_QUALITY_EVALS,
            "period": which,
            "entries": [CompactEntry(covers=covers, rows=1, bytes=packed.stat().st_size)]
            if which == period else [],
        })
        path = ledger.compact_index_path(state, LedgerName.SUMMARY_QUALITY_EVALS, which)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(index.to_json().encode("ascii"))
    late = file_rows(state, [late_row], fmt=Format.JSON)
    historical = "a" * 64
    csv_path = legacy_file(state, "2026/07/settled.csv", [historical])
    before = bytes_under(state)
    semantics = list(writer.records(state))
    assert {writer.observation_digest(row) for row in semantics} == {row_digest(packed_row)}

    result = migrate(state, load_observation_lookup())

    wanted = {historical, row_digest(packed_row), row_digest(late_row)}
    assert recorded(state, wanted) == wanted
    assert result.evaluation_rows_read == 2
    assert list(writer.records(state)) == semantics
    for relative, content in before.items():
        if relative != csv_path.relative_to(state).as_posix():
            assert (state / relative).read_bytes() == content
    assert packed.exists() and all(path.exists() for path in late)


def test_existing_lookup_requires_explicit_verification_and_keeps_extra_history(tmp_path: Path) -> None:
    state = tmp_path / "state"
    needed, earlier = "a" * 64, "b" * 64
    legacy_file(state, DAILY_SEGMENT, [needed])
    seed_lookup(state, {needed, earlier})
    before = bytes_under(state)
    lookup_bytes = bytes_under(lookup_root(state))
    with pytest.raises(FileExistsError, match="existing=verify"):
        migrate(state, load_observation_lookup())
    assert bytes_under(state) == before

    result = migrate(state, load_observation_lookup(), existing="verify")

    assert result.existing_verified and result.generation == "d" * 64
    assert result.written_paths == ()
    assert bytes_under(lookup_root(state)) == lookup_bytes
    assert recorded(state, {needed, earlier}) == {needed, earlier}


def test_retry_after_partial_csv_removal_keeps_ids_from_already_removed_files(tmp_path: Path) -> None:
    state = tmp_path / "state"
    first, second = "a" * 64, "b" * 64
    removed = legacy_file(state, "2026/07/settled.csv", [first])
    remaining = legacy_file(state, DAILY_SEGMENT, [second])
    seed_lookup(state, {first, second})
    removed.unlink()
    before = bytes_under(lookup_root(state))

    result = migrate(state, load_observation_lookup(), existing="verify")

    assert result.removed_paths == (remaining.relative_to(state).as_posix(),)
    assert bytes_under(lookup_root(state)) == before
    assert recorded(state, {first, second}) == {first, second}


def test_retry_after_all_csvs_are_removed_does_not_reset_the_published_root(tmp_path: Path) -> None:
    state = tmp_path / "state"
    identities = {"a" * 64, "b" * 64}
    legacy_file(state, "2026/07/settled.csv", sorted(identities))
    first = migrate(state, load_observation_lookup())
    before = bytes_under(state)

    repeated = migrate(state, load_observation_lookup(), existing="verify")

    assert repeated.existing_verified
    assert repeated.generation == first.generation
    assert repeated.written_paths == repeated.removed_paths == ()
    assert bytes_under(state) == before
    assert recorded(state, identities) == identities


def test_retry_ignores_unpublished_private_work_and_preserves_other_agent_files(tmp_path: Path) -> None:
    state = tmp_path / "state"
    legacy_file(state, "2026/07/settled.csv", ["a" * 64, "b" * 64])
    private = state / ".observation-migration-interrupted"
    private.mkdir()
    with ObservationLookup(private / "lookup") as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, load_observation_lookup())
    unrelated = state / "raw" / "seen" / "other-agent.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"keep exactly\n")
    before = bytes_under(private)

    migrate(state, load_observation_lookup())

    assert bytes_under(private) == before
    assert unrelated.read_bytes() == b"keep exactly\n"
    assert recorded(state, {"a" * 64, "b" * 64}) == {"a" * 64, "b" * 64}


def test_an_existing_lookup_missing_an_id_is_not_rebuilt_or_cleaned_up(tmp_path: Path) -> None:
    state = tmp_path / "state"
    legacy_file(state, "2026/07/settled.csv", ["a" * 64])
    seed_lookup(state, {"b" * 64})
    before = bytes_under(state)

    with pytest.raises(ValueError, match="missing 1 required IDs"):
        migrate(state, load_observation_lookup(), existing="verify")

    assert bytes_under(state) == before


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_a_damaged_root_is_not_initialized_again(tmp_path: Path, damage: str) -> None:
    state = tmp_path / "state"
    legacy_file(state, "2026/07/settled.csv", ["a" * 64])
    seed_lookup(state, {"a" * 64})
    manifest = lookup_root(state) / ROOT_NAME
    if damage == "missing":
        manifest.unlink()
    else:
        manifest.write_bytes(b"{}\n")
    before = bytes_under(state)

    with pytest.raises((ValueError, FileNotFoundError)):
        migrate(state, load_observation_lookup(), existing="verify")

    assert bytes_under(state) == before


@pytest.mark.parametrize("content", [
    b"",
    b"observation_digest\n" + b"a" * 64 + b"\n",
    b"version,observation_digest,extra\n2026-09-07," + b"a" * 64 + b",extra\n",
    b"version,observation_digest\n2026-09-07,not-a-digest\n",
    b"version,observation_digest\n2026-09-07\n",
    b"version,observation_digest\n2026-09-07," + b"a" * 64 + b",extra\n",
    b"version,observation_digest\n2099-01-01," + b"a" * 64 + b"\n",
    b'version,observation_digest\n2026-09-07,"unterminated\n',
])
def test_bad_csv_is_not_skipped_or_deleted(tmp_path: Path, content: bytes) -> None:
    state = tmp_path / "state"
    file_rows(state, [a_row()])
    path = legacy_file(state, DAILY_SEGMENT, ["a" * 64])
    path.write_bytes(content)
    before = bytes_under(state)

    with pytest.raises((ValueError, csv.Error)):
        migrate(state, load_observation_lookup())

    assert bytes_under(state) == before
    assert not lookup_root(state).exists()


@pytest.mark.parametrize("relative", [
    "2026/08/20.csv",
    "2026/13/20/2026-08-20-1-1-work-00.csv",
    "2026/08/20/extra/2026-08-20-1-1-work-00.csv",
    "2026/08/20/someone-elses.csv",
])
def test_unknown_calendar_layout_is_not_silently_omitted(tmp_path: Path, relative: str) -> None:
    state = tmp_path / "state"
    legacy_file(state, relative, ["a" * 64])
    before = bytes_under(state)
    with pytest.raises(ValueError, match="unknown legacy index path"):
        migrate(state, load_observation_lookup())
    assert bytes_under(state) == before


def test_unreadable_raw_history_prevents_legacy_cleanup(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (raw,) = file_rows(state, [a_row()])
    raw.write_bytes(b"unreadable evaluation\n")
    legacy_file(state, DAILY_SEGMENT, ["a" * 64])
    before = bytes_under(state)
    with pytest.raises(ValueError, match="neither a parquet nor a JSON-lines"):
        migrate(state, load_observation_lookup())
    assert bytes_under(state) == before


def test_a_misplaced_evaluation_file_is_not_read_as_another_day(tmp_path: Path) -> None:
    state = tmp_path / "state"
    (raw,) = file_rows(state, [a_row()])
    raw.rename(raw.with_name("misplaced.parquet"))
    before = bytes_under(state)
    with pytest.raises(ValueError, match="misplaced evaluation file"):
        migrate(state, load_observation_lookup())
    assert bytes_under(state) == before


@pytest.mark.parametrize("boundary", ["lookup", "raw"])
def test_linked_input_or_output_cannot_reach_another_state(
    tmp_path: Path, boundary: str
) -> None:
    state = tmp_path / "state"
    legacy_file(state, DAILY_SEGMENT, ["a" * 64])
    other = tmp_path / "other-state"
    other.mkdir()
    (other / "keep.txt").write_bytes(b"other agent\n")
    root = lookup_root(state) if boundary == "lookup" else ledger.raw_root(
        state, LedgerName.SUMMARY_QUALITY_EVALS
    )
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(str(other), str(root))
        else:
            root.symlink_to(other, target_is_directory=True)
    except OSError as refusal:
        pytest.skip(f"filesystem links are unavailable: {refusal.strerror}")
    before = bytes_under(other)
    try:
        with pytest.raises(
            ValueError, match=r"symbolic links|linked parents|outside the two roots"
        ):
            migrate(state, load_observation_lookup(), existing="verify")
        assert bytes_under(other) == before
    finally:
        if sys.platform == "win32":
            root.rmdir()
        else:
            root.unlink()


def test_parent_traversal_cannot_select_another_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    with pytest.raises(ValueError, match="parent traversal"):
        migrate(state / ".." / "other-state", load_observation_lookup())


def test_a_split_lookup_keeps_every_legacy_candidate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    identities = {derive_text_digest(f"legacy-{number}") for number in range(300)}
    legacy_file(state, "2026/07/settled.csv", sorted(identities))
    settings = load_observation_lookup().model_copy(update={"max_leaf_bytes": 16384})

    result = migrate(state, settings)

    assert result.required_ids == len(identities)
    with ObservationLookup(lookup_root(state)) as lookup:
        assert lookup.manifest().node.kind == "page"
        assert lookup.recorded(identities) == identities


def test_the_explicit_cli_reports_real_counts_and_relative_paths(tmp_path: Path) -> None:
    state = tmp_path / "state"
    row = a_row()
    file_rows(state, [row])
    legacy_file(state, DAILY_SEGMENT, ["a" * 64])
    command = [sys.executable, "-m", "utilities.migrate_observation_lookup", "--state-dir", str(state)]

    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["required_ids"] == 2 and result["evaluation_rows_read"] == 1
    assert result["removed_paths"] == [f"summary-quality-evals-index/{DAILY_SEGMENT}"]
    assert all(not Path(path).is_absolute() and "\\" not in path for path in result["written_paths"])
    assert recorded(state, {row_digest(row), "a" * 64}) == {row_digest(row), "a" * 64}
    before = bytes_under(state)
    refused = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert refused.returncode == 2 and "existing=verify" in refused.stderr
    assert bytes_under(state) == before


@pytest.mark.parametrize("name", [
    "2026-08-20-1-1-work-00.csv",
    "settled.csv",
    ledger.BEFORE_PARTITION_NAME,
    "repair-20260820T091500Z.csv",
])
def test_declared_legacy_daily_names_remain_migratable(tmp_path: Path, name: str) -> None:
    state = tmp_path / "state"
    legacy_file(state, f"2026/08/20/{name}", ["a" * 64])

    result = migrate(state, load_observation_lookup())

    assert result.legacy_ids == result.required_ids == 1
    assert recorded(state, {"a" * 64}) == {"a" * 64}