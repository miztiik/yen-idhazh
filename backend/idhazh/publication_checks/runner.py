"""One publication-check run: read the days once, ask every check, report.

This module routes. It holds no rule of its own - what makes a day wrong lives
in `checks/`, and the only thing decided here is the day-shape parse every
check is entitled to assume, because a check that re-parsed the payload would
be reading the same bytes for the fourth time.

The parse is also the guarantee no writer can give itself: a day is read back
through `DigestDay` by the gate rather than by the stage that wrote it, so a
producer that stopped matching its own contract is caught by a different
reader (`CLAUDE.md` section 1a).

**The sweep grows with the archive** (Guardrail #12). `published_days` globs
the whole committed tree and no prune deletes a `digest.json`, so a run with no
`only` parses every day there has ever been. That read is what the question
needs: a contract change can invalidate any frozen day, and a bounded input
would answer it for some of them. Measured 2026-09-08 on an i7-1265U: 18 days,
19.87 MB, 0.45 s - about 44 MB/s. At the 727-day horizon the 1 GB Pages cap
sets, that is roughly 645 MB and about 15 s on a laptop, 30-60 s on the
4-vCPU runner, against a 6 h job - a 360 to 1440 times margin. The daily
publish never pays it: `digest.yml` names the one day it wrote.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from idhazh import ledger, run_context
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.publication_checks.registry import (
    CheckScope,
    CommittedDay,
    DayContext,
    PublicationCheckError,
    TreeContext,
    discover,
    validate_registry,
)
from idhazh.stages.common import LOG, published_days

#: One writer, one job, no fan-out - the gate reads the whole archive in one
#: process, so there is no second shard for a row to land in.
WHOLE_ARCHIVE_SHARD: Final = 0


def _day_of(path: Path) -> str:
    """`2026-09-01` out of `.../2026/09/01/digest.json`, for a log line."""
    parts = path.parts[-4:-1]
    return "-".join(parts) if len(parts) == 3 else path.as_posix()


def _parse_committed_days(paths: Sequence[Path]) -> tuple[list[CommittedDay], list[str]]:
    """Every day in scope, read once, plus a fault for each one that will not parse.

    Four ways a file fails before any rule looks at it, and each says which. A
    day that fails `DigestDay` is still handed on with `day=None`: the JSON
    object is there, so the projection check can still say whether a reader's
    browser would refuse it too, and reporting both in one run is the
    difference between one fix and two.
    """
    parsed: list[CommittedDay] = []
    faults: list[str] = []
    for path in paths:
        date = _day_of(path)
        try:
            payload = path.read_bytes()
        except OSError as error:
            faults.append(f"{date} cannot be read: {error.strerror or error}")
            continue
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as error:
            faults.append(f"{date} is not JSON: {error}")
            continue
        if not isinstance(raw, dict):
            faults.append(f"{date} is a {type(raw).__name__}, not a day")
            continue
        day: DigestDay | None
        try:
            day = DigestDay.model_validate(raw)
        except ValidationError as error:
            faults.append(
                f"{date} fails digest-day.schema.json: {error.error_count()} problems\n{error}"
            )
            day = None
        parsed.append(CommittedDay(date=date, path=path, payload=payload, raw=raw, day=day))
    return parsed, faults


def _file_rows(
    state_dir: Path,
    name: LedgerName,
    rows: tuple[Contract, ...],
    *,
    check: str,
    run_id: str,
    commit_sha: str,
) -> None:
    """One check's rows into its declared ledger, through the ledger door.

    A row that names its own day is filed under that day, and the run's own day
    is the day for a row that names none. The check's name is part of the
    producer: the door keeps one file per writer, so two checks filing one
    ledger in one run would otherwise be one writer, and the second file would
    replace the first.
    """
    ledger.persist(
        state_dir,
        rows,
        ledger=name,
        covers=run_id[:10],
        identity=WriterIdentity(
            run_id=run_id,
            attempt=run_context.run_attempt(),
            job=ServerJob.ASSEMBLE,
            shard=WHOLE_ARCHIVE_SHARD,
            producer=f"{__name__}:{check}",
            git_sha=commit_sha,
        ),
    )


def run_publication_checks(
    root: Path,
    only: Sequence[str] = (),
    *,
    state_dir: Path | None = None,
    run_id: str | None = None,
    commit_sha: str | None = None,
) -> int:
    """Every check on disk against the committed days, and what it costs to fail.

    **This exists because prerendering stopped proving it.** Until the reading
    decisions were split on 2026-09-01, every story a day published was
    serialised into a document at build time, so a story the contract refused
    took the build down before it could be merged. A reading document now
    carries a seed and a browser fetches the rest, so the build never opens the
    stories past the seed and a broken one reaches a reader instead of a log.
    The guarantee is weaker than it was and it is written down rather than
    hidden: a broken day can no longer be built, it can only no longer be
    merged.

    `only` names the days to open, as `YYYY-MM-DD`. Empty means every committed
    day. An empty tree fails, and so does a named day that is not there - a
    gate that checked nothing prints the same line as one that checked every
    day.

    A check that declares a ledger has its rows filed through the ledger door
    only when this run is day-scoped and has a state directory to write into,
    so a contract-change sweep over the whole archive re-reports without
    re-filing. Each file names the run and the commit that wrote it, so a
    filing run needs both.

    Returns 0 when nothing is wrong, 1 when something is. A wiring fault raises
    `PublicationCheckError`, which the CLI reports as exit 2.
    """
    committed = published_days(root)
    if not committed:
        LOG.error(
            "check-publication found no digest.json under %s - a run over nothing passes "
            "every contract",
            root.as_posix(),
        )
        return 1

    if only:
        wanted = set(only)
        committed = [path for path in committed if _day_of(path) in wanted]
        missing = sorted(wanted - {_day_of(path) for path in committed})
        if missing:
            LOG.error("check-publication was asked for days that are not committed: %s", missing)
            return 1

    registry = discover()
    validate_registry(registry)

    parsed, faults = _parse_committed_days(committed)
    day_context = DayContext(digest_root=root, public_root=root.parent, days=tuple(parsed))
    tree_context = TreeContext(
        root=root, months=frozenset(date[:7] for date in only) if only else None
    )
    filing = state_dir if only else None

    for check in registry:
        result = check.run(day_context if check.scope is CheckScope.DAY else tree_context)
        faults.extend(result.faults)
        if check.ledger is None:
            if result.rows:
                raise PublicationCheckError(
                    f"{check.name} declares no ledger and has nowhere to file "
                    f"{len(result.rows)} row(s)"
                )
            continue
        if filing is None:
            continue
        if run_id is None:
            raise PublicationCheckError(
                f"{check.name} files rows into {check.ledger.value} and this run has no "
                f"--run-id, so nothing would say which run wrote them"
            )
        if commit_sha is None:
            raise PublicationCheckError(
                f"{check.name} files rows into {check.ledger.value} and this run has no "
                f"--commit, so nothing would say which commit wrote them"
            )
        _file_rows(
            filing,
            check.ledger,
            result.rows,
            check=check.name,
            run_id=run_id,
            commit_sha=commit_sha,
        )

    for fault in faults:
        LOG.error("check-publication %s", fault)
    if faults:
        LOG.error(
            "check-publication: %s fault(s) over %s committed day(s). A reader's browser "
            "fetches these files and cannot be upgraded",
            len(faults),
            len(parsed),
        )
        return 1

    LOG.info("check-publication: %s committed days match every contract", len(parsed))
    return 0
