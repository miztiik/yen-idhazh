"""Emit a Parquet report of recorded visual attempts for named UTC dates."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from idhazh.command_logging import configure_command_logging
from idhazh.config import DEFAULT_CONFIG_DIR, REPO_ROOT
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.evals.visual_attempt_report import GROUP_COLUMNS, read_report
from idhazh.ledger import STATE_DIRNAME, parquet
from idhazh.ledger.arrow_schema import Column, ColumnType, columns_of


def _utc_date(value: str) -> str:
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("date must use YYYY-MM-DD")
    except ValueError as refusal:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a UTC date written YYYY-MM-DD"
        ) from refusal
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date", action="append", required=True, type=_utc_date,
        help="UTC date, YYYY-MM-DD. Repeat for each requested day.",
    )
    parser.add_argument(
        "--state-dir", type=Path, default=REPO_ROOT / STATE_DIRNAME,
        help="Local state root. Defaults to this repository's state directory.",
    )
    args = parser.parse_args(argv)
    settings = AppConfig.from_json(
        (DEFAULT_CONFIG_DIR / "idhazh.json").read_text(encoding="utf-8")
    )
    configure_command_logging(settings.logging.level)
    try:
        report = read_report(args.state_dir, args.date)
        for day in report.missing_dates:
            print(f"no recorded visual-design attempts date={day} (UTC)", file=sys.stderr)
        native = {column.name: column for column in columns_of(VisualAttemptRow)}
        columns = (
            *(native[name] for name in GROUP_COLUMNS),
            Column("attempts", ColumnType.INT64, nullable=False),
        )
        data = parquet.render(
            columns,
            report.rows,
            envelope={},
            compression=settings.ledger.compression_compact,
        )
        sys.stdout.buffer.write(data)
    except ValueError as refusal:
        print(f"visual attempt report refused: {refusal}", file=sys.stderr)
        return 1
    except OSError as refusal:
        print(f"visual attempt report I/O failed: {refusal.strerror}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
