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

**`close` hands back the row itself.** The names alone were not enough: a loose
mapping let about 53 of these cells be computed on every item and thrown away
with nothing raising, because the row the ledger keeps was built somewhere else
out of two payloads that cannot carry them.

**`persist` is what stops the row dying with the shard.** A validated row that
reaches only a log line reaches only a CI artifact, so the value is written
beside the article and the summary the same item produced, under the name every
other per-item payload is filed under. `recorded_row` is the other half: the
census reads that file back and prefers it to rebuilding the row from two
payloads that between them cannot carry most of these cells.

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
from pathlib import Path
from typing import Final

from idhazh.assemble import write_atomic
from idhazh.contracts.item_health import ItemHealthRow, ItemStage
from idhazh.contracts.knobs.observability import LoggingConfig
from idhazh.telemetry import events

#: This module's own logger, for the one thing it says on its own account: a
#: recorded payload it could not read. Every other line here is emitted through
#: the logger its caller handed the recorder.
LOG: Final = logging.getLogger("idhazh")

#: What one item's recorded row is filed as, beside the article and the summary
#: it describes, under `backend/var/run/<date>/items/`. The payload is
#: `ItemHealthRow` itself, so nothing new is declared and nothing is migrated -
#: the file is the row the recorder already validated (CLAUDE.md section 11).
HEALTH_SUFFIX: Final = ".health.json"

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

        Nothing is folded here. The column does it: every census column that can
        hold text somebody else wrote carries its own fold, so a value reaching
        the row through any door at all is made to fit
        (`contracts.base.fits_its_column`). A door here as well would be a second
        place to forget, which is how the first one came to cover the log line
        and not the ledger row.
        """
        unknown = sorted(set(cells) - events.RECORD_CELLS)
        if unknown:
            raise ValueError(f"a record cell names no column: {', '.join(unknown)}")
        self._cells.update(cells)

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
        return {name: self._cells.get(name) for name in events.CENSUS_CELLS}

    def _emit(
        self, name: events.EventName, src: ItemStage, cells: Mapping[str, object]
    ) -> None:
        self._log.info(
            events.record(ts=self._now(), src=src, run=self._run_id, name=name, cells=cells)
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
        self._emit(events.EventName.ITEM_START, ItemStage.FETCH, self.cells())

    def stage_done(self, stage: ItemStage, ms: int) -> None:
        """Say a named stage ended. The completion record arrives only if the item does."""
        if not self._flags.stage_lines:
            return
        self._emit(
            events.EventName.STAGE_DONE,
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
            events.EventName.MODEL_WAITING,
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
            events.EventName.STAGE_DONE,
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

    def close(self) -> ItemHealthRow:
        """Seal the item's clock and return the item's census row, validated.

        `item_total_ms` and `stage_gap_ms` are computed here rather than at the
        call site, so they cannot be filled by two subtractions that disagree.

        **The return is the contract and not a mapping, and that is the whole of
        this method.** About 53 of these cells were computed on every item and
        dropped with no type error anywhere, because the census row was rebuilt
        somewhere else out of two payloads that cannot carry them. A row built
        here is a row every cell was checked against its own column in.

        **A cell this refuses is a producer that named the wrong column**, which
        is a defect in the stage rather than a fact about the item, so it raises
        rather than degrading: an item that cannot say where it stopped has
        nothing to record.
        """
        total = int((time.monotonic() - self._started) * 1000) - self._parked_ms
        named = sum(
            int(value)
            for name in NAMED_STAGE_MS
            if isinstance(value := self._cells.get(name), int)
        )
        self._cells["version"] = ItemHealthRow.schema_version()
        self._cells["item_ended_at"] = self._now()
        self._cells["item_total_ms"] = total
        self._cells["stage_gap_ms"] = total - named
        return ItemHealthRow.model_validate(self.cells())

    def done(self) -> ItemHealthRow:
        """Say the item ended - for a failure exactly as for a success."""
        row = self.close()
        if self._flags.item_lines:
            self._emit(events.EventName.ITEM_DONE, ItemStage.PUBLISH, self.cells())
        return row

    def abandoned(self, why: str) -> ItemHealthRow:
        """Say the shard bound killed this item mid-flight."""
        row = self.close()
        if self._flags.item_lines:
            self._emit(
                events.EventName.ITEM_ABANDONED,
                ItemStage.PUBLISH,
                {**self.cells(), "detail": why},
            )
        return row


def persist(items_dir: Path, row: ItemHealthRow) -> Path:
    """Leave one item's recorded row where it outlives the process that recorded it.

    **The row was validated and then dropped.** `close` hands back every cell the
    work stage learned, the log line carries them, and the log is a CI artifact
    kept for days - so the census the ledger keeps was rebuilt somewhere else out
    of the article and the summary payloads, which between them cannot carry 70
    of the 119 columns. This is the file that makes the value survive the shard.

    **The payload is `ItemHealthRow` and nothing else**, so there is no second
    shape to version, to migrate or to keep in step (CLAUDE.md section 11).

    It lands beside `<item_id>.article.json` and `<item_id>.summary.json` because
    that directory is what a work shard uploads and what assemble downloads: a
    store of its own would need a second artifact, and a commit of its own would
    be one commit an item.

    Temp-file-plus-rename, like every other per-item payload (CLAUDE.md section
    1a), so a shard killed mid-write leaves a whole file or no file.
    """
    path = items_dir / f"{row.item_id}{HEALTH_SUFFIX}"
    write_atomic(path, row.to_json())
    return path


def recorded_row(items_dir: Path, item_id: str) -> ItemHealthRow | None:
    """The row this item's shard sealed, or nothing where no shard sealed one.

    The read side of `persist`, and it lives beside it so one module knows the
    filename. A caller asks for an item and gets the row or nothing; where it
    gets nothing it rebuilds the row from the payloads instead
    (`census.census_row`).

    **Nothing here is the file's absence.** A shard writes this the moment it
    seals an item, so an item with no file is an item no shard reached - which
    is most of the plan on a run that died, and is exactly what the census's
    fallback exists to record.

    **A file that will not open is nothing too, and that is a degrade rather
    than a raise** (CLAUDE.md section 1a). A half-written or unreadable payload
    costs the run the 58 cells only the shard could know; letting it raise would
    cost the run the whole day's census. The stage counts what it rebuilt and
    logs the count, so a shard whose rows all came back unreadable is a number
    an operator can see rather than a silence.
    """
    path = items_dir / f"{item_id}{HEALTH_SUFFIX}"
    if not path.exists():
        return None
    try:
        return ItemHealthRow.read(path)
    except (OSError, ValueError):
        LOG.warning("a recorded item-health payload would not read path=%s", path)
        return None


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
        events.record(
            ts=now(),
            src=ItemStage.PUBLISH,
            run=run_id,
            name=events.EventName.SHARD_DONE,
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
