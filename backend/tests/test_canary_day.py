"""The canary day's score ledger - the fixture the console's pages read.

The browser suite runs against this day, so a state the fixture does not carry
is a state that suite cannot test: a row for every confidence band, a cut
article beside an uncut one, an item that is both an abstract and cut, and a
chart the compiler really drew.

These assertions are about the fixture's shape rather than its numbers. A value
in `SCORED` is a fixture and may be edited; a fixture that stopped exercising a
state a page can show is the defect this file guards against.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from support.paths import FIXTURES_DIR, REPO_ROOT

from idhazh import config, ledger
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.visual import VisualType
from idhazh.contracts.visual_data import RENDERER_VERSION, VisualData
from utilities import build_canary_day


def evaluation() -> EvaluationConfig:
    """The committed evaluation settings the day is scored under."""
    return config.load().app.evaluation


def published() -> list[DigestItem]:
    """The day's published items, read off the canary fixtures by the test that asks."""
    return build_canary_day.published_items(evaluation(), FIXTURES_DIR / "canaries")


def scored() -> list[EvalRow]:
    """The day's score rows, one per published item."""
    return build_canary_day.score_rows(published(), evaluation())


def rows_with_a_recorded_length() -> list[EvalRow]:
    """The rows that recorded the article's length before the cut.

    A row without it has no cut to compare, so the cut rule says nothing about it.
    """
    return [row for row in scored() if row.source_words_before_cap is not None]


def source_words(row: EvalRow) -> int:
    """The article's length before the cut, where the fixture recorded one.

    `EvalRow.source_words_before_cap` is nullable because a row written before
    2026-08-27 whose article was truncated has no full length anywhere. Some
    fixture rows are in that state on purpose, so every caller here reads
    `rows_with_a_recorded_length()` and a None reaching this function is a broken
    fixture.
    """
    assert row.source_words_before_cap is not None, f"{row.item_id} records no article length"
    return row.source_words_before_cap


def test_each_published_item_and_its_filed_row_agree_on_id_band_and_cut(tmp_path: Path) -> None:
    """Two files, one judgement, read back the way the console reads them.

    The digest page and the console read different files, so each filed row is
    read back through the ledger door and held to the item it was scored from. A
    builder that scores the wrong band or cut, or a writer that drops or rewrites
    a row, fails here. The cut is the rule the console counts.
    """
    items = published()
    assert build_canary_day.file_scores(tmp_path, items, evaluation()) == len(items)
    rows = {row.item_id: row for row in filed_rows(tmp_path)}

    assert set(rows) == {item.item_id for item in items}
    for item in items:
        assert rows[item.item_id].date == build_canary_day.DATE
        assert rows[item.item_id].band == item.band
        assert rows[item.item_id].truncation_flagged == item.truncated


def test_the_eight_item_day_has_a_rendered_chart_after_the_canary_seed(tmp_path: Path) -> None:
    settings = config.load()
    day = build_canary_day.build(tmp_path / "digest", settings.app.evaluation, settings.app.visuals)
    assert len(day.items) == 8
    item = next(item for item in day.items if item.item_id == "ai-04")
    assert item.visual is not None
    assert item.visual.kind == "chart"
    assert item.visual.state == "rendered"
    assert item.visual.data_path == "digest/2026/08/20/ai-04.json"
    assert (tmp_path / item.visual.data_path).is_file()


def test_the_canary_line_is_compiled_from_the_named_source_fixture(tmp_path: Path) -> None:
    settings = config.load()
    day = build_canary_day.build(tmp_path / "digest", settings.app.evaluation, settings.app.visuals)
    item = day.items[6]
    assert item.visual is not None
    assert item.visual.state == "rendered"
    assert item.visual.data_path is not None

    data = VisualData.read(tmp_path / item.visual.data_path)
    assert data.item_id == item.item_id
    assert data.renderer_version == RENDERER_VERSION
    assert data.type is VisualType.LINE
    marks = {mark.mark_id: mark for mark in data.marks}
    assert [
        (
            marks[time_id].time,
            marks[quantity_id].element_id,
            str(marks[quantity_id].value),
        )
        for time_id, quantity_id in zip(data.encoding.time, data.encoding.quantity, strict=True)
    ] == [
        ("2025", "quantity-88-95", "2400"),
        ("2024", "quantity-60-67", "1800"),
        ("2023", "quantity-32-39", "1200"),
    ]


def test_the_canary_stack_is_compiled_from_its_separately_declared_whole(
    tmp_path: Path,
) -> None:
    settings = config.load()
    day = build_canary_day.build(tmp_path / "digest", settings.app.evaluation, settings.app.visuals)
    item = day.items[4]
    assert item.item_id == "ai-05"
    assert item.visual is not None
    assert item.visual.state == "rendered"
    assert item.visual.data_path == "digest/2026/08/20/ai-05.json"

    data = VisualData.read(tmp_path / item.visual.data_path)
    assert data.item_id == item.item_id
    assert data.type is VisualType.STACKED_BAR
    marks = {mark.mark_id: mark for mark in data.marks}
    assert [marks[mark_id].element_id for mark_id in data.encoding.category] == [
        "quantity-22-29"
    ]
    assert [
        (
            marks[series_id].text,
            str(marks[quantity_id].value),
            marks[quantity_id].unit,
        )
        for series_id, quantity_id in zip(data.encoding.series, data.encoding.quantity, strict=True)
    ] == [
        ("Wind", "10", "mw"),
        ("solar", "10", "mw"),
        ("hydro", "10", "mw"),
    ]


