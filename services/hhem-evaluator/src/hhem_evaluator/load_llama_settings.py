"""How are the private address and request deadline read from named model configuration?"""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, StringConstraints, ValidationError

from .contracts.llama_settings import LlamaSettings


class _ConfigProjection(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", allow_inf_nan=False)


class _ModelServer(_ConfigProjection):
    base_url: StrictStr


class _SelectedConfiguration(_ConfigProjection):
    model_server: _ModelServer
    models_file: Annotated[
        str, StringConstraints(pattern=r"^models/[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
    ]


class _RequestDeadline(_ConfigProjection):
    request_timeout_minutes: Annotated[float, Field(gt=0)]


class _SelectedDeclaration(_ConfigProjection):
    summarizer: _RequestDeadline


def load_llama_settings(path: Path) -> LlamaSettings:
    """Project only the values this client computes on; do not load or choose weights."""
    try:
        selected = _SelectedConfiguration.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        raise ValueError(
            "Invalid model_server.base_url or models_file in model configuration."
        ) from None
    try:
        declaration = _SelectedDeclaration.model_validate_json(
            (path.parent / selected.models_file).read_bytes()
        )
        return LlamaSettings(
            base_url=selected.model_server.base_url,
            request_timeout_ms=declaration.summarizer.request_timeout_minutes * 60_000,
        )
    except (OSError, ValidationError):
        raise ValueError(
            "Invalid summarizer.request_timeout_minutes or model_server.base_url."
        ) from None
