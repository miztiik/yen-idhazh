"""Which paths one gardener task may list for its named period window.

Task declarations own stable roots. The task's window chooses the periods below
those roots, so neither a publisher nor a local run discovers older siblings.
A compaction has no window: it is handed its ledger's marks alone, and each of
its steps names the periods it chooses as it runs.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path, PurePosixPath

from idhazh import ledger, month_partition
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    DaysWindow,
    MonthsWindow,
    RetentionPolicy,
    TaskPolicy,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import ledger_marks


def _day_window(name: str, policy: RetentionPolicy, today: date) -> tuple[str, str]:
    """The task's expired days and its configured lookback, oldest first."""
    if not isinstance(policy.window, DaysWindow):
        raise ValueError(f"{name} does not have a day window")
    kept_from = today - timedelta(
        days=policy.window.value
        if name in {"digest-fragments", "visual-prune"}
        else policy.window.value - 1
    )
    last = kept_from - timedelta(days=1)
    first = last - timedelta(days=policy.lookback_periods)
    return first.isoformat(), last.isoformat()


def _month_window(policy: RetentionPolicy, today: date) -> tuple[str, str]:
    """The expired months and their configured lookback, oldest first."""
    if not isinstance(policy.window, MonthsWindow):
        raise ValueError("this task does not have a month window")
    kept_from = month_partition.oldest_month_kept(today, policy.window.value)
    first = month_partition.months_before(kept_from, policy.lookback_periods + 1)
    return first[0], first[-1]


def scheduled_range(
    name: str, policy: TaskPolicy, today: date
) -> tuple[str, str] | None:
    """The fixed period range this scheduled retention task may read, or None for any other kind.

    A compaction has none: each of its steps chooses its own periods from its
    ledger's marks.
    """
    if not isinstance(policy, RetentionPolicy):
        return None
    if isinstance(policy.window, DaysWindow):
        return _day_window(name, policy, today)
    if isinstance(policy.window, MonthsWindow):
        return _month_window(policy, today)
    return None


def periods_in_range(period_range: tuple[str, str]) -> tuple[tuple[date, ...], tuple[str, ...]]:
    """Expand one inclusive date or month range into its named periods."""
    first_text, last_text = period_range
    if month_partition.is_month_stem(first_text) and month_partition.is_month_stem(last_text):
        months = tuple(month_partition.months_between(first_text, last_text))
        days = tuple(
            date(year, month, offset + 1)
            for stem in months
            for year, month in [tuple(map(int, stem.split("-")))]
            for offset in range(calendar.monthrange(year, month)[1])
        )
        return days, months
    if month_partition.is_month_stem(first_text) or month_partition.is_month_stem(last_text):
        raise ValueError("range endpoints must both be UTC dates or both be YYYY-MM months")
    start_day, end_day = date.fromisoformat(first_text), date.fromisoformat(last_text)
    if (
        start_day > end_day
        or start_day.isoformat() != first_text
        or end_day.isoformat() != last_text
    ):
        raise ValueError("day range endpoints must be ordered YYYY-MM-DD dates")
    days = tuple(
        start_day + timedelta(days=offset) for offset in range((end_day - start_day).days + 1)
    )
    months = tuple(sorted({day.strftime("%Y-%m") for day in days}))
    return days, months


def _dated_paths(
    root: Path, days: tuple[date, ...], months: tuple[str, ...], *, monthly: bool
) -> set[Path]:
    """Named day and month paths in the common dated-tree layouts."""
    paths: set[Path] = set()
    if monthly:
        for month in months:
            year, number = month.split("-")
            folder = root / year / number
            paths.update(
                {
                    folder,
                    root / f"{month}.csv",
                    root / f"{month}.json",
                    root / f"{month}.parquet",
                    folder.with_suffix(".csv"),
                    folder.with_suffix(".parquet"),
                    folder / "settled.csv",
                }
            )
    else:
        for day in days:
            folder = root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
            paths.update(
                {
                    folder,
                    folder.with_suffix(".csv"),
                    folder.with_suffix(".json"),
                    folder.with_suffix(".jsonl"),
                    folder.with_suffix(".parquet"),
                }
            )
    return paths


def _ledger_paths(
    folder: str,
    repo_root: Path,
    which: LedgerName,
    days: tuple[date, ...],
    months: tuple[str, ...],
    *,
    monthly: bool,
) -> set[Path]:
    """Named ledger periods plus compact indexes."""
    paths: set[Path] = set()
    parts = PurePosixPath(folder).parts
    tier_index = next(
        (index for index, part in enumerate(parts) if part in {"raw", "compact"}), None
    )
    if tier_index is None:
        raise ValueError(f"{folder} is not a raw or compact ledger folder")
    state_dir = repo_root.joinpath(*parts[:tier_index])
    root = repo_root / folder
    if parts[tier_index] == "raw":
        if monthly:
            for month in months:
                paths.add(root / month[:4] / month[5:7])
        else:
            for day in days:
                paths.add(root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}")
        return paths

    if monthly:
        for month in months:
            paths.add(root / Period.DAILY.value / month[:4] / month[5:7])
            for fmt in Format:
                paths.add(ledger.compact_path(state_dir, which, Period.MONTHLY, month, fmt=fmt))
    else:
        for day in days:
            stamp = day.isoformat()
            for fmt in Format:
                paths.add(ledger.compact_path(state_dir, which, Period.DAILY, stamp, fmt=fmt))
    for year in sorted({month[:4] for month in months}):
        for fmt in Format:
            paths.add(ledger.compact_path(state_dir, which, Period.YEARLY, year, fmt=fmt))
    paths.update(ledger_marks.name_marks(state_dir, which))
    return paths


def paths_for_task(
    repo_root: Path,
    name: str,
    policy: TaskPolicy,
    period_range: tuple[str, str] | None,
    *,
    today: date,
) -> tuple[Path, ...]:
    """The exact period roots this task may list, each one file or one named period.

    A compaction lists its ledger's marks and nothing else, whatever the range:
    each of its steps names the periods it chooses as it runs.
    """
    if isinstance(policy, CompactionPolicy):
        return tuple(
            sorted(
                path
                for state_root in policy.state_roots
                for path in ledger_marks.name_marks(
                    repo_root.joinpath(*PurePosixPath(state_root).parts), policy.ledger
                )
            )
        )
    if period_range is None:
        return ()
    days, months = periods_in_range(period_range)
    monthly = month_partition.is_month_stem(period_range[0])
    paths: set[Path] = set()
    for folder in (*policy.claims(), *policy.reads):
        root = repo_root / folder
        if (
            name == "visual-prune"
            and isinstance(policy, RetentionPolicy)
            and isinstance(policy.window, DaysWindow)
        ):
            first_kept = today - timedelta(days=policy.window.value)
            paths.update(
                _dated_paths(
                    root,
                    (first_kept,),
                    (first_kept.strftime("%Y-%m"),),
                    monthly=False,
                )
            )
        parts = PurePosixPath(folder).parts
        tier_index = next(
            (index for index, part in enumerate(parts) if part in {"raw", "compact"}), None
        )
        if tier_index is not None and parts[tier_index] in {"raw", "compact"}:
            suffix = parts[tier_index + 1 :]
            which = ledger.door_ledger_at(tuple(suffix))
            if which is None:
                paths.update(_dated_paths(root, days, months, monthly=monthly))
            else:
                paths.update(_ledger_paths(folder, repo_root, which, days, months, monthly=monthly))
            continue
        paths.update(_dated_paths(root, days, months, monthly=monthly))
    return tuple(sorted(paths))
