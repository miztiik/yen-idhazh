"""Where is the line between a live feed and a tombstone, and what may a drawn mark claim?"""

from __future__ import annotations

import json
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.visual_data import RENDERER_VERSION, VisualData
from idhazh.contracts.visual_decision import VisualDecision

from ._fixtures import (
    mutate,
    taxonomy_fixture,
)

pytestmark = pytest.mark.contract


def sources_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json")
    )
    return payload


def test_a_retired_feed_cannot_sit_in_the_live_list() -> None:
    """The split is only real if the shape refuses the old arrangement.

    `feeds` is the list Collect loops. A retired entry there would cost a
    request every run and reach a reader, which is the exact failure the split
    exists to end - so it is a load error, not a filter someone remembers.
    """
    payload = sources_payload()
    payload["feeds"].append(payload["retired"].pop())
    with pytest.raises(ValueError, match="belongs in `retired`"):
        Sources.model_validate(payload)


def test_a_live_feed_cannot_hide_on_the_tombstone_shelf() -> None:
    """The other direction, which is the quieter bug.

    A feed parked in `retired` with an active status is never fetched, and
    nothing says so. It just stops producing, and the config still reads as
    though it were being consulted.
    """
    payload = sources_payload()
    payload["retired"][0]["status"] = "active"
    payload["retired"][0]["retired_on"] = None
    with pytest.raises(ValueError, match="without a retired status"):
        Sources.model_validate(payload)


def test_yesterdays_sources_file_fails_loudly_and_names_the_key() -> None:
    """The migration ruling, pinned.

    `config/sources.json` is written by a person in the same commit as the
    model, so there is no read-side migration and no silent coercion at the
    boundary. What replaces it is a load error that names the key the entry has
    to move to - which is only worth relying on if it is tested.
    """
    legacy = sources_payload()
    legacy["feeds"].extend(legacy.pop("retired"))
    with pytest.raises(ValueError, match="`retired`"):
        Sources.model_validate(legacy)


def test_an_id_is_unique_across_all_three_lists() -> None:
    """A duplicate id is what makes a published `source_id` ambiguous.

    Checking `feeds` alone would have let a tombstone shadow a live feed - two
    titles and two kinds for one id, with the winner decided by list order.
    """
    payload = sources_payload()
    payload["retired"][0]["id"] = payload["feeds"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)

    payload = sources_payload()
    payload["salience"][0]["id"] = payload["retired"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)


def test_an_address_is_not_read_twice_under_two_ids() -> None:
    """Retiring a feed and re-adding it under a new id is a real editing move.

    Left unchecked it doubles every request to that host and carries the same
    story twice, which reads as corroboration.
    """
    payload = sources_payload()
    payload["retired"][0]["url"] = payload["feeds"][0]["url"]
    with pytest.raises(ValueError, match="urls must be distinct"):
        Sources.model_validate(payload)


