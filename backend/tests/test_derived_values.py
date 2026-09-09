"""The four ways code may reach a number the article did not write, and the proof it reached no fifth.

The oracle here has two halves and neither is sufficient alone. **Every
displayed value resolves** - to a Tier 1 element, or to a derived value whose
chain names its function, its version and every input element - and **a function
the list does not hold is refused by name**. The first half without the second
passes on a build that quietly grew a fifth function; the second without the
first passes on a build that draws a figure nothing resolves.

No model runs here and none can: every input is a committed file under
`tests/fixtures/visual-validator/` or a shape built in this file, and one test
reads the derived-value module's own imports to keep it that way (`CLAUDE.md`
section 0a).

Constant cost in the size of one plan and one article's table (Rule #12). No
test here reads a collection a run appends to.
"""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig, VisualsConfig
from idhazh.contracts.derived import DerivedFunction, DerivedValue, DisplayedValue
from idhazh.contracts.element import Element, ElementTable
from idhazh.contracts.visual import EncodingRole, VisualPlan, VisualType
from idhazh.derived_values import (
    DERIVED_VALUE_VERSION,
    DerivedValueError,
    bin_edges,
    convert,
    count,
    derived_value_rate,
    resolve_displayed_values,
    share_of_declared_whole,
    sum_of,
    trusted_data_ratio,
)
from idhazh.visual_validator import validate_plan
from idhazh.visual_vocabulary import UNIT_DIMENSIONS, UNIT_TABLE_VERSION

pytestmark = pytest.mark.visual

VALIDATOR_FIXTURES: Final = FIXTURES_DIR / "visual-validator"
DERIVED_MODULE: Final = Path(__file__).resolve().parents[1] / "idhazh" / "derived_values.py"


def committed_visuals() -> VisualsConfig:
    """The knobs the pipeline actually ships, never a number typed here (Rule #6)."""
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


def load_plan(stem: str) -> VisualPlan:
    return VisualPlan.from_json(read_text(VALIDATOR_FIXTURES / "plans" / f"{stem}.json"))


def load_table(stem: str) -> ElementTable:
    return ElementTable.from_json(read_text(VALIDATOR_FIXTURES / "tables" / f"{stem}.json"))


