"""A number the article did not write, and the chain that says how code reached it.

Every figure a reader reads off an axis resolves one of two ways. It is a
**Tier 1 element** - the characters the article itself wrote, cut by code at a
span anybody can re-slice - or it is a **derived value**, arithmetic code
performed over Tier 1 elements, carrying a chain back to every one of them.
There is no third way, and `DisplayedValue` is that sentence written as a shape:
exactly one of the two, never both, never neither.

**Four functions, and the list is closed.** `count`, `sum`,
`share_of_declared_whole`, `convert`. Its shortness is the guarantee rather than
a starting point (O45, O47): the model picks the type and points at elements, and
it cannot name a function, cannot supply an operand, and has no numeric field
anywhere in its schema - `contracts/visual.py` refuses to import if it grows one.
So the worst a prompt injection can do is pick the wrong elements. It cannot ask
for arithmetic, and it cannot ask for arithmetic this list does not hold.

**`convert` is a derived value and formatting is not.** `2000000` drawn as `2M`
moves no quantity: same number, different glyphs, and nothing to record.
`4200 tonnes` drawn as `4.2 kt` is a different number against a different unit,
so it carries the full chain (O47, section 7.5). Where the line falls decides
what needs provenance, and running the two together is how a formatting rule
becomes permission to state a figure the article never gave.

**Nothing is lost, which is what makes conversion safe here.** An element's
Tier 1 `span_excerpt` is the article's own characters and is never overwritten.
The axis draws the readable form and the chain carries the original, so a reader
who wants the article's own figure can always be given it.

## What a chain has to name, and why each part of it

`function`, `version` and `inputs` are required on every derived value, because
the oracle for this contract is that a displayed value resolves - and a value
naming its function but not its inputs resolves to nothing an auditor can check.
`inputs` holds Tier 1 element ids and never another derived value: a chain that
nests can be complete at each hop and still name no element at the bottom, and
"every input element" is what the rule asks for.

Three fields are set by one function each and null everywhere else, and the shape
refuses the mismatch rather than leaving it to a reader of the payload:

- `source_unit` and `unit_table_version` belong to `convert`, and they are the
  two facts a later build needs to redo the move: what it came from, and which
  table said the two measure the same thing. `unit` is the target unit, so there
  is no second spelling of it.
- `bin_lower` and `bin_upper` belong to a binned `count`, and they are what makes
  the count re-derivable: the inputs say what was counted and the bounds say why
  those and not their siblings.

## No schema stem, and that is a decision rather than an omission

These are `Model`s and not `Contract`s, so `python -m idhazh.contracts.export`
writes no `schemas/derived-value.schema.json`. The stem belongs to the payload
that *carries* a resolved set, and that payload is the compiler's - it does not
exist yet. Minting one now would mean a committed fixture standing in for a
writer nobody has built, which is the "field nobody writes" defect one level up.
The shapes land here ahead of their producer because contracts come before logic
(Guardrail #3) and because `contracts/` is where a shape lives, not because something
persists one today.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import Model, SchemaVersion
from idhazh.contracts.element import (
    QUANTITY_VALUE_PATTERN,
    UNIT_MAX_LENGTH,
    VALUE_MAX_LENGTH,
    ElementId,
)
from idhazh.contracts.visual import MAX_IDS_PER_ROLE, EncodingRole

#: The closed allow-list, written down as strings as well as declared as an enum.
#: The enum is what a payload is held to; this is what the enum is held to, and
#: the module raises at import if the two disagree. A fifth function is not a
#: widening somebody can make quietly - it is a failing import with this constant
#: named in the message.
ALLOW_LIST: Final[frozenset[str]] = frozenset(
    {"count", "sum", "share_of_declared_whole", "convert"}
)

#: How many Tier 1 elements one derived value may read. A share reads its part
#: plus every element of the whole, and a channel holds at most
#: `MAX_IDS_PER_ROLE`, so this is that plus the part. Tied to the channel width
#: rather than typed here, so a cap rise moves both (Guardrail #6).
MAX_DERIVED_INPUTS: Final = MAX_IDS_PER_ROLE + 1

#: A derived value is written the one way a Tier 1 quantity is: a decimal pinned
#: as text, so no float formatting can drift under a committed file. Wider than
#: `VALUE_MAX_LENGTH` is not needed - a share carries the most digits of the four
#: and it is a division at a fixed 28-digit context.
DerivedNumber = Annotated[
    str, StringConstraints(pattern=QUANTITY_VALUE_PATTERN, max_length=VALUE_MAX_LENGTH)
]
DerivedUnit = Annotated[str, StringConstraints(min_length=1, max_length=UNIT_MAX_LENGTH)]


class DerivedFunction(StrEnum):
    """The four ways code may reach a number the article did not write.

    Each member's arithmetic is defined by the implementation of the same name in
    `idhazh.derived_values`, and `inputs` is ordered because two of them read the
    order: a share's part comes first and its whole follows.
    """

    #: How many of the input elements there are. Unitless - a count of things
    #: measures nothing - and the value is the length of `inputs`.
    COUNT = "count"
    #: The total of the inputs, every one of which states the same unit. A
    #: channel measuring two things is converted first or it is not summed.
    SUM = "sum"
    #: `inputs[0]` as a percentage of the total of every input. The whole is
    #: declared by enumeration - these parts and no others - which is what the
    #: middle word means. A share of a whole nobody declared is a share of an
    #: assumption.
    SHARE_OF_DECLARED_WHOLE = "share_of_declared_whole"
    #: One input read against a different unit of the same dimension. The only
    #: member that reads a table, and the only one that records which table.
    CONVERT = "convert"


class DerivedValue(Model):
    """One number code computed, and the complete chain back to what it read."""

    function: DerivedFunction = Field(
        description="Which of the four. Closed, and a name outside the list does not load."
    )
    version: SchemaVersion = Field(
        description=(
            "The date-stamp of the arithmetic that produced this value - the four "
            "functions and the binning rule. Stamped by code, so a later build can say "
            "whether this number would come out the same today."
        )
    )
    inputs: list[ElementId] = Field(
        min_length=1,
        max_length=MAX_DERIVED_INPUTS,
        description=(
            "Every Tier 1 element this value read, in the order the function reads them. "
            "Element ids and never another derived value: a chain that nests can be "
            "complete at each hop and still name no element at the bottom."
        ),
    )
    value: DerivedNumber = Field(
        description="What code computed, as a decimal pinned to text the way a Tier 1 value is."
    )
    unit: DerivedUnit | None = Field(
        description=(
            "What this value measures, which for a conversion is the target unit. Null "
            "on a count, because a count of things measures nothing."
        )
    )
    source_unit: DerivedUnit | None = Field(
        description="What a conversion moved from. Null on the other three."
    )
    unit_table_version: SchemaVersion | None = Field(
        description=(
            "The date-stamp of the table that said the two units measure the same thing. "
            "Null on the other three, because they read no table."
        )
    )
    bin_lower: DerivedNumber | None = Field(
        description="The inclusive floor of the bin a count was taken over. Null off a histogram."
    )
    bin_upper: DerivedNumber | None = Field(
        description="The ceiling of that bin. Null off a histogram."
    )

    @model_validator(mode="after")
    def _each_function_carries_its_own_fields_and_no_others(self) -> Self:
        """A field set by the wrong function is a chain saying something it did not do.

        Left unchecked, a `sum` carrying a `source_unit` reads as a converted
        total, and nothing downstream can tell it from one.
        """
        converting = self.function is DerivedFunction.CONVERT
        if converting:
            if len(self.inputs) != 1:
                raise ValueError("a conversion moves one value, so it reads one element")
            if self.source_unit is None or self.unit is None:
                raise ValueError("a conversion records the unit it came from and the one it is in")
            if self.source_unit == self.unit:
                raise ValueError("a conversion between one unit and itself moved nothing")
            if self.unit_table_version is None:
                raise ValueError("a conversion records the table that said the two are one thing")
        elif self.source_unit is not None or self.unit_table_version is not None:
            raise ValueError(f"only a conversion reads a unit table, and this is a {self.function}")
        if self.function is DerivedFunction.COUNT and self.unit is not None:
            raise ValueError("a count of things measures nothing, so it states no unit")
        if self.function is DerivedFunction.SHARE_OF_DECLARED_WHOLE:
            if len(self.inputs) < 2:
                raise ValueError("a share names its part and the parts that make the whole")
            if self.unit != "%":
                raise ValueError("a share of a declared whole is a percentage")
        if self.function is DerivedFunction.SUM and len(self.inputs) < 2:
            raise ValueError("a total of one element is that element")
        bounded = (self.bin_lower is None, self.bin_upper is None)
        if len(set(bounded)) != 1:
            raise ValueError("a bin has a floor and a ceiling, or it has neither")
        if not bounded[0] and self.function is not DerivedFunction.COUNT:
            raise ValueError("only a binned count is taken over an interval")
        return self


class DisplayedValue(Model):
    """One figure a reader will read, and the one of two ways it resolves.

    Exactly one of `element_id` and `derived` is set. Written as two optional
    fields with no rule, "neither" is a payload somebody can write and the oracle
    becomes a test of whether anybody wrote one; written as a rule, a value that
    resolves to nothing does not load and the walk over a plan proves the
    resolver never reaches for the exception.
    """

    role: EncodingRole | None = Field(
        description=(
            "The channel this value is drawn in, or null where it names a mark or marks "
            "one out - `labels` and `annotations` are not channels."
        )
    )
    element_id: ElementId | None = Field(
        description=(
            "The Tier 1 element whose own characters are drawn. The characters are not "
            "copied here: the element holds them, and a second copy is a copy that can "
            "disagree."
        )
    )
    derived: DerivedValue | None = Field(
        description="The arithmetic and its chain, where no element states the figure drawn."
    )

    @model_validator(mode="after")
    def _one_of_the_two_ways_and_only_one(self) -> Self:
        if (self.element_id is None) == (self.derived is None):
            raise ValueError(
                "a displayed value is an element the article wrote or a derived value with "
                "a chain - never both, and never neither"
            )
        return self


if {member.value for member in DerivedFunction} != ALLOW_LIST:
    raise TypeError(
        "the allow-list is closed and its shortness is the guarantee (O45, O47) - "
        f"ALLOW_LIST holds {sorted(ALLOW_LIST)} and DerivedFunction declares "
        f"{sorted(member.value for member in DerivedFunction)}. A fifth function is not "
        "this contract's to add; it is an owner decision, because the list being short is "
        "the whole argument that a plan cannot ask for arbitrary arithmetic"
    )
