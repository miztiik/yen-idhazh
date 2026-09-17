"""Where each item-health column comes from, and which ones anything fills.

**An operator script, never a test.** It reads every committed
`state/item-health/` day file to say which columns carry a value, and that read
costs more as the archive grows (CLAUDE.md Guardrail #12) - which section 13
forbids a test to do, and which would put a fuse on the answer besides: a test
asserting a column empty goes red on the day the column first fills, which is a
date on the calendar rather than a change anybody made. So it lives here, where
pytest does not run it, and the tables it prints are pasted into
`docs/architecture/sources/item-health-columns.md` rather than asserted.

Run it from the repository root:

    python backend/utilities/item_health_provenance.py

**What it settles.** Every column of `ItemHealthRow.csv_columns()` is printed
exactly once, under exactly one of the eight groups below, and the run exits 1
when the groups do not partition that list - so a column minted without a group
cannot pass unnoticed, and the pasted table cannot drift into holding a column
twice or dropping one.

**What it does not settle.** Whether the module it names is the RIGHT place to
compute a column. It says one module binds the name, never that one should.
"""

from __future__ import annotations

import ast
import csv
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final, NamedTuple, get_args, get_origin

from idhazh import day_partition
from idhazh.contracts.item_health import RETIRED_CELLS, ItemHealthRow
from idhazh.telemetry.record import ItemRecorder

#: The tree a column's value can be computed in. `backend/utilities/` is not on
#: it: a script that prints a number is not a producer of a census row.
SOURCE_ROOT: Final = "backend/idhazh"

#: The committed archive. Read whole, which is the growing read this file owns.
LEDGER_ROOT: Final = "state/item-health"

#: **The two doors a value uses to become a cell of this row**: the census row's
#: own construction, and the record the work stage emits while it is still
#: running. Naming a column anywhere else is not producing it - `date` is a
#: column on nine other contracts and `tier` is a property of a source, so a
#: scan that counted every use of the word named 37 modules for `date` and said
#: nothing.
ROW_SINK: Final = ItemHealthRow.__name__
RECORD_SINK: Final = ItemRecorder.note.__name__

#: The module that declares the row. It names every column by construction and
#: produces none of them - a contract says what a cell may be, never what it
#: is - so the class rule below would otherwise make it the answer to all 113.
CONTRACT_MODULE: Final = ItemHealthRow.__module__.replace(".", "/") + ".py"


class Group(NamedTuple):
    """One question the row answers, and the columns that answer it."""

    title: str
    question: str
    columns: tuple[str, ...]


