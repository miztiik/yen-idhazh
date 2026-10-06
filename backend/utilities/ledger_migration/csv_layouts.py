"""Which CSV layout and retention window did each supported ledger use before it moved?"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final, NamedTuple

from idhazh import ledger
from idhazh.contracts.eval_row import RENAMED_CELLS
from idhazh.contracts.item_health import RETIRED_CELLS
from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow, MonthsWindow, Window
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry
from utilities.ledger_migration.refusals import RefusedError


class CsvLedger(NamedTuple):
    """How one ledger was filed before it moved to the door, and how long it was kept."""

    old_entry: LedgerEntry
    old_window: Window
    old_headings: Mapping[str, str | None] = MappingProxyType({})


def _tree(name: LedgerName, folder: str | None = None) -> LedgerEntry:
    """A CSV day tree, one file a writer a day, under its own name unless it sat elsewhere."""
    return LedgerEntry(
        name=name, grain=Grain.DAY_TREE, prefix=tuple((folder or name.value).split("/"))
    )


def _day_file(name: LedgerName) -> LedgerEntry:
    """One shared CSV file a day, under the ledger's own name."""
    return LedgerEntry(name=name, grain=Grain.DAY_FILE, prefix=(name.value,), suffix=".csv")


CSV_LEDGERS: Final[Mapping[LedgerName, CsvLedger]] = MappingProxyType(
    {
        # The full-grain series of the telemetry-aggregate task deleted it.
        LedgerName.ITEM_HEALTH: CsvLedger(
            _tree(LedgerName.ITEM_HEALTH),
            MonthsWindow(unit="months", value=14),
            RETIRED_CELLS,
        ),
        # Filed under `scores/`, its name before it was renamed. No eval row is deleted.
        LedgerName.SUMMARY_QUALITY_EVALS: CsvLedger(
            _tree(LedgerName.SUMMARY_QUALITY_EVALS, "scores"),
            ForeverWindow(unit="forever"),
            RENAMED_CELLS,
        ),
        # The host-fingerprint retention task deleted it, until its compaction took over.
        LedgerName.HOST_FINGERPRINT: CsvLedger(
            _tree(LedgerName.HOST_FINGERPRINT), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.COUNTERFACTUAL_SCORES: CsvLedger(
            _tree(LedgerName.COUNTERFACTUAL_SCORES), DaysWindow(unit="days", value=30)
        ),
        # Nothing deletes a candidate's verdict.
        LedgerName.CANDIDATE_MODELS: CsvLedger(
            _tree(LedgerName.CANDIDATE_MODELS), ForeverWindow(unit="forever")
        ),
        LedgerName.FEED_HEALTH: CsvLedger(
            _tree(LedgerName.FEED_HEALTH), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES: CsvLedger(
            _tree(
                LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES,
                "content-similarity-judge/merge-line-holdout-scores",
            ),
            ForeverWindow(unit="forever"),
            MappingProxyType({"key_point_weight": None}),
        ),
        LedgerName.SEEN: CsvLedger(_day_file(LedgerName.SEEN), DaysWindow(unit="days", value=90)),
        # Nothing deletes a published record: forgetting one republishes it.
        LedgerName.PUBLISHED: CsvLedger(
            _day_file(LedgerName.PUBLISHED), ForeverWindow(unit="forever")
        ),
    }
)
# Removal condition: delete this package and its command when no program-written CSV
# remains.


def require_layout(which: LedgerName) -> LedgerEntry:
    """The old layout the table declares for this ledger, or a refusal naming it."""
    if which not in CSV_LEDGERS:
        raise RefusedError(f"{which.value}: no supported CSV layout in CSV_LEDGERS")
    entry = CSV_LEDGERS[which].old_entry
    if entry.grain not in (Grain.DAY_TREE, Grain.DAY_FILE):
        raise RefusedError(
            f"{which.value}: unsupported CSV layout {entry.grain.value} "
            f"under {'/'.join(entry.prefix)}"
        )
    return entry


def csv_root(state_dir: Path, which: LedgerName) -> Path:
    """Where this ledger's CSV sat under a state root: the prefix its old entry names."""
    return state_dir.joinpath(*require_layout(which).prefix)


def door_ledgers() -> list[LedgerName]:
    """Every ledger in the table that `config/ledgers.json` files through the door now."""
    return [name for name in CSV_LEDGERS if ledger.entry(name).grain is Grain.RAW_AND_COMPACT]
