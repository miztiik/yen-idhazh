"""Load `config/` once, validate it, and hand it to the stages.

A stage never reads a file by itself and never reaches for an environment
variable. Everything tunable arrives here, schema-validated, so a bad config is
a startup failure with a readable message rather than a strange result four
hundred seconds into a run.

The digests of the files that were read travel with the run, because a knob
edited between two runs changes every output and is otherwise invisible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.run_manifest import ConfigDigest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR: Final = REPO_ROOT / "config"

_FILES: Final[tuple[str, ...]] = ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json")


@dataclass(frozen=True, slots=True)
class Settings:
    """Every tunable the run will consult, already validated."""

    app: AppConfig
    sources: Sources
    taxonomy: Taxonomy
    watchlist: Watchlist
    digests: tuple[ConfigDigest, ...]


def load(config_dir: Path = DEFAULT_CONFIG_DIR) -> Settings:
    """A fresh clone runs on the committed defaults; a missing file is a failure, not a default."""
    read = {name: (config_dir / name).read_text(encoding="utf-8") for name in _FILES}
    return Settings(
        app=AppConfig.from_json(read["idhazh.json"]),
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
