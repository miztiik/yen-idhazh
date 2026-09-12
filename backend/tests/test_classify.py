"""The two calls that read one article, and the bytes they build.

Row #7a moved these out of `test_visual_planner` with the code they cover. The
first test is the move's own oracle and it belongs at the top: a refactor that
changed a request body would have shipped looking like a rename.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import (
    CALL_ONE_REPLIES,
    CALL_TWO_REPLIES,
    CONFIG_DIR,
    FIXTURES_DIR,
    REPO_ROOT,
    RecordedEndpoint,
    a_table,
    call_one_payload,
    read_text,
)
from pydantic import BaseModel, ValidationError

from idhazh import config, summarize
from idhazh.classify.calls import (
    ANCHORED_MAX,
    CALL_TWO_BUDGET_TOKENS,
    CHARS_PER_WORD,
    LABEL_PASS_VERSION,
    LABELS_MAX,
    PROPOSED_MAX,
    SALIENCE_SCORE,
    CallOneReply,
    MentionGroup,
    anchored,
    apply_labels,
    build_call_one_request,
    build_call_two_request,
    call_one_schema,
    call_one_system_prompt,
    call_one_user_turn,
    call_two_output_tokens,
    call_two_prose_words,
    call_two_schema,
    call_two_user_turn,
    candidate_menu,
    drawn_label,
    mention_elements,
    model_anchored,
    numbered_sentences,
    parse_call_one,
    parse_call_two,
    proposed_quantities,
    range_elements,
    recovered_completion,
    sentence_id,
)
from idhazh.contracts.app_config import (
    ElementsConfig,
    InferenceConfig,
    SummarizeConfig,
    VisualsConfig,
)
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementKind, ElementTable, Extractor
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import CODE_STAMPED_FIELDS, VisualPlan, widest_json_characters
from idhazh.contracts.visual_decision import VisualKind
from idhazh.elements import SpanDriftError, element_table
from idhazh.extract import approx_tokens
from idhazh.llm.server import Completion, post
from idhazh.visual_planner import plan_lost_to_the_budget

RECORDED_PAYLOADS = FIXTURES_DIR / "planner" / "recorded-call-payloads.json"

#: How to re-record after a DELIBERATE prompt or bound change. Nothing else may
#: move these bytes, which is the whole point of the file.
RECAPTURE = (
    "python -c \"import json, pathlib, sys; sys.path[:0] = ['backend', 'backend/tests']; "
    "import test_classify as t; p = pathlib.Path(t.RECORDED_PAYLOADS); d = json.loads("
    "p.read_text()); d['call_one'], d['call_two'] = t.rebuilt_payloads(d['inputs']); "
    "p.write_text(json.dumps(d, indent=2) + chr(10))\""
)


def rebuilt_payloads(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Both request bodies, from the inputs the fixture recorded beside them.

    Every input is read from the fixture rather than from `config/`, so a knob an
    operator turns cannot move these bytes and a later row is free to turn one.
    What can move them is a prompt file, a decoder bound or a change to this
    code - which is exactly the set a byte comparison should notice.
    """
    article = Article.from_json(read_text(REPO_ROOT / inputs["article"]))
    table = element_table(
        article, config=ElementsConfig(max_per_article=inputs["elements_max_per_article"])
    )
    reply = json.loads(read_text(REPO_ROOT / inputs["call_one_reply"]))
    call_one = build_call_one_request(
        article,
        table,
        model_id=inputs["model_id"],
        inference=InferenceConfig.model_validate(inputs["inference"]),
    )
    call_two = build_call_two_request(
        call_one,
        reply["choices"][0]["message"]["content"],
        source_words=article.band_source_words,
    )
    return call_one, call_two


def test_both_request_bodies_are_the_bytes_recorded_before_the_code_moved() -> None:
    """The oracle for the move: a pure move proves itself by producing the same bytes.

    The fixture was captured from `visual_planner` in the commit before a line of
    it moved, so a rename that quietly re-rendered a prompt, reordered a message
    or dropped a decoder bound fails here rather than in a run nobody watches.
    It is asserted on the serialised bytes rather than on the dicts, because a
    key order a server tokenises differently is a real difference and a dict
    comparison cannot see it.
    """
    recorded = json.loads(read_text(RECORDED_PAYLOADS))
    call_one, call_two = rebuilt_payloads(recorded["inputs"])

    built = json.dumps({"call_one": call_one, "call_two": call_two}, indent=2)
    kept = json.dumps(
        {"call_one": recorded["call_one"], "call_two": recorded["call_two"]}, indent=2
    )
    assert built == kept, f"the request bodies moved. If that was deliberate:\n{RECAPTURE}"


def test_the_same_check_fails_on_a_body_that_was_re_rendered() -> None:
    """The bite proof: an oracle that cannot fail is not an oracle."""
    recorded = json.loads(read_text(RECORDED_PAYLOADS))
    tampered = dict(recorded["inputs"]) | {"model_id": recorded["inputs"]["model_id"] + "x"}

    call_one, _ = rebuilt_payloads(tampered)

    assert call_one != recorded["call_one"]


# --- Call 1: the model reads the article and points at it --------------------
#
# The oracle for this row is one sentence: no field of call 1's schema accepts a
# number, a span or a character offset. It is asserted against the schema the
# decoder is handed, so a figure the article does not carry is unreachable by
# grammar rather than caught by a check downstream - and `schema_types` is shown
# to fail on a shape that does accept one, two tests below.

#: Five figures, two sentences apart, one of them a date. Small enough that a
#: cap of two bites where a reader can see it bite.
DENSE_TEXT = (
    "The plant produced 4,200 megawatt hours in March 2026, up from 3,150 megawatt hours in "
    "February. Costs fell 12 percent. Officials expect about 5,000 megawatt hours next year."
)


def schema_types(node: object) -> set[str]:
    """Every JSON type the schema declares anywhere in it, `$defs` included."""
    if isinstance(node, dict):
        declared = node.get("type")
        named = {declared} if isinstance(declared, str) else set(declared or [])
        return named.union(*(schema_types(value) for value in node.values()), set())
    if isinstance(node, list):
        return set().union(*(schema_types(value) for value in node), set())
    return set()


def a_reply(**named: object) -> CallOneReply:
    """A reply with every required field filled, so a case reads as its point."""
    body: dict[str, object] = {
        "labels": [],
        "proposed": [],
        "entity_mentions": [],
        "place_mentions": [],
        "quotes": [],
        "claims": [],
        "keyphrases": [],
        "lede_sentence_ids": [],
    }
    body.update(named)
    return CallOneReply.model_validate(body)


