"""Which body-free lifecycle facts can independent process logs share?"""

from typing import Literal

from pydantic import Field

from hhem_evaluator.contracts.server_contract import ServerContract
from hhem_evaluator.shared.contracts.base import Milliseconds, RelativePath, Uuid4
from hhem_evaluator.shared.contracts.optional_fields import is_absent

DiagnosticAction = Literal[
    "started", "ready", "stopped", "failed", "cancelled", "unavailable", "completed"
]


class LifecycleFields(ServerContract):
    action: DiagnosticAction
    level: Literal["INFO", "WARNING", "ERROR"]
    code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$", exclude_if=is_absent)
    http_status: int | None = Field(default=None, ge=100, le=599, exclude_if=is_absent)
    duration_ms: Milliseconds | None = Field(default=None, exclude_if=is_absent)
    log_file: RelativePath | None = Field(default=None, exclude_if=is_absent)
    execution_id: Uuid4 | None = Field(default=None, exclude_if=is_absent)
