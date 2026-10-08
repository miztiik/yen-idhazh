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
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.contracts.merge_line_holdout_score import (
    DROPPED_CELLS as DROPPED_HOLDOUT_SCORE_CELLS,
)
from idhazh.ledger.paths import REGISTRY_FILENAME
from utilities.ledger_migration.refusals import RefusedError


class CsvLedger(NamedTuple):
    """How one ledger was filed before it moved to the door, and how long it was kept.

    `day_column` names the cell a row's UTC day is read from, for a layout whose
    path names no day: one CSV file holding every row. A layout whose path names
    the day leaves it unset.
    """

    old_entry: LedgerEntry
    old_window: Window
    old_headings: Mapping[str, str | None] = MappingProxyType({})
    day_column: str | None = None


def _tree(name: LedgerName, folder: str | None = None) -> LedgerEntry:
    """A CSV day tree, one file a writer a day, under its own name unless it sat elsewhere."""
    return LedgerEntry(name=name, grain=Grain.DAY_TREE, prefix=(folder or name.value,))


def _day_file(name: LedgerName, folders: tuple[str, ...] = ()) -> LedgerEntry:
    """One shared CSV file a day, under the ledger's own name unless it sat elsewhere.

    `folders` is the path under `state/` where that is not the ledger's own name,
    such as a family's folder and then the ledger's own.
    """
    return LedgerEntry(
        name=name, grain=Grain.DAY_FILE, prefix=folders or (name.value,), suffix=".csv"
    )


def _flat_file(name: LedgerName, folders: tuple[str, ...]) -> LedgerEntry:
    """One CSV file named for the ledger, holding every row, in a folder it shared."""
    return LedgerEntry(name=name, grain=Grain.FLAT, prefix=folders, stem=name.value, suffix=".csv")


CSV_LEDGERS: Final[Mapping[LedgerName, CsvLedger]] = MappingProxyType(
    {
        # The full-grain series of the telemetry-aggregate task deleted it.
        LedgerName.ITEM_HEALTH: CsvLedger(
            _tree(LedgerName.ITEM_HEALTH), MonthsWindow(unit="months", value=14),
            RETIRED_CELLS,
        ),
        # Filed under `scores/`, its name before it was renamed. No eval row is deleted.
        LedgerName.SUMMARY_QUALITY_EVALS: CsvLedger(
            _tree(LedgerName.SUMMARY_QUALITY_EVALS, "scores"), ForeverWindow(unit="forever"),
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
        # A person's command filed one shared file a day inside the judge's folder.
        # Nothing deleted a reading.
        LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES: CsvLedger(
            _day_file(
                LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES,
                ("content-similarity-judge", "merge-line-holdout-scores"),
            ),
            ForeverWindow(unit="forever"),
            MappingProxyType(dict.fromkeys(DROPPED_HOLDOUT_SCORE_CELLS)),
        ),
        LedgerName.SEEN: CsvLedger(_day_file(LedgerName.SEEN), DaysWindow(unit="days", value=90)),
        # Nothing deletes a published record: forgetting one republishes it.
        LedgerName.PUBLISHED: CsvLedger(
            _day_file(LedgerName.PUBLISHED), ForeverWindow(unit="forever")
        ),
        # A person's harvest rewrote one file in the judge's folder with every mark,
        # each row naming the day it was marked. Nothing deleted a mark.
        LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS: CsvLedger(
            _flat_file(
                LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS, ("content-similarity-judge",)
            ),
            ForeverWindow(unit="forever"),
            day_column="marked_on",
        ),
    }
)
# Removal condition: delete this package and its command when no program-written CSV
# remains.


def require_layout(which: LedgerName) -> LedgerEntry:
    """The old layout the table declares for this ledger, or a refusal naming it.

    A day tree and a shared day file name the day in their path. One file holding
    every row is read only where the table names the column its day comes from.
    """
    if which not in CSV_LEDGERS:
        raise RefusedError(f"{which.value}: no supported CSV layout in CSV_LEDGERS")
    held = CSV_LEDGERS[which]
    entry = held.old_entry
    dated = entry.grain is Grain.FLAT and held.day_column is not None
    if not entry.prefix or not (dated or entry.grain in (Grain.DAY_TREE, Grain.DAY_FILE)):
        raise RefusedError(
            f"{which.value}: unsupported CSV layout {entry.grain.value} "
            f"under {'/'.join(entry.prefix)}"
        )
    return entry


def csv_root(state_dir: Path, which: LedgerName) -> Path:
    """Where this ledger's CSV sat under a state root: the prefix its old entry names."""
    return state_dir.joinpath(*require_layout(which).prefix)


def csv_file(state_dir: Path, which: LedgerName) -> Path:
    """The one CSV file a flat layout held every row in, or a refusal for any other layout."""
    entry = require_layout(which)
    if entry.grain is not Grain.FLAT:
        raise RefusedError(f"{which.value}: its CSV layout {entry.grain.value} is not one file")
    return csv_root(state_dir, which) / f"{entry.stem}{entry.suffix}"


def door_ledgers(config_dir: Path) -> list[LedgerName]:
    """Every ledger in the table that this config's registry files through the door now.

    Read from the config a run is held against, so a run over a recorded config
    takes the ledgers that config had moved, and no ledger moved since.
    """
    registry = ledger.registry_entries(
        LedgersConfig.from_json((config_dir / REGISTRY_FILENAME).read_text(encoding="utf-8"))
    )
    return [name for name in CSV_LEDGERS if registry[name].grain is Grain.RAW_AND_COMPACT]
