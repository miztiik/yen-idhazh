"""Which named instruction file does each production task read?"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Final

from pydantic import AfterValidator, StringConstraints, model_validator

from idhazh.contracts.base import Model, RelPath
from idhazh.contracts.knobs.removed import refuse_a_removed_knob

#: The task this block used to name. `generate_labels` was the instruction file of
#: the model call that found the names and places in an article. The text-analysis
#: service finds them now, so no task reads such a file and nothing replaces it.
SUPERSEDED_PROMPT_FILES_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"generate_labels": ""}
)


def validate_prompt_file(value: str) -> str:
    """Keep configured task instructions inside the selected config's prompts directory."""
    if not value.startswith("prompts/") or not value.endswith(".txt"):
        raise ValueError("prompt file must name a relative .txt file under prompts/")
    return value


PromptFile = Annotated[
    RelPath, StringConstraints(strict=True), AfterValidator(validate_prompt_file)
]


class PromptFilesConfig(Model):
    write_digest_summary: PromptFile = "prompts/write-digest-summary.txt"
    plan_visual: PromptFile = "prompts/plan-visual.txt"
    summarize_article: PromptFile = "prompts/generate-summary.txt"
    compare_articles: PromptFile = "prompts/compare-articles.txt"

    @model_validator(mode="before")
    @classmethod
    def _a_removed_task_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("prompt_files", data, SUPERSEDED_PROMPT_FILES_NAMES)
