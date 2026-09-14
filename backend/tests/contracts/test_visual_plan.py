"""What may a model's visual plan not contain, and how long can its reply get?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.visual import (
    CODE_STAMPED_FIELDS,
    FORBIDDEN_FIELDS,
    MAX_LABELS,
    NUMERIC_FIELDS,
    WORST_CASE_REPLY_CHARACTERS,
    EncodingRole,
    PlanDecision,
    PlanEncodings,
    VisualPlan,
    VisualType,
    numeric_leaves,
    unbounded_leaves,
    worst_case_reply_characters,
)

pytestmark = pytest.mark.contract


#
# One combined test passes while three of the four are unenforced, so each gets
# its own arm and each arm names the thing it refuses. Every payload here is a
# committed fixture with one field changed (Guardrail #7, Guardrail #12) - nothing walks a
# collection a run appends to.


def _plan_payload(name: str = "bar-chart") -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "visual-plan" / f"{name}.json")
    )
    return payload


def test_a_plan_of_references_and_closed_names_loads() -> None:
    """The happy path, without which the four refusals below prove nothing."""
    plan = VisualPlan.model_validate(_plan_payload())
    assert plan.decision is PlanDecision.VISUAL
    assert plan.type is VisualType.BAR
    drawn = set(plan.labels) | set(plan.annotations)
    drawn |= {i for ids in plan.encodings.filled().values() for i in ids}
    assert drawn <= set(plan.element_ids), "everything drawn is an element the plan declared"


def test_a_plan_carrying_geometry_does_not_load() -> None:
    """Prohibition 1. A pixel binds the plan to one renderer, so there is nowhere
    to put one: geometry is a number, and the schema admits exactly one number."""
    for pixel in ("canvas_width", "x", "y", "width", "font_size", "axis_max"):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            VisualPlan.model_validate(_plan_payload() | {pixel: 800})
    assert numeric_leaves() == NUMERIC_FIELDS == {"confidence"}


def test_a_plan_carrying_a_literal_number_does_not_load() -> None:
    """Prohibition 2. A bar height is reached by citing an element, so the worst
    an injection can do is pick the wrong bars rather than draw the wrong figure.

    Two arms, because the ways in differ: a new field is refused as an unknown
    key, and a number pushed into a reference field is refused by its type.
    """
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualPlan.model_validate(_plan_payload() | {"values": [4200, 3100]})
    with pytest.raises(ValidationError, match="element_ids"):
        VisualPlan.model_validate(_plan_payload() | {"element_ids": [4200, 3100]})
    assert VisualPlan.model_fields["confidence"].metadata, "the one number is bounded to 0..1"
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        VisualPlan.model_validate(_plan_payload() | {"confidence": 4200.0})


def test_a_plan_carrying_authored_text_does_not_load() -> None:
    """Prohibition 3, the half the shape can carry. Code cuts every character a
    reader sees off a chart, so what names a mark is an element reference and a
    typed string is refused by grammar rather than caught by a check."""
    payload = _plan_payload()
    with pytest.raises(ValidationError, match="labels"):
        VisualPlan.model_validate(payload | {"labels": ["Wind capacity, MW"]})
    with pytest.raises(ValidationError, match="annotations"):
        VisualPlan.model_validate(payload | {"annotations": ["the tallest bar"]})
    encodings = payload["encodings"] | {"category": ["Denmark", "Germany"]}
    with pytest.raises(ValidationError, match="encodings"):
        VisualPlan.model_validate(payload | {"encodings": encodings})


def test_a_plan_that_omits_a_role_does_not_load() -> None:
    """Every role name is a key and the decoder may not skip one.

    Optional arrays produced "a confident chart with no bars in it", twice, on
    the first live run - a plan that names `bar` and simply leaves `quantity`
    out reads as a complete answer. Presence is the whole guarantee this shape
    makes: what a `bar` may leave empty is the validator's rule, and a validator
    cannot rule on a key it never received.
    """
    payload = _plan_payload()
    for role in EncodingRole:
        short = {name: ids for name, ids in payload["encodings"].items() if name != role.value}
        with pytest.raises(ValidationError, match=rf"encodings\.{role.value}\b"):
            VisualPlan.model_validate(payload | {"encodings": short})
    with pytest.raises(ValidationError, match="encodings"):
        VisualPlan.model_validate({k: v for k, v in payload.items() if k != "encodings"})


def test_a_role_the_type_cannot_use_is_present_and_empty() -> None:
    """The other half: an inapplicable role loads as `[]` rather than failing.

    A bar has no bins, no size and no second measured axis, so the four-bar
    fixture carries seven empty channels beside its two filled ones. The shape
    accepts every combination it can spell, including one no type would ever
    draw, because ruling which roles a `bar` may fill needs the type's own rule
    set - and that is the validator's, not the schema's.
    """
    payload = _plan_payload()
    assert set(payload["encodings"]) == {role.value for role in EncodingRole}
    plan = VisualPlan.model_validate(payload)
    assert set(plan.encodings.filled()) == {EncodingRole.CATEGORY, EncodingRole.QUANTITY}
    assert plan.encodings.bins == [] and plan.encodings.size == []
    absurd = payload["encodings"] | {"bins": payload["encodings"]["quantity"]}
    assert VisualPlan.model_validate(payload | {"encodings": absurd}).encodings.bins, (
        "a bar with bins in it is a plan the validator refuses and the shape spells"
    )


def test_the_role_vocabulary_and_the_channels_are_one_list_in_one_order() -> None:
    """Two spellings of one list, and the decoder is held to the second.

    The validator reads roles as data off the enum; the model is held to the
    object's fields. Order as well as names, because field order is decode order
    here as it is on the plan itself.
    """
    assert tuple(PlanEncodings.model_fields) == tuple(role.value for role in EncodingRole)
    channels = VisualPlan.json_schema()["$defs"]["PlanEncodings"]
    # `canonical_json` sorts keys, so `required` is the only place in the committed
    # document where the declared order - and so the decode order - survives.
    assert channels["required"] == [role.value for role in EncodingRole]
    assert channels["additionalProperties"] is False, "a role the vocabulary lacks is not a role"


def test_naming_a_mark_has_one_home_and_it_is_not_a_role() -> None:
    """There is no `label` role, and section 12.8 X2 lists one - so this is the
    assertion that keeps the call made rather than re-opened.

    `labels` is the one naming channel: the elements whose own characters name
    the marks and the axes, eight marks and two axes. A `label` role would ask a
    model the same question a second time inside `encodings`, and a model that
    answers twice can answer two ways with no fact to settle which. `event_label`
    is not the same thing - a timeline's `time` channel places a dot and nothing
    else, so the event text is the mark rather than a name for one.
    """
    assert "label" not in PlanEncodings.model_fields
    assert "label" not in {role.value for role in EncodingRole}
    assert "labels" in VisualPlan.model_fields
    assert MAX_LABELS == 10, "eight marks and two axes, which is what naming a mark is for"


def test_required_but_empty_roles_cost_what_the_module_says_they_cost() -> None:
    """Every role being a key is paid for on every reply, so the price is checked.

    Characters are the half a test can hold, and they are exact. The token
    figure beside them in the module docstring came from `llama-tokenize` against
    the Qwen3 vocabulary, which needs weights this repository does not commit
    (Guardrail #2), so it is recorded there with its hardware and date instead.
    """
    cost = {}
    for stem in ("bar-chart", "declined"):
        body = {
            name: value
            for name, value in _plan_payload(stem).items()
            if name not in CODE_STAMPED_FIELDS
        }
        lean = body | {"encodings": {r: ids for r, ids in body["encodings"].items() if ids}}
        dumped = (json.dumps(b, separators=(",", ":"), sort_keys=True) for b in (body, lean))
        whole, without = (len(text) for text in dumped)
        cost[stem] = whole - without
    assert cost == {"bar-chart": 87, "declined": 114}


def test_a_plan_carrying_alt_text_does_not_load() -> None:
    """Prohibition 4. The compiler assembles alt text out of the element values
    it already holds; the model writing it would be one prose channel restating
    the chart's own data, which no validator can read."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualPlan.model_validate(_plan_payload() | {"alt_text": "A bar chart of wind capacity."})
    assert FORBIDDEN_FIELDS == {"alt_text"}
    assert FORBIDDEN_FIELDS.isdisjoint(VisualPlan.model_fields), (
        "the field is named rather than merely absent, so a later widening does not start"
    )


def test_every_decoded_array_and_string_in_the_plan_is_bounded() -> None:
    """A bound with no total is half a decision, so this is what makes the
    worst-case arithmetic in the module docstring true rather than intended.

    `version` is the one exception and it is not decoded: the base contract
    stamps it on read, so no reply spends a character on it.
    """
    assert unbounded_leaves() == {"version"}
    with pytest.raises(ValidationError, match="element_ids"):
        VisualPlan.model_validate(
            _plan_payload() | {"element_ids": [f"quantity-{n}-{n + 4}" for n in range(99)]}
        )


def test_confidence_decodes_after_the_type() -> None:
    """Field order is decode order. Second in the list a confidence conditions
    every field after it, and the model reads its own hedge back as evidence."""
    order = list(VisualPlan.model_fields)
    assert order.index("confidence") > order.index("type")
    assert order.index("purpose") < order.index("type"), "the form is chosen for a reason"


def test_a_plan_that_declines_draws_nothing() -> None:
    """`none` is the common and correct answer, and it is a decision rather than
    an absence - a refusal that carries half a chart is two answers to one
    question."""
    declined = VisualPlan.model_validate(_plan_payload("declined"))
    assert declined.decision is PlanDecision.NONE
    assert declined.why, "a refusal still says why"
    with pytest.raises(ValidationError, match="declines carries no type"):
        VisualPlan.model_validate(_plan_payload("declined") | {"type": "bar"})
    with pytest.raises(ValidationError, match="proposes a visual states its title"):
        VisualPlan.model_validate(_plan_payload() | {"title": None})


def test_a_plan_may_not_draw_an_element_it_never_declared() -> None:
    """The cheap half of "every element exists", asked of the payload alone: a
    role citing an id the plan did not list is the plan disagreeing with itself.
    Whether the id names a real element is the validator's question."""
    payload = _plan_payload()
    with pytest.raises(ValidationError, match="did not declare"):
        VisualPlan.model_validate(payload | {"labels": ["quantity-9001-9008"]})


def test_the_worst_case_reply_length_is_arithmetic_and_the_fixtures_are_a_fraction_of_it() -> None:
    """Row 14's bounds buy one number, and this is the number.

    The ceiling is recomputed from the generated schema, so a bound that moves
    without the docstring's table moving with it fails at import. The two
    committed plans are measured beside it, because a ceiling nothing is
    compared against says nothing about what a reply actually costs.
    """
    assert worst_case_reply_characters() == WORST_CASE_REPLY_CHARACTERS == 3767
    measured = {}
    for stem in ("bar-chart", "declined"):
        decoded = {
            name: value
            for name, value in _plan_payload(stem).items()
            if name not in CODE_STAMPED_FIELDS
        }
        measured[stem] = len(json.dumps(decoded, separators=(",", ":"), sort_keys=True))
    assert measured == {"bar-chart": 838, "declined": 368}
    assert max(measured.values()) < WORST_CASE_REPLY_CHARACTERS // 4
