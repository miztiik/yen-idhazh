"""How is the named UniEval configuration combined with the one shared listener?"""

from pathlib import Path

from pydantic import ValidationError

from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings
from summary_evaluator.shared.load_prompt_text import load_prompt_text
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_settings import (
    AuthoredUnievalSettings,
    UnievalSettings,
)


def load_unieval_settings(
    root: Path, listener: ListenerSettings, logging: LoggingSettings
) -> UnievalSettings:
    try:
        authored = AuthoredUnievalSettings.model_validate_json(
            (root / "config" / "summary-evals" / "unieval-evaluator" / "settings.json").read_bytes()
        )
        return UnievalSettings.model_validate(
            {
                **authored.model_dump(exclude={"version", "prompt_files", "prompts"}),
                "version": UNIEVAL_VERSION,
                "prompts": {
                    **authored.prompts.model_dump(),
                    **{
                        dimension: load_prompt_text(root / "config", prompt_file)
                        for dimension, prompt_file in authored.prompt_files.model_dump().items()
                    },
                },
                "listener": listener,
                "logging": logging,
            }
        )
    except OSError:
        raise ValueError(
            "config/summary-evals/unieval-evaluator/settings.json could not be read"
        ) from None
    except ValidationError as error:
        location = error.errors(include_input=False, include_context=False)[0]["loc"]
        field = ".".join(str(part) for part in location)
        raise ValueError(
            f"Invalid config/summary-evals/unieval-evaluator/settings.json field: {field}"
        ) from None