def a_group(
    name: str, *surfaces: tuple[str, str], salience: str = "supporting"
) -> dict[str, object]:
    """One named thing and the sentences it is named in, as `(sentence_id, surface)`."""
    return {
        "mentions": [{"sentence_id": where, "surface": words} for where, words in surfaces],
        "name": name,
        "salience": salience,
    }


def a_range(first: str, last: str, **named: object) -> dict[str, object]:
    body: dict[str, object] = {
        "sentence_start_id": first,
        "sentence_end_id": last,
        "speaker": "",
        "attribution": "unattributed",
        "hedge": False,
    }
    body.update(named)
    return body


def a_label(element_id: str, **named: object) -> dict[str, object]:
    body: dict[str, object] = {
        "element_id": element_id,
        "measure": "",
        "dimension": "",
        "entity": "",
        "time_element_id": "",
        "attribution": "unattributed",
        "hedge": False,
        "salience": "background",
    }
    body.update(named)
    return body


@pytest.fixture
def dense(article_ok: Article) -> Article:
    return article_ok.model_copy(update={"text": DENSE_TEXT})


class TestTheOracle:
    def test_no_field_of_call_one_accepts_a_number_a_span_or_an_offset(self) -> None:
        """The row's whole point. A span and an offset are integers, so this covers both."""
        assert schema_types(call_one_schema()) & {"integer", "number"} == set()

    def test_the_same_check_fails_on_a_shape_that_does_accept_one(self) -> None:
        """The bite proof: a passing oracle that cannot fail is not an oracle.

        This is the shape section 10.1a rejected - the model handing back the
        offsets it means. It is written here so the assertion above is known to
        be able to go red, rather than passing because it looks at nothing.
        """

        class SpanCitation(BaseModel):
            span_start: int
            surface: str

        assert schema_types(SpanCitation.model_json_schema()) & {"integer", "number"} == {"integer"}

    def test_an_unknown_element_id_drops_that_label_and_keeps_its_siblings(
        self, dense: Article
    ) -> None:
        """The other half of the oracle. A rejection costs one label, never the article."""
        table = a_table(dense)
        real = table.elements[0].element_id
        reply = a_reply(
            labels=[
                a_label("quantity-9000-9010", measure="a fact no pass found"),
                a_label(real, measure="output", salience="primary"),
            ]
        )

        labelled = apply_labels(table, reply, label_source="m")

        by_id = {element.element_id: element for element in labelled.elements}
        assert by_id[real].measure == "output"
        assert len(labelled.elements) == len(table.elements)
        assert all(element.measure != "a fact no pass found" for element in labelled.elements)


class TestCallOneShape:
    def test_the_schema_is_generated_from_the_model(self) -> None:
        assert call_one_schema() == CallOneReply.model_json_schema()

    def test_every_field_is_required_so_the_decoder_must_emit_it(self) -> None:
        """A field with a default is absent from `required`, and the grammar skips it."""
        assert set(call_one_schema()["required"]) == {
            "labels",
            "proposed",
            "entity_mentions",
            "place_mentions",
            "quotes",
            "claims",
            "keyphrases",
            "lede_sentence_ids",
        }

    def test_the_mention_lists_do_not_reach_the_tag_control(self) -> None:
        """Andre's ruling on tags binds this shape, and this is where it was settled.

        What that control protects is the reader-facing tag vocabulary: a page
        choosing its own tags steers it, so no prompt here asks a model to pick
        one. A mention list is not that. The model points at characters code
        cuts, the group key is matched against slugs code already holds, and
        this pass mints nothing - so the control is untouched and the two lists
        are named for the Tier 1 thing code takes from them rather than for the
        Tier 2 key, which is also the truer name.

        It is checked over the schema as well as the prompt, which is one more
        surface than `test_tag.py` reads: the schema is handed to the decoder in
        `response_format`, so a class docstring is prompt text too.
        """
        schema = json.dumps(call_one_schema()).lower()
        prompt = call_one_system_prompt().lower()
        for banned in ("lens", "event type", "entities"):
            assert banned not in prompt, banned
            assert banned not in schema, banned
        assert "entity_mentions" in call_one_schema()["properties"]
        assert "place_mentions" in call_one_schema()["properties"]

    def test_a_mention_is_written_before_the_name_that_groups_it(self) -> None:
        """Field order is decode order (row 12): the anchor first, the judgement last."""
        group = list(call_one_schema()["$defs"]["NamedMentions"]["properties"])
        assert group == ["mentions", "name", "salience"]

    def test_what_was_found_decodes_before_what_it_means(self) -> None:
        """Field order is decode order (row 12): the anchor first, the judgement last."""
        label = list(call_one_schema()["$defs"]["ElementLabel"]["properties"])
        assert label[0] == "element_id"
        assert label[-1] == "salience"

    def test_the_schema_forbids_an_unknown_key(self) -> None:
        with pytest.raises(ValidationError):
            CallOneReply.model_validate({"labels": [], "tool_call": {"name": "rm"}})

    def test_the_label_bound_is_the_menu_size_the_planner_already_reads(self) -> None:
        """The bound has a reason, so the reason is checked rather than written down."""
        assert LABELS_MAX == VisualsConfig().max_facts

    def test_a_reply_missing_a_field_is_a_shape_failure(self) -> None:
        with pytest.raises(ValidationError):
            parse_call_one('{"labels":[],"proposed":[]}')

    def test_a_reply_that_found_nothing_is_a_legal_reply(self) -> None:
        """`can emit no number at all` includes emitting nothing at all."""
        assert parse_call_one(json.dumps(a_reply().model_dump())).labels == []

    def test_it_strips_a_thinking_block(self) -> None:
        raw = "<think>reading it</think>" + json.dumps(a_reply().model_dump())
        assert parse_call_one(raw).proposed == []


