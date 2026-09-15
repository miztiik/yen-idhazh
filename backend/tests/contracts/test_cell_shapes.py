"""Can every CSV cell survive the column that will hold it?

The defect this answers is small and kills a whole shard: a failure detail
carrying a character the column refuses makes the row reporting the failure
raise, so the run loses the evidence AND the item. A helper whose output its own
column can still refuse is not a sanitizer.

Nothing here reads a committed ledger. Every case is built (CLAUDE.md section
13), because a built case carries the character the archive has never produced -
which is the whole population at risk.
"""

from __future__ import annotations

import csv
import importlib
import io
import json
import logging
import os
import pkgutil
import shutil
import subprocess
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Union, get_args, get_origin

import pytest
from conftest import REPO_ROOT
from pydantic import BeforeValidator, StringConstraints, TypeAdapter, ValidationError

import idhazh.contracts as contracts_package
from idhazh.contracts import base
from idhazh.contracts.base import (
    CHARACTER_CLASS_PATTERNS,
    FOLDABLE_PATTERNS,
    Contract,
    column_bounds,
    field_column,
    fit_cell,
)
from idhazh.contracts.public_telemetry import PublicTelemetryRow

pytestmark = pytest.mark.contract


#
# Ten inputs, one per way a cell has been broken or could be. Four of them are
# CSV's own delimiters, four are characters a page chooses and we do not, one is
# a length nobody budgeted for, and the last is the case that made `min_length`
# a live defect rather than a theoretical one.
#
HOSTILE: dict[str, str] = {
    "comma": "unexpected, and then some",
    "double_quote": 'the field said "no"',
    "newline": "first line\nsecond line",
    "tab": "column\tcolumn",
    "em_dash": "the model \u2014 not the runtime \u2014 refused",
    "curly_quote": "the page\u2019s own \u201cheadline\u201d",
    "non_latin": "\u0418\u0437\u0432\u0435\u0441\u0442\u0438\u044f \u0441\u043e\u043e\u0431\u0449\u0430\u0435\u0442",
    "emoji": "shipped \U0001f680 today",
    "very_long": "overlong " * 1200,
    "folds_to_nothing": "\u200b\u200b\u200b",
}

#: What a cell that folded away to nothing says instead. Any non-empty printable
#: string does; these tests care that the column accepts it, not which one it is.
ABSENT = "unprintable"


def _csv_contracts() -> list[type[Contract]]:
    """Every persisted contract that declares CSV columns, found rather than listed.

    Walking the package is the point. A contract added next month is audited the
    day it lands, which a hand-maintained list cannot promise.
    """
    found: list[type[Contract]] = []
    for info in pkgutil.iter_modules(contracts_package.__path__):
        module = importlib.import_module(f"{contracts_package.__name__}.{info.name}")
        for member in vars(module).values():
            if (
                isinstance(member, type)
                and issubclass(member, Contract)
                and member.__module__ == module.__name__
                and hasattr(member, "csv_columns")
            ):
                found.append(member)
    return sorted(found, key=lambda model: model.__name__)


def _carries_text(annotation: Any) -> bool:
    """Does this annotation admit a plain string?

    An enum is excluded even though `StrEnum` members are strings: its members
    are a closed vocabulary this repository writes, so there is no foreign value
    for a fold to rescue.
    """
    pending: list[Any] = [annotation]
    while pending:
        node = pending.pop()
        if node is str:
            return True
        if isinstance(node, type) and issubclass(node, Enum):
            continue
        origin = get_origin(node)
        if origin is Annotated or origin is Union or origin is type(int | str):
            pending.extend(get_args(node))
    return False


def _string_columns() -> Iterator[tuple[type[Contract], str, Any]]:
    """Every string column of every CSV contract, with its whole annotated type."""
    for model in _csv_contracts():
        for name, field in model.model_fields.items():
            column = field_column(field)
            if _carries_text(column):
                yield model, name, column


