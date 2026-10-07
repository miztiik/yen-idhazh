"""Which recorded config preserves the cleanup windows before yearly expiry was enabled?"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Final

from conftest import FIXTURES_DIR

from ._garden import COMMITTED_FILES

# Recorded from c8251c596, before the owner approved finite yearly retention.
PRE_YEARLY_CONFIG: Final = FIXTURES_DIR / "gardener" / "pre-yearly-retention" / "config"


def copy_pre_yearly_config(root: Path) -> Path:
    """Copy the three config files and the declarations their named task list selects."""
    destination = root / "config"
    (destination / "gardener").mkdir(parents=True, exist_ok=True)
    for name in COMMITTED_FILES:
        shutil.copyfile(PRE_YEARLY_CONFIG / name, destination / name)
    names = json.loads((PRE_YEARLY_CONFIG / "idhazh_gardener.json").read_text(encoding="utf-8"))[
        "task_names"
    ]
    for name in names:
        shutil.copyfile(
            PRE_YEARLY_CONFIG / "gardener" / f"{name}.json",
            destination / "gardener" / f"{name}.json",
        )
    return destination
