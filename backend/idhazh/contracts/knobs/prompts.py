"""Which named instruction file does each production task read?"""

from typing import Annotated

from pydantic import AfterValidator, StringConstraints

from idhazh.contracts.base import Model, RelPath


def validate_prompt_file(value: str) -> str:
    """Keep configured task instructions inside the selected config's prompts directory."""
    if not value.startswith("prompts/") or not value.endswith(".txt"):
        raise ValueError("prompt file must name a relative .txt file under prompts/")
    return value


PromptFile = Annotated[
    RelPath, StringConstraints(strict=True), AfterValidator(validate_prompt_file)
]


class PromptFilesConfig(Model):
    generate_labels: PromptFile = "prompts/generate-labels.txt"
    write_digest_summary: PromptFile = "prompts/write-digest-summary.txt"
    plan_visual: PromptFile = "prompts/plan-visual.txt"
    continue_summary: PromptFile = "prompts/continue-summary.txt"
    summarize_article: PromptFile = "prompts/summarize-article.txt"
    compare_articles: PromptFile = "prompts/compare-articles.txt"