def _minted_patterns() -> frozenset[str]:
    """The patterns naming an identity this repository mints.

    Read off `contracts.base` rather than written out here. A column whose rule
    is a literal spelled in its own module is invisible to this set, which is
    what makes `test_every_string_column_says_which_kind_it_is` a guarantee
    rather than a list: the column names itself in the failure.
    """
    return frozenset(
        value
        for name, value in vars(base).items()
        if name.endswith("_PATTERN") and isinstance(value, str)
    ) - frozenset(CHARACTER_CLASS_PATTERNS)


def _foldable_columns() -> list[tuple[type[Contract], str, Any]]:
    """Every string column whose rule names a character class or a length."""
    chosen = []
    for model, name, column in _string_columns():
        pattern, minimum, maximum = column_bounds(column)
        if pattern in FOLDABLE_PATTERNS and (
            pattern is not None or minimum is not None or maximum is not None
        ):
            chosen.append((model, name, column))
    return chosen


def _annotation_parts(column: Any) -> list[Any]:
    """Every metadata object on a column, through unions and nested `Annotated`.

    A nullable column is `Annotated[str, ...] | None`, so its constraints sit one
    level down. Reading only the top level finds nothing and makes every test
    below vacuously green, which is the failure this walk exists to prevent.
    """
    found: list[Any] = []
    pending: list[Any] = [column]
    while pending:
        for part in get_args(pending.pop()):
            if isinstance(part, BeforeValidator | StringConstraints):
                found.append(part)
            else:
                pending.append(part)
    return found


def _self_folding_columns() -> list[tuple[type[Contract], str, Any]]:
    """Every string column that folds its own cell, found by the validator it carries."""
    return [
        (model, name, column)
        for model, name, column in _string_columns()
        if any(isinstance(part, BeforeValidator) for part in _annotation_parts(column))
    ]


#
# The structural guarantee. Everything below it is a consequence.
#


def test_every_string_column_says_which_kind_it_is() -> None:
    """A column's rule is either a character class or an identity, and it says which.

    This is what makes the rest of this module a guarantee instead of a list
    somebody maintains. A new constrained string column passes only by declaring
    a pattern `contracts.base` already names - so it is either foldable, and the
    cases below run against it automatically, or it is minted, and its producer
    keeps the refusal it already had. A third kind fails here, naming itself.
    """
    minted = _minted_patterns()
    unclassified = [
        f"{model.__name__}.{name} declares {column_bounds(column)[0]!r}"
        for model, name, column in _string_columns()
        if column_bounds(column)[0] not in FOLDABLE_PATTERNS
        and column_bounds(column)[0] not in minted
    ]

    assert not unclassified, (
        "a string column declares a pattern that is neither a character class nor an identity "
        f"named in idhazh.contracts.base: {unclassified}. Name it in base and this passes."
    )


def test_the_walk_reaches_every_csv_contract() -> None:
    """The walk finding nothing would make every test below vacuously green."""
    models = _csv_contracts()

    assert len(models) >= 20, f"only {len(models)} CSV contracts found; the walk is broken"
    assert len(_foldable_columns()) >= 20, "no constrained string columns found; the walk is broken"
    assert len(_self_folding_columns()) >= 10, "no self-folding columns found; the walk is broken"


def test_the_constraints_are_declared_before_the_fold_and_the_fold_runs_first() -> None:
    """Annotation order is the whole mechanism, and it reads backwards.

    A `BeforeValidator` wraps everything that PRECEDES it in the `Annotated`
    list, so the constraints have to be written first to be checked second.
    Written the other way round they become predicates over a function schema:
    the value is checked before the fold can rescue it, and `pattern` vanishes
    from the generated schema, which would move every `schemas/` file that
    carries such a column. Both halves are pinned, because the second one is the
    one a green test suite would not otherwise notice.
    """
    for model, name, column in _self_folding_columns():
        parts = _annotation_parts(column)
        where = [index for index, part in enumerate(parts) if isinstance(part, BeforeValidator)]
        constrained = [
            index for index, part in enumerate(parts) if isinstance(part, StringConstraints)
        ]
        assert constrained and where, f"{model.__name__}.{name} lost half its annotation"
        assert max(constrained) < min(where), (
            f"{model.__name__}.{name} declares its fold before its constraints, so the "
            "constraints are checked first and the fold can rescue nothing"
        )

        declared = column_bounds(column)[0]
        assert declared is not None, f"{model.__name__}.{name} folds into no character class"
        emitted = TypeAdapter(column).json_schema(mode="validation")
        assert declared in json.dumps(emitted), (
            f"{model.__name__}.{name} no longer emits its pattern; the generated schema moved"
        )

        fitted = TypeAdapter(column).validate_python(HOSTILE["em_dash"])
        assert fitted, f"{model.__name__}.{name} folded a printable value away"
        assert "\u2014" not in fitted, f"{model.__name__}.{name} ran its constraints first"


