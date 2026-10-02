"""What happened to one item on one UTC day?

Read health through the shared ledger reader. Inspect only the requested day's
trace files, one writer at a time, inside the trace task's configured retention.
Cost depends on that day's rows and trace bytes, never on accumulated history.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path

from pydantic import TypeAdapter

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.retention_files import first_kept_day
from idhazh.ledger.filenames import PRE_IDENTITY_TRACE
from idhazh.telemetry.spans import Span
from idhazh.telemetry.traces import TRACE_SUFFIX, committed_trace_path


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("item_id", help="The exact item id to inspect on the UTC date.")


def _files(state: Path, date: str) -> list[tuple[str, int, str, int, Path]]:
    found: list[tuple[str, int, str, int, Path]] = []
    for path in ledger.path(state, LedgerName.TRACES, date).glob(f"*{TRACE_SUFFIX}"):
        if PRE_IDENTITY_TRACE.fullmatch(path.stem):
            ordinal, shard = path.stem.split("-")
            found.append((f"{date}-{ordinal}", 0, "unknown", int(shard), path))
            continue
        writer = ledger.parse_segment_name(path, suffix=TRACE_SUFFIX)
        expected = committed_trace_path(state, **writer._asdict())
        if path != expected:
            raise ValueError(f"{path.name} names a run outside the requested UTC day")
        found.append((*writer, path))
    return sorted(found)


def _spans(path: Path, trace_id: str) -> list[Span]:
    adapter = TypeAdapter(Span)
    spans: list[Span] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("expected a span object")
                if record.get("trace_id") == trace_id:
                    spans.append(adapter.validate_python(record))
            except ValueError as error:
                raise ValueError(f"{path.name}:{number}: invalid trace record: {error}") from error
    return spans


def _tree(spans: list[Span]) -> Iterator[str]:
    by_id = {span.span_id: span for span in spans}
    if len(by_id) != len(spans):
        raise ValueError("trace contains duplicate span ids in one writer file")
    children: dict[str | None, list[Span]] = {}
    for span in spans:
        children.setdefault(span.parent_id, []).append(span)
    def order(span: Span) -> tuple[str, str]:
        return span.started_at, span.span_id

    roots = sorted(
        (span for span in spans if span.parent_id not in by_id), key=order
    )
    pending = [(span, 0) for span in reversed(roots)]
    visited: set[str] = set()
    while pending:
        span, depth = pending.pop()
        if span.span_id in visited:
            raise ValueError("trace contains a cycle in its parent links")
        visited.add(span.span_id)
        orphan = " (parent absent)" if span.parent_id and span.parent_id not in by_id else ""
        yield (
            f"{'  ' * depth}{span.name.value} [{span.span_id}] "
            f"{span.duration_ms} ms; {span.started_at} UTC{orphan}"
        )
        if span.attributes:
            attributes = json.dumps(dict(span.attributes), sort_keys=True)
            yield f"{'  ' * (depth + 1)}attributes: {attributes}"
        pending.extend(
            (child, depth + 1)
            for child in sorted(children.get(span.span_id, []), key=order, reverse=True)
        )
    if len(visited) != len(spans):
        raise ValueError("trace contains a cycle in its parent links")


def report(
    state: Path,
    *,
    item_id: str,
    date: str,
    config_dir: Path,
    today: date_type | None = None,
) -> Iterator[str]:
    requested = date_type.fromisoformat(date)
    if requested.isoformat() != date:
        raise ValueError("--date takes a YYYY-MM-DD UTC day")
    current = today if today is not None else datetime.now(UTC).date()
    policy = config.load_gardener(config_dir).tasks[LedgerName.TRACES.value]
    first_kept = first_kept_day(
        policy.window, current, days_back=lambda days: current - timedelta(days=days - 1)
    )
    health = [
        row for row in ledger.load_days(state, LedgerName.ITEM_HEALTH, [date], model=ItemHealthRow)
        if row.item_id == item_id
    ]
    yield f"Item {item_id} on {date} UTC"
    for row in sorted(health, key=lambda row: row.run_id):
        yield f"Run {row.run_id}: resolved item-health row; attempt not recorded"
        yield row.model_dump_json(indent=2)
    if not health:
        yield "No item-health row for this item on the requested UTC day."
    if first_kept is not None and requested < first_kept:
        yield (
            f"Trace not read: {date} is outside configured retention "
            f"(first kept day {first_kept.isoformat()} UTC). This does not prove deletion."
        )
        return
    matched_runs: set[str] = set()
    for run_id, attempt, job, shard, path in _files(state, date):
        spans = _spans(path, f"{run_id}-{item_id}")
        if not spans:
            continue
        matched_runs.add(run_id)
        yield (
            f"Run {run_id}, attempt {attempt if attempt else 'unknown'}, "
            f"job {job}, shard {shard}: {path.relative_to(state).as_posix()}"
        )
        yield from _tree(spans)
    for run_id in sorted({row.run_id for row in health} - matched_runs):
        yield f"Run {run_id}: no trace for this item in the requested UTC day's files."
    if not health and not matched_runs:
        yield "No trace for this item in the requested UTC day's files."