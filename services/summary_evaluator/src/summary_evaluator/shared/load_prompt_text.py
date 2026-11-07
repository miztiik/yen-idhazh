"""Read exactly one configured prompt file while retaining all its UTF-8 text."""

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from summary_evaluator.shared.contracts.prompt_files import PromptFile

_PROMPT_FILE = TypeAdapter(PromptFile)


def load_prompt_text(config_root: Path, prompt_file: PromptFile) -> str:
    try:
        named = _PROMPT_FILE.validate_python(prompt_file)
    except ValidationError:
        raise ValueError("Expected a safe relative POSIX prompt file under prompts/") from None
    path = config_root / named
    if not path.resolve().is_relative_to(config_root.resolve()):
        raise ValueError(f"{named} must stay inside the selected config root")
    try:
        return path.read_bytes().decode("utf-8")
    except OSError:
        raise ValueError(f"{named} could not be read") from None
    except UnicodeError:
        raise ValueError(f"{named} must contain valid UTF-8") from None
