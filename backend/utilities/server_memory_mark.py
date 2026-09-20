"""Does the model server's recorded memory mark ever fall, and in whose order?

**An operator script, never a test.** It reads every committed
`state/item-health/` day file, so it costs more as the archive grows
(CLAUDE.md Guardrail #12), and every number it prints is a property of data a
run appended - which CLAUDE.md section 13 forbids a test to assert on, because a
red would arrive on the day a run wrote an unusual shard rather than on the day
somebody changed the code.

Run it from the repository root:

    python backend/utilities/server_memory_mark.py
    python backend/utilities/server_memory_mark.py --day 2026-09-20

**The question.** `llama_rss_peak_bytes` is `VmHWM` from `/proc/<pid>/status`
for the model server, and one server serves a whole shard. A reader meeting a
mark that falls from one item to the next has two very different things to tell
apart: rows read in an order the mark was never taken in, and a mark that really
went down.

**What it settles.** Which of the two it is, by counting the same falls under
both clocks the row carries - `item_started_at`, stamped where the fetch loop
reached the item, and `item_ended_at`, stamped a moment after the mark was read
- and, for every fall that survives the second clock, whether the server was
still the same process.

**What it cannot settle.** No row carries the server's process id, so identity
is answered by its resident set: a server that restarted has dropped the weights
and reads a small fraction of what it read before. That separates a restart from
a reclaimed page; it cannot separate two processes that happened to hold the
same amount.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Final

from idhazh import day_partition

#: The committed archive. Read whole, which is the growing read this file owns.
LEDGER_ROOT: Final = "state/item-health"

#: The mark under investigation, and the current resident set beside it.
MARK: Final = "llama_rss_peak_bytes"
SET_NOW: Final = "llama_rss_bytes"

#: **The two clocks, and the whole of the ordering question.** The first is
#: stamped where the fetch loop reached the item; the second where the item's
#: record was sealed, one statement after the mark was read. The stage fetches
#: every item and then runs the model over them in a different order, so the two
#: disagree about what "the next item" means.
FETCH_CLOCK: Final = "item_started_at"
MODEL_CLOCK: Final = "item_ended_at"

#: One job, one machine, one model server. A shard number alone spans days and
#: runs, and `plan` and `assemble` both spell shard 0.
JOB_KEY: Final = ("date", "run_id", "shard")

#: Below this share of the previous item's resident set, the server gave the
#: weights back - which is a restart rather than a page the kernel reclaimed.
#: The weights are most of the resident set, so the two cases are not close
#: together and the exact line does not decide any answer here.
A_RESTART_HOLDS_LESS_THAN: Final = 0.5

#: What the kernel hands back and takes away in. A drop that is not a whole
#: number of these is not pages moving.
PAGE_BYTES: Final = 4096


@dataclass(frozen=True, slots=True)
class Fall:
    """One pair of items where the later row recorded a lower mark."""

    job: tuple[str, ...]
    drop: int
    set_before: int
    set_after: int

    @property
    def page_aligned(self) -> bool:
        return self.drop % PAGE_BYTES == 0

    @property
    def set_ratio(self) -> float:
        return self.set_after / self.set_before if self.set_before else 0.0

    @property
    def same_process(self) -> bool:
        return self.set_ratio >= A_RESTART_HOLDS_LESS_THAN


@dataclass(frozen=True, slots=True)
class Order:
    """What the mark did when the rows were read in one clock's order."""

    pairs: int
    falls: tuple[Fall, ...]

    @property
    def jobs_with_a_fall(self) -> int:
        return len({fall.job for fall in self.falls})


def cell(row: dict[str, str], name: str) -> str:
    """One cell, empty where the column is absent as well as where it is blank.

    A day file written before a column existed does not carry the heading at
    all, and an older row read through `csv.DictReader` answers `None` for it.
    """
    return (row.get(name) or "").strip()


def marked_rows(root: Path, day: str | None) -> tuple[list[dict[str, str]], int]:
    """Every committed row that carries both the mark and the clock it was taken on.

    **This is the growing read.** It opens every day file under
    `state/item-health/` (Guardrail #12). A bounded window cannot answer the
    question: a fall is a property of a pair of rows inside one shard, and
    whether any shard anywhere has ever produced one is the thing being asked.
    `--day` narrows it to one day for a spot check, which is the bounded form
    where the reader already knows which run they are looking at.
    """
    kept: list[dict[str, str]] = []
    files = 0
    for path in day_partition.day_files(root / LEDGER_ROOT):
        if day is not None and day_partition.date_of(path) != day:
            continue
        files += 1
        with path.open(encoding="utf-8", newline="") as handle:
            kept.extend(
                row
                for row in csv.DictReader(handle)
                if cell(row, MARK) and cell(row, MODEL_CLOCK) and cell(row, FETCH_CLOCK)
            )
    return kept, files


def jobs(rows: list[dict[str, str]]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    """The rows grouped by the job that produced them, which is one server each."""
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(cell(row, name) for name in JOB_KEY)].append(row)
    return grouped


