"""Check the item-health ledger's prefill rate against the model server's own counters.

Two instruments measure the same thing and neither knows about the other. The
item-health ledger sums a field the summarize stage copied out of each model
reply; `state/runtime-counters.csv` carries what llama-server counted for the
whole shard. `docs/architecture/summarize/throughput.md` and the console both
publish rates derived from the first one, so the second one is what makes those
rates checkable rather than merely reported (Rule #10).

This is an audit and not a stage. It runs when somebody doubts a published
number, never on the daily pipeline's critical path, because a check that can
fail a publication is a check that gets switched off the first time a shard's
server dies. It is committed rather than kept as a private script so the answer
is reproducible from a fork or a stale branch (Rule #5), which is the same
reason `migrate_published_ledger.py` lives here.

Usage, from the root of a checkout:

    python backend/utilities/reconcile_prefill.py --run 2026-08-26-5

Exit code 1 when the two disagree by more than `TOLERANCE`, so a shell can gate
on it.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.ledger import item_health_path, load_runtime_counters

#: How far apart the two instruments may be before one of them is wrong.
#:
#: Stated before either side was read, and deliberately not a `config/` knob: a
#: knob is something an operator tunes, and tuning this one is how a failing
#: check is made to pass. It sits here with its reason for the same reason
#: `ledger.HEALTH_WINDOW_DAYS` does.
#:
#: Five percent is far above the noise and far below the failure. The two
#: instruments count different populations - the server counts the startup
#: warmup and every retry, the ledger records one row per settled item - but an
#: unrecorded request adds tokens and seconds together, so it moves a ratio
#: barely at all. Millisecond rounding over about 150 rows is under 0.001
#: percent. The failure this check exists to catch is counting cached tokens as
#: read, which on run `2026-08-25-1` was 11.09 tok/s against 19.96, an 80
#: percent error.
TOLERANCE: Final = 0.05

#: The two ledger cells a read rate cannot be made without. A row missing either
#: predates token capture and is not evidence in either direction - see the "a
#: null is not a zero" caveat in `docs/architecture/sources/item-health.md`.
#: `cached_tokens` is read separately because an empty cell there is a legitimate
#: zero: a prompt that reused nothing.
_REQUIRED: Final = ("prefill_ms", "input_tokens")


@dataclass(frozen=True, slots=True)
class Pooled:
    """Tokens read and seconds spent, summed. Never a mean of per-item rates."""

    tokens: int
    seconds: float
    parts: int

    @property
    def rate(self) -> float:
        """Tokens per second. Sum over sum, which is the only correct composition."""
        return self.tokens / self.seconds if self.seconds > 0 else 0.0


def pool_counters(rows: list[RuntimeCountersRow]) -> Pooled:
    """One run's shards, summed. A shard whose scrape came back empty is counted
    as a part and contributes nothing, so a caller can see it was there."""
    return Pooled(
        tokens=sum(row.prompt_tokens_total or 0 for row in rows),
        seconds=sum(row.prompt_seconds_total or 0.0 for row in rows),
        parts=len(rows),
    )


def pool_ledger(path: Path, *, run_id: str) -> Pooled:
    """One run's item-health rows, summed over `input_tokens - cached_tokens`.

    That subtraction is the definition: `cached_tokens` is what the runtime
    reused instead of reading, so leaving it in reports a rate the machine never
    ran at. The console and the throughput doc use the same one.
    """
    tokens = 0
    milliseconds = 0
    parts = 0
    if not path.exists():
        return Pooled(tokens=0, seconds=0.0, parts=0)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["run_id"] != run_id:
                continue
            if any(not row[cell] for cell in _REQUIRED):
                continue
            tokens += int(row["input_tokens"]) - int(row["cached_tokens"] or 0)
            milliseconds += int(row["prefill_ms"])
            parts += 1
    return Pooled(tokens=tokens, seconds=milliseconds / 1000.0, parts=parts)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What the two instruments said, and whether they agree."""

    run_id: str
    ledger: Pooled
    server: Pooled

    @property
    def gap(self) -> float:
        """How far the ledger sits from the server, as a share of the server."""
        if self.server.rate == 0:
            return 0.0 if self.ledger.rate == 0 else 1.0
        return abs(self.ledger.rate - self.server.rate) / self.server.rate

    @property
    def agrees(self) -> bool:
        return self.gap <= TOLERANCE

    @property
    def verdict(self) -> str:
        """Plain words, and when they disagree, which side to doubt first."""
        if self.server.parts == 0:
            return "no shard committed a counter snapshot for this run - nothing to check against"
        if self.ledger.parts == 0:
            return "no item-health row for this run carries timings - nothing to check"
        if self.agrees:
            return (
                f"agree: {self.gap * 100:.3f} percent apart, "
                f"inside the {TOLERANCE * 100:.0f} percent bound"
            )
        blame = "the ledger" if self.ledger.rate > self.server.rate else "the server counters"
        return (
            f"DISAGREE: {self.gap * 100:.2f} percent apart, outside the "
            f"{TOLERANCE * 100:.0f} percent bound. {blame} reports the higher rate, so "
            f"{blame} is the side to doubt first"
        )

    def report(self) -> str:
        return "\n".join(
            (
                f"run {self.run_id}",
                f"  ledger  {self.ledger.rate:8.4f} tok/s  "
                f"({self.ledger.tokens} tokens read over {self.ledger.seconds:.2f} s, "
                f"{self.ledger.parts} items)",
                f"  server  {self.server.rate:8.4f} tok/s  "
                f"({self.server.tokens} tokens read over {self.server.seconds:.2f} s, "
                f"{self.server.parts} shards)",
                f"  {self.verdict}",
            )
        )


def reconcile(state_dir: Path, *, run_id: str) -> Reconciliation:
    """Both sides of one run, pooled the same way."""
    return Reconciliation(
        run_id=run_id,
        ledger=pool_ledger(item_health_path(state_dir, run_id[:10]), run_id=run_id),
        server=pool_counters(load_runtime_counters(state_dir, run_id=run_id)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="A run id, `<YYYY-MM-DD>-<n>`.")
    parser.add_argument("--state", type=Path, default=Path("state"))
    args = parser.parse_args()
    result = reconcile(args.state, run_id=args.run)
    print(result.report())
    if result.server.parts == 0 or result.ledger.parts == 0:
        return 1
    return 0 if result.agrees else 1


if __name__ == "__main__":
    raise SystemExit(main())
