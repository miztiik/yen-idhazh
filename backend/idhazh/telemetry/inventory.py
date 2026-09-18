"""What does the instrument hold for one day?

The read side of `docs/concepts/telemetry.md`, at day grain. Three questions a
person asks of a run that already finished: which instrument files that day has,
how its items ended, and how long its spans took. Every answer is bounded by the
date it is asked about, so none of them costs more as the archive grows
(Guardrail #12) - the month shard a date falls in is the largest thing opened,
and it is named as a month in the report rather than counted as the day's.

Nothing here writes. `publish/` owns every projection a run produces; this file
opens what those wrote and counts it.

Each function returns the report rather than the records. The file that knows
what a field means is the file that should say what it means next to the number
(CLAUDE.md section 0b), and the router that calls these prints them unread.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from idhazh import ledger
from idhazh.assemble import month_of


def _day_files(state_root: Path, date: str) -> list[Path]:
    """Every file under `state_root` that belongs to this one date.

    A glob keyed on the date rather than a list of stores, so a store added
    tomorrow is reported without an edit here (Guardrail #6). Every day-sharded
    ledger writes `<store>/<YYYY>/<MM>/<DD>` with its own suffix - `.csv` for the
    ledgers, `.json` for day-metrics, `<DD>-<ordinal>-<shard>.jsonl` for a
    committed trace - so the stem is the whole of what they share.

    **Two depths, because a store may nest.** A one-segment glob misses
    `<group>/<store>/<YYYY>/<MM>/<DD>` and says nothing about the miss, so a
    nested store would be absent from an inventory that reported success.
    """
    year, month, day = date.split("-")
    stem = f"{year}/{month}/{day}*"
    return sorted(set(state_root.glob(f"*/{stem}")) | set(state_root.glob(f"*/*/{stem}")))


def _month_files(state_root: Path, date: str) -> list[Path]:
    """Every month shard the date falls inside. Read as a month, not as the day.

    A month shard is `<store>/<YYYY-MM>` with its own suffix, one level up from
    the day tree and deliberately so: a store keeps its month fold in its own
    directory rather than beside day shards a walker would read as the same
    shape.

    Two depths, for the reason `_day_files` gives.
    """
    stem = f"{month_of(date)}.*"
    return sorted(set(state_root.glob(f"*/{stem}")) | set(state_root.glob(f"*/*/{stem}")))


def files(state_root: Path, *, date: str) -> list[str]:
    """Which instrument files this date has, and how large each one is."""
    day_files = _day_files(state_root, date)
    month_files = _month_files(state_root, date)
    if not day_files and not month_files:
        return [f"{date}: the instrument recorded no file"]

    report = [f"{date}: {len(day_files) + len(month_files)} instrument files"]
    for path in day_files:
        relpath = path.relative_to(state_root).as_posix()
        report.append(f"  {relpath}  {path.stat().st_size} bytes")
    for path in month_files:
        relpath = path.relative_to(state_root).as_posix()
        report.append(f"  {relpath}  {path.stat().st_size} bytes, the whole month")
    return report


def outcomes(state_root: Path, *, date: str) -> list[str]:
    """How this date's items ended, counted by stage, outcome and failure code.

    One day's item-health shard and nothing else. A day the ledger never
    recorded has no file, which is not a fault: a run that planned nothing that
    day wrote nothing that day.
    """
    rows = ledger.load_item_health_shard(ledger.item_health_path(state_root, date))
    if not rows:
        return [f"{date}: the item-health ledger recorded no item"]

    counted = Counter(
        (str(row.stage), str(row.outcome), str(row.code) if row.code else "no code")
        for row in rows
    )
    report = [f"{date}: {len(rows)} items"]
    report += [
        f"  {stage} {outcome} {code}  {count} items"
        for (stage, outcome, code), count in sorted(counted.items())
    ]
    return report


def spans(state_root: Path, *, date: str) -> list[str]:
    """How long this date's spans took, totalled by span name across every shard.

    The rollup is sharded by month, so the shard is opened and filtered to the
    date. `total_ms` is a total and not a mean precisely so that it re-sums
    across shards, which is what this adds up.
    """
    path = ledger.span_rollup_path(state_root, month_of(date))
    rows = [row for row in ledger.load_span_rollup_shard(path) if row.date == date]
    if not rows:
        return [f"{date}: the span rollup recorded no span"]

    counts: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for row in rows:
        counts[str(row.span_name)] += row.count
        totals[str(row.span_name)] += row.total_ms
    report = [f"{date}: {sum(counts.values())} spans over {len(rows)} rollup rows"]
    report += [
        f"  {name}  {counts[name]} spans, {totals[name]} ms in total"
        for name in sorted(counts)
    ]
    return report
