"""Does the column report name a real producer, and refuse a word that only looks like one?

`ItemHealthRow` has 119 columns and nine other contracts also have a `date`, so
the scan's whole job is telling a module that fills a cell from one that uses
the same word. Every fixture here is a source tree or a day file built under
`tmp_path`. Nothing reads `backend/idhazh/` or the committed archive, which both
grow, so nothing here costs more as they do (CLAUDE.md section 13) - and a built
tree can carry the shape the real one has never produced.

The one exception is the grouping check, which reads `csv_columns()`. That is a
contract and not a collection: it is 119 names today and 119 names on a five
year old clone.
"""

from __future__ import annotations

from pathlib import Path

from idhazh.contracts.item_health import ItemHealthRow
from utilities import item_health_provenance as provenance

COLUMNS = frozenset(
    {
        "date",
        "fetch_ms",
        "label_prefill_ms",
        "summary_prefill_ms",
        "label_kind",
        "summary_kind",
        "max_output_tokens",
        "cpu_busy_pct",
    }
)


def module(root: Path, name: str, source: str) -> None:
    """One module of the built source tree the scan walks."""
    path = root / provenance.SOURCE_ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8", newline="\n")


def day(root: Path, name: str, header: str, *rows: str) -> None:
    """One day file of the built ledger, at the path the walk expects."""
    path = root / provenance.LEDGER_ROOT / "2026" / "09" / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8", newline="\n")


def test_every_column_falls_in_exactly_one_group() -> None:
    """The oracle. A column minted with no group would be missing from the table."""
    assert provenance.partition_fault(provenance.GROUPS, ItemHealthRow.csv_columns()) is None


def test_the_groups_cover_the_contract_and_nothing_else() -> None:
    """Counting is the cheap half; the names are what the pasted table prints."""
    grouped = [name for group in provenance.GROUPS for name in group.columns]

    assert len(grouped) == len(ItemHealthRow.csv_columns())
    assert sorted(grouped) == sorted(ItemHealthRow.csv_columns())


def test_a_column_no_group_holds_is_named() -> None:
    """The failure this exists to catch, driven from a group list we built."""
    groups = (provenance.Group("One", "why", ("date",)),)

    fault = provenance.partition_fault(groups, ("date", "fetch_ms"))

    assert fault is not None
    assert "fetch_ms" in fault


def test_a_column_two_groups_hold_is_named() -> None:
    """A column in two groups reads as a complete table and prints twice."""
    groups = (
        provenance.Group("One", "why", ("date",)),
        provenance.Group("Two", "why", ("date", "fetch_ms")),
    )

    fault = provenance.partition_fault(groups, ("date", "fetch_ms"))

    assert fault is not None
    assert "date" in fault


def test_a_name_no_column_has_is_named() -> None:
    """A renamed column leaves its old name in a group, and the group still counts."""
    groups = (provenance.Group("One", "why", ("date", "retired_ms")),)

    fault = provenance.partition_fault(groups, ("date",))

    assert fault is not None
    assert "retired_ms" in fault


def test_a_module_that_only_uses_the_word_is_not_a_producer(tmp_path: Path) -> None:
    """Nine contracts carry a `date`. Only the one that fills this row counts."""
    module(
        tmp_path,
        "stranger.py",
        "def build():\n    return SomeOtherContract(date='2026-09-15', fetch_ms=1)\n",
    )
    module(
        tmp_path,
        "producer.py",
        "def build(planned):\n    return ItemHealthRow(date=planned.date, fetch_ms=12)\n",
    )

    computed, lands = provenance.scan(tmp_path, COLUMNS)

    assert computed["date"] == {"backend/idhazh/producer.py"}
    assert lands["fetch_ms"] == {"backend/idhazh/producer.py"}


def test_a_record_the_row_never_sees_is_computed_and_not_landed(tmp_path: Path) -> None:
    """The whole point of the report: a cell can be measured and reach no row."""
    module(
        tmp_path,
        "worker.py",
        "def run(recorder):\n    recorder.note(cpu_busy_pct=11.5)\n",
    )

    computed, lands = provenance.scan(tmp_path, COLUMNS)

    assert computed["cpu_busy_pct"] == {"backend/idhazh/worker.py"}
    assert lands["cpu_busy_pct"] == set()


def test_a_dict_of_cells_counts_and_a_dict_that_holds_one_does_not(tmp_path: Path) -> None:
    """A bag of cells is every key a column. One column among strangers is not."""
    module(
        tmp_path,
        "cells.py",
        "def cells():\n"
        "    return {'fetch_ms': 1, 'cpu_busy_pct': 2.0}\n"
        "\n"
        "def summary():\n"
        "    return {'fetch_ms': 1, 'items': 4, 'failures': {}}\n",
    )

    computed, _ = provenance.scan(tmp_path, COLUMNS)

    assert computed["cpu_busy_pct"] == {"backend/idhazh/cells.py"}
    assert computed["fetch_ms"] == {"backend/idhazh/cells.py"}, "the first dict is enough"


