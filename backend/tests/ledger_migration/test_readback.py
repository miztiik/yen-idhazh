"""Is a day proven only from stored files that check out, never from a stale listing?"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from conftest import SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex
from utilities.ledger_migration import (
    phases,
    planning,
    refusals,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    ITEM,
    MONTHS,
    OLD,
    RUN,
    TODAY,
    by_key,
    config_beside,
    file_hashes,
    item_row,
    plan_named_roots,
    read_back,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_old_raw_listing_does_not_block_a_late_csv_key_in_a_packed_root(tmp_path: Path) -> None:
    state = tmp_path / "state"
    config_dir = config_beside(state)
    first = item_row(OLD, "ai-01", machine=True)
    write_csv(state, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [first.csv_row()])
    inputs = MigrationInputs(
        state_dirs=[state],
        which=[ITEM],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=config_dir,
        months=MONTHS,
    )
    phases.write_roots(planning.plan_roots(inputs))
    missing = "019f75f0-4bb0-835b-8c7e-824db9007c61.parquet"
    listing = ledger.raw_index_path(state, ITEM, OLD)
    listing.parent.mkdir(parents=True, exist_ok=True)
    listing.write_text(
        RawDayIndex(
            version=RawDayIndex.schema_version(),
            ledger=ITEM,
            date=OLD,
            files=[missing],
            content_sha256=hashlib.sha256(missing.encode()).hexdigest(),
            listed_at=f"{OLD}T12:00:00Z",
        ).to_json(),
        encoding="ascii",
        newline="\n",
    )
    late = item_row(OLD, "ai-02", machine=True)
    source = write_csv(state, ITEM, OLD, writer_file_name(OLD, 2, ServerJob.WORK), [late.csv_row()])
    phases.write_roots(planning.plan_roots(inputs))
    phases.verify_roots(planning.plan_roots(inputs))
    phases.retire_roots(inputs)
    assert not source.exists()
    assert read_back(state, ITEM, OLD) == by_key(ITEM, [first.csv_row(), late.csv_row()])


def test_an_unreadable_old_compact_index_refuses_as_not_proven(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    write_csv(
        root,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    path = ledger.compact_index_path(root, ITEM, Period.DAILY)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"version":"2026-09-01","ledger":"item-health","period":"daily","entries":"broken"}',
        encoding="ascii",
        newline="\n",
    )
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match=r"daily.json:"):
        plan_named_roots([root], ITEM)
    assert file_hashes(tmp_path) == before


@pytest.mark.parametrize("damage", ["file", "index", "entry", "size", "raw"])
def test_verify_validates_compact_and_raw_even_when_another_tier_serves_the_day(
    tmp_path: Path, damage: str
) -> None:
    state = tmp_path / "state"
    config_dir = config_beside(state)
    row = item_row(OLD, "ai-01", machine=True)
    write_csv(state, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    inputs = MigrationInputs(
        state_dirs=[state],
        which=[ITEM],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=config_dir,
        months=MONTHS,
    )
    phases.write_roots(planning.plan_roots(inputs))
    path = ledger.compact_file(state, ITEM, Period.DAILY, OLD)
    assert path is not None
    index_path = ledger.compact_index_path(state, ITEM, Period.DAILY)
    if damage == "file":
        path.unlink()
    elif damage == "index":
        ledger.compact_index_path(state, ITEM, Period.MONTHLY).unlink()
    elif damage in ("entry", "size"):
        index = CompactIndex.read(index_path)
        entries = [
            entry.model_copy(update={"bytes": entry.bytes + 1})
            if entry.covers == OLD and damage == "size"
            else entry
            for entry in index.entries
            if entry.covers != OLD or damage != "entry"
        ]
        index_path.write_text(
            index.model_copy(update={"entries": entries}).to_json(), encoding="ascii", newline="\n"
        )
    else:
        (raw,) = ledger.persist(
            state, [row], ledger=ITEM, covers=OLD, identity=writer_identity(RUN, SEED_COMMIT)
        )
        raw.write_bytes(b"broken raw file hidden by the compact index")
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match=rf"{ITEM.value} {OLD}"):
        phases.verify_roots(planning.plan_roots(inputs))
    assert file_hashes(tmp_path) == before
