"""Run the named CSV migration phases and report their results."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN
from idhazh.contracts.ledger_name import LedgerName
from utilities import csv_ledgers, migration_phases
from utilities.csv_ledgers import NotProvenError, RefusedError
from utilities.named_inputs import month_directories

EXIT_MIGRATED: Final = 0
EXIT_NOT_PROVEN: Final = 1


def _pattern(pattern: str, what: str) -> Callable[[str], str]:
    """An argument type that takes only a value matching this pattern."""

    def take(value: str) -> str:
        if re.fullmatch(pattern, value) is None:
            raise argparse.ArgumentTypeError(f"{value!r} is not {what}")
        return value

    return take


def _month_argument(value: str) -> str:
    try:
        month_directories(Path(), [value])
    except ValueError as refusal:
        raise argparse.ArgumentTypeError(f"{value!r} is not a UTC month YYYY-MM") from refusal
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument(
        "--state-dir",
        required=True,
        action="append",
        type=Path,
        help="A tree to migrate; repeat for more.",
    )
    parser.add_argument(
        "--month",
        action="append",
        required=True,
        type=_month_argument,
        help="UTC month YYYY-MM; repeatable.",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        type=_pattern(RUN_ID_PATTERN, "a run id, <YYYY-MM-DD>-<number>"),
        help="The run every file names. Use the same one on a second run.",
    )
    parser.add_argument(
        "--git-sha",
        required=True,
        type=_pattern(COMMIT_SHA_PATTERN, "the forty hex digits of a commit"),
        help="The commit this checkout is at, which every file names: git rev-parse HEAD.",
    )
    parser.add_argument(
        "--ledger",
        action="append",
        choices=[name.value for name in csv_ledgers.CSV_LEDGERS],
        default=None,
        help=(
            "A ledger to migrate or check; repeat it for more. Without it, every ledger "
            "in the table that config/ledgers.json files as raw-and-compact."
        ),
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--check", action="store_true", help="Write nothing. Exit 1 if any CSV file remains."
    )
    modes.add_argument(
        "--plan", action="store_true", help="Preview validated inputs; write nothing."
    )
    modes.add_argument("--write", action="store_true", help="Write and pack; keep every CSV.")
    modes.add_argument("--verify", action="store_true", help="Prove CSV parity; write nothing.")
    modes.add_argument(
        "--retire", action="store_true", help="Re-plan and prove all, then delete CSV."
    )
    args = parser.parse_args(argv)
    state_dirs: list[Path] = list(dict.fromkeys(path.resolve() for path in args.state_dir))
    which = (
        list(dict.fromkeys(LedgerName(value) for value in args.ledger))
        if args.ledger
        else csv_ledgers.door_ledgers()
    )

    if args.check:
        try:
            remaining = [
                (root, path)
                for root in state_dirs
                for path in csv_ledgers.left(root, which, months=args.month)
            ]
        except (NotProvenError, RefusedError) as refusal:
            print(f"a CSV tree cannot be read: {refusal}", file=sys.stderr)
            return EXIT_NOT_PROVEN
        for _, path in remaining:
            print(f"{csv_ledgers.root_label(path)} is still a CSV")
        print(f"{len(remaining)} CSV file(s) left")
        return EXIT_NOT_PROVEN if remaining else EXIT_MIGRATED

    inputs = migration_phases.MigrationInputs(
        state_dirs=state_dirs,
        which=which,
        run_id=args.run_id,
        git_sha=args.git_sha,
        today=datetime.now(UTC).date(),
        months=args.month,
    )
    for root in inputs.state_dirs:
        mode = "packs" if migration_phases.packs_here(root, inputs.config_dir) else "raw only"
        print(f"{csv_ledgers.root_label(root)}: {mode}")
    try:
        if args.plan or args.write or args.verify:
            plans = migration_phases.plan_roots(inputs)
            if args.write:
                moved = migration_phases.write_roots(plans)
            elif args.verify:
                moved = migration_phases.verify_roots(plans)
            else:
                moved = migration_phases.collect_reports(plans)
                for plan in plans:
                    for name, days in plan.planned.items():
                        if not days:
                            print(
                                f"{csv_ledgers.root_label(plan.state_dir)}: {name.value}: "
                                f"no CSV inputs in {', '.join(plan.inputs.months)}"
                            )
                        for day, held in days.items():
                            print(
                                f"{csv_ledgers.root_label(plan.state_dir)}: {name.value} {day}: "
                                f"{'write needed' if held.changed else 'rows already held'}; "
                                f"{len(held.files)} CSV file(s), {len(held.rows)} row(s)"
                            )
        else:
            action = (
                migration_phases.retire_roots if args.retire else migration_phases.migrate_roots
            )
            moved = action(inputs)
    except RefusedError as refusal:
        print(f"refused, nothing written: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    for root, each in moved:
        label = csv_ledgers.root_label(root)
        print(
            f"{label}: {each.which.value}: {each.csv_files} CSV file(s), "
            f"{each.csv_bytes} bytes, over "
            f"{each.days} day(s) -> {each.rows} row(s); {each.filed} day(s) filed, "
            f"{len(each.packed)} day(s) packed ({each.packed[0] if each.packed else '-'} to "
            f"{each.packed[-1] if each.packed else '-'}); "
            f"{len(each.compaction_written)} compaction file(s) written, "
            f"{len(each.compaction_deleted)} deleted; "
            f"{'CSV kept' if args.plan or args.write or args.verify else 'every CSV file deleted'}"
            f"{'; parity proven' if args.verify else ''}"
        )
    return EXIT_MIGRATED


if __name__ == "__main__":
    raise SystemExit(main())
