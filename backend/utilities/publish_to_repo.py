"""How does completed work land on main without merging two writers' output?"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from idhazh.contracts.shard_landing import ShardLanding
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_PUSH_REFUSED, Shard


@dataclass(frozen=True, slots=True)
class PushOutcome:
    """The result of publishing one completed shard."""

    exit_code: int
    landing: ShardLanding | None = None
    push_try: int | None = None
    stale_paths: tuple[str, ...] = ()


def publish(
    shard: Shard,
    *,
    attempts: int,
    repo: Path,
    say: Callable[[str], None] = print,
) -> PushOutcome:
    """Reparent a completed shard's exact operations, never rerunning its tasks."""
    from utilities.gardener_publish import (
        BRANCH,
        Checkout,
        _refuse_a_directory,
        _what_staging_missed,
        sleep_with_jitter,
    )

    refused = _refuse_a_directory(shard, repo)
    if refused is not None:
        say(f"shard {shard.index}: {refused}")
        return PushOutcome(exit_code=EXIT_INTEGRITY)
    checkout = Checkout(repo)
    written, deleted = sorted(shard.written_paths), sorted(shard.deleted_paths)
    compared = sorted((shard.written_paths | shard.deleted_paths) - {shard.record_path})
    base = ""
    for attempt in range(1, attempts + 1):
        base = checkout.fetch()
        landed = checkout.remote_blob(shard.record_path)
        if landed is not None:
            if landed == checkout.local_blob(shard.record_path):
                return PushOutcome(EXIT_OK, ShardLanding.ALREADY_ON_MAIN, attempt)
            say(
                f"shard {shard.index}: {shard.record_path} is on {BRANCH} with other bytes, "
                "so two runs claimed one record"
            )
            return PushOutcome(exit_code=EXIT_INTEGRITY)
        stale = checkout.changed_on_main(compared)
        if stale:
            return PushOutcome(EXIT_OK, ShardLanding.STALE, attempt, tuple(stale))
        index = checkout.stage(written, deleted)
        missed = _what_staging_missed(shard, checkout, index)
        if missed is not None:
            say(f"shard {shard.index}: {missed}")
            return PushOutcome(exit_code=EXIT_INTEGRITY)
        if checkout.push(checkout.commit(index, shard.message)):
            return PushOutcome(EXIT_OK, ShardLanding.LANDED, attempt)
        if attempt < attempts:
            sleep_with_jitter(attempt)
    if checkout.fetch() != base:
        return PushOutcome(EXIT_OK, ShardLanding.LOST, attempts)
    return PushOutcome(EXIT_PUSH_REFUSED, ShardLanding.REFUSED, attempts)
