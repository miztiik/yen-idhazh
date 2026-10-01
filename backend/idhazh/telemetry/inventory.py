"""What does the instrument hold for one day?

The read side of `docs/concepts/telemetry.md`, at day grain. Two questions a
person asks of a run that already finished: which instrument files that day has,
and how its items ended. Every answer is bounded by the
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
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName


def _day_files(state_root: Path, date: str) -> list[Path]:
    """Every file under `state_root` that belongs to this one date.

    A glob keyed on the date rather than a list of ledgers, so a ledger added
    tomorrow is reported without an edit here (Guardrail #6). Every day-sharded
    ledger writes `<ledger>/<YYYY>/<MM>/<DD>` with its own suffix, so the stem is
    the whole of what they share.

    **A day is a file in some ledgers and a directory of writer-owned files in
    others**, and the directory is opened rather than weighed. A directory's own
    `st_size` is the size of the entry, not of what is in it, so reporting one
    would print a number that looks like bytes and is not.

    **Three depths, because a ledger may nest.** A one-segment glob misses
    `<group>/<ledger>/<YYYY>/<MM>/<DD>` and says nothing about the miss, so a
    nested ledger would be absent from an inventory that reported success. The
    ledger door files a raw day at `raw/<ledger>/<YYYY>/<MM>/<DD>/` and a packed
    one at `compact/<ledger>/daily/<YYYY>/<MM>/<DD>`, which is the third depth.
    """
    year, month, day = date.split("-")
    stem = f"{year}/{month}/{day}*"
    found = {
        entry
        for pattern in (f"*/{stem}", f"*/*/{stem}", f"*/*/*/{stem}")
        for entry in state_root.glob(pattern)
    }
    files: set[Path] = set()
    for entry in found:
        if entry.is_dir():
            files.update(child for child in entry.iterdir() if child.is_file())
        else:
            files.add(entry)
    return sorted(files)


def _month_files(state_root: Path, date: str) -> list[Path]:
    """Every month shard the date falls inside. Read as a month, not as the day.

    A month shard is `<ledger>/<YYYY-MM>` with its own suffix, one level up from
    the day tree and deliberately so: a ledger keeps its month fold in its own
    directory rather than beside day shards a walker would read as the same
    shape.

    Two depths, for the reason `_day_files` gives, and a third for the ledger
    door's packed month, `compact/<ledger>/monthly/<YYYY>/<MM>`.
    """
    stem = f"{month_of(date)}.*"
    year, month = month_of(date).split("-")
    patterns = (f"*/{stem}", f"*/*/{stem}", f"*/*/*/{year}/{month}.*")
    return sorted({entry for pattern in patterns for entry in state_root.glob(pattern)})


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

    One day of the census, settled, and nothing else. Every work shard of a run
    files its own raw file, so the count is over all of them and a re-run's
    second attempt does not add its items a second time.

    A day the ledger never recorded holds no row, which is not a fault: a run
    that planned nothing that day wrote nothing that day.
    """
    rows = ledger.load_days(state_root, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow)
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
