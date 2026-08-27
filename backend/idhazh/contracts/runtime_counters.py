"""What llama-server itself counted during one `work` shard.

`state/runtime-counters.csv`. One row per shard per run, appended by the `work`
job just after it commits the rows its items earned.

**What one row covers.** Both `llamacpp:` figures are cumulative for the server
process, and a shard starts one llama-server and keeps it for the whole job. So
one scrape at job end is the whole shard, and there is nothing to subtract. A
per-request scrape would add requests to the thing it measures and still report
only the last one.

**Why this exists.** Every timing on the item-health ledger is a field the
summarize stage copied out of one model reply, and two documents publish rates
derived from it - `docs/architecture/summarize/throughput.md` and the console.
Nothing committed could check them, because the only place the server's own
counters landed was a job log with two days of retention. Rule #10 says an
unreconcilable number may not justify a design, so the second instrument had to
become a committed row.

**How rows compose into a run.** A run has one row per shard. The run figure is
the sum of the tokens over the sum of the seconds - never the mean of the
per-shard rates. A rate is a ratio, and averaging ratios weighs a shard that did
20 items the same as one that did 40
(`docs/reference/measurements.md`). Deliberately there is no per-row rate
property here: the pooling lives in `backend/utilities/reconcile_prefill.py`,
where it can only be done the one correct way.

**Why not a field on `RunManifest`.** Four reasons, and any one of them is
enough. The grain is wrong - a manifest run record is one run and this is one
shard, so the manifest would grow a variable-length list. The producer is wrong
- the manifest is written by `assemble`, in another job hours later, so these
numbers would have to travel inside the items artifact, which expires in a day
and is not uploaded at all when a job is cancelled. The audience is wrong -
`run.json` is a published payload a reader's browser fetches, and this is
measurement evidence that belongs under `state/`, which is never served. And the
timing is wrong - a concurrent branch was also opening `RunManifest`, and two
branches stamping one contract's changelog on the same day raise `TypeError` at
import (`docs/architecture/contracts/schemas.md`).
"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Timestamp,
)

#: The Prometheus series each field is read from, on llama.cpp `b10598`. The
#: names are the wire format and the field names are ours, so a llama.cpp rename
#: is one edit here and shows up as a null column rather than as a wrong number.
#: Read from a real capture, not from the upstream README: the README at tag
#: b10598 lists neither `prompt_tokens_cached_total` nor the "excluding cached
#: tokens" wording that settles what `prompt_tokens_total` means.
SERIES: Final[dict[str, str]] = {
    "llamacpp:prompt_tokens_total": "prompt_tokens_total",
    "llamacpp:prompt_tokens_cached_total": "prompt_tokens_cached_total",
    "llamacpp:prompt_seconds_total": "prompt_seconds_total",
    "llamacpp:tokens_predicted_total": "tokens_predicted_total",
    "llamacpp:tokens_predicted_seconds_total": "tokens_predicted_seconds_total",
    "llamacpp:n_decode_total": "n_decode_total",
    "llamacpp:n_tokens_max": "n_tokens_max",
    "llamacpp:n_busy_slots_per_decode": "n_busy_slots_per_decode",
}

#: Fields whose series is a whole count. A value that is not whole is a rename
#: or a format change, and it raises rather than truncate.
_WHOLE: Final = frozenset(
    {
        "prompt_tokens_total",
        "prompt_tokens_cached_total",
        "tokens_predicted_total",
        "n_decode_total",
        "n_tokens_max",
    }
)


class RuntimeCountersRow(Contract):
    """One `work` shard, one run, one row."""

    __schema_stem__: ClassVar[str] = "runtime-counters-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "Initial shape: the shard, and the llamacpp: counters its server "
                "reported at job end."
            ),
            why=(
                "The item-health ledger's prefill and decode timings are copied out of "
                "the model's own replies, one request at a time, and two published "
                "surfaces quote rates derived from them. Nothing committed could check "
                "either, because the server's own counters were scraped into a job log "
                "that keeps them for two days. A number that cannot be reconciled "
                "cannot justify a design (Rule #10), so the second instrument is now a "
                "committed row."
            ),
        ),
    )

    date: DateStamp = Field(
        description="The digest day, the same one the item-health row files under."
    )
    run_id: RunId
    shard: int = Field(ge=0, description="Which work shard this server served.")
    shards: int = Field(ge=1, description="How many shards the run split into. The denominator.")
    scraped_at: Timestamp = Field(
        description="When the counters were read. Job end, after the last item settled."
    )

    prompt_tokens_total: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the server actually read, cached ones excluded. The same "
            "quantity the ledger spells `input_tokens - cached_tokens`."
        ),
    )
    prompt_tokens_cached_total: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens reused from the cache instead of read. The ledger's `cached_tokens`."
        ),
    )
    prompt_seconds_total: float | None = Field(
        default=None, ge=0, description="Seconds spent reading prompts. The ledger's `prefill_ms`."
    )
    tokens_predicted_total: int | None = Field(
        default=None, ge=0, description="Tokens written. The ledger's `output_tokens`."
    )
    tokens_predicted_seconds_total: float | None = Field(
        default=None, ge=0, description="Seconds spent writing. The ledger's `decode_ms`."
    )
    n_decode_total: int | None = Field(
        default=None, ge=0, description="llama_decode() calls, speculative and multimodal excluded."
    )
    n_tokens_max: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The longest sequence the server saw, prompt plus generation. Says how "
            "close the day came to `n_ctx`."
        ),
    )
    n_busy_slots_per_decode: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Slots busy per decode call, averaged. Says whether batching happened at "
            "all, which is what separates 'more slots did not help' from 'more slots "
            "were never used'."
        ),
    )

    @model_validator(mode="after")
    def _shard_fits_inside_the_run(self) -> Self:
        if self.shard >= self.shards:
            raise ValueError("a shard index must be below the shard count")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A series this build does not publish is an empty cell.

        Empty is not zero. A server that never answered and a server that read no
        tokens are different facts, and one of them is a broken scrape.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never a zero."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name in SERIES.values():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def from_metrics_text(
        cls,
        text: str,
        *,
        date: str,
        run_id: str,
        shard: int,
        shards: int,
        scraped_at: str,
    ) -> Self:
        """Read one row out of a `GET /metrics` body.

        A series this build does not publish is left null rather than defaulted,
        so a llama.cpp rename shows as a missing column instead of as a zero that
        a later reader would average. A series that is present but unreadable
        raises: the workflow step tolerates its own failure, so a broken scrape
        costs this row and never the shard.
        """
        values: dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, raw = line.partition(" ")
            field = SERIES.get(name)
            if field is None:
                continue
            values[field] = _number(name, field, raw.strip())
        return cls.model_validate(
            {
                "date": date,
                "run_id": run_id,
                "shard": shard,
                "shards": shards,
                "scraped_at": scraped_at,
                **values,
            }
        )


def _number(series: str, field: str, raw: str) -> float | int:
    value = float(raw)
    if field not in _WHOLE:
        return value
    if not value.is_integer():
        raise ValueError(f"{series} is a count and reported {raw!r}")
    return int(value)
