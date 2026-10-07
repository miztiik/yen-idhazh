"""Is a filled cell under an undeclared, ragged or conflicting heading refused, never dropped?"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import SEED_COMMIT
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.item_health import DROPPED_CELLS, MACHINE_CELLS_RENAMED, ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import json_lines, parquet
from utilities import migrate_to_parquet as command
from utilities.ledger_migration import (
    csv_layouts,
    path_labels,
    phases,
    planning,
    refusals,
)
from utilities.ledger_migration.identity import SHARD
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    HOST,
    ITEM,
    MONTH_ARGS,
    MONTHS,
    OLD,
    RUN,
    TODAY,
    by_key,
    config_beside,
    file_hashes,
    item_row,
    plan_named_roots,
    probe_row,
    read_back,
    run_migration,
    seen_row,
    write_csv,
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def _stored(path: Path) -> list[dict[str, Any]]:
    """A ledger file's rows as stored, the door's own columns included."""
    data = path.read_bytes()
    return (parquet.read if data.startswith(b"PAR1") else json_lines.read)(data)[1]


@pytest.mark.parametrize("operation", ["plan", "migrate", "retire"])
@pytest.mark.parametrize("fault", ["unknown", "ragged", "conflicting rename"])
def test_no_undeclared_csv_cell_can_be_retired(
    tmp_path: Path, operation: str, fault: str
) -> None:
    root = tmp_path / "trial"
    row = item_row(OLD, "ai-01", machine=True).csv_row()
    heading = "undeclared_reading"
    if fault == "unknown":
        row[heading] = "7"
    elif fault == "conflicting rename":
        heading = "job"
        row[heading] = ServerJob.PLAN.value
    source = write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row])
    if fault == "ragged":
        heading = "no heading"
        lines = source.read_text(encoding="utf-8").splitlines()
        source.write_text("\n".join([lines[0], lines[1] + ",7"]) + "\n", encoding="utf-8")
    inputs = MigrationInputs(
        state_dirs=[root], which=[ITEM], run_id=RUN, git_sha=SEED_COMMIT,
        today=TODAY, config_dir=PRE_YEARLY_CONFIG, months=MONTHS,
    )
    before = file_hashes(tmp_path)
    action = {
        "plan": planning.plan_roots,
        "migrate": phases.migrate_roots,
        "retire": phases.retire_roots,
    }[operation]
    with pytest.raises(refusals.NotProvenError, match=heading) as refused:
        action(inputs)
    message = str(refused.value)
    assert all(part in message for part in (root.name, ITEM.value, OLD, source.name))
    assert file_hashes(tmp_path) == before
    assert source.exists()


@pytest.mark.parametrize("fault", ["unknown", "ragged", "empty unknown"])
def test_shared_csv_uses_the_same_heading_checks(tmp_path: Path, fault: str) -> None:
    root = tmp_path / "trial"
    row = seen_row(OLD).csv_row()
    if fault != "ragged":
        row["undeclared_reading"] = "" if fault == "empty unknown" else "7"
    source = write_shared_csv(root, LedgerName.SEEN, OLD, [row])
    if fault == "ragged":
        lines = source.read_text(encoding="utf-8").splitlines()
        source.write_text("\n".join([lines[0], lines[1] + ",7"]) + "\n", encoding="utf-8")
    before = file_hashes(tmp_path)
    if fault == "empty unknown":
        plans = plan_named_roots([root], LedgerName.SEEN)
        phases.write_roots(plans)
        phases.verify_roots(plan_named_roots([root], LedgerName.SEEN))
        assert read_back(root, LedgerName.SEEN, OLD) == by_key(
            LedgerName.SEEN, [seen_row(OLD).csv_row()]
        )
    else:
        heading = "no heading" if fault == "ragged" else "undeclared_reading"
        with pytest.raises(refusals.NotProvenError, match=heading) as refused:
            plan_named_roots([root], LedgerName.SEEN)
        assert source.name in str(refused.value)
        assert file_hashes(tmp_path) == before
    assert source.exists()


def test_an_item_health_file_under_the_old_headings_reads_back_under_the_new_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`job` and `shard` named the machine until the door took those two words for the writer.

    A file written before the rename reads back with the machine under
    `machine_job` and `machine_shard`, the migration under the door's own `job`
    and `shard`, and the dropped headings nowhere.
    """
    state = tmp_path / "state"
    row = item_row(OLD, "ai-01", machine=True)
    retired = {current: old for old, current in MACHINE_CELLS_RENAMED.items()}
    cells = {retired.get(name, name): value for name, value in row.csv_row().items()}
    dropped = dict.fromkeys(sorted(DROPPED_CELLS), "7")
    write_csv(state, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [cells | dropped])

    config_beside(state)
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match="not declared"):
        run_migration(state, ITEM)
    assert file_hashes(tmp_path) == before
    declarations = csv_layouts.CSV_LEDGERS
    entry = declarations[ITEM]._replace(
        old_headings={**declarations[ITEM].old_headings, **dict.fromkeys(DROPPED_CELLS)}
    )
    monkeypatch.setattr(csv_layouts, "CSV_LEDGERS", {**declarations, ITEM: entry})
    run_migration(state, ITEM)

    assert ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow) == [row]
    found = ledger.compact_file(state, ITEM, Period.DAILY, OLD)
    assert found is not None
    (stored,) = _stored(found)
    assert (stored["machine_job"], stored["machine_shard"]) == (ServerJob.WORK.value, 0)
    assert (stored["job"], stored["shard"]) == (ServerJob.MIGRATE.value, SHARD)
    assert not DROPPED_CELLS & stored.keys()


def test_a_row_that_will_not_parse_is_refused_before_anything_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The utility exits 1 naming the ledger, the day, the file and the row, and touches nothing."""
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    name = writer_file_name(OLD, 1, ServerJob.WORK)
    write_csv(state, HOST, OLD, name, [probe_row(OLD).csv_row() | {"cores": "four"}])
    before = file_hashes(tmp_path)

    code = command.main(
        [*MONTH_ARGS, *["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]]
    )

    assert code == command.EXIT_NOT_PROVEN
    assert (
        f"nothing deleted: {path_labels.label_path(state)}: {HOST.value} {OLD}: {name} row 2 "
        in capsys.readouterr().err
    )
    assert file_hashes(tmp_path) == before
