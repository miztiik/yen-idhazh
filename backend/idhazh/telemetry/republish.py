"""How does a day already on disk publish its instrument again?

`stages/assemble.py` publishes a day it has just built, from run payloads under
`backend/var/` that no commit keeps. This is the other way in: the day is
already in the published tree, so its own `digest.json` and `run.json` are the
inputs, and every projection is written again from those.

It derives the paths and opens the payloads that `dispatch.py` is forbidden to
touch, then hands `publish_all` exactly the inputs that call takes. There is one
dispatcher and this is not a second one - both entries walk the same
`PROJECTIONS` tuple, in the same order, once each.

Outside `publish/` on purpose. That package is one dispatcher and the ten
projections it routes to, and a module in it that is not a projection is a
payload no run writes. This file is a caller of the dispatcher, which is what
`stages/assemble.py` is too, and neither of them lives in there.

Reading the day back is what makes this bounded. One date names one directory
and one month, so the work does not grow with the archive (Guardrail #12).
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path

from idhazh.assemble import day_dir, month_of, read_taxonomy_vectors
from idhazh.config import Settings
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.run_manifest import RunManifest
from idhazh.telemetry.publish.dispatch import Published, publish_all


def republish_day(
    *,
    state_root: Path,
    digest_root: Path,
    date: str,
    settings: Settings,
    repo_root: Path,
) -> Published:
    """Dispatch every projection again for one published day.

    The run identity comes off the manifest rather than off the clock. A day's
    last run is the one that wrote the payloads in the directory, so publishing
    against a fresh run id would file this under a run that never happened.
    """
    target = day_dir(digest_root, date)
    day = DigestDay.read(target / "digest.json")
    manifest = RunManifest.read(target / "run.json")
    return publish_all(
        state_root=state_root,
        digest_root=digest_root,
        date=date,
        month=month_of(date),
        today=date_type.fromisoformat(date),
        run_id=manifest.runs[-1].run_id,
        generated_at=day.generated_at,
        day=day,
        manifest=manifest,
        settings=settings,
        taxonomy_vectors=read_taxonomy_vectors(repo_root, settings.taxonomy),
    )