#: The census columns that hold text somebody else wrote - a kernel file, an
#: environment variable, a runtime's finish reason, a Pydantic message quoting
#: the value it refused. Named here rather than walked, because the point of the
#: two tests below is that the row is built by hand with no helper in the way.
FOREIGN_CENSUS_CELLS: tuple[str, ...] = (
    "detail",
    "time_source",
    "label_finish_reason",
    "summary_finish_reason",
    "cpu_model",
    "runner_name",
    "model_id",
    "model_quantisation",
    "failed_field",
    "failed_rule",
)


def _failed_census_row(**cells: Any) -> Any:
    """One item-health row, built by calling the contract and nothing else."""
    from idhazh.contracts.item_health import (
        FailureCode,
        ItemHealthRow,
        ItemOutcome,
        ItemStage,
    )

    built: dict[str, Any] = {
        "version": ItemHealthRow.schema_version(),
        "date": "2026-09-15",
        "run_id": "2026-09-15-1",
        "item_id": "world-abcdefghjkmnpqrs",
        "url_key": "a" * 64,
        "canonical_url": "https://example.com/a",
        "vertical": "world",
        "source_id": "a-source",
        "stage": ItemStage.SUMMARIZE,
        "outcome": ItemOutcome.FAILED,
        "code": FailureCode.BAD_SHAPE,
    }
    built.update(cells)
    return ItemHealthRow(**built)


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_row_built_by_hand_still_gets_the_fold(case: str) -> None:
    """The column folds, so there is no door a producer can go round.

    This is the arm that says the guarantee is structural. It calls the contract
    directly - no recorder, no writer, no helper - with the value in every column
    that holds text somebody else wrote, and asks for a row back rather than a
    refusal. A helper the producer has to remember can be forgotten; a type
    cannot.
    """
    raw = HOSTILE[case]
    row = _failed_census_row(**dict.fromkeys(FOREIGN_CENSUS_CELLS, raw))

    for name in FOREIGN_CENSUS_CELLS:
        cell = getattr(row, name)
        assert cell, f"{name} folded away to nothing"
        assert len(cell.splitlines()) == 1, f"{name} kept a line break"
        assert cell.isascii(), f"{name} kept a character the column refuses"


def test_a_row_built_by_hand_still_refuses_a_crooked_identity() -> None:
    """Folding an address would invent one, so an identity column keeps its refusal."""
    with pytest.raises(ValidationError, match="item_id"):
        _failed_census_row(item_id="NOT an item id \u2014 at all")

    with pytest.raises(ValidationError, match="url_key"):
        _failed_census_row(url_key="NOT a digest \u2014 at all")



