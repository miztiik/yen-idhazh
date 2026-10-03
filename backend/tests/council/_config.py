"""Which named config files does a council command-line fixture need?"""

from __future__ import annotations

import shutil
from pathlib import Path

from conftest import CONFIG_DIR

from idhazh.contracts.app_config import AppConfig


def copy_config(root: Path) -> Path:
    """Copy the loader's named inputs and the active model file, never the tree."""
    target = root / "config"
    target.mkdir(parents=True)
    for name in (
        "idhazh.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
    ):
        shutil.copyfile(CONFIG_DIR / name, target / name)
    app = AppConfig.from_json((target / "idhazh.json").read_text(encoding="utf-8"))
    model = target / app.models_file
    model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONFIG_DIR / app.models_file, model)
    return target
