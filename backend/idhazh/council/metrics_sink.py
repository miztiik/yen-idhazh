"""How does a row a judge wrote reach the store that judge names?

The council's own path, end to end: one unit of work writes one file on its own
runner, the workflow uploads that directory, and the collecting job appends what
it downloaded to the store the tenant named. Deliberately not the digest
pipeline's segment store - that machinery exists to stop many committing writers
conflicting on one file, and the council has one committing writer whose day file
is already settled by a key carrying the run id.

**This file declares nothing about what is in the payload.** It renders the row
the tenant handed it, and reads one back through the tenant's own contract. A
tenant may rename every column it files without a line here moving.
"""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Final, cast

from idhazh import ledger
from idhazh.contracts.base import SLUG_PATTERN
from idhazh.council.tenancy import JudgeRow

_SLUG: Final = re.compile(SLUG_PATTERN)

#: What a shipped file is called. One a shard, named for the shard, so the
#: collecting job can merge every tenant's upload into one tree and still tell
#: which unit wrote which row.
SHIPPED_SUFFIX: Final = ".csv"


def checked_slug(judge_id: str) -> str:
    """The slug back, refused unless a path may be built out of it.

    The value arrives from a tenant's own module constant and never from fetched
    text, and a path built from an unchecked string is a hole whether or not
    anything is coming through it today. Public because every directory and
    every filename inside the carried root takes the slug, so one check has to
    cover all of them.
    """
    if not _SLUG.match(judge_id):
        raise ValueError(
            f"a judge id becomes a path component here, and {judge_id!r} is not a slug"
        )
    return judge_id


def _shipped_dir(root: Path, judge_id: str) -> Path:
    """Where one tenant's shipped files sit under a run directory.

    The slug is a directory level rather than part of a filename, so two tenants'
    shard 0 do not collide when the collecting job merges every artifact into one
    tree.
    """
    return root / checked_slug(judge_id)


def ship_judge_metrics(row: JudgeRow, *, judge_id: str, shard: int, out_dir: Path) -> Path:
    """Write one unit's row where the workflow can upload it. Returns the file.

    Temp-file-then-rename, so a job killed part way through leaves the
    collecting job no half-written row to parse. Rendering is the validation: the
    row is written under the columns its own class names, so a cell the contract
    declares and the row does not carry fails here rather than arriving in a
    committed store as an empty string.

    `shard` is a parameter rather than a cell read off the row, because reading a
    tenant's field by name is the coupling this whole path exists to remove.
    """
    directory = _shipped_dir(out_dir, judge_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{shard}{SHIPPED_SUFFIX}"
    document = ledger.render_file(type(row).csv_columns(), [row.csv_row()])
    scratch = directory / f"{path.stem}.{os.getpid()}.tmp"
    scratch.write_text(document, encoding="utf-8", newline="")
    scratch.replace(path)
    return path


def shipped_rows[Row: JudgeRow](
    shipped_root: Path, *, judge_id: str, contract: type[Row]
) -> list[Row]:
    """Every row one tenant's units shipped, through the contract that wrote them.

    Split out from the append below because the council's own record goes to a
    store this module must not name: it is appended by the ledger writer that
    owns that store's settlement key, and this is the half of the trip the two
    payloads share.

    A file an upload truncated fails here rather than reaching a committed
    store. What it reads is bounded by how many units the run split into, not by
    anything the archive has accumulated (Guardrail #12).
    """
    # `CsvContract` declares its reader as returning the row protocol rather than
    # the class's own type, so the caller's contract is what names the row here.
    return cast(
        "list[Row]",
        [
            contract.from_csv_row(raw)
            for path in sorted(_shipped_dir(shipped_root, judge_id).glob(f"*{SHIPPED_SUFFIX}"))
            for raw in _rows_of(path)
        ],
    )


def collect_judge_metrics(
    shipped_root: Path, *, judge_id: str, contract: type[JudgeRow], into: Path
) -> int:
    """Append every shipped row to the store the tenant named. Returns how many landed.

    `into` is handed in by the tenant, so the council spells no judge's store
    path and a second tenant needs no change here.
    """
    rows = shipped_rows(shipped_root, judge_id=judge_id, contract=contract)
    return ledger.extend_ledger_file(into, contract.csv_columns(), rows)


def _rows_of(path: Path) -> list[dict[str, str]]:
    """One shipped file, as the cells it carries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
