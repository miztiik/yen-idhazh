"""Do stored-output checks refuse broken named files?"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SEED_COMMIT, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.stored_output import check_compact_period, check_raw_day

pytestmark = pytest.mark.contract
DAY: Final = "2026-09-02"
WHICH: Final = LedgerName.ITEM_HEALTH


def _raw(root: Path, day: str = DAY) -> Path:
    row = ItemHealthRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json").read_text(encoding="ascii")
    ).model_copy(update={"date": day})
    (path,) = ledger.persist(
        root,
        [row],
        ledger=WHICH,
        covers=day,
        identity=WriterIdentity(
            run_id=f"{day}-1",
            attempt=1,
            job=ServerJob.MIGRATE,
            shard=0,
            producer="utilities.migrate_to_parquet",
            git_sha=SEED_COMMIT,
        ),
    )
    return path


def _packed(root: Path, period: Period, covers: str) -> Path:
    """One compact file for a period, packed from a raw row filed on a day inside it."""
    raw = _raw(root, covers if period is Period.DAILY else f"{covers}-02")
    return ledger.persist_period(
        root,
        ledger.load_stored([raw], model=ItemHealthRow),
        model=ItemHealthRow,
        ledger=WHICH,
        period=period,
        covers=covers,
        identity=ledger.read_envelope(raw).identity,
        built_from=1,
    )


def _compact(root: Path) -> tuple[Path, Path]:
    path = _packed(root, Period.DAILY, DAY)
    index_path = ledger.compact_index_path(root, WHICH, Period.DAILY)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=WHICH,
            period=Period.DAILY,
            entries=[CompactEntry(covers=DAY, rows=1, bytes=path.stat().st_size)],
        ).to_json(),
        encoding="ascii",
        newline="\n",
    )
    return path, index_path


def test_raw_check_reads_real_files_and_reports_presence(tmp_path: Path) -> None:
    path = _raw(tmp_path)
    assert check_raw_day(tmp_path, WHICH, DAY)
    path.unlink()
    assert not check_raw_day(tmp_path, WHICH, DAY)


def test_raw_check_refuses_an_unreadable_actual_file(tmp_path: Path) -> None:
    path = _raw(tmp_path)
    path.write_bytes(b"not a ledger")
    with pytest.raises(ValueError, match="neither a parquet nor"):
        check_raw_day(tmp_path, WHICH, DAY)


@pytest.mark.parametrize("damage", ["none", "missing", "size", "unindexed"])
def test_compact_check_checks_the_named_period_and_entry(tmp_path: Path, damage: str) -> None:
    path, index = _compact(tmp_path)
    if damage == "none":
        assert check_compact_period(tmp_path, WHICH, Period.DAILY, DAY)
        return
    if damage == "missing":
        path.unlink()
    elif damage == "size":
        value = CompactIndex.read(index)
        index.write_text(
            value.model_copy(
                update={"entries": [value.entries[0].model_copy(update={"bytes": 0})]}
            ).to_json(),
            encoding="ascii",
            newline="\n",
        )
    else:
        index.unlink()
    with pytest.raises(ValueError):
        check_compact_period(tmp_path, WHICH, Period.DAILY, DAY)


@pytest.mark.parametrize("sample", ["an-empty-day", "a-lost-day", "a-month-with-lost-days"])
def test_an_entry_with_no_file_is_indexed_until_a_file_holds_it(
    tmp_path: Path, sample: str
) -> None:
    """A check that treats every entry as a file fails this: it refuses an empty period or a
    lost day as holding 0 files where it expects one. A file the index says is not there is
    refused."""
    index = CompactIndex.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "compact-index" / f"{sample}.json")
    )
    index_path = ledger.compact_index_path(tmp_path, WHICH, index.period)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(index.to_json(), encoding="ascii", newline="\n")
    (covers,) = [entry.covers for entry in index.entries if not entry.names_file]

    assert check_compact_period(tmp_path, WHICH, index.period, covers)

    _packed(tmp_path, index.period, covers)
    with pytest.raises(ValueError, match="an entry with no file"):
        check_compact_period(tmp_path, WHICH, index.period, covers)


def test_an_unreadable_old_index_is_a_named_value_error(tmp_path: Path) -> None:
    _, index = _compact(tmp_path)
    index.write_text(
        '{"version":"2026-09-01","ledger":"item-health","period":"daily","entries":"broken"}',
        encoding="ascii",
        newline="\n",
    )
    with pytest.raises(ValueError, match=r"daily.json:"):
        check_compact_period(tmp_path, WHICH, Period.DAILY, DAY)


@pytest.mark.parametrize("period", list(Period))
def test_a_corrupt_watermark_is_a_named_value_error(tmp_path: Path, period: Period) -> None:
    through = {Period.DAILY: DAY, Period.MONTHLY: DAY[:7], Period.YEARLY: DAY[:4]}[period]
    path = ledger.watermark_path(tmp_path, WHICH, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        Watermark(
            version=Watermark.schema_version(),
            ledger=WHICH,
            period=period,
            through=through,
            advanced_at="2026-09-03T00:00:00Z",
            run_id=f"{DAY}-1",
        ).to_json(),
        encoding="ascii",
        newline="\n",
    )
    path.write_text('{"version":"2026-09-27","through":"broken"}', encoding="ascii")

    with pytest.raises(ValueError, match=r"watermark.json:"):
        check_compact_period(tmp_path, WHICH, period, through)
