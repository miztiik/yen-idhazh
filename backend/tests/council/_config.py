"""Which named config files does a council command-line fixture need?"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from conftest import CONFIG_DIR

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.council import CouncilConfig


def copy_config(root: Path) -> Path:
    """Copy the loader's named inputs and the active model file, never the tree."""
    target = root / "config"
    target.mkdir(parents=True)
    for name in (
        "idhazh.json",
        "llm_council.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
        "ledgers.json",
    ):
        shutil.copyfile(CONFIG_DIR / name, target / name)
    app = AppConfig.from_json((target / "idhazh.json").read_text(encoding="utf-8"))
    model = target / app.models_file
    model.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONFIG_DIR / app.models_file, model)
    council = CouncilConfig.model_validate_json(
        (target / "llm_council.json").read_text(encoding="utf-8")
    )
    for name in council.judge_names:
        (target / "judges").mkdir(exist_ok=True)
        shutil.copyfile(CONFIG_DIR / "judges" / f"{name}.json", target / "judges" / f"{name}.json")
    return target


def write_declarations(target: Path, slugs: tuple[str, ...]) -> None:
    """Write explicit active, model-free declarations for the test's registered judges."""
    (target / "judges").mkdir(exist_ok=True)
    for slug in slugs:
        (target / "judges" / f"{slug}.json").write_text(
            json.dumps({"lifecycle_status": "active", "runs_model": False}),
            encoding="utf-8",
            newline="\n",
        )
