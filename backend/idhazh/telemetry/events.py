"""Which line does a stage log, and what may that line say?

Two shapes ride one vocabulary, and the shape is a property of the name. A
warning rides the nested envelope `event` builds; the work stage's instrument
rides the flat record `record` builds, because the common operation on those is
grepping one field across a whole shard. A reader never has to guess which shape
a line is (`docs/concepts/telemetry.md`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from idhazh.contracts.item_health import ItemHealthRow, ItemStage

#: Envelope version. It rides every record so a reader can evolve its parsing.
ENVELOPE_VERSION: Final = "1"


class EventName(StrEnum):
    """Every event name a stage may emit.

    A name with no emitter cannot be told apart from one that fires, so a name is
    added here in the commit that emits it.

    **Two shapes carry these names and the shape is a property of the name.** The
    two `*.failed` members are warnings and ride the nested envelope `event`
    builds. The six below them are the work stage's instrument and ride the flat
    record `record` builds, because the common operation on them is grepping one
    field across a whole shard and a nested envelope makes that harder than it
    needs to be (owner, 2026-09-14).
    """

    ITEM_SUMMARIZE_FAILED = "item.summarize.failed"
    #: The marks compiled and the file did not land. This is the visual stage
    #: breaking, and it is a different fact from the planner deciding an article
    #: has nothing to draw - `VisualDecision.none_reason` records that one, and
    #: no reader can tell a refusal from a broken writer by looking at a picture
    #: that is not there. The item publishes either way, shorter.
    ITEM_VISUAL_FAILED = "item.visual.failed"
    #: An item was picked up. It exists so a killed shard names the item it died
    #: on: before it, a timeout left no trace of the in-flight item at all.
    ITEM_START = "item.start"
    #: One named stage of one item ended. The completion record arrives only for
    #: an item that finished, and a shard that dies on a timeout finishes none.
    STAGE_DONE = "stage.done"
    #: A model call is still in flight. The slowest single call this project has
    #: measured returned after 22 minutes having printed nothing at all.
    MODEL_WAITING = "model.waiting"
    #: An item ended, and it is emitted for failures as well as successes - the
    #: expensive failures were the least visible thing in the log.
    ITEM_DONE = "item.done"
    #: The shard bound killed an item mid-flight. Distinct from a failure,
    #: because nothing about the item was refused.
    ITEM_ABANDONED = "item.abandoned"
    #: The shard ended: its totals, its failures by code, and its slowest item.
    SHARD_DONE = "shard.done"


#: The names that ride the flat record rather than the nested envelope. Declared
#: as a set rather than left to a reader's eye, so `refuse_the_wrong_shape` can
#: hold each emitter to the shape its own name chose.
FLAT_RECORDS: Final[frozenset[EventName]] = frozenset(
    {
        EventName.ITEM_START,
        EventName.STAGE_DONE,
        EventName.MODEL_WAITING,
        EventName.ITEM_DONE,
        EventName.ITEM_ABANDONED,
        EventName.SHARD_DONE,
    }
)


#: What a flat record may say beyond the census row's own columns. Ten keys, and
#: each one is a fact about the record or about the text that crossed the wire
#: rather than about the item: which stage ended, how long a call has been in
#: flight, what the shard totalled, what the prompt hashed to. An eleventh key
#: that is a property of the ITEM belongs in `ItemHealthRow` first, because a
#: field the log carries and the ledger does not is the drift this instrument
#: exists to end.
#:
#: **`prompt_sha256` is the exception and it is a deliberate one.** It says
#: which bytes the model was sent, and `ItemHealthRow` has no column for it
#: because putting one there needs `Summary` widened too - the assemble stage
#: builds the row from the summary payload and the summary carries no prompt
#: digest. That is a two-contract change and it is priced in the pull request
#: rather than taken here. Until it lands the digest reaches a person through
#: the job log alone, which keeps it for about as long as the capture artifact
#: does.
INSTRUMENT_CELLS: Final[frozenset[str]] = frozenset(
    {
        #: Which named stage `stage.done` is reporting.
        "stage",
        #: Which call `model.waiting` is waiting on.
        "call",
        #: How long that call has been in flight, in seconds.
        "waited_s",
        #: The shard's own totals on `shard.done`, as a flat count map.
        "items",
        "failures",
        "slowest",
        #: What the model was sent and what came back, recorded whether or not
        #: the text itself was captured. Two runs whose prompts differ are two
        #: different measurements, and this is the cheapest way to see that.
        "prompt_sha256",
        "prompt_chars",
        "reply_chars",
        #: Whether the text behind those numbers was written to the artifact.
        "captured",
    }
)

#: Every census column, in the row's own order. One tuple rather than a call at
#: each site, so a record and a ledger row read down the same way and a reader
#: comparing the two is comparing the same sequence.
CENSUS_CELLS: Final[tuple[str, ...]] = ItemHealthRow.csv_columns()

#: Every key a flat record may carry. The census row's columns, plus the ten
#: above. Derived rather than written out, so a column added to the ledger is
#: loggable the same day and a typo at a call site is refused rather than
#: minting a field nobody reads.
RECORD_CELLS: Final[frozenset[str]] = frozenset(CENSUS_CELLS) | INSTRUMENT_CELLS


class EventLevel(StrEnum):
    """Severity, as the envelope spells it."""

    WARNING = "warning"


def event(
    *,
    ts: str,
    src: ItemStage,
    run: str | None,
    name: EventName,
    level: EventLevel,
    ctx: Mapping[str, str | None],
    data: Mapping[str, str | None],
) -> str:
    """Serialize one event as the single line a stage logs.

    `ctx` and `data` stay open because their keys vary by event. The envelope
    around them does not, and building it here rather than at the call site is
    what stops a second emitter shipping a second shape.
    """
    if name in FLAT_RECORDS:
        raise ValueError(f"{name.value} is a flat record; call telemetry.record")
    return json.dumps(
        {
            "ts": ts,
            "src": src.value,
            "v": ENVELOPE_VERSION,
            "run": run,
            "name": name.value,
            "level": level.value,
            "ctx": dict(ctx),
            "data": dict(data),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def record(
    *,
    ts: str,
    src: ItemStage,
    run: str | None,
    name: EventName,
    cells: Mapping[str, object],
) -> str:
    """Serialize one instrument record as the single flat line a stage logs.

    **Flat, and that is the whole design.** The common operation on these lines
    is `grep '"summary_decode_ms":' | ...` across a 200-minute shard, and a
    nested `ctx`/`data` envelope puts every interesting field one level down
    where no line-oriented tool can reach it (owner, 2026-09-14). The four
    envelope fields sit beside the cells rather than above them, and a cell may
    not be called `ts`, `src`, `v`, `run` or `name` for that reason.

    **Every key is a column name `ItemHealthRow` already declares**, apart from
    the handful this module names below. A field called one thing in the log and
    another in the ledger is the drift this instrument exists to end, so the
    caller builds its cells through `idhazh.itemrecord` and this function refuses
    a key neither vocabulary holds.

    Values are JSON scalars. Nothing fetched reaches here: the keys are a closed
    set and none of them is the article's own words (Guardrail #11).
    """
    if name not in FLAT_RECORDS:
        raise ValueError(f"{name.value} is a nested event; call telemetry.event")
    unknown = sorted(set(cells) - RECORD_CELLS)
    if unknown:
        raise ValueError(f"a record cell names no column: {', '.join(unknown)}")
    return json.dumps(
        {"ts": ts, "src": src.value, "v": ENVELOPE_VERSION, "run": run, "name": name.value}
        | dict(cells),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
