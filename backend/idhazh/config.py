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
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Final

from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.turns import TURN_ROLE, TurnsConfig
from idhazh.contracts.knobs.windows import months_a_window_can_touch
from idhazh.contracts.run_manifest import ConfigDigest
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.contracts.watchlist import Watchlist
from idhazh.sanitize import why_a_forged_turn_would_survive

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR: Final = REPO_ROOT / "config"

_FILES: Final[tuple[str, ...]] = ("idhazh.json", "sources.json", "taxonomy.json", "watchlist.json")
#: Read for validation and not digested. It owns the console window every
#: cleanup age has to outlive, so a run that deletes a shard has to have checked
#: against the file the published console really reads - `AppConfig.console` is
#: the layer under it and can disagree. Its digest is not recorded because
#: nothing in the run reads a value out of it.
_APPEARANCE_FILE: Final = "appearance.json"

#: The roles `idhazh.llm.server.TurnMarkers.conversation` substitutes into the
#: turn opening. A marker is checked as the bytes an attacker would have to
#: write into an article, and those bytes carry a role.
_RENDERED_ROLES: Final = ("system", "user")


def _forgeable_markers(turns: TurnsConfig) -> Iterator[tuple[str, str]]:
    """Every marker a forged turn could be spelled with, rendered.

    `system_joiner` is not one of them. It separates two blocks inside one turn
    rather than opening or closing a turn, and every template that folds joins
    with ordinary whitespace - a rule demanding the pattern recognise it would
    refuse a joiner of two newlines.

    `safe_substitute`, where `TurnMarkers.turn` is strict. A marker naming some
    other placeholder is a real failure and it already has a message: it raises
    at the first render. Repeating it here as a `KeyError` out of config load
    would only bury the one this function exists to report.
    """
    for role in _RENDERED_ROLES:
        yield "turn_opening", Template(turns.turn_opening).safe_substitute({TURN_ROLE: role})
    yield "turn_closing", turns.turn_closing
    yield "reply_opening", turns.reply_opening
    yield "reply_opening_thinking", turns.reply_opening_thinking


def refuse_markers_the_boundary_cannot_hold(models_file: str, models: ModelsConfig) -> None:
    """An entry whose turn markers survive sanitization is refused at load.

    The control-token pattern in `idhazh.sanitize` is what keeps a forged turn
    out of an article (Guardrail #11), and it knows the families it was written
    for. An entry may name weights from a family it does not - and then the
    first article carrying that family's markers is what finds out, which is
    finding out too late. So the question is asked once, over the markers the
    entry declares, before anything is fetched.

    **Every entry the file declares, not only the served roles.** A second entry
    is rendered into a prompt exactly as the first one is, so an entry whose
    markers a forged turn survives is the same hole wherever it sits.

    **It cannot be a validator on `TurnsConfig`.** `backend/idhazh/contracts/`
    is the bottom of the dependency graph and may import no other subpackage
    (`CLAUDE.md` section 4), so a contract cannot ask the sanitizer anything. It
    is here rather than at extraction because this is the one place every run
    reads `config/`, and it already refuses a models file for a shape the
    contract caught.
    """
    for role, entry in models.entries():
        for field, marker in _forgeable_markers(entry.turns):
            surviving = why_a_forged_turn_would_survive(marker)
            if surviving is None:
                continue
            raise ValueError(
                f"config/{models_file} is refused: models.{role}.turns.{field} renders "
                f"{marker!r}, and {surviving}. An article carrying that marker would "
                "reach this model with the turn boundary intact. Teach the family to "
                "backend/idhazh/sanitize.py and move SANITIZER_VERSION with it, or name "
                "a model whose markers it already strips"
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
    refuse_markers_the_boundary_cannot_hold(app.models_file, models)
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