def plan_payload(stem: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(read_text(VALIDATOR_FIXTURES / "plans" / f"{stem}.json"))
    return payload


def elements_of(table: ElementTable, *ids: str) -> list[Element]:
    known = {element.element_id: element for element in table.elements}
    return [known[one] for one in ids]


def resolve(plan: VisualPlan, table: ElementTable) -> list[DisplayedValue]:
    return resolve_displayed_values(plan, table, visuals=committed_visuals())


#: `wind`'s four megawatt quantities, largest last so the binning case is not
#: sorted by accident. 900, 1200, 2100 and 3400 MW.
WIND_QUANTITIES: Final = (
    "quantity-93-99",
    "quantity-58-66",
    "quantity-112-120",
    "quantity-76-84",
)
WIND_ENTITIES: Final = ("entity-86-92", "entity-41-48", "entity-104-111", "entity-68-75")


def built_plan(visual_type: VisualType, **channels: list[str]) -> VisualPlan:
    """One plan of a shape the committed fixtures do not hold, built rather than found.

    A histogram and a pie are the two types whose marks are arithmetic rather
    than the article's own characters, and neither has a committed fixture
    because row 3 had no reason to write one. Building them here is what section
    13 asks for: the awkward shape is the point, and a built one carries a case
    the fixtures have never produced.
    """
    payload = plan_payload("passes")
    payload["type"] = visual_type.value
    payload["encodings"] = {role.value: [] for role in EncodingRole}
    cited: list[str] = []
    for name, ids in channels.items():
        payload["encodings"][name] = ids
        cited += ids
    payload["element_ids"] = cited
    payload["labels"] = []
    payload["annotations"] = []
    return VisualPlan.model_validate(payload)


def test_the_allow_list_is_four_functions_and_it_is_closed() -> None:
    """Four, and the shortness is the guarantee (O45, O47).

    Asserted as an equality rather than as a length, because a fifth function
    arriving as a rename of a fourth would pass a count. ESCALATE trigger 2 says
    a fifth is not this row's to add; this is that trigger made mechanical, so
    the next person to reach for one meets a failing test rather than a
    paragraph.
    """
    assert {member.value for member in DerivedFunction} == {
        "count",
        "sum",
        "share_of_declared_whole",
        "convert",
    }


def test_a_function_the_list_does_not_hold_is_refused_by_name() -> None:
    """The oracle's second half: refused, and the refusal says which one.

    "Refused" alone is not enough. A payload naming `mean` and a payload with a
    typo in `count` both fail, and an operator reading a log line needs to know
    which of the two happened.
    """
    with pytest.raises(ValidationError) as refusal:
        DerivedValue.model_validate(
            {
                "function": "mean",
                "version": DERIVED_VALUE_VERSION,
                "inputs": ["quantity-58-66", "quantity-76-84"],
                "value": "2300",
                "unit": "mw",
                "source_unit": None,
                "unit_table_version": None,
                "bin_lower": None,
                "bin_upper": None,
            }
        )
    assert "mean" in str(refusal.value)


def test_a_derived_value_carries_a_chain_or_it_does_not_load() -> None:
    """Function, version and every input element - all three, or the shape refuses.

    The chain is the whole trust argument, so it is a shape rule rather than a
    validator rule: a derived value with no inputs is a number with no source,
    and there is no stage at which that is worth carrying.
    """
    with pytest.raises(ValidationError):
        DerivedValue.model_validate(
            {
                "function": "sum",
                "version": DERIVED_VALUE_VERSION,
                "inputs": [],
                "value": "2300",
                "unit": "mw",
                "source_unit": None,
                "unit_table_version": None,
                "bin_lower": None,
                "bin_upper": None,
            }
        )


def test_a_displayed_value_is_an_element_or_a_derived_value_and_never_both_or_neither() -> None:
    """The oracle's first half, made impossible to fail by construction.

    A walk that counts values with neither is only as good as the shape it walks.
    Left as two optional fields, "neither" is a payload somebody can write, and
    the walk becomes a test of whether anybody wrote one. Here it is a shape rule,
    and the walk below then proves the resolver never reaches for the exception.
    """
    for payload in (
        {"role": "quantity", "element_id": None, "derived": None},
        {
            "role": "quantity",
            "element_id": "quantity-58-66",
            "derived": {
                "function": "count",
                "version": DERIVED_VALUE_VERSION,
                "inputs": ["quantity-58-66"],
                "value": "1",
                "unit": None,
                "source_unit": None,
                "unit_table_version": None,
                "bin_lower": None,
                "bin_upper": None,
            },
        },
    ):
        with pytest.raises(ValidationError):
            DisplayedValue.model_validate(payload)


def test_every_displayed_value_of_a_committed_plan_resolves() -> None:
    """The oracle's first half, walked over the two committed plans that draw.

    Zero values with neither, and every one of them reaching an element the
    article's own table holds - which is what `trusted_data_ratio` reports.
    """
    for plan_stem, table_stem in (("passes", "wind"), ("units-convert", "tonnes-and-kilotonnes")):
        table = load_table(table_stem)
        values = resolve(load_plan(plan_stem), table)
        assert values, f"{plan_stem} draws marks, so it resolves to something"
        unresolved = [one for one in values if one.element_id is None and one.derived is None]
        assert unresolved == [], f"{plan_stem} draws a value that resolves to nothing"
        assert trusted_data_ratio(values, table) == 1.0


def test_a_mixed_but_commensurable_channel_is_drawable_and_each_converted_mark_carries_its_chain(
) -> None:
    """The seam row 3 named, closed.

    `units-convert` passes every one of the validator's nine checks and is not
    drawable: three mills reported in `tonne`, `kt` and `t`, and an axis drawn
    from those characters puts 4,200 beside 4.2. After this row the channel
    resolves to one unit, and every mark code moved carries the chain that says
    what it moved from.
    """
    table = load_table("tonnes-and-kilotonnes")
    plan = load_plan("units-convert")
    assert validate_plan(plan, table, visuals=committed_visuals()) == [], (
        "row 3 passes this plan; the conversion is what row 4 owes it"
    )
    marks = [one for one in resolve(plan, table) if one.role is EncodingRole.QUANTITY]
    assert len(marks) == 3
    drawn_units = {
        one.derived.unit if one.derived is not None else table_unit(table, one.element_id)
        for one in marks
    }
    assert {UNIT_DIMENSIONS[unit][1] for unit in drawn_units if unit} == {Decimal(1000)}, (
        "one axis, one scale - `t` and `tonne` are two spellings of one unit, and moving "
        "between them moves no number, so it is formatting and carries no chain"
    )
    converted = [one for one in marks if one.derived is not None]
    assert len(converted) == 1, "only the kilotonne mark moved; the two in tonnes did not"
    chain = converted[0].derived
    assert chain is not None
    assert chain.function is DerivedFunction.CONVERT
    assert chain.version == DERIVED_VALUE_VERSION
    assert chain.inputs == ["quantity-55-61"]
    assert chain.source_unit == "kt"
    assert chain.unit == "t"
    assert chain.unit_table_version == UNIT_TABLE_VERSION
    assert chain.value == "4200", "4.2 kt is 4,200 t, and the two mills are level"


def table_unit(table: ElementTable, element_id: str | None) -> str | None:
    return next(one.unit for one in table.elements if one.element_id == element_id)


def test_convert_refuses_two_units_that_do_not_measure_the_same_thing() -> None:
    """Code does the arithmetic and it refuses the arithmetic that is not one.

    The validator already refuses this plan, so this is the second door: a caller
    reaching `convert` directly cannot talk it into a megawatt-to-kilogram move.
    """
    table = load_table("capacity-and-headcount")
    quantity = next(one for one in table.elements if one.unit == "mw")
    with pytest.raises(DerivedValueError) as refusal:
        convert(quantity, target="kg")
    assert "mw" in str(refusal.value) and "kg" in str(refusal.value)


def test_count_names_every_element_it_counted() -> None:
    """A count is re-derivable from its own chain: the value is the length of `inputs`."""
    table = load_table("wind")
    counted = elements_of(table, *WIND_QUANTITIES[:3])
    value = count(counted, lower=Decimal(900), upper=Decimal(2100))
    assert value.function is DerivedFunction.COUNT
    assert value.value == "3"
    assert value.unit is None, "a count of things measures nothing"
    assert value.inputs == [one.element_id for one in counted]
    assert (value.bin_lower, value.bin_upper) == ("900", "2100")


def test_sum_refuses_a_channel_that_measures_two_things() -> None:
    """One unit, or no total. Converting first is `convert`'s job and a second chain."""
    table = load_table("capacity-and-headcount")
    with pytest.raises(DerivedValueError):
        sum_of([one for one in table.elements if one.kind.value == "quantity"])


def test_sum_totals_the_elements_it_names() -> None:
    table = load_table("wind")
    total = sum_of(elements_of(table, *WIND_QUANTITIES))
    assert total.function is DerivedFunction.SUM
    assert total.value == "7600"
    assert total.unit == "mw"
    assert set(total.inputs) == set(WIND_QUANTITIES)


def test_share_of_declared_whole_is_a_percentage_of_the_parts_it_names() -> None:
    """The part first, the whole after it, and every one of them in the chain.

    The whole is declared by enumeration - these parts and no others - which is
    what the function's middle word means. A share of a whole nobody declared is
    a share of an assumption.
    """
    table = load_table("wind")
    parts = elements_of(table, *WIND_QUANTITIES)
    share = share_of_declared_whole(parts[0], parts)
    assert share.function is DerivedFunction.SHARE_OF_DECLARED_WHOLE
    assert share.unit == "%"
    assert share.inputs[0] == parts[0].element_id
    assert set(share.inputs) == set(WIND_QUANTITIES)
    assert Decimal(share.value) == pytest.approx(Decimal(900) / Decimal(7600) * 100)


def test_a_pie_resolves_to_shares_of_the_slices_it_draws() -> None:
    table = load_table("wind")
    plan = built_plan(
        VisualType.PIE, category=list(WIND_ENTITIES), quantity=list(WIND_QUANTITIES)
    )
    assert validate_plan(plan, table, visuals=committed_visuals()) == []
    values = resolve(plan, table)
    slices = [one for one in values if one.role is EncodingRole.QUANTITY]
    assert len(slices) == 4
    assert all(one.derived is not None for one in slices)
    assert {one.derived.unit for one in slices if one.derived is not None} == {"%"}
    total = sum(Decimal(one.derived.value) for one in slices if one.derived is not None)
    assert total == pytest.approx(Decimal(100))
    names = [one for one in values if one.role is EncodingRole.CATEGORY]
    assert [one.element_id for one in names] == list(WIND_ENTITIES), (
        "a slice's name is the article's own characters and is never arithmetic"
    )


def test_a_histogram_resolves_to_bin_counts_and_the_bins_come_from_config() -> None:
    """Binning is versioned config, never model-chosen (row 45).

    The plan names the quantities and nothing else. How many bins they fall into
    is a knob the operator sets, and the model has no field that could say.
    """
    table = load_table("wind")
    plan = built_plan(VisualType.HISTOGRAM, bins=list(WIND_QUANTITIES))
    assert validate_plan(plan, table, visuals=committed_visuals()) == []
    values = resolve(plan, table)
    assert len(values) == committed_visuals().histogram_bins
    assert all(one.derived is not None for one in values)
    counted = [Decimal(one.derived.value) for one in values if one.derived is not None]
    assert sum(counted) == Decimal(4), "every value falls in exactly one bin"
    named = {
        cited
        for one in values
        if one.derived is not None
        for cited in one.derived.inputs
    }
    assert named == set(WIND_QUANTITIES)


def test_the_bin_edges_are_equal_width_and_the_widest_value_lands_inside() -> None:
    """The last bin is closed so the maximum has somewhere to go.

    Half-open everywhere else, or a value on an internal edge is counted twice
    and the counts stop adding up to the marks.
    """
    edges = bin_edges([Decimal(900), Decimal(3400)], bins=5)
    assert len(edges) == 6
    assert edges[0] == Decimal(900) and edges[-1] == Decimal(3400)
    widths = {edges[index + 1] - edges[index] for index in range(5)}
    assert len(widths) == 1


def test_a_histogram_of_one_repeated_value_is_refused_rather_than_binned() -> None:
    """No spread, no bins. Failing closed beats drawing five empty bars and one full one."""
    with pytest.raises(DerivedValueError):
        bin_edges([Decimal(900), Decimal(900)], bins=3)


def test_a_type_this_build_cannot_resolve_is_refused_by_name() -> None:
    """The seven types with no role rule have no answer to "what is displayed".

    Row 3 refuses them at the validator. The resolver refuses them again rather
    than returning an empty list, because an empty list reads as "this plan draws
    nothing" and the plan says otherwise.
    """
    table = load_table("wind")
    payload = plan_payload("passes")
    payload["type"] = VisualType.KEYFACTS.value
    plan = VisualPlan.model_validate(payload)
    with pytest.raises(DerivedValueError) as refusal:
        resolve(plan, table)
    assert "keyfacts" in str(refusal.value)


def test_a_plan_that_declines_displays_nothing_and_the_rates_say_so() -> None:
    """Null and zero are different facts: a rate over nothing is not zero."""
    values = resolve(load_plan("declines"), load_table("wind"))
    assert values == []
    assert derived_value_rate(values) is None
    assert trusted_data_ratio(values, load_table("wind")) is None


def test_the_two_rates_measure_two_different_things() -> None:
    """One is a narrowness alarm and the other a correctness alarm.

    `derived_value_rate` rising says the pictures are increasingly our arithmetic
    rather than the article's own figures. `trusted_data_ratio` below one says
    something is drawn that resolves to nothing. A build can fail either without
    moving the other, which is why both are reported (P.L22, 12.11 G21).
    """
    table = load_table("tonnes-and-kilotonnes")
    values = resolve(load_plan("units-convert"), table)
    assert derived_value_rate(values) == pytest.approx(1 / len(values))
    assert trusted_data_ratio(values, table) == 1.0
    stranger = load_table("wind")
    assert trusted_data_ratio(values, stranger) == 0.0, (
        "every input names an element this table does not hold"
    )


def test_no_model_can_reach_the_arithmetic() -> None:
    """Code does the arithmetic, and the module's own imports are the proof.

    The same guard row 3 wrote for the validator, for the same reason: a judge
    sharing the failure modes of the thing judged is not a measurement
    (`CLAUDE.md` section 0a), and here the thing judged is a figure a reader will
    read off an axis.
    """
    tree = ast.parse(DERIVED_MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    reaches_a_model = sorted(
        name
        for name in imported
        if any(word in name for word in ("llama", "model_client", "prompt", "http", "requests"))
    )
    assert reaches_a_model == []


def test_the_unit_table_version_is_not_a_config_key() -> None:
    """A stamp an operator can edit without editing the table is a stamp that lies.

    The plan's file list proposed `visuals.unit_table_version`. It is ruled
    against here and the ruling is written down in
    `docs/architecture/publishing/visuals.md`: which units measure the same thing
    is arithmetic rather than a knob, so the table and its stamp stay in code and
    a derived value's chain records the stamp it actually read.
    """
    assert "unit_table_version" not in VisualsConfig.model_fields
    assert UNIT_TABLE_VERSION and DERIVED_VALUE_VERSION