def read_in(grouped: dict[tuple[str, ...], list[dict[str, str]]], clock: str) -> Order:
    """Where the mark falls when consecutive means consecutive by this clock."""
    pairs = 0
    falls: list[Fall] = []
    for job, members in sorted(grouped.items()):
        ordered = sorted(members, key=lambda row: cell(row, clock))
        for before, after in pairwise(ordered):
            pairs += 1
            drop = int(cell(before, MARK)) - int(cell(after, MARK))
            if drop > 0:
                falls.append(
                    Fall(
                        job=job,
                        drop=drop,
                        set_before=int(cell(before, SET_NOW) or 0),
                        set_after=int(cell(after, SET_NOW) or 0),
                    )
                )
    return Order(pairs=pairs, falls=tuple(falls))


def out_of_step(grouped: dict[tuple[str, ...], list[dict[str, str]]]) -> int:
    """How many rows sit at a different position under each clock.

    The one number that says the two orders are different questions rather than
    the same question with a tie-break.
    """
    moved = 0
    for members in grouped.values():
        by_fetch = sorted(
            members, key=lambda row: (cell(row, FETCH_CLOCK), cell(row, "item_index"))
        )
        by_model = sorted(members, key=lambda row: cell(row, MODEL_CLOCK))
        moved += sum(1 for a, b in zip(by_fetch, by_model, strict=False) if a is not b)
    return moved


def set_falls(grouped: dict[tuple[str, ...], list[dict[str, str]]]) -> tuple[int, int, int]:
    """How often the CURRENT resident set falls, in the order the mark was taken.

    The mark is the larger of the current set and a mark the kernel refreshes
    only when the process itself gives memory back, so what the current set is
    doing is the context every fall above has to be read in.
    """
    fell = pairs = worst = 0
    for members in grouped.values():
        ordered = sorted(members, key=lambda row: cell(row, MODEL_CLOCK))
        for before, after in pairwise(ordered):
            pairs += 1
            drop = int(cell(before, SET_NOW) or 0) - int(cell(after, SET_NOW) or 0)
            if drop > 0:
                fell += 1
                worst = max(worst, drop)
    return fell, pairs, worst


def mark_against_set(rows: list[dict[str, str]]) -> tuple[int, int]:
    """How the mark sits against the current set on the same row.

    The kernel prints the larger of the current resident set and a mark it
    refreshes only when the process itself gives memory back, so a mark BELOW
    the set on the same read would say that rule is not what we are looking at.
    How often the two are equal says how much of the time the mark is simply
    reporting the set.
    """
    below = equal = 0
    for row in rows:
        mark, now = int(cell(row, MARK)), int(cell(row, SET_NOW) or 0)
        below += 1 if mark < now else 0
        equal += 1 if mark == now else 0
    return below, equal


def report(root: Path, day: str | None) -> int:
    """Print the evidence. Non-zero only where there is nothing to read."""
    rows, files = marked_rows(root, day)
    if not rows:
        where = "the committed ledger" if day is None else f"{day}"
        print(f"no row of {where} carries {MARK} with both clocks", file=sys.stderr)
        return 1

    grouped = jobs(rows)
    orders = (read_in(grouped, FETCH_CLOCK), read_in(grouped, MODEL_CLOCK))
    print(
        f"{len(rows):,} rows carry `{MARK}`, over {files} day files and "
        f"{len(grouped)} jobs.\n"
    )
    print("| Rows read in this order | Pairs | Falls | Jobs with a fall |")
    print("| --- | --- | --- | --- |")
    print(
        f"| `{FETCH_CLOCK}` - where the fetch loop reached the item | "
        f"{orders[0].pairs} | {len(orders[0].falls)} | "
        f"{orders[0].jobs_with_a_fall} of {len(grouped)} |"
    )
    print(
        f"| `{MODEL_CLOCK}` - where the mark was read | "
        f"{orders[1].pairs} | {len(orders[1].falls)} | "
        f"{orders[1].jobs_with_a_fall} of {len(grouped)} |"
    )
    print(
        f"\n{out_of_step(grouped):,} of {len(rows):,} rows sit at a different position "
        f"under the two clocks.\n"
    )

    fell, pairs, worst = set_falls(grouped)
    print(
        f"The server's current resident set falls in {fell} of {pairs} pairs, worst "
        f"{worst:,} bytes - so the machine is taking pages back from it routinely.\n"
    )

    below, equal = mark_against_set(rows)
    print(
        f"The mark reads below the current set on {below} rows and exactly equals it "
        f"on {equal:,} of {len(rows):,} - which is what `max(the set now, a stored "
        f"mark)` looks like from outside.\n"
    )

    survivors = orders[1].falls
    if not survivors:
        print("No fall survives the clock the mark was read on.")
        return 0

    print("### Falls that survive the clock the mark was read on\n")
    print("| Job | Drop (bytes) | Whole pages | Set before | Set after | Same process |")
    print("| --- | --- | --- | --- | --- | --- |")
    for fall in survivors:
        print(
            f"| {'/'.join(fall.job)} | {fall.drop:,} | "
            f"{'yes' if fall.page_aligned else 'NO'} | {fall.set_before:,} | "
            f"{fall.set_after:,} | "
            f"{'yes' if fall.same_process else 'NO - it restarted'} "
            f"({fall.set_ratio:.4f}) |"
        )
    restarts = sum(1 for fall in survivors if not fall.same_process)
    print(
        f"\n{restarts} of {len(survivors)} of these sit either side of a server that "
        f"gave the weights back. The rest fell while the same process held them, so "
        f"the mark itself went down."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day", default=None, metavar="YYYY-MM-DD", help="One day, not all.")
    return report(Path.cwd(), parser.parse_args().day)


if __name__ == "__main__":
    raise SystemExit(main())