def test_a_tombstone_still_answers_for_the_items_it_published() -> None:
    """`known_feeds` is the union both label maps read (`assemble.py`).

    An item published before a feed retired keeps its `source_id` forever. If
    the id stops resolving, the page shows the raw slug and the item is
    republished as `reporting` - relabelling an announcement as journalism.
    """
    sources = Sources.from_json(read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json"))
    known = {feed.id for feed in sources.known_feeds()}
    assert known == {feed.id for feed in sources.feeds} | {feed.id for feed in sources.retired}
    assert "example-defunct-daily" in known


def test_the_lens_vocabulary_may_lose_an_entry_but_never_hold_one_twice() -> None:
    """What survived the retype, and what deliberately did not.

    Until 2026-09-12 `Taxonomy` refused any file that did not label every
    `LensId` exactly once, so a lens could not be dropped without editing
    Python. That check is gone with the enum, and dropping the last lens is now
    a legal config edit - which is the whole point of the row and also the
    reason the reading side had to learn to render an id it cannot name. Two
    ids the same is still a defect, because then one of them decides nothing.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["lenses"].pop()
    Taxonomy.model_validate(payload)

    payload["lenses"].append(payload["lenses"][0])
    with pytest.raises(ValueError, match="lens ids must be distinct"):
        Taxonomy.model_validate(payload)


def test_every_desk_ships_with_a_floor_and_a_ceiling() -> None:
    """A fresh clone runs on these, so they are the numbers a reader gets.

    The floor is a count and the ceiling is a share, and the five ceilings sum
    to 1.6, so they are satisfiable together rather than five rules that cannot
    all hold. Ruled by Editor, 2026-09-13, against the 24 committed days:
    `india` has never passed 44.7 percent of a day and `world` 37.2, so a region
    desk sits at 0.4; `ai` reached 29.5 percent on the largest day on record, so
    it sits at 0.35 with headroom over what supply has produced; the two subject
    desks with 21 feeds sit at 0.25, above their worst full days of 19.3 and
    16.7 percent.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    bounds = {desk.id: (desk.floor, desk.ceiling) for desk in taxonomy.verticals}

    assert bounds == {
        "ai": (6, 0.35),
        "energy": (6, 0.25),
        "business-economy": (6, 0.25),
        "world": (6, 0.4),
        "india": (6, 0.4),
        "science": (6, 0.25),
        "climate": (6, 0.25),
    }
    assert sum(ceiling for _, ceiling in bounds.values()) > 1.0, (
        "five ceilings that sum below one cannot all hold on any day"
    )


def test_a_taxonomy_with_no_floor_and_no_ceiling_still_validates() -> None:
    """The schema gates shape and never contents, so neither key is required.

    Three taxonomy fixtures written by another plan carry no floor and no
    ceiling. A required key would turn this row into three failing tests in
    somebody else's, so both are optional and both default to the value that is
    no rule at all - a desk nobody configured may hold the whole day and is
    required to publish nothing.
    """
    schema = json.loads(read_text(REPO_ROOT / "schemas" / "taxonomy.schema.json"))
    required = schema["$defs"]["VerticalDef"].get("required", [])

    assert "floor" not in required
    assert "ceiling" not in required

    for stem in ("definitions-a", "definitions-b", "retired-event"):
        for desk in taxonomy_fixture(stem).verticals:
            assert (desk.floor, desk.ceiling) == (0, 1.0), (
                f"{stem}.json carries no bounds, so {desk.id} must read as having no rule"
            )


def test_a_published_item_carrying_a_retired_lens_still_reads() -> None:
    """The read-side half of the retype, on a record a run really wrote.

    `tests/fixtures/digest/retired-lens-item.json` is a verbatim copy of one of
    the 18 committed items carrying `ai-roi`, which `config/taxonomy.json`
    retired on 2026-08-30. Measured 2026-09-12 over the 22 committed days and
    8,922 items: 12 on 2026-08-27, 3 on 2026-08-28 and 3 on 2026-08-29. It is a
    fixture rather than a walk of the archive because a test may not pay for
    what the pipeline has piled up (Guardrail #12), and because the fixture outlives
    the day those three days age out of retention.

    It also carries a live lens beside the tombstone, so the case it proves is
    the mixed one: a day does not get to keep half of what it said.
    """
    item = DigestItem.model_validate_json(
        read_text(FIXTURES_DIR / "digest" / "retired-lens-item.json")
    )
    assert item.lenses == ["ai-roi", "china"]

    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    retired = {lens.id for lens in taxonomy.lenses if lens.status is LifecycleStatus.RETIRED}
    assert "ai-roi" in retired, "the fixture stopped being the case this test is about"
    assert "ai-roi" not in taxonomy.lens_terms(), "a tombstone must stop matching"


def test_an_id_the_committed_vocabulary_no_longer_names_still_reads() -> None:
    """The migration, stated as the thing it has to survive.

    A closed enum could not read a word `config/taxonomy.json` had stopped
    carrying, so the only safe way to remove a lens was never to remove one. An
    open slug reads it, which is what lets a person delete an entry without
    making every day that published it unreadable. The id is removed from the
    fixture's vocabulary rather than from the committed file, so nothing here
    depends on what config happens to hold today.
    """
    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "retired-lens-item.json"))
    payload["lenses"] = ["ai-roi", "supply-chain"]
    item = DigestItem.model_validate(payload)
    assert item.lenses == ["ai-roi", "supply-chain"]

    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    assert "supply-chain" not in {lens.id for lens in taxonomy.lenses}

    with pytest.raises(ValidationError):
        DigestItem.model_validate({**payload, "lenses": ["Supply Chain"]})


