"""Which column type each field of a contract becomes in a columnar ledger file.

The mapping is a literal table, not a fallback chain, and not inferred from the
first row: a nullable column whose first row is null would infer as a null type
and then refuse the second row. An annotation the table does not name raises by
name, so a contract that grows a field this file cannot place stops at the first
write rather than landing a column nobody declared.

The types are named after the arrow types they become, and nothing here imports
the engine. `idhazh.ledger.parquet` is the one module that turns a name into an
engine type, so swapping the engine is a change to that one file.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel


class ColumnType(StrEnum):
    """The column types a contract field can become."""

    STRING = "string"
    INT64 = "int64"
    FLOAT64 = "float64"
    BOOL = "bool"
    #: A tuple of strings, such as the run ids a feed retirement cites as evidence.
    STRING_LIST = "list<string>"


@dataclass(frozen=True, slots=True)
class Column:
    """One column: its name, its type, and whether a row may leave it empty."""

    name: str
    type: ColumnType
    nullable: bool


#: Every plain Python type a field may be declared as, and the column it becomes.
#: A constrained string alias from `contracts/base.py` - a date stamp, a run id,
#: a digest - is a `str` underneath and lands here as one. A date stays a string
#: rather than a date type: it is a stamp a person reads in a diff and in a
#: partition path, and a second type would be a second spelling of one value.
_PLAIN: dict[type, ColumnType] = {
    str: ColumnType.STRING,
    int: ColumnType.INT64,
    float: ColumnType.FLOAT64,
    bool: ColumnType.BOOL,
}


def _unwrapped(annotation: Any) -> Any:
    """The type under any `Annotated[...]` layers, whose metadata is a constraint."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _is_a_string(annotation: Any) -> bool:
    """Whether this annotation is a string underneath: `str`, an alias of it, or a `StrEnum`."""
    bare = _unwrapped(annotation)
    return isinstance(bare, type) and (bare is str or issubclass(bare, StrEnum))


def _column_type(name: str, annotation: Any) -> tuple[ColumnType, bool]:
    """One field's column type and nullability, or a `TypeError` naming the field."""
    bare = _unwrapped(annotation)
    nullable = False
    if get_origin(bare) in (Union, types.UnionType):
        members = [_unwrapped(member) for member in get_args(bare)]
        present = [member for member in members if member is not type(None)]
        nullable = len(present) < len(members)
        if len(present) == 1:
            bare = present[0]
    if get_origin(bare) is tuple:
        held = get_args(bare)
        if len(held) == 2 and held[1] is Ellipsis and _is_a_string(held[0]):
            return ColumnType.STRING_LIST, nullable
    if isinstance(bare, type):
        if bare in _PLAIN:
            return _PLAIN[bare], nullable
        # An enum stays its string value, never a dictionary column: a dictionary
        # encoding is the engine's choice, and this file is read by two engines.
        if issubclass(bare, StrEnum):
            return ColumnType.STRING, nullable
        # An integer enum stays its number, the value its JSON form already carries,
        # so a reader filters on the number a person reads in the contract.
        if issubclass(bare, IntEnum):
            return ColumnType.INT64, nullable
    raise TypeError(
        f"{name} is declared {annotation!r}, which no column type in "
        "idhazh/ledger/arrow_schema.py maps. Add the annotation to the table or "
        "change the field; a column is never inferred from the rows"
    )


def columns_of(model: type[BaseModel]) -> tuple[Column, ...]:
    """Every field of this contract as a column, in the contract's own field order."""
    return tuple(
        Column(name, *_column_type(name, field.annotation))
        for name, field in model.model_fields.items()
    )
