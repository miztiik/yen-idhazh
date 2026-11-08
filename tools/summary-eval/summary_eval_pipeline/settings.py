"""Which committed bounds and instruction govern the summary workflow?"""

from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, ValidationError
from summary_evaluator.shared.contracts.base import (
    ContextIdentity,
    NonblankText,
    PositiveCount,
    RelativePath,
)
from summary_evaluator.shared.contracts.prompt_files import PromptFile
from summary_evaluator.shared.contracts.service_settings import LoggingSettings
from summary_evaluator.shared.load_prompt_text import load_prompt_text

from .contracts import WorkflowContract


class PipelineControls(WorkflowContract):
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


class AuthoredPipelineSettings(PipelineControls):
    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-07",
            "readCompatibility": (
                "current_only; resolve the prompt into unchanged workflow controls"
            ),
            "changelog": [
                {"version": "2026-11-07", "change": "Name the generation instruction file."},
                {
                    "version": "2026-11-05",
                    "change": "Declare independent native workflow controls.",
                },
            ],
        }
    )
    version: Literal["2026-11-07"]
    generation_prompt_file: PromptFile


class PipelineSettings(PipelineControls):
    generation_instruction: NonblankText


def load_pipeline_settings(root: Path) -> PipelineSettings:
    path = root / "config" / "summary-evals" / "workflow.json"
    try:
        authored = AuthoredPipelineSettings.model_validate_json(path.read_bytes())
        return PipelineSettings(
            **authored.model_dump(exclude={"version", "generation_prompt_file"}),
            generation_instruction=load_prompt_text(
                root / "config", authored.generation_prompt_file
            ),
        )
    except OSError:
        raise ValueError("The committed manual workflow settings are invalid.") from None
    except ValidationError as error:
        location = error.errors(include_input=False, include_context=False)[0]["loc"]
        field = ".".join(str(part) for part in location)
        raise ValueError(f"The committed manual workflow settings are invalid: {field}.") from None
