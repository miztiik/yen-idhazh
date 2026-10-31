"""Group recorded visual attempts for named UTC dates without inventing missing evidence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.ledger.ledger_files import LedgerReadStatus, load_days

GROUP_COLUMNS: Final = (
    "date",
    "potential_primary",
    "state",
    "rejection_reason",
    "planned_type",
    "rendered_type",
)

type ReportRow = dict[str, str | int | None]


@dataclass(frozen=True, slots=True)
class VisualAttemptReport:
    """The counted groups and requested UTC dates with no recorded rows."""

    rows: list[ReportRow]
    missing_dates: tuple[str, ...]


def read_report(state_dir: Path, days: Collection[str]) -> VisualAttemptReport:
    """Count settled attempts, refusing an incomplete or wholly unrecorded selection."""
    status = LedgerReadStatus()
    rows = load_days(
        state_dir,
        LedgerName.VISUAL_DESIGN_ATTEMPTS,
        days,
        model=VisualAttemptRow,
        read_status=status,
    )
    if not status.complete:
        raise ValueError("incomplete visual-design-attempts read; no report produced")

    missing_dates = tuple(sorted(set(days) - {row.date for row in rows}))
    if not rows:
        raise ValueError(
            f"no records for the requested UTC dates: {', '.join(missing_dates)}; "
            "no report produced"
        )

    counts: Counter[tuple[str | None, ...]] = Counter(
        (
            row.date,
            row.potential_primary,
            row.state,
            row.rejection_reason,
            row.planned_type,
            row.rendered_type,
        )
        for row in rows
    )
    report: list[ReportRow] = []
    for group in sorted(
        counts, key=lambda group: tuple(cell if cell is not None else "" for cell in group)
    ):
        record: ReportRow = dict(zip(GROUP_COLUMNS, group, strict=True))
        record["attempts"] = counts[group]
        report.append(record)
    return VisualAttemptReport(report, missing_dates)
