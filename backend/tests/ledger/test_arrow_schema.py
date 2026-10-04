"""Does every field annotation the ledger door can meet map to one declared column type?

The mapping is a literal table, so these tests read the table back through the
public function and name what it refuses. A refusal is the point of half of
them: a column inferred from the rows is how a nullable field whose first value
is null becomes a column that refuses the second row.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, Any, ClassVar, Literal, cast

import pytest
from conftest import REPO_ROOT
from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, RunId, Sha256
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_plan import RunPlan
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
        dict[str, str],
        Literal["a", "b"],
        tuple[str, str],
        int | str,
        Literal["a"] | str,
    ],
    ids=["dict", "literal", "fixed-tuple", "mixed-union", "literal-union"],
)
def test_an_annotation_the_table_does_not_name_is_refused_by_name(annotation: object) -> None:
    with pytest.raises(
        TypeError, match=r"field is declared .* (unsupported|no logical type|do not reduce)"
    ):
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


class NestedItem(Model):
    """A nested model used to prove recursive logical types and arrow schemas."""

    key: str
    count: int | None = None


class NestedDetails(Model):
    """A second nesting level for the struct tree."""

    item: NestedItem


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
    details: NestedDetails
    maybe_item: NestedItem | None = None
    values: tuple[int, ...] = ()
    names: list[str | None]


STRING = LogicalType(kind="scalar", scalar="string")
INT64 = LogicalType(kind="scalar", scalar="int64")


def test_recursive_logical_tree_maps_lists_structs_and_nullability_exactly() -> None:
    nullable_int = LogicalType(kind="scalar", scalar="int64", nullable=True)
    nested_item = LogicalType(
        kind="struct",
        fields=(
            LogicalField(name="key", type=STRING, nullable=False),
            LogicalField(name="count", type=nullable_int, nullable=True),
        ),
    )

    assert logical_type_of(list[str], field_path="OuterRow.tags") == LogicalType(
        kind="list", item_type=STRING, item_nullable=False
    )
    assert logical_type_of(list[NestedItem], field_path="OuterRow.items") == LogicalType(
        kind="list", item_type=nested_item, item_nullable=False
    )
    assert logical_type_of(NestedDetails, field_path="OuterRow.details") == LogicalType(
        kind="struct",
        fields=(
            LogicalField(
                name="item",
                type=nested_item,
                nullable=False,
            ),
        ),
    )
    assert logical_type_of(NestedItem | None, field_path="OuterRow.maybe_item") == LogicalType(
        kind="struct",
        nullable=True,
        fields=nested_item.fields,
    )
    assert logical_type_of(list[int | None], field_path="OuterRow.names") == LogicalType(
        kind="list", item_type=nullable_int, item_nullable=True
    )


def test_recursive_logical_tree_maps_enums_aliases_tuples_and_reduced_unions() -> None:
    constrained = Annotated[str, Field(min_length=1)]

    assert logical_type_of(Colour, field_path="colour") == STRING
    assert logical_type_of(Rank, field_path="rank") == INT64
    assert logical_type_of(DateStamp, field_path="date") == STRING
    assert logical_type_of(constrained, field_path="name") == STRING
    assert logical_type_of(tuple[str, ...], field_path="values") == LogicalType(
        kind="list", item_type=STRING, item_nullable=False
    )
    assert logical_type_of(Sha256 | str, field_path="digest") == STRING


@pytest.mark.parametrize(
    "annotation",
    [
        dict[str, str],
        tuple[str, str],
        int | str,
        list[dict[str, str]],
        set[str],
        Any,
        object,
        complex,
    ],
    ids=[
        "dict",
        "fixed-tuple",
        "mixed-union",
        "list-of-dict",
        "set",
        "any",
        "object",
        "arbitrary-class",
    ],
)
def test_unsupported_annotations_are_refused_with_a_full_path(annotation: object) -> None:
    with pytest.raises(TypeError, match=r"RunPlan\.items\[\]\.field"):
        logical_type_of(annotation, field_path="RunPlan.items[].field")


def test_different_model_types_are_refused_even_when_their_fields_match() -> None:
    class Left(Model):
        value: str

    class Right(Model):
        value: str

    with pytest.raises(TypeError, match=r"RunPlan\.items\[\]\.choice.*different model types"):
        logical_type_of(Left | Right, field_path="RunPlan.items[].choice")


def test_recursive_model_references_are_refused_at_the_full_path() -> None:
    class RecursiveItem(Model):
        children: list[RecursiveItem]

    with pytest.raises(TypeError, match=r"RecursiveItem\.children\[\].*recursive model"):
        logical_type_of(RecursiveItem, field_path="RecursiveItem")


def test_run_plan_maps_through_the_generic_tree() -> None:
    logical = logical_type_of(RunPlan, field_path="RunPlan")
    fields = {field.name: field for field in logical.fields}

    assert fields["items"].type.kind == "list"
    assert fields["items"].type.item_type is not None
    assert fields["items"].type.item_type.kind == "struct"
    assert fields["verticals"].type.kind == "list"
    assert fields["dropped_published_ages"].type.kind == "list"
    assert fields["dropped_published_ages"].nullable is True


def test_recursive_arrow_schema_keeps_nested_nullability() -> None:
    import pyarrow

    from idhazh.ledger import parquet

    columns = (
        Column("tags", logical_type_of(list[str], field_path="OuterRow.tags"), nullable=False),
        Column(
            "items",
            logical_type_of(list[NestedItem | None], field_path="OuterRow.items"),
            nullable=False,
        ),
        Column(
            "maybe_item",
            logical_type_of(NestedItem | None, field_path="OuterRow.maybe_item"),
            nullable=True,
        ),
    )
    schema = parquet._schema(columns, metadata=None)

    assert schema == pyarrow.schema(
        [
            pyarrow.field(
                "tags",
                pyarrow.list_(pyarrow.field("item", pyarrow.string(), nullable=False)),
                nullable=False,
            ),
            pyarrow.field(
                "items",
                pyarrow.list_(
                    pyarrow.field(
                        "item",
                        pyarrow.struct(
                            [
                                pyarrow.field("key", pyarrow.string(), nullable=False),
                                pyarrow.field("count", pyarrow.int64(), nullable=True),
                            ]
                        ),
                        nullable=True,
                    )
                ),
                nullable=False,
            ),
            pyarrow.field(
                "maybe_item",
                pyarrow.struct(
                    [
                        pyarrow.field("key", pyarrow.string(), nullable=False),
                        pyarrow.field("count", pyarrow.int64(), nullable=True),
                    ]
                ),
                nullable=True,
            ),
        ]
    )


def test_ledger_engines_and_door_have_no_run_plan_special_case() -> None:
    paths = [
        REPO_ROOT / "backend" / "idhazh" / "ledger" / name
        for name in ("arrow_schema.py", "parquet.py", "json_lines.py", "persist.py")
    ]

    for path in paths:
        assert "RunPlan" not in path.read_text(encoding="utf-8"), path