#: **The eight questions this row grew by.** It reached 113 columns one
#: question at a time, and a reader meeting the flat list cannot see that.
#: Which question a column serves is editorial - nothing in the contract says
#: it - so the membership is declared here and checked against
#: `ItemHealthRow.csv_columns()` on every run rather than trusted.
GROUPS: Final[tuple[Group, ...]] = (
    Group(
        "Identity",
        "Which item, at which address, from which feed, on which run, and on "
        "whose machine.",
        (
            "version",
            "date",
            "run_id",
            "item_id",
            "url_key",
            "canonical_url",
            "vertical",
            "source_id",
            "shard",
            "job",
        ),
    ),
    Group(
        "What happened to it",
        "Where the item stopped, whether it got there, and what refused it.",
        (
            "stage",
            "outcome",
            "code",
            "http_status",
            "detail",
            "failed_field",
            "failed_rule",
            "recovered",
            "on_front_page",
        ),
    ),
    Group(
        "Why it ran at all",
        "Which term of the score carried this item onto the page. The ranker "
        "computes every term and the plan artifact expires in a day, so "
        "without this copy the only surviving answer is the total.",
        (
            "selection_score",
            "authority_score",
            "tier_score",
            "feed_weight",
            "feed_reliability",
            "lens_bonus",
            "recency_bonus",
            "carriage_step",
            "watchlist_bonus",
            "carried_by",
            "watchlist_hit",
            "tier",
            "source_form",
            "published_at",
            "time_source",
        ),
    ),
    Group(
        "The article",
        "How long the fetched body was, whether a cap cut it, and what its own "
        "numbers say it could carry.",
        (
            "source_chars",
            "source_words",
            "source_words_before_cap",
            "truncation_cap_tokens",
            "span_integrity",
            "elements_found",
            "element_class",
        ),
    ),
    Group(
        "The two model calls",
        "What each call sent, reused and wrote, how fast, under which budget, "
        "and why it stopped. The largest group, because one stage timing could "
        "not say which of the two calls moved.",
        (
            "summary_words",
            "summarize_ms",
            "prefill_ms",
            "decode_ms",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "model_calls",
            "label_kind",
            "label_prefill_ms",
            "label_decode_ms",
            "label_input_tokens",
            "label_output_tokens",
            "label_cached_tokens",
            "summary_kind",
            "summary_prefill_ms",
            "summary_decode_ms",
            "summary_input_tokens",
            "summary_output_tokens",
            "summary_cached_tokens",
            "label_ms",
            "summary_ms",
            "visual_plan_ms",
            "visual_plan_ms_is_estimate",
            "model_wait_ms",
            "visual_plan_tokens_written",
            "label_cache_pct",
            "summary_cache_pct",
            "label_prefill_tokens_per_s",
            "label_decode_tokens_per_s",
            "summary_prefill_tokens_per_s",
            "summary_decode_tokens_per_s",
            "label_finish_reason",
            "summary_finish_reason",
            "label_budget_tokens",
            "summary_budget_tokens",
        ),
    ),
    Group(
        "The item clock",
        "Which part of the item got slower, and what none of the named parts "
        "claimed. `stage_gap_ms` is the one that can catch a step nobody named.",
        (
            "item_started_at",
            "item_ended_at",
            "item_index",
            "shard_item_count",
            "queue_wait_ms",
            "fetch_ms",
            "fetch_connect_ms",
            "fetch_ttfb_ms",
            "robots_ms",
            "retry_count",
            "retry_total_ms",
            "extract_ms",
            "faithfulness_ms",
            "item_total_ms",
            "stage_gap_ms",
        ),
    ),
    Group(
        "The machine",
        "Whether a slower row was a slower runner. A throughput with no "
        "machine beside it is not a measurement (Guardrail #10).",
        (
            "cpu_model",
            "cpu_busy_pct",
            "cpu_busy_max",
            "cpu_busy_min",
            "load_1m",
            "llama_rss_bytes",
            "llama_rss_peak_bytes",
            "python_rss_bytes",
            "cgroup_peak_bytes",
            "slot_id",
            "kv_tokens_at_start",
            "prefix_shared_with_previous",
        ),
    ),
    Group(
        "The run settings",
        "Whether changing a knob helped. Config is committed, but a run reads "
        "its own day's config and git history is not a join key.",
        (
            "model_id",
            "model_quantisation",
            "n_ctx_configured",
            "n_parallel",
            "n_threads",
            "n_batch",
            "max_output_tokens",
            "run_visual_decision",
            "temperature",
        ),
    ),
)


def partition_fault(groups: Sequence[Group], columns: Sequence[str]) -> str | None:
    """What is wrong with the grouping, or None when it is a bijection.

    The oracle. A column in no group is silently missing from the pasted table
    and a column in two groups is silently in it twice, and both read as a
    complete table - which is why this is checked rather than reviewed.
    """
    grouped = [name for group in groups for name in group.columns]
    twice = sorted({name for name in grouped if grouped.count(name) > 1})
    missing = [name for name in columns if name not in grouped]
    stranger = sorted({name for name in grouped if name not in columns})
    faults = []
    if missing:
        faults.append(f"{len(missing)} in no group: {', '.join(missing)}")
    if twice:
        faults.append(f"{len(twice)} in two groups: {', '.join(twice)}")
    if stranger:
        faults.append(f"{len(stranger)} naming no column: {', '.join(stranger)}")
    return "; ".join(faults) if faults else None


def type_name(annotation: object) -> str:
    """The column's type as a person would say it, with the optional stripped.

    Every column but the first ten is nullable, so printing `| None` on a
    hundred rows says nothing and costs a column's width on every one of them.
    """
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    inner = args[0] if len(args) == 1 else annotation
    if get_origin(inner) is Annotated:
        inner = get_args(inner)[0]
    return inner.__name__ if isinstance(inner, type) else str(inner)


def sequence_constants(trees: Iterable[ast.Module]) -> dict[str, frozenset[str]]:
    """Every module-level tuple, list or set of strings, by the name it is under.

    The vocabulary a composed key is allowed to be made of. `CALL_SLOTS` and
    `COST_FIELDS` are the two that matter: twelve per-call columns are spelled
    `f"{slot}_{field}"` and appear in no source file as a literal name.
    """
    out: dict[str, frozenset[str]] = {}
    for tree in trees:
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            else:
                continue
            if not isinstance(node.value, ast.Tuple | ast.List | ast.Set):
                continue
            strings = frozenset(
                part.value
                for part in node.value.elts
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            if not strings:
                continue
            for name in targets:
                out[name] = out.get(name, frozenset()) | strings
    return out


def hole(tokens: Iterable[str]) -> str:
    """The pattern one hole of a composed key may be filled by.

    An empty vocabulary gives a pattern that matches nothing, so a key nobody
    can resolve credits nobody rather than everybody.
    """
    alternatives = "|".join(re.escape(token) for token in sorted(tokens))
    return f"(?:{alternatives})" if alternatives else "(?!)"


def function_tokens(
    node: ast.AST, sequences: Mapping[str, frozenset[str]], fallback: frozenset[str]
) -> frozenset[str]:
    """What a function's composed keys may be made of.

    **The constants the function itself names**, which is what stops a key with
    two holes matching a column it could never have produced: the per-call
    flattener names `CALL_SLOTS` and `COST_FIELDS`, and without this it also
    claimed `max_output_tokens`, because some other module's list holds `max`.
    A function naming no constant fills its holes from the whole tree - one
    spells its slot as a parameter, and a narrower answer there would be no
    answer at all.
    """
    named = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and child.id in sequences
    }
    return frozenset().union(*(sequences[name] for name in named)) if named else fallback


