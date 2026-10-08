"""How does a row a judge wrote reach the ledger that judge names?

The council's own path, end to end: one unit of work writes one file on its own
runner, the workflow uploads that directory, and the collecting job files what
it downloaded through the ledger door into the ledger the tenant named, under
the writer identity the tenant hands it. Every file the door writes has one
writer, so the collecting job never shares a file with another run.

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
from idhazh.contracts.base import SLUG_PATTERN, Contract, DateStamp
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council.tenancy import JudgeRow

_SLUG: Final = re.compile(SLUG_PATTERN)

#: What a shipped file is called. One a unit, named for that unit, so the
#: collecting job can merge every tenant's upload into one tree without a collision.
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


def ship_judge_metrics(row: JudgeRow, *, judge_id: str, name: str, out_dir: Path) -> Path:
    """Write one unit's row where the workflow can upload it. Returns the file.

    Temp-file-then-rename, so a job killed part way through leaves the
    collecting job no half-written row to parse. Rendering is the validation: the
    row is written under the columns its own class names, so a cell the contract
    declares and the row does not carry fails here rather than arriving in a
    committed ledger as an empty string.

    `name` is checked before it becomes a path component. A step may not be a
    shard, and reading a tenant's field by name is the coupling this path removes.
    """
    directory = _shipped_dir(out_dir, judge_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{checked_slug(name)}{SHIPPED_SUFFIX}"
    document = ledger.render_file(type(row).csv_columns(), [row.csv_row()])
    scratch = directory / f"{path.stem}.{os.getpid()}.tmp"
    scratch.write_text(document, encoding="utf-8", newline="")
    scratch.replace(path)
    return path


def shipped_rows[Row: JudgeRow](
    shipped_root: Path, *, judge_id: str, contract: type[Row]
) -> list[Row]:
    """Every row one tenant's units shipped, through the contract that wrote them.

    Split out from the filing below because the council's own record goes to a
    ledger the session files itself, and this is the half of the trip the two
    payloads share.

    A file an upload truncated fails here rather than reaching a committed
    ledger. What it reads is bounded by how many units the run split into, not by
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
    shipped_root: Path,
    *,
    judge_id: str,
    contract: type[JudgeRow],
    which: LedgerName,
    state_dir: Path,
    covers: DateStamp,
    identity: WriterIdentity,
) -> int:
    """File every shipped row through the ledger door, into the ledger the tenant named.

    Returns how many landed. `which` and `identity` are handed in by the tenant,
    so the council spells no judge's ledger and a second tenant needs no change
    here. The door asks the ledger's family whether it takes new rows, so a
    paused or retired family files nothing and says so once.

    The door files a contract, so a row class that is not one is refused before
    a shipped file is read.
    """
    if not issubclass(contract, Contract):
        raise TypeError(
            f"{contract.__name__} is not a contract, so the ledger door has no shape to "
            "file its rows under"
        )
    rows = shipped_rows(shipped_root, judge_id=judge_id, contract=contract)
    filed = ledger.persist(state_dir, rows, ledger=which, covers=covers, identity=identity)
    return len(rows) if filed else 0


def _rows_of(path: Path) -> list[dict[str, str]]:
    """One shipped file, as the cells it carries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