@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_folded_value_is_accepted_by_the_column_it_was_folded_for(case: str) -> None:
    """Whatever the producer had, the column takes what comes out of the fold.

    Every constrained string column, against every case, in one assertion. The
    columns come from the walk, so a column added later is covered without this
    test being edited.
    """
    refused: list[str] = []
    for model, name, column in _foldable_columns():
        fitted = fit_cell(HOSTILE[case], column=column, absent=ABSENT)
        try:
            TypeAdapter(column).validate_python(fitted)
        except ValidationError:
            refused.append(f"{model.__name__}.{name} refused {fitted[:60]!r}")

    assert not refused, refused


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_folded_value_is_never_empty(case: str) -> None:
    """A `min_length=1` column is the live defect, so the floor is tested on its own.

    An empty cell would raise where the row exists to say a failure happened, so
    the fold's floor has to be a string and not the absence of one.
    """
    for model, name, column in _foldable_columns():
        fitted = fit_cell(HOSTILE[case], column=column, absent=ABSENT)
        assert fitted, f"{model.__name__}.{name} folded to nothing"


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_folded_value_is_one_physical_line(case: str) -> None:
    """`state/**/*.csv` merges by union, which resolves one physical line at a time.

    `csv` quotes an embedded newline correctly and the file still gains a line,
    so a union merge stacks half a row against half of somebody else's. The fold
    collapses whitespace before anything else for this reason alone.
    """
    for model, name, column in _foldable_columns():
        fitted = fit_cell(HOSTILE[case], column=column, absent=ABSENT)
        assert len(fitted.splitlines()) == 1, f"{model.__name__}.{name} kept a line break"


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_a_folded_row_round_trips_through_csv(case: str) -> None:
    """Write it, read it back, get the same cells - and the same number of lines."""
    for model, name, column in _foldable_columns():
        fitted = fit_cell(HOSTILE[case], column=column, absent=ABSENT)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["before", "cell", "after"], lineterminator="\n")
        writer.writeheader()
        writer.writerow({"before": "a", "cell": fitted, "after": "b"})
        text = buffer.getvalue()

        assert len(text.splitlines()) == 2, f"{model.__name__}.{name} wrote more than one row"
        read_back = list(csv.DictReader(io.StringIO(text)))
        assert read_back[0]["cell"] == fitted, f"{model.__name__}.{name} did not survive the trip"
        assert read_back[0]["before"] == "a"
        assert read_back[0]["after"] == "b"


def test_the_fold_refuses_a_column_that_names_an_identity() -> None:
    """A fold that satisfied `^[0-9a-f]{64}$` would have invented a digest.

    The refusal is the feature. A cell holding an identity the pipeline minted
    has no foreign value to rescue, and quietly producing something shaped like a
    digest would put a fabricated address in a ledger row.
    """
    minted = [
        column
        for _, _, column in _string_columns()
        if column_bounds(column)[0] in _minted_patterns()
    ]
    assert minted, "no identity columns found; the walk is broken"

    for column in minted:
        with pytest.raises(ValueError, match="names an identity"):
            fit_cell("anything at all", column=column, absent=ABSENT)


#
# The producers. The walk above proves the fold satisfies every column; these
# prove the writers reach the fold.
#


def test_the_failure_detail_writer_fits_its_column() -> None:
    """`detail_cell` is the helper the live defect was in."""
    from idhazh import telemetry
    from idhazh.contracts.item_health import UNSPECIFIED, ItemHealthDetail

    adapter = TypeAdapter(ItemHealthDetail)
    for case, raw in HOSTILE.items():
        cell = telemetry.detail_cell(raw)
        adapter.validate_python(cell)
        assert cell, f"{case} produced an empty detail"
        assert len(cell.splitlines()) == 1, f"{case} produced more than one line"

    assert telemetry.detail_cell("") == UNSPECIFIED
    assert telemetry.detail_cell("   ") == UNSPECIFIED


def test_the_recorder_passes_a_stage_cell_through_untouched() -> None:
    """The recorder folds nothing, because the column does it.

    A record cell is a log line, and the same name on the census row is a column
    that folds its own cell. Folding in both places would be two rules over one
    value, and it was one rule over the wrong value before: the fold lived here
    and the census row was built somewhere that never called it.
    """
    from idhazh import itemrecord, telemetry

    recorder = itemrecord.ItemRecorder(
        run_id="2026-09-15-1",
        flags=itemrecord.Flags(item_lines=False, stage_lines=False),
        now=lambda: "2026-09-15T00:00:00Z",
        log=logging.getLogger("test"),
    )
    recorder.note(cpu_model=HOSTILE["em_dash"], item_id=HOSTILE["curly_quote"])

    assert recorder.get("cpu_model") == HOSTILE["em_dash"]
    assert recorder.get("item_id") == HOSTILE["curly_quote"]
    with pytest.raises(ValueError, match="names no column"):
        recorder.note(not_a_column="anything")
    assert "cpu_model" in telemetry.RECORD_CELLS