def test_a_retired_event_reaches_no_prompt_and_stops_matching() -> None:
    """`status` is a control on an event too, and the block's bytes are the proof.

    The same two assertions `test_a_draft_or_retired_entry_reaches_no_prompt`
    makes for a lens, against the vocabulary that could not make them until
    2026-09-13: `EventDef` extended plain `Model`, so a run had nothing to
    filter on and offered a word the vocabulary had stopped carrying.

    `tests/fixtures/taxonomy/retired-event.json` keeps both the tombstone's
    sentence and its keywords on purpose. A tombstone that had given them up
    would be silent whatever the code did, so the test would pass on a build
    with no filter in it - and then the filter is what nobody would notice
    losing. The live event beside it spells no `status` at all, which is the
    other half: the change is additive with defaults, so an event written
    before 2026-09-13 reads as active and nothing has to migrate.
    """
    offered = taxonomy_fixture("retired-event")
    live = next(event for event in offered.events if event.id == "funding")
    assert live.status is LifecycleStatus.ACTIVE, "an event with no status reads as active"
    assert live.retired_on is None

    payload = json.loads(offered.to_json())
    for entry in payload["events"]:
        if entry["status"] != LifecycleStatus.ACTIVE.value:
            entry["definition"] = "a sentence no prompt may carry"

    assert Taxonomy.model_validate(payload).definition_block() == offered.definition_block()
    assert "ipo" not in offered.definition_block()
    assert "Stock market listing" not in offered.definition_block()
    assert "funding" in offered.definition_block(), "the live event must still be offered"

    assert "ipo" not in offered.event_terms(), "a tombstone must stop matching"
    assert "funding" in offered.event_terms()


def test_a_published_item_carrying_a_retired_event_still_reads() -> None:
    """The read-side half, and why retiring an event may not take a day's word away.

    `tests/fixtures/digest/retired-lens-item.json` is a verbatim copy of a
    committed item, and it carries two events of its own. Putting the fixture's
    tombstone into that list is the case a retirement has to survive: the day is
    frozen and the vocabulary moved, so the id has to keep reading and the
    tombstone has to keep the words the day was published under.

    It is the same rule `test_a_published_item_carrying_a_retired_lens_still_reads`
    states for a lens. No committed event is retired today, so the tombstone
    comes from the fixture rather than from `config/taxonomy.json` - which also
    keeps the test off a file another row may edit.
    """
    taxonomy = taxonomy_fixture("retired-event")
    tombstone = next(event for event in taxonomy.events if event.status is LifecycleStatus.RETIRED)
    assert tombstone.retired_on, "a retired entry must carry the day it was retired"

    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "retired-lens-item.json"))
    payload["events"] = [tombstone.id, "deal"]
    item = DigestItem.model_validate(payload)

    assert item.events == [tombstone.id, "deal"]
    assert tombstone.display_name == "Stock market listing"


