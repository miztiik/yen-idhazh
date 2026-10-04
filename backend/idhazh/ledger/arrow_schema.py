"""Annotation-to-logical-shape rules for the ledger layer.

The mapping is explicit, not inferred from the first row. A contract field can
be a scalar, a list, or a nested struct, and the same recursive tree is what the
PyArrow adapter turns into a native schema. The historical flat column table is
kept for the existing row-ledger code, but the new generic tree is the single
entry point for recursive shapes.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
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
class LogicalField:
    """One field of a nested struct, including its recursive logical type."""

    name: str
    type: LogicalType
    nullable: bool


@dataclass(frozen=True, slots=True)
class LogicalType:
    """A recursive logical tree: scalar, list or struct."""

    kind: str
    scalar: str | None = None
    nullable: bool = False
    item_type: LogicalType | None = None
    item_nullable: bool = False
    fields: tuple[LogicalField, ...] = ()


@dataclass(frozen=True, slots=True)
class Column:
    """One column: its name, its type, and whether a row may leave it empty."""

    name: str
    type: ColumnType | LogicalType
    nullable: bool


#: Every plain Python type a field may be declared as, and the column it becomes.
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


def _field_path(base: str, name: str) -> str:
    """A nested field path like `items[].field` rather than a Python path."""
    return f"{base}.{name}" if base else name


def _with_nullable(logical: LogicalType, nullable: bool) -> LogicalType:
    """In-place nullability on the root value without changing its logical shape."""
    return LogicalType(
        kind=logical.kind,
        scalar=logical.scalar,
        nullable=nullable or logical.nullable,
        item_type=logical.item_type,
        item_nullable=logical.item_nullable,
        fields=logical.fields,
    )


def logical_type_of(
    annotation: Any, *, field_path: str = "root", model_stack: tuple[type[BaseModel], ...] = ()
) -> LogicalType:
    """The logical tree of an annotation, naming the full nested field path on refusal."""
    bare = _unwrapped(annotation)
    if bare is Any or bare is object:
        raise TypeError(f"{field_path} is declared {annotation!r}, and Any/object are unsupported")
    if bare is type(None):
        raise TypeError(
            f"{field_path} is declared {annotation!r}, which is only supported as a union member"
        )

    origin = get_origin(bare)
    if origin in (Union, types.UnionType):
        members = [_unwrapped(member) for member in get_args(bare)]
        present = [member for member in members if member is not type(None)]
        if not present:
            raise TypeError(f"{field_path} is declared {annotation!r}, which is a null-only union")
        model_members = {
            member
            for member in present
            if isinstance(member, type) and issubclass(member, BaseModel)
        }
        if len(model_members) > 1:
            names = ", ".join(sorted(member.__name__ for member in model_members))
            raise TypeError(
                f"{field_path} is declared {annotation!r}, and unions of different "
                f"model types are unsupported ({names})"
            )
        nullable = len(present) < len(members)
        resolved = [
            logical_type_of(member, field_path=field_path, model_stack=model_stack)
            for member in present
        ]
        if len(resolved) == 1:
            return _with_nullable(resolved[0], nullable)
        first = resolved[0]
        for candidate in resolved[1:]:
            if candidate != first:
                raise TypeError(
                    f"{field_path} is declared {annotation!r}, whose non-null members "
                    "do not reduce to the same logical type"
                )
        return _with_nullable(first, nullable)

    if origin in (list, tuple):
        args = get_args(bare)
        if not args:
            raise TypeError(
                f"{field_path} is declared {annotation!r}, and an empty list type is unsupported"
            )
        if origin is tuple:
            if len(args) != 2 or args[1] is not Ellipsis:
                raise TypeError(
                    f"{field_path} is declared {annotation!r}, and fixed tuples are unsupported"
                )
            item_annotation = args[0]
        else:
            item_annotation = args[0]
        item_type = logical_type_of(
            item_annotation, field_path=f"{field_path}[]", model_stack=model_stack
        )
        return LogicalType(
            kind="list",
            item_type=item_type,
            item_nullable=item_type.nullable,
            nullable=False,
        )

    if isinstance(bare, type):
        if bare in _PLAIN:
            return LogicalType(
                kind="scalar",
                scalar={str: "string", int: "int64", float: "float64", bool: "bool"}[bare],
            )
        if issubclass(bare, str):
            return LogicalType(kind="scalar", scalar="string")
        if issubclass(bare, bool):
            return LogicalType(kind="scalar", scalar="bool")
        if issubclass(bare, int):
            return LogicalType(kind="scalar", scalar="int64")
        if issubclass(bare, float):
            return LogicalType(kind="scalar", scalar="float64")
        if issubclass(bare, StrEnum):
            return LogicalType(kind="scalar", scalar="string")
        if issubclass(bare, IntEnum):
            return LogicalType(kind="scalar", scalar="int64")
        if issubclass(bare, BaseModel):
            if bare in model_stack:
                raise TypeError(f"{field_path} is a recursive model reference to {bare.__name__}")
            fields: list[LogicalField] = []
            for name, field in bare.model_fields.items():
                child_path = _field_path(field_path, name)
                child = logical_type_of(
                    field.annotation,
                    field_path=child_path,
                    model_stack=(*model_stack, bare),
                )
                fields.append(LogicalField(name=name, type=child, nullable=child.nullable))
            return LogicalType(kind="struct", fields=tuple(fields))
        if issubclass(bare, Mapping):
            raise TypeError(
                f"{field_path} is declared {annotation!r}, and dictionaries or "
                "mappings are unsupported"
            )
        if issubclass(bare, (set, frozenset)):
            raise TypeError(f"{field_path} is declared {annotation!r}, and sets are unsupported")
        raise TypeError(
            f"{field_path} is declared {annotation!r}, which no logical type in "
            "idhazh/ledger/arrow_schema.py maps"
        )

    if origin in (dict, Mapping):
        raise TypeError(
            f"{field_path} is declared {annotation!r}, and dictionaries or mappings are unsupported"
        )
    if origin in (set, frozenset):
        raise TypeError(f"{field_path} is declared {annotation!r}, and sets are unsupported")
    raise TypeError(
        f"{field_path} is declared {annotation!r}, which no logical type in "
        "idhazh/ledger/arrow_schema.py maps"
    )


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
        elif all(_is_a_string(member) for member in present):
            return ColumnType.STRING, nullable
    if get_origin(bare) is tuple:
        held = get_args(bare)
        if len(held) == 2 and held[1] is Ellipsis and _is_a_string(held[0]):
            return ColumnType.STRING_LIST, nullable
    if isinstance(bare, type):
        if bare in _PLAIN:
            return _PLAIN[bare], nullable
        if issubclass(bare, str):
            return ColumnType.STRING, nullable
        if issubclass(bare, bool):
            return ColumnType.BOOL, nullable
        if issubclass(bare, int):
            return ColumnType.INT64, nullable
        if issubclass(bare, float):
            return ColumnType.FLOAT64, nullable
        if issubclass(bare, StrEnum):
            return ColumnType.STRING, nullable
        if issubclass(bare, IntEnum):
            return ColumnType.INT64, nullable
    raise TypeError(
        f"{name} is declared {annotation!r}, which no column type in "
        "idhazh/ledger/arrow_schema.py maps. Add the annotation to the table or "
        "change the field; a column is never inferred from the rows"
    )


def columns_of(model: type[BaseModel]) -> tuple[Column, ...]:
    """Every field as a legacy flat column where possible, else a recursive tree."""
    columns: list[Column] = []
    for name, field in model.model_fields.items():
        try:
            cell_type, nullable = _column_type(name, field.annotation)
            columns.append(Column(name=name, type=cell_type, nullable=nullable))
        except TypeError:
            logical = logical_type_of(field.annotation, field_path=name)
            columns.append(Column(name=name, type=logical, nullable=logical.nullable))
    return tuple(columns)