def test_the_census_row_fits_every_cell_a_stage_hands_it() -> None:
    """The cells a stage records reach the ledger through the row, and it folds.

    They come from a kernel file, an environment variable, a runtime's finish
    reason and a Pydantic message quoting text it refused - four producers, and
    the column is what covers all of them.
    """
    from idhazh.contracts.item_health import ItemHealthRow

    for case, raw in HOSTILE.items():
        row = _failed_census_row(**dict.fromkeys(FOREIGN_CENSUS_CELLS, raw))
        for name in FOREIGN_CENSUS_CELLS:
            column = field_column(ItemHealthRow.model_fields[name])
            value = getattr(row, name)
            TypeAdapter(column).validate_python(value)
            assert value, f"{case} emptied {name}"


def test_the_recorder_leaves_a_minted_identity_alone() -> None:
    """An item id that arrived wrong stays wrong, and the row still refuses it.

    Folding it would turn a bug in identity into a row that validates and points
    at nothing. `test_a_row_built_by_hand_still_refuses_a_crooked_identity` is
    the other half: the log line keeps the value, and the ledger row raises.
    """
    from idhazh import itemrecord

    crooked = "NOT an item id \u2014 at all"
    recorder = itemrecord.ItemRecorder(
        run_id="2026-09-15-1",
        flags=itemrecord.Flags(item_lines=False, stage_lines=False),
        now=lambda: "2026-09-15T00:00:00Z",
        log=logging.getLogger("test"),
    )
    recorder.note(item_id=crooked, url_key=crooked)

    assert recorder.get("item_id") == crooked
    assert recorder.get("url_key") == crooked


def test_the_processor_name_fits_its_column() -> None:
    """`cpu_model` is read from a kernel file, so nobody chose what is in it.

    `/proc/cpuinfo` is decoded with `errors="replace"`, which mints U+FFFD out of
    any byte that is not valid UTF-8 - a character the column refuses. The
    fallback is `platform.processor()`, which is whatever the OS says and is
    bounded by nothing.
    """
    from idhazh.contracts.runtime_counters import UNPRINTABLE_CPU, RuntimeCountersRow

    for case, raw in HOSTILE.items():
        row = RuntimeCountersRow.from_metrics_text(
            "",
            date="2026-09-15",
            run_id="2026-09-15-1",
            job="work",
            scraped_at="2026-09-15T00:00:00Z",
            shard=0,
            shards=1,
            cpu_model=raw,
        )
        assert row.cpu_model, f"{case} emptied cpu_model"
        assert len(row.cpu_model.splitlines()) == 1

    silent = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-09-15",
        run_id="2026-09-15-1",
        job="work",
        scraped_at="2026-09-15T00:00:00Z",
        shard=0,
        shards=1,
        cpu_model=None,
    )
    assert silent.cpu_model is None, (
        "a probe that reported nothing is not a probe that was unreadable"
    )

    unreadable = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-09-15",
        run_id="2026-09-15-1",
        job="work",
        scraped_at="2026-09-15T00:00:00Z",
        shard=0,
        shards=1,
        cpu_model="\ufffd\ufffd",
    )
    assert unreadable.cpu_model == "??", "two unreadable bytes are two characters, not a verdict"

    blank = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-09-15",
        run_id="2026-09-15-1",
        job="work",
        scraped_at="2026-09-15T00:00:00Z",
        shard=0,
        shards=1,
        cpu_model="\t\t",
    )
    assert blank.cpu_model is None, "whitespace is a probe that said nothing, not an unreadable one"

    nothing_printable = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-09-15",
        run_id="2026-09-15-1",
        job="work",
        scraped_at="2026-09-15T00:00:00Z",
        shard=0,
        shards=1,
        cpu_model="\u0301\u0301",
    )
    assert nothing_printable.cpu_model == UNPRINTABLE_CPU


