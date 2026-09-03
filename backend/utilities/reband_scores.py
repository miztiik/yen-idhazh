"""Report how historical eval rows band under today's rules.

The eval ledger records the band that was written at score time. That is the
right history to keep, but it is the wrong column to read when the question is
"what would these rows be under the current band function?"

**It reaches only the months still at full grain.** Re-banding needs each row's
own `hhem`, `coverage`, `unsupported_numbers` and `hedge_dropped`, and a month
past `observability.scores_full_grain_months` keeps distributions rather than
rows. Those months are named in the report and are not re-banded - deliberately
lost, and printed rather than silently missing from the denominator.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from idhazh.config import load
from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.evals import archive, writer
from idhazh.evals.score import band

REQUIRED_COLUMNS = ("band", "hhem", "unsupported_numbers", "coverage", "hedge_dropped")
ORDERED_BANDS = (ConfidenceBand.HIGH.value, ConfidenceBand.MEDIUM.value, ConfidenceBand.LOW.value)
REASON_ORDER = (
    "lead coverage",
    "dropped hedge",
    "lead coverage and dropped hedge",
    "unsupported numbers",
)


@dataclass(frozen=True, slots=True)
class RebandReport:
    rows: int
    recorded: Counter[str]
    current: Counter[str]
    moves: Counter[tuple[str, str]]
    reasons: Counter[str]


def _bool_cell(value: str) -> bool:
    return value.strip().lower() == "true"


def _faithfulness(value: str) -> float | None:
    return float(value) if value.strip() else None


def _reason(row: dict[str, str], config: EvaluationConfig) -> str:
    low_coverage = float(row["coverage"]) < config.lead_coverage_min
    dropped_hedge = _bool_cell(row["hedge_dropped"])
    unsupported = int(row["unsupported_numbers"] or 0) > 0
    if low_coverage and dropped_hedge:
        return "lead coverage and dropped hedge"
    if low_coverage:
        return "lead coverage"
    if dropped_hedge:
        return "dropped hedge"
    if unsupported:
        return "unsupported numbers"
    return "other"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or ())]
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        return list(reader)


def read_ledger(state_dir: Path) -> list[dict[str, str]]:
    """Every committed row, oldest month first.

    The ledger is a directory of month shards, so a re-band that opened one file
    would report on whatever slice of history that file happened to be. Reading
    every shard is what makes the percentages below percentages of the ledger.

    Each shard's columns are checked on its own: a month written before a column
    existed has to fail by name here rather than arrive as a missing key inside
    the arithmetic.

    A tree whose every month has been summarised is refused by name. It is not
    an empty ledger and it is not a fresh clone: the rows existed and are gone,
    and only a message that says so stops somebody re-running this and believing
    the pipeline never scored anything.
    """
    shards = writer.ledger_shards(state_dir)
    if not shards:
        summarised = archive.archived_months(state_dir)
        if summarised:
            raise ValueError(
                f"every month of {(state_dir / writer.LEDGER_DIRNAME).as_posix()} has aged "
                f"out of the full-grain window - {', '.join(summarised)} exist only as "
                f"summaries, and a band is a function of one row. {archive.RAW_WINDOW_NOTE}"
            )
        raise ValueError(
            f"{(state_dir / writer.LEDGER_DIRNAME).as_posix()} holds no <YYYY-MM>.csv shard"
        )
    return [row for shard in shards for row in read_rows(shard)]


def reband(rows: Iterable[dict[str, str]], config: EvaluationConfig) -> RebandReport:
    recorded: Counter[str] = Counter()
    current: Counter[str] = Counter()
    moves: Counter[tuple[str, str]] = Counter()
    reasons: Counter[str] = Counter()
    total = 0

    for row in rows:
        total += 1
        old = row["band"]
        new = band(
            _faithfulness(row["hhem"]),
            unsupported_numbers=int(row["unsupported_numbers"] or 0),
            lead_coverage=float(row["coverage"]),
            hedge_dropped=_bool_cell(row["hedge_dropped"]),
            config=config,
        ).value
        recorded[old] += 1
        current[new] += 1
        if old != new:
            moves[(old, new)] += 1
            reasons[_reason(row, config)] += 1

    return RebandReport(
        rows=total,
        recorded=recorded,
        current=current,
        moves=moves,
        reasons=reasons,
    )


def _share(count: int, total: int) -> str:
    return f"{count / total:.1%}" if total else "0.0%"


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def lines_for(report: RebandReport, path: Path, *, archived: Sequence[str] = ()) -> list[str]:
    moved = sum(report.moves.values())
    lines = [
        f"scores: {_display_path(path)}",
        f"rows: {report.rows}",
    ]
    if archived:
        lines.append(
            f"not re-banded: {', '.join(archived)} - summarised out of the full-grain "
            "window, so those months have no row to band"
        )
    lines.append("recorded bands:")
    lines.extend(
        f"  {name}: {report.recorded[name]} ({_share(report.recorded[name], report.rows)})"
        for name in ORDERED_BANDS
    )
    lines.append("current bands:")
    lines.extend(
        f"  {name}: {report.current[name]} ({_share(report.current[name], report.rows)})"
        for name in ORDERED_BANDS
    )
    lines.append(f"rows moved: {moved} ({_share(moved, report.rows)})")
    if moved:
        lines.append("moves:")
        lines.extend(
            f"  {old} -> {new}: {count}"
            for (old, new), count in sorted(report.moves.items())
        )
        lines.append("move reasons:")
        for reason in REASON_ORDER:
            count = report.reasons[reason]
            if count:
                lines.append(f"  {reason}: {count}")
        for reason in sorted(set(report.reasons) - set(REASON_ORDER)):
            lines.append(f"  {reason}: {report.reasons[reason]}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("state"),
        help="The state directory. Every month shard under scores/ is read.",
    )
    parser.add_argument("--config", type=Path, default=Path("config"))
    args = parser.parse_args(argv)

    config = load(args.config).app.evaluation
    report = reband(read_ledger(args.state), config)
    print(
        "\n".join(
            lines_for(
                report,
                args.state / writer.LEDGER_DIRNAME,
                archived=archive.archived_months(args.state),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