class TestCallOnePrompting:
    def test_the_article_reaches_the_model_fenced_as_data(self, dense: Article) -> None:
        turn = call_one_user_turn(dense, a_table(dense))
        assert "UNTRUSTED" in turn.upper()
        assert "4,200 megawatt hours" in turn

    def test_the_system_prompt_never_carries_the_article(self, dense: Article) -> None:
        assert (dense.text or "") not in call_one_system_prompt()

    def test_the_model_reads_the_article_and_not_a_summary(
        self, dense: Article, summary_ok: Summary
    ) -> None:
        """Decision 1. A compression cannot carry the series a chart exists to show."""
        turn = call_one_user_turn(dense, a_table(dense))
        assert (summary_ok.summary or "") not in turn

    def test_every_sentence_the_model_may_cite_carries_its_address(self) -> None:
        addressed = numbered_sentences(DENSE_TEXT)
        assert addressed.startswith("[s0] The plant produced")
        assert "[s2] Officials expect" in addressed

    def test_the_menu_addresses_every_candidate_by_its_own_id(self, dense: Article) -> None:
        table = a_table(dense)
        menu = candidate_menu(table)
        assert all(f"[{element.element_id}]" in menu for element in table.elements)

    def test_an_article_with_nothing_in_it_says_so(self, article_ok: Article) -> None:
        bare = article_ok.model_copy(update={"text": "Nothing to count here."})
        assert "no quantities or dates" in candidate_menu(a_table(bare))

    def test_a_table_over_another_string_is_refused_rather_than_printed(
        self, dense: Article, article_ok: Article
    ) -> None:
        """Every row of the menu is an offset. Against the wrong text they all point elsewhere."""
        with pytest.raises(SpanDriftError):
            call_one_user_turn(article_ok, a_table(dense))

    def test_the_request_hands_the_decoder_the_reply_shape(self, dense: Article) -> None:
        payload = build_call_one_request(
            dense,
            a_table(dense),
            model_id="m",
            inference=config.load(CONFIG_DIR).app.models.summarize.inference,
        )
        assert payload["response_format"]["json_schema"]["schema"] == call_one_schema()
        assert payload["messages"][0]["role"] == "system"
        assert (dense.text or "") not in payload["messages"][0]["content"]
        assert "4,200 megawatt hours" in payload["messages"][1]["content"]