def test_the_headline_writer_fits_its_column() -> None:
    """An eval row carries the source's own headline, which is a stranger's text."""
    from idhazh.contracts.eval_row import EvalRow

    for case, raw in HOSTILE.items():
        cell = base.fit_field(raw, model=EvalRow, field="title", absent="Untitled item")
        TypeAdapter(field_column(EvalRow.model_fields["title"])).validate_python(cell)
        assert cell, f"{case} emptied the title"


def test_the_feed_detail_writer_fits_its_column() -> None:
    """A feed health detail lands on a published page, so it is fitted before it is written."""
    from idhazh.contracts.feed_health import FeedHealthRow

    for case, raw in HOSTILE.items():
        cell = base.fit_field(raw, model=FeedHealthRow, field="detail", absent="unstated")
        TypeAdapter(field_column(FeedHealthRow.model_fields["detail"])).validate_python(cell)
        assert cell, f"{case} emptied the detail"


def test_the_qualification_ledger_writer_fits_its_columns() -> None:
    """The gate's runner label is an environment variable nobody in this repo wrote."""
    from idhazh.contracts.validation_row import ValidationRow

    for field in ("runner", "detail"):
        column = field_column(ValidationRow.model_fields[field])
        for case, raw in HOSTILE.items():
            cell = base.fit_field(raw, model=ValidationRow, field=field, absent="unstated")
            TypeAdapter(column).validate_python(cell)
            assert cell, f"{case} emptied {field}"


#
# Two parsers read these files: `csv` here, and a state machine in the bundle.
# One fixture, both readers, so they cannot drift apart quietly.
#

_BROWSER_PARSER = REPO_ROOT / "frontend" / "src" / "lib" / "charts" / "series.ts"

_DRIVER = """
import { readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';

registerHooks({
  resolve(specifier, context, next) {
    if (specifier.startsWith('.') && !/\\.[a-z]+$/.test(specifier)) {
      return next(`${specifier}.ts`, context);
    }
    return next(specifier, context);
  }
});

const parser = await import(pathToFileURL(process.argv[2]).href);
const rows = parser.parseTelemetryCsv(readFileSync(process.argv[3], 'utf8'));
process.stdout.write(JSON.stringify(rows.map((row) => row.item_id)));
"""


def test_both_parsers_read_a_folded_shard_to_the_same_cells(tmp_path: Path) -> None:
    """The bundle parses these bytes too, and it wrote its own state machine to do it.

    A cell that Python reads one way and the browser reads another is a defect
    neither side can see. Driving the shipped module rather than a copy of it is
    the only version of this test worth having (Guardrail #7).
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    if not _BROWSER_PARSER.exists():
        pytest.skip("the published bundle's parser is not in this checkout")

    column = field_column(PublicTelemetryRow.model_fields["item_id"])
    expected = [fit_cell(raw, column=column, absent=ABSENT) for raw in HOSTILE.values()]

    names = PublicTelemetryRow.csv_columns()
    shard = tmp_path / "telemetry.csv"
    with shard.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for cell in expected:
            row = dict.fromkeys(names, "")
            row.update(
                date="2026-09-15",
                run_id="2026-09-15-1",
                item_id=cell,
                vertical="ai",
                source_id="lab-blog",
                stage="publish",
                outcome="ok",
            )
            writer.writerow(row)

    text = shard.read_text(encoding="utf-8")
    assert len(text.splitlines()) == len(expected) + 1, "a folded cell split a row in two"
    by_python = [row["item_id"] for row in csv.DictReader(io.StringIO(text))]
    assert by_python == expected

    driver = tmp_path / "read-with-the-bundle.mjs"
    driver.write_text(_DRIVER, encoding="utf-8", newline="\n")
    # Fixed argv, and every path in it is one this test wrote or found.
    finished = subprocess.run(
        [node, "--experimental-strip-types", str(driver), str(_BROWSER_PARSER), str(shard)],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "NODE_OPTIONS": ""},
        check=False,
    )
    if finished.returncode != 0:
        pytest.fail(f"the bundle's parser could not run: {finished.stderr[-2000:]}")

    assert json.loads(finished.stdout) == expected, "the two parsers disagree about these bytes"
