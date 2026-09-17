"""Everything that observes this pipeline, one module per question.

`docs/concepts/telemetry.md` owns the concept, and these modules are that page's
own sections: which line a stage logs, how a span opens and nests, where a
finished span goes, what a shard's tree totals, where a committed trace lives,
what one item's terminal state was, and which feed is still worth asking.

`publish/` holds the other half - every projection of those observations a run
writes, behind the one dispatcher that names their order.

The package owns who fills a row, never what the row is. Every shape it produces
is declared in `idhazh.contracts` (Guardrail #3).
"""

from __future__ import annotations

# Re-exported so that no caller outside this package had to change when
# `telemetry.py` became `telemetry/`. Five names no caller outside the package
# ever reached are deliberately absent - `DEGRADED_BUT_DONE`, `FLAT_RECORDS`,
# `INSTRUMENT_CELLS`, `AttrValue` and `refuse_text` - each of which still lives
# in the module that owns it. REMOVAL CONDITION: a name here goes the day its
# last caller outside `idhazh/telemetry/` goes. A re-export that outlives its
# cut-over is a second name for everything (Guardrail #6).
#
# **`record` is the one pre-split name that is not here.** `record.py` owns one
# item's row, and Python binds a submodule onto its package, so re-exporting a
# function under the same name gives `telemetry.record` two meanings decided by
# import order. The function is `telemetry.events.record`, which is where it has
# always been defined.
from idhazh.telemetry.census import (
    census_row,
    classify_item,
    detail_cell,
    is_final,
)
from idhazh.telemetry.events import (
    CENSUS_CELLS,
    ENVELOPE_VERSION,
    RECORD_CELLS,
    EventLevel,
    EventName,
    event,
)
from idhazh.telemetry.rollup import roll_up_spans
from idhazh.telemetry.sinks import (
    CollectingSink,
    FanOut,
    FileSink,
    NullSink,
    langfuse_sink,
)
from idhazh.telemetry.spans import (
    MAX_ATTRIBUTE_CHARS,
    AttrKey,
    OpenSpan,
    Span,
    SpanKind,
    SpanName,
    SpanSink,
    Tracer,
    article_attributes,
    attribute,
    item_attributes,
    summary_attributes,
)
from idhazh.telemetry.traces import (
    TRACES_DIRNAME,
    committed_trace_path,
    committed_trace_relpath,
    trace_date,
)

__all__ = [
    "CENSUS_CELLS",
    "ENVELOPE_VERSION",
    "MAX_ATTRIBUTE_CHARS",
    "RECORD_CELLS",
    "TRACES_DIRNAME",
    "AttrKey",
    "CollectingSink",
    "EventLevel",
    "EventName",
    "FanOut",
    "FileSink",
    "NullSink",
    "OpenSpan",
    "Span",
    "SpanKind",
    "SpanName",
    "SpanSink",
    "Tracer",
    "article_attributes",
    "attribute",
    "census_row",
    "classify_item",
    "committed_trace_path",
    "committed_trace_relpath",
    "detail_cell",
    "event",
    "is_final",
    "item_attributes",
    "langfuse_sink",
    "roll_up_spans",
    "summary_attributes",
    "trace_date",
]
