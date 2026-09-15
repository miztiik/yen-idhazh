"""What does one shard's finished span tree total?

The fold that turns a shard's spans into the committed record under
`state/span-rollup/`. It commits five span names and not the eleven the tracer
opens - the five `RollupSpan` names, which are the steps no ledger column
already times (`contracts.span_rollup`, `docs/concepts/telemetry.md`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.telemetry.spans import Span, SpanName

#: The five spans committed to `state/span-rollup`, as `SpanName` members. Derived
#: from the contract's `RollupSpan` so that enum is the one place the committed
#: set is written down; the `SpanName(member.value)` lookup also fails at import
#: if a committed name ever stops naming a real span.
_COMMITTED_SPANS: Final[frozenset[SpanName]] = frozenset(
    SpanName(member.value) for member in RollupSpan
)


def roll_up_spans(
    spans: Iterable[Span], *, date: str, run_id: str, shard: int, wall_clock_ms: int
) -> list[SpanRollupRow]:
    """Fold one shard's finished spans to one row per committed span name.

    Only the five spans `state/span-rollup` commits are kept; the other six each
    have a ledger column that already times them, so a row here would restate a
    number a ledger holds. A name the shard never opened produces no row rather
    than a zero row. The rows come back in `RollupSpan` order, so a shard appends
    the same bytes in the same order on every run.

    The shard supplies its own `date`, `run_id`, `shard` and `wall_clock_ms`. The
    sub-step spans do not carry them, so the fold reads the identity and the wall
    clock from the caller rather than guessing them from whichever span happens to
    hold an attribute.

    Every second of the shard is accounted for. `wall_clock_ms` is how long the
    shard ran; the item spans are its top-level spans; and `unattributed_ms`,
    `wall_clock_ms` minus the item spans added together, is the overhead between
    and around items that no span covers. It is carried on the `item` row, the one
    row a working shard always produces. A set of spans that claims more time than
    the shard had is unreconcilable and raises rather than rounding to zero.
    """
    counts: dict[SpanName, int] = {}
    totals: dict[SpanName, int] = {}
    for span in spans:
        if span.name not in _COMMITTED_SPANS:
            continue
        counts[span.name] = counts.get(span.name, 0) + 1
        totals[span.name] = totals.get(span.name, 0) + span.duration_ms
    item_ms = totals.get(SpanName.ITEM, 0)
    unattributed_ms = wall_clock_ms - item_ms
    if unattributed_ms < 0:
        raise ValueError(
            f"the shard's item spans claim {item_ms} ms but the shard ran for "
            f"{wall_clock_ms} ms; the item spans overlap or the wall clock is wrong"
        )
    rows: list[SpanRollupRow] = []
    for member in RollupSpan:
        name = SpanName(member.value)
        if name not in counts:
            continue
        rows.append(
            SpanRollupRow(
                version=SpanRollupRow.schema_version(),
                date=date,
                run_id=run_id,
                shard=shard,
                span_name=member,
                count=counts[name],
                total_ms=totals[name],
                unattributed_ms=unattributed_ms if member is RollupSpan.ITEM else None,
            )
        )
    return rows
