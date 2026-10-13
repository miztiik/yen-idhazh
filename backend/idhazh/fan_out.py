"""How many work jobs one run dispatches."""

from __future__ import annotations

from idhazh.contracts.knobs.run import RunConfig


def shard_count(items: int, *, run: RunConfig) -> int:
    """How many jobs a run derives when no operator dispatch count is given.

    `run.shard_size` is what one worker is sized to carry, so a day that needs
    fewer workers gets fewer. Every extra job restores the weights again, and
    that restore is the largest fixed cost in the pipeline (Guardrail #2). The count
    never passes `run.max_parallel` and never falls below one, so an empty day
    still runs a worker that exits cleanly rather than an empty matrix.

    The plan step records this answer. An operator dispatching `digest.yml`
    names a count instead, and may name a larger one than this will ever return.

    The bound this has to clear is the worst case, not the day in hand: at
    `run.safety_ceiling_per_run` items the shard each worker draws must still
    finish inside the `work` job's timeout.
    """
    return max(1, min(-(-items // run.shard_size), run.max_parallel))
