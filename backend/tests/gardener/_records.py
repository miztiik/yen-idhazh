"""How does a gardener test file a record row the way the runner files a shard's record?

Through the ledger door, into the gardener's own ledger under the test's state
root, one file a call, as `runner._record` files one. The row is the committed
sample of a dry walk of `workflow-runs`, moved to the day it is filed on, so a
case names only the cells it is about.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName

#: How far back a scheduled pass of the runs task keeps a run.
KEPT_DAYS: Final = 90


def file_a_record(state: Path, *, on: str, run: int = 1, **cells: Any) -> CollectionPruneRow:
    """One shard's record, holding one row of the runs task, filed through the door on `on`."""
    sample = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR
            / "collection-prune-row"
            / "a-dry-walk-that-counted-past-its-ceiling.json"
        )
    )
    line = (date.fromisoformat(on) - timedelta(days=KEPT_DAYS)).isoformat()
    row = CollectionPruneRow.model_validate(
        sample
        | {"date": on, "run_id": f"{on}-{run}", "until": line, "work_ended_at": f"{on}T00:46:31Z"}
        | cells
    )
    ledger.persist(
        state,
        [row],
        ledger=LedgerName.GARDENER,
        covers=on,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=row.attempt,
            job=ServerJob.RUN_TASKS,
            shard=row.shard,
            producer="gardener.runner",
            git_sha="b" * 40,
        ),
    )
    return row
