"""Which native references can this label request select, and which legacy replies remain safe?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError
from support.models import a_markers, a_server

from idhazh.classify import calls
from idhazh.contracts.article import Article
from idhazh.contracts.base import canonical_json, derive_url_key
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.visual import widest_json_characters
from idhazh.elements import SpanDriftError, element_table


def article_with_text(text: str) -> Article:
    url = "https://example.test/article"
    return Article.model_validate(
        {
            "item_id": "test-01",
            "url_key": derive_url_key(url),
            "source_url": url,
            "canonical_url": url,
            "source_id": "test",
            "tier": 1,
            "vertical": "test",
            "rank_score": 0,
            "text": text,
            "word_count": len(text.split()),
            "fetched_at": "2026-11-11T00:00:00Z",
            "status": "ok" if text else "extract_failed",
            "failure_detail": None if text else "Empty source.",
            "extractor_version": "test",
            "sanitizer_version": "test",
        }
    )


def request(article: Article, table: ElementTable, **sampling: Any) -> dict[str, Any]:
    return calls.build_label_request(
        article,
        table,
        model_id="test",
        server=a_server(),
        sampling=sampling,
        markers=a_markers(),
    )


def empty_reply(**fields: object) -> dict[str, object]:
    return {
        "labels": [],
        "proposed": [],
        "entity_mentions": [],
        "place_mentions": [],
    } | fields


def test_request_only_offers_printed_references() -> None:
    article = article_with_text(
        "Unit A reported 10 units in 2026. Unit B reported 20 units and wrote [s99].",
    )
    table = element_table(article, config=ElementsConfig())
    schema = request(article, table)["json_schema"]
    labels = schema["$defs"]["ElementLabel"]["properties"]
    candidates = [one.element_id for one in table.elements]
    dates = [one.element_id for one in table.elements if one.kind is ElementKind.DATE]
    sentences = [
        calls.sentence_id(index) for index, _ in enumerate(calls.sentence_spans(article.text or ""))
    ]

    assert labels["element_id"].get("enum") == candidates, (
        "the label decoder must choose only candidates printed in this request"
    )
    assert labels["time_element_id"]["enum"] == [*dates, ""]
    assert schema["$defs"]["Citation"]["properties"]["sentence_id"]["enum"] == sentences
    assert all(f"[{address}]" in calls.candidate_menu(table) for address in candidates)
    assert all(
        f"[{address}] " in calls.numbered_sentences(article.text or "") for address in sentences
    )
    assert "s99" not in sentences
    assert not set(candidates) & set(sentences)
    assert any(one.element_id not in dates for one in table.elements)


@pytest.mark.parametrize("text", ["", " \t\r\n", "Nothing numeric."])
def test_empty_pools_need_no_invented_address(text: str) -> None:
    article = article_with_text(text)
    table = element_table(article, config=ElementsConfig())
    schema = calls.label_request_schema(article, table)
    assert schema["properties"]["labels"]["maxItems"] == 0
    assert schema["$defs"]["ElementLabel"]["properties"]["time_element_id"]["enum"] == [""]
    assert "enum" not in schema["$defs"]["ElementLabel"]["properties"]["element_id"]
    if not text.strip():
        assert schema["$defs"]["Citation"]["properties"]["sentence_id"]["enum"] == ["s0"]
    assert calls.parse_label(json.dumps(empty_reply())).model_dump() == empty_reply()
    assert all(not field.get("minItems", 0) for field in schema["properties"].values())


def test_projection_preserves_native_shape_and_request_budget() -> None:
    native = calls.label_schema()
    before = canonical_json(native)
    width = widest_json_characters(native)
    budget = calls.label_budget_tokens()
    article = article_with_text("Unit A counted 10 units in 2026. Unit B responded.")
    table = element_table(article, config=ElementsConfig())
    payload = request(article, table)
    schema = payload["json_schema"]
    other = article_with_text("Another unit responded.")
    calls.label_request_schema(other, element_table(other, config=ElementsConfig()))

    assert canonical_json(calls.label_schema()) == before
    assert widest_json_characters(calls.label_schema()) == width
    assert calls.label_budget_tokens() == budget == payload["n_predict"]
    capped = request(article, table, max_tokens=8192)
    assert capped["max_tokens"] == 8192
    assert "n_predict" not in capped
    assert list(schema["properties"]) == list(native["properties"])
    assert schema["required"] == native["required"]
    for name in ("ElementLabel", "Citation"):
        expected = native["$defs"][name]
        projected = schema["$defs"][name]
        assert projected["required"] == expected["required"]
        assert list(projected["properties"]) == list(expected["properties"])
        for field, leaf in projected["properties"].items():
            if field in {"element_id", "time_element_id", "sentence_id"}:
                assert {key: value for key, value in leaf.items() if key != "enum"} == expected[
                    "properties"
                ][field]
            else:
                assert leaf == expected["properties"][field]
    assert schema["required"] == ["labels", "proposed", "entity_mentions", "place_mentions"]


def test_selected_mentions_still_parse_and_anchor_verbatim() -> None:
    text = "Unit A may chair\nthe review if funded. Unit B opposed it."
    article = article_with_text(text)
    table = element_table(article, config=ElementsConfig())
    reply = calls.parse_label(
        json.dumps(
            empty_reply(
                entity_mentions=[
                    {
                        "mentions": [{"sentence_id": "s0", "surface": "Unit A"}],
                        "name": "Unit A",
                        "salience": "primary",
                    }
                ],
            )
        )
    )
    whole = calls.anchored(table, text, reply, config=ElementsConfig(), label_source="test")
    assert whole.span_drift(text) is None
    assert whole.source_text_hash == table.source_text_hash
    assert [one.span_excerpt for one in whole.elements if one.kind is ElementKind.ENTITY] == [
        "Unit A"
    ]


LEGACY_RANGE: dict[str, object] = {
    "sentence_start_id": "s0", "sentence_end_id": "s0", "speaker": "",
    "attribution": "unattributed", "hedge": False,
}


def legacy_observations(**fields: object) -> dict[str, object]:
    return {
        "quotes": [],
        "claims": [LEGACY_RANGE],
        "keyphrases": ["old evidence"],
        "lede_sentence_ids": ["s0"],
    } | fields


def test_legacy_observations_are_validated_then_discarded_not_anchored() -> None:
    text = "Unit A counted 10 units."
    article = article_with_text(text)
    table = element_table(article, config=ElementsConfig())
    reply = calls.parse_label(json.dumps(empty_reply(**legacy_observations())))

    assert reply.model_dump() == empty_reply()
    whole = calls.anchored(table, text, reply, config=ElementsConfig(), label_source="test")
    assert whole.elements == table.elements


@pytest.mark.parametrize("retired", [
    {"quotes": []},
    legacy_observations(claims="not a list"),
    legacy_observations(claims=[{"sentence_start_id": "s0"}]),
    legacy_observations(quotes=[LEGACY_RANGE] * 9),
    legacy_observations(claims=[LEGACY_RANGE | {"speaker": "x" * 61}]),
    legacy_observations(claims=[LEGACY_RANGE | {"unrelated": True}]),
    legacy_observations(keyphrases=["x" * 61]),
    legacy_observations(lede_sentence_ids=["s0"] * 3),
    legacy_observations(lede_sentence_ids=["x" * 49]),
    legacy_observations(unrelated=[]),
])
def test_malformed_legacy_observations_and_unknown_fields_still_fail(
    retired: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        calls.parse_label(json.dumps(empty_reply(**retired)))


def test_request_still_refuses_a_table_over_another_source() -> None:
    article = article_with_text("Unit A counted 10 units.")
    another = article_with_text("Unit B counted 20 units.")
    with pytest.raises(SpanDriftError):
        request(article, element_table(another, config=ElementsConfig()))
