"""Does this ledger take new rows now? Read off its family's lifecycle status on every call.

`config/ledgers.json` gives every family a status. `active` is written; `paused`
and `retired` are not. Every route that writes new rows asks this before it
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
"""

from __future__ import annotations

import logging
from typing import Final

from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgerFamily, LedgerLifecycleStatus
from idhazh.ledger import paths

LOG: Final = logging.getLogger("idhazh")


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


def accepts_new_rows(which: LedgerName, rows: int) -> bool:
    """Whether new rows may be written into this ledger now.

    `True` for an active family. For a paused or retired one, one warning naming
    the ledger, its family, the status and how many rows were not written, and
    `False` - the caller then writes nothing and carries on.
    """
    family = _family_of(which)
    if family.lifecycle_status is LedgerLifecycleStatus.ACTIVE:
        return True
    LOG.warning(
        "ledger write skipped ledger=%s family=%s status=%s rows=%s",
        which.value,
        family.name,
        family.lifecycle_status.value,
        rows,
    )
    return False
