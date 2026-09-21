"""The fingerprint column's retirement trigger, answered from rows and not a date.

The console reads a day's pipeline identity from its recorded input manifest
where it has one, and falls back to the score ledger's `pipeline_fingerprint`
column where it does not. The fallback is for days written before the manifest
existed, so it retires itself - and "has it retired yet" is a question about
what the rows hold, which is why it is an operator surface rather than a
collected test (CLAUDE.md section 13).

Every case below builds its own two-day ledger in a temp directory. Nothing
here reads `state/scores/`: that collection grows, and a test over it would
cost more every run and would go red because somebody published a day.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utilities.fingerprint_column_due import main

pytestmark = pytest.mark.contract

HEADER = "date,run_id,pipeline_fingerprint\n"


def _ledger(root: Path, days: dict[str, str]) -> Path:
    """A score ledger holding one row per named day, with the stamp given."""
    for day, stamp in days.items():
        year, month, date = day.split("-")
        shard = root / "scores" / year / month / f"{date}.csv"
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text(f"{HEADER}{day},{day}-1,{stamp}\n", encoding="utf-8", newline="")
    return root


def _config(root: Path, window: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "idhazh.json").write_text(
        json.dumps({"console": {"max_window_days": window}}), encoding="utf-8"
    )
    return root


def _read(capsys: pytest.CaptureFixture[str]) -> dict[str, str]:
    out = capsys.readouterr().out.splitlines()
    return dict(line.split("=", 1) for line in out if "=" in line)


def test_a_stamped_day_inside_the_window_holds_the_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _ledger(tmp_path / "state", {"2026-09-10": "abc123", "2026-09-11": ""})
    config = _config(tmp_path / "config", 366)

    assert (
        main(["--state-root", str(state), "--config-root", str(config), "--today", "2026-09-11"])
        == 0
    )

    said = _read(capsys)
    assert said["due"] == "false"
    assert said["stamped_days"] == "1"
    assert said["newest_stamped_day"] == "2026-09-10"
    # A window that walks back from today, so the stamped day leaves it a window
    # later. The date is derived from the rows rather than written down anywhere.
    assert said["clear_on"] == "2027-09-11"


def test_the_column_goes_once_the_stamped_days_fall_out_of_the_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _ledger(tmp_path / "state", {"2026-09-10": "abc123"})
    config = _config(tmp_path / "config", 7)

    assert (
        main(["--state-root", str(state), "--config-root", str(config), "--today", "2026-09-30"])
        == 0
    )

    said = _read(capsys)
    assert said["due"] == "true"
    assert said["stamped_rows"] == "0"
    assert said["clear_on"] == "now"


def test_an_empty_column_is_not_a_stamp(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Every shard written after the cutover still has the column. Counting the
    # column instead of its contents would report the fallback load-bearing forever.
    state = _ledger(tmp_path / "state", {"2026-09-14": "", "2026-09-15": "   "})
    config = _config(tmp_path / "config", 366)

    assert (
        main(["--state-root", str(state), "--config-root", str(config), "--today", "2026-09-15"])
        == 0
    )

    said = _read(capsys)
    assert said["due"] == "true"
    assert said["days_read"] == "2"
    assert said["stamped_days"] == "0"
