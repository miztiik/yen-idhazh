"""Does the row a shard sealed reach the ledger, or is it rebuilt on the way?

`test_work_health_payload.py` asks whether the work stage leaves its row on
disk. This asks the other half: whether the census reads that file back. Until
it did, the row was written by the worker and then ignored, and the day's ledger
carried a rebuild from the article and the summary payloads - which between them
cannot say what the machine was, what the calls cost, or how long the item
waited.

Two writers reach that ledger and `ledger.append_item_health` keeps the FIRST
row for a key, so the write order would decide which row a day keeps. The tests
below take that question off the table rather than assuming an answer: both
writers now derive the row from the same sealed file, so they agree cell for
cell and the order buys nothing.

Every test is driven from the fixture plan's five items over captured pages and
recorded replies - no network, nothing mocked (Guardrail #7), and a cost that
does not move when the archive grows (Guardrail #12).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text
from pytest import MonkeyPatch

from idhazh import config, ledger, telemetry
from idhazh.contracts.article import Article
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.runtime_counters import ServerJob
from idhazh.contracts.summary import Summary
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.record import stage_record
from idhazh.telemetry.census import EXTRACTION_CELLS
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import _work_stage, isolate_ledgers

pytestmark = pytest.mark.slow

#: The fixture plan's size. Named once so a sixth item moves one line.
PLANNED_ITEMS: Final = 5

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)


def worked(tmp_path: Path, monkeypatch: MonkeyPatch) -> tuple[RunPlan, Path]:
    """One real work stage with every output root inside the test's own tree."""
    isolate_ledgers(tmp_path, monkeypatch)
    run_plan, items_dir, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
    )
    return run_plan, items_dir


def sealed(items_dir: Path) -> dict[str, ItemHealthRow]:
    """The row each shard sealed for its item, read back off disk.

    Read inside the test rather than at module scope, so an unexpected shape
    fails the test that wanted it instead of the whole file (CLAUDE.md section
    13).
    """
    return {
        path.name.removesuffix(HEALTH_SUFFIX): ItemHealthRow.from_json(read_text(path))
        for path in sorted(items_dir.glob(f"*{HEALTH_SUFFIX}"))
    }


def committed(state_dir: Path, date: str) -> dict[str, ItemHealthRow]:
    """The row the day's ledger kept for each item."""
    path = ledger.item_health_path(state_dir, date)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [ItemHealthRow.from_csv_row(record) for record in csv.DictReader(handle)]
    return {row.item_id: row for row in rows}


def filled(row: ItemHealthRow) -> set[str]:
    """Which of the row's columns carry a value."""
    return {name for name in ItemHealthRow.csv_columns() if getattr(row, name) is not None}


def rebuilt_from_payloads(
    items_dir: Path,
    planned: PlannedItem,
    run_plan: RunPlan,
    *,
    shard: int | None = None,
    job: ServerJob | None = None,
) -> ItemHealthRow:
    """What the census would have said with no sealed row to read.

    This is the fallback path, driven from the same payloads the run left on
    disk, so the two rows in the comparison describe one item on one run.
    `shard` and `job` are the caller's own pair, which the fallback takes and a
    preferred row ignores in favour of what the worker sealed.
    """
    article_path = items_dir / f"{planned.item_id}.article.json"
    summary_path = items_dir / f"{planned.item_id}.summary.json"
    return telemetry.census_row(
        recorded=None,
        planned=planned,
        article=Article.from_json(read_text(article_path)) if article_path.exists() else None,
        summary=Summary.from_json(read_text(summary_path)) if summary_path.exists() else None,
        date=run_plan.date,
        run_id=run_plan.run_id,
        shard=shard,
        job=job,
    )


