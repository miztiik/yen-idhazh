"""Which paths one gardener task may list for its named period window.

Task declarations own stable roots. The task's window chooses the periods below
those roots, so neither a publisher nor a local run discovers older siblings.
A compaction has no window: it is handed its ledger's marks alone, and each of
its steps names the periods it chooses as it runs.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from idhazh import ledger, month_partition
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.knobs.gardener import (
    DEFAULT_DAY_LOOKBACK_PERIODS,
    DEFAULT_MONTH_LOOKBACK_PERIODS,
    CompactionPolicy,
    DaysWindow,
    MonthsWindow,
    RetentionPolicy,
    TaskPolicy,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import ledger_marks, schedule

_TRIAL_ROOT_PREFIX = "state/pipeline-tests-"


def _month_shift(month: str, count: int) -> str:
    """Move a real month stem by a signed number of calendar months."""
    year, number = map(int, month.split("-"))
    total = year * 12 + number - 1 + count
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _newest_eligible_month(today: date, after_days: int) -> str:
    """The newest closed month old enough at 00:00 UTC on this day."""
    now = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    cursor = _month_shift(today.strftime("%Y-%m"), -1)
    while not schedule.is_month_eligible(cursor, now=now, after_days=after_days):
        cursor = _month_shift(cursor, -1)
    return cursor


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


def _fold_day_window(policy: RetentionPolicy, today: date) -> tuple[str, str] | None:
    """The closed day periods a task's independent fold may settle."""
    if policy.fold is None:
        return None
    lookback = policy.lookback or DEFAULT_DAY_LOOKBACK_PERIODS
    newest_day = schedule.newest_eligible(
        now=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        after_days=policy.fold.after_days,
    )
    first_day = newest_day - timedelta(days=lookback)
    return first_day.isoformat(), newest_day.isoformat()


def _fold_month_window(policy: RetentionPolicy, today: date) -> tuple[str, str] | None:
    """The closed month periods a task's independent fold may settle."""
    if policy.fold is None or not policy.fold.settles_months:
        return None
    lookback = policy.lookback or DEFAULT_MONTH_LOOKBACK_PERIODS
    newest = _newest_eligible_month(today, policy.fold.after_days)
    first_month = _month_shift(newest, -lookback)
    months = month_partition.months_between(first_month, newest)
    return months[0], months[-1]


def _fold_window(policy: RetentionPolicy, today: date) -> tuple[str, str] | None:
    """The main fixed period range for a task's independent fold."""
    if policy.fold is None:
        return None
    return _fold_month_window(policy, today) or _fold_day_window(policy, today)


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
    return _fold_window(policy, today)


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
        start_day + timedelta(days=offset)
        for offset in range((end_day - start_day).days + 1)
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


def _trial_paths(
    root: Path, days: tuple[date, ...], months: tuple[str, ...], *, monthly: bool
) -> set[Path]:
    """Named period paths for one pipeline-test root and its declared ledgers."""
    paths: set[Path] = set()
    if monthly:
        for month in months:
            year, number = month.split("-")
            for which in LedgerName:
                paths.add(root / which.value / year / number)
                paths.add(root / which.value / f"{month}.csv")
        return paths
    for day in days:
        suffix = Path(f"{day:%Y}/{day:%m}/{day:%d}")
        paths.add(root / "traces" / suffix)
        for which in LedgerName:
            paths.add(root / which.value / suffix)
            paths.add(root / "raw" / which.value / suffix)
            paths.add(root / which.value / f"{day:%Y-%m}.csv")
            for extension in (".csv", ".json", ".parquet"):
                paths.add(root / which.value / suffix.with_suffix(extension))
                paths.add(root / "raw" / which.value / suffix.with_suffix(extension))
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
    """Named ledger periods plus compact indexes and watermarks."""
    paths: set[Path] = set()
    state_dir = repo_root / ledger.STATE_DIRNAME
    root = repo_root / folder
    if folder.startswith("state/raw/"):
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
            sorted(ledger_marks.name_marks(repo_root / ledger.STATE_DIRNAME, policy.ledger))
        )
    if period_range is None:
        return ()
    days, months = periods_in_range(period_range)
    monthly = month_partition.is_month_stem(period_range[0])
    paths: set[Path] = set()
    for folder in (*policy.claims(), *policy.reads):
        root = repo_root / folder
        if name == "trials" and folder.startswith(_TRIAL_ROOT_PREFIX):
            paths.update(_trial_paths(root, days, months, monthly=monthly))
            continue
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
        if folder.startswith("state/raw/") or folder.startswith("state/compact/"):
            try:
                which = LedgerName(folder.removeprefix("state/raw/").removeprefix("state/compact/"))
            except ValueError:
                paths.update(_dated_paths(root, days, months, monthly=monthly))
            else:
                paths.update(
                    _ledger_paths(
                        folder, repo_root, which, days, months, monthly=monthly
                    )
                )
            continue
        paths.update(_dated_paths(root, days, months, monthly=monthly))
    if isinstance(policy, RetentionPolicy) and policy.fold is not None:
        fold_ranges = (
            (_fold_month_window(policy, today), True),
            (_fold_day_window(policy, today), False),
        )
        for fold_range, fold_monthly in fold_ranges:
            if fold_range is None or fold_range == period_range:
                continue
            fold_days, fold_months = periods_in_range(fold_range)
            for folder in policy.owns or ():
                paths.update(
                    _dated_paths(
                        repo_root / folder,
                        fold_days,
                        fold_months,
                        monthly=fold_monthly,
                    )
                )
    return tuple(sorted(paths))
