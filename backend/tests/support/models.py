"""Model-specific backend test inputs derived from committed config."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from idhazh import config
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.llm.server import TurnMarkers, server_argv, turn_markers_from_renderings

from .paths import CONFIG_DIR, DERIVED_TURN_MARKERS, read_text


def active_model_file(config_dir: Path = CONFIG_DIR) -> str:
    """Return the validated active model pointer from app config."""
    return config.load(config_dir).app.models_file


def committed_renderings(
    model_file: str | None = None, config_dir: Path = CONFIG_DIR
) -> dict[str, Any]:
    """Read the recorded template renderings for a named or active model."""
    active = config.load(config_dir) if model_file is None else None
    chosen = PurePosixPath(active.app.models_file).name if active is not None else model_file
    loaded = json.loads(read_text(DERIVED_TURN_MARKERS))
    if not isinstance(loaded, dict):
        raise TypeError("Derived turn markers must be a JSON object")
    entries = loaded.get("entries")
    if not isinstance(entries, dict):
        raise TypeError("Derived turn markers entries must be a JSON object")
    recorded = entries.get(chosen)
    if not isinstance(recorded, dict):
        raise KeyError(f"Derived turn markers have no entry for {chosen}")
    if active is not None and recorded.get("model_id") != active.models.summarizer.id:
        raise ValueError(
            f"Derived turn markers for {chosen} name {recorded.get('model_id')}, "
            f"not configured model {active.models.summarizer.id}"
        )
    return {str(key): value for key, value in recorded.items()}


def committed_markers(model_file: str | None = None, config_dir: Path = CONFIG_DIR) -> TurnMarkers:
    """Build markers from the recorded template for a named or active model."""
    recorded = committed_renderings(model_file, config_dir=config_dir)
    return turn_markers_from_renderings(
        model_id=str(recorded["model_id"]),
        plain=str(recorded["plain"]),
        thinking=str(recorded["thinking"]),
        history=str(recorded["history"]),
        thinking_close=recorded["thinking_close"],
        thinking_kwarg=recorded["thinking_kwarg"],
    )


def a_server(config_dir: Path = CONFIG_DIR, /, **flags: Any) -> dict[str, Any]:
    """Copy active server settings and override the fields under test."""
    return config.load(config_dir).models.summarizer.server | flags


def a_sampling(config_dir: Path = CONFIG_DIR, /, **values: Any) -> dict[str, Any]:
    """Copy active sampling settings and override the fields under test."""
    return config.load(config_dir).models.summarizer.sampling | values


def llama_server_flags(model_files: Sequence[str]) -> frozenset[str]:
    """Return flags emitted by an explicit list of model entries."""
    emitted: set[str] = set()
    for name in model_files:
        model = ModelsConfig.from_json(read_text(CONFIG_DIR / "models" / name)).summarizer
        emitted |= set(
            server_argv(
                binary=Path("bin/llama-server"),
                weights=Path("models/w.gguf"),
                model=model,
                server=model.server,
                port=8080,
            )
        )
    return frozenset(
        token
        for token in emitted
        if token.startswith("-") and token not in {"--model", "--threads"}
    )
