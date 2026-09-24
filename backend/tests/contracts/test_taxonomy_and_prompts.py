"""Is a definition config, and does editing one move the prompt and nothing else?"""

from __future__ import annotations

import json
import re

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.item_health import (
    FAILURE_CODE_STAGES,
    SOURCE_NEUTRAL_FAILURE_CODES,
    TERMINAL_STAGES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.telemetry.publish.public_telemetry import PUBLIC_COLUMNS

from ._fixtures import (
    DOC_ITEM_HEALTH,
    DOC_ONE_URL,
    backticked,
    paragraph_after,
    taxonomy_fixture,
)

pytestmark = pytest.mark.contract


def json_leaves(payload: object, path: str = "") -> dict[str, object]:
    """Every scalar in a payload, addressed, so two payloads can be diffed leaf by leaf."""
    if isinstance(payload, dict):
        return {
            address: leaf
            for key, value in payload.items()
            for address, leaf in json_leaves(value, f"{path}/{key}").items()
        }
    if isinstance(payload, list):
        return {
            address: leaf
            for index, value in enumerate(payload)
            for address, leaf in json_leaves(value, f"{path}[{index}]").items()
        }
    return {path: payload}


def test_editing_one_definition_moves_the_prompt_and_nothing_else() -> None:
    """Change a sentence in the vocabulary file and the model is asked a different question.

    `definitions-a.json` and `definitions-b.json` are the same vocabulary with
    one lens's definition rewritten - proved here rather than promised, by
    walking both payloads and requiring exactly one leaf to differ. Both are
    written through the contract the committed schema is generated from, so
    parsing them is validating against it.

    A vocabulary that needs a code change to move its own definition is not
    config, whatever file it lives in. This test is what says so out loud: no
    Python is edited between the two cases and no schema is regenerated, and the
    block the labelling prompt is built from still moves.
    """
    a = taxonomy_fixture("definitions-a")
    b = taxonomy_fixture("definitions-b")

    left = json_leaves(json.loads(a.to_json()))
    right = json_leaves(json.loads(b.to_json()))
    assert set(left) == set(right), "the two fixtures are not the same vocabulary"
    differing = sorted(address for address in left if left[address] != right[address])
    assert differing == ["/lenses[0]/definition"], "the two fixtures differ somewhere else too"

    assert a.definition_block() != b.definition_block()
    assert a.definition_block().count("\n") == b.definition_block().count("\n")


def test_a_draft_or_retired_entry_reaches_no_prompt() -> None:
    """`status` is a control, not a convention, and the block's bytes are the proof.

    `definitions-a.json` carries a draft vertical a model proposed and a retired
    lens kept as a tombstone. Neither may contribute a byte: a draft is a word
    nobody has approved, and a tombstone is there so a day already carrying it
    still renders. So writing a sentence onto both and re-reading the block has
    to produce the same string, which is the assertion a filter that forgets one
    call site fails and prose cannot catch.
    """
    offered = taxonomy_fixture("definitions-a")
    payload = json.loads(offered.to_json())
    for entry in [*payload["verticals"], *payload["lenses"]]:
        if entry["status"] != LifecycleStatus.ACTIVE.value:
            entry["definition"] = "a sentence no prompt may carry"

    assert Taxonomy.model_validate(payload).definition_block() == offered.definition_block()
    assert "proposed-desk" not in offered.definition_block()
    assert "ai-roi" not in offered.definition_block()


def test_every_offered_entry_of_the_committed_vocabulary_carries_its_sentence() -> None:
    """The rule the contract enforces, held against the file a run really reads.

    An id and a display name tell a model nothing, so a word offered with no
    sentence beside it is a word it cannot read. The committed config is the one
    that decides a run, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    block = taxonomy.definition_block()
    offered = [
        *(
            (item.id, item.definition)
            for item in taxonomy.verticals
            if item.status is LifecycleStatus.ACTIVE
        ),
        *(
            (item.id, item.definition)
            for item in taxonomy.lenses
            if item.status is LifecycleStatus.ACTIVE
        ),
        *(
            (item.id, item.definition)
            for item in taxonomy.events
            if item.status is LifecycleStatus.ACTIVE
        ),
    ]
    for entry_id, definition in offered:
        assert definition, f"{entry_id} is offered to the model with no definition"
        assert definition in block


def test_the_frontend_names_every_committed_lens_including_a_tombstone() -> None:
    """The page's own copy of the lens display names, held against the config.

    `frontend/src/lib/payload/lenses.ts` restates them because it is TypeScript
    and the vocabulary is JSON, and it holds them rather than taking them
    through `data` so the names are not repeated inside every prerendered day
    page. Drift either way is a defect a build never catches.

    **Every** committed lens, retired ones included, and that is the half that
    changed on 2026-09-12. Omitting a tombstone did not keep it off the page so
    much as make the page stop saying what a frozen day said: `ai-roi` was
    retired on 2026-08-30 and is carried by 18 committed items, and all 18
    rendered one chip fewer than their payload held. A retired lens keeps its
    name here; deleting the entry from config is what takes the name away, and
    the page then falls back to the raw id rather than to silence.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "lenses.ts")
    declared = re.search(r"LENS_NAMES: Readonly<Record<string, string>> = \{(.*?)\};", source, re.DOTALL)
    assert declared is not None, "lenses.ts no longer declares LENS_NAMES"
    named = dict(re.findall(r"'?([a-z0-9-]+)'?: '([^']+)'", declared.group(1)))
    committed = {lens.id: lens.display_name for lens in taxonomy.lenses}
    assert named == committed, "the page and config/taxonomy.json disagree about the lens names"


