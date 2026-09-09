"""What a visual plan may say, held as tables that two stages read.

A plan is a set of references into one article's element table plus three closed
vocabularies, and **two stages read those vocabularies rather than one**. The
validator asks whether a plan holds to them. The resolver asks what a plan that
already holds to them displays. Neither owns the tables, so they live here and
both import them.

That is the whole reason this module exists. The tables sat in
`visual_validator.py` until 2026-09-09 and `derived_values.py` imported five
names out of it, which reads as a later stage borrowing an earlier stage's
constant and is something else. Which units measure the same thing, which roles
a type may fill, which channels are drawn on a measured axis and whether two
units convert are facts about the visual language rather than about validation,
and both stages are consumers of them. A shared vocabulary with no home ends up
in whichever consumer happened to be written first.

**Moving the tables did not move either stamp.** A date-stamp that changes
because a file moved is a date-stamp that lies, which is the same argument that
keeps both of them out of `config/`.

## Neither table is a knob, and neither stamp is one either

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

This module is not a contract and does not belong under `contracts/`: it holds
no persisted shape, it generates no schema, and it imports `idhazh.elements`,
which a contract may not (`CLAUDE.md` section 4). It sits beside the contracts
instead, at the bottom of this subsystem's own graph - it imports two contract
modules and the element reader, and nothing here imports a stage.

Nothing here decides anything about one plan. `commensurable` is the conversion
table's own predicate and both stages ask it; every question about a particular
plan is a check in `visual_validator.py` or a function in `derived_values.py`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, NamedTuple

from idhazh.contracts.element import ElementKind
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.elements import normalise_unit

#: The date-stamp of the role table below - which roles a type may fill. It is
#: not the plan contract's `version`, which says when the *shape* last moved,
#: and it is not `UNIT_TABLE_VERSION`, which stamps the other table. A plan
#: carries the vocabulary it was planned against, and `plan_version_current`
#: compares the two.
PLAN_VOCABULARY_VERSION: Final = "2026-09-09"


class TypeRules(NamedTuple):
    """Which channels a type must fill, may fill, and counts its marks in.

    `marks` names the channel the mark count is read from, which is not always
    the same as the marks themselves. A histogram is the one type where it is
    not: its `bins` channel holds the values being distributed and its marks are
    the bars, `visuals.histogram_bins` of them. `enough_data` carries that.
    """

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
#: what `idhazh.derived_values.convert` reads.
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
