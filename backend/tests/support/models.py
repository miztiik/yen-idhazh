"""Build explicit turn markers and read selected model settings for tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from string import Template
from typing import Any

from idhazh import config
from idhazh.llm.server import SystemPlacement, TurnMarkers

from .paths import CONFIG_DIR


def active_model_file(config_dir: Path = CONFIG_DIR) -> str:
    """Return the validated active model pointer from app config."""
    return config.load(config_dir).app.models_file


def a_markers(**overrides: Any) -> TurnMarkers:
    """Build a fixed protocol input, not a recording or the selected model's template."""
    return replace(
        TurnMarkers(
            turn_opening=Template("<|im_start|>${role}\n"),
            turn_closing="<|im_end|>\n",
            reply_opening="<|im_start|>assistant\n",
            reply_opening_thinking="<|im_start|>assistant\n<think>\n",
            system_role=SystemPlacement.OWN_TURN,
            system_joiner="",
            thinking_close=None,
            thinking_kwarg="enable_thinking",
        ),
        **overrides,
    )


def a_server(config_dir: Path | None = None, /, **flags: Any) -> dict[str, Any]:
    """Build test settings, or copy a selected config when explicitly requested."""
    server = (
        {"--ctx-size": 8192}
        if config_dir is None
        else config.load(config_dir).models.summarizer.server
    )
    return server | flags


def a_sampling(config_dir: Path | None = None, /, **values: Any) -> dict[str, Any]:
    """Build test sampling, or copy a selected config when explicitly requested."""
    sampling = {} if config_dir is None else config.load(config_dir).models.summarizer.sampling
    return sampling | values
