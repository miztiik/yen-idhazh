"""The four functions, and the resolver that turns a validated plan into figures.

A visual plan carries references and closed names, never a number. Something has
to turn it into the figures a reader will read off an axis, and that something is
here. It reads a plan the validator has already passed, resolves every mark, and
returns one `DisplayedValue` per figure - each one either a Tier 1 element the
article itself wrote, or a derived value with a chain back to every element code
read to reach it.

**No model runs here and none can.** Code does the arithmetic (section 10.6): a
model has no character-level view and cannot count, and a figure it produced
would be a figure with no source. `backend/tests/test_derived_values.py` reads
this module's own imports to keep it that way.

## What the resolver reaches today, and what it does not

Three of the four functions are reached by resolving a plan. `convert` closes the
seam row 3 named: a channel measuring one thing in three spellings passes every
validator check and is not drawable, because an axis drawn from those characters
puts 4,200 beside 4.2. `share_of_declared_whole` is what a pie slice *is*, and
`count` is what a histogram bar is.

`sum` is the fourth and nothing displays one, because no type in the vocabulary
draws a total. It is here, tested and complete, and the resolver reaches it on the
day a template draws one. That is a named seam rather than a gap: the function is
on the closed list because O45 put it there, and shipping the list four short of
its own definition would be the widening this contract exists to prevent, arriving
as an omission.

## A refusal is a value, and the caller degrades the item

`resolve_displayed_values` returns a `Resolution`: the figures, or one `Refusal`
naming the check that stopped it. The caller's answer is always the same one -
publish the item with no picture and record the check - so making it read a
refusal off the return is what "degrade, do not fail" means in code (section 1a).
A caller that has to remember a `try` is a caller who will one day not.

Thirteen of the fourteen refusals restate a check `visual_validator` makes, and
reaching one of those means a caller resolved a plan it never validated. The
fourteenth, `values_have_spread`, is the resolver's own: a histogram whose values
crowd into one end of their own range passes every one of the validator's nine
checks and still leaves a bar with nothing in it. That one case is why this
returns rather than raises. It is kept distinct from `enough_values_for_bins`,
which is the same empty bar for the other reason - fewer values than bins - and
that reason is a plan fault the validator names.

The four functions and the helpers under them still raise `DerivedValueError`. A
caller reaching `convert` with two units that do not measure the same thing has a
bug rather than an article with a problem, and the boundary that a stage calls is
the one place that turns the raise into a refusal.

## The target unit is code's choice, never the plan's

A channel mixing `tonne`, `kt` and `t` has to be drawn against one of them. Taking
the first entry's unit would hand the choice to the model, which orders the
channel - and the whole argument is that the model reaches no arithmetic. So the
target is the **smallest scale present in the channel**, and among units sharing
that scale the one that sorts first. Two properties fall out of it and both are
load-bearing: it is a fact about the channel's contents rather than about the
plan's order, and converting to the smallest present unit only ever multiplies, so
no value is divided into a repeating decimal and no rounding decision of ours is
hidden inside a mark. A ratio that will not state exactly is refused rather than
rounded (`convert`), because precision is declared and declaring it is the
compiler's, not ours.

## Every number is a Decimal at a fixed context

`float` is not a currency of this repository - a Tier 1 value is a decimal pinned
to text for the reason a timestamp is, and a derived value is written the same
way. A share is the one function whose division does not terminate, so it runs in
an explicit 28-digit context rather than the process default: a global anybody can
change is a number that would come out differently in two builds.

Constant cost in the size of one plan and one article's table, both capped by the
contract and by `elements.max_per_article` (Guardrail #12).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from enum import StrEnum
from typing import Final, NamedTuple

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.derived import DerivedFunction, DerivedValue, DisplayedValue
from idhazh.contracts.element import Element, ElementTable
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.visual_vocabulary import (
    TYPE_RULES,
    UNIT_DIMENSIONS,
    UNIT_TABLE_VERSION,
    VALUE_ROLES,
    commensurable,
)

#: The date-stamp of the arithmetic below - the four functions and the binning
#: rule - and what every chain records. Not `UNIT_TABLE_VERSION`, which stamps
#: the table a conversion reads and which a `convert` chain records beside this
#: one; two inputs, two stamps, and a chain that names both can be redone.
DERIVED_VALUE_VERSION: Final = "2026-09-09"

#: Where a share's division stops. Fixed here rather than inherited from
#: `decimal.getcontext()`, which any caller in the process can move - a figure a
#: reader reads may not depend on what some other module did to a global.
_SHARE_PRECISION: Final = 28

_HUNDRED: Final = Decimal(100)


class ResolverCheck(StrEnum):
    """Why a plan could not be turned into figures, one stable name per cause.

    A name rather than a string, for the reason `ValidatorCheck` is one: a
    refusal that cannot say which rule fired is a rule that can never be
    retired, tuned or shown to work. The names are what a caller records beside
    the item it degraded.

    **Thirteen of the fourteen restate a check the validator makes**, and a
    caller only reaches one of those by resolving a plan it never validated.
    `VALUES_HAVE_SPREAD` is the exception and it is the whole reason this
    contract is a value rather than an exception: a histogram whose values crowd
    into one end of their own range passes every one of the validator's nine
    checks and still has an empty bar.
    """

    #: A cited id is not in the article's element table.
    ELEMENT_EXISTS = "element_exists"
    #: A drawn element states no figure, so there is nothing to plot.
    ELEMENT_STATES_A_VALUE = "element_states_a_value"
    #: A converted element states no unit, so there is nothing to move.
    ELEMENT_STATES_A_UNIT = "element_states_a_unit"
    #: The type has no role rule, so this build cannot say what it displays.
    TYPE_HAS_ROLE_RULE = "type_has_role_rule"
    #: A measured channel does not reduce to one unit.
    UNITS_COMMENSURABLE = "units_commensurable"
    #: A conversion was asked for between one unit and itself.
    TARGET_IS_A_DIFFERENT_UNIT = "target_is_a_different_unit"
    #: A conversion ratio will not state exactly, and rounding it here would be
    #: a digit nobody declared.
    CONVERSION_IS_EXACT = "conversion_is_exact"
    #: A total or a share was asked of inputs stating more than one unit.
    ONE_UNIT_ACROSS_INPUTS = "one_unit_across_inputs"
    #: A total or a whole was asked of a single element, which is that element.
    TWO_INPUTS_AT_LEAST = "two_inputs_at_least"
    #: A declared whole totals zero, so no part has a share of it.
    WHOLE_IS_NOT_NOTHING = "whole_is_not_nothing"
    #: Fewer than two bins is not a distribution.
    BINS_ARE_A_DISTRIBUTION = "bins_are_a_distribution"
    #: A count or a binning was asked over no elements at all.
    SOMETHING_TO_MEASURE = "something_to_measure"
    #: A bin is empty because there are fewer values than bins. A plan fault
    #: `enough_data` names, restated here for a caller that skipped it.
    ENOUGH_VALUES_FOR_BINS = "enough_values_for_bins"
    #: A bin is empty because the values crowd into one end of their own range.
    #: The one refusal no validator check makes.
    VALUES_HAVE_SPREAD = "values_have_spread"


class DerivedValueError(ValueError):
    """The plan cannot be turned into figures, and `check` says which part.

    A `ValueError` so a caller written before this class still catches it, and
    its own type so a caller can tell it from a shape refusal.

    It is raised by the four functions and by the helpers under them, because a
    caller reaching `convert` with two units that do not measure the same thing
    has a bug rather than an article with a problem. It is **not** raised out of
    `resolve_displayed_values`, which is the boundary a stage calls: that
    catches it and hands back a `Refusal`, so degrading the item is what a
    caller naturally does (`CLAUDE.md` section 1a).
    """

    def __init__(self, check: ResolverCheck, detail: str) -> None:
        super().__init__(detail)
        self.check = check
        self.detail = detail


class Refusal(NamedTuple):
    """One reason a validated plan still draws nothing, and the fact that says why.

    The resolver's counterpart to the validator's `Rejection`, and it is one
    rather than a list because the two answer different questions. The validator
    reports every rule that did not hold, so an operator can see all of an
    article's problems at once. The resolver stops at the first figure it cannot
    produce, because the marks after it are not computable either and reporting
    them would be reporting consequences.

    `detail` is built out of element ids, role names, type names, units and
    digits, never out of an element's own characters - it is destined for a log
    line and later for a ledger cell, and those characters came off a stranger's
    page (Guardrail #11).
    """

    check: ResolverCheck
    detail: str


class Resolution(NamedTuple):
    """What one plan draws, or the one check that stopped it. Never both.

    `refusal` is `None` and `values` holds the figures, or `refusal` names the
    check and `values` is empty. A plan that declines draws nothing and refuses
    nothing, which is the third state and a fact rather than a failure.
    """

    values: list[DisplayedValue]
    refusal: Refusal | None


def _plain(value: Decimal) -> str:
    """A decimal as the one spelling a payload may carry.

    `normalize` alone turns 4200 into `4.2E+3`, which is the same number and a
    different string, and a committed file may not hold two spellings of one
    value. Formatting it back to positional notation is what makes the round trip
    stable.
    """
    return format(value.normalize(), "f")


def _quantity(element: Element) -> Decimal:
    """What a Tier 1 quantity states, as a number.

    The shape already holds `value` to `QUANTITY_VALUE_PATTERN`, and the
    validator's `no_invented_values` has already re-read it out of the element's
    own characters. So this converts and does not judge.
    """
    if element.value is None:
        raise DerivedValueError(
            ResolverCheck.ELEMENT_STATES_A_VALUE,
            f"{element.element_id} states no value and cannot be drawn",
        )
    try:
        return Decimal(element.value)
    except InvalidOperation as unreadable:  # pragma: no cover - the pattern cannot produce one
        raise DerivedValueError(
            ResolverCheck.ELEMENT_STATES_A_VALUE,
            f"{element.element_id} does not read as a number",
        ) from unreadable


def count(inputs: Sequence[Element], *, lower: Decimal, upper: Decimal) -> DerivedValue:
    """How many of these there are, over the interval they were taken from.

    The value is the length of `inputs`, so the chain re-derives it without
    reading anything else. The bounds are what say why these elements and not
    their siblings - a count with no interval is a count nobody can check the
    membership of.
    """
    if not inputs:
        raise DerivedValueError(
            ResolverCheck.SOMETHING_TO_MEASURE, "a count with no elements counted has no chain"
        )
    return DerivedValue(
        function=DerivedFunction.COUNT,
        version=DERIVED_VALUE_VERSION,
        inputs=[element.element_id for element in inputs],
        value=str(len(inputs)),
        unit=None,
        source_unit=None,
        unit_table_version=None,
        bin_lower=_plain(lower),
        bin_upper=_plain(upper),
    )


def sum_of(inputs: Sequence[Element]) -> DerivedValue:
    """The total of these, every one of which states the same unit.

    The Python name carries a suffix because `sum` is a builtin; the allow-list
    name is `sum` and that is what the chain records.

    A channel measuring two things is not summed. Converting it first is
    `convert`'s job and a second chain, and doing both inside one function would
    produce a total whose chain names a unit none of its inputs was written in.
    """
    if len(inputs) < 2:
        raise DerivedValueError(
            ResolverCheck.TWO_INPUTS_AT_LEAST, "a total of one element is that element"
        )
    units = {element.unit for element in inputs}
    if len(units) != 1:
        stated = sorted(unit or "(no unit)" for unit in units)
        raise DerivedValueError(
            ResolverCheck.ONE_UNIT_ACROSS_INPUTS,
            f"a total needs one unit and these state {stated}",
        )
    return DerivedValue(
        function=DerivedFunction.SUM,
        version=DERIVED_VALUE_VERSION,
        inputs=[element.element_id for element in inputs],
        value=_plain(sum((_quantity(element) for element in inputs), Decimal(0))),
        unit=inputs[0].unit,
        source_unit=None,
        unit_table_version=None,
        bin_lower=None,
        bin_upper=None,
    )


def share_of_declared_whole(part: Element, whole: Sequence[Element]) -> DerivedValue:
    """This part as a percentage of the whole these parts declare.

    The whole is declared by enumeration - these elements and no others - which
    is what the middle word of the name means. A share of a whole nobody declared
    is a share of an assumption, and the assumption never appears in the chain.

    The part comes first in `inputs` and the whole follows, which is why `inputs`
    is ordered. A whole totalling zero is refused rather than divided by.
    """
    if len(whole) < 2:
        raise DerivedValueError(
            ResolverCheck.TWO_INPUTS_AT_LEAST,
            "a whole of one part is that part, and its share is all of it",
        )
    units = {element.unit for element in whole} | {part.unit}
    if len(units) != 1:
        stated = sorted(unit or "(no unit)" for unit in units)
        raise DerivedValueError(
            ResolverCheck.ONE_UNIT_ACROSS_INPUTS,
            f"a share needs one unit and these state {stated}",
        )
    with localcontext() as context:
        context.prec = _SHARE_PRECISION
        total = sum((_quantity(element) for element in whole), Decimal(0))
        try:
            share = _quantity(part) / total * _HUNDRED
        except (DivisionByZero, InvalidOperation) as empty:
            raise DerivedValueError(
                ResolverCheck.WHOLE_IS_NOT_NOTHING,
                "a whole of nothing has no parts to take a share of",
            ) from empty
    return DerivedValue(
        function=DerivedFunction.SHARE_OF_DECLARED_WHOLE,
        version=DERIVED_VALUE_VERSION,
        inputs=[part.element_id] + [element.element_id for element in whole],
        value=_plain(share),
        unit="%",
        source_unit=None,
        unit_table_version=None,
        bin_lower=None,
        bin_upper=None,
    )


def convert(element: Element, *, target: str) -> DerivedValue:
    """This element's figure read against a different unit of the same dimension.

    The one function that reads a table, and the only one whose chain records
    which table. `4,200 tonnes` and `4.2 kt` are one quantity written two ways,
    and until one of them moves they cannot share an axis.

    **A ratio that will not state exactly is refused rather than rounded.** The
    table holds no such pair today, so this fails closed on a table that grows
    rather than on one that exists: precision is declared and declaring it is the
    compiler's, so a rounding decision hidden inside a mark is a digit nobody
    chose.
    """
    source = element.unit
    if source is None:
        raise DerivedValueError(
            ResolverCheck.ELEMENT_STATES_A_UNIT,
            f"{element.element_id} states no unit, so there is nothing to move",
        )
    if not commensurable(source, target):
        raise DerivedValueError(
            ResolverCheck.UNITS_COMMENSURABLE,
            f"{source} and {target} do not measure the same thing",
        )
    if source == target:
        raise DerivedValueError(
            ResolverCheck.TARGET_IS_A_DIFFERENT_UNIT,
            f"{source} and {target} are one unit, and moving it moves nothing",
        )
    from_scale, to_scale = UNIT_DIMENSIONS[source][1], UNIT_DIMENSIONS[target][1]
    moved = _quantity(element) * from_scale / to_scale
    if moved * to_scale != _quantity(element) * from_scale:  # pragma: no cover - exact today
        raise DerivedValueError(
            ResolverCheck.CONVERSION_IS_EXACT,
            f"{source} to {target} does not state exactly, and rounding it here would be a "
            "digit nobody declared",
        )
    return DerivedValue(
        function=DerivedFunction.CONVERT,
        version=DERIVED_VALUE_VERSION,
        inputs=[element.element_id],
        value=_plain(moved),
        unit=target,
        source_unit=source,
        unit_table_version=UNIT_TABLE_VERSION,
        bin_lower=None,
        bin_upper=None,
    )


def bin_edges(values: Sequence[Decimal], *, bins: int) -> list[Decimal]:
    """`bins + 1` equal-width edges over the range these values cover.

    Half-open everywhere except the last bin, which is closed, so the widest value
    has somewhere to go. Half-open throughout and it falls off the end; closed
    throughout and a value on an internal edge is counted twice, and the counts
    stop adding up to the marks.

    How many bins is a `config/` knob and never the model's (row 45). Where the
    edges fall is arithmetic and is here, stamped by `DERIVED_VALUE_VERSION`.

    A set with no spread is refused. Every value in one bin and the rest empty is
    a drawing that says the opposite of what a histogram is for.
    """
    if bins < 2:
        raise DerivedValueError(
            ResolverCheck.BINS_ARE_A_DISTRIBUTION, f"{bins} bins is not a distribution"
        )
    if not values:
        raise DerivedValueError(
            ResolverCheck.SOMETHING_TO_MEASURE, "a histogram of nothing has no range to bin"
        )
    low, high = min(values), max(values)
    if low == high:
        raise DerivedValueError(
            ResolverCheck.VALUES_HAVE_SPREAD,
            "these values have no spread, so there is no distribution to draw",
        )
    with localcontext() as context:
        context.prec = _SHARE_PRECISION
        width = (high - low) / bins
        return [low + width * step for step in range(bins)] + [high]


def _target_unit(elements: Sequence[Element]) -> str | None:
    """Which unit this channel draws in, chosen from its contents and not its order.

    The smallest scale present, and among units sharing that scale the one that
    sorts first. `None` where every entry already agrees, which is the common case
    and the one that needs no arithmetic at all.
    """
    units = {element.unit for element in elements}
    if len(units) < 2:
        return None
    if any(unit is None or unit not in UNIT_DIMENSIONS for unit in units):
        raise DerivedValueError(
            ResolverCheck.UNITS_COMMENSURABLE,
            "this channel mixes units the conversion table does not hold, which "
            "`units_convertible` refuses",
        )
    named = sorted(unit for unit in units if unit is not None)
    return min(named, key=lambda unit: (UNIT_DIMENSIONS[unit][1], unit))


def _channel(role: EncodingRole, elements: Sequence[Element]) -> list[DisplayedValue]:
    """Every mark of one measured channel, moved onto one scale where it has to be.

    **Scale, not spelling.** `tonne` and `t` are two names for one unit, and
    drawing 4,200 of one beside 4,200 of the other moves no quantity - which is
    decision 2's own line, so it is formatting and carries no chain. What earns a
    chain is `4.2 kt` becoming `4,200`, because that is a different number.
    """
    for element in elements[1:]:
        if not commensurable(elements[0].unit, element.unit):
            raise DerivedValueError(
                ResolverCheck.UNITS_COMMENSURABLE,
                f"the {role.value} channel does not measure one thing, which "
                "`units_convertible` refuses",
            )
    target = _target_unit(elements)
    scale = UNIT_DIMENSIONS[target][1] if target is not None else None
    drawn: list[DisplayedValue] = []
    for element in elements:
        moving = (
            target is not None
            and element.unit is not None
            and UNIT_DIMENSIONS[element.unit][1] != scale
        )
        if moving and target is not None:
            drawn.append(
                DisplayedValue(role=role, element_id=None, derived=convert(element, target=target))
            )
        else:
            drawn.append(DisplayedValue(role=role, element_id=element.element_id, derived=None))
    return drawn


def _slices(elements: Sequence[Element]) -> list[DisplayedValue]:
    """A pie's marks: each slice as a share of the whole the slices declare."""
    return [
        DisplayedValue(
            role=EncodingRole.QUANTITY,
            element_id=None,
            derived=share_of_declared_whole(element, elements),
        )
        for element in elements
    ]


def _bars(elements: Sequence[Element], *, bins: int) -> list[DisplayedValue]:
    """A histogram's marks: how many values fall in each bin the config asked for.

    **A bin nothing falls into refuses the drawing.** Its chain would name no
    element, and a mark that resolves to nothing is the one thing this contract
    exists to keep off a page. The caller degrades the item and publishes no
    picture, which is the honest answer when a knob asks for more bins than the
    channel has spread to fill.

    **Two causes, and the refusal says which.** Fewer values than bins leaves a
    bin empty by counting alone, and that is a plan fault `enough_data` names.
    Values that crowd into one end of their own range leave a bin empty with a
    value for every bin, and no validator check makes that refusal - it is the
    resolver's own and it is why this module refuses with a value rather than an
    exception.
    """
    values = [_quantity(element) for element in elements]
    edges = bin_edges(values, bins=bins)
    drawn: list[DisplayedValue] = []
    for step in range(bins):
        low, high = edges[step], edges[step + 1]
        last = step == bins - 1
        inside = [
            element
            for element, value in zip(elements, values, strict=True)
            if low <= value and (value <= high if last else value < high)
        ]
        if not inside:
            short = len(elements) < bins
            raise DerivedValueError(
                ResolverCheck.ENOUGH_VALUES_FOR_BINS if short else ResolverCheck.VALUES_HAVE_SPREAD,
                f"nothing falls between {_plain(low)} and {_plain(high)}: "
                + (
                    f"{len(elements)} values cannot fill {bins} bins"
                    if short
                    else f"these {len(elements)} values crowd into fewer than {bins} bins"
                ),
            )
        drawn.append(
            DisplayedValue(
                role=EncodingRole.BINS,
                element_id=None,
                derived=count(inside, lower=low, upper=high),
            )
        )
    return drawn


def resolve_displayed_values(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> Resolution:
    """Every figure this plan will draw, or the one check that stopped it.

    This is what the row's oracle walks, and it is the boundary a stage calls. A
    plan that declines draws nothing and resolves to nothing, which is a fact
    rather than a failure: empty values and no refusal.

    **It refuses with a value rather than an exception**, because the caller's
    answer is always the same one and it is written in
    `docs/architecture/publishing/visuals.md`: the item publishes with no
    picture and the check that refused it is recorded. Taking a whole day's
    digest off the air to punish one story is the trade `CLAUDE.md` section 1a
    already refuses, and a caller that has to remember a `try` is a caller who
    will one day not.

    Thirteen of the fourteen refusals restate a check `visual_validator` makes,
    so reaching one means a caller resolved a plan it never validated.
    `values_have_spread` is the fourteenth and no validator check makes it - a
    histogram whose values crowd into one end of their own range is a valid plan
    with an empty bar.
    """
    if plan.decision is PlanDecision.NONE:
        return Resolution([], None)
    try:
        return Resolution(_resolved(plan, table, visuals=visuals), None)
    except DerivedValueError as refused:
        return Resolution([], Refusal(refused.check, refused.detail))


def _resolved(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> list[DisplayedValue]:
    """The arithmetic half, which raises. Its one caller turns that into a refusal."""
    known = {element.element_id: element for element in table.elements}
    missing = [cited for cited in plan.element_ids if cited not in known]
    if missing:
        raise DerivedValueError(
            ResolverCheck.ELEMENT_EXISTS,
            f"{missing[0]} is not in the element table, so nothing draws it",
        )
    if plan.type is None or plan.type not in TYPE_RULES:
        named = plan.type.value if plan.type is not None else "(no type)"
        raise DerivedValueError(
            ResolverCheck.TYPE_HAS_ROLE_RULE,
            f"{named} has no role rule, so this build cannot say what it displays",
        )
    filled = {
        role: [known[cited] for cited in ids]
        for role, ids in plan.encodings.filled().items()
    }
    drawn: list[DisplayedValue] = []
    for role in EncodingRole:
        elements = filled.get(role)
        if not elements:
            continue
        if plan.type is VisualType.PIE and role is EncodingRole.QUANTITY:
            drawn += _slices(elements)
        elif plan.type is VisualType.HISTOGRAM and role is EncodingRole.BINS:
            drawn += _bars(elements, bins=visuals.histogram_bins)
        elif role in VALUE_ROLES:
            drawn += _channel(role, elements)
        else:
            drawn += [
                DisplayedValue(role=role, element_id=element.element_id, derived=None)
                for element in elements
            ]
    drawn += [
        DisplayedValue(role=None, element_id=cited, derived=None)
        for cited in list(plan.labels) + list(plan.annotations)
    ]
    return drawn


def derived_value_rate(values: Sequence[DisplayedValue]) -> float | None:
    """What share of these figures code computed rather than the article wrote.

    The narrowness alarm. The closed allow-list and this rate are the only two
    things keeping the derived-value contract narrow, and skipping either loses
    the guarantee unnoticed (P.L22, 12.11 G21) - the list stops a plan asking for
    arithmetic nobody sanctioned, and this says how much of what a reader sees is
    arithmetic at all.

    `None` over an empty set. A rate over nothing is not zero, and a day whose
    planner drew no charts reads as a perfect score under the other convention.
    """
    if not values:
        return None
    return sum(1 for one in values if one.derived is not None) / len(values)


def trusted_data_ratio(values: Sequence[DisplayedValue], table: ElementTable) -> float | None:
    """What share of these figures resolves, against the table they claim to come from.

    The correctness alarm, and the reported face of the rule this whole contract
    is for: a figure resolves when it is a Tier 1 element the article's table
    holds, or a derived value whose every input is one. Below one means something
    is drawn that resolves to nothing.

    The shape already refuses a displayed value with neither leg, so what this
    catches is the leg that points somewhere the table does not go - a resolved
    set carried past the article it was built from.

    `None` over an empty set, for the reason `derived_value_rate` gives.
    """
    if not values:
        return None
    known = {element.element_id for element in table.elements}
    resolved = 0
    for one in values:
        if one.element_id is not None:
            resolved += int(one.element_id in known)
        elif one.derived is not None:
            resolved += int(all(cited in known for cited in one.derived.inputs))
    return resolved / len(values)
