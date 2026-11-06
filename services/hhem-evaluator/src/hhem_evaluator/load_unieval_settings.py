"""How is the named UniEval configuration combined with the one shared listener?"""

from pathlib import Path

from pydantic import ValidationError

from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.unieval_settings import AuthoredUnievalSettings, UnievalSettings


def load_unieval_settings(root: Path, api: ApiSettings) -> UnievalSettings:
    try:
        authored = AuthoredUnievalSettings.model_validate_json(
            (root / "config" / "unieval-evaluator.json").read_bytes()
        )
    except OSError:
        raise ValueError("config/unieval-evaluator.json could not be read") from None
    except ValidationError as error:
        location = error.errors(include_input=False, include_context=False)[0]["loc"]
        field = ".".join(str(part) for part in location)
        raise ValueError(f"Invalid config/unieval-evaluator.json field: {field}") from None
    if authored.worker.shutdown_timeout_ms > api.shutdown_timeout_ms:
        raise ValueError("The shared shutdown wait is shorter than the UniEval worker wait")
    return UnievalSettings(
        **authored.model_dump(),
        listener=api.listener,
        logging=api.logging,
    )
