"""How do label evidence, request contracts and two-call continuations behave?"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from string import Template
from typing import Any

import pytest
from pydantic import ValidationError
from support.models import a_markers, a_server
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text
from support.prompts import LABEL_REPLIES, SUMMARIZE_AND_PLAN_REPLIES, a_table, label_payload
from support.server import RecordedEndpoint

from idhazh import config, summarize
from idhazh.classify.calls import (
    LABEL_PASS_VERSION,
    PROPOSED_MAX,
    ParsedLabelReply,
    anchored,
    apply_labels,
    build_label_request,
    build_summarize_and_plan_request,
    candidate_menu,
    drawn_label,
    label_request_schema,
    label_schema,
    label_system_prompt,
    label_user_turn,
    mention_elements,
    model_anchored,
    numbered_sentences,
    parse_label,
    parse_summarize_and_plan,
    proposed_quantities,
    recovered_completion,
    sentence_id,
    sentence_spans,
    summarize_and_plan_schema,
)
from idhazh.classify.dag import response_tokens
from idhazh.classify.plan_visual_request import (
    PLANNING_COLUMNS,
    PLANNING_JUDGEMENTS,
    planning_menu,
)
from idhazh.contracts.article import Article
from idhazh.contracts.element import (
    ElementKind,
    ElementTable,
    Extractor,
)
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.models import ModelEntry
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.summary import SummaryStatus
from idhazh.contracts.visual import (
    TITLE_MAX_LENGTH,
    EncodingRole,
    VisualType,
)
from idhazh.contracts.visual_validation import ValidatorCheck
from idhazh.elements import element_table
from idhazh.extract import approx_tokens
from idhazh.llm.server import (
    Completion,
    SystemPlacement,
    TurnMarkers,
    continued_prompt,
    post,
    render_prompt,
    response_limit,
)
from idhazh.render.chart import compile_chart
from idhazh.sanitize import FENCE_CLOSE, FENCE_OPEN
from idhazh.stages.two_calls import _shape_cells, two_calls_one_item
from idhazh.visual_validator import validate_plan


def configured() -> ModelEntry:
    """Read the validated summarizer entry selected by config."""
    return config.load(CONFIG_DIR).models.summarizer


def markers_from(recorded: dict[str, Any]) -> TurnMarkers:
    """The markers a set of recorded bodies was rendered with.

    Read off the fixture rather than off a running server, so the byte oracle
    below says what this code renders rather than what a model's template
    happens to write today.
    """
    return TurnMarkers(
        turn_opening=Template(recorded["turn_opening"]),
        turn_closing=recorded["turn_closing"],
        reply_opening=recorded["reply_opening"],
        reply_opening_thinking=recorded["reply_opening_thinking"],
        system_role=SystemPlacement(recorded.get("system_role", "own_turn")),
        system_joiner=recorded.get("system_joiner") or "",
        thinking_close=recorded["thinking_close"],
        thinking_kwarg=recorded.get("thinking_kwarg"),
    )


CHAT_TEMPLATE_RENDERING = FIXTURES_DIR / "prompts" / "chat-template.json"


class TestThePromptBytes:


    def test_explicit_turn_markers_match_the_recorded_template(self) -> None:
        """Check both reply openings against their historical recording.

        Its runtime and weights provenance stays in the fixture. No current
        model entry supplies inputs to this historical protocol comparison.
        """
        recorded = json.loads(read_text(CHAT_TEMPLATE_RENDERING))
        system, user = recorded["system"], recorded["user"]
        markers = a_markers(
            reply_opening="<|im_start|>assistant\n<think>\n\n</think>\n\n"
        )
        thinking = dataclasses.replace(markers, thinking_close="</think>")

        assert render_prompt(system=system, user=user, markers=markers) == (
            recorded["generation_prompt"]
        )
        assert render_prompt(system=system, user=user, markers=thinking) == (
            recorded["generation_prompt_thinking"]
        )

    def test_the_chat_template_breaks_the_property_our_renderer_keeps(self) -> None:
        """Why this row exists, as a paired assertion rather than a paragraph.

        The template writes an empty reasoning block into a generation prompt
        and drops it when the same turn comes back as history, so its second
        rendering stops matching its first four tokens early and everything
        behind the break is read again. Ours cannot: the second prompt is the
        first one extended.
        """
        recorded = json.loads(read_text(CHAT_TEMPLATE_RENDERING))
        markers = a_markers(
            reply_opening="<|im_start|>assistant\n<think>\n\n</think>\n\n"
        )
        opening = recorded["generation_prompt"] + recorded["reply"]
        ours = continued_prompt(
            render_prompt(
                system=recorded["system"], user=recorded["user"], markers=markers
            ),
            reply=recorded["reply"],
            user=recorded["question"],
            markers=markers,
        )

        assert not recorded["continued_prompt"].startswith(opening)
        assert ours.startswith(opening)

    def test_a_prompt_that_does_not_end_on_a_reply_opening_is_refused(self) -> None:
        """Nothing may be appended to a prompt whose end nobody recognises."""
        with pytest.raises(ValueError, match="reply opening"):
            continued_prompt(
                "a prompt that stops mid-sentence",
                reply="{}",
                user="and then?",
                markers=a_markers(),
            )

    def test_turn_rendering_uses_the_supplied_markers(self) -> None:
        """The substitution test: move the markers and the bytes move with them."""
        markers = a_markers()
        moved = dataclasses.replace(markers, turn_closing="<<END>>")

        assert markers.turn("user", "hello").endswith(markers.turn_closing)
        assert moved.turn("user", "hello").endswith("<<END>>")

    def test_a_shorter_reply_opening_cannot_shadow_a_longer_one(self) -> None:
        """Built rather than derived, because the incumbent is safe by luck.

        `opening_of` matches on a suffix. Here the plain opening IS a suffix of
        the thinking one, so a first-match-wins reader would splice a thinking
        continuation with the plain opening and break the prefix the two calls
        exist to keep. Longest-first makes that unreachable.
        """
        markers = markers_from(
            {
                "turn_opening": "<turn $role>",
                "turn_closing": "</turn>",
                "reply_opening": "<turn assistant>",
                "reply_opening_thinking": "<thinking><turn assistant>",
                "thinking_close": None,
            }
        )

        assert markers.opening_of("..." + markers.reply_opening_thinking) == (
            markers.reply_opening_thinking
        )
        assert markers.opening_of("..." + markers.reply_opening) == markers.reply_opening


# --- The label call: the model reads the article and points at it --------------------
#
# The oracle for this row is one sentence: no field of the label call's schema accepts a
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


def a_reply(**named: object) -> ParsedLabelReply:
    """A reply with every required field filled, so a case reads as its point."""
    body: dict[str, object] = {
        "labels": [],
        "proposed": [],
        "named_mentions": [],
    }
    body.update(named)
    return parse_label(json.dumps(body))


def a_group(
    name: str, *surfaces: tuple[str, str], kind: str = "entity"
) -> dict[str, object]:
    """One named thing and the sentences it is named in, as `(sentence_id, surface)`."""
    return {
        "mentions": [{"sentence_id": where, "surface": words} for where, words in surfaces],
        "kind": kind,
        "name": name,
    }


def a_label(element_id: str, **named: object) -> dict[str, object]:
    body: dict[str, object] = {
        "element_id": element_id,
        "measure": "",
        "entity": "",
    }
    body.update(named)
    return body


@pytest.fixture
def dense(article_ok: Article) -> Article:
    return article_ok.model_copy(update={"text": DENSE_TEXT})


class TestTheOracle:
    def test_no_field_of_the_label_reply_accepts_a_number_a_span_or_an_offset(self) -> None:
        """The row's whole point. A span and an offset are integers, so this covers both."""
        assert schema_types(label_schema()) & {"integer", "number"} == set()

    def test_an_unknown_element_id_drops_that_label_and_keeps_its_siblings(
        self, dense: Article
    ) -> None:
        """The other half of the oracle. A rejection costs one label, never the article."""
        table = a_table(dense)
        real = table.elements[0].element_id
        reply = a_reply(
            labels=[
                a_label("quantity-9000-9010", measure="a fact no pass found"),
                a_label(real, measure="output"),
            ]
        )

        labelled = apply_labels(table, reply, label_source="m")

        by_id = {element.element_id: element for element in labelled.elements}
        assert by_id[real].measure == "output"
        assert len(labelled.elements) == len(table.elements)
        assert all(element.measure != "a fact no pass found" for element in labelled.elements)


