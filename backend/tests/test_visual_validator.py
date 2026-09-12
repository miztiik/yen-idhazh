"""Every check the validator makes, and the proof that each one refuses alone.

The oracle for this module is not "a bad plan is refused". It is **one fixture
per check, each failing only its own check**. A validator whose fixtures each
trip three rules cannot tell you which rule works, and a check that never fires
alone is a check nobody can retire, tune or trust.

No model runs here and none can: every input is a committed file under
`tests/fixtures/visual-validator/`, and one test reads the validator's own
source to prove it imports nothing that could reach one (`CLAUDE.md` section 0a).
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
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.visual import (
    EncodingRole,
    PlanDecision,
    VisualPlan,
    VisualPurpose,
    VisualType,
)
from idhazh.visual_validator import (
    Rejection,
    ValidatorCheck,
    validate_plan,
)
from idhazh.visual_vocabulary import (
    DOWNGRADE_EDGES,
    DOWNGRADE_TABLE_VERSION,
    LONGEST_DOWNGRADE_CHAIN,
    PLAN_VOCABULARY_VERSION,
    ROLE_KINDS,
    TYPE_RULES,
    UNIT_DIMENSIONS,
    UNRULED_TYPES,
    VALUE_ROLES,
    commensurable,
)

pytestmark = pytest.mark.visual

VALIDATOR_FIXTURES: Final = FIXTURES_DIR / "visual-validator"


def committed_visuals() -> VisualsConfig:
    """The knobs the pipeline actually ships, never a number typed here (Guardrail #6)."""
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


def tuned_visuals(**knobs: int) -> VisualsConfig:
    """The committed knobs with one moved, through validation rather than around it.

    `model_copy(update=...)` sets an attribute without running a validator, so a
    config it produces can be one the pipeline would refuse to load.
    """
    return VisualsConfig.model_validate(committed_visuals().model_dump(mode="json") | knobs)


def load_plan(stem: str) -> VisualPlan:
    return VisualPlan.from_json(read_text(VALIDATOR_FIXTURES / "plans" / f"{stem}.json"))


def load_table(stem: str) -> ElementTable:
    return ElementTable.from_json(read_text(VALIDATOR_FIXTURES / "tables" / f"{stem}.json"))


def refuse(plan_stem: str, table_stem: str) -> list[Rejection]:
    return validate_plan(load_plan(plan_stem), load_table(table_stem), visuals=committed_visuals())


def histogram_over(*quantities: str) -> VisualPlan:
    """A histogram plan citing these quantities, built because no fixture holds one.

    Every committed plan is a bar, and a histogram is the one type whose channel
    holds the values being distributed rather than the marks drawn - so the case
    this section is about cannot be found and has to be built (section 13).
    """
    payload: dict[str, Any] = json.loads(read_text(VALIDATOR_FIXTURES / "plans" / "passes.json"))
    payload["type"] = VisualType.HISTOGRAM.value
    payload["encodings"] = {role.value: [] for role in EncodingRole}
    payload["encodings"][EncodingRole.BINS.value] = list(quantities)
    payload["element_ids"] = list(quantities)
    payload["labels"] = []
    payload["annotations"] = []
    return VisualPlan.model_validate(payload)


#: One fixture per check, and the check it is built to be the only cause of.
#: `passes` appears twice on purpose: the same plan clears every check against
#: the honest table and fails `no_invented_values` against the table whose cell
#: disagrees with its own characters, which is the cleanest statement of what
#: that check is for.
ONE_CHECK_EACH: Final[tuple[tuple[str, str, ValidatorCheck], ...]] = (
    ("element-missing", "wind", ValidatorCheck.ELEMENT_EXISTS),
    ("kind-mismatched", "wind", ValidatorCheck.SEMANTICALLY_COMPATIBLE),
    ("units-disagree", "capacity-and-headcount", ValidatorCheck.UNITS_CONVERTIBLE),
    ("role-not-for-type", "wind", ValidatorCheck.ROLES_VALID_FOR_TYPE),
    ("too-few-marks", "wind", ValidatorCheck.ENOUGH_DATA),
    ("duplicate-in-role", "wind", ValidatorCheck.NO_DUPLICATE_IN_ROLE),
    ("passes", "misread-quantity", ValidatorCheck.NO_INVENTED_VALUES),
    ("numeral-unmatched", "wind", ValidatorCheck.NUMERALS_MATCHED),
    ("stale-vocabulary", "wind", ValidatorCheck.PLAN_VERSION_CURRENT),
)


def test_the_checks_are_the_nine_the_row_names() -> None:
    """Nine checks, and a tenth arrives with a fixture that trips only it.

    The set below is the row's own list. It is asserted rather than trusted
    because the same list is what section 14.5 gate 3 quotes, and every
    restatement of it in the source document dropped something.
    """
    assert {check.value for check in ValidatorCheck} == {
        "element_exists",
        "semantically_compatible",
        "units_convertible",
        "roles_valid_for_type",
        "enough_data",
        "no_duplicate_in_role",
        "no_invented_values",
        "numerals_matched",
        "plan_version_current",
    }
    assert {check for _, _, check in ONE_CHECK_EACH} == set(ValidatorCheck), (
        "a check with no fixture of its own has never been shown to fire alone"
    )


def test_a_plan_of_cited_elements_and_legal_roles_passes_every_check() -> None:
    """The happy path, without which the nine refusals below prove nothing."""
    assert refuse("passes", "wind") == []


@pytest.mark.parametrize(
    ("plan_stem", "table_stem", "check"),
    ONE_CHECK_EACH,
    ids=[check.value for _, _, check in ONE_CHECK_EACH],
)
def test_each_fixture_trips_its_own_check_and_no_other(
    plan_stem: str, table_stem: str, check: ValidatorCheck
) -> None:
    """The row's oracle, asserted as an equality rather than as a membership.

    `check in [r.check for r in rejections]` passes while three other rules are
    firing on the same fixture, which is exactly the state this test exists to
    refuse.
    """
    rejections = refuse(plan_stem, table_stem)
    assert [rejection.check for rejection in rejections] == [check]
    assert rejections[0].detail, "a refusal names what it saw, or nobody can act on it"


def test_a_plan_that_declines_needs_only_its_vocabulary_stamp() -> None:
    """`none` is the common and correct answer, and it draws nothing to check.

    The stamp is still read, because a refusal planned against a vocabulary this
    build does not hold says nothing about this build's vocabulary either.
    """
    declines = load_plan("declines")
    assert declines.decision is PlanDecision.NONE
    assert validate_plan(declines, load_table("wind"), visuals=committed_visuals()) == []
    stale = declines.model_copy(update={"plan_version": "2026-09-01"})
    stale = VisualPlan.model_validate(stale.model_dump(mode="json"))
    assert [r.check for r in validate_plan(stale, load_table("wind"), visuals=committed_visuals())] == [
        ValidatorCheck.PLAN_VERSION_CURRENT
    ]


# --- The two units checks, which are one ruling read from both sides ---------


def test_the_recorded_headcount_failure_is_a_committed_fixture() -> None:
    """Decision 4: the behaviour behind `same_unit_bars` outlives the module.

    A small model was given an article about solar capacity, picked the three
    correct year-on-year megawatt bars, and appended the sector's headcount.
    That is a real recorded failure and this is where it is kept, so retiring
    the planner cannot delete it.
    """
    table = load_table("capacity-and-headcount")
    units = [element.unit for element in table.elements if element.kind is ElementKind.QUANTITY]
    assert units == ["mw", "mw", "mw", "people"], "three capacity bars and one headcount"
    rejections = refuse("units-disagree", "capacity-and-headcount")
    assert [rejection.check for rejection in rejections] == [ValidatorCheck.UNITS_CONVERTIBLE]
    assert "people" in rejections[0].detail and "mw" in rejections[0].detail


def test_two_spellings_of_one_dimension_are_not_two_units() -> None:
    """Decision 2: "convertible or identical" keeps its second word.

    Comparing unit strings for equality is cheaper and it refuses `4,200 tonnes`
    beside `4.2 kt`, which is the pair a reader most needs joined. The fixture
    is that pair, and it passes.
    """
    table = load_table("tonnes-and-kilotonnes")
    units = [element.unit for element in table.elements if element.kind is ElementKind.QUANTITY]
    assert units == ["tonne", "kt", "t"], "one dimension, three spellings, no two equal"
    assert len(set(units)) == 3, "string equality would refuse every pair here"
    assert refuse("units-convert", "tonnes-and-kilotonnes") == []


def test_a_unit_the_table_does_not_name_is_never_assumed_compatible() -> None:
    """The table is a closed allow-list, and the fail-closed direction is the point.

    Units are read off a stranger's page (Guardrail #11), so an unknown one is
    compared by identity and by nothing else. Two currencies are the case that
    matters: joining them needs an exchange rate, which is a number no article
    wrote.
    """
    assert commensurable("mw", "mw") and commensurable("tonne", "kt")
    assert not commensurable("$", "\u00a3"), "an exchange rate is a number nobody wrote"
    assert not commensurable("mw", "mwh"), "power is not energy"
    assert not commensurable("mw", None), "a bare number does not measure what a megawatt measures"
    assert not commensurable("widget", "gadget"), "an unknown unit compares by identity only"
    assert "m" not in UNIT_DIMENSIONS, "a bare m is metres or millions, and a guess is a 1e6 error"
    assert "ton" not in UNIT_DIMENSIONS, "short, long and metric tons are three different masses"


# --- The type vocabulary, and the stamp that says which one a plan met -------


def test_every_declarable_type_has_a_rule_or_is_named_as_having_none() -> None:
    """Silence is the failure mode a per-type check has, so there is no silence.

    A type in neither set would be waved through by `roles_valid_for_type` and
    by `enough_data`, which is worse than refusing it - the plan draws and
    nothing said so.
    """
    assert set(TYPE_RULES) | UNRULED_TYPES == set(VisualType)
    assert not set(TYPE_RULES) & UNRULED_TYPES
    for visual_type, rules in TYPE_RULES.items():
        assert rules.marks in rules.required, f"{visual_type.value} counts marks it may not have"
        assert not rules.required & rules.optional


def test_a_type_whose_rules_are_not_written_yet_is_refused_rather_than_drawn() -> None:
    """Declarable is not renderable, and the ladder is what catches this.

    Plans 16 to 18 own the composition, infographic and diagram families. Until
    then a plan naming one of their types is refused here by name, and plan 11's
    downgrade ladder re-enters this same validator with a nearer neighbour.
    """
    plan = load_plan("passes")
    for unruled in sorted(UNRULED_TYPES, key=lambda member: member.value):
        named = VisualPlan.model_validate(plan.model_dump(mode="json") | {"type": unruled.value})
        rejections = validate_plan(named, load_table("wind"), visuals=committed_visuals())
        assert ValidatorCheck.ROLES_VALID_FOR_TYPE in [r.check for r in rejections]
        assert "no role rule" in rejections[0].detail


def test_the_vocabulary_stamp_is_compared_rather_than_matched() -> None:
    """Decision 3: versions are date-stamps, so "current" orders them.

    The two directions are different faults with different fixes, so the detail
    says which one this is: a plan behind the vocabulary is re-planned, and a
    plan ahead of it was written by a build this one cannot read.
    """
    plan = load_plan("passes")
    assert plan.plan_version == PLAN_VOCABULARY_VERSION
    behind = VisualPlan.model_validate(plan.model_dump(mode="json") | {"plan_version": "2026-01-01"})
    ahead = VisualPlan.model_validate(plan.model_dump(mode="json") | {"plan_version": "2099-01-01"})
    table, visuals = load_table("wind"), committed_visuals()
    assert "behind" in validate_plan(behind, table, visuals=visuals)[0].detail
    assert "ahead" in validate_plan(ahead, table, visuals=visuals)[0].detail


# --- The three that read committed knobs rather than a number typed here -----


def test_enough_data_reads_the_committed_knobs_and_not_a_literal() -> None:
    """Guardrail #6. The floor is `visuals.min_chart_points` and it is read, not chosen."""
    visuals = committed_visuals()
    assert (visuals.min_chart_points, visuals.max_chart_points) == (3, 8)
    plan, table = load_plan("too-few-marks"), load_table("wind")
    assert [r.check for r in validate_plan(plan, table, visuals=visuals)] == [
        ValidatorCheck.ENOUGH_DATA
    ]
    lowered = visuals.model_copy(update={"min_chart_points": 2})
    assert lowered.min_chart_points == 2, "model_copy takes a key the model does not have"
    assert validate_plan(plan, table, visuals=lowered) == []
    tightened = visuals.model_copy(update={"max_chart_points": 3})
    assert tightened.max_chart_points == 3
    assert [r.check for r in validate_plan(load_plan("passes"), table, visuals=tightened)] == [
        ValidatorCheck.ENOUGH_DATA
    ]


def test_a_histogram_needs_a_value_for_every_bin_it_draws() -> None:
    """A histogram's marks are its bins, and its channel holds the values, not the marks.

    Counting the channel asked the wrong question. Here it admitted three values
    against five bars: two of the five would count nothing, `derived_values`
    refuses that drawing, and the validator had already said the plan was fine.
    The floor is `visuals.histogram_bins` because those are the marks that have
    to be filled, and it is a knob rather than a number chosen here (Guardrail #6).
    """
    table = load_table("wind")
    three = histogram_over("quantity-93-99", "quantity-58-66", "quantity-112-120")
    assert validate_plan(three, table, visuals=tuned_visuals(histogram_bins=3)) == []
    rejections = validate_plan(three, table, visuals=tuned_visuals(histogram_bins=5))
    assert [rejection.check for rejection in rejections] == [ValidatorCheck.ENOUGH_DATA]
    assert "3 values" in rejections[0].detail
    assert "5 bins" in rejections[0].detail


def test_a_bin_count_outside_the_mark_window_never_loads() -> None:
    """A histogram draws the same number of bars whatever the plan says, so this is asked once.

    Its bins are the marks a reader counts, so they are bounded by the two knobs
    that already say how many marks a chart may draw. Asked where the config
    loads, a wrong knob names the operator who set it and the run never starts.
    Asked per plan it would refuse every histogram of every run, name the
    article, and be right about none of them.
    """
    visuals = committed_visuals()
    assert visuals.min_chart_points <= visuals.histogram_bins <= visuals.max_chart_points
    for bins in (visuals.min_chart_points - 1, visuals.max_chart_points + 1):
        with pytest.raises(ValidationError):
            tuned_visuals(histogram_bins=bins)


def test_a_numeral_in_reader_facing_prose_is_matched_against_the_cited_elements() -> None:
    """The three prose channels the shape could only length-bound.

    Each is checked on its own arm, because one combined arm passes while two of
    the three are unread. A numeral the article's own characters carry is fine;
    a numeral from nowhere is not, and neither is one the model reached by
    converting - code does the arithmetic, and row 4 records it when it does.
    """
    plan, table, visuals = load_plan("passes"), load_table("wind"), committed_visuals()
    for field, prose in (
        ("title", "Capacity reached 5,000 MW"),
        ("caption", "Output rose 40 percent."),
        ("why", "The 2019 figure is the one the story turns on."),
    ):
        edited = VisualPlan.model_validate(plan.model_dump(mode="json") | {field: prose})
        rejections = validate_plan(edited, table, visuals=visuals)
        assert [r.check for r in rejections] == [ValidatorCheck.NUMERALS_MATCHED], field
        assert field in rejections[0].detail
    stated = VisualPlan.model_validate(
        plan.model_dump(mode="json") | {"caption": "Germany's 3,400 MW leads the four."}
    )
    assert validate_plan(stated, table, visuals=visuals) == [], "the article's own figure is fine"
    converted = VisualPlan.model_validate(
        plan.model_dump(mode="json") | {"caption": "Germany leads on 3.4 GW."}
    )
    assert [r.check for r in validate_plan(converted, table, visuals=visuals)] == [
        ValidatorCheck.NUMERALS_MATCHED
    ], "a model that converted a figure wrote a number the article did not"


def test_an_element_whose_cell_disagrees_with_its_own_characters_is_refused() -> None:
    """The residue the shape cannot see, and the reason this check is not free.

    `Element` holds `span_excerpt` to the width of its span. It cannot hold it
    to the value beside it, because the value is a reading of those characters
    and the shape does no reading. The table crosses a stage boundary as a
    payload, so the consumer that is about to draw the figure re-reads it.
    """
    honest = load_table("wind")
    misread = load_table("misread-quantity")
    changed = [
        (mine.element_id, mine.value, theirs.value)
        for mine, theirs in zip(honest.elements, misread.elements, strict=True)
        if mine.value != theirs.value
    ]
    assert changed == [("quantity-58-66", "1200", "4200")], "one cell differs and nothing else"
    assert misread.elements[2].span_excerpt == "1,200 MW"
    rejections = refuse("passes", "misread-quantity")
    assert [r.check for r in rejections] == [ValidatorCheck.NO_INVENTED_VALUES]
    assert "quantity-58-66" in rejections[0].detail


# --- The two structural guards -----------------------------------------------


@pytest.mark.parametrize("module", ["visual_validator", "visual_vocabulary"])
def test_no_check_can_reach_a_model(module: str) -> None:
    """ESCALATE trigger 1, asserted rather than promised.

    A judge that shares the failure modes of the thing judged is not a
    measurement (`CLAUDE.md` section 0a), so the validator is deterministic code
    over committed data. The cheapest way to keep it that way is to read its own
    imports: nothing that can open a socket or start a server is among them. The
    vocabulary the checks read is held to the same list, or moving a table out
    of the validator would move it out from under this guard.
    """
    source = read_text(Path(__file__).resolve().parents[1] / "idhazh" / f"{module}.py")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {name for name in imported if name.split(".")[0] in {"http", "socket", "urllib"}}
    assert not {name for name in imported if "llm" in name or "server" in name}
    assert imported <= {
        "__future__",
        "collections.abc",
        "decimal",
        "enum",
        "idhazh.contracts.app_config",
        "idhazh.contracts.element",
        "idhazh.contracts.visual",
        "idhazh.elements",
        "idhazh.visual_vocabulary",
        "re",
        "typing",
    }, f"a new import into {module} is a new way for a check to stop being deterministic"


def test_every_role_and_every_value_role_is_declared() -> None:
    """The two tables the kind checks read, held against the role vocabulary."""
    assert set(ROLE_KINDS) == set(EncodingRole)
    assert VALUE_ROLES <= set(EncodingRole)
    for role in VALUE_ROLES:
        assert ROLE_KINDS[role] == frozenset({ElementKind.QUANTITY}), (
            f"{role.value} is drawn on a measured axis, so only a quantity fills it"
        )


@pytest.mark.parametrize(
    "path",
    sorted(VALIDATOR_FIXTURES.glob("*/*.json")),
    ids=lambda path: f"{path.parent.name}/{path.stem}",
)
def test_every_fixture_round_trips_byte_identically(path: Path) -> None:
    """A hand-edited fixture drifts from the model that is supposed to describe it.

    `tests/fixtures/contracts/` gets this from the contract gate. These live
    outside it because a table whose cell is deliberately wrong would read as a
    canonical example in that folder, so the gate comes with them.
    """
    text = read_text(path)
    payload: dict[str, Any] = json.loads(text)
    contract = ElementTable if path.parent.name == "tables" else VisualPlan
    assert contract.from_json(text).to_json() == text
    assert "\r" not in text and payload


def test_the_unit_table_scales_within_one_dimension_are_arithmetic() -> None:
    """A kilotonne is a thousand tonnes. That is not a knob and it is checked.

    `MAGNITUDE` in `idhazh.elements` is the precedent: a magnitude word's
    multiplier is arithmetic and lives in code beside the pattern that reads it.
    """
    assert UNIT_DIMENSIONS["tonne"] == ("mass", Decimal(1000))
    assert UNIT_DIMENSIONS["kt"] == ("mass", Decimal(1_000_000))
    assert UNIT_DIMENSIONS["kt"][1] == UNIT_DIMENSIONS["tonne"][1] * 1000
    assert UNIT_DIMENSIONS["mw"] == ("power", Decimal(1_000_000))
    dimensions = {dimension for dimension, _ in UNIT_DIMENSIONS.values()}
    assert dimensions == {"power", "energy", "mass", "length", "duration"}


class TestTheDowngradeAllowList:
    """The table the ladder walks, held to what an edge has to be to be one.

    It is a static allow-list rather than a rule, because without one the ladder
    can walk a comparison into a timeline and record it as legal - and the
    cross-family ban is what "purpose survives" implies and never states.
    """

    def test_every_target_is_a_type_the_validator_can_pass(self) -> None:
        """A target the validator refuses by name rescues nothing, so it is not an edge.

        "Any chart to `table` at depth 2" is in the source document and `table`
        has no role rule, which is why it is absent here.
        """
        for source, edges in DOWNGRADE_EDGES.items():
            for edge in edges:
                assert edge.target in TYPE_RULES, (
                    f"{source.value} steps down to {edge.target.value}, which has no rule"
                )
                assert edge.target not in UNRULED_TYPES

    def test_no_edge_leads_somewhere_that_would_be_refused_identically(self) -> None:
        """An edge whose target wants the same channels cannot change any outcome.

        `line` to `area` is the shape this refuses: both require a time and a
        quantity, so a plan refused as one is refused as the other, and listing
        it would be a rung nobody can stand on.
        """
        for source, edges in DOWNGRADE_EDGES.items():
            if source not in TYPE_RULES:
                continue
            for edge in edges:
                assert TYPE_RULES[edge.target].required != TYPE_RULES[source].required, (
                    f"{source.value} -> {edge.target.value} asks for the same channels"
                )

    def test_every_edge_names_the_purposes_it_leaves_standing(self) -> None:
        for source, edges in DOWNGRADE_EDGES.items():
            for edge in edges:
                assert edge.purposes, f"{source.value} -> {edge.target.value} preserves nothing"
                assert edge.purposes <= set(VisualPurpose)

    def test_the_edges_do_not_cycle(self) -> None:
        """The ladder is bounded by the config's rung count, and a cycle would let a
        plan arrive back at a type the validator already refused, one depth poorer."""
        assert LONGEST_DOWNGRADE_CHAIN >= 1
        assert LONGEST_DOWNGRADE_CHAIN < len(VisualType)

    def test_a_slope_has_no_edge_because_a_bar_loses_the_pairing(self) -> None:
        """Named rather than derived: it is a judgement the source document made,
        and a test is where a judgement stops being somebody's memory."""
        assert VisualType.SLOPE not in DOWNGRADE_EDGES
        assert VisualType.LINE not in DOWNGRADE_EDGES
        assert VisualType.FLOW not in DOWNGRADE_EDGES

    def test_the_edge_table_has_a_stamp_of_its_own(self) -> None:
        """Folded into the plan vocabulary's, adding an edge would re-plan every
        item carrying an older stamp - a model call apiece."""
        stamps = {DOWNGRADE_TABLE_VERSION, PLAN_VOCABULARY_VERSION}
        assert len(stamps) == 2