def test_every_cell_the_shard_sealed_reaches_the_days_ledger(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The row the worker validated is the row the day keeps, cell for cell.

    The three extraction cells are the exception and they are named rather than
    excused: the work stage does not measure them, so the census lays its own
    reading over the sealed row. Everything else is the shard's own number.
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch)
    state = tmp_path / "state"

    stage_record(run_plan, settings=config.load(CONFIG_DIR))

    kept = committed(state, run_plan.date)
    on_disk = sealed(items_dir)
    assert set(kept) == set(on_disk) == {item.item_id for item in run_plan.items}
    assert len(kept) == PLANNED_ITEMS
    for item_id, row in kept.items():
        moved = {
            name
            for name in ItemHealthRow.csv_columns()
            if getattr(row, name) != getattr(on_disk[item_id], name)
        }
        assert moved <= set(EXTRACTION_CELLS), f"{item_id} lost cells its shard had measured"


def test_the_ledger_row_says_more_than_the_payloads_could(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Preferring the sealed row has to be worth the read, so measure it here.

    The comparison is a strict superset rather than a count, because a count
    written here is a number that has to be edited every time a column starts
    being filled - and the day somebody edits it down is the day the ratchet
    stops holding.
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch)
    state = tmp_path / "state"

    stage_record(run_plan, settings=config.load(CONFIG_DIR))

    kept = committed(state, run_plan.date)
    for planned in run_plan.items:
        rebuild = rebuilt_from_payloads(items_dir, planned, run_plan)
        assert filled(rebuild) < filled(kept[planned.item_id]), (
            f"{planned.item_id} gained nothing from the row its shard sealed"
        )


def test_which_writer_reaches_the_ledger_first_does_not_change_the_row(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The sharp edge, blunted: both writers derive the row from the same file.

    `ledger.append_item_health` keeps the first row for a key, so whichever
    writer arrives first decides what the day carries forever - the file is
    append-only and cannot correct a row. That used to be a real fork, because
    the two stages ran two derivations. It is not one any more: both read the
    row the shard sealed, and this test is what says so.

    One work stage feeds both arms. Two runs would differ in every timing cell
    and prove nothing about the derivation.
    """
    settings = config.load(CONFIG_DIR)
    run_plan, _ = worked(tmp_path, monkeypatch)
    state = tmp_path / "state"

    stage_record(run_plan, settings=settings)
    after_the_worker = committed(state, run_plan.date)

    ledger.item_health_path(state, run_plan.date).unlink()
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")
    after_assemble = committed(state, run_plan.date)

    assert set(after_the_worker) == set(after_assemble)
    assert len(after_the_worker) == PLANNED_ITEMS
    for item_id, row in after_the_worker.items():
        assert row == after_assemble[item_id], f"{item_id} depends on which writer got there first"


def test_an_item_whose_shard_sealed_nothing_still_gets_a_census_line(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The fallback earns its place on a run whose worker died mid-item.

    Nothing sealed a row for that item, so there is nothing to prefer. The day
    still needs a line for it, and the line says what the payloads can say - the
    answer to "why is this column empty" is "no shard recorded this item", not
    "the census dropped it".
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch)
    state = tmp_path / "state"
    orphan = run_plan.items[0]
    (items_dir / f"{orphan.item_id}{HEALTH_SUFFIX}").unlink()

    stage_record(run_plan, settings=config.load(CONFIG_DIR))

    kept = committed(state, run_plan.date)
    # `stage_record` runs as shard 0 of 1 in the `work` job here and stamps both
    # on a row it rebuilt, which is the one moment either is known.
    rebuild = rebuilt_from_payloads(items_dir, orphan, run_plan, shard=0, job=ServerJob.WORK)
    assert set(kept) == {item.item_id for item in run_plan.items}
    assert filled(kept[orphan.item_id]) - set(EXTRACTION_CELLS) == filled(rebuild) - set(
        EXTRACTION_CELLS
    ), "the fallback row says something the payloads cannot"
    assert kept[orphan.item_id].cpu_model is None
    assert all(kept[item.item_id].cpu_model is not None for item in run_plan.items[1:])
    assert kept[orphan.item_id].job is ServerJob.WORK, (
        "the stage that rebuilt the row knows which job it is, even where the shard sealed nothing"
    )
