"""Does every field annotation the ledger door can meet map to one declared column type?

The mapping is a literal table, so these tests read the table back through the
public function and name what it refuses. A refusal is the point of half of
them: a column inferred from the rows is how a nullable field whose first value
is null becomes a column that refuses the second row.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import ClassVar, Literal, cast

import pytest
from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Sha256
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.validation_row import ValidationRow
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.ledger.arrow_schema import (
    Column,
    ColumnType,
    LogicalField,
    LogicalType,
    columns_of,
    logical_type_of,
)

pytestmark = pytest.mark.contract


class Colour(StrEnum):
    """A string enum, which is stored as its value."""

    RED = "red"


class Rank(IntEnum):
    """An integer enum, which is stored as its number."""

    FIRST = 1


def _one_field(annotation: object) -> type[Contract]:
    """A contract declaring one field of this annotation, built for the table to read."""
    return cast(
        "type[Contract]",
        type(
            "OneField",
            (Contract,),
            {
                "__annotations__": {"field": annotation},
                "__schema_stem__": "one-field",
                "__changelog__": (
                    ChangelogEntry(
                        version="2026-09-27",
                        change="Initial shape: one field of the annotation under test.",
                        why="The column table is read back one annotation at a time.",
                    ),
                ),
                "__module__": __name__,
            },
        ),
    )


class EveryAnnotation(Contract):
    """One field of every annotation the column table names.

    **A fixture, not a mock** (Guardrail #7): it stands in for nobody and is
    deliberately absent from `contracts.CONTRACTS`.
    """

    __schema_stem__: ClassVar[str] = "every-annotation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-27",
            change="Initial shape: one field of every annotation the column table names.",
            why="The table is proven one row at a time, against a real contract.",
        ),
    )

    date: DateStamp
    digest: Sha256
    words: str
    maybe_words: str | None = None
    count: int
    maybe_count: int | None = None
    share: float
    maybe_share: float | None = None
    flag: bool
    maybe_flag: bool | None = None
    colour: Colour
    maybe_colour: Colour | None = None
    rank: Rank
    maybe_rank: Rank | None = None
    run_ids: tuple[RunId, ...] = Field(default=())
    digest_or_text: Sha256 | str
    maybe_digest_or_text: Sha256 | str | None = None


def test_every_row_of_the_table_maps_to_its_column_and_its_nullability() -> None:
    columns = {column.name: column for column in columns_of(EveryAnnotation)}

    assert columns == {
        "version": Column("version", ColumnType.STRING, nullable=False),
        "date": Column("date", ColumnType.STRING, nullable=False),
        "digest": Column("digest", ColumnType.STRING, nullable=False),
        "words": Column("words", ColumnType.STRING, nullable=False),
        "maybe_words": Column("maybe_words", ColumnType.STRING, nullable=True),
        "count": Column("count", ColumnType.INT64, nullable=False),
        "maybe_count": Column("maybe_count", ColumnType.INT64, nullable=True),
        "share": Column("share", ColumnType.FLOAT64, nullable=False),
        "maybe_share": Column("maybe_share", ColumnType.FLOAT64, nullable=True),
        "flag": Column("flag", ColumnType.BOOL, nullable=False),
        "maybe_flag": Column("maybe_flag", ColumnType.BOOL, nullable=True),
        "colour": Column("colour", ColumnType.STRING, nullable=False),
        "maybe_colour": Column("maybe_colour", ColumnType.STRING, nullable=True),
        "rank": Column("rank", ColumnType.INT64, nullable=False),
        "maybe_rank": Column("maybe_rank", ColumnType.INT64, nullable=True),
        "run_ids": Column("run_ids", ColumnType.STRING_LIST, nullable=False),
        "digest_or_text": Column("digest_or_text", ColumnType.STRING, nullable=False),
        "maybe_digest_or_text": Column("maybe_digest_or_text", ColumnType.STRING, nullable=True),
    }


def test_the_columns_come_in_the_contracts_own_field_order() -> None:
    assert [column.name for column in columns_of(EveryAnnotation)] == list(
        EveryAnnotation.model_fields
    )


@pytest.mark.parametrize(
    "annotation",
    [
        list[str],
        dict[str, str],
        Literal["a", "b"],
        tuple[int, ...],
        tuple[str, str],
        int | str,
        Literal["a"] | str,
    ],
    ids=["list", "dict", "literal", "tuple-of-int", "fixed-tuple", "mixed-union", "literal-union"],
)
def test_an_annotation_the_table_does_not_name_is_refused_by_name(annotation: object) -> None:
    with pytest.raises(TypeError, match=r"field is declared .* no column type"):
        columns_of(_one_field(annotation))


@pytest.mark.parametrize(
    "model",
    [
        VisualPruneRow,
        FeedRetirementRow,
        ItemHealthRow,
        EvalRow,
        HostFingerprintRow,
        CounterfactualScoreRow,
        ValidationRow,
        FeedHealthRow,
        SeenRow,
        PublishedRow,
    ],
)
def test_every_field_of_a_contract_the_door_files_maps(model: type[Contract]) -> None:
    """A ledger moved onto the door must not stop at its first write."""
    assert [column.name for column in columns_of(model)] == list(model.model_fields)


class NestedItem(Contract):
    """A nested model used to prove recursive logical types and arrow schemas."""

    __schema_stem__: ClassVar[str] = "nested-item"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-04",
            change="Initial shape: a nested item for ledger logical-type tests.",
            why="The recursive tree is proven against a real nested contract.",
        ),
    )

    key: str
    count: int | None = None


class OuterRow(Contract):
    """A row with lists, nested models and nullable members."""

    __schema_stem__: ClassVar[str] = "outer-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-04",
            change="Initial shape: list and nested model support for the ledger path.",
            why="A nested row exercises the recursive logical tree under both engines.",
        ),
    )

    title: str
    tags: list[str]
    items: list[NestedItem]
    maybe_item: NestedItem | None = None
    values: tuple[int, ...] = ()
    names: list[str | None]


def test_recursive_logical_tree_maps_expected_shapes() -> None:
    tags = logical_type_of(list[str], field_path="tags")
    assert tags == LogicalType(kind="list", item_type=LogicalType(kind="scalar", scalar="string"), item_nullable=False)

    items = logical_type_of(list[NestedItem], field_path="items")
    assert items.kind == "list"
    assert items.item_type.kind == "struct"
    assert [field.name for field in items.item_type.fields] == ["version", "key", "count"]
    assert items.item_type.fields[2].nullable is True

    maybe_item = logical_type_of(NestedItem | None, field_path="maybe_item")
    assert maybe_item.kind == "struct"
    assert maybe_item.nullable is True

    inner_alias = type("NameAlias", (str,), {})
    assert logical_type_of(inner_alias, field_path="name").kind == "scalar"
    assert logical_type_of(tuple[str, ...], field_path="values") == logical_type_of(list[str], field_path="values")


@pytest.mark.parametrize(
    "annotation",
    [
        dict[str, str],
        tuple[str, str],
        int | str,
        list[dict[str, str]],
        set[str],
    ],
    ids=["dict", "fixed-tuple", "mixed-union", "list-of-dict", "set"],
)
def test_unsupported_annotations_are_refused_with_a_full_path(annotation: object) -> None:
    with pytest.raises(TypeError, match=r"items\[\]"):
        logical_type_of(annotation, field_path="items[]")


def test_recursive_arrow_schema_keeps_nested_nullability() -> None:
    from idhazh.ledger import parquet

    logical = LogicalType(
        kind="list",
        item_type=LogicalType(
            kind="struct",
            fields=(
                LogicalField(name="key", type=LogicalType(kind="scalar", scalar="string"), nullable=False),
                LogicalField(name="count", type=LogicalType(kind="scalar", scalar="int64"), nullable=True),
            ),
        ),
        item_nullable=False,
    )
    schema = parquet._schema([Column("items", logical, nullable=False)], metadata=None)
    field = schema.field("items")
    assert field.nullable is False
    item = field.type
    assert item.value_field.nullable is False
    assert item.value_field.type.field("count").nullable is True
