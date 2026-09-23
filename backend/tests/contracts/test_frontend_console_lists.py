"""Does every hand-written list in the console still name what its contract declares?

Six console modules carry a value that has to match what a Pydantic contract
declares - the eval panel's column map, the settings vocabulary, the doubt
reasons, the bandwidth margin, the prompt-reuse column grammar, and the date the
busy share stopped holding the stolen half. A copy that has fallen behind its
contract draws a panel with a column missing from it, names a column no run
writes, or prints a correction for the wrong day, and none of those shows up as
an error anywhere.

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
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.eval_row import BandReason, EvalRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.observability import ObservabilityConfig

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
