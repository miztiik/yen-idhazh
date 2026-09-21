"""What shape does a judge present to the council?

Seven members and one return type. A `typing.Protocol` is structural, so the
council types against this and imports no implementation, and an implementation
inherits nothing from the venue it runs in. The direction of the dependency is
the whole point: registration points a judge at the council, never the council
at a judge.

Nothing here names a judge, and nothing here needs one to be declared,
instantiated or type-checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.ledger import CsvContract, CsvRecord


class JudgeRow(CsvContract, CsvRecord, Protocol):
    """A tenant's own row: the instance that renders itself, and the class that
    names its columns and reads one back.

    Both halves, because the council writes a row whose fields it never reads and
    the collecting job reads that row back. `idhazh.ledger` declares the two
    halves separately - `CsvRecord` is the row and `CsvContract` is its class
    side - and every CSV contract in this repository hand-declares both.

    Deliberately not `Contract`: the base class declares no `csv_row`, no
    `csv_columns` and no `from_csv_row`, so a value typed as it cannot be written
    as a row at all.
    """


@dataclass(frozen=True, slots=True)
class ShardResult:
    """What one unit of hosted work hands back to the council.

    A frozen dataclass rather than a contract. It crosses one function boundary
    inside one process and is never persisted as itself, so it needs no
    validation, no schema and no stem - and having no `model_dump` is what stops
    anything flattening the tenant's row. Measured on pydantic 2.13.4 on
    2026-09-21: a pydantic field typed as the contract base class silently drops
    every subclass column on the dump, so a probe carrying a count of seven
    dumped as its version stamp and nothing else.

    Five of the six values fill the council's own record. `metrics` is the
    tenant's and stays opaque - the council writes what `csv_row()` returns and
    reads no field of it by name.
    """

    #: How the unit ended. The council files this and never infers it.
    outcome: ShardOutcome

    #: How many model calls the unit made. Null, not zero, for a tenant that runs
    #: no model: only the tenant knows which of the two it is.
    model_calls: int | None = None

    #: Prompt tokens across the unit.
    tokens_in: int | None = None

    #: Generated tokens across the unit.
    tokens_out: int | None = None

    #: Wall clock inside model calls. Read against the unit's own clock, the two
    #: say how much of it was the model and how much was everything else.
    model_seconds: float | None = None

    #: The tenant's own row, or nothing at all from a tenant with nothing to
    #: report.
    metrics: JudgeRow | None = None


class Tenant(Protocol):
    """A judge, as the council sees it. Seven members, and the count is the point.

    Three of them are facts about the tenant, one is a question about its own
    store, and three are units of work. Every member that does work takes the
    run id, because a tenant's own rows are keyed on it.

    The three facts are read-only, so a tenant may answer them with a module
    constant, a class attribute or a property, whichever suits it.
    """

    @property
    def judge_id(self) -> str:
        """The tenant's own slug. The council records it and never checks it
        against a list of who may exist."""
        ...

    @property
    def shard_count(self) -> int:
        """How many ways this tenant's work splits.

        A tenant with no model answers 1: sharding exists because a model is
        slow, and four jobs for work that runs no model pay four weights
        restores for nothing.
        """
        ...

    @property
    def committed_paths(self) -> tuple[str, ...]:
        """The store paths this tenant's own work writes, for the collecting job
        to stage.

        Without it the workflow spells one tenant's paths as literals and a
        second tenant's output is never committed.
        """
        ...

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        """Which dates inside the council's window this tenant has not counted.

        The council owns the window - its floor, its length and its per-night cap.
        The tenant owns what is missing and why, under its own stamp rule and its
        own reset semantics.
        """
        ...

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        """Pick the work, once a date, before any shard runs."""
        ...

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        """One shard of the work, stopped before `deadline`.

        The tenant decides what a unit is and when it is safe to stop, because
        only it knows what a half-finished unit would cost. `deadline` is a
        `time.monotonic()` reading and not a clock time, so a host whose wall
        clock moves cannot shorten or extend it.
        """
        ...

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        """Count, fit, or do nothing, once a date after every shard has reported."""
        ...