def test_the_console_reads_only_telemetry_columns_the_writer_writes() -> None:
    """The browser's copy of the projection header, held against the writer.

    `frontend/src/lib/charts/series.ts` restates `PUBLIC_COLUMNS` because it is
    TypeScript and the writer is Python. It resolves every cell by name against
    the header of the file it read, so an insert, a reorder and an append all
    move nothing it draws, and none of the three is this test's business.

    What is this test's business is a name the writer never writes. The reader
    degrades such a cell to absent rather than refusing the file, which is right
    for a stale shard and useless as a guard against a typo or a rename - both
    would draw a blank column on a page that has no way to know. So the rule is
    containment: every name the console reads is a name the writer writes.
    Nothing else ties the two lists together.
    """
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "charts" / "series.ts")
    declared = re.search(
        r"export const TELEMETRY_COLUMNS = \[(.*?)\] as const;", source, re.DOTALL
    )
    assert declared is not None, "series.ts no longer declares a TELEMETRY_COLUMNS array"
    names = tuple(re.findall(r"'([^']+)'", declared.group(1)))
    assert names, "TELEMETRY_COLUMNS matched but held no column names"
    unwritten = [name for name in names if name not in PUBLIC_COLUMNS]
    assert not unwritten, (
        "series.ts reads telemetry columns public_telemetry.py never writes: "
        f"{unwritten}"
    )


def test_the_console_fallback_bands_match_the_committed_ladder() -> None:
    """The console's fallback length ladder, held against the file it stands in for.

    `summarizeConfig()` in `frontend/src/lib/server/config.ts` returns
    `SUMMARIZE_DEFAULTS` when `config/idhazh.json` cannot be read, and those
    bands draw the compression plot's target zone and set its y axis. A stale
    copy draws a wrong chart and says nothing, so the copy is pinned here.
    """
    committed: list[dict[str, int]] = json.loads(read_text(CONFIG_DIR / "idhazh.json"))[
        "summarize"
    ]["bands"]
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    declared = re.search(
        r"const SUMMARIZE_DEFAULTS: SummarizeConfig = \{\s*bands: \[(.*?)\]\s*\};",
        source,
        re.DOTALL,
    )
    assert declared is not None, "config.ts no longer declares a SUMMARIZE_DEFAULTS ladder"
    fallback = [
        {name: int(value) for name, value in re.findall(r"(\w+): (\d+)", band)}
        for band in re.findall(r"\{([^{}]*)\}", declared.group(1))
    ]
    assert fallback, "SUMMARIZE_DEFAULTS matched but held no bands"
    keys = (
        "min_source_words",
        "target_words_min",
        "target_words_max",
    )
    expected = [{key: band[key] for key in keys} for band in committed]
    assert fallback == expected, (
        "config.ts and config/idhazh.json disagree about the summary bands: "
        f"the console falls back to {fallback}, the committed ladder is {expected}"
    )