class TestTheLabelCallShape:
    def test_a_mention_is_written_before_the_name_that_groups_it(self) -> None:
        """Field order is decode order: the anchor first, the judgement last."""
        group = list(label_schema()["$defs"]["NamedMentions"]["properties"])
        assert group == ["mentions", "kind", "name"]

    def test_what_was_found_decodes_before_what_it_means(self) -> None:
        """Field order is decode order: the anchor first, the judgement last."""
        label = list(label_schema()["$defs"]["ElementLabel"]["properties"])
        assert label[0] == "element_id"
        assert label == ["element_id", "measure", "entity"]

    def test_a_reply_missing_a_field_is_a_shape_failure(self) -> None:
        with pytest.raises(ValidationError):
            parse_label('{"labels":[],"proposed":[]}')


class TestTheLabelCallPrompting:
    @pytest.mark.parametrize(
        "text",
        [
            "Mira Sen may chair\nthe review if funded. Arun Sen declined.",
            '  A literal "\\n" and [s99] stay data.\r\nThe next sentence.  ',
            "Line controls:\r\n\t\v\f\x1c\x1d\x1e\x85\u2028\u2029 remain in this sentence.",
        ],
    )
    def test_addressed_lines_reversibly_preserve_every_original_sentence(self, text: str) -> None:
        lines = numbered_sentences(text).splitlines()
        spans = sentence_spans(text)

        assert len(lines) == len(spans)
        decoded = []
        for index, (line, (start, end)) in enumerate(zip(lines, spans, strict=True)):
            address = f"[s{index}] "
            assert line.startswith(address)
            sentence = json.loads(line.removeprefix(address))
            assert sentence == text[start:end]
            decoded.append(sentence)
        assert "".join(decoded) == text

    @pytest.mark.parametrize(
        "marker",
        ["<|im_start|>", "<start_of_turn>", "<\uff5cUser\uff5c>", FENCE_OPEN, FENCE_CLOSE],
    )
    def test_escaped_source_stays_inside_the_sanitizer_boundary(
        self, article_ok: Article, marker: str
    ) -> None:
        text = f'An actor wrote {marker} and a literal \\u003c marker.\nIt is data.'
        article = article_ok.model_copy(update={"text": text})
        turn = label_user_turn(article, a_table(article))

        assert turn.count(FENCE_OPEN) == turn.count(FENCE_CLOSE) == 3
        if marker not in (FENCE_OPEN, FENCE_CLOSE):
            assert marker not in turn
        assert r"\\u003c" in turn
        assert article.text == text

    def test_the_menu_addresses_every_candidate_by_its_own_id(self, dense: Article) -> None:
        table = a_table(dense)
        menu = candidate_menu(table)
        assert all(f"[{element.element_id}]" in menu for element in table.elements)

    def test_the_request_hands_the_decoder_the_reply_shape(self, dense: Article) -> None:
        entry = configured()
        payload = build_label_request(
            dense,
            a_table(dense),
            model_id="m",
            server=entry.server,
            sampling=entry.sampling,
            markers=a_markers(),
        )
        markers = a_markers()
        assert payload["json_schema"] == label_request_schema(dense, a_table(dense))
        assert payload["prompt"].startswith(markers.turn("system", label_system_prompt()))
        assert "4,200 megawatt hours" in payload["prompt"]
        assert payload["prompt"].endswith(markers.opening())