def test_a_manifest_whose_runs_skip_a_number_reads() -> None:
    """Two runs finish in parallel, so no writer can know what the next number is.

    A number a writer had to derive from what another writer had already done is
    the one rule here that needed the runs to be a sequence. The ordinal names a
    block of the day, the fold hands it out, and the gap a lost or abandoned
    block leaves is a fact rather than a defect.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "runs-with-a-gap.json"))

    manifest = RunManifest.model_validate(payload)

    assert [run.n for run in manifest.runs] == [1, 2, 4]


def test_two_runs_of_a_day_cannot_share_an_ordinal() -> None:
    """With the sequence gone, this is what stops one block being counted twice.

    Nothing else refuses it: the two records carry different ids and both are
    addressed by the date, so the day would report one block's items against
    two entries and every count over the runs would double.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][1]["n"] = payload["runs"][0]["n"]
    with pytest.raises(ValueError, match="share an ordinal"):
        RunManifest.model_validate(payload)


def test_a_day_whose_runs_skip_a_number_reads() -> None:
    """The same rule on the payload a reader's browser fetches.

    The item introduced by the skipped-to block is what makes this bite: a bound
    against the number of recorded runs passed it only while the ordinals ran
    1..N, and the check is membership of the recorded set now.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["runs"][1]["n"] = 4
    introduced = 0
    for item in payload["items"]:
        if item["introduced_by_run"] == 2:
            item["introduced_by_run"] = 4
            introduced += 1
    assert introduced, "no item was introduced by the second run, so this proves nothing"

    day = DigestDay.model_validate(payload)

    assert [run.n for run in day.runs] == [1, 4]
    assert max(item.introduced_by_run for item in day.items) == 4


def test_two_runs_of_a_published_day_cannot_share_an_ordinal() -> None:
    """`items_added` is counted per ordinal, so a repeat charges one block twice.

    Both references claim every item, which is what the double count looks like
    from inside the payload. Every other clause reads it as correct: the items
    are in order, they all name a recorded ordinal, and each reference's count
    matches what that ordinal introduced.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in payload["items"]:
        item["introduced_by_run"] = payload["runs"][0]["n"]
    for run in payload["runs"]:
        run["n"] = payload["runs"][0]["n"]
        run["items_added"] = len(payload["items"])
    with pytest.raises(ValueError, match="share an ordinal"):
        DigestDay.model_validate(payload)


def test_an_item_cannot_name_an_introducing_run_the_day_never_recorded() -> None:
    """The other half of the membership check, on the run that wrote the words."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][-1]["introduced_by_run"] = 3
    payload["runs"][-1]["items_added"] = 0
    with pytest.raises(ValueError, match="introduced by a run that is not recorded"):
        DigestDay.model_validate(payload)


def test_run_counts_reconcile() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][0]["items_failed"] = 0
    with pytest.raises(ValueError, match="must equal planned"):
        RunManifest.model_validate(payload)


def test_a_manifest_written_before_charts_were_counted_still_reads() -> None:
    """Section 11's release blocker for `charts_drafted`, tested against the key."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in payload["runs"]:
        del run["charts_drafted"]
    assert [run.charts_drafted for run in RunManifest.model_validate(payload).runs] == [0, 0]


def test_a_published_chart_written_before_the_field_reads_as_a_chart_draft() -> None:
    """A chart on the page was necessarily the chart the model asked for.

    Defaulting the missing key to false would make the manifest report fewer
    drafts than published charts, which is the one thing `charts_drafted` exists
    to measure.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    del payload["drafted_chart"]
    assert VisualDecision.model_validate(payload).drafted_chart is True

    absent = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json"))
    del absent["drafted_chart"]
    assert VisualDecision.model_validate(absent).drafted_chart is False


def test_a_visual_published_before_the_data_file_reads_as_carrying_none() -> None:
    """The read-side migration, proved by removing the key rather than by waiting.

    Every day in the archive was published before a browser drew anything, so
    every committed `visual` block lacks `data_path` entirely. Absent has to read
    as no data carried - one sentence, and it is the sentence that decides
    whether 24 days keep rendering. Asserting it against a fixture with the key
    cut out is what makes it provable today; counting how many committed days
    still lack it would be a check timed to go red on a date nobody chose
    (`CLAUDE.md` section 13).
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    carried = 0
    for item in payload["items"]:
        if item["visual"] is not None:
            item["visual"].pop("data_path", None)
            carried += 1
    assert carried, "the fixture stopped carrying a visual, so this proves nothing"

    day = DigestDay.model_validate(payload)

    assert [item.visual.data_path for item in day.items if item.visual] == [None] * carried


