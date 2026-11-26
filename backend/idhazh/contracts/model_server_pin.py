"""Which launcher-owned model process may supply serving observations?"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final, Literal

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract
from idhazh.contracts.recorded_instant import RecordedInstant

MODEL_SERVER_PIN_VERSION: Final = "2026-11-26"


class ModelServerPin(Contract):
    """Private launch evidence, not a model result or publication artifact."""

    __schema_stem__: ClassVar[str] = "model-server-pin"
    __require_explicit_version__: ClassVar[bool] = True
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version=MODEL_SERVER_PIN_VERSION,
            change="Identify the local model process that supplies serving readings.",
            why="A reused PID or a different listener must not supply another server's readings.",
        ),
    )

    version: Literal["2026-11-26"]
    pid: Annotated[int, Field(strict=True, gt=0)]
    start_ticks: Annotated[int, Field(strict=True, ge=0)]
    started_at: RecordedInstant