def test_the_fixture_covers_every_confidence_band() -> None:
    assert {row.band for row in scored()} == set(ConfidenceBand)


def test_the_fixture_holds_a_cut_row_and_an_uncut_one() -> None:
    """The cut rule below passes on rows that never exercise one side of it.

    Counted over the rows that recorded a length: a cut row with no length before
    the cut cannot be compared against anything, so over every scored row this
    would pass on a fixture whose every cut row is unrecorded.
    """
    placed = rows_with_a_recorded_length()
    flagged = [row for row in placed if row.truncation_flagged]
    assert flagged, "no row that recorded a length is cut"
    assert len(flagged) < len(placed), "every row that recorded a length is cut"


def test_the_truncation_flag_follows_the_configured_rule() -> None:
    """The flag says extract cut the body, so the two length columns must agree.

    This is the whole rule now. It used to be checked against a faithfulness gap
    as well, and that second check was the defect: the gap is a score difference
    and this column names a cut, so a row could satisfy one and contradict the
    other. Over the committed ledger it did - the flag was true on exactly one
    row, and that row read 748 words of a 748-word article.
    """
    for row in rows_with_a_recorded_length():
        # A cut page is a page the model saw less of. The two columns are the
        # only record of how much less, and a row missing one of them says
        # nothing about the cut either way.
        assert (row.source_words < source_words(row)) == row.truncation_flagged


def test_one_published_item_is_both_an_abstract_and_cut() -> None:
    """The note joins a sentence per limit, and nothing rendered the pair.

    Nothing in extract exempts an abstract from the cap, so the two facts can
    land on one real item. They never have: measured 2026-08-29 over every
    committed `frontend/public/digest/**/digest.json`, no published item carries
    an abstract note at all. Without this row the joined sentence has a unit test
    and no page, so no browser can read back what a reader would meet.

    Exactly one, because the browser suite addresses it and two would make the
    assertion there depend on which one Playwright found first.
    """
    both = [
        item for item in published() if item.source_form is SourceForm.ABSTRACT and item.truncated
    ]

    assert len(both) == 1, "no published item is both an abstract and cut"
    # Composed by `assemble.reader_note`, whose wording its own test pins.
    assert both[0].reader_note


def filed_rows(state: Path) -> list[EvalRow]:
    """The day's score rows as the ledger door reads them back."""
    return ledger.load_days(
        state, LedgerName.SUMMARY_QUALITY_EVALS, [build_canary_day.DATE], model=EvalRow
    )


def test_the_scores_are_filed_by_the_pipelines_writer(tmp_path: Path) -> None:
    """Filed by the writer the pipeline files with, so no shape can be invented here.

    The rows read back through the ledger door are the rows the builder scored,
    field for field.
    """
    rows = scored()
    assert build_canary_day.file_scores(tmp_path, published(), evaluation()) == len(rows)

    assert filed_rows(tmp_path) == rows


def test_scored_keys_command_exits_with_the_filed_rows(tmp_path: Path) -> None:
    items, settings = published(), evaluation()
    assert build_canary_day.file_scores(tmp_path, items, settings) == len(items)

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "backend" / "utilities" / "build_canary_day.py"),
            "--scored-keys",
            "--state",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {row.item_id: row.url_key for row in scored()}


def test_a_fresh_run_writes_the_same_ledger_every_time(tmp_path: Path) -> None:
    """The rows are a function of the fixture, never of how often it was built.

    Compared as the rows the door reads back rather than as bytes, because each
    raw file names the instant it was written.
    """
    items, settings = published(), evaluation()
    written = []
    for index in range(3):
        state = tmp_path / f"run-{index}"
        assert build_canary_day.file_scores(state, items, settings) == len(items)
        written.append(filed_rows(state))

    assert written[0] == written[1] == written[2]


def test_filing_the_same_day_twice_reads_back_the_same_rows(tmp_path: Path) -> None:
    """The second write is the same work unit, so a read takes it in place of the first.

    The builder clears its state directory before writing, so this is the belt
    behind that brace: a ledger that survived the clear still cannot double.
    """
    items, settings = published(), evaluation()
    assert build_canary_day.file_scores(tmp_path, items, settings) == len(items)
    once = filed_rows(tmp_path)

    assert build_canary_day.file_scores(tmp_path, items, settings) == len(items)
    assert filed_rows(tmp_path) == once


def test_a_build_leaves_no_file_an_earlier_build_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build over the tree of a build under another `DATE` holds only its own files.

    The earlier build's newest day stayed in the digest tree, and the site build
    dated its fixture rows from that day. So each folder the builder writes holds
    one file the earlier build left, and the build must remove each of them. The
    builder never writes `publication.json`, so it must leave that file alone.
    """
    root = tmp_path / "canary"
    left = [
        "digest/2026/10/01/digest.json",
        "assist/index/2026-10.json",
        "console/band.json",
        "telemetry/2026-10.csv",
        "run-timeline/2026-10.csv",
        "state/day-metrics/2026/10/01.json",
    ]
    for name in [*left, "publication.json"]:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("written before this build\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["build_canary_day.py", "--out", str(root / "digest"), "--state", str(root / "state")],
    )

    assert build_canary_day.main() == 0

    assert [name for name in left if (root / name).exists()] == []
    assert (root / "digest/2026/08/20/digest.json").is_file()
    assert (root / "assist/index/2026-08.json").is_file()
    assert not any(
        (root / name).exists()
        for name in ("machine", "run-days", "day-metrics", "telemetry", "run-timeline")
    )
    assert (root / "publication.json").read_text(encoding="utf-8") == "written before this build\n"
