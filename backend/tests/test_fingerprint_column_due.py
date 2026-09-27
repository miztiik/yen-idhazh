"""The fingerprint column's retirement trigger, answered from rows and not a date.

The console reads a day's pipeline identity from its recorded input manifest
where it has one, and falls back to the score ledger's `pipeline_fingerprint`
column where it does not. The fallback is for days written before the manifest
existed, so it retires itself - and "has it retired yet" is a question about
what the rows hold, which is why it is an operator surface rather than a
collected test (CLAUDE.md section 13).

Every case below builds its own ledger in a temp directory, laid out the way a
run leaves one: a directory a day, with each writer's file in it and, once the
day is folded, its `settled.csv`. The rows are the committed eval-row fixture
re-dated, so every cell has the shape a committed row has. Nothing here reads
`state/scores/`: that collection grows, and a test over it would cost more every
run and would go red because somebody published a day.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, fold, read_text, seed_scores

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob, derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
from utilities.fingerprint_column_due import main

pytestmark = pytest.mark.contract

#: A committed row's shape, stamp included. Read inside each test, never here.
FIXTURE = CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"


def _a_row(day: str, *, stamped: bool) -> EvalRow:
    """One measurement on `day`, with or without the stamp the fixture carries.

    Each day gets its own address, so the writer files it as a new measurement
    rather than as a repeat of the day before.
    """
    held = json.loads(read_text(FIXTURE))
    address = f"{held['source_url']}-{day}"
    held.update(
        date=day,
        run_id=f"{day}-1",
        scored_at=f"{day}T06:18:02Z",
        source_url=address,
        url_key=derive_url_key(address),
    )
    if not stamped:
        held["pipeline_fingerprint"] = None
    return EvalRow.model_validate(held)


def _ledger(root: Path, days: dict[str, bool]) -> Path:
    """A score ledger holding one row per named day, written by the real writer."""
    for day, stamped in days.items():
        seed_scores(root, [_a_row(day, stamped=stamped)], run_id=f"{day}-1")
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


def _ask(state: Path, config: Path, today: str) -> int:
    return main(["--state-root", str(state), "--config-root", str(config), "--today", today])


def test_a_stamped_day_inside_the_window_holds_the_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _ledger(tmp_path / "state", {"2026-09-10": True, "2026-09-11": False})
    config = _config(tmp_path / "config", 366)

    assert _ask(state, config, "2026-09-11") == 0

    said = _read(capsys)
    assert said["due"] == "false"
    assert said["days_read"] == "2"
    assert said["stamped_days"] == "1"
    assert said["newest_stamped_day"] == "2026-09-10"
    # A window that walks back from today, so the stamped day leaves it a window
    # later. The date is derived from the rows rather than written down anywhere.
    assert said["clear_on"] == "2027-09-11"


def test_the_column_goes_once_the_stamped_days_fall_out_of_the_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _ledger(tmp_path / "state", {"2026-09-10": True})
    config = _config(tmp_path / "config", 7)

    assert _ask(state, config, "2026-09-30") == 0

    said = _read(capsys)
    assert said["due"] == "true"
    assert said["stamped_rows"] == "0"
    assert said["clear_on"] == "now"


def test_an_empty_column_is_not_a_stamp(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Every row written after the cutover still has the column. Counting the
    # column instead of its contents would report the fallback load-bearing forever.
    state = _ledger(tmp_path / "state", {"2026-09-14": False, "2026-09-15": False})
    config = _config(tmp_path / "config", 366)

    assert _ask(state, config, "2026-09-15") == 0

    said = _read(capsys)
    assert said["due"] == "true"
    assert said["days_read"] == "2"
    assert said["stamped_days"] == "0"


def test_a_stamped_row_in_a_folded_day_directory_holds_the_column_and_counts_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The layout the committed ledger really has, which the tool once walked past.

    The day was folded into `settled.csv`, and a late writer's file beside it
    repeats the same measurement. A reader looking for `<DD>.csv` finds no file
    and calls the column retired; a reader that adds the two files up counts the
    row twice.
    """
    day = "2026-09-12"
    state = _ledger(tmp_path / "state", {day: True})
    fold(state, day)
    folder = ledger.path(state, LedgerName.SCORES, day)
    late = ledger.day_shard_path(
        state,
        LedgerName.SCORES,
        date=day,
        run_id=f"{day}-2",
        attempt=1,
        job=ServerJob.ASSEMBLE,
        shard=0,
    )
    late.write_bytes((folder / day_shards.SETTLED_NAME).read_bytes())
    config = _config(tmp_path / "config", 366)

    assert sorted(path.name for path in folder.iterdir()) == sorted(
        [day_shards.SETTLED_NAME, late.name]
    )
    assert _ask(state, config, "2026-09-20") == 0

    said = _read(capsys)
    assert said["due"] == "false"
    assert said["days_read"] == "1"
    assert said["stamped_days"] == "1"
    assert said["stamped_rows"] == "1"
    assert said["newest_stamped_day"] == day
