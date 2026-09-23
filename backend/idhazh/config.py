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

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.run_manifest import ConfigDigest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.llm.server import SETTING_KEYS, refuse_a_sampling_key_a_route_sets

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR: Final = REPO_ROOT / "config"

_FILES: Final[tuple[str, ...]] = ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json")
#: Read for validation and not digested. It owns the console window every
#: cleanup age has to outlive, so a run that deletes a shard has to have checked
#: against the file the published console really reads - `AppConfig.console` is
#: the layer under it and can disagree. Its digest is not recorded because
#: nothing in the run reads a value out of it.
_APPEARANCE_FILE: Final = "appearance.json"


def refuse_a_model_nothing_could_run(models_file: str, models: ModelsConfig) -> None:
    """Four questions asked once, before anything is fetched and before any server.

    The settings blocks are plain mappings, so llama-server refuses a flag it
    does not accept and nothing here second-guesses it. These four are the ones
    the binary cannot answer for.

    **The window is required**, because this project computes on it and a
    default of ours beside a default of the server's is two answers for one
    value. It is real arithmetic in `idhazh.classify.dag` and
    `idhazh.evals.qualify`, and the published site reads it at build time. The
    per-request timeout is required too and the entry itself enforces that, so a
    string there raises naming the key rather than inside a request mid-item.

    **A sampling key that a route sets itself is refused here**, where an
    operator is reading a message about the file they just edited. Left to the
    builder it fires on the first item of every shard at once, after each has
    already restored the cache and loaded the weights.

    **`declared_for` catches one specific edit**: a weights string changed in
    place with the settings left behind. Nothing else in the tree sees a
    half-done model swap, and a stale weights reference is silent.

    **The judge rule catches a second entry naming weights nobody serves.** No
    server is started for it, so it decodes on the weights the summariser's
    server holds while every verdict is recorded under a model that never saw
    the pair.
    """
    for role, entry in models.entries():
        key = SETTING_KEYS["n_ctx"]
        if key not in entry.server:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} declares no {key}. "
                "This project computes on it, so there is no server-side default "
                "to fall back to"
            )
        taken = refuse_a_sampling_key_a_route_sets(entry.sampling)
        if taken is not None:
            raise ValueError(
                f"config/{models_file} is refused: models.{role}.sampling is not free "
                f"to set every key, and {taken}. A request key that re-spells or "
                "disables constrained decoding is the route's own"
            )
        if entry.declared_for != entry.sha256:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} is declared for "
                f"{entry.declared_for or 'no weights at all'} and names "
                f"{entry.sha256 or 'no weights at all'}. Every setting and every marker "
                "on that entry was derived against one model on one runner, so re-derive "
                f"them for these weights and set models.{role}.declared_for to the digest "
                "the entry carries - or put the entry back"
            )
        if role not in type(models).roles() and entry.sha256 != models.summarizer.sha256:
            raise ValueError(
                f"config/{models_file} is refused: models.{role} names weights "
                f"{entry.sha256 or 'nothing at all'} and models.summarizer names "
                f"{models.summarizer.sha256 or 'nothing at all'}. No server is started "
                f"for models.{role}, so it decodes on the weights the summariser's "
                "server holds - name those, or make it a role of its own"
            )


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
    refuse_a_model_nothing_could_run(app.models_file, models)
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
