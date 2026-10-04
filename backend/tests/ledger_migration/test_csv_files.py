"""Does the migration list only the named months, and refuse a malformed day by name?"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.seen import PublishedRow
from utilities import migrate_to_parquet as command
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
    phases,
    refusals,
)
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    EVALS,
    ITEM,
    MONTH_ARGS,
    MONTHS,
    OLD,
    RUN,
    TODAY,
    by_key,
    config_beside,
    fixture_text,
    item_row,
    read_back,
    run_migration,
    seen_row,
    write_csv,
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def _published(day: str) -> PublishedRow:
    base = PublishedRow.model_validate_json(fixture_text("published-row", "one-item.json"))
    return PublishedRow.model_validate({**base.model_dump(), "published_on": day})


def _day_file_config(state: Path, which: Sequence[LedgerName]) -> Path:
    """A real temporary registry and compaction declaration for shared-day migration cases."""
    config_dir = config_beside(state)
    registry_path = config_dir / "ledgers.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for family in registry["families"]:
        for entry in family["ledgers"]:
            if LedgerName(entry["name"]) in which:
                entry.update(
                    grain=Grain.RAW_AND_COMPACT.value,
                    prefix=[entry["name"]],
                    stem=None,
                    suffix=None,
                )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="ascii", newline="")
    source = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    declared = json.loads(source.read_text(encoding="utf-8"))
    for name in which:
        policy = declared | {
            "ledger": name.value,
            "owns": [f"state/raw/{name.value}", f"state/compact/{name.value}"],
        }
        target = config_dir / "gardener" / f"compact-{name.value}.json"
        target.write_text(json.dumps(policy, indent=2) + "\n", encoding="ascii", newline="")
        knobs_path = config_dir / "idhazh_gardener.json"
        knobs = json.loads(knobs_path.read_text(encoding="ascii"))
        task = f"compact-{name.value}"
        if task not in knobs["task_names"]:
            knobs["task_names"].append(task)
        knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    return config_dir


def test_a_layout_this_does_not_read_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed shared-day layout is named and refused, never skipped.

    A check that read nothing there would pass over every file it holds.
    """
    state = tmp_path / "state"
    malformed = csv_layouts.csv_root(state, LedgerName.SEEN) / "2026" / "09" / "not-a-day.csv"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("version,url_key,first_seen_at,first_seen_run\n", encoding="ascii")
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]

    code = command.main([*MONTH_ARGS, *[*argv, "--check", "--ledger", LedgerName.SEEN.value]])

    assert code == command.EXIT_NOT_PROVEN
    assert "not-a-day.csv is not a YYYY/MM/DD.csv file" in capsys.readouterr().err


def test_a_shared_day_file_moves_cell_for_cell(tmp_path: Path) -> None:
    """The YYYY/MM/DD.csv layout reads through each row contract before its file is deleted."""
    state = tmp_path / "state"
    day = TODAY.isoformat()
    expected = {
        LedgerName.SEEN: {day: [seen_row(day).csv_row()]},
        LedgerName.PUBLISHED: {day: [_published(day).csv_row()]},
    }
    source_files = {
        (which, day): write_shared_csv(state, which, day, rows)
        for which, days in expected.items()
        for day, rows in days.items()
    }

    config_dir = _day_file_config(state, (LedgerName.SEEN, LedgerName.PUBLISHED))
    moved = {
        each.which: each
        for _, each in phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[LedgerName.SEEN, LedgerName.PUBLISHED],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                config_dir=config_dir,
                months=MONTHS,
            )
        )
    }

    for which, days in expected.items():
        assert moved[which].rows == sum(len(rows) for rows in days.values())
        for day, rows in days.items():
            assert read_back(state, which, day) == by_key(which, rows)
            assert not source_files[which, day].exists()
        assert not csv_layouts.csv_root(state, which).exists()
        assert not csv_files.left(state, [which], months=MONTHS)


def test_a_shared_day_file_with_a_refused_layout_preserves_every_csv(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    valid = write_shared_csv(state, LedgerName.SEEN, OLD, [seen_row(OLD).csv_row()])
    refused = csv_layouts.csv_root(state, LedgerName.SEEN) / "2026/09/not-a-day.csv"
    refused.write_text("version,url_key,first_seen_at,first_seen_run\n", encoding="ascii")
    before = {valid: valid.read_bytes(), refused: refused.read_bytes()}
    config_dir = _day_file_config(state, (LedgerName.SEEN,))

    with pytest.raises(refusals.NotProvenError, match=r"not a YYYY/MM/DD\.csv file"):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[LedgerName.SEEN],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                config_dir=config_dir,
                months=MONTHS,
            )
        )

    assert {path: path.read_bytes() for path in before} == before


def test_named_month_migration_ignores_other_csv_and_raw_months(tmp_path: Path) -> None:
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    other_csv = csv_layouts.csv_root(state, ITEM) / "2026/10/not-a-day.csv"
    other_raw = ledger.raw_root(state, ITEM) / "2026/10/01/invalid.parquet"
    for path in (other_csv, other_raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff")

    run_migration(state, ITEM)

    assert csv_files.left(state, [ITEM], months=MONTHS) == []
    assert other_csv.read_bytes() == other_raw.read_bytes() == b"\xff"
    assert len(ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow)) == 1