class TestLabelling:
    def test_a_label_writes_the_cells_it_can_anchor(self, article_ok: Article) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        first = table.elements[0].element_id
        reply = a_reply(
            labels=[
                a_label(first, measure="output")
            ]
        )

        element = apply_labels(table, reply, label_source="qwen").elements[0]

        assert element.measure == "output"
        assert all(value is None for value in (
            element.dimension, element.attribution, element.hedge, element.time, element.salience
        ))
        assert element.label_source == "qwen"
        assert element.ledger_version == LABEL_PASS_VERSION

    def test_an_empty_label_records_no_judgement(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        reply = a_reply(labels=[a_label(table.elements[0].element_id)])
        assert apply_labels(table, reply, label_source="m") == table

    def test_dates_keep_their_source_values_without_quantity_judgements(
        self, article_ok: Article
    ) -> None:
        table = a_table(article_ok, DENSE_TEXT)
        date = next(one for one in table.elements if one.kind is ElementKind.DATE)
        reply = a_reply(labels=[a_label(date.element_id, measure="not a quantity")])
        assert apply_labels(table, reply, label_source="m") == table

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
        reply = a_reply(proposed=[{"surface": "5,000 megawatt hours"}])

        recovered = anchored(
            table, DENSE_TEXT, reply, config=ElementsConfig(max_per_article=2), label_source="m"
        )

        landed = [one for one in recovered.elements if one.extractor is Extractor.MODEL]
        assert [one.value for one in landed] == ["5000"]
        assert [one.unit for one in landed] == ["megawatt"]

    def test_a_surface_the_article_never_wrote_is_refused(self) -> None:
        """A figure the model typed rather than found has nowhere to anchor."""
        reply = a_reply(proposed=[{"surface": "9,900 megawatt hours"}])
        assert proposed_quantities(DENSE_TEXT, reply) == []

    def test_a_surface_that_occurs_twice_in_its_sentence_is_refused(self) -> None:
        """Mis-pointing is the failure no span check can see, so ambiguity is a rejection."""
        text = "It shipped 500 tonnes. Later it shipped 500 tonnes more."
        reply = a_reply(proposed=[{"surface": "500 tonnes"}])
        assert proposed_quantities(text, reply) == []

    def test_a_surface_holding_two_figures_is_refused(self) -> None:
        text = "Output moved between 1,100 tonnes and 1,900 tonnes."
        reply = a_reply(
            proposed=[{"surface": "1,100 tonnes and 1,900 tonnes"}]
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
        reply = a_reply(proposed=[{"surface": "about a third"}])
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


# --- Source-backed entity and place mentions --------------------------------
#
# The oracle for this row is two sentences. For every surviving element of every
# kind, `article.text[span_start:span_end] == span_excerpt`. And no element's
# drawn label is ever its Tier 2 `name` - the label is one of the mentions that
# anchored.

#: One item carrying both model-pointed kinds. The name a page must never
#: draw - "Vestas Wind Systems A/S" - appears nowhere in it, which is decision
#: 1's case: the canonical name may be written nowhere verbatim.
POINTED_TEXT = (
    "Vestas said its plants ran at full output through March. "
    "Vestas expects the same in April, an official in Aarhus said. "
    "The company has not published the figures."
)

#: The named mentions the producer reads for that item.
POINTED_REPLY: dict[str, object] = {
    "named_mentions": [
        a_group("Vestas Wind Systems A/S", ("s0", "Vestas"), ("s1", "Vestas")),
        a_group("Aarhus", ("s1", "Aarhus"), kind="place"),
    ],
}


def kinds_of(table: ElementTable) -> set[ElementKind]:
    return {element.kind for element in table.elements}


class TestTheMentionAnchoringOracle:
    def test_a_drawn_label_is_one_of_the_mentions_that_anchored(self) -> None:
        """The mention draws and the name never does.

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


class TestMentions:
    @pytest.mark.parametrize(
        ("surface", "expected"),
        [("Coast", []), ("Coast adults", ["Coast adults"])],
    )
    def test_a_qualifying_source_phrase_must_still_match_exactly_once(
        self, surface: str, expected: list[str]
    ) -> None:
        text = "Coast adults reported 12 percent; Coast parents reported 20 percent."
        groups = mention_elements(
            text,
            a_reply(named_mentions=[{
                "mentions": [{"surface": surface}], "kind": "place", "name": "Coast"
            }]).named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert [one.span_excerpt for group in groups for one in group.elements] == expected

    def test_a_name_the_item_never_wrote_still_anchors_its_mentions(self) -> None:
        """Decision 1. The name is a grouping key and is never searched for."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(**POINTED_REPLY).named_mentions,
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
            a_reply(named_mentions=[a_group("Vestas", ("s0", "Vestas"))]).named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_a_surface_from_another_sentence_is_refused(self) -> None:
        """Only the named sentence is searched, so a real word in the wrong place misses."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(named_mentions=[a_group("Aarhus", ("s0", "Aarhus"))]).named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_one_refused_mention_leaves_its_siblings_standing(self) -> None:
        """Decision 5: a rejection is per element, never per article."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(
                named_mentions=[
                    a_group("Vestas", ("s0", "Vestas"), ("s9", "Vestas"), ("s1", "Vestas"))
                ]
            ).named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert len(groups[0].elements) == 2

    def test_a_whitespace_surface_is_refused_rather_than_cutting_nothing(self) -> None:
        """A zero-width span is a payload the contract will not hold."""
        groups = mention_elements(
            POINTED_TEXT,
            a_reply(named_mentions=[a_group("Vestas", ("s0", " "))]).named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert groups == []

    def test_a_tracked_name_groups_under_the_slug_and_an_unknown_one_mints_none(self) -> None:
        """The alias ledger is separate work, so this pass never invents a group."""
        reply = a_reply(**POINTED_REPLY)

        tracked = mention_elements(
            POINTED_TEXT,
            reply.named_mentions,
            label_source="m",
            entity_slugs={"vestas wind systems a/s": "vestas"},
        )
        unknown = mention_elements(
            POINTED_TEXT,
            reply.named_mentions,
            label_source="m",
            entity_slugs={},
        )

        assert all(one.entity == "vestas" for one in tracked[0].elements)
        assert all(one.entity is None for one in unknown[0].elements)

    def test_a_mention_is_tier_one_and_says_who_judged_the_rest(self) -> None:
        """Only an assigned identity records judgment provenance."""
        element = mention_elements(
            POINTED_TEXT,
            a_reply(named_mentions=[a_group("Aarhus", ("s1", "Aarhus"), kind="place")]).named_mentions,
            label_source="qwen",
            entity_slugs={"aarhus": "aarhus"},
        )[0].elements[0]

        assert element.kind is ElementKind.PLACE
        assert element.extractor is Extractor.MODEL
        assert element.value is None and element.unit is None
        assert element.entity == "aarhus" and element.salience is None
        assert element.label_source == "qwen"
        assert element.ledger_version == LABEL_PASS_VERSION


class TestMergingMentions:
    def test_two_groups_claiming_one_address_keep_one_element(self, article_ok: Article) -> None:
        """A kind and a span identify one fact, so the second citation adds nothing."""
        table = a_table(article_ok, POINTED_TEXT)
        reply = a_reply(
            named_mentions=[
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

        for kind in (ElementKind.ENTITY, ElementKind.PLACE):
            kept = len([one for one in whole.elements if one.kind is kind])
            assert whole.candidates_found[kind] >= kept > 0


def test_malformed_retired_label_evidence_never_reaches_a_continuation(
    article_ok: Article, tmp_path: Path,
) -> None:
    raw = a_reply().model_dump() | {
        "quotes": [], "claims": "not a source range",
        "keyphrases": [], "lede_sentence_ids": [],
    }
    body = json.dumps({"content": json.dumps(raw), "stop": True}).encode()
    with RecordedEndpoint(200, body) as server:
        result = two_calls_one_item(
            article_ok, config.load(CONFIG_DIR), date="2026-11-11",
            endpoint=server.endpoint,
            capture_root=tmp_path / "captures", render_root=tmp_path / "assets",
        )
    assert len(server.sent) == 1
    assert result.summary.status is not SummaryStatus.OK
    assert result.answer_reply is None and result.decision is None


def test_a_recorded_label_reply_labels_the_table_over_a_loopback_socket(
    article_ok: Article,
) -> None:
    """The row end to end, with no network and nothing mocked.

    The reply is played back by a real HTTP server on loopback and read through
    the transport every stage uses. The envelope is a llama-server envelope; the
    content is written by hand rather than captured, because no stage dispatches
    the label call yet - the call that turns this table into a page is a later row. It
    carries no `usage` block for the same reason: a token count nobody measured
    is not a token count (Guardrail #10), and the transport reads a missing one as
    zero.
    """
    table = element_table(article_ok, config=ElementsConfig())
    entry = configured()
    payload = build_label_request(
        article_ok,
        table,
        model_id="m",
        server=entry.server,
        sampling=entry.sampling,
        markers=a_markers(),
    )
    body = (LABEL_REPLIES / "labelled.json").read_bytes()

    with RecordedEndpoint(200, body) as server:
        completion = post(payload, endpoint=server.endpoint, timeout=10.0)

    reply = parse_label(completion.content)
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
    }, "the reply's one place is 'Denmark', which the item never names"
    assert [
        one.span_excerpt for one in labelled.elements if one.kind is ElementKind.ENTITY
    ] == ["Example Lab"]
    assert labelled.span_drift(article_ok.text or "") is None
    assert sentence_id(labelled.elements[0].sentence_index) in candidate_menu(labelled)


# --- The summarize-and-plan call: the summary and the plan, over the prefix the label call already paid for
#
# Two oracles, because the two halves fail for different reasons. The floor is
# that the summarize-and-plan call's prompt opens with the label call's, byte for byte - so the article
# prefills once, or the prompt was built wrong. The target is whether the label call's
# own generated reply caches too, and that is a number off a running server
# rather than an assertion: `docs/architecture/summarize/prompt.md` records it.

def summarize_and_plan_payload(article: Article, reply: str = "{}") -> dict[str, Any]:
    return build_summarize_and_plan_request(
        label_payload(article),
        reply,
        a_table(article),
        markers=a_markers(),
    )


def build_label_with_derived_budget(
    article: Article, *, sampling: dict[str, Any] | None = None
) -> dict[str, Any]:
    return build_label_request(
        article,
        a_table(article),
        model_id="m",
        server=a_server(),
        sampling={} if sampling is None else sampling,
        markers=a_markers(),
    )


class TestTheSummarizeAndPlanOracle:
    def test_current_plan_collects_references_without_losing_confidence_or_prose_checks(
        self, article_ok: Article
    ) -> None:
        text = (
            "Unit A reported 10 units. Unit B reported 20 units. "
            "Unit C reported 30 units. The sample contained 99 units."
        )
        table = anchored(
            a_table(article_ok, text), text,
            a_reply(named_mentions=[
                a_group("Unit A", ("s0", "Unit A")),
                a_group("Unit B", ("s1", "Unit B")),
                a_group("Unit C", ("s2", "Unit C")),
            ]),
            config=ElementsConfig(), label_source="test",
        )
        quantities = [
            one.element_id for one in table.elements if one.kind is ElementKind.QUANTITY
        ]
        categories = [one.element_id for one in table.elements if one.kind is ElementKind.ENTITY]
        body = json.loads(declining_reply())
        body["visual"].pop("element_ids")
        body["visual"].update(
            decision="visual", purpose="comparison", type="bar",
            title="Reported output", caption=None, why="Compare reported output.",
            labels=categories, annotations=[quantities[0]], confidence=0.8,
        )
        body["visual"]["encodings"].update(category=categories, quantity=quantities[:3])
        parsed = parse_summarize_and_plan(json.dumps(body))
        assert parsed.visual is not None
        assert parsed.visual.confidence == 0.8
        assert set(parsed.visual.element_ids) == set(categories + quantities[:3])
        assert validate_plan(parsed.visual, table, visuals=VisualsConfig()) == []
        assert compile_chart(parsed.visual, table, visuals=VisualsConfig()).data.type is VisualType.BAR
        assert "element_ids" not in summarize_and_plan_schema()["$defs"]["VisualPlanDraft"][
            "properties"
        ]
        body["visual"]["caption"] = "The sample contained 99 units."
        parsed = parse_summarize_and_plan(json.dumps(body))
        assert parsed.visual is not None
        assert ValidatorCheck.NUMERALS_MATCHED in {
            rejection.check
            for rejection in validate_plan(parsed.visual, table, visuals=VisualsConfig())
        }

    def test_the_menu_preserves_finalized_source_cells_and_existing_judgements(
        self, article_ok: Article
    ) -> None:
        initial = a_table(article_ok, POINTED_TEXT, cap=2)
        finalized = anchored(
            initial, POINTED_TEXT, a_reply(**POINTED_REPLY),
            config=ElementsConfig(max_per_article=2), label_source="m",
            entity_slugs={"vestas wind systems a/s": "vestas"},
        )
        before = finalized.model_dump(mode="json")
        menu = planning_menu(finalized)
        data = json.loads(menu.removeprefix(FENCE_OPEN + "\n").removesuffix("\n" + FENCE_CLOSE))
        assert data["columns"] == [
            "element_id", "kind", "span_excerpt", "value", "unit", "sentence_id"
        ]
        assert data["rows"] == [
            [
                (element.model_dump(mode="json") | {"sentence_id": sentence_id(element.sentence_index)})[
                    name
                ]
                for name in PLANNING_COLUMNS
            ]
            for element in finalized.elements
        ]
        assert data["labels"] == {
            element.element_id: {
                name: element.model_dump(mode="json")[name]
                for name in PLANNING_JUDGEMENTS
                if getattr(element, name) is not None
            }
            for element in finalized.elements
            if any(getattr(element, name) is not None for name in PLANNING_JUDGEMENTS)
        }
        assert finalized.model_dump(mode="json") == before

    def test_an_empty_table_admits_only_empty_reference_lists_and_a_null_whole(
        self, article_ok: Article
    ) -> None:
        table = ElementTable.model_validate(a_table(article_ok).model_dump() | {"elements": []})
        native = summarize_and_plan_schema()
        schema = summarize_and_plan_schema(table=table)
        plan = schema["$defs"]["VisualPlanDraft"]["properties"]
        arrays = [
            *schema["$defs"]["PlanEncodings"]["properties"].values(),
            *(plan[name] for name in ("labels", "annotations")),
        ]
        assert all(field["maxItems"] == 0 for field in arrays)
        assert plan["declared_whole_element_id"]["type"] == "null"
        assert "anyOf" not in plan["declared_whole_element_id"]
        assert all(field["items"].get("enum") != [] for field in arrays)
        assert summarize_and_plan_schema() == native
        assert list(schema["properties"]) == ["summary", "visual"]

    def test_the_actual_planning_request_exposes_every_finalized_element(
        self, article_ok: Article
    ) -> None:
        """Removing the anchored table loses the numeric categories added by labelling."""
        text = "Unit A approved 10 units. Unit B approved 20 units. Unit C approved 30 units."
        article = Article.model_validate(
            article_ok.model_dump(mode="json")
            | {
                "title": "Three units report approvals",
                "text": text,
                "word_count": len(text.split()),
                "source_word_count": len(text.split()),
                "token_count": approx_tokens(len(text.split())),
            }
        )
        settings = config.load(CONFIG_DIR)
        reply = a_reply(
            named_mentions=[
                a_group("Unit A", ("s0", "Unit A")),
                a_group("Unit B", ("s1", "Unit B")),
                a_group("Unit C", ("s2", "Unit C")),
            ],
        )
        initial = element_table(article, config=settings.app.elements)
        finalized = anchored(
            initial,
            text,
            reply,
            config=settings.app.elements,
            label_source=settings.models.summarizer.id,
        )
        decline: dict[str, Any] = {
            "decision": "none",
            "purpose": None,
            "type": None,
            "declared_whole_element_id": None,
            "encodings": {role.value: [] for role in EncodingRole},
            "labels": [],
            "annotations": [],
            "why": "The approvals are already clear in prose.",
            "title": None,
            "caption": None,
            "confidence": 0.5,
        }
        answer = {
            "summary": {
                "title": "Three units report approvals",
                "summary": "Unit A approved ten units, Unit B twenty and Unit C thirty.",
            },
            "visual": decline,
        }
        bodies = [
            json.dumps({"content": content, "stop": True}).encode("utf-8")
            for content in (reply.model_dump_json(), json.dumps(answer))
        ]
        with RecordedEndpoint(200, *bodies) as server:
            two_calls_one_item(
                article, settings, date="2026-11-10", endpoint=server.endpoint
            )
        assert len(server.sent) == 2
        request = server.sent[1]
        assert "visual" in request["json_schema"]["properties"]
        ids = [element.element_id for element in finalized.elements]
        assert any(
            element.kind is ElementKind.ENTITY and element.element_id not in {
                candidate.element_id for candidate in initial.elements
            }
            for element in finalized.elements
        )
        assert all(element_id in request["prompt"] for element_id in ids)
        schema = request["json_schema"]
        plan = schema["$defs"]["VisualPlanDraft"]["properties"]
        references = [
            *(channel["items"] for channel in schema["$defs"]["PlanEncodings"]["properties"].values()),
            *(plan[name]["items"] for name in ("labels", "annotations")),
            plan["declared_whole_element_id"]["anyOf"][0],
        ]
        assert all(reference["enum"] == ids for reference in references)
        assert all("entity-999-999" not in reference["enum"] for reference in references)

    def test_the_summary_call_opens_with_the_label_prompt_and_the_reply_it_returned(
        self, dense: Article
    ) -> None:
        """The whole of row #3c, as one string comparison and no server.

        A prefix cache reuses the longest common prefix of the tokenised prompt.
        Since the bytes are ours, the summarize-and-plan call's prompt is the label call's extended rather
        than re-rendered, so what the cache can reach is everything the label call read
        AND everything it wrote. Asserted on the bytes rather than on a
        `prefill_ms` ratio, which would confound cache reuse with how long the
        new turn is and read as partial success when the prompt was built wrong.
        """
        first = label_payload(dense)
        reply = '{"labels": []}'

        assert summarize_and_plan_payload(dense, reply)["prompt"].startswith(first["prompt"] + reply)


class TestTheInstructionsSitInFrontOfTheArticle:
    """Row #3e. What can be shared is shared, and what cannot is three lines.

    The system turn is the same bytes on every item, so the server prefills it
    once a shard. The turn behind the article is read again on every item for
    ever, because the article in front of it differs and a prefix cache cannot
    reach past it - so every token left there is a token paid per item.
    """


    def test_the_system_turn_is_the_same_bytes_on_every_item(
        self, dense: Article, article_ok: Article
    ) -> None:
        """The whole basis of the prefix cache, and the one way this row could
        have cost more than it saved.

        `-np` on the summarize entry is 1, so the server holds one
        cache slot. A system turn carrying anything the article picked would
        evict the article on every alternation between two variants, and the
        article is thousands of tokens where this row moved hundreds.
        """
        ask = config.load(CONFIG_DIR).app.summarize
        entry = configured()
        markers = a_markers()
        opening = markers.turn("system", label_system_prompt(ask))

        for article in (dense, article_ok):
            payload = build_label_request(
                article,
                a_table(article),
                model_id="m",
                server=entry.server,
                sampling=entry.sampling,
                markers=a_markers(),
                prompt_config=ask,
            )
            assert payload["prompt"].startswith(opening)


def declining_reply(**changed: object) -> str:
    """A complete in-memory reply, with one optional contradiction in its decline."""
    return json.dumps({
        "summary": {
            "title": "Reservoir repairs remain under review",
            "summary": (
                "The council is reviewing a repair proposal. The report names no comparable "
                "measures and leaves the schedule and scope of the work unresolved."
            ),
        },
        "visual": {
            "decision": "none",
            "purpose": None,
            "type": None,
            "declared_whole_element_id": None,
            "encodings": {role.value: [] for role in EncodingRole},
            "element_ids": [],
            "labels": [],
            "annotations": [],
            "why": "The source supports no useful visual.",
            "title": None,
            "caption": None,
            "confidence": 0.0,
            **changed,
        },
    })


@pytest.mark.parametrize(
    ("changed", "field", "rule"),
    (
        ({"title": "model-only words"}, "title", "visual_plan_decline_empty"),
        ({"title": "model-only words" * TITLE_MAX_LENGTH}, "visual.title", "string_too_long"),
        ({"confidence": "model-only words"}, "visual.confidence", "float_parsing"),
        ({"model-only words": "model-only words"}, "visual", "extra_forbidden"),
    ),
)
def test_shape_diagnostics_keep_native_fields_and_rules_without_reply_text(
    changed: dict[str, object], field: str, rule: str,
) -> None:
    with pytest.raises(ValidationError) as caught:
        parse_summarize_and_plan(declining_reply(**changed))

    cells = _shape_cells(caught.value)

    assert cells["failed_field"] == field
    assert cells["failed_rule"] == rule
    assert field in cells["detail"] and rule in cells["detail"]
    assert "model-only words" not in repr(cells)
    assert "input_value" not in cells["detail"]
    assert "\n" not in cells["detail"]


def test_an_unstructured_shape_failure_does_not_copy_its_input() -> None:
    cells = _shape_cells(ValueError("model-only words"))
    assert cells == {"detail": "ValueError", "failed_field": None, "failed_rule": None}


class TestTheSecondRequest:
    def test_the_second_call_decodes_nothing_the_first_call_settled(self, dense: Article) -> None:
        """Determinism is set in one place, and the summarize-and-plan call does not become a second one."""
        first = build_label_with_derived_budget(
            dense, sampling={"temperature": 0.25, "top_p": 0.8, "seed": 42}
        )
        second = build_summarize_and_plan_request(
            first, "{}", a_table(dense), markers=a_markers()
        )

        assert [
            second[key] for key in ("temperature", "top_p", "seed", "stream", "cache_prompt")
        ] == [first[key] for key in ("temperature", "top_p", "seed", "stream", "cache_prompt")]
        assert second["prompt"].endswith(
            a_markers().opening_of(first["prompt"])
        ), "the reply opening is read off the label call's prompt, so the two cannot disagree"

    @pytest.mark.parametrize("plan", [True, False])
    @pytest.mark.parametrize(
        "sampling",
        [pytest.param({}, id="no-limit-named"), pytest.param({"max_tokens": 4096}, id="limit-named")],
    )
    def test_the_second_call_runs_to_the_model_files_limit_with_or_without_a_plan(
        self, dense: Article, sampling: dict[str, Any], plan: bool
    ) -> None:
        """One limit, the one the window gate reserves, whether or not a plan is asked for.

        Where the model file names none, the first body carries the label call's own
        derived limit; a second body that kept it would cut every plan there.
        """
        first = build_label_with_derived_budget(dense, sampling=sampling)

        second = build_summarize_and_plan_request(
            first, "{}", a_table(dense), markers=a_markers(), plan=plan
        )

        assert response_tokens(second) == response_limit(sampling)


class TestARepliedCutByTheBudget:
    def test_a_reply_cut_in_the_plan_still_carries_its_summary(self) -> None:
        """E5. The bytes come back on an ordinary 200 and used to be thrown away unread."""
        body = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "cut-in-the-plan.json"))
        cut = Completion(
            content=body["choices"][0]["message"]["content"], finish_reason="length"
        )

        recovered = recovered_completion(cut)

        assert recovered is not None
        assert recovered.finish_reason == "stop"
        assert json.loads(recovered.content)["title"].startswith("Example Lab")

    def test_a_reply_cut_inside_the_summary_recovers_nothing(self) -> None:
        """The one case where there is genuinely nothing to publish."""
        body = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "cut-in-the-plan.json"))
        content = body["choices"][0]["message"]["content"]
        early = content[: content.index(', "summary": ')]

        assert recovered_completion(Completion(content=early, finish_reason="length")) is None

    def test_a_reply_that_finished_is_recast_and_never_repaired(self) -> None:
        """One path for both replies, and the repair fires only where there was a cut.

        A reply that ran to the end carries the same closed summary object in the
        same place, so it takes the same recasting - and `finish_reason` is left
        exactly as the server reported it, because there is nothing to repair. A
        second path for the ordinary reply is what left the repair out of the
        live one until 2026-09-15.
        """
        body = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "summary-and-plan.json"))
        content = body["choices"][0]["message"]["content"]

        recast = recovered_completion(Completion(content=content, finish_reason="stop"))
        exotic = recovered_completion(Completion(content=content, finish_reason="eos"))

        assert recast is not None and exotic is not None
        assert recast.finish_reason == "stop"
        assert exotic.finish_reason == "eos", "a reason this call did not repair is carried"
        assert "visual" not in json.loads(recast.content), "the plan half is not the summary"

    def test_a_recovered_reply_publishes_through_every_check_the_summarizer_runs(
        self, article_ok: Article
    ) -> None:
        """The recovery hands back a single-call reply, so nothing downstream is relaxed.

        The address check reads the recovered words the same way it reads any
        others. Recovery stops an item being thrown away unread; it decides
        nothing about whether it may publish.
        """
        body = json.loads(read_text(SUMMARIZE_AND_PLAN_REPLIES / "cut-in-the-plan.json"))
        cut = Completion(
            content=body["choices"][0]["message"]["content"], finish_reason="length"
        )
        recovered = recovered_completion(cut)
        assert recovered is not None

        summary = summarize.to_summary(
            article_ok,
            recovered,
            model_id="m",
            generated_at="2026-09-10T00:00:00Z",
        )

        assert summary.status is SummaryStatus.OK
        assert summary.summary and "34 percent" in summary.summary