def key_columns(node: ast.expr, filler: str, columns: frozenset[str]) -> set[str]:
    """The column names one key expression can produce.

    A plain string is itself. **A composed key counts for every column the
    composition could have produced**, each hole filled from `filler` - so a
    name it could not have produced is never credited, and one it could have
    is. Anything else resolves to nothing rather than to a guess.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value} & columns
    if not isinstance(node, ast.JoinedStr):
        return set()
    pattern = "".join(
        re.escape(part.value)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
        else filler
        for part in node.values
    )
    return {name for name in columns if re.fullmatch(pattern, name)}


def is_sink(call: ast.Call) -> bool:
    """Does a keyword of this call become a cell of this row?"""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == ROW_SINK
    return isinstance(func, ast.Attribute) and func.attr == RECORD_SINK


def census_dict(node: ast.Dict, filler: str, columns: frozenset[str]) -> set[str]:
    """The columns a dict names, or nothing where it is not a dict of cells.

    **Every named key has to be a column**, which is what tells a bag of cells
    from a dict that happens to hold one - the shard summary's `{"shard": ...,
    "items": ..., "failures": ...}` names a column and is not a row. A `**merge`
    is passed over rather than refused: it says nothing either way.
    """
    named: set[str] = set()
    for key in node.keys:
        if key is None:
            continue
        found = key_columns(key, filler, columns)
        if not found:
            return set()
        named |= found
    return named


def census_class(node: ast.ClassDef, columns: frozenset[str]) -> set[str]:
    """The columns a class names, or nothing where it is not a bag of cells.

    The same test the dict form uses, one level up. `FetchTimings` is five
    fields and five columns, and it hands them to the record as a dict built
    from its own field names - a key no static read can resolve, over values
    nothing else in the tree ever names.
    """
    named: set[str] = set()
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id not in columns:
                return set()
            named.add(statement.target.id)
    return named


def bound_names(node: ast.AST, filler: str, columns: frozenset[str]) -> set[str]:
    """Every column name this subtree puts a value under, on its way into the row.

    Four shapes carry a cell here: a keyword of one of the two sinks, a dict
    whose every key is a column, a store into such a dict by name, and a class
    whose every field is a column. Reading a column binds nothing, and neither
    does using its word for something else.
    """
    out: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and is_sink(child):
            out.update(
                keyword.arg
                for keyword in child.keywords
                if keyword.arg is not None and keyword.arg in columns
            )
        elif isinstance(child, ast.Dict):
            out |= census_dict(child, filler, columns)
        elif isinstance(child, ast.ClassDef):
            out |= census_class(child, columns)
        elif isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Store):
            out |= key_columns(child.slice, filler, columns)
    return out


def module_columns(
    tree: ast.Module, sequences: Mapping[str, frozenset[str]], columns: frozenset[str]
) -> tuple[set[str], dict[str, set[str]]]:
    """Every column this module puts a value under, and the same function by function.

    Function by function because that is the grain a composed key's vocabulary
    is decided at. The per-function answer is also what the landing question
    needs: the row's construction unpacks a helper, and this is that helper.
    """
    everything = frozenset().union(*sequences.values()) if sequences else frozenset()
    found: set[str] = set()
    per_function: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            filler = hole(function_tokens(node, sequences, everything))
            per_function[node.name] = bound_names(node, filler, columns)
            found |= per_function[node.name]
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found |= bound_names(node, hole(everything), columns)
    return found, per_function


def landed_names(
    call: ast.Call, keys_of: Mapping[str, set[str]], columns: frozenset[str]
) -> set[str]:
    """The columns one `ItemHealthRow(...)` construction fills.

    Its own keywords, plus the keys of any `**helper(...)` it unpacks - one
    level, which is what the per-call flattener needs and all anything here does.
    """
    out = {keyword.arg for keyword in call.keywords if keyword.arg is not None}
    for keyword in call.keywords:
        unpacked = keyword.value
        if keyword.arg is None and isinstance(unpacked, ast.Call):
            if isinstance(unpacked.func, ast.Name):
                out |= keys_of.get(unpacked.func.id, set())
    return out & columns


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where one column's value comes from, and whether the archive has any."""

    column: str
    type_name: str
    computed_in: tuple[str, ...]
    lands_in: tuple[str, ...]
    in_archive: bool


class Reading(NamedTuple):
    """One record a column, and the size of the archive they were read against."""

    records: tuple[Provenance, ...]
    rows: int
    files: int


def scan(root: Path, columns: frozenset[str]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Which modules bind each column, and which of them land it in the row.

    Landing is the narrower question and the one worth asking: a column can be
    computed on every item and reach only a log line, which is what most of
    these do. It is answered by following the keywords of the
    `ItemHealthRow(...)` call rather than by naming a writer here, so a second
    construction site would appear on its own.
    """
    trees = {
        path.relative_to(root).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted((root / SOURCE_ROOT).rglob("*.py"))
    }
    sequences = sequence_constants(trees.values())

    computed: dict[str, set[str]] = {name: set() for name in columns}
    lands: dict[str, set[str]] = {name: set() for name in columns}
    for module, tree in trees.items():
        found, keys_of = module_columns(tree, sequences, columns)
        if not module.endswith(CONTRACT_MODULE):
            for name in found:
                computed[name].add(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == ROW_SINK:
                    for name in landed_names(node, keys_of, columns):
                        lands[name].add(module)
    return computed, lands


def archive_columns(root: Path, columns: frozenset[str]) -> tuple[frozenset[str], int, int]:
    """Which columns carry a cell somewhere in the committed ledger.

    **This is the growing read.** It opens every day file under
    `state/item-health/`, so it costs more on a five-year archive than on a
    fresh clone (Guardrail #12). A bounded input cannot answer it: the question
    is whether ANY run has ever written the column, and a window answers only
    for the days inside it - so it would report a column retired last year as
    one nothing was ever wired to write.

    A cell under a retired heading counts for the column that replaced it.
    `ItemHealthRow.from_csv_row` reads those files that way, so a reader does
    see the value, and a report that skipped them would call the column empty.
    """
    seen: set[str] = set()
    rows = 0
    files = 0
    for path in day_partition.day_files(root / LEDGER_ROOT):
        files += 1
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows += 1
                seen.update(RETIRED_CELLS.get(name, name) for name, cell in row.items() if cell)
    return frozenset(seen) & columns, rows, files


def read(root: Path) -> Reading:
    """One record per column, in the contract's own order."""
    columns = ItemHealthRow.csv_columns()
    named = frozenset(columns)
    computed, lands = scan(root, named)
    filled, rows, files = archive_columns(root, named)
    fields = ItemHealthRow.model_fields
    return Reading(
        records=tuple(
            Provenance(
                column=name,
                type_name=type_name(fields[name].annotation),
                computed_in=tuple(sorted(computed[name])),
                lands_in=tuple(sorted(lands[name])),
                in_archive=name in filled,
            )
            for name in columns
        ),
        rows=rows,
        files=files,
    )


def _modules(paths: Sequence[str]) -> str:
    return ", ".join(f"`{path}`" for path in paths) if paths else "-"


def report(root: Path) -> int:
    """Print the tables the doc pastes. Non-zero when the grouping is wrong."""
    columns = ItemHealthRow.csv_columns()
    fault = partition_fault(GROUPS, columns)
    if fault is not None:
        print(f"the eight groups do not cover the contract: {fault}", file=sys.stderr)
        return 1

    reading = read(root)
    records = {record.column: record for record in reading.records}
    filled = sum(1 for record in reading.records if record.in_archive)
    today = datetime.now(UTC).date().isoformat()

    print(f"Generated by `python backend/utilities/{Path(__file__).name}` on {today}.")
    print(
        f"{filled} of {len(columns)} columns carry a value somewhere in the committed "
        f"ledger - {reading.rows:,} rows over {reading.files} day files.\n"
    )
    print("| Group | Columns | The question it answers |")
    print("| --- | --- | --- |")
    for group in GROUPS:
        print(f"| {group.title} | {len(group.columns)} | {group.question} |")

    for group in GROUPS:
        print(f"\n### {group.title}\n")
        print(f"{group.question}\n")
        print("| Column | Type | Computed in | Reaches the row | In the archive |")
        print("| --- | --- | --- | --- | --- |")
        for name in group.columns:
            record = records[name]
            print(
                f"| `{name}` | {record.type_name} | {_modules(record.computed_in)} "
                f"| {_modules(record.lands_in)} | {'yes' if record.in_archive else 'no'} |"
            )
    return 0


def main() -> int:
    return report(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
