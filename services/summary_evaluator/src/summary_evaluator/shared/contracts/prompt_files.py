"""Which safe relative file can supply a named task's instructions?"""

from typing import Annotated

from pydantic import AfterValidator

from summary_evaluator.shared.contracts.base import RelativePath


def validate_prompt_file(value: str) -> str:
    if not value.startswith("prompts/") or not value.endswith(".txt"):
        raise ValueError("Expected a relative .txt prompt file under prompts/")
    return value


PromptFile = Annotated[RelativePath, AfterValidator(validate_prompt_file)]