def test_a_composed_key_resolves_from_the_constants_its_function_names(tmp_path: Path) -> None:
    """Twelve per-call columns exist in no source file as a literal name.

    `max_output_tokens` is the case that made this rule: some other list holds
    `max`, and a two-hole key filled from the whole tree claimed the column.
    """
    module(
        tmp_path,
        "flatten.py",
        "SLOTS = ('label', 'summary')\n"
        "FIELDS = ('prefill_ms',)\n"
        "OTHER = ('max', 'output_tokens')\n"
        "\n"
        "def flatten(calls):\n"
        "    cells = {}\n"
        "    for slot in SLOTS:\n"
        "        cells[f'{slot}_kind'] = None\n"
        "        for field in FIELDS:\n"
        "            cells[f'{slot}_{field}'] = None\n"
        "    return cells\n",
    )

    computed, _ = provenance.scan(tmp_path, COLUMNS)

    assert computed["label_prefill_ms"] == {"backend/idhazh/flatten.py"}
    assert computed["summary_prefill_ms"] == {"backend/idhazh/flatten.py"}
    assert computed["label_kind"] == {"backend/idhazh/flatten.py"}
    assert computed["max_output_tokens"] == set(), "a name the function could not compose"


def test_a_helper_unpacked_into_the_row_lands_its_keys(tmp_path: Path) -> None:
    """The per-call cells reach the row through a `**helper(...)` and no keyword."""
    module(
        tmp_path,
        "writer.py",
        "SLOTS = ('label',)\n"
        "FIELDS = ('prefill_ms',)\n"
        "\n"
        "def _flatten(calls):\n"
        "    cells = {}\n"
        "    for slot in SLOTS:\n"
        "        for field in FIELDS:\n"
        "            cells[f'{slot}_{field}'] = None\n"
        "    return cells\n"
        "\n"
        "def build(calls):\n"
        "    return ItemHealthRow(date='2026-09-15', **_flatten(calls))\n",
    )

    _, lands = provenance.scan(tmp_path, COLUMNS)

    assert lands["label_prefill_ms"] == {"backend/idhazh/writer.py"}
    assert lands["summary_prefill_ms"] == set(), "the fixture records one slot"


def test_a_class_of_cells_counts_and_the_contract_that_declares_the_row_does_not(
    tmp_path: Path,
) -> None:
    """The fetch timings are five dataclass fields handed over by field name.

    No static read resolves that dict's keys, and the class is the only place
    the five names appear. The contract holds all 119 the same way and fills
    none of them, so it is left out by name.
    """
    module(
        tmp_path,
        "timings.py",
        "class Timings:\n"
        "    fetch_ms: int | None = None\n"
        "    cpu_busy_pct: float | None = None\n"
        "\n"
        "class Something:\n"
        "    fetch_ms: int | None = None\n"
        "    elapsed: int = 0\n",
    )

    computed, _ = provenance.scan(tmp_path, COLUMNS)

    assert computed["cpu_busy_pct"] == {"backend/idhazh/timings.py"}
    assert computed["fetch_ms"] == {"backend/idhazh/timings.py"}, "the first class is enough"


def test_the_module_that_declares_the_row_produces_nothing(tmp_path: Path) -> None:
    """A contract says what a cell may be, never what it is."""
    module(
        tmp_path,
        provenance.CONTRACT_MODULE.removeprefix("idhazh/"),
        "class ItemHealthRow:\n    date: str\n    fetch_ms: int | None = None\n",
    )

    computed, _ = provenance.scan(tmp_path, COLUMNS)

    assert computed["date"] == set()
    assert computed["fetch_ms"] == set()


def test_an_empty_cell_is_not_a_value(tmp_path: Path) -> None:
    """Empty means the run measured nothing, which is the answer the report gives."""
    day(tmp_path, "01", "date,fetch_ms,cpu_busy_pct", "2026-09-01,12,")

    filled, rows, files = provenance.archive_columns(tmp_path, COLUMNS)

    assert filled == {"date", "fetch_ms"}
    assert (rows, files) == (1, 1)


def test_a_retired_heading_counts_for_the_column_that_replaced_it(tmp_path: Path) -> None:
    """Every older day file heads its first call `call_1_*`, and a reader sees it.

    `ItemHealthRow.from_csv_row` maps those headings forward, so a report that
    skipped them would call a filled column empty.
    """
    day(tmp_path, "02", "date,call_1_prefill_ms", "2026-09-02,940")

    filled, _, _ = provenance.archive_columns(tmp_path, COLUMNS)

    assert "label_prefill_ms" in filled


def test_every_day_file_is_read(tmp_path: Path) -> None:
    """The growing read is over the whole tree, so the count has to be the whole tree."""
    day(tmp_path, "03", "date,fetch_ms", "2026-09-03,1")
    day(tmp_path, "04", "date,fetch_ms", "2026-09-04,2", "2026-09-04,3")

    _, rows, files = provenance.archive_columns(tmp_path, COLUMNS)

    assert (rows, files) == (3, 2)


def test_a_missing_ledger_reads_as_nothing(tmp_path: Path) -> None:
    """A fresh clone has no `state/item-health/`, and the report still runs."""
    filled, rows, files = provenance.archive_columns(tmp_path, COLUMNS)

    assert (filled, rows, files) == (frozenset(), 0, 0)


def test_a_type_is_printed_without_its_optional() -> None:
    """A hundred rows saying `| None` cost a column's width and say nothing."""
    fields = ItemHealthRow.model_fields

    assert provenance.type_name(fields["fetch_ms"].annotation) == "int"
    assert provenance.type_name(fields["stage"].annotation) == "ItemStage"
    assert provenance.type_name(fields["date"].annotation) == "str"
