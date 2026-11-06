"""Which committed bounds and instruction govern the summary workflow?"""

from pathlib import Path

from hhem_evaluator.shared.contracts.base import (
    ContextIdentity,
    NonblankText,
    PositiveCount,
    RelativePath,
)
from hhem_evaluator.shared.contracts.service_settings import LoggingSettings
from pydantic import ValidationError

from .contracts import WorkflowContract


class PipelineSettings(WorkflowContract):
    event_envelope_bytes: PositiveCount
    max_input_bytes: PositiveCount
    max_generation_request_bytes: PositiveCount
    max_generation_response_bytes: PositiveCount
    max_response_bytes: PositiveCount
    control_max_bytes: PositiveCount
    http_connect_timeout_ms: PositiveCount
    poll_interval_ms: PositiveCount
    pipeline_name: ContextIdentity
    task_name: ContextIdentity
    output_directory: RelativePath
    generation_instruction: NonblankText
    native_startup_timeout_ms: PositiveCount
    native_shutdown_timeout_ms: PositiveCount
    native_forced_stop_ms: PositiveCount
    native_max_metadata_bytes: PositiveCount
    native_quiet_flags: tuple[str, ...]
    native_logging: LoggingSettings
    native_log_directory: RelativePath
    host_startup_timeout_ms: PositiveCount
    host_shutdown_timeout_ms: PositiveCount
    host_stop_grace_ms: PositiveCount
    host_forced_stop_ms: PositiveCount


def load_pipeline_settings(root: Path) -> PipelineSettings:
    path = root / "config" / "summary-eval-tests.json"
    try:
        return PipelineSettings.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        raise ValueError("The committed manual workflow settings are invalid.") from None
