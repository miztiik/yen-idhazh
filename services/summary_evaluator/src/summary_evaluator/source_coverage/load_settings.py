"""How is the one named coverage configuration combined with shared transport bounds?"""

from pathlib import Path

from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings
from summary_evaluator.source_coverage.contracts.service_settings import (
    AuthoredCoverageSettings,
    CoverageSettings,
)


def load_settings(
    root: Path, listener: ListenerSettings, logging: LoggingSettings
) -> CoverageSettings:
    authored = AuthoredCoverageSettings.model_validate_json(
        (root / "config" / "summary-evals" / "unieval-evaluator" / "coverage.json").read_bytes()
    )
    return CoverageSettings(**authored.model_dump(), listener=listener, logging=logging)
