"""What the hardware console draws about the machines a run drew.

Three panels read this shape: the cards for the machines one run drew, the
reading-against-writing split repeated once per machine, and the count of what
the platform has been giving us over a window. They are declared here before
any of them is drawn, because a panel written against a shape nobody agreed is
a panel that has to be migrated the first time the shape moves
(`CLAUDE.md` Guardrail #3, and the same reason `run-timeline-row` landed ahead
of its producer).

**Nothing writes this document yet.** The console derives it at build time out
of `state/runtime-counters.csv` and `state/host-fingerprint/`, the way every
other panel on that route is derived, and the generated schema is what the
frontend resolves its column names and its flag vocabulary against. What the
declaration buys today is that the vocabulary has one home: the twelve chips a
card draws come from `WATCHED_FLAGS` through this schema, so a flag added to
the probe cannot leave the console drawing eleven.

**A card carries every watched flag, present or absent.** That is enforced here
rather than left to the markup: an empty `flags` cell is a reading and not a
gap (`docs/reference/host-metrics.md`), so a list of only the flags a machine
has cannot say what it is missing - which is the one thing the panel exists to
show. `MachineCard` refuses a flag list that is not the full set.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, RunId
from idhazh.contracts.host_fingerprint import WATCHED_FLAGS

#: The grey the ramp keeps for "Machine not recorded". An absence is not a
#: machine and must not take a machine's hue, so no named machine is ever
#: assigned this stop.
UNRECORDED_COLOUR_STOP: int = 8

#: The key the shards that recorded no machine are grouped under. A key rather
#: than an empty string, so the group sorts, keys a DOM node and reads back like
#: any other - and so nothing has to treat "no key" as a special case that a
#: later reader forgets about.
UNRECORDED_KEY: str = "unrecorded"


class WatchedFlag(StrEnum):
    """One instruction-set flag the console draws a chip for.

    The closed set `WATCHED_FLAGS` already holds, restated as an enum so the
    generated schema carries the names and the frontend reads them from there
    rather than typing a second copy. The check below is what makes it a
    restatement instead of a copy.
    """

    AMX_BF16 = "amx_bf16"
    AMX_INT8 = "amx_int8"
    AMX_TILE = "amx_tile"
    AVX2 = "avx2"
    AVX512_BF16 = "avx512_bf16"
    AVX512_FP16 = "avx512_fp16"
    AVX512_VNNI = "avx512_vnni"
    AVX512F = "avx512f"
    AVX_VNNI = "avx_vnni"
    F16C = "f16c"
    FMA = "fma"
    SSE4_2 = "sse4_2"


if tuple(flag.value for flag in WatchedFlag) != WATCHED_FLAGS:
    raise RuntimeError(
        "WatchedFlag must restate WATCHED_FLAGS exactly, in the same order; "
        f"got {tuple(flag.value for flag in WatchedFlag)} against {WATCHED_FLAGS}"
    )


class MachineFlag(Model):
    """One chip on a card: a flag, and whether this machine reported it."""

    name: WatchedFlag
    present: bool = Field(
        description=(
            "Whether the host reported this flag. False draws an outlined chip "
            "rather than dropping the flag, because what a machine cannot do is "
            "the half a list of what it can do refuses to say."
        ),
    )


class MachinePlacement(Model):
    """Where the platform put this machine, and which microcode it was running.

    The five cells a processor detail table would have carried, kept behind the
    card's own disclosure instead. Every one is absent on a machine whose host
    metadata service did not answer, which is every developer machine.
    """

    vm_size: str | None = Field(default=None)
    vm_location: str | None = Field(default=None)
    vm_zone: str | None = Field(default=None)
    vm_fault_domain: str | None = Field(default=None)
    microcode: str | None = Field(
        default=None,
        description=(
            "The one cell that moves without anything else moving, so it is the "
            "only explanation left for a speed change with no other change."
        ),
    )
    cpu_model_raw: str | None = Field(
        default=None,
        description=(
            "The host's own `model name` line, unnormalised. The card's heading is "
            "a display name, and a display name that dropped a word has to be "
            "checkable against what was recorded."
        ),
    )


class MachineIdentity(Model):
    """What names a machine on this route, and what colour it takes.

    `key` is the fingerprint where the fingerprint ledger reached this run, and
    the processor's own model-name string where it did not. Colour is assigned
    ascending by that key so a machine keeps its stop at every window preset -
    assigning by speed or by draw count would encode an ordering the ramp does
    not mean, and assigning by order of first appearance would change a
    machine's colour when the operator changes the span.
    """

    key: str = Field(min_length=1)
    name: str = Field(
        min_length=1,
        description=(
            "The machine in words, on the row, always. Colour here encodes a fact, "
            "so it is semantic and may never be the only carrier of it."
        ),
    )
    colour_stop: int = Field(
        ge=1,
        le=UNRECORDED_COLOUR_STOP,
        description=(
            "Which stop of the chart ramp this machine takes, 1-based. 8 is "
            "reserved for shards that recorded no machine at all."
        ),
    )
    folded: list[str] = Field(
        default_factory=list,
        description=(
            "The machines folded into this row once the ramp ran out, named in "
            "words. Empty on every row that is one machine. Never two machines in "
            "one colour without the page saying so."
        ),
    )


class MachineCard(Model):
    """One machine a run drew, and what it can do."""

    identity: MachineIdentity
    part: str | None = Field(
        default=None,
        description=(
            "Family, model and stepping as one string - `25/1/1`. Two machines "
            "reporting one model name can differ here, and that difference is the "
            "only thing that explains a speed gap between them."
        ),
    )
    flags: list[MachineFlag] = Field(
        default_factory=list,
        description=(
            "Every watched flag, present or absent, or nothing at all where the "
            "fingerprint never reached this run. Never a subset."
        ),
    )
    flags_recorded: bool = Field(
        default=False,
        description=(
            "Whether the instruction set was read at all. False is a different "
            "fact from a machine that reported none of the watched flags, and "
            "drawing twelve absent chips for it would publish the second as the "
            "first."
        ),
    )
    l3_cache_bytes: int | None = Field(default=None, ge=0)
    memcpy_gib_s: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Large-block copy bandwidth. Absent where the probe was switched off, "
            "which is a different fact from a rate of zero."
        ),
    )
    memcpy_probe_mib: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The buffer the probe used. It rides beside the rate so the two are "
            "read in one sentence: a buffer at or below L3 measured cache."
        ),
    )
    shards_drawn: int = Field(ge=1, description="Shards of the run that drew this machine.")
    shards_total: int = Field(ge=0, description="Shards the run split into. The denominator.")
    placement: MachinePlacement | None = Field(default=None)

    @model_validator(mode="after")
    def _every_flag_or_none(self) -> Self:
        if not self.flags:
            return self
        drawn = [flag.name.value for flag in self.flags]
        if drawn != list(WATCHED_FLAGS):
            raise ValueError(
                "MachineCard.flags must carry every watched flag once, in order, "
                "or be empty where the instruction set was never read"
            )
        return self


class MachineSplit(Model):
    """How one machine's shards split their seconds and their tokens.

    Sum over sum within the machine, never a mean of per-shard rates: averaging
    ratios weighs a shard that read twenty items like one that read forty. The
    existing rule, now applied per machine instead of across all of them.
    """

    identity: MachineIdentity
    shards: int = Field(ge=1, description="Shards of this machine that reported all four cells.")
    read_seconds: float = Field(ge=0)
    write_seconds: float = Field(ge=0)
    read_tokens: float = Field(ge=0)
    write_tokens: float = Field(ge=0)
    read_tokens_per_second: float | None = Field(default=None, ge=0)
    write_tokens_per_second: float | None = Field(default=None, ge=0)
    write_cost_ratio: float | None = Field(
        default=None,
        ge=0,
        description=(
            "How many read tokens one written token costs, on this machine's "
            "shards alone. Null unless both rates are known - a ratio against an "
            "absent rate is not a ratio."
        ),
    )


class FleetKind(Model):
    """One kind of machine, counted over the window."""

    identity: MachineIdentity
    placements: int = Field(
        ge=0,
        description=(
            "Job placements recorded on this kind. A count of what happened, never "
            "a rate and never a probability: the share of a future draw is exactly "
            "what a lottery refuses to quote."
        ),
    )


class MachinePanels(Contract):
    """The three machine panels of `/console/machine/`, for one run and one window."""

    __schema_stem__: ClassVar[str] = "machine-panels"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-17",
            change="Initial shape: machine cards, the split per machine, and the fleet count.",
            why="A run is not a machine, and one pooled rate was wrong on 86 of 90 runs.",
        ),
    )

    run_id: RunId | None = Field(
        default=None, description="The run the cards and the split are about."
    )
    date: DateStamp | None = Field(default=None)
    machines: list[MachineCard] = Field(default_factory=list)
    splits: list[MachineSplit] = Field(default_factory=list)
    fleet: list[FleetKind] = Field(default_factory=list)
    fleet_rows: int = Field(
        default=0,
        ge=0,
        description=(
            "Recorded placements the fleet count was made from. It is printed as "
            "the denominator and it is what the drawing threshold is read against."
        ),
    )
    fleet_days: int = Field(
        default=0, ge=0, description="Days the fleet count covers. The window, in days."
    )
    fingerprint_recording: bool = Field(
        default=True,
        description=(
            "Whether the machine record is switched on. False is why a panel has "
            "nothing, and the panel says so in words that never name the setting."
        ),
    )
