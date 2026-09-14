"""Load `config/` once, validate it, and hand it to the stages.

A stage never reads a file by itself and never reaches for an environment
variable. Everything tunable arrives here, schema-validated, so a bad config is
a startup failure with a readable message rather than a strange result four
hundred seconds into a run.

The digests of the files that were read travel with the run, because a knob
edited between two runs changes every output and is otherwise invisible. The
active model's file is one of them: it is named by `models_file` rather than
fixed, so a run that did not record it could not say which model's numbers it
read.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig, ModelsConfig, months_a_window_can_touch
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.run_manifest import ConfigDigest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR: Final = REPO_ROOT / "config"

_FILES: Final[tuple[str, ...]] = ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json")
#: Read for validation and not digested. It owns the console window every
#: cleanup age has to outlive, so a run that deletes a shard has to have checked
#: against the file the published console really reads - `AppConfig.console` is
#: the layer under it and can disagree. Its digest is not recorded because
#: nothing in the run reads a value out of it.
_APPEARANCE_FILE: Final = "appearance.json"

#: The turn envelope lived here until 2026-09-13 and now lives on the model
#: entry (`models.<role>.turns`). The path is checked rather than forgotten
#: because the package location is exactly where somebody would put it back, and
#: a file nothing reads is a set of markers an operator believes are live.
RETIRED_TURN_MARKERS: Final = Path(__file__).parent / "prompts" / "turn_markers.json"


def models_path(config_dir: Path, app: AppConfig) -> Path:
    """Where the active model is, following the pointer and nothing else.

    One function so that a test, an operator utility and the loader all resolve
    it the same way. The grammar on `AppConfig.models_file` is what keeps this
    inside `config/models/`, so this joins rather than checks.
    """
    return config_dir / app.models_file


@dataclass(frozen=True, slots=True)
class Settings:
    """Every tunable the run will consult, already validated."""

    app: AppConfig
    models: ModelsConfig
    appearance: AppearanceConfig
    sources: Sources
    taxonomy: Taxonomy
    watchlist: Watchlist
    digests: tuple[ConfigDigest, ...]


def load(config_dir: Path = DEFAULT_CONFIG_DIR) -> Settings:
    """A fresh clone runs on the committed defaults; a missing file is a failure, not a default."""
    if RETIRED_TURN_MARKERS.exists():
        raise ValueError(
            f"{RETIRED_TURN_MARKERS.name} is back in backend/idhazh/prompts/ and nothing "
            "reads it. The turn envelope is models.<role>.turns in the file "
            "config/idhazh.json points models_file at, pinned to the weights by "
            "declared_for - delete this file and edit the entry"
        )
    read = {name: (config_dir / name).read_text(encoding="utf-8") for name in _FILES}
    app = AppConfig.from_json(read["idhazh.json"])
    read[app.models_file] = models_path(config_dir, app).read_text(encoding="utf-8")
    try:
        models = ModelsConfig.from_json(read[app.models_file])
    except ValidationError as error:
        # Which file, named in the first line. Every model has a file of its own
        # now, so the one thing a refusal could no longer say for itself is the
        # one an operator needs before they can edit anything.
        raise ValueError(f"config/{app.models_file} is refused: {error}") from error
    appearance = AppearanceConfig.from_json(
        (config_dir / _APPEARANCE_FILE).read_text(encoding="utf-8")
    )
    window = appearance.console.max_window_days
    app.observability.refuse_windows_shorter_than(
        months_a_window_can_touch(window), window_days=window
    )
    return Settings(
        app=app,
        models=models,
        appearance=appearance,
        sources=Sources.from_json(read["sources.json"]),
        taxonomy=Taxonomy.from_json(read["taxonomy.json"]),
        watchlist=Watchlist.from_json(read["watchlist.json"]),
        digests=tuple(
            ConfigDigest(
                path=f"config/{name}",
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
            for name, text in sorted(read.items())
        ),
    )
