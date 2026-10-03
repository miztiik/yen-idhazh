"""Can named publication writers preserve history without discovering archive files?"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.contracts.base import ServerJob
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_inventory import PublicationEntry, PublicationInventory
from idhazh.publication import (
    PUBLICATION_FILENAME,
    initialize_from_paths,
    initialize_inventory,
    read_inventory,
    record_day,
    record_feed_health,
    record_files,
    record_month,
    record_state_files,
    upgrade_inventory,
)
from utilities.publication_inventory import main


def paths(inventory: PublicationInventory, root: str) -> list[str]:
    return [entry.path for entry in inventory.entries if entry.root == root]


CONTRACT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "contracts"


def empty_inventory(root: Path) -> None:
    initialize_inventory(
        root,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )


def put(root: Path, name: str, text: str = "{}") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def test_recorded_inventory_round_trip() -> None:
    inventory = PublicationInventory.read(
        CONTRACT_FIXTURES_DIR / "publication-inventory" / "published.json"
    )
    assert PublicationInventory.model_validate_json(inventory.to_json()) == inventory
    assert set(PublicationInventory.model_fields) == {
        "version",
        "changelog",
        "dates",
        "entries",
        "total_bytes",
        "total_items",
    }
    assert PublicationInventory.schema_version() == "2026-10-03T13:33"


def test_named_schema_fixture_matches_backend_model() -> None:
    path = CONTRACT_FIXTURES_DIR / "publication-inventory" / "schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == PublicationInventory.model_json_schema()


@pytest.mark.parametrize(
    ("dates", "files"),
    [
        (["2026-02-30"], ["digest/2026/02/30/digest.json"]),
        (["2026-08-20", "2026-08-20"], ["digest/2026/08/20/digest.json"]),
        (["2026-08-19", "2026-08-20"], []),
        ([], ["../outside.json"]),
        ([], ["C:/private.json"]),
        ([], ["digest\\unsafe.json"]),
        ([], ["z.json", "a.json"]),
        (["2026-08-20"], []),
    ],
)
def test_inventory_refuses_invalid_names_or_order(dates: list[str], files: list[str]) -> None:
    with pytest.raises(ValidationError):
        PublicationInventory(
            version=PublicationInventory.schema_version(),
            dates=dates,
            entries=[PublicationEntry(path=name, bytes=0, items=0) for name in files],
        )


def test_missing_inventory_names_explicit_migration(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="--seed"):
        record_files(tmp_path, paths=[])
    assert not (tmp_path / PUBLICATION_FILENAME).exists()


def test_named_seed_keeps_existing_days_and_refuses_overwrite(tmp_path: Path) -> None:
    seed = PublicationInventory.read(
        CONTRACT_FIXTURES_DIR / "publication-inventory" / "published.json"
    )
    for name in paths(seed, "public"):
        put(tmp_path, name)
    initialize_inventory(tmp_path, seed=seed)
    assert read_inventory(tmp_path) == seed
    with pytest.raises(FileExistsError):
        initialize_inventory(tmp_path, seed=seed)


def test_seed_refuses_missing_named_files(tmp_path: Path) -> None:
    seed = PublicationInventory.read(
        CONTRACT_FIXTURES_DIR / "publication-inventory" / "published.json"
    )
    with pytest.raises(FileNotFoundError, match="seed names missing"):
        initialize_inventory(tmp_path, seed=seed)


def test_writer_uses_only_named_files_and_preserves_other_days(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    first = "digest/2026/08/19/digest.json"
    second = "digest/2026/08/20/digest.json"
    put(tmp_path, first)
    put(tmp_path, second)
    put(tmp_path, "digest/2020/01/01/unlisted.json")
    record_files(tmp_path, dates=["2026-08-19"], paths=[first], item_counts={first: 1})
    inventory = record_files(
        tmp_path, dates=["2026-08-20"], paths=[second], item_counts={second: 2}
    )
    assert inventory.dates == ["2026-08-20", "2026-08-19"]
    assert paths(inventory, "public") == [first, second]
    assert inventory.total_items == 3
    assert inventory.total_bytes == 4
    before = (tmp_path / PUBLICATION_FILENAME).read_bytes()
    record_files(tmp_path, dates=["2026-08-20"], paths=[second])
    assert (tmp_path / PUBLICATION_FILENAME).read_bytes() == before


def test_month_refresh_removes_only_named_missing_files(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    old = "machine/2026-07.csv"
    current = "machine/2026-08.csv"
    put(tmp_path, old)
    target = put(tmp_path, current)
    put(tmp_path, "run-timeline/2026-08.csv")
    record_files(tmp_path, paths=[old, current])
    target.unlink()
    inventory = record_month(tmp_path, "2026-08")
    assert paths(inventory, "public") == [old, "run-timeline/2026-08.csv"]
    assert inventory.total_bytes == 4


def test_removing_a_named_digest_also_removes_its_date(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    name = f"digest/{day.date.replace('-', '/')}/digest.json"
    digest = put(tmp_path, name, day.to_json())
    record_files(tmp_path, dates=[day.date], paths=[name], item_counts={name: len(day.items)})

    digest.unlink()
    inventory = record_files(tmp_path, paths=[name], remove_dates=[day.date])

    assert inventory.dates == []
    assert paths(inventory, "public") == []
    assert inventory.total_bytes == 0
    assert inventory.total_items == 0


def test_day_writer_recomputes_visual_name_not_payload_path(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    prefix = f"digest/{day.date.replace('-', '/')}"
    put(tmp_path, f"{prefix}/digest.json", day.to_json())
    put(tmp_path, f"{prefix}/run.json")
    expected = [f"{prefix}/digest.json", f"{prefix}/run.json"]
    for item in day.items:
        if item.visual is not None:
            item.visual.data_path = "private/untrusted.json"
            expected.append(f"{prefix}/{item.item_id}.json")
            put(tmp_path, expected[-1])
    inventory = record_day(tmp_path, day)
    assert inventory.dates == [day.date]
    assert paths(inventory, "public") == sorted(expected)
    assert inventory.total_items == len(day.items)
    assert inventory.total_bytes == sum((tmp_path / name).stat().st_size for name in expected)


def test_replacing_a_named_entry_adjusts_totals_without_recounting_history(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    name = "digest/2026/08/20/digest.json"
    put(tmp_path, name, "first")
    record_files(tmp_path, dates=["2026-08-20"], paths=[name], item_counts={name: 3})
    put(tmp_path, name, "longer replacement")
    inventory = record_files(tmp_path, paths=[name], item_counts={name: 4})
    assert inventory.total_items == 4
    assert inventory.total_bytes == len("longer replacement")
    assert inventory.entries == [PublicationEntry(path=name, bytes=18, items=4)]


def test_new_digest_requires_explicit_count(tmp_path: Path) -> None:
    empty_inventory(tmp_path)
    name = "digest/2026/08/20/digest.json"
    put(tmp_path, name)
    with pytest.raises(ValueError, match="requires its item_counts"):
        record_files(tmp_path, dates=["2026-08-20"], paths=[name])
    assert read_inventory(tmp_path).total_items == 0


def test_legacy_upgrade_measures_only_explicit_names(tmp_path: Path) -> None:
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    name = f"digest/{day.date.replace('-', '/')}/digest.json"
    digest = put(tmp_path, name, day.to_json())
    put(tmp_path, "not-indexed.json", "not measured")
    legacy = {
        "version": "2026-10-03",
        "changelog": [{"version": "2026-10-03", "change": "Initial shape", "why": "Named reads"}],
        "dates": [day.date],
        "files": [name],
    }
    put(tmp_path, PUBLICATION_FILENAME, json.dumps(legacy))
    with pytest.raises(ValueError, match="upgrade"):
        read_inventory(tmp_path)
    inventory = upgrade_inventory(tmp_path)
    assert paths(inventory, "public") == [name]
    assert inventory.total_items == len(day.items)
    assert inventory.total_bytes == digest.stat().st_size
    assert read_inventory(tmp_path) == inventory


@pytest.mark.parametrize("total", ["total_bytes", "total_items"])
def test_inconsistent_totals_are_refused(total: str) -> None:
    inventory = PublicationInventory.read(
        CONTRACT_FIXTURES_DIR / "publication-inventory" / "published.json"
    ).model_dump(mode="json")
    inventory[total] += 1
    with pytest.raises(ValidationError, match=total):
        PublicationInventory.model_validate(inventory)


def test_initializer_cli_accepts_explicit_empty_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.argv", ["publication_inventory", "--public-root", str(tmp_path), "--empty"]
    )
    assert main() == 0
    assert read_inventory(tmp_path).dates == []


def test_explicit_path_list_seeds_all_named_days_without_discovery(tmp_path: Path) -> None:
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    first = f"digest/{day.date.replace('-', '/')}/digest.json"
    put(tmp_path, first, day.to_json())
    day.date = "2026-08-22"
    second = "digest/2026/08/22/digest.json"
    put(tmp_path, second, day.to_json())
    put(tmp_path, "run-timeline/2026-08.csv", "header\n")
    put(tmp_path, "not-named.json", "not part of the seed")
    inventory = initialize_from_paths(tmp_path, paths=[second, first, "run-timeline/2026-08.csv"])
    assert inventory.dates == ["2026-08-22", "2026-08-21"]
    assert paths(inventory, "public") == sorted([first, second, "run-timeline/2026-08.csv"])
    assert inventory.total_items == 2 * len(day.items)
    assert inventory.total_bytes == sum(
        (tmp_path / name).stat().st_size for name in paths(inventory, "public")
    )


def test_explicit_path_list_refuses_a_digest_under_the_wrong_day(tmp_path: Path) -> None:
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    name = "digest/2026/08/22/digest.json"
    put(tmp_path, name, day.to_json())
    with pytest.raises(ValueError, match="does not match"):
        initialize_from_paths(tmp_path, paths=[name])
    assert not (tmp_path / PUBLICATION_FILENAME).exists()


def test_initializer_cli_reads_only_its_named_path_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public_root = tmp_path / "public"
    put(public_root, "run-timeline/2026-08.csv")
    names = put(tmp_path, "paths.txt", "run-timeline/2026-08.csv\n")
    monkeypatch.setattr(
        "sys.argv",
        ["publication_inventory", "--public-root", str(public_root), "--paths", str(names)],
    )
    assert main() == 0
    assert paths(read_inventory(public_root), "public") == ["run-timeline/2026-08.csv"]


def test_state_entry_does_not_change_public_totals_or_disappear_on_public_update(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    state = tmp_path / "state"
    empty_inventory(public)
    name = "raw/feed-health/2026/08/20/writer.parquet"
    put(state, name, "row\n")
    record_state_files(public, state, paths=[name])
    put(public, "telemetry/2026-08.csv", "abc")
    inventory = record_files(public, paths=["telemetry/2026-08.csv"])
    assert paths(inventory, "state") == [name]
    assert paths(inventory, "public") == ["telemetry/2026-08.csv"]
    assert inventory.total_bytes == 3
    assert inventory.total_items == 0
    assert inventory.entries[-1] == PublicationEntry(root="state", path=name, bytes=4, items=0)
    (state / name).unlink()
    inventory = record_state_files(public, state, paths=[name])
    assert paths(inventory, "state") == []
    assert inventory.total_bytes == 3


def test_state_seed_reads_only_named_state_files(tmp_path: Path) -> None:
    public = tmp_path / "public"
    state = tmp_path / "state"
    name = "raw/feed-health/2026/08/20/writer.parquet"
    put(state, name)
    put(state, "raw/feed-health/old-unlisted.parquet")
    inventory = initialize_from_paths(public, paths=[], state_root=state, state_paths=[name])
    assert paths(inventory, "state") == [name]
    assert paths(inventory, "public") == []
    assert inventory.total_bytes == 0


def test_feed_health_registers_the_raw_file_returned_by_the_ledger(tmp_path: Path) -> None:
    from idhazh import ledger

    public = tmp_path / "public"
    state = tmp_path / "state"
    empty_inventory(public)
    row = FeedHealthRow.read(CONTRACT_FIXTURES_DIR / "feed-health-row" / "answered.json")
    files = ledger.persist(
        state,
        [row],
        ledger=LedgerName.FEED_HEALTH,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.PLAN,
            shard=0,
            producer="tests.publication_inventory",
            git_sha="a" * 40,
        ),
    )
    names = [path.relative_to(state).as_posix() for path in files]
    inventory = record_feed_health(public, state, paths=names)
    assert paths(inventory, "state") == names
    assert names[0].startswith("raw/feed-health/2026/08/23/")


def test_measured_inventory_without_roots_upgrades_by_its_named_list(tmp_path: Path) -> None:
    day = DigestDay.read(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    name = f"digest/{day.date.replace('-', '/')}/digest.json"
    target = put(tmp_path, name, day.to_json())
    legacy = {
        "version": "2026-10-03T13:10",
        "changelog": [
            {"version": "2026-10-03T13:10", "change": "Measure named entries", "why": "Named reads"}
        ],
        "dates": [day.date],
        "files": [name],
        "entries": [{"path": name, "bytes": target.stat().st_size, "items": len(day.items)}],
        "total_bytes": target.stat().st_size,
        "total_items": len(day.items),
    }
    put(tmp_path, PUBLICATION_FILENAME, json.dumps(legacy))
    inventory = upgrade_inventory(tmp_path)
    assert inventory.version == PublicationInventory.schema_version()
    assert inventory.entries[0].root == "public"
    assert inventory.total_items == len(day.items)
    assert paths(inventory, "state") == []
    assert read_inventory(tmp_path) == inventory


def test_feed_health_registration_happens_after_real_writer_creates_rows(tmp_path: Path) -> None:
    from idhazh import ledger

    public, state = tmp_path / "public", tmp_path / "state"
    empty_inventory(public)
    row = FeedHealthRow.read(CONTRACT_FIXTURES_DIR / "feed-health-row" / "answered.json")
    before = record_feed_health(public, state, paths=[])
    assert paths(before, "state") == []
    files = ledger.persist(
        state,
        [row],
        ledger=LedgerName.FEED_HEALTH,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.PLAN,
            shard=0,
            producer="tests.publication_inventory",
            git_sha="a" * 40,
        ),
    )
    names = [path.relative_to(state).as_posix() for path in files]
    inventory = record_feed_health(public, state, paths=names)
    assert len(paths(inventory, "state")) == 1
    name = paths(inventory, "state")[0]
    assert name.startswith("raw/feed-health/2026/08/23/")
    assert (state / name).is_file()
    assert inventory.entries[0].bytes == (state / name).stat().st_size
    assert inventory.total_bytes == 0


def test_concurrent_public_and_state_writers_preserve_all_entries(tmp_path: Path) -> None:
    public, state = tmp_path / "public", tmp_path / "state"
    empty_inventory(public)
    public_names = ["telemetry/2026-08.csv", "machine/2026-08.csv"]
    state_names = [
        "raw/feed-health/2026/08/20/one.parquet",
        "raw/feed-health/2026/08/20/two.parquet",
    ]
    for name in public_names:
        put(public, name)
    for name in state_names:
        put(state, name)
    script = (
        "import sys; from pathlib import Path; "
        "from idhazh.publication import record_files,record_state_files; "
        "public,state=Path(sys.argv[1]),Path(sys.argv[2]); "
        "root,name=sys.argv[3:]; "
        "[(record_files(public,paths=[name]) if root=='public' "
        "else record_state_files(public,state,paths=[name])) for _ in range(5)]"
    )
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(public), str(state), root, name],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for root, names in (("public", public_names), ("state", state_names))
        for name in names
    ]
    for worker in workers:
        output, errors = worker.communicate(timeout=120)
        assert worker.returncode == 0, (output.decode(), errors.decode())
    inventory = read_inventory(public)
    assert paths(inventory, "public") == sorted(public_names)
    assert paths(inventory, "state") == sorted(state_names)
    assert inventory.total_bytes == 4
