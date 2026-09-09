"""Every check a visual plan must pass, run with no model in the loop.

A plan is a set of references into one article's element table plus three
closed vocabularies. `VisualPlan` guarantees the shape of that - no geometry, no
literal value, no authored text where a reader reads a fact. This module
guarantees the rest, and the rest is where the trust is: an element the article
does not hold, a bar measured in one thing beside a bar measured in another, a
role the type cannot draw, a figure whose own characters do not read as the
figure.

**Nine checks, and each one refuses alone.** That is a design constraint rather
than a testing preference. A validator that reports one string cannot say which
rule fired, so a rule can never be retired, tuned or trusted; and a fixture that
trips three rules at once proves none of them. So every check returns at most
one `Rejection` carrying its own stable name, every check reads only what the
checks before it have already resolved, and `backend/tests/test_visual_validator.py`
holds one fixture per check that trips only that one.

**No check calls a model, and none can.** A judge that shares the failure modes
of the thing judged is not a measurement (`CLAUDE.md` section 0a), so every
answer here is deterministic code over committed data. The test reads this
module's own imports to keep it that way.

**A refusal degrades one item; it never fails a build.** The caller writes the
item with no picture and records the check that refused it (`CLAUDE.md` section
1a). The one invariant in this area that does break a build is the span
invariant, and only on its write side - `docs/architecture/publishing/visuals.md`
carries that ruling and why it is the exception.

## What is in code here, and what is in `config/`

`visuals.min_chart_points` and `visuals.max_chart_points` are knobs and are read
from `config/` (Rule #6). The two tables below are not knobs and are here:

- **Which roles a type may fill** is a relation between two closed vocabularies,
  `VisualType` and `EncodingRole`, both of which are Python enums in
  `contracts/visual.py`. A JSON file cannot reference either, so a copy there
  would be a second spelling that drifts - and "a bar has no bins" is what a bar
  *is* rather than something an operator should be able to edit. A config edit
  that let a bar draw bins would publish a plan no compiler has a template for.
- **Which units measure the same thing** is arithmetic. A kilotonne is a
  thousand tonnes whatever anybody configures. `MAGNITUDE` in `idhazh.elements`
  is the precedent: a magnitude word's multiplier lives in code beside the
  pattern that reads it. The same argument is why its date-stamp is here rather
  than in `config/` as `visuals.unit_table_version`: a stamp an operator can
  edit without editing the table it stamps is a stamp that lies, and every
  derived value that recorded it lies with it.

**Two stamps, one per table, because they answer different questions.**
`PLAN_VOCABULARY_VERSION` is the role table's, and `plan_version_current`
compares a plan against it - so moving it re-plans every item that carries an
older one, which is a model call apiece. `UNIT_TABLE_VERSION` is the conversion
table's, and it is what a derived value's chain records. Folded into one, adding
a unit spelling would cost a re-plan of every in-flight plan, and a reader
auditing a drawn `4.2` would get a stamp that also moves when a bar gains a
legal role.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final, NamedTuple

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.elements import normalise_unit, read_value

#: The date-stamp of the role table below - which roles a type may fill. It is
#: not the plan contract's `version`, which says when the *shape* last moved,
#: and it is not `UNIT_TABLE_VERSION`, which stamps the other table. A plan
#: carries the vocabulary it was planned against, and `plan_version_current`
#: compares the two.
PLAN_VOCABULARY_VERSION: Final = "2026-09-09"


class ValidatorCheck(StrEnum):
    """The nine checks, in the order the validator runs them.

    Each member is the property that must HOLD, not the failure - the same way
    `span_integrity_pass` and `derived_provenance_complete` are named. A caller
    records the member, so this is the vocabulary a later ledger column carries;
    it moves into `contracts/` on the day something persists it.
    """

    #: Every element the plan declares is one the article's table holds.
    ELEMENT_EXISTS = "element_exists"
    #: Each element's kind fits the channel it fills.
    SEMANTICALLY_COMPATIBLE = "semantically_compatible"
    #: Within one measured channel, every unit is convertible or identical.
    UNITS_CONVERTIBLE = "units_convertible"
    #: The filled roles are the ones this type declares.
    ROLES_VALID_FOR_TYPE = "roles_valid_for_type"
    #: The marks fit between the two committed chart-point knobs.
    ENOUGH_DATA = "enough_data"
    #: No element fills one channel twice.
    NO_DUPLICATE_IN_ROLE = "no_duplicate_in_role"
    #: Every drawn figure reads out of the characters the element names.
    NO_INVENTED_VALUES = "no_invented_values"
    #: Every numeral in the prose is one a cited element states.
    NUMERALS_MATCHED = "numerals_matched"
    #: The plan met the vocabulary this build holds.
    PLAN_VERSION_CURRENT = "plan_version_current"


class Rejection(NamedTuple):
    """One check that did not hold, and the smallest fact that says why.

    `detail` is built out of element ids, role names, type names, units and
    digits, and never out of an element's own characters. Those characters came
    off a stranger's page, and a detail is destined for a log line and later for
    a ledger cell (Rule #11).
    """

    check: ValidatorCheck
    detail: str


class TypeRules(NamedTuple):
    """Which channels a type must fill, may fill, and counts its marks in."""

    required: frozenset[EncodingRole]
    optional: frozenset[EncodingRole]
    marks: EncodingRole


_R = EncodingRole
_T = VisualType

#: The eleven types whose channels the nine role descriptions determine. These
#: are grammar-of-graphics forms and the table is not a design choice - a
#: scatter needs two measured axes, a histogram needs bins, a timeline needs a
#: time and something to name each dated point.
TYPE_RULES: Final[dict[VisualType, TypeRules]] = {
    _T.BAR: TypeRules(frozenset({_R.CATEGORY, _R.QUANTITY}), frozenset({_R.SERIES}), _R.QUANTITY),
    _T.DOT: TypeRules(frozenset({_R.CATEGORY, _R.QUANTITY}), frozenset({_R.SERIES}), _R.QUANTITY),
    _T.LINE: TypeRules(frozenset({_R.TIME, _R.QUANTITY}), frozenset({_R.SERIES}), _R.QUANTITY),
    _T.AREA: TypeRules(frozenset({_R.TIME, _R.QUANTITY}), frozenset({_R.SERIES}), _R.QUANTITY),
    _T.SCATTER: TypeRules(
        frozenset({_R.QUANTITY_X, _R.QUANTITY}), frozenset({_R.SERIES, _R.ENTITY}), _R.QUANTITY
    ),
    _T.BUBBLE: TypeRules(
        frozenset({_R.QUANTITY_X, _R.QUANTITY, _R.SIZE}),
        frozenset({_R.SERIES, _R.ENTITY}),
        _R.QUANTITY,
    ),
    _T.SLOPE: TypeRules(
        frozenset({_R.TIME, _R.QUANTITY}), frozenset({_R.SERIES, _R.ENTITY}), _R.QUANTITY
    ),
    _T.STACKED_BAR: TypeRules(
        frozenset({_R.CATEGORY, _R.QUANTITY, _R.SERIES}), frozenset(), _R.QUANTITY
    ),
    _T.PIE: TypeRules(frozenset({_R.CATEGORY, _R.QUANTITY}), frozenset(), _R.QUANTITY),
    _T.HISTOGRAM: TypeRules(frozenset({_R.BINS}), frozenset(), _R.BINS),
    _T.TIMELINE: TypeRules(
        frozenset({_R.TIME, _R.EVENT_LABEL}), frozenset({_R.ENTITY}), _R.TIME
    ),
}

#: The seven whose channels are a design decision rather than a reading of the
#: role names, and the decision belongs to the plan that ships each family:
#: `table` and `flow` to the composition and diagram vocabularies, and the five
#: infographic forms to theirs. Naming them here rather than leaving them out is
#: the whole point - a type in neither set would be waved through by the two
#: per-type checks and drawn with nothing having ruled on it. Until their plans
#: land, a plan naming one is refused and plan 11's ladder downgrades it to a
#: nearer neighbour, which is what "declarable is not renderable" means.
UNRULED_TYPES: Final[frozenset[VisualType]] = frozenset(
    {_T.TABLE, _T.FLOW, _T.COMPARISON, _T.CALLOUT, _T.QUOTECARD, _T.WHOWHAT, _T.KEYFACTS}
)

#: Which element kinds may fill each channel. A channel that measures takes a
#: quantity and nothing else; a channel that names takes something with a name.
ROLE_KINDS: Final[dict[EncodingRole, frozenset[ElementKind]]] = {
    _R.CATEGORY: frozenset({ElementKind.ENTITY, ElementKind.PLACE, ElementKind.DATE}),
    _R.QUANTITY: frozenset({ElementKind.QUANTITY}),
    _R.QUANTITY_X: frozenset({ElementKind.QUANTITY}),
    _R.TIME: frozenset({ElementKind.DATE}),
    _R.SERIES: frozenset({ElementKind.ENTITY, ElementKind.PLACE, ElementKind.DATE}),
    _R.SIZE: frozenset({ElementKind.QUANTITY}),
    _R.BINS: frozenset({ElementKind.QUANTITY}),
    _R.ENTITY: frozenset({ElementKind.ENTITY, ElementKind.PLACE}),
    _R.EVENT_LABEL: frozenset({ElementKind.CLAIM, ElementKind.QUOTE, ElementKind.ENTITY}),
}

#: The channels drawn on a measured axis, which are the ones whose entries have
#: to measure the same thing. `time` is not one: a date carries no unit.
VALUE_ROLES: Final[frozenset[EncodingRole]] = frozenset(
    {_R.QUANTITY, _R.QUANTITY_X, _R.SIZE, _R.BINS}
)

#: The date-stamp of the conversion table below. Separate from
#: `PLAN_VOCABULARY_VERSION` for the reason in the module docstring, and in code
#: rather than in `config/` for the reason beside the table.
UNIT_TABLE_VERSION: Final = "2026-09-09"

_KILO: Final = Decimal(1_000)
_MEGA: Final = Decimal(1_000_000)
_GIGA: Final = Decimal(1_000_000_000)
_TERA: Final = Decimal(1_000_000_000_000)

#: Which units measure the same thing, and how much of the dimension's base one
#: of them is. The dimension is what `units_convertible` reads; the scale is
#: what a conversion will read, and the conversion is row 4's - see the seam
#: note on `_units_convertible`.
#:
#: **It is a closed allow-list and the omissions are the safety.** A unit comes
#: off a stranger's page (Rule #11), so one this table does not name is compared
#: by identity and is never assumed compatible with anything. `m` is absent
#: because it is metres or millions and a guess there is a one-million-fold
#: error on a published bar - the same reason `MAGNITUDE` in `idhazh.elements`
#: omits it. `ton` is absent because short, long and metric tons are three
#: different masses. Currency symbols are absent because joining two of them
#: needs an exchange rate, which is a number no article wrote.
#:
#: Every key is `normalise_unit`-stable, or it is a spelling no producer emits.
UNIT_DIMENSIONS: Final[dict[str, tuple[str, Decimal]]] = {
    "w": ("power", Decimal(1)),
    "watt": ("power", Decimal(1)),
    "kw": ("power", _KILO),
    "kilowatt": ("power", _KILO),
    "mw": ("power", _MEGA),
    "megawatt": ("power", _MEGA),
    "gw": ("power", _GIGA),
    "gigawatt": ("power", _GIGA),
    "tw": ("power", _TERA),
    "terawatt": ("power", _TERA),
    "wh": ("energy", Decimal(1)),
    "kwh": ("energy", _KILO),
    "mwh": ("energy", _MEGA),
    "gwh": ("energy", _GIGA),
    "twh": ("energy", _TERA),
    "g": ("mass", Decimal("0.001")),
    "gram": ("mass", Decimal("0.001")),
    "kg": ("mass", Decimal(1)),
    "kilogram": ("mass", Decimal(1)),
    "t": ("mass", _KILO),
    "tonne": ("mass", _KILO),
    "kt": ("mass", _MEGA),
    "kilotonne": ("mass", _MEGA),
    "mm": ("length", Decimal("0.001")),
    "cm": ("length", Decimal("0.01")),
    "km": ("length", _KILO),
    "kilometre": ("length", _KILO),
    "kilometer": ("length", _KILO),
    "s": ("duration", Decimal(1)),
    "second": ("duration", Decimal(1)),
    "min": ("duration", Decimal(60)),
    "minute": ("duration", Decimal(60)),
    "hr": ("duration", Decimal(3600)),
    "hour": ("duration", Decimal(3600)),
    "day": ("duration", Decimal(86400)),
}

#: A run of digits with optional thousands separators and a decimal part. What
#: the numerals check reads out of a prose channel, and out of the characters an
#: element was cut from.
_NUMERAL: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")


def commensurable(one: str | None, other: str | None) -> bool:
    """Do these two units measure the same thing?

    Identical is the easy half. The other half is why decision 2 kept the word:
    comparing unit strings for equality refuses `4,200 tonnes` beside `4.2 kt`,
    which is the pair a reader most needs joined, and it accepts `tonnes` beside
    `t` only by accident of spelling. Two units are commensurable when they are
    the same string, or when this table names both of them under one dimension.

    A `None` unit is a bare number. It is commensurable with another bare number
    and with nothing else: "4,200" beside "1,200 MW" is not a comparison, it is
    two facts on one axis.
    """
    if one == other:
        return True
    first, second = UNIT_DIMENSIONS.get(one or ""), UNIT_DIMENSIONS.get(other or "")
    return first is not None and second is not None and first[0] == second[0]


def _ascii(text: str) -> str:
    """A unit as it can safely reach a log line and a ledger cell.

    Units are read off fetched bytes, and a currency symbol is not ASCII
    (`CLAUDE.md` section 5). Escaping keeps the unit identifiable without
    putting a stranger's characters into our output verbatim.
    """
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _numerals(text: str) -> set[Decimal]:
    """Every number written in a string, normalised so `4,200` and `4200` are one."""
    found: set[Decimal] = set()
    for match in _NUMERAL.finditer(text):
        try:
            found.add(Decimal(match.group().replace(",", "")))
        except InvalidOperation:  # pragma: no cover - the pattern cannot produce one
            continue
    return found


def _element_exists(plan: VisualPlan, known: Mapping[str, Element]) -> Rejection | None:
    """`element_ids` is the plan's whole element set, so this is the only resolver.

    The contract already refuses a plan whose roles cite an id it never
    declared, so checking the declared list covers every channel, every label
    and every annotation. Every check after this one reads resolved elements
    only, which is what stops one absent element tripping four rules at once.
    """
    missing = [cited for cited in plan.element_ids if cited not in known]
    if not missing:
        return None
    more = f" and {len(missing) - 1} more" if len(missing) > 1 else ""
    return Rejection(
        ValidatorCheck.ELEMENT_EXISTS,
        f"{missing[0]}{more} is not in the element table for {plan.plan_version}",
    )


def _semantically_compatible(drawn: Mapping[EncodingRole, list[Element]]) -> Rejection | None:
    """Does each element's kind fit the channel it fills?

    A quantity drawn on a naming axis is a bar labelled with a number nobody
    wrote a name for; a quote drawn on a measured axis has no height at all.
    This is a `(role, kind)` question. Which roles the *type* may fill is a
    different table and a different check.
    """
    for role, elements in sorted(drawn.items(), key=lambda pair: pair[0].value):
        for element in elements:
            if element.kind not in ROLE_KINDS[role]:
                allowed = ", ".join(sorted(kind.value for kind in ROLE_KINDS[role]))
                return Rejection(
                    ValidatorCheck.SEMANTICALLY_COMPATIBLE,
                    f"{element.element_id} is a {element.kind.value} in the {role.value} "
                    f"channel, which takes {allowed}",
                )
    return None


def _units_convertible(drawn: Mapping[EncodingRole, list[Element]]) -> Rejection | None:
    """Does every entry in one measured channel measure the same thing?

    This is the recorded failure the planner's `same_unit_bars` was written for:
    a small model picked three correct megawatt bars and appended the sector's
    headcount, and an axis labelled from the first bar would state that as a
    comparison. `tests/fixtures/visual-validator/` keeps that case.

    **This check answers whether a conversion is possible, never what it
    produces.** A channel mixing commensurable units passes here and is not
    drawable until something converts it, because drawing 4,200 beside 4.2 on one
    axis is worse than refusing both. `idhazh.derived_values.resolve_displayed_values`
    is what converts it, and it records a chain naming the source unit, the target
    unit and `UNIT_TABLE_VERSION`.
    """
    for role, elements in sorted(drawn.items(), key=lambda pair: pair[0].value):
        if role not in VALUE_ROLES or not elements:
            continue
        base = elements[0]
        for element in elements[1:]:
            if not commensurable(base.unit, element.unit):
                return Rejection(
                    ValidatorCheck.UNITS_CONVERTIBLE,
                    f"the {role.value} channel measures {_ascii(base.unit or '(no unit)')} in "
                    f"{base.element_id} and {_ascii(element.unit or '(no unit)')} in "
                    f"{element.element_id}, which do not convert",
                )
    return None


def _roles_valid_for_type(
    visual_type: VisualType, filled: Mapping[EncodingRole, Sequence[str]]
) -> Rejection | None:
    """Are the filled channels the ones this type declares?

    The schema requires every role to be a key so the decoder cannot skip one,
    and it cannot say "at most four roles for a bar" - which is why this ruling
    was left here. A `bar` carrying `bins` loads and is refused.
    """
    rules = TYPE_RULES.get(visual_type)
    if rules is None:
        return Rejection(
            ValidatorCheck.ROLES_VALID_FOR_TYPE,
            f"{visual_type.value} has no role rule in vocabulary {PLAN_VOCABULARY_VERSION} yet",
        )
    drawn = set(filled)
    if missing := sorted(role.value for role in rules.required - drawn):
        return Rejection(
            ValidatorCheck.ROLES_VALID_FOR_TYPE,
            f"a {visual_type.value} draws its {missing[0]} channel and this plan left it empty",
        )
    if extra := sorted(role.value for role in drawn - rules.required - rules.optional):
        return Rejection(
            ValidatorCheck.ROLES_VALID_FOR_TYPE,
            f"a {visual_type.value} has no {extra[0]} channel",
        )
    return None


def _enough_data(
    visual_type: VisualType,
    filled: Mapping[EncodingRole, Sequence[str]],
    *,
    visuals: VisualsConfig,
) -> Rejection | None:
    """Are there enough marks to be a comparison, and few enough to read?

    Both bounds are `config/` knobs and neither is a number chosen here
    (Rule #6). Below the floor a chart says less than the sentence it sits
    under; above the ceiling it is a table drawn badly.
    """
    rules = TYPE_RULES.get(visual_type)
    if rules is None or rules.marks not in filled:
        # A type with no rule, or a required channel left empty, belongs to
        # `roles_valid_for_type`. There is nothing here to count.
        return None
    marks = len(filled[rules.marks])
    if marks < visuals.min_chart_points:
        return Rejection(
            ValidatorCheck.ENOUGH_DATA,
            f"{marks} marks in the {rules.marks.value} channel, against a floor of "
            f"{visuals.min_chart_points}",
        )
    if marks > visuals.max_chart_points:
        return Rejection(
            ValidatorCheck.ENOUGH_DATA,
            f"{marks} marks in the {rules.marks.value} channel, against a ceiling of "
            f"{visuals.max_chart_points}",
        )
    return None


def _no_duplicate_in_role(filled: Mapping[EncodingRole, Sequence[str]]) -> Rejection | None:
    """Does any element fill one channel twice?

    Without this a model can name one quantity three times, the units all agree
    because they are one unit, the width check passes, and a chart of one number
    under three names publishes - every value true and the comparison invented.
    """
    for role, ids in sorted(filled.items(), key=lambda pair: pair[0].value):
        seen: set[str] = set()
        for cited in ids:
            if cited in seen:
                return Rejection(
                    ValidatorCheck.NO_DUPLICATE_IN_ROLE,
                    f"{cited} fills the {role.value} channel more than once",
                )
            seen.add(cited)
    return None


def _no_invented_values(cited: Sequence[Element]) -> Rejection | None:
    """Does every figure read out of the characters its element names?

    This is the check the whole subsystem exists for, asked of the last thing
    that can still be wrong. The model cannot state a number - no field accepts
    one - and the element table can: `Element` holds `span_excerpt` to the width
    of its span and cannot hold it to the `value` beside it, because the value
    is a reading of those characters. So the consumer about to draw the figure
    re-reads it with the producer's own reader.

    **This is the first leg of a two-leg rule, and it is asked here because it
    is asked of the plan.** Every displayed value resolves either to a Tier 1
    element or to a derived value with a complete provenance chain. A plan cites
    elements and nothing else, so what this check can ask is whether each cited
    element still reads as its own characters. The second leg is asked of the
    resolved set rather than of the plan, by
    `idhazh.derived_values.trusted_data_ratio`, because a derived value does not
    exist until something resolves the plan into figures.
    """
    for element in cited:
        read = read_value(element.kind, element.span_excerpt)
        if read != element.value:
            return Rejection(
                ValidatorCheck.NO_INVENTED_VALUES,
                f"{element.element_id} states {element.value} and its own characters read "
                f"as {read}",
            )
    return None


def _numerals_matched(plan: VisualPlan, cited: Sequence[Element]) -> Rejection | None:
    """Is every numeral in the prose one a cited element states?

    `title`, `caption` and `why` are the three channels the shape could only
    length-bound, because deciding whether a numeral inside one is real needs
    the article's element table and the plan deliberately does not carry it.

    The allowed set is the article's own characters, so a caption quoting a
    figure as the article wrote it passes. A caption that CONVERTED one does
    not: code does the arithmetic and records that it did, and a model that
    reached 3.4 GW from 3,400 MW has written a number the article never did.
    """
    allowed: set[Decimal] = set()
    for element in cited:
        allowed |= _numerals(element.value or "")
        allowed |= _numerals(element.span_excerpt)
    for field, prose in (("title", plan.title), ("caption", plan.caption), ("why", plan.why)):
        if prose is None:
            continue
        unmatched = sorted(_numerals(prose) - allowed)
        if unmatched:
            more = f" and {len(unmatched) - 1} more" if len(unmatched) > 1 else ""
            return Rejection(
                ValidatorCheck.NUMERALS_MATCHED,
                f"{field} states {unmatched[0]}{more}, which no cited element does",
            )
    return None


def _plan_version_current(plan: VisualPlan) -> Rejection | None:
    """Was this plan made against the vocabulary this build holds?

    A comparison rather than an equality, because versions are date-stamps and
    the two directions are different faults with different fixes. Behind, and
    the vocabulary moved after the plan was made, so the item is re-planned.
    Ahead, and the plan came from a build this one cannot read, so nothing here
    can say what it meant.

    `roles_valid_for_type` reads the CURRENT table and would already refuse a
    plan the table no longer allows. This check is for the plan the table still
    allows *by accident* - a role whose meaning moved rather than its legality.
    That is contract drift found rather than drawn.
    """
    if plan.plan_version == PLAN_VOCABULARY_VERSION:
        return None
    where = "behind" if plan.plan_version < PLAN_VOCABULARY_VERSION else "ahead of"
    fix = (
        "re-plan the item"
        if where == "behind"
        else "this build cannot read what it meant"
    )
    return Rejection(
        ValidatorCheck.PLAN_VERSION_CURRENT,
        f"planned against {plan.plan_version}, which is {where} this build's vocabulary "
        f"of {PLAN_VOCABULARY_VERSION} - {fix}",
    )


def validate_plan(
    plan: VisualPlan, table: ElementTable, *, visuals: VisualsConfig
) -> list[Rejection]:
    """Every check, in enum order, at most one rejection each.

    An empty list means the plan may be drawn. Anything else means this item
    publishes with no picture and the caller records which checks refused it -
    a refusal degrades one item and never fails a run (`CLAUDE.md` section 1a).

    Constant cost in the size of one plan and one article's table, both of which
    are capped by the contract and by `elements.max_per_article` (Rule #12).
    """
    rejections: list[Rejection] = []
    if plan.decision is PlanDecision.VISUAL:
        known = {element.element_id: element for element in table.elements}
        filled = plan.encodings.filled()
        drawn = {
            role: [known[cited] for cited in ids if cited in known]
            for role, ids in filled.items()
        }
        cited = [known[one] for one in plan.element_ids if one in known]
        found = [
            _element_exists(plan, known),
            _semantically_compatible(drawn),
            _units_convertible(drawn),
        ]
        # The contract refuses a plan that proposes a visual and states no type,
        # so this narrows rather than branches.
        if plan.type is not None:
            found.append(_roles_valid_for_type(plan.type, filled))
            found.append(_enough_data(plan.type, filled, visuals=visuals))
        found += [
            _no_duplicate_in_role(filled),
            _no_invented_values(cited),
            _numerals_matched(plan, cited),
        ]
        rejections += [rejection for rejection in found if rejection is not None]
    # A plan that declines draws nothing, so eight of the nine have nothing to
    # read. The stamp is still asked: a refusal made against a vocabulary this
    # build does not hold says nothing about this build's vocabulary either.
    if (stamp := _plan_version_current(plan)) is not None:
        rejections.append(stamp)
    return rejections


if set(TYPE_RULES) | UNRULED_TYPES != set(VisualType) or set(TYPE_RULES) & UNRULED_TYPES:
    raise TypeError(
        "every declarable type has a role rule or is named as having none - a type in "
        f"neither is drawn with nothing having ruled on it; unplaced: "
        f"{sorted(member.value for member in set(VisualType) - set(TYPE_RULES) - UNRULED_TYPES)}"
    )
for _type, _rules in TYPE_RULES.items():
    if _rules.marks not in _rules.required:
        raise TypeError(f"{_type.value} counts its marks in a channel it need not fill")
    if _rules.required & _rules.optional:
        raise TypeError(f"{_type.value} declares a channel both required and optional")
if set(ROLE_KINDS) != set(EncodingRole):
    raise TypeError(
        "every channel says which kinds may fill it, or a role is checked by nothing - "
        f"missing: {sorted(role.value for role in set(EncodingRole) - set(ROLE_KINDS))}"
    )
for _role in VALUE_ROLES:
    if ROLE_KINDS[_role] != frozenset({ElementKind.QUANTITY}):
        raise TypeError(f"{_role.value} is drawn on a measured axis, so only a quantity fills it")
#: A spelling `normalise_unit` never produces is an entry no producer can reach,
#: so it is a dead row that reads as cover.
if _unreachable := sorted(unit for unit in UNIT_DIMENSIONS if normalise_unit(unit) != unit):
    raise TypeError(f"no producer emits these unit spellings: {_unreachable}")
