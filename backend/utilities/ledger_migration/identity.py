"""Which writer identity does every migrated file carry, so a re-run replaces its own write?"""

from __future__ import annotations

from typing import Final

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity

# Committed raw files carry this producer, so it stays the command's module name.
PRODUCER: Final = "utilities.migrate_to_parquet"
ATTEMPT: Final = 1
SHARD: Final = 0


def writer_identity(run_id: str, git_sha: str) -> WriterIdentity:
    """The identity every file of this run and commit is written under."""
    return WriterIdentity(
        run_id=run_id,
        attempt=ATTEMPT,
        job=ServerJob.MIGRATE,
        shard=SHARD,
        producer=PRODUCER,
        git_sha=git_sha,
    )
