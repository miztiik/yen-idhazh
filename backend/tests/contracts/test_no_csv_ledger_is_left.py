"""Is any ledger still kept as CSV?

Every ledger now files through the ledger door, or files JSON at an address the
registry builds. Three checks, and each reads a fixed input (Guardrail #12): the
registry in `config/ledgers.json`, the `.gitattributes` file, and what
`git ls-files` names for two patterns under `state/`. None walks a tree.
"""

from __future__ import annotations

import subprocess
from typing import Final

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.ledger import paths

pytestmark = pytest.mark.contract

#: The grains a ledger files under: the door's own, and the two that address one
#: JSON document by its name or by its stamp.
DOOR_OR_ONE_DOCUMENT: Final = frozenset({Grain.RAW_AND_COMPACT, Grain.FLAT, Grain.STAMPED})

#: The ledgers that still file by day outside the door, each with its grain and
#: suffix. None is CSV: the day record is one JSON file a day, and a trace and a
#: run's block of a day are JSON files inside a day folder. A ledger added here
#: is a decision somebody wrote down, not a CSV tree that came back unseen.
FILED_BY_DAY: Final[dict[LedgerName, tuple[Grain, str | None]]] = {
    LedgerName.DAY_METRICS: (Grain.DAY_FILE, ".json"),
    LedgerName.TRACES: (Grain.DAY_TREE, None),
    LedgerName.DIGEST_FRAGMENTS: (Grain.DAY_TREE, None),
}

#: A committed CSV file under `state/`, at any depth.
STATE_CSV: Final = ("state/*.csv", "state/**/*.csv")


def test_no_ledger_in_the_registry_files_csv() -> None:
    """Fails when an entry names `.csv`, or files by day without a line above."""
    registry = LedgersConfig.from_json(read_text(CONFIG_DIR / paths.REGISTRY_FILENAME))
    held = paths.registry_entries(registry)

    as_csv = sorted(name.value for name, entry in held.items() if entry.suffix == ".csv")
    by_day = {
        name: (entry.grain, entry.suffix)
        for name, entry in held.items()
        if entry.grain not in DOOR_OR_ONE_DOCUMENT
    }

    assert as_csv == [], f"{', '.join(as_csv)} still file CSV; a ledger files through the door"
    assert by_day == FILED_BY_DAY, (
        "only the three JSON day trees named here file by day outside the door"
    )


def test_no_path_takes_a_union_merge() -> None:
    """A union merge stacked two appends to one CSV file, and no ledger appends to one now."""
    attributes = [
        line
        for line in read_text(REPO_ROOT / ".gitattributes").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert [line for line in attributes if "merge=union" in line] == []


def test_no_csv_file_is_committed_under_state() -> None:
    """Fails when any commit adds a CSV file under `state/`, at any depth."""
    committed = subprocess.run(
        ["git", "ls-files", "--", *STATE_CSV],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert committed == [], f"{len(committed)} CSV file(s) under state/, first {committed[:3]}"