def test_a_recorded_summarize_and_plan_reply_parses_over_a_loopback_socket(
    article_ok: Article,
) -> None:
    """The row end to end, with no network and nothing mocked.

    The reply is played back by a real HTTP server on loopback and read through
    the transport every stage uses. The envelope is a llama-server envelope; the
    content is written by hand rather than captured, because no stage dispatches
    the summarize-and-plan call yet - the gate in front of it and the picture it leads to are later
    rows. It carries no `usage` block for the same reason: a token count nobody
    measured is not a token count (Guardrail #10).

    The plan's own `element_ids` are checked against the article's table here,
    which is the point of decision 3 - the plan sources the article, and the
    summary above it in the same reply only conditions it. Whether that table
    holds every id is the validator's rule and a later row's.
    """
    payload = summarize_and_plan_payload(article_ok, read_text(FIXTURES_DIR / "completions" / "label" / "labelled.json"))
    body = (SUMMARIZE_AND_PLAN_REPLIES / "summary-and-plan.json").read_bytes()

    with RecordedEndpoint(200, body) as server:
        completion = post(payload, endpoint=server.endpoint, timeout=10.0)

    reply = parse_summarize_and_plan(completion.content)
    table = element_table(article_ok, config=ElementsConfig())
    labelled = anchored(
        table,
        article_ok.text or "",
        parse_label(
            json.loads(read_text(FIXTURES_DIR / "completions" / "label" / "labelled.json"))[
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
