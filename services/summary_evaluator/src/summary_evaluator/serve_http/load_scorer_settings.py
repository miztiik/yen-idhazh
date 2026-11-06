"""How are enabled scorers given the shared listener and logging snapshot?"""

from pathlib import Path

from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.load_settings import SettingsLoadError
from summary_evaluator.hhem.load_settings import load_settings as read_hhem_settings
from summary_evaluator.serve_http.api_settings import ApiSettingsLoadError, load_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.load_unieval_settings import (
    load_unieval_settings as read_unieval_settings,
)


def load_hhem_settings(path: Path, api: ApiSettings | None = None) -> ServiceSettings:
    try:
        selected = api or load_api_settings(path.parent.parent / "api.json")
    except ApiSettingsLoadError:
        raise SettingsLoadError(
            "Invalid shared settings in config/summary-evals/api.json."
        ) from None
    return read_hhem_settings(
        path, selected.listener, selected.logging, enabled="hhem" in selected.enabled_routes
    )


def load_unieval_settings(root: Path, api: ApiSettings) -> UnievalSettings:
    settings = read_unieval_settings(root, api.listener, api.logging)
    if settings.worker.shutdown_timeout_ms > api.shutdown_timeout_ms:
        raise ValueError("The shared shutdown wait is shorter than the UniEval worker wait")
    return settings
