"""Which unchanged schema date and vocabularies identify HHEM scoring?"""

from typing import Final, Literal

SCHEMA_VERSION: Final = "2026-11-02"

SchemaVersion = Literal["2026-11-02"]

Operation = Literal["service", "worker", "request", "queue", "primary", "full"]

Comparison = Literal["primary", "full"]

OutcomeStatus = Literal["complete", "partial", "failed"]