class TestLabelling:
    def test_a_label_writes_the_cells_it_can_anchor(self, article_ok: Article) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        first = table.elements[0].element_id
        reply = a_reply(
            labels=[
                a_label(
                    first,
                    measure="output",
                    dimension="by month",
                    attribution="named",
                    hedge=True,
                    salience="primary",
                )
            ]
        )

        element = apply_labels(table, reply, label_source="qwen").elements[0]

        assert element.measure == "output"
        assert element.dimension == "by-month", "a dimension groups, so it is one controlled word"
        assert element.attribution == "named"
        assert element.hedge is True
        assert element.label_source == "qwen"
        assert element.ledger_version == LABEL_PASS_VERSION

    def test_a_band_becomes_the_score_that_band_means(self, article_ok: Article) -> None:
        """The model picks a word; code converts. It never types the number."""
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(labels=[a_label(table.elements[0].element_id, salience="supporting")])

        assert apply_labels(table, reply, label_source="m").elements[0].salience == pytest.approx(
            SALIENCE_SCORE["supporting"]
        )

    def test_a_fact_stated_in_the_items_own_voice_records_no_attribution(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(labels=[a_label(table.elements[0].element_id, attribution="unattributed")])

        assert apply_labels(table, reply, label_source="m").elements[0].attribution is None

    def test_a_time_that_names_a_date_copies_the_date_the_article_wrote(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        date = next(one for one in table.elements if one.kind is ElementKind.DATE)
        reply = a_reply(
            labels=[a_label(table.elements[0].element_id, time_element_id=date.element_id)]
        )

        assert apply_labels(table, reply, label_source="m").elements[0].time == date.value

    def test_a_time_that_names_no_date_drops_the_time_and_keeps_the_measure(
        self, article_ok: Article
    ) -> None:
        """Each cell degrades on its own. One unusable judgement is not eight."""
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(
            labels=[
                a_label(
                    table.elements[0].element_id, measure="output", time_element_id="date-1-2"
                )
            ]
        )

        element = apply_labels(table, reply, label_source="m").elements[0]
        assert element.time is None
        assert element.measure == "output"

    def test_a_time_that_names_a_quantity_is_not_a_time(self, article_ok: Article) -> None:
        """A date is the only kind that reads as a date, whatever the reply cites."""
        table = a_table(article_ok, DENSE_TEXT)
        other = next(
            one for one in table.elements[1:] if one.kind is ElementKind.QUANTITY
        ).element_id
        reply = a_reply(labels=[a_label(table.elements[0].element_id, time_element_id=other)])

        assert apply_labels(table, reply, label_source="m").elements[0].time is None

    def test_an_entity_nothing_tracks_is_not_minted(self, article_ok: Article) -> None:
        """The name groups mentions. The slug is the watchlist's and is never invented."""
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(labels=[a_label(table.elements[0].element_id, entity="The Plant")])

        assert apply_labels(table, reply, label_source="m").elements[0].entity is None

    def test_a_tracked_entity_lands_under_the_slug_the_watchlist_holds(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(labels=[a_label(table.elements[0].element_id, entity="The Plant")])

        labelled = apply_labels(
            table, reply, label_source="m", entity_slugs={"the plant": "example-plant"}
        )
        assert labelled.elements[0].entity == "example-plant"

    def test_the_first_citation_of_one_address_wins(self, article_ok: Article) -> None:
        """A second opinion about one fact must not make the result depend on decode order."""
        table = a_table(article_ok, DENSE_TEXT)
        first = table.elements[0].element_id
        reply = a_reply(
            labels=[a_label(first, measure="output"), a_label(first, measure="revenue")]
        )

        assert apply_labels(table, reply, label_source="m").elements[0].measure == "output"

    def test_a_label_leaves_every_tier_one_cell_alone(self, article_ok: Article) -> None:
        """Tier 1 is what code cut. No judgement may move a span or a value."""
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(
            labels=[a_label(one.element_id, measure="anything") for one in table.elements]
        )

        labelled = apply_labels(table, reply, label_source="m")
        before = [(one.span_start, one.span_end, one.value, one.unit) for one in table.elements]
        after = [(one.span_start, one.span_end, one.value, one.unit) for one in labelled.elements]
        assert after == before


class TestProposals:
    def test_a_figure_past_the_pattern_cap_is_recovered(self, article_ok: Article) -> None:
        """What `proposed` is for: the bound on work is what a dense article hits."""
        table = a_table(article_ok, DENSE_TEXT, cap=2)
        reply = a_reply(proposed=[{"sentence_id": "s2", "surface": "5,000 megawatt hours"}])

        recovered = anchored(
            table, DENSE_TEXT, reply, config=ElementsConfig(max_per_article=2), label_source="m"
        )

        landed = [one for one in recovered.elements if one.extractor is Extractor.MODEL]
        assert [one.value for one in landed] == ["5000"]
        assert [one.unit for one in landed] == ["megawatt"]

    def test_a_recovered_figure_is_cut_from_the_article_and_not_from_the_reply(self) -> None:
        """The model pointed. Code cut. The characters are the article's own."""
        reply = a_reply(proposed=[{"sentence_id": "s2", "surface": "5,000 megawatt hours"}])

        landed = proposed_quantities(DENSE_TEXT, reply)

        assert [DENSE_TEXT[one.span_start : one.span_end] for one in landed] == [
            one.span_excerpt for one in landed
        ]

    def test_a_surface_the_article_never_wrote_is_refused(self) -> None:
        """A figure the model typed rather than found has nowhere to anchor."""
        reply = a_reply(proposed=[{"sentence_id": "s2", "surface": "9,900 megawatt hours"}])
        assert proposed_quantities(DENSE_TEXT, reply) == []

    def test_a_surface_that_occurs_twice_in_its_sentence_is_refused(self) -> None:
        """Mis-pointing is the failure no span check can see, so ambiguity is a rejection."""
        text = "It shipped 500 tonnes and then 500 tonnes more."
        reply = a_reply(proposed=[{"sentence_id": "s0", "surface": "500 tonnes"}])
        assert proposed_quantities(text, reply) == []

    def test_a_surface_holding_two_figures_is_refused(self) -> None:
        text = "Output moved between 1,100 tonnes and 1,900 tonnes."
        reply = a_reply(
            proposed=[{"sentence_id": "s0", "surface": "1,100 tonnes and 1,900 tonnes"}]
        )
        assert proposed_quantities(text, reply) == []

    def test_an_address_that_names_no_sentence_is_refused(self) -> None:
        text = "Costs fell 12 percent."
        for address in ("s9", "twelve", "x"):
            reply = a_reply(proposed=[{"sentence_id": address, "surface": "12 percent"}])
            assert proposed_quantities(text, reply) == [], address

    def test_a_number_spelled_out_in_words_stays_refused(self) -> None:
        """Decision 4. There is nothing for the pattern to parse."""
        text = "Cost fell by about a third against the model it replaces."
        reply = a_reply(proposed=[{"sentence_id": "s0", "surface": "about a third"}])
        assert proposed_quantities(text, reply) == []

    def test_a_relative_change_stays_refused(self) -> None:
        text = "Throughput doubled against the previous release."
        reply = a_reply(proposed=[{"sentence_id": "s0", "surface": "doubled"}])
        assert proposed_quantities(text, reply) == []

    def test_a_proposal_over_characters_the_pass_already_read_is_dropped(
        self, article_ok: Article
    ) -> None:
        """A second reading of what code already read is not a recovery."""
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(proposed=[{"sentence_id": "s0", "surface": "4,200 megawatt hours"}])

        merged = anchored(table, DENSE_TEXT, reply, config=ElementsConfig(), label_source="m")

        assert [one.element_id for one in merged.elements] == [
            one.element_id for one in table.elements
        ]

    def test_the_count_of_what_was_found_still_covers_what_was_kept(
        self, article_ok: Article
    ) -> None:
        """A proposal that read is a candidate, whether or not it survived the merge."""
        table = a_table(article_ok, DENSE_TEXT, cap=2)
        reply = a_reply(proposed=[{"sentence_id": "s2", "surface": "5,000 megawatt hours"}])

        merged = anchored(
            table, DENSE_TEXT, reply, config=ElementsConfig(max_per_article=2), label_source="m"
        )

        found = merged.candidates_found[ElementKind.QUANTITY]
        assert found == table.candidates_found[ElementKind.QUANTITY] + 1

    def test_the_merge_never_evicts_what_the_pattern_found(self, article_ok: Article) -> None:
        """The recovery is not spent out of the pattern's budget, or it is unreachable."""
        table = a_table(article_ok, DENSE_TEXT, cap=2)
        reply = a_reply(proposed=[{"sentence_id": "s2", "surface": "5,000 megawatt hours"}])

        merged = anchored(
            table, DENSE_TEXT, reply, config=ElementsConfig(max_per_article=2), label_source="m"
        )

        assert {one.element_id for one in table.elements} <= {
            one.element_id for one in merged.elements
        }
        assert len(merged.elements) <= 2 + PROPOSED_MAX


# --- The four kinds only a model can find ------------------------------------
#
# The oracle for this row is two sentences. For every surviving element of every
# kind, `article.text[span_start:span_end] == span_excerpt`. And no element's
# drawn label is ever its Tier 2 `name` - the label is one of the mentions that
# anchored. Both halves carry a bite proof below, because a passing check that
# cannot fail is not a check.

#: One item carrying all four model-pointed kinds. The name a page must never
#: draw - "Vestas Wind Systems A/S" - appears nowhere in it, which is decision
#: 1's case: the canonical name may be written nowhere verbatim.
POINTED_TEXT = (
    "Vestas said its plants ran at full output through March. "
    "Vestas expects the same in April, an official in Aarhus said. "
    "The company has not published the figures."
)

#: The whole reply for that item, as the four lists a producer reads.
POINTED_REPLY: dict[str, object] = {
    "entity_mentions": [a_group("Vestas Wind Systems A/S", ("s0", "Vestas"), ("s1", "Vestas"))],
    "place_mentions": [a_group("Aarhus", ("s1", "Aarhus"))],
    "quotes": [a_range("s1", "s1", speaker="an official", attribution="anonymous")],
    "claims": [a_range("s2", "s2")],
}


def kinds_of(table: ElementTable) -> set[ElementKind]:
    return {element.kind for element in table.elements}


class TestTheFourKindsOracle:
    def test_every_surviving_element_of_every_kind_cuts_its_own_excerpt(
        self, article_ok: Article
    ) -> None:
        """Half one of the oracle, done by the test rather than by the contract.

        The four kinds are asserted present first. A re-slice check over an empty
        set passes and means nothing, and this row's whole subject is the set.
        """
        table = a_table(article_ok, POINTED_TEXT)

        whole = anchored(
            table, POINTED_TEXT, a_reply(**POINTED_REPLY), config=ElementsConfig(), label_source="m"
        )

        assert {
            ElementKind.ENTITY,
            ElementKind.PLACE,
            ElementKind.QUOTE,
            ElementKind.CLAIM,
        } <= kinds_of(whole)
        for element in whole.elements:
            assert POINTED_TEXT[element.span_start : element.span_end] == element.span_excerpt

    def test_the_same_check_goes_red_when_the_text_moves_under_the_spans(
        self, article_ok: Article
    ) -> None:
        """The bite proof for half one: one inserted character and it fails.

        Half one already held for `quantity` and `date` before this row, so on
        its own it is not a measurement of anything new. This is what shows it
        can still fail - the spans are real offsets into one string and nothing
        else.
        """
        table = a_table(article_ok, POINTED_TEXT)
        whole = anchored(
            table, POINTED_TEXT, a_reply(**POINTED_REPLY), config=ElementsConfig(), label_source="m"
        )
        moved = " " + POINTED_TEXT

        assert whole.span_drift(POINTED_TEXT) is None
        assert whole.span_drift(moved) is not None
        assert any(
            moved[element.span_start : element.span_end] != element.span_excerpt
            for element in whole.elements
        )

    def test_a_drawn_label_is_one_of_the_mentions_that_anchored(self) -> None:
        """Half two: the mention draws and the name never does.

        The item writes "Vestas" twice and never writes the canonical name, so a
        page that drew `name` would show a string the item does not contain.
        """
        groups, _ = model_anchored(
            POINTED_TEXT, a_reply(**POINTED_REPLY), label_source="m", entity_slugs={}
        )
        group = next(one for one in groups if one.elements[0].kind is ElementKind.ENTITY)

        assert drawn_label(group) in {one.span_excerpt for one in group.elements}
        assert drawn_label(group) == "Vestas"
        assert group.name == "Vestas Wind Systems A/S"

    def test_the_same_check_goes_red_on_a_label_taken_from_the_name(self) -> None:
        """The bite proof for half two: the shape invariant 2 forbids, checked.

        `named_label` is the easier and tidier implementation the drawing warns
        about. It is written here so the assertion above is known to be able to
        go red, rather than passing because both sides say the same thing.
        """
        groups, _ = model_anchored(
            POINTED_TEXT, a_reply(**POINTED_REPLY), label_source="m", entity_slugs={}
        )
        group = next(one for one in groups if one.elements[0].kind is ElementKind.ENTITY)

        def named_label(one: MentionGroup) -> str:
            return one.name

        assert named_label(group) not in {one.span_excerpt for one in group.elements}
        assert named_label(group) not in POINTED_TEXT


class TestMentions:
    def test_a_name_the_item_never_wrote_still_anchors_its_mentions(self) -> None:
        """Decision 1. The name is a grouping key and is never searched for."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(**POINTED_REPLY).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert [one.span_excerpt for one in groups[0].elements] == ["Vestas", "Vestas"]
        assert [one.sentence_index for one in groups[0].elements] == [0, 1]

    def test_a_surface_that_occurs_twice_in_its_sentence_is_refused(self) -> None:
        """Decision 2, and the only control the design has over mis-pointing."""
        text = "Vestas told Vestas staff nothing. The plant is quiet."
        groups = mention_elements(
            text,
            a_reply(entity_mentions=[a_group("Vestas", ("s0", "Vestas"))]).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_a_surface_from_another_sentence_is_refused(self) -> None:
        """Only the named sentence is searched, so a real word in the wrong place misses."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(entity_mentions=[a_group("Aarhus", ("s0", "Aarhus"))]).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_one_refused_mention_leaves_its_siblings_standing(self) -> None:
        """Decision 5: a rejection is per element, never per article."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(
                entity_mentions=[
                    a_group("Vestas", ("s0", "Vestas"), ("s9", "Vestas"), ("s1", "Vestas"))
                ]
            ).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert len(groups[0].elements) == 2

    def test_a_group_that_anchors_nothing_is_dropped(self) -> None:
        """Zero surviving mentions is a name nobody can point at."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(entity_mentions=[a_group("Orsted", ("s0", "Orsted"))]).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_a_whitespace_surface_is_refused_rather_than_cutting_nothing(self) -> None:
        """A zero-width span is a payload the contract will not hold."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(entity_mentions=[a_group("Vestas", ("s0", " "))]).entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_a_tracked_name_groups_under_the_slug_and_an_unknown_one_mints_none(self) -> None:
        """The alias ledger is separate work, so this pass never invents a group."""
        reply = a_reply(**POINTED_REPLY)

        tracked = mention_elements(
            POINTED_TEXT,
            reply.entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={"vestas wind systems a/s": "vestas"},
        )
        unknown = mention_elements(
            POINTED_TEXT,
            reply.entity_mentions,
            kind=ElementKind.ENTITY,
            label_source="m",
            entity_slugs={},
        )

        assert all(one.entity == "vestas" for one in tracked[0].elements)
        assert all(one.entity is None for one in unknown[0].elements)

    def test_a_mention_is_tier_one_and_says_who_judged_the_rest(self) -> None:
        """The span is code's; the salience is the model's, and it is attributed."""
        element = mention_elements(
            POINTED_TEXT,
            a_reply(**POINTED_REPLY).place_mentions,
            kind=ElementKind.PLACE,
            label_source="qwen",
            entity_slugs={},
        )[0].elements[0]

        assert element.kind is ElementKind.PLACE
        assert element.extractor is Extractor.MODEL
        assert element.value is None and element.unit is None
        assert element.salience == SALIENCE_SCORE["supporting"]
        assert element.label_source == "qwen"
        assert element.ledger_version == LABEL_PASS_VERSION


class TestSentenceRanges:
    def test_a_quote_is_the_sentences_between_two_addresses(self) -> None:
        """Decision 3: addresses only. Code slices; the reply carries no text."""
        element = range_elements(
            POINTED_TEXT,
            a_reply(**POINTED_REPLY).quotes,
            kind=ElementKind.QUOTE,
            label_source="m",
            entity_slugs={},
        )[0]

        assert element.span_excerpt == (
            "Vestas expects the same in April, an official in Aarhus said."
        )
        assert POINTED_TEXT[element.span_start : element.span_end] == element.span_excerpt
        assert element.attribution == "anonymous"

    def test_a_range_over_several_sentences_carries_all_of_them(self) -> None:
        element = range_elements(
            POINTED_TEXT,
            a_reply(claims=[a_range("s0", "s2")]).claims,
            kind=ElementKind.CLAIM,
            label_source="m",
            entity_slugs={},
        )[0]

        assert element.span_excerpt == POINTED_TEXT.strip()

    def test_a_run_the_shape_will_not_hold_is_dropped_rather_than_cut_down(self) -> None:
        """A truncated excerpt stops being the characters its span names."""
        long_text = " ".join(f"Sentence {index} runs on and on and on." for index in range(40))

        found = range_elements(
            long_text,
            a_reply(quotes=[a_range("s0", "s39")]).quotes,
            kind=ElementKind.QUOTE,
            label_source="m",
            entity_slugs={},
        )

        assert len(long_text) > 500
        assert found == []

    def test_an_address_that_names_no_sentence_is_dropped(self) -> None:
        found = range_elements(
            POINTED_TEXT,
            a_reply(quotes=[a_range("s0", "s99"), a_range("later", "s1")]).quotes,
            kind=ElementKind.QUOTE,
            label_source="m",
            entity_slugs={},
        )

        assert found == []

    def test_a_range_that_ends_before_it_starts_is_dropped(self) -> None:
        found = range_elements(
            POINTED_TEXT,
            a_reply(claims=[a_range("s2", "s0")]).claims,
            kind=ElementKind.CLAIM,
            label_source="m",
            entity_slugs={},
        )

        assert found == []

    def test_an_item_speaking_in_its_own_voice_records_no_attribution(self) -> None:
        element = range_elements(
            POINTED_TEXT,
            a_reply(**POINTED_REPLY).claims,
            kind=ElementKind.CLAIM,
            label_source="m",
            entity_slugs={},
        )[0]

        assert element.attribution is None
        assert element.hedge is False
        assert element.label_source == "m"


class TestMergingTheFourKinds:
    def test_a_quote_carrying_a_quantity_keeps_both(self, article_ok: Article) -> None:
        """`settle` is the rule between the two pattern passes and never sees these.

        A quote is a run of sentences, so it holds every figure inside it. Under
        the settle rule one of the two would drop the other, and that is exactly
        what these kinds must not do.
        """
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(quotes=[a_range("s0", "s0")])

        whole = anchored(table, DENSE_TEXT, reply, config=ElementsConfig(), label_source="m")

        quote = next(one for one in whole.elements if one.kind is ElementKind.QUOTE)
        inside = [
            one
            for one in whole.elements
            if one.kind is ElementKind.QUANTITY
            and quote.span_start <= one.span_start
            and one.span_end <= quote.span_end
        ]
        assert inside, "the fixture sentence has to carry a figure for this to mean anything"
        assert {one.element_id for one in table.elements} <= {
            one.element_id for one in whole.elements
        }

    def test_two_groups_claiming_one_address_keep_one_element(self, article_ok: Article) -> None:
        """A kind and a span identify one fact, so the second citation adds nothing."""
        table = a_table(article_ok, POINTED_TEXT)
        reply = a_reply(
            entity_mentions=[
                a_group("Vestas Wind Systems A/S", ("s0", "Vestas")),
                a_group("Vestas A/S", ("s0", "Vestas")),
            ]
        )

        whole = anchored(table, POINTED_TEXT, reply, config=ElementsConfig(), label_source="m")

        assert len([one for one in whole.elements if one.kind is ElementKind.ENTITY]) == 1

    def test_the_count_of_what_was_found_covers_every_new_kind(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, POINTED_TEXT)

        whole = anchored(
            table, POINTED_TEXT, a_reply(**POINTED_REPLY), config=ElementsConfig(), label_source="m"
        )

        for kind in (ElementKind.ENTITY, ElementKind.PLACE, ElementKind.QUOTE, ElementKind.CLAIM):
            kept = len([one for one in whole.elements if one.kind is kind])
            assert whole.candidates_found[kind] >= kept > 0

    def test_the_merge_stays_inside_the_bound_the_grammar_states(
        self, article_ok: Article
    ) -> None:
        """Every addition is bounded by the reply shape, so the total is stated."""
        table = a_table(article_ok, POINTED_TEXT, cap=2)

        whole = anchored(
            table,
            POINTED_TEXT,
            a_reply(**POINTED_REPLY),
            config=ElementsConfig(max_per_article=2),
            label_source="m",
        )

        assert len(whole.elements) <= 2 + PROPOSED_MAX + ANCHORED_MAX
        lists = call_one_schema()["properties"]
        per_group = call_one_schema()["$defs"]["NamedMentions"]["properties"]["mentions"]
        assert ANCHORED_MAX == (
            (lists["entity_mentions"]["maxItems"] + lists["place_mentions"]["maxItems"])
            * per_group["maxItems"]
            + lists["quotes"]["maxItems"]
            + lists["claims"]["maxItems"]
        ), "the bound is read off the grammar the decoder is handed, so it cannot drift from it"

    def test_a_label_cannot_reach_a_quote_the_menu_never_printed(
        self, article_ok: Article
    ) -> None:
        """A label names a candidate. A quote's own producer owns its judgements."""
        table = a_table(article_ok, POINTED_TEXT)
        first = a_reply(quotes=[a_range("s0", "s0", attribution="named")])
        quote = anchored(table, POINTED_TEXT, first, config=ElementsConfig(), label_source="m")
        address = next(
            one.element_id for one in quote.elements if one.kind is ElementKind.QUOTE
        )

        whole = anchored(
            table,
            POINTED_TEXT,
            a_reply(
                labels=[a_label(address, measure="a label aimed at a quote")],
                quotes=[a_range("s0", "s0", attribution="named")],
            ),
            config=ElementsConfig(),
            label_source="m",
        )

        assert all(one.measure is None for one in whole.elements)
        assert next(
            one.attribution for one in whole.elements if one.kind is ElementKind.QUOTE
        ) == "named"


def test_a_recorded_call_one_reply_labels_the_table_over_a_loopback_socket(
    article_ok: Article,
) -> None:
    """The row end to end, with no network and nothing mocked.

    The reply is played back by a real HTTP server on loopback and read through
    the transport every stage uses. The envelope is a llama-server envelope; the
    content is written by hand rather than captured, because no stage dispatches
    call 1 yet - the call that turns this table into a page is a later row. It
    carries no `usage` block for the same reason: a token count nobody measured
    is not a token count (Guardrail #10), and the transport reads a missing one as
    zero.
    """
    table = element_table(article_ok, config=ElementsConfig())
    payload = build_call_one_request(
        article_ok,
        table,
        model_id="m",
        inference=config.load(CONFIG_DIR).app.models.summarize.inference,
    )
    body = (CALL_ONE_REPLIES / "labelled.json").read_bytes()

    with RecordedEndpoint(200, body) as server:
        completion = post(payload, endpoint=server.endpoint, timeout=10.0)

    reply = parse_call_one(completion.content)
    labelled = anchored(
        table, article_ok.text or "", reply, config=ElementsConfig(), label_source="m"
    )

    judged = {one.element_id: one.measure for one in labelled.elements if one.measure}
    assert judged == {
        "quantity-149-159": "cost per million tokens",
        "quantity-197-201": "throughput on commodity CPUs",
    }
    assert all(
        one.extractor is Extractor.REGEX
        for one in labelled.elements
        if one.kind is ElementKind.QUANTITY
    ), "the one proposal in the reply is 'about a third', which no pattern can read"
    assert kinds_of(labelled) == {
        ElementKind.QUANTITY,
        ElementKind.ENTITY,
        ElementKind.QUOTE,
        ElementKind.CLAIM,
    }, "the reply's one place is 'Denmark', which the item never names"
    assert [
        one.span_excerpt for one in labelled.elements if one.kind is ElementKind.ENTITY
    ] == ["Example Lab"]
    assert labelled.span_drift(article_ok.text or "") is None
    assert sentence_id(labelled.elements[0].sentence_index) in candidate_menu(labelled)


# --- Call 2: the summary and the plan, over the prefix call 1 already paid for
#
# Two oracles, because the two halves fail for different reasons. The floor is
# that call 2's prompt opens with call 1's, byte for byte - so the article
# prefills once, or the prompt was built wrong. The target is whether call 1's
# own generated reply caches too, and that is a number off a running server
# rather than an assertion: `docs/architecture/summarize/prompt.md` records it.

def call_two_payload(article: Article, reply: str = "{}") -> dict[str, Any]:
    return build_call_two_request(
        call_one_payload(article), reply, source_words=article.band_source_words
    )


def bounded(schema: object, path: str = "") -> set[str]:
    """Every place in a generated schema a decoder may write without a bound."""
    loose: set[str] = set()
    if isinstance(schema, dict):
        kind = schema.get("type")
        if kind == "string" and "maxLength" not in schema and "enum" not in schema:
            loose.add(path)
        if kind == "array" and "maxItems" not in schema:
            loose.add(path)
        for key, value in schema.items():
            loose |= bounded(value, f"{path}.{key}" if path else str(key))
    if isinstance(schema, list):
        for index, value in enumerate(schema):
            loose |= bounded(value, f"{path}[{index}]")
    return loose


class TestTheCallTwoOracle:
    def test_call_two_opens_with_call_ones_prompt_byte_for_byte(self, dense: Article) -> None:
        """The floor. One re-rendered character in front of the article re-prefills it.

        A prefix cache reuses the longest common prefix of the tokenised prompt,
        so this is the property the cache hit is made of. It is asserted on the
        bytes rather than on a `prefill_ms` ratio, which would confound cache
        reuse with how long the new turn is and read as partial success when the
        prompt was built in the wrong order.
        """
        first = call_one_payload(dense)

        assert call_two_payload(dense)["messages"][:2] == first["messages"]

    def test_the_same_check_fails_on_a_prompt_that_was_re_rendered(
        self, dense: Article, article_ok: Article
    ) -> None:
        """The bite proof: an oracle that cannot fail is not an oracle."""
        other = call_one_payload(article_ok)

        assert call_two_payload(dense)["messages"][:2] != other["messages"]

    def test_the_summary_is_decoded_before_the_plan(self) -> None:
        """Decision 5, asserted where the decoder meets it rather than in the class.

        Field order is decode order, and this order is what makes a cut reply
        recoverable: the summary closes before the plan starts.
        """
        assert list(call_two_schema()["properties"]) == ["summary", "visual"]


class TestCallTwoShape:
    def test_call_ones_reply_is_replayed_as_the_assistant_turn(self, dense: Article) -> None:
        turns = call_two_payload(dense, '{"labels": []}')["messages"]

        assert [turn["role"] for turn in turns] == ["system", "user", "assistant", "user"]
        assert turns[2]["content"] == '{"labels": []}'

    def test_the_second_question_asks_for_both_halves_in_order(self) -> None:
        turn = call_two_user_turn()

        assert turn.index('"summary"') < turn.index('"visual"')

    def test_the_second_question_carries_no_article(self, dense: Article) -> None:
        """The article is in the first user turn and is still there.

        A second copy would spend prefill on bytes the server already holds, and
        would put the same untrusted text in front of the model twice.
        """
        assert (dense.text or "") not in call_two_payload(dense)["messages"][3]["content"]

    def test_the_ask_and_the_decoder_hold_the_same_band(self, dense: Article) -> None:
        """A prompt that asks for more key points than the decoder allows loses the item."""
        ask = config.load(CONFIG_DIR).app.summarize
        band = ask.band_for(dense.band_source_words)
        turn = call_two_user_turn(ask, source_words=dense.band_source_words)
        schema = call_two_schema(ask, source_words=dense.band_source_words)
        points = schema["$defs"]["SummaryDraft"]["properties"]["key_points"]

        assert f"{band.key_points_min} to {band.key_points_max} of them" in turn
        assert (points["minItems"], points["maxItems"]) == (
            band.key_points_min,
            band.key_points_max,
        )

    def test_they_still_agree_when_no_article_names_a_band(self) -> None:
        """The union rail, and the prompt has to state it too.

        With no article named the decoder holds the envelope every band fits
        inside. A prompt reading the shortest band's numbers off `band_for(0)`
        would ask for one key point where the grammar admits five.
        """
        ask = SummarizeConfig()
        points = call_two_schema(ask)["$defs"]["SummaryDraft"]["properties"]["key_points"]
        floor, ceiling = summarize.key_point_rail(ask, None, False)

        assert (points["minItems"], points["maxItems"]) == (floor, ceiling)
        assert f"{floor} to {ceiling} of them" in call_two_user_turn(ask)

    def test_the_plan_the_decoder_sees_carries_neither_field_code_stamps(self) -> None:
        """`version` and `plan_version` are facts code holds, not questions for a model."""
        plan = call_two_schema()["$defs"]["VisualPlanDraft"]["properties"]

        assert set(plan) & CODE_STAMPED_FIELDS == set()
        assert set(plan) | CODE_STAMPED_FIELDS == set(VisualPlan.model_fields)

    def test_no_string_and_no_array_in_the_reply_is_unbounded(self) -> None:
        """The precondition of the budget arithmetic, asserted rather than assumed."""
        assert bounded(call_two_schema()) == set()

    def test_a_reply_the_shape_forbids_is_refused(self) -> None:
        """Closed to unknown keys, so a planted tool call fails here."""
        body = json.loads(read_text(CALL_TWO_REPLIES / "summary-and-plan.json"))
        decoded = json.loads(body["choices"][0]["message"]["content"])
        decoded["visual"]["alt_text"] = "a picture of anything at all"

        with pytest.raises(ValidationError):
            parse_call_two(json.dumps(decoded), source_words=1320)


class TestTheDerivedBudget:
    def test_the_budget_is_the_arithmetic_and_not_a_number_somebody_chose(self) -> None:
        """Prose at 1.3 tokens a word, structure at one token a character."""
        ask = SummarizeConfig()
        words = call_two_prose_words(ask)
        whole = widest_json_characters(call_two_schema(ask))

        assert call_two_output_tokens(ask) == approx_tokens(words) + (
            whole - words * CHARS_PER_WORD
        )
        assert call_two_output_tokens(ask) == CALL_TWO_BUDGET_TOKENS

    def test_a_bound_that_moves_moves_the_budget_with_it(self) -> None:
        """Re-derived, not restated. This is what "derived" has to mean to be worth saying."""
        ask = SummarizeConfig()
        wider = ask.model_copy(update={"key_point_words_max": ask.key_point_words_max * 2})

        assert call_two_output_tokens(wider) > call_two_output_tokens(ask)

    def test_the_request_hands_the_decoder_the_derived_budget(self, dense: Article) -> None:
        payload = call_two_payload(dense)

        assert payload["max_tokens"] == call_two_output_tokens()
        assert payload["response_format"]["json_schema"]["schema"] == call_two_schema(
            source_words=dense.band_source_words
        )

    def test_the_second_call_decodes_nothing_the_first_call_settled(self, dense: Article) -> None:
        """Determinism is set in one place, and call 2 does not become a second one."""
        first = call_one_payload(dense)
        second = call_two_payload(dense)

        assert [second[key] for key in ("temperature", "top_p", "seed", "stream")] == [
            first[key] for key in ("temperature", "top_p", "seed", "stream")
        ]
        assert second["chat_template_kwargs"] == first["chat_template_kwargs"]


class TestARepliedCutByTheBudget:
    def test_a_reply_cut_in_the_plan_still_carries_its_summary(self) -> None:
        """E5. The bytes come back on an ordinary 200 and used to be thrown away unread."""
        body = json.loads(read_text(CALL_TWO_REPLIES / "cut-in-the-plan.json"))
        cut = Completion(
            content=body["choices"][0]["message"]["content"], finish_reason="length"
        )

        recovered = recovered_completion(cut)

        assert recovered is not None
        assert recovered.finish_reason == "stop"
        assert json.loads(recovered.content)["title"].startswith("Example Lab")

    def test_a_reply_cut_inside_the_summary_recovers_nothing(self) -> None:
        """The one case where there is genuinely nothing to publish."""
        body = json.loads(read_text(CALL_TWO_REPLIES / "cut-in-the-plan.json"))
        content = body["choices"][0]["message"]["content"]
        early = content[: content.index('"key_points"')]

        assert recovered_completion(Completion(content=early, finish_reason="length")) is None

    def test_a_reply_that_finished_is_never_recovered(self) -> None:
        """Recovery is for a cut reply. Anything else parses whole or fails as a shape."""
        body = json.loads(read_text(CALL_TWO_REPLIES / "summary-and-plan.json"))

        assert recovered_completion(Completion(content=body["choices"][0]["message"]["content"])) is None

    def test_a_recovered_reply_publishes_through_every_check_the_summarizer_runs(
        self, article_ok: Article
    ) -> None:
        """The recovery hands back a single-call reply, so nothing downstream is relaxed.

        The length verdict, the copied-source reject, the address reject and the
        restatement drop all read the recovered words the same way they read any
        others. Recovery stops an item being thrown away unread; it decides
        nothing about whether it may publish.
        """
        body = json.loads(read_text(CALL_TWO_REPLIES / "cut-in-the-plan.json"))
        cut = Completion(
            content=body["choices"][0]["message"]["content"], finish_reason="length"
        )
        recovered = recovered_completion(cut)
        assert recovered is not None

        summary = summarize.to_summary(
            article_ok,
            recovered,
            model_id="m",
            pipeline_fingerprint="0" * 64,
            generated_at="2026-09-10T00:00:00Z",
            prompt_config=config.load(CONFIG_DIR).app.summarize,
        )

        assert summary.status is SummaryStatus.OK
        assert summary.summary and "34 percent" in summary.summary
        assert summary.key_points

    def test_the_same_bytes_uncut_still_fail_the_way_they_always_did(
        self, article_ok: Article
    ) -> None:
        """The bite proof for the recovery: `to_summary` alone cannot read a cut reply."""
        body = json.loads(read_text(CALL_TWO_REPLIES / "cut-in-the-plan.json"))
        cut = Completion(
            content=body["choices"][0]["message"]["content"], finish_reason="length"
        )

        summary = summarize.to_summary(
            article_ok,
            cut,
            model_id="m",
            pipeline_fingerprint="0" * 64,
            generated_at="2026-09-10T00:00:00Z",
        )

        assert summary.status is SummaryStatus.FAILED

    def test_the_item_still_gets_a_decision_and_it_is_nothing(self, summary_ok: Summary) -> None:
        """`decision = none`, and never a failure code: the item publishes without a picture."""
        decision = plan_lost_to_the_budget(
            summary_ok, model_id="m", decided_at="2026-09-10T00:00:00Z", version="2026-08-21"
        )

        assert decision.kind is VisualKind.NONE
        assert decision.rationale and "output budget" in decision.rationale


def test_a_recorded_call_two_reply_parses_over_a_loopback_socket(article_ok: Article) -> None:
    """The row end to end, with no network and nothing mocked.

    The reply is played back by a real HTTP server on loopback and read through
    the transport every stage uses. The envelope is a llama-server envelope; the
    content is written by hand rather than captured, because no stage dispatches
    call 2 yet - the gate in front of it and the picture it leads to are later
    rows. It carries no `usage` block for the same reason: a token count nobody
    measured is not a token count (Guardrail #10).

    The plan's own `element_ids` are checked against the article's table here,
    which is the point of decision 3 - the plan sources the article, and the
    summary above it in the same reply only conditions it. Whether that table
    holds every id is the validator's rule and a later row's.
    """
    payload = call_two_payload(article_ok, read_text(FIXTURES_DIR / "completions" / "call-one" / "labelled.json"))
    body = (CALL_TWO_REPLIES / "summary-and-plan.json").read_bytes()

    with RecordedEndpoint(200, body) as server:
        completion = post(payload, endpoint=server.endpoint, timeout=10.0)

    reply = parse_call_two(completion.content, source_words=article_ok.band_source_words)
    table = element_table(article_ok, config=ElementsConfig())
    labelled = anchored(
        table,
        article_ok.text or "",
        parse_call_one(
            json.loads(read_text(FIXTURES_DIR / "completions" / "call-one" / "labelled.json"))[
                "choices"
            ][0]["message"]["content"]
        ),
        config=ElementsConfig(),
        label_source="m",
    )

    assert reply.summary.title.startswith("Example Lab")
    assert reply.visual is not None
    assert reply.visual.decision == "visual"
    assert set(reply.visual.element_ids) <= {one.element_id for one in labelled.elements}

