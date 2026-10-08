"""How does each migration result read as a line on standard output?"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from utilities.ledger_migration.path_labels import label_path
from utilities.ledger_migration.planning import Moved, RootPlan


def root_line(root: Path, *, packs: bool, raw_only: bool = False) -> str:
    """Whether a named root is packed or filed raw."""
    if raw_only:
        return f"{label_path(root)}: raw only requested; packing outstanding"
    return f"{label_path(root)}: {'packs' if packs else 'raw only'}"


def left_lines(paths: Sequence[Path]) -> list[str]:
    """Each CSV file still left, then how many there are."""
    lines = [f"{label_path(path)} is still a CSV" for path in paths]
    return [*lines, f"{len(paths)} CSV file(s) left"]


def preview_lines(plans: Sequence[RootPlan]) -> list[str]:
    """Each planned day of each named ledger, or that a ledger has no CSV in the named months."""
    lines: list[str] = []
    for plan in plans:
        for name, days in plan.planned.items():
            if not days:
                lines.append(
                    f"{label_path(plan.state_dir)}: {name.value}: "
                    f"no CSV inputs in {', '.join(plan.inputs.months)}"
                )
            for day, held in days.items():
                lines.append(
                    f"{label_path(plan.state_dir)}: {name.value} {day}: "
                    f"{'write needed' if held.changed else 'rows already held'}; "
                    f"{len(held.files)} CSV file(s), {len(held.rows)} row(s)"
                )
    return lines


def moved_line(
    root: Path, each: Moved, *, csv_kept: bool, proven: bool, raw_only: bool = False
) -> str:
    """What one ledger's migration did at one root, in the numbers a reviewer asks for."""
    return (
        f"{label_path(root)}: {each.which.value}: {each.csv_files} CSV file(s), "
        f"{each.csv_bytes} bytes, over "
        f"{each.days} day(s) -> {each.rows} row(s); {each.filed} day(s) filed, "
        f"{len(each.packed)} day(s) packed ({each.packed[0] if each.packed else '-'} to "
        f"{each.packed[-1] if each.packed else '-'}); "
        f"{len(each.compaction_written)} compaction file(s) written, "
        f"{len(each.compaction_deleted)} deleted; "
        f"{'CSV kept' if csv_kept else 'every CSV file deleted'}"
        f"{'; parity proven' if proven else ''}"
        f"{'; raw-only write complete; packing and parity proof outstanding' if raw_only else ''}"
    )
