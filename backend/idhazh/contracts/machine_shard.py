"""What one work shard's machine did, folded from the two ledgers that recorded it
(`frontend/public/machine/<YYYY-MM>.csv`).

One row per `(date, run_id, shard)`. Two instruments meet on it and neither is
derived from the other. `server_prompt_tokens` and `server_prompt_seconds` are
what the model server itself counted, copied from the host row at the same key.
`read_tokens` and `read_ms` are what the item ledger says the same shard read,
added over its items. A gap between the two rates is one of the two instruments
being wrong, which is the only reason this row carries both.

**Every other cell is a fold of the item ledger, never a second account.** A
sum, a maximum or a count over the shard's own item rows - so a reader that
wants an item's own number opens `state/item-health/` and a reader that wants
the shard's totals reads this. Nothing here restates a cell that already sits on
the host row.

**The planned shard count is not on this row.** It belongs to the run rather
than to a shard, the plan settled it before any work job existed, and
`RunManifest.shards` is where it lives. Counting the rows here instead would
make the denominator equal the numerator.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId


class MachineShardRow(Contract):
    """One work shard of one run, as its machine and its items reported it."""

    __schema_stem__: ClassVar[str] = "machine-shard-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-19",
            change="Initial shape: one row per date, run and work shard.",
            why="The published machine series moved onto the two ledgers that survive.",
        ),
    )

    date: DateStamp
    run_id: RunId
    shard: int = Field(ge=0, description="Which work shard of the run this row folds.")

    items: int = Field(
        ge=0,
        description=(
            "Item rows the shard committed with both of a model call's token cells. "
            "The denominator every fold below was taken over, so a total made from "
            "three items of forty is readable as one."
        ),
    )

    read_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the item ledger says this shard read: `input_tokens` minus "
            "`cached_tokens`, added over its items. Cached tokens are excluded because "
            "the server counts them that way, and counting them as read is the defect "
            "this pairing caught in August."
        ),
    )
    read_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the item ledger charged to prefill, added over the shard's "
            "items. The denominator of the ledger's own read rate."
        ),
    )
    cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the shard reused from the cache instead of reading. Read "
            "beside `read_tokens`: the two together are every prompt token the shard "
            "needed."
        ),
    )
    written_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Tokens the shard's model calls wrote, added over its items.",
    )
    write_ms: int | None = Field(
        default=None,
        ge=0,
        description="Milliseconds the item ledger charged to decode, added over the items.",
    )
    longest_sequence: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The longest prompt-plus-answer any one item reached. A maximum and never "
            "a sum - it is read against the configured context window, and a sum of "
            "sequences is a length no model call ever saw."
        ),
    )
    n_ctx_configured: int | None = Field(
        default=None,
        gt=0,
        description=(
            "The context window the shard's server was started with. Carried so "
            "`longest_sequence` is readable without a config file from the same day."
        ),
    )

    cpu_model: str | None = Field(
        default=None,
        description=(
            "The processor the host drew, in its own words, from the machine record "
            "at this key. Null where the record did not reach the shard."
        ),
    )
    cpu_busy_pct: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The lowest share of processor time any of the shard's items spent busy. "
            "The item ledger's `Watch` over the model window, not a whole-job figure: "
            "a low reading says that item waited rather than computed."
        ),
    )
    llama_rss_peak_bytes: int | None = Field(
        default=None,
        ge=0,
        description="The model server's memory high-water mark over the shard's items.",
    )
    python_rss_bytes: int | None = Field(
        default=None, ge=0, description="The pipeline process's own high-water mark."
    )
    cgroup_peak_bytes: int | None = Field(
        default=None,
        ge=0,
        description="What the container accounted to the shard, at its highest.",
    )

    model_load_ms: float | None = Field(
        default=None,
        ge=0,
        description=(
            "What the shard paid opening the weights before its first item, from the "
            "machine record. Once a job, which is this row's grain."
        ),
    )
    job_seconds: int | None = Field(
        default=None,
        ge=0,
        description="The shard job's own wall clock, from the machine record.",
    )

    server_prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the model server itself counted reading, cached ones "
            "excluded. The second instrument: `read_tokens` is arithmetic over the "
            "item ledger, and arithmetic over a ledger cannot check that ledger."
        ),
    )
    server_prompt_seconds: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Seconds the model server itself counted reading prompts. Pairs with the "
            "column above - a rate is a ratio, and the 80 percent error this pairing "
            "caught was in the numerator."
        ),
    )

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A fold with nothing to add up is an empty cell.

        Empty is not zero. A shard whose items never reported a token count and a
        shard that read no tokens are different facts, and only one of them is a
        broken instrument.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent reading, never a zero."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time."""
        return tuple(name for name, field in cls.model_fields.items() if field.default is None)


__all__ = ["MachineShardRow"]