def test_recorded_item_health_codes_never_count_against_a_source() -> None:
    assert len(SOURCE_NEUTRAL_FAILURE_CODES) == 20
    assert FailureCode.NOT_ATTEMPTED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_UNREACHABLE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_REFUSED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.NOT_PROSE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.HTTP_CLIENT_ERROR not in SOURCE_NEUTRAL_FAILURE_CODES


def test_a_signal_that_publishes_is_never_charged_to_a_source() -> None:
    """`counts_against_source` reads the code and not the outcome.

    So a signal that records and still publishes would charge its feed for every
    story the feed published. All four shape signals ride on an `ok` row -
    `reject_*` is false for each of them - and all four are therefore neutral.
    Flip one of those switches and this test is the reason to think again.
    """
    for code in (
        FailureCode.TOO_SHORT,
        FailureCode.NOT_PROSE,
        FailureCode.BOILERPLATE,
        FailureCode.CONTAMINATED,
    ):
        assert code in SOURCE_NEUTRAL_FAILURE_CODES, f"{code.value} rides on an ok row"


def test_a_signal_that_cannot_fire_is_never_charged_to_a_source() -> None:
    """`boilerplate` left the neutral set on 2026-09-17 and came back the same day.

    It moved out when a store started feeding the comparison it rests on. Over one
    full run that store changed the signal exactly zero times - 12,917 committed
    item-health rows, no `boilerplate` cell among them - so the store was reverted
    and the code is back to dividing by an empty set. A signal that cannot fire
    must not count against a publisher, because the only thing it could ever do
    then is be wrong.
    """
    assert FailureCode.BOILERPLATE in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_is_the_models_fault_and_never_the_feeds(code: FailureCode) -> None:
    """A wire service publishing short briefs must not be quarantined for our model.

    `collect.availability_strikes_before_rest` is 5, so leaving either code out
    of the source-neutral set would take a working feed off the list on the fifth
    copy.
    """
    assert FAILURE_CODE_STAGES[code] == frozenset({ItemStage.SUMMARIZE})
    assert code in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_survives_the_ledger_round_trip(code: FailureCode) -> None:
    """The census row is the only durable record of a dropped item, so it must read back."""
    published = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    row = published.model_copy(
        update={
            "stage": ItemStage.SUMMARIZE,
            "outcome": ItemOutcome.FAILED,
            "code": code,
            "summary_words": 44,
        }
    )

    restored = ItemHealthRow.from_csv_row(row.csv_row())
    assert restored.code is code
    assert restored.summary_words == 44
    assert restored.counts_against_source is False
    assert restored == row


def test_a_prompt_that_did_not_fit_is_our_budget_and_not_the_sources_fault() -> None:
    """The article was long. The context window and the truncation cap are ours."""
    assert FailureCode.CONTEXT_EXCEEDED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FAILURE_CODE_STAGES[FailureCode.CONTEXT_EXCEEDED] == frozenset({ItemStage.SUMMARIZE})


