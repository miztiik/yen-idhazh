"""Which committed bounds and names govern one manual caller?"""

from pathlib import Path

from pydantic import ValidationError

from .contracts.base import ContextIdentity, NativeContract, PositiveCount


class ManualSettings(NativeContract):
    event_envelope_bytes: PositiveCount
    max_response_bytes: PositiveCount
    control_max_bytes: PositiveCount
    http_connect_timeout_ms: PositiveCount
    poll_interval_ms: PositiveCount
    pipeline_name: ContextIdentity
    task_name: ContextIdentity


def load_manual_settings(root: Path) -> ManualSettings:
    path = root / "config" / "hhem-evaluator" / "workflow.json"
    try:
        return ManualSettings.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        raise ValueError("The committed manual workflow settings are invalid.") from None
