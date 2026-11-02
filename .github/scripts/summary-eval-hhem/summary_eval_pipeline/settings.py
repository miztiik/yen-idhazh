"""Which committed bounds and names govern one manual caller?"""

from pathlib import Path

from hhem_evaluator.contracts.base import (
    ContextIdentity,
    NativeContract,
    PositiveCount,
    RelativePath,
)
from pydantic import ValidationError


class PipelineSettings(NativeContract):
    event_envelope_bytes: PositiveCount
    max_response_bytes: PositiveCount
    control_max_bytes: PositiveCount
    http_connect_timeout_ms: PositiveCount
    poll_interval_ms: PositiveCount
    pipeline_name: ContextIdentity
    task_name: ContextIdentity
    output_directory: RelativePath


def load_pipeline_settings(root: Path) -> PipelineSettings:
    path = root / "config" / "summary-eval-hhem.json"
    try:
        return PipelineSettings.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        raise ValueError("The committed manual workflow settings are invalid.") from None
