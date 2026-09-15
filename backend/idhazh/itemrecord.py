"""Every cell of one item's census row, filled as the work stage learns it.

A 5x model-time regression ran for six days because nothing printed during a
200-minute shard and the per-item record reached a person only afterwards, in a
CSV, for the items that passed. This module is the other half of that ledger:
the same cells, under the same names, on a line the run emits while it is still
running.

**The names are `ItemHealthRow`'s and this module mints none of its own.** A
field called one thing in the log and another in the ledger is the drift the
whole instrument exists to end, so `note` refuses a key neither vocabulary
holds and a typo at a call site fails loudly rather than minting a cell nobody
reads.

**A recorder is opened per item and nothing here outlives the article it was
opened for.** It is mutable for that reason: the work stage learns these cells
in the order the pipeline produces them, and a frozen shape would mean
threading twenty arguments through five call sites.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

from idhazh import telemetry
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.knobs.observability import LoggingConfig

#: The stages `stage_gap_ms` subtracts from the item's own wall clock. Four, and
#: they tile the item without overlapping: `label_ms` and `summary_ms` are a
#: split of `summarize_ms`, so counting them here as well would charge the model
#: stage twice and drive the gap negative on every item.
#:
#: **What is left over is the point.** Payload writes, the element pass, the
#: evidence write and anything a later row adds without naming it all land in
#: the gap, which is the only cell that can catch a regression in a step nobody
#: has thought to time.
NAMED_STAGE_MS: Final = ("fetch_ms", "extract_ms", "summarize_ms", "faithfulness_ms")


@dataclass(frozen=True, slots=True)
class Flags:
    """Which records exist, read once per shard rather than once per item.

    A copy of `LoggingConfig`'s five switches rather than the config object, so
    a test can build one without a whole `AppConfig` and so nothing here can
    reach for a knob it was not handed.
    """

    item_lines: bool = True
    stage_lines: bool = True
    waiting_heartbeat_seconds: int = 0
    capture_prompts: bool = False
    capture_replies: bool = False

    @classmethod
    def of(cls, logging_config: LoggingConfig) -> Flags:
        """The five switches, off the block that declares them."""
        return cls(
            item_lines=logging_config.item_lines,
            stage_lines=logging_config.stage_lines,
            waiting_heartbeat_seconds=logging_config.waiting_heartbeat_seconds,
            capture_prompts=logging_config.capture_prompts,
            capture_replies=logging_config.capture_replies,
        )


class ItemRecorder:
    """One item's cells, and the records it emits as it fills them.

    `now` is handed in so a test can drive a record from a clock it owns, and so
    the timestamp on a line and the timestamp on a payload come from one
    function rather than from two that agree by luck.
    """

    __slots__ = (
        "_cells",
        "_flags",
        "_in_flight",
        "_log",
        "_now",
        "_parked_ms",
        "_run_id",
        "_started",
    )

    def __init__(
        self,
        *,
        run_id: str,
        flags: Flags,
        now: Callable[[], str],
        log: logging.Logger,
    ) -> None:
        self._run_id = run_id
        self._flags = flags
        self._now = now
        self._log = log
        self._cells: dict[str, object] = {}
        self._started = time.monotonic()
        self._in_flight = "summarize"
        self._parked_ms = 0

    @property
    def flags(self) -> Flags:
        """The switches this recorder was opened with."""
        return self._flags

    def note(self, **cells: object) -> None:
        """Record cells, refusing any key neither vocabulary declares.

        A string cell is folded into the column that will hold it on the way in
        (`telemetry.fit_record_cells`), because most of what lands here is not
        ours: a processor name out of a kernel file, a runner label out of the
        environment, a finish reason out of `llama-server`, a quantisation out of
        the committed config, a Pydantic message that quotes the value it
        refused. Folding at this one door covers every one of them by
        enumeration, so a column declared tomorrow is covered the day it is
        declared. A key that names an identity rather than a character class is
        left alone and keeps the refusal it already had.
        """
        unknown = sorted(set(cells) - telemetry.RECORD_CELLS)
        if unknown:
            raise ValueError(f"a record cell names no column: {', '.join(unknown)}")
        self._cells.update(telemetry.fit_record_cells(cells))

    def get(self, name: str) -> object:
        """One cell, for a caller that needs a value back rather than the whole row."""
        return self._cells.get(name)

    def cells(self) -> dict[str, object]:
        """Every census cell, in the census row's own order.

        Ordered by `ItemHealthRow.csv_columns()` rather than by the order they
        were learned, so two records of two items read down the same way.
        **Absent cells are present and null**: a grep for one field across a
        shard has to find every item, and an item that skipped a stage is
        exactly the one worth finding.
        """
        return {name: self._cells.get(name) for name in telemetry.CENSUS_CELLS}

    def _emit(
        self, name: telemetry.EventName, src: ItemStage, cells: Mapping[str, object]
    ) -> None:
        self._log.info(
            telemetry.record(ts=self._now(), src=src, run=self._run_id, name=name, cells=cells)
        )

    def _addressed(self, **extra: object) -> dict[str, object]:
        """The three cells that say which item a short record is about."""
        return {
            "item_id": self._cells.get("item_id"),
            "shard": self._cells.get("shard"),
            "item_index": self._cells.get("item_index"),
            **extra,
        }

    def start(self) -> None:
        """Say which item is in flight, so a killed shard names the one it died on."""
        if not self._flags.item_lines:
            return
        self._emit(telemetry.EventName.ITEM_START, ItemStage.FETCH, self.cells())

    def stage_done(self, stage: ItemStage, ms: int) -> None:
        """Say a named stage ended. The completion record arrives only if the item does."""
        if not self._flags.stage_lines:
            return
        self._emit(
            telemetry.EventName.STAGE_DONE,
            stage,
            self._addressed(stage=stage.value, waited_s=round(ms / 1000, 3)),
        )

    def calling(self, call: str) -> None:
        """Name the model call about to go on the wire, for the heartbeat to read.

        Until 2026-09-15 the heartbeat said `summarize` for both calls, which is
        the stage rather than the call. An operator watching a stalled shard
        could not tell which of the two was hanging - and the two have different
        causes, because one is cold prefill and the other is decode.
        """
        self._in_flight = call

    def waiting(self, waited_s: float) -> None:
        """Say the model call now in flight is still in flight, and for how long."""
        self._emit(
            telemetry.EventName.MODEL_WAITING,
            ItemStage.SUMMARIZE,
            self._addressed(call=self._in_flight, waited_s=waited_s),
        )

    def call_done(self, call: str, cells: Mapping[str, object]) -> None:
        """Say one model call ended, and what crossed the wire.

        A `stage.done` rather than a name of its own, because a model call IS
        the summarize stage happening twice and a seventh event name for the
        same moment is a name a reader has to learn (Fowler, 2026-09-15). What
        makes the two lines tell apart is `call`.
        """
        if not self._flags.stage_lines:
            return
        self._emit(
            telemetry.EventName.STAGE_DONE,
            ItemStage.SUMMARIZE,
            self._addressed(stage=ItemStage.SUMMARIZE.value, call=call, **dict(cells)),
        )

    def parked(self, ms: int) -> None:
        """Discount time the item spent on a list rather than being worked on.

        The stage fetches every item and then runs the model over them in a
        different order, so an item's wall clock from `start` to `close` counts
        the whole queue ahead of it. Summing that across a shard counted the
        shard's own duration once per item: on a two-item shard it read 2,786
        seconds against a true 2,196 (2026-09-14). `item_total_ms` is what the
        item cost; `queue_wait_ms` is what it waited, and the two are separate
        questions.
        """
        self._parked_ms += max(ms, 0)

    def close(self) -> dict[str, object]:
        """Seal the item's clock and return its cells.

        `item_total_ms` and `stage_gap_ms` are computed here rather than at the
        call site, so they cannot be filled by two subtractions that disagree.
        """
        total = int((time.monotonic() - self._started) * 1000) - self._parked_ms
        named = sum(
            int(value)
            for name in NAMED_STAGE_MS
            if isinstance(value := self._cells.get(name), int)
        )
        self._cells["item_ended_at"] = self._now()
        self._cells["item_total_ms"] = total
        self._cells["stage_gap_ms"] = total - named
        return self.cells()

    def done(self) -> dict[str, object]:
        """Say the item ended - for a failure exactly as for a success."""
        cells = self.close()
        if self._flags.item_lines:
            self._emit(telemetry.EventName.ITEM_DONE, ItemStage.PUBLISH, cells)
        return cells

    def abandoned(self, why: str) -> dict[str, object]:
        """Say the shard bound killed this item mid-flight."""
        cells = self.close()
        if self._flags.item_lines:
            self._emit(
                telemetry.EventName.ITEM_ABANDONED, ItemStage.PUBLISH, {**cells, "detail": why}
            )
        return cells


def shard_done(
    *,
    run_id: str,
    shard: int,
    flags: Flags,
    now: Callable[[], str],
    log: logging.Logger,
    items: int,
    failures: Mapping[str, int],
    slowest: Mapping[str, object] | None,
) -> None:
    """Say what the whole shard did: its totals, its failures, its slowest item.

    `failures` is a flat count by failure code rather than a list of items,
    because the question a person asks of a finished shard is which code moved -
    and a list of eighty item ids answers that only after they have counted.
    """
    if not flags.item_lines:
        return
    log.info(
        telemetry.record(
            ts=now(),
            src=ItemStage.PUBLISH,
            run=run_id,
            name=telemetry.EventName.SHARD_DONE,
            cells={
                "shard": shard,
                "items": items,
                "failures": dict(failures),
                "slowest": dict(slowest) if slowest else None,
            },
        )
    )


@contextmanager
def timed(recorder: ItemRecorder, stage: ItemStage, cell: str) -> Iterator[None]:
    """Time one named stage, record it under `cell`, and say it ended."""
    started = time.monotonic()
    try:
        yield
    finally:
        ms = int((time.monotonic() - started) * 1000)
        recorder.note(**{cell: ms})
        recorder.stage_done(stage, ms)
