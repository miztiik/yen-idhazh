"""Verify committed pipeline-test door files under explicitly named state roots."""

from __future__ import annotations

import argparse
import calendar
import sys
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.stored_output import check_compact_period, check_raw_day


def _root(repo_root: Path, value: str) -> Path:
    """One POSIX root from a command line or plan, relative to the repository."""
    return repo_root.joinpath(*value.split("/"))


def _month_days(month: str) -> tuple[str, ...]:
    """Every UTC day in one `YYYY-MM` month."""
    first = date.fromisoformat(f"{month}-01")
    if first.strftime("%Y-%m") != month:
        raise ValueError(f"{month!r} is not a YYYY-MM UTC month")
    return tuple(
        date(first.year, first.month, day).isoformat()
        for day in range(1, calendar.monthrange(first.year, first.month)[1] + 1)
    )


def refusals(
    repo_root: Path,
    *,
    roots: Sequence[str],
    ledgers: Iterable[LedgerName],
    months: Sequence[str],
) -> list[str]:
    """Why the named committed trial roots do not read back, one line each."""
    days_by_month = {month: _month_days(month) for month in months}
    found: list[str] = []
    for root_name in roots:
        state_dir = _root(repo_root, root_name)
        for which in ledgers:
            for month, days in days_by_month.items():
                for day in days:
                    try:
                        check_raw_day(state_dir, which, day)
                        check_compact_period(state_dir, which, Period.DAILY, day)
                    except ValueError as refusal:
                        found.append(f"{root_name} {which.value} {day}: {refusal}")
                for period, covers in ((Period.MONTHLY, month), (Period.YEARLY, month[:4])):
                    try:
                        check_compact_period(state_dir, which, period, covers)
                    except ValueError as refusal:
                        found.append(f"{root_name} {which.value} {covers}: {refusal}")
    return found


def verify(
    repo_root: Path,
    *,
    roots: Sequence[str],
    ledgers: Iterable[LedgerName],
    months: Sequence[str],
) -> None:
    """Refuse if any named root, ledger or month fails stored-output validation."""
    if not roots:
        raise ValueError("verify needs at least one root")
    ledgers = tuple(ledgers)
    if not ledgers:
        raise ValueError("verify needs at least one ledger")
    if not months:
        raise ValueError("verify needs at least one UTC month")
    rejected = refusals(repo_root, roots=roots, ledgers=ledgers, months=months)
    if rejected:
        raise ValueError("\n".join(rejected))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path())
    parser.add_argument("--root", action="append", default=[], help="POSIX path to a state root.")
    parser.add_argument("--ledger", action="append", default=[], help="Ledger name to verify.")
    parser.add_argument("--month", action="append", default=[], help="UTC month, YYYY-MM.")
    args = parser.parse_args(argv)

    try:
        ledgers = [LedgerName(value) for value in args.ledger]
        verify(args.repo_root, roots=args.root, ledgers=ledgers, months=args.month)
    except ValueError as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
