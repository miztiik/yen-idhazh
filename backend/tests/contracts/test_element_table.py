"""What may an element claim, and does its span still cut the text it describes?"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.element import (
    JUDGED_FIELDS,
    TIER_ONE_FIELDS,
    TIER_TWO_FIELDS,
    Element,
    ElementKind,
    ElementTable,
    Extractor,
)

pytestmark = pytest.mark.contract


#
# The element shape splits what code cut out of the bytes from what a labeller
# said about it. Both halves have to be tested. "An element with only its Tier 1
# fields validates" on its own proves nothing, because a shape whose Tier 1
# fields carried defaults would pass it while letting a judgement travel with no
# anchor. The pair is the split.


def _element_payload(path: Path, index: int = 0) -> dict[str, Any]:
    """One element out of a committed table, as a plain dict to mutate."""
    payload: dict[str, Any] = json.loads(read_text(CONTRACT_FIXTURES_DIR / "element-table" / path))
    element: dict[str, Any] = payload["elements"][index]
    return element

def test_an_element_carrying_only_its_tier_one_fields_validates() -> None:
    """The first half of the oracle. Nine keys, no judgement, and it loads."""
    element = {
        name: value
        for name, value in _element_payload(Path("regex-only.json")).items()
        if name in TIER_ONE_FIELDS
    }
    assert set(element) == set(TIER_ONE_FIELDS)
    assert Element.model_validate(element).extractor is Extractor.REGEX

@pytest.mark.parametrize("missing", TIER_ONE_FIELDS)
def test_a_tier_two_field_with_no_tier_one_anchor_is_refused(missing: str) -> None:
    """The second half, and the one that bites. Every Tier 1 field is required,
    so a judged element that has lost any one of its anchors does not load - it
    is not silently accepted with a default standing in for the missing one."""
    element = _element_payload(Path("labelled.json"), index=1)
    assert element["salience"] is not None or element["measure"] is not None
    element.pop(missing)
    with pytest.raises(ValidationError, match=missing):
        Element.model_validate(element)

def test_the_generated_schema_requires_tier_one_and_nothing_else() -> None:
    """The split is machine-checked rather than promised in a docstring."""
    required = ElementTable.json_schema()["$defs"]["Element"]["required"]
    assert sorted(required) == sorted(TIER_ONE_FIELDS)
    assert not set(required) & set(TIER_TWO_FIELDS)

def test_every_element_field_belongs_to_exactly_one_tier() -> None:
    """A field added without a tier is a field with no trust story. The module
    refuses to import in that state; this is the readable half of that guard."""
    assert tuple(Element.model_fields) == TIER_ONE_FIELDS + TIER_TWO_FIELDS
    assert not set(TIER_ONE_FIELDS) & set(TIER_TWO_FIELDS)

def test_the_contract_covers_six_kinds_though_two_have_producers() -> None:
    assert {kind.value for kind in ElementKind} == {
        "quantity",
        "date",
        "entity",
        "place",
        "quote",
        "claim",
    }

def test_span_excerpt_is_the_verbatim_slice_and_a_cleaned_string_is_refused() -> None:
    """`visual_planner.NumericFact.raw` is `currency + sign + digits`, whitespace
    cleaned, so it drops the magnitude word and the unit. Substituting it for the
    excerpt shortens the string without moving the offsets, and the shape refuses
    that outright - the width of the span and the length of the excerpt are one
    number. This is why one name survives and the third field does not exist."""
    element = _element_payload(Path("regex-only.json"), index=2)
    assert element["span_excerpt"] == "$4.5 billion"
    raw_shaped = dict(element, span_excerpt="$4.5")
    with pytest.raises(ValidationError, match="verbatim slice"):
        Element.model_validate(raw_shaped)

def test_element_id_is_rebuilt_not_trusted() -> None:
    element = _element_payload(Path("regex-only.json"))
    relabelled = dict(element, element_id=f"quantity-0-{element['span_end']}")
    with pytest.raises(ValidationError, match="element_id"):
        Element.model_validate(relabelled)

def test_only_a_measured_kind_reads_as_a_value() -> None:
    """A quote has no number, and a shape that let one be written is the shape
    the span exists to make unnecessary."""
    quote = dict(
        _element_payload(Path("labelled.json")),
        kind="quote",
        entity=None,
        salience=None,
        label_source=None,
        ledger_version=None,
        value="7",
    )
    quote["element_id"] = f"quote-{quote['span_start']}-{quote['span_end']}"
    with pytest.raises(ValidationError, match="value"):
        Element.model_validate(quote)

def test_a_date_may_not_carry_a_resolved_relative_reference() -> None:
    """"Three years ago" resolves against a publication date the article never
    wrote. The grammar refuses it at the shape, so no producer can write one by
    accident."""
    date_element = _element_payload(Path("regex-only.json"), index=1)
    assert date_element["kind"] == "date"
    with pytest.raises(ValidationError, match="value"):
        Element.model_validate(dict(date_element, value="three years ago"))

def test_a_judged_field_names_who_judged_it() -> None:
    """Tier 2 is a claim somebody made. A claim with no author cannot be measured
    later, and an author with no claim is a record of nothing."""
    judged = _element_payload(Path("labelled.json"), index=1)
    with pytest.raises(ValidationError, match="label_source"):
        Element.model_validate(dict(judged, label_source=None, ledger_version=None))
    unjudged = {
        name: value for name, value in judged.items() if name not in set(JUDGED_FIELDS)
    }
    with pytest.raises(ValidationError, match="label_source"):
        Element.model_validate(unjudged | {"label_source": "qwen35-9b"})

def test_a_span_past_the_end_of_the_text_is_refused() -> None:
    """The table carries the length of the string its spans index, so the shape
    can refuse an offset that points nowhere without holding the text."""
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["source_text_length"] = payload["elements"][0]["span_end"] - 1
    with pytest.raises(ValidationError, match="ends past"):
        ElementTable.model_validate(payload)

def test_one_kind_and_one_span_is_one_fact() -> None:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["elements"] = [payload["elements"][0], dict(payload["elements"][0])]
    with pytest.raises(ValidationError, match="one address"):
        ElementTable.model_validate(payload)

def test_the_table_reads_in_the_order_the_article_was_written() -> None:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["elements"] = list(reversed(payload["elements"]))
    with pytest.raises(ValidationError, match="span_start"):
        ElementTable.model_validate(payload)

def test_the_element_table_holds_one_hash_for_the_whole_article() -> None:
    """Decision 6, made mechanical: the hash is a field of the table and no
    element carries one. A per-element hash would be redundant against this plus
    the re-slice, on every article for ever."""
    assert "source_text_hash" in ElementTable.model_fields
    assert not [name for name in Element.model_fields if "hash" in name]

#
# Row 1 checks that `span_excerpt` is as wide as its span, which refuses a
# whitespace-cleaned string outright. Row 4 is the half that check cannot reach:
# the text is not in the payload, so the shape can compare two numbers and never
# two strings. `span_drift` takes the text and cuts it.


def _element_table_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    return payload

def _text_the_table_indexes(payload: dict[str, Any]) -> str:
    """A string of the length the table names, with every excerpt at its own offset."""
    characters = ["."] * payload["source_text_length"]
    for element in payload["elements"]:
        characters[element["span_start"] : element["span_end"]] = element["span_excerpt"]
    return "".join(characters)

def test_a_committed_table_re_slices_against_the_text_its_spans_describe() -> None:
    """The invariant at rest. Without this the two tests below prove nothing."""
    payload = _element_table_payload()
    assert ElementTable.model_validate(payload).span_drift(_text_the_table_indexes(payload)) is None

def test_a_same_width_excerpt_passes_the_shape_and_fails_the_re_slice() -> None:
    """What row 4 adds over row 1, in one comparison.

    `1,200 Mw` is exactly as wide as `1,200 MW`, so the width check has nothing
    to say about it and the element loads. It is still not the characters the
    span holds, and a figure drawn from it would carry an excerpt the article
    never wrote.
    """
    payload = _element_table_payload()
    text = _text_the_table_indexes(payload)
    payload["elements"][0]["span_excerpt"] = "1,200 Mw"

    misread = ElementTable.model_validate(payload)
    assert misread.elements[0].span_excerpt == "1,200 Mw", "the shape accepts it"
    drift = misread.span_drift(text)
    assert drift is not None
    assert drift.startswith(misread.elements[0].element_id)

def test_a_text_that_moved_by_one_character_names_the_first_span_that_moved() -> None:
    """The reason is a log line, so it carries no fetched bytes (Guardrail #11) - the
    element's own address and the two lengths, which say what moved and by how
    much without quoting a stranger's page back at an operator."""
    payload = _element_table_payload()
    table = ElementTable.model_validate(payload)
    moved = " " + _text_the_table_indexes(payload)

    drift = table.span_drift(moved)
    assert drift is not None
    assert drift.startswith(table.elements[0].element_id)
    assert f"{table.source_text_length} characters" in drift
    assert str(len(moved)) in drift
    assert table.elements[0].span_excerpt not in drift

def test_the_re_slice_added_no_field_to_the_persisted_shape() -> None:
    """The text a span indexes is not in the payload and is not going into it -
    `span_excerpt` is article body text, which no published payload may carry
    (`CLAUDE.md` section 0a). So the check is a method over a text the caller
    already holds, and the shape did not have to move for it."""
    assert callable(ElementTable.span_drift)
    assert "span_drift" not in ElementTable.model_fields
    assert "text" not in ElementTable.model_fields
