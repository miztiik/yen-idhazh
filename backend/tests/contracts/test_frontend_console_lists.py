"""Does every hand-written list in the console still name what its contract declares?

Eleven console modules carry a value that has to match what a Pydantic contract
declares - the eval panel's column map, the settings vocabulary, the doubt
reasons, the bandwidth margin, the prompt-reuse column grammar, the date the
busy share stopped holding the stolen half, the article, feed, holdout score,
holdout mark and fitted line records' column lists, the columns the run
timeline reads off every row, and the routes the strip draws. A copy that has
fallen behind its contract draws a panel with a column missing from it, names a
column no run writes, or prints a correction for the wrong day, and none of
those shows up as an error anywhere.

**These six moved here from the browser suite on 2026-09-23**, where each read
the generated `schemas/<stem>.schema.json`, or the TypeScript generated beside
it, off disk. That tree is gone, and the contract that generated it is where the
question was always answerable: a set comparison needs no browser, no site build
and no canary day, so it now fails in the backend suite instead of after a
fourteen-minute browser run. The specs kept everything they alone can say - that
the panel draws the list, and what the words read like.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, get_args

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.console_band import RouteId
from idhazh.contracts.eval_row import BandReason, EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.console import ConsoleChrome
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.run_timeline import RunTimelineRow
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from idhazh.telemetry.publish.console_band import ROUTES

pytestmark = pytest.mark.contract

CONSOLE: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "console"
SERVER: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "server"


def object_keys(text: str, name: str) -> list[str]:
    """The keys of `export const <name>: ... = { ... };`, in the order they are written."""
    found = re.search(rf"export const {name}\b[^=]*= \{{(.*?)\n\}};", text, re.DOTALL)
    assert found, f"no exported object named {name}"
    return re.findall(r"^\t([A-Za-z_][A-Za-z0-9_]*):", found[1], re.MULTILINE)


def quoted_ids(text: str, name: str) -> list[str]:
    """Every `id: '<value>'` inside `export const <name> = [ ... ];`."""
    found = re.search(rf"export const {name}\b[^=]*= \[(.*?)\n\];", text, re.DOTALL)
    assert found, f"no exported array named {name}"
    return re.findall(r"\bid: '([^']*)'", found[1])


def quoted_strings(text: str, name: str) -> list[str]:
    """Every quoted string inside `export const <name> = [ ... ] as const;`, in order."""
    found = re.search(rf"export const {name}\b[^=]*= \[(.*?)\n\] as const;", text, re.DOTALL)
    assert found, f"no exported constant array named {name}"
    return re.findall(r"'([^']*)'", found[1])


def const_strings(text: str, name: str) -> list[str]:
    """Every quoted string inside `export const <name> = [ ... ] as const;`."""
    found = re.search(rf"export const {name}\b[^=]*= \[(.*?)\] as const;", text, re.DOTALL)
    assert found, f"no exported constant array named {name}"
    return re.findall(r"'([^']*)'", found[1])


def test_the_strip_names_every_route_the_band_declares_in_the_order_it_writes_them() -> None:
    """The fallback strip and the published one must name one set of routes, in one order.

    `band.ts` types `RouteId` and `ROUTE_IDS` by hand, and `readBand()` draws one
    tab per entry of `ROUTE_IDS` in that order whatever the payload holds. A route
    the contract gains and the list lacks would never reach the strip; a route
    the list names and the contract lacks would draw a tab no band can fill.
    """
    text = read_text(CONSOLE / "band.ts")
    typed = re.search(r"^export type RouteId = ([^;]*);$", text, re.MULTILINE)
    assert typed, "band.ts no longer declares the RouteId union on one line"
    listed = re.search(r"^const ROUTE_IDS: RouteId\[\] = \[([^\]]*)\];$", text, re.MULTILINE)
    assert listed, "band.ts no longer declares ROUTE_IDS on one line"

    written = [route_id.value for route_id, *_ in ROUTES]
    assert sorted(written) == sorted(member.value for member in RouteId), (
        "ROUTES in the band producer does not write every RouteId exactly once"
    )
    assert re.findall(r"'([^']*)'", typed[1]) == written, (
        "the RouteId union in band.ts is not RouteId's members in the order ROUTES writes them"
    )
    assert re.findall(r"'([^']*)'", listed[1]) == written, (
        "ROUTE_IDS in band.ts is not RouteId's members in the order ROUTES writes them"
    )


def test_the_frontend_console_chrome_vocabulary_matches_the_contract() -> None:
    """The route chrome knob crosses from Python config to the Svelte layout."""
    text = read_text(CONSOLE / "chrome.ts")
    assert const_strings(text, "CONSOLE_CHROMES") == list(get_args(ConsoleChrome))


def test_the_article_record_asks_for_every_column_the_contract_declares_in_its_order() -> None:
    """The door answers only the columns it is asked for, so the list is the whole row.

    `ledger-rows.ts` spells `ItemHealthRow`'s columns once, because the door
    never offers every column. A column the contract gains and the list lacks
    would reach a panel as an empty reading rather than as an error. The order
    is held too: the door sorts the rows it returns by the columns in the order
    they were asked for.
    """
    asked = quoted_strings(read_text(SERVER / "ledger-rows.ts"), "ITEM_HEALTH_COLUMNS")
    declared = list(ItemHealthRow.csv_columns())

    assert asked == declared, (
        "ITEM_HEALTH_COLUMNS in ledger-rows.ts is not ItemHealthRow's columns in order. "
        f"Missing: {[name for name in declared if name not in asked]}. "
        f"Not declared: {[name for name in asked if name not in declared]}. "
        "If both are empty, only the order differs: write them in the contract's order."
    )


def test_the_feed_record_asks_only_for_columns_the_contract_declares_in_its_order() -> None:
    """The Voices page reads part of the feed record, so its list is a part, in order.

    `ledger-rows.ts` spells the `FeedHealthRow` columns the page reads, because
    the door never offers every column. A column the contract renames or drops
    would reach the page as an empty reading rather than as an error.
    """
    asked = quoted_strings(read_text(SERVER / "ledger-rows.ts"), "FEED_HEALTH_COLUMNS")
    declared = list(FeedHealthRow.csv_columns())

    assert asked, "FEED_HEALTH_COLUMNS in ledger-rows.ts names no column"
    assert [name for name in declared if name in asked] == asked, (
        "FEED_HEALTH_COLUMNS in ledger-rows.ts is not part of FeedHealthRow's columns in "
        f"order. Not declared: {[name for name in asked if name not in declared]}. "
        "If that is empty, only the order differs: write them in the contract's order."
    )


def test_the_holdout_score_asks_only_for_columns_the_contract_declares_in_its_order() -> None:
    """The Judgement page reads part of the holdout score, so its list is a part, in order.

    `content-similarity-holdout.ts` spells the `MergeLineHoldoutScore` columns the panel
    reads, because the door never offers every column. A column the contract
    renames or drops would reach the panel as an empty reading rather than as an
    error.
    """
    asked = quoted_strings(read_text(SERVER / "content-similarity-holdout.ts"), "HOLDOUT_SCORE_COLUMNS")
    declared = list(MergeLineHoldoutScore.csv_columns())

    assert asked, "HOLDOUT_SCORE_COLUMNS in content-similarity-holdout.ts names no column"
    assert [name for name in declared if name in asked] == asked, (
        "HOLDOUT_SCORE_COLUMNS in content-similarity-holdout.ts is not part of "
        "MergeLineHoldoutScore's columns in order. Not declared: "
        f"{[name for name in asked if name not in declared]}. "
        "If that is empty, only the order differs: write them in the contract's order."
    )


def test_the_fitted_line_asks_only_for_columns_the_contract_declares_in_its_order() -> None:
    """The Judgement page reads part of the fitted line, so its list is a part, in order.

    `content-similarity-judge.ts` spells the `FittedSimilarityThreshold` columns the
    merge line, the agreement strip and the record read, because the door never
    offers every column. A column the contract renames or drops would reach a
    panel as an empty reading rather than as an error.
    """
    asked = quoted_strings(read_text(SERVER / "content-similarity-judge.ts"), "FITTED_LINE_COLUMNS")
    declared = list(FittedSimilarityThreshold.csv_columns())

    assert asked, "FITTED_LINE_COLUMNS in content-similarity-judge.ts names no column"
    assert [name for name in declared if name in asked] == asked, (
        "FITTED_LINE_COLUMNS in content-similarity-judge.ts is not part of "
        "FittedSimilarityThreshold's columns in order. Not declared: "
        f"{[name for name in asked if name not in declared]}. "
        "If that is empty, only the order differs: write them in the contract's order."
    )


def test_the_holdout_marks_ask_for_every_column_but_the_stamp_in_the_contract_order() -> None:
    """The Judgement page reads each hand mark whole but for `version`, in the contract's order.

    `content-similarity-holdout.ts` spells the `SimilarityHoldoutPair` columns it asks
    the door for, because the door never offers every column. A column the
    contract renames, adds or drops would reach the panel as an empty reading
    rather than as an error.
    """
    asked = quoted_strings(read_text(SERVER / "content-similarity-holdout.ts"), "HOLDOUT_PAIR_COLUMNS")
    declared = [name for name in SimilarityHoldoutPair.csv_columns() if name != "version"]

    assert asked == declared, (
        "HOLDOUT_PAIR_COLUMNS in content-similarity-holdout.ts is not every SimilarityHoldoutPair "
        f"column but version, in order. Not declared: {[n for n in asked if n not in declared]}; "
        f"not asked: {[n for n in declared if n not in asked]}."
    )


def test_the_run_timeline_reads_only_columns_every_row_carries() -> None:
    """A column the timeline reads off every row has to be one no row leaves empty.

    `run-timeline.ts` spells the columns the Pipelines run timeline reads off every
    row, and draws an item's bar from them. Each has to be a `RunTimelineRow` field
    that is required and does not allow null, so every published row carries it.
    A column that may be absent, such as a step nothing timed, belongs with the
    steps the panel names as not recorded, never in this list, where it would
    draw an empty slice.
    """
    asked = quoted_strings(read_text(SERVER / "run-timeline.ts"), "TIMELINE_COLUMNS")
    schema = RunTimelineRow.model_json_schema()
    required = set(schema.get("required", []))

    def nullable(name: str) -> bool:
        field = schema["properties"][name]
        return field.get("type") == "null" or any(
            option.get("type") == "null" for option in field.get("anyOf", [])
        )

    always = [
        name for name in RunTimelineRow.model_fields if name in required and not nullable(name)
    ]
    assert asked, "TIMELINE_COLUMNS in run-timeline.ts names no column"
    assert [name for name in asked if name not in always] == [], (
        "TIMELINE_COLUMNS in run-timeline.ts names a column a RunTimelineRow may leave "
        f"empty or does not declare. Every row carries only: {always}"
    )


def test_every_eval_column_is_drawn_on_a_panel_or_declared_not_a_measurement() -> None:
    """A column the checker writes that reaches no panel is a column nobody reads."""
    text = read_text(CONSOLE / "eval-instruments.ts")
    drawn = object_keys(text, "DRAWN_BY")
    excluded = object_keys(text, "NOT_A_MEASUREMENT")
    declared = set(EvalRow.model_fields)

    assert not set(drawn) & set(excluded), "a column is both drawn and declared not a measurement"
    assert not declared - set(drawn) - set(excluded), (
        "a column the checker writes reaches no console panel and is not declared as "
        "identity. Give it a panel in DRAWN_BY, or a one-line reason in NOT_A_MEASUREMENT: "
        f"{sorted(declared - set(drawn) - set(excluded))}"
    )
    assert not (set(drawn) | set(excluded)) - declared, (
        "a map names a column EvalRow does not have: "
        f"{sorted((set(drawn) | set(excluded)) - declared)}"
    )


def test_every_recorded_input_has_words_and_every_word_has_a_recorded_input() -> None:
    """The settings panel spells each recorded input; a new one arrives unspelled."""
    spelled = object_keys(read_text(CONSOLE / "settings-moved.ts"), "SETTING_WORDS")
    assert sorted(spelled) == sorted(PipelineInputs.model_fields), (
        "a recorded input with no words, or words with no recorded input"
    )


def test_the_panel_names_every_reason_the_contract_can_publish() -> None:
    """A sixth reason has to fail here rather than go unnoticed on the page."""
    drawn = quoted_ids(read_text(CONSOLE / "doubt-reasons.ts"), "REASONS")
    assert sorted(drawn) == sorted(member.value for member in BandReason), (
        "the panel and the contract disagree about which reasons exist"
    )


def test_the_page_grades_bandwidth_by_the_margin_the_probe_sized_its_buffer_with() -> None:
    """Two numbers in two languages would let the page refuse a row the probe wrote."""
    shipped = ObservabilityConfig.model_fields["host_fingerprint_bandwidth_cache_multiple"].default
    text = read_text(SERVER / "config.ts")
    found = re.search(r"^\thost_fingerprint_bandwidth_cache_multiple: (\d+),$", text, re.MULTILINE)
    assert found, "config.ts no longer carries a fallback for the bandwidth cache multiple"
    assert int(found[1]) == shipped


def test_every_request_the_item_ledger_names_carries_its_reading_speed_column() -> None:
    """The pairing the prompt-reuse panel draws, asserted on the contract that writes it.

    The column grammar is the frontend's `REUSE_COLUMN`, restated here because
    this is the side that owns the columns. How many requests the pipeline makes
    is a config value, so what is asserted is the property rather than a count.
    """
    columns = list(ItemHealthRow.model_fields)
    names = [found[1] for column in columns if (found := re.fullmatch(r"(.+)_cache_pct", column))]

    assert names, "ItemHealthRow names no request at all"
    for name in names:
        assert f"{name}_prefill_tokens_per_s" in columns, (
            f"{name} carries no reading-speed column to pair with"
        )


def test_the_correction_the_panel_prints_names_the_date_the_contract_records() -> None:
    """One date, written in two languages, and neither side can see the other move.

    The panel tells a reader that a row older than this date counted the host's
    stolen share as our own work. `cpu_busy_pct` records the same date, and a
    correction printed for a day the contract did not move is a claim about the
    archive that the archive does not support.
    """
    stated = ItemHealthRow.json_schema()["properties"]["cpu_busy_pct"]["description"]
    said = re.search(r"A row written before (\d{4}-\d{2}-\d{2}) counted that time as ours", stated)
    assert said, (
        "`cpu_busy_pct` no longer records the date it stopped holding the stolen share, "
        "so the correction the panel prints cannot be checked against anything"
    )

    text = read_text(CONSOLE / "machine" / "processor-lost.ts")
    drawn = re.search(r"^export const BUSY_HELD_BOTH_BEFORE = '([^']*)';$", text, re.MULTILINE)
    assert drawn, "processor-lost.ts no longer declares BUSY_HELD_BOTH_BEFORE"
    assert drawn[1] == said[1], (
        f"the panel prints a correction for {drawn[1]} and the contract records {said[1]}"
    )