def test_a_rendered_decision_must_record_where_its_marks_landed() -> None:
    """The other half of the rule, one stage earlier.

    This payload is a one-day run artifact under gitignored `backend/var/`, so
    the run that writes it is the run that reads it and no older shape is ever
    opened. That is what lets the rule here be both ways round where the
    published day's can only be one.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    payload.pop("data_path", None)

    with pytest.raises(ValueError, match="where its marks landed"):
        VisualDecision.model_validate(payload)


def test_only_a_rendered_visual_carries_data() -> None:
    """A path to a file the renderer never wrote is a 404 the payload asked for."""
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json",
        data_path="digest/2026/08/22/ai-01.json",
    )
    with pytest.raises(ValueError, match="rendered visual"):
        VisualDecision.model_validate(payload)

VISUAL_DATA_FIXTURE: Final = (
    CONTRACT_FIXTURES_DIR / "visual-data" / "bars-from-the-committed-plan.json"
)

def _visual_data() -> dict[str, Any]:
    """The one fitting case, compiled from the committed plan by the real compiler."""
    payload: dict[str, Any] = json.loads(read_text(VISUAL_DATA_FIXTURE))
    return payload


def test_a_visual_data_document_states_the_renderer_it_was_compiled_for() -> None:
    """One home for the version, and this is it.

    `spec_format` carried the same idea in two places and the two disagreed on
    2026-09-05T18:00. So a mark never states a version, a decision never states
    one, and the day payload never states one - the document a browser reads
    states it, because that is the document whose shape can move.
    """
    data = VisualData.model_validate(_visual_data())

    assert data.renderer_version == RENDERER_VERSION
    assert "renderer_version" not in data.marks[0].model_dump()


def _derived(payload: dict[str, Any], value: str, unit: str | None) -> dict[str, Any]:
    """A chain of the shape `DerivedValue` declares, over elements the article has.

    A `sum` reads at least two elements and no unit table, so the inputs are the
    fixture's own quantity elements rather than invented ids - a chain naming an
    element nobody extracted would be refused for that instead, and the test
    would pass while proving something else.
    """
    reads = [mark["element_id"] for mark in payload["marks"] if mark["element_id"]]
    return {
        "version": "2026-08-21",
        "function": "sum",
        "inputs": [read for read in reads if read.startswith("quantity-")][:2],
        "value": value,
        "unit": unit,
        "source_unit": None,
        "unit_table_version": None,
        "bin_lower": None,
        "bin_upper": None,
    }


def test_a_mark_came_from_the_article_or_from_a_chain_and_never_from_neither() -> None:
    """A drawn number with no provenance is the thing this subsystem exists to refuse."""
    payload = _visual_data()
    payload["marks"][0]["element_id"] = None

    with pytest.raises(ValueError, match="never both, and never neither"):
        VisualData.model_validate(payload)


def test_a_mark_may_not_claim_two_provenances_at_once() -> None:
    payload = _visual_data()
    payload["marks"][0]["derived"] = _derived(payload, "1200", "mw")

    with pytest.raises(ValueError, match="never both, and never neither"):
        VisualData.model_validate(payload)


def test_a_mark_that_says_nothing_and_measures_nothing_is_refused() -> None:
    """It would draw a bar with no name and no length. Nothing to look at."""
    payload = _visual_data()
    payload["marks"][0]["text"] = None

    with pytest.raises(ValueError, match="names something or measures something"):
        VisualData.model_validate(payload)


def test_a_unit_with_no_figure_beside_it_is_refused() -> None:
    payload = _visual_data()
    payload["marks"][0]["unit"] = "mw"

    with pytest.raises(ValueError, match="unit"):
        VisualData.model_validate(payload)


def test_a_channel_that_names_a_mark_the_document_lacks_is_refused() -> None:
    """The browser would draw a bar short, and be right to."""
    payload = _visual_data()
    payload["encoding"]["category"].append("m99")

    with pytest.raises(ValueError, match="does not carry"):
        VisualData.model_validate(payload)


def test_a_mark_nothing_draws_is_refused_rather_than_shipped() -> None:
    """Bytes on the wire that reach no pixel. Either the plan or the channel is wrong."""
    payload = _visual_data()
    payload["encoding"]["category"] = payload["encoding"]["category"][:-1]

    with pytest.raises(ValueError, match="no channel draws"):
        VisualData.model_validate(payload)


def test_one_mark_may_not_be_drawn_in_two_channels() -> None:
    """A name that is also a length draws a bar whose label is its own size."""
    payload = _visual_data()
    payload["encoding"]["entity"] = [payload["encoding"]["category"][0]]

    with pytest.raises(ValueError, match="two channels"):
        VisualData.model_validate(payload)


def test_two_marks_may_not_share_an_id() -> None:
    """The channels address marks by id, so a repeat makes a channel ambiguous."""
    payload = _visual_data()
    payload["marks"][1]["mark_id"] = payload["marks"][0]["mark_id"]

    with pytest.raises(ValueError, match="share one id"):
        VisualData.model_validate(payload)


def test_a_derived_mark_is_drawn_at_the_figure_its_chain_computed() -> None:
    """Otherwise the bar and the provenance under it are two different numbers."""
    payload = _visual_data()
    figure = payload["encoding"]["quantity"][0]
    chain = _derived(payload, "99", "mw")
    for mark in payload["marks"]:
        if mark["mark_id"] == figure:
            mark["element_id"] = None
            mark["derived"] = chain

    with pytest.raises(ValueError, match="chain computed"):
        VisualData.model_validate(payload)


def test_a_later_run_appends_and_never_reorders() -> None:
    """Row 13's monotonicity rule, made mechanical."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"].insert(0, payload["items"].pop())
    with pytest.raises(ValueError, match="never reorders"):
        DigestDay.model_validate(payload)


