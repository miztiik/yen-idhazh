"""Does this ledger take new rows now? Read off its family's lifecycle status on every call.

`config/ledgers.json` gives every family a status. `active` is written; `paused`
and `retired` are not written in production. Every route that writes new rows asks this before it
writes, and on a no it writes nothing and returns what an empty write returns:
a status is a decision about one folder, so a run that stopped on it would cost
every other family its rows. The skip logs one warning, which is the only trace
the rows were ever meant to exist.

**The check sits at the write, never in the path builders.** `path`, `tree_root`
and `relpath` also serve readers, and a paused family is still read.

**A status says whether new rows are written, never how long old ones are
kept.** Compaction, ageing and the prune's own log never ask, and the ledger
door exempts a compact-tier write and any write from a maintenance job - each of
those files rows again that were already recorded, and skipping one after its
source was deleted would lose rows while the run reported success.

An explicitly selected paused council trial may write raw rows to its exact
isolated root for its run and attempt. Retired families and non-raw writers keep
the gate. The council opens this scope only during isolated trial settlement.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Final

from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgerFamily, LedgerLifecycleStatus
from idhazh.ledger import paths

LOG: Final = logging.getLogger("idhazh")
_TRIAL: ContextVar[tuple[Path, str, int] | None] = ContextVar("raw_ledger_trial", default=None)


@contextmanager
def isolated_trial(state_dir: Path, *, identity: WriterIdentity) -> Iterator[None]:
    """Authorize raw writes for one selected trial's exact root and invocation."""
    token = _TRIAL.set((state_dir.resolve(), identity.run_id, identity.attempt))
    try:
        yield
    finally:
        _TRIAL.reset(token)


def _family_of(which: LedgerName) -> LedgerFamily:
    """The family holding this ledger, from the registry `paths` loaded.

    Read from the module attribute on every call rather than captured once, so
    the status in force is the one the registry holds now. The registry refuses
    a ledger with no family when it loads, so the loop always finds one.
    """
    for family in paths._CONFIG.families:
        if any(held.name is which for held in family.ledgers):
            return family
    raise KeyError(f"{which.value} is in no family of config/{paths.REGISTRY_FILENAME}")


def accepts_new_rows(
    which: LedgerName,
    rows: int,
    *,
    state_dir: Path | None = None,
    identity: WriterIdentity | None = None,
) -> bool:
    """Whether new rows may be written into this ledger now.

    `True` for an active family or a paused raw write in its authorized trial.
    Otherwise, one warning naming
    the ledger, its family, the status and how many rows were not written, and
    `False` - the caller then writes nothing and carries on.
    """
    family = _family_of(which)
    if family.lifecycle_status is LedgerLifecycleStatus.ACTIVE:
        return True
    trial = _TRIAL.get()
    if (
        family.lifecycle_status is LedgerLifecycleStatus.PAUSED
        and trial is not None
        and state_dir is not None
        and identity is not None
        and (state_dir.resolve(), identity.run_id, identity.attempt) == trial
    ):
        return True
    LOG.warning(
        "ledger write skipped ledger=%s family=%s status=%s rows=%s",
        which.value,
        family.name,
        family.lifecycle_status.value,
        rows,
    )
    return False
