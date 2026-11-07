"""Read one configured instruction file without changing its consumer's newline policy."""

from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from idhazh.contracts.knobs.prompts import PromptFile

_PROMPT_FILE = TypeAdapter(PromptFile)


def load_prompt_text(
    config_dir: Path, prompt_file: PromptFile, *, newline: str | None = None
) -> str:
    try:
        named = _PROMPT_FILE.validate_python(prompt_file)
    except ValidationError:
        raise ValueError(
            "prompt file must name a safe relative POSIX path under prompts/"
        ) from None
    path = config_dir / named
    if not path.resolve().is_relative_to(config_dir.resolve()):
        raise ValueError(f"{named} must stay inside the selected config root")
    try:
        with path.open(encoding="utf-8", newline=newline) as stream:
            text = stream.read()
    except OSError:
        raise ValueError(f"{named} could not be read") from None
    except UnicodeError:
        raise ValueError(f"{named} must contain valid UTF-8") from None
    if not text.strip():
        raise ValueError(f"{named} must not be blank")
    return text
