"""Run the named CSV migration phases and report their results."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from idhazh import config, crash_trace
from idhazh.contracts.base import COMMIT_SHA_PATTERN, RUN_ID_PATTERN
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration import phases, report_lines
from utilities.ledger_migration.csv_files import left
from utilities.ledger_migration.csv_layouts import CSV_LEDGERS, door_ledgers
from utilities.ledger_migration.inputs import MigrationInputs
from utilities.ledger_migration.packing import packs_here
from utilities.ledger_migration.planning import collect_reports, plan_roots
from utilities.ledger_migration.refusals import NotProvenError, RefusedError
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


def _parser() -> argparse.ArgumentParser:
    """Named roots, months, run and commit, and at most one mode; no mode runs the full chain."""
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
        choices=[name.value for name in CSV_LEDGERS],
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
    modes.add_argument(
        "--write", action="store_true", help="Write raw rows and eligible packing; keep every CSV."
    )
    modes.add_argument("--verify", action="store_true", help="Prove CSV parity; write nothing.")
    modes.add_argument(
        "--retire", action="store_true", help="Re-plan and prove all, then delete CSV."
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="With explicit --write, file raw rows but leave compact files unchanged.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.raw_only and not args.write:
        parser.error("--raw-only requires explicit --write")
    state_dirs: list[Path] = list(dict.fromkeys(path.resolve() for path in args.state_dir))
    which = (
        list(dict.fromkeys(LedgerName(value) for value in args.ledger))
        if args.ledger
        else door_ledgers()
    )

    if args.check:
        try:
            remaining = [
                path
                for root in state_dirs
                for path in left(root, which, months=args.month)
            ]
        except (NotProvenError, RefusedError) as refusal:
            print(f"a CSV tree cannot be read: {refusal}", file=sys.stderr)
            return EXIT_NOT_PROVEN
        for line in report_lines.left_lines(remaining):
            print(line)
        return EXIT_NOT_PROVEN if remaining else EXIT_MIGRATED

    inputs = MigrationInputs(
        state_dirs=state_dirs,
        which=which,
        run_id=args.run_id,
        git_sha=args.git_sha,
        today=datetime.now(UTC).date(),
        config_dir=config.DEFAULT_CONFIG_DIR,
        months=args.month,
    )
    for root in inputs.state_dirs:
        print(
            report_lines.root_line(
                root, packs=packs_here(root, inputs.config_dir), raw_only=args.raw_only
            )
        )
    try:
        if args.plan or args.write or args.verify:
            plans = plan_roots(inputs)
            if args.write:
                moved = phases.write_roots(plans, raw_only=args.raw_only)
            elif args.verify:
                moved = phases.verify_roots(plans)
            else:
                moved = collect_reports(plans)
                for line in report_lines.preview_lines(plans):
                    print(line)
        else:
            action = phases.retire_roots if args.retire else phases.migrate_roots
            moved = action(inputs)
    except RefusedError as refusal:
        print(f"refused, nothing written: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    except NotProvenError as refusal:
        print(f"not proven, nothing deleted: {refusal}", file=sys.stderr)
        return EXIT_NOT_PROVEN
    csv_kept = args.plan or args.write or args.verify
    for root, each in moved:
        print(
            report_lines.moved_line(
                root,
                each,
                csv_kept=csv_kept,
                proven=args.verify,
                raw_only=args.raw_only,
            )
        )
    return EXIT_MIGRATED


if __name__ == "__main__":
    # A crash prints where it broke: a message can quote a ledger row it read.
    crash_trace.install()
    raise SystemExit(main())