def test_a_partial_day_says_so() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json", partial=False)
    with pytest.raises(ValueError, match="partial"):
        DigestDay.model_validate(payload)


def test_vertical_counts_agree_with_the_items() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["verticals"][0]["count"] = 5
    with pytest.raises(ValueError, match="count disagrees"):
        DigestDay.model_validate(payload)


def test_a_revision_names_the_run_that_wrote_it() -> None:
    """Either both revision fields are set or neither is. One of the two alone is a wrong join."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)

    payload["items"][0]["updated_by_run"] = 2
    assert DigestDay.model_validate(payload).items[0].updated_by_run == 2

    del payload["items"][0]["updated_at"]
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)


def test_a_revision_cannot_precede_the_run_that_introduced_the_item() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][2]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][2]["updated_by_run"] = 1
    with pytest.raises(ValueError, match="cannot precede"):
        DigestDay.model_validate(payload)


def test_an_item_cannot_name_a_revising_run_the_day_never_recorded() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][0]["updated_by_run"] = 3
    with pytest.raises(ValueError, match="revised by a run that is not recorded"):
        DigestDay.model_validate(payload)


def test_a_day_written_before_the_revision_field_still_loads() -> None:
    """Additive and null-defaulted, so no committed payload had to be rewritten."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in payload["items"]:
        del item["updated_by_run"]

    day = DigestDay.model_validate(payload)

    assert [item.updated_by_run for item in day.items] == [None] * len(day.items)
