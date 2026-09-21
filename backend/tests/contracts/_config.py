"""Committed-config readers the config modules share."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from conftest import FIXTURES_DIR

#: Every place `pipeline_fingerprint` may still be named in source a person
#: wrote or a generator emits, and why. The removal cannot be gated on "the name
#: appears nowhere": the read-side migration has to name the key it pops, and one
#: shape still declares the field because the console still reads its column. So
#: the gate is that every mention is one of these, with its reason beside it.
FINGERPRINT_SURVIVORS: Final[dict[str, str]] = {
    "backend/idhazh/contracts/day_metrics.py": (
        "the popper: 23 committed state/day-metrics/ records and both published "
        "month mirrors carry the key, and extra=forbid refuses it"
    ),
    "backend/idhazh/contracts/run_manifest.py": (
        "the popper, spelled plural: every run.json committed before the key was "
        "dropped carries pipeline_fingerprints, and a published day is never rewritten"
    ),
    "backend/idhazh/contracts/eval_row.py": (
        "the one field that survives the drop, because the console reads its "
        "state/scores/ column for every day that recorded its identity that way - "
        "the condition that removes it is on the line that declares it"
    ),
    "frontend/src/contracts/eval-row.ts": (
        "generated from the field above, so it goes when that field goes and "
        "cannot be edited out on its own"
    ),
    "backend/idhazh/contracts/score_archive.py": "a changelog entry and a docstring, both history",
    "backend/idhazh/contracts/evidence.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/label_row.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/qualification.py": "a changelog entry, which is history",
    "backend/idhazh/contracts/summary.py": "a changelog entry, which is history",
    "frontend/src/lib/server/model-work.ts": (
        "the arm that reads a day whose identity is a digest, and the precedence "
        "that lets a manifest beside one win. It retires on the condition written "
        "beside the field itself, which is about the rows and not about a date"
    ),
    "frontend/src/lib/console/eval-instruments.ts": (
        "the ledger column's own note, which says why no panel draws it"
    ),
}


#: The two shapes that carry a read-side migration for the retired key, the key
#: each one pops, and the misspelling that must still be refused. `RunRecord`
#: spells it plural, so one shared key constant in `base.py` would have covered
#: neither model honestly. Each misspelling is the key with one letter gone,
#: which is the shape a hand-written payload actually takes.
FINGERPRINT_POPPERS: Final[dict[str, tuple[str, str]]] = {
    "DayMetrics": ("pipeline_fingerprint", "pipeline_fingerprnt"),
    "RunManifest": ("pipeline_fingerprints", "pipeline_fingerprnts"),
}


#: One payload per popped shape, copied out of the committed archive so the
#: oracle reads a fixed file rather than whatever a run last wrote. They sit
#: outside `tests/fixtures/contracts/` on purpose: every file under that tree is
#: asserted to round-trip byte-identically through its own shape, and a payload
#: of the PREVIOUS shape cannot, which is the whole point of it.
FINGERPRINT_FIXTURES: Final[dict[str, Path]] = {
    "DayMetrics": FIXTURES_DIR / "retired-fingerprint" / "day-metrics.json",
    "RunManifest": FIXTURES_DIR / "retired-fingerprint" / "run-manifest.json",
}


def misspell(node: Any, key: str, wrong: str) -> Any:
    """The same payload with one key renamed, wherever in the tree it sits."""
    if isinstance(node, dict):
        return {(wrong if name == key else name): misspell(v, key, wrong) for name, v in node.items()}
    if isinstance(node, list):
        return [misspell(value, key, wrong) for value in node]
    return node
