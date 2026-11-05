"""Which merge line did the named published day's latest build record?"""

from __future__ import annotations

import logging

from idhazh.contracts.run_manifest import RunManifest

LOG = logging.getLogger("idhazh")


def read_published_line(
    date: str, *, manifest: RunManifest | None, floor_min: float
) -> float:
    """Choose from a compatible validated manifest, falling back only for absent evidence."""
    if manifest is None:
        reason = "missing_manifest"
    else:
        _, latest = max(
            enumerate(manifest.runs),
            key=lambda entry: (entry[1].completed_at or "", entry[0]),
        )
        if latest.same_story_floor_applied is not None:
            return latest.same_story_floor_applied
        reason = "null_applied_line"
    LOG.info(
        "pick-item-pairs date=%s legacy-fallback=%s floor_min=%s",
        date, reason, floor_min,
    )
    return floor_min
