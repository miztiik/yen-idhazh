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

`visuals.min_chart_points`, `visuals.max_chart_points` and
`visuals.histogram_bins` are knobs and are read from `config/` (Rule #6).

The tables the checks read are neither knobs nor this module's:
`idhazh.visual_vocabulary` holds which roles a type may fill, which kinds may
fill a channel, which channels are drawn on a measured axis, which units measure
the same thing, and the two date-stamps over those tables. They are facts about
the visual language rather than about validation, `idhazh.derived_values` reads
them too, and the argument for keeping each of them out of `config/` is written
beside it there.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final, NamedTuple

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.element import Element, ElementTable
from idhazh.contracts.visual import EncodingRole, PlanDecision, VisualPlan, VisualType
from idhazh.elements import read_value
from idhazh.visual_vocabulary import (
    PLAN_VOCABULARY_VERSION,
    ROLE_KINDS,
    TYPE_RULES,
    VALUE_ROLES,
    commensurable,
)


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
    #: The marks fit between the two committed chart-point knobs - and for a
    #: histogram, whose marks are its bins, there is a value for every bin.
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


#: A run of digits with optional thousands separators and a decimal part. What
#: the numerals check reads out of a prose channel, and out of the characters an
#: element was cut from.
_NUMERAL: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")


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

    **A histogram is the one type whose channel does not hold its marks.** Its
    `bins` channel holds the values being distributed, and the marks are the
    bars - `visuals.histogram_bins` of them, the same number for every histogram
    in the run. So whether that many bars is readable is a question about the
    config rather than about a plan, and `VisualsConfig` answers it once at load
    by holding the knob inside this same floor and ceiling. What is left to ask
    of a plan is whether the article gave enough values to fill those bars:
    fewer values than bins leaves a bin empty, `idhazh.derived_values` refuses
    that drawing, and a plan the validator passed should never reach it.
    """
    rules = TYPE_RULES.get(visual_type)
    if rules is None or rules.marks not in filled:
        # A type with no rule, or a required channel left empty, belongs to
        # `roles_valid_for_type`. There is nothing here to count.
        return None
    cited = len(filled[rules.marks])
    if visual_type is VisualType.HISTOGRAM:
        if cited < visuals.histogram_bins:
            return Rejection(
                ValidatorCheck.ENOUGH_DATA,
                f"{cited} values in the {rules.marks.value} channel, against the "
                f"{visuals.histogram_bins} bins they have to fill",
            )
        return None
    if cited < visuals.min_chart_points:
        return Rejection(
            ValidatorCheck.ENOUGH_DATA,
            f"{cited} marks in the {rules.marks.value} channel, against a floor of "
            f"{visuals.min_chart_points}",
        )
    if cited > visuals.max_chart_points:
        return Rejection(
            ValidatorCheck.ENOUGH_DATA,
            f"{cited} marks in the {rules.marks.value} channel, against a ceiling of "
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
