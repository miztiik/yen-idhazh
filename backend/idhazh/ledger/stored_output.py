"""Do named raw and compact files agree with their stored identities and compact indexes?"""

from __future__ import annotations

from pathlib import Path

from idhazh.contracts.base import StalePayloadError
from idhazh.contracts.file_envelope import Format, Period, Tier
from idhazh.contracts.ledger_index import CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import keys, paths
from idhazh.ledger.persist import load_stored, read_envelope
from idhazh.ledger.raw_files import read_day_files


def check_raw_day(state_dir: Path, which: LedgerName, day: str) -> bool:
    """Validate actual raw files and report presence."""
    raw = read_day_files(state_dir, which, day)
    for held in raw:
        stored = load_stored([held.path], model=keys.door_contract(which))
        if any(
            row.identity.ledger != which
            or row.identity.covers != day
            or row.identity.unit_id != str(held.envelope.unit_id)
            or row.identity.attempt != held.envelope.identity.attempt
            for row in stored
        ):
            raise ValueError(f"{held.path.name}: raw row identity differs from its envelope")
    return bool(raw)


def check_compact_period(state_dir: Path, which: LedgerName, period: Period, covers: str) -> bool:
    """Validate a named compact period and its index entry, and report indexed presence.

    An entry with no file, an `empty` period or a `lost` day, is present while no
    file holds it, and a file where it stands is refused.
    """
    watermark_path = paths.watermark_path(state_dir, which, period)
    if watermark_path.exists():
        try:
            watermark = Watermark.read(watermark_path)
        except (ValueError, StalePayloadError) as refusal:
            raise ValueError(f"{watermark_path.name}: {refusal}") from refusal
        if (watermark.ledger, watermark.period) != (which, period):
            raise ValueError(f"{watermark_path.name}: watermark names another ledger or period")
    index_path = paths.compact_index_path(state_dir, which, period)
    entry = None
    if index_path.exists():
        try:
            index = CompactIndex.read(index_path)
        except (ValueError, StalePayloadError) as refusal:
            raise ValueError(f"{index_path.name}: {refusal}") from refusal
        if (index.ledger, index.period) != (which, period):
            raise ValueError(f"{index_path.name}: index names another ledger or period")
        entry = next((row for row in index.entries if row.covers == covers), None)
    files = [
        path
        for fmt in Format
        if (path := paths.compact_path(state_dir, which, period, covers, fmt=fmt)).exists()
    ]
    if entry is None and files:
        raise ValueError(f"{files[0].name} has no compact index entry")
    if entry is None:
        return False
    if not entry.names_file:
        if files:
            raise ValueError(
                f"{files[0].name} is there, and the {period.value} index marks {covers} "
                f"{entry.state.value}, an entry with no file"
            )
        return True
    if len(files) != 1:
        raise ValueError(f"compact {period.value} {covers} has {len(files)} files, expected one")
    path = files[0]
    envelope = read_envelope(path)
    if (envelope.ledger, envelope.tier, envelope.period, envelope.covers) != (
        which,
        Tier.COMPACT,
        period,
        covers,
    ):
        raise ValueError(f"{path.name}: compact envelope names another ledger or period")
    stored = load_stored([path], model=keys.door_contract(which))
    if (entry.rows, entry.bytes) != (len(stored), path.stat().st_size):
        raise ValueError(f"{index_path.name}: {covers} row count or size differs from its file")
    if any(
        held.identity.ledger != which
        or not (held.identity.covers == covers or held.identity.covers.startswith(f"{covers}-"))
        for held in stored
    ):
        raise ValueError(f"{path.name}: a stored row belongs to another ledger or period")
    return True