def test_an_item_health_row_written_before_the_context_code_still_reads() -> None:
    """Section 11's release blocker for an additive enum member.

    A row this month's ledger already holds carries the previous schema stamp
    and a code minted before today. It must still load, and it must still read
    as source-neutral, or a committed ledger stops parsing on the day the
    vocabulary grows.
    """
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "summarize-model-unreachable.json")
    )

    assert row.version == "2026-08-24T18:30"
    assert row.version != ItemHealthRow.schema_version()
    assert row.code is FailureCode.MODEL_UNREACHABLE
    assert row.counts_against_source is False
    assert ItemHealthRow.from_csv_row(row.csv_row()) == row


def test_item_health_csv_round_trip_uses_empty_cells_for_absent_values() -> None:
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    cells = row.csv_row()
    assert cells["code"] == ""
    assert cells["http_status"] == ""
    assert ItemHealthRow.from_csv_row(cells) == row


def test_no_failure_code_admits_a_stage_an_item_cannot_stop_at() -> None:
    """A code's stage set is the gate a new stage name has to get past.

    `unknown` mapped to `frozenset(ItemStage)`, so any name added to the enum for
    any reason became a legal census row the day it was declared - one line, and
    the only one, between a stage vocabulary and a ledger that accepts it.
    `ItemStage` is also the type of `telemetry.event(src=...)` and of
    `DayStageTiming.stage`, and neither of those means an ending, so names that
    no row may carry now exist and this is what keeps them out.
    """
    for code, stages in FAILURE_CODE_STAGES.items():
        assert stages <= TERMINAL_STAGES, f"{code.value} admits a stage no item stops at"


@pytest.mark.parametrize("stage", sorted(set(ItemStage) - TERMINAL_STAGES))
def test_the_census_refuses_a_stage_an_item_cannot_stop_at(stage: ItemStage) -> None:
    """`stage` answers where the item STOPPED, so a step it passed through is a lie.

    An item whose picture failed still reaches the digest. A `visual` row here
    would say it did not, and would take one off the `publish` count that
    `day_metrics` and the console read off this same file.

    Parametrized over whatever is not terminal rather than over `visual`, so the
    next stage name added for a log line or a clock arrives here already asked
    the question instead of arriving unnoticed.
    """
    payload = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    ).model_dump(mode="json")
    payload["stage"] = stage.value

    with pytest.raises(ValidationError, match="where an item stopped"):
        ItemHealthRow.model_validate(payload)


def test_the_pages_that_name_the_summarize_codes_still_agree_with_the_enum() -> None:
    """Two pages enumerate the summarize codes by hand, and neither is generated.

    `copied_source` and `leaked_address` were minted on 2026-08-27 and both pages
    kept the old list for a day, so each one asserted a vocabulary the code had
    already outgrown. `unknown` is excluded because it belongs to every stage and
    `to_summary` never returns it.
    """
    summarize_only = {
        code.value
        for code, stages in FAILURE_CODE_STAGES.items()
        if stages == frozenset({ItemStage.SUMMARIZE})
    }

    tabled = re.findall(r"^\| `summarize` \|(.+)\|$", read_text(DOC_ITEM_HEALTH), re.MULTILINE)
    assert len(tabled) == 1, "the item-health stage table no longer has one summarize row"
    assert backticked(tabled[0]) == summarize_only

    listed = re.findall(r"^\| Summary `([a-z_]+)`", read_text(DOC_ONE_URL), re.MULTILINE)
    assert set(listed) == summarize_only
    assert len(listed) == len(summarize_only), "the one-URL page lists a code twice"


def test_the_item_health_page_splits_the_codes_the_way_the_contract_does() -> None:
    """The source-neutral split is a promise about which feed gets quarantined."""
    text = read_text(DOC_ITEM_HEALTH)
    neutral = {code.value for code in SOURCE_NEUTRAL_FAILURE_CODES}

    assert backticked(paragraph_after(text, "never count against a source:")) == neutral
    assert backticked(paragraph_after(text, "can count against the source:")) == {
        code.value for code in FailureCode
    } - neutral
