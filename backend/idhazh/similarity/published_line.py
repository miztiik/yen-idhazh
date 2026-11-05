"""Which merge line did the named published day's latest build record?"""

from __future__ import annotations

import logging
from pathlib import Path

from idhazh.contracts.run_manifest import RunManifest

LOG = logging.getLogger("idhazh")


def read_published_line(date: str, *, manifest_path: Path, floor_min: float) -> float:
    """Validate one manifest; use the configured floor only for absent legacy evidence."""
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        reason = "missing_manifest"
    else:
        manifest = RunManifest.from_json(text)
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
