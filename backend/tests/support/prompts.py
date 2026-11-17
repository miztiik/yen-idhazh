"""Build the model's request from an article and its real element table."""

from pathlib import Path
from typing import Any, Final

from idhazh import config
from idhazh.classify.calls import build_summary_request
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.elements import element_table

from .models import a_markers
from .paths import CONFIG_DIR, FIXTURES_DIR

SUMMARIZE_AND_PLAN_REPLIES: Final = FIXTURES_DIR / "completions" / "summarize-and-plan"

#: Words only the retired first call's prompt and reply shape used. A request to the model
#: that carries any of them is still asking that call's question.
THE_FIRST_CALLS_WORDS: Final = (
    '"named_mentions"',
    '"proposed"',
    "Extract quantity meanings",
    "supplied quantity table",
)


def a_table(
    article: Article,
    text: str | None = None,
    *,
    cap: int | None = None,
    config_dir: Path = CONFIG_DIR,
) -> ElementTable:
    settings = config.load(config_dir).app.elements
    if text is not None:
        article = article.model_copy(update={"text": text})
    if cap is not None:
        settings = ElementsConfig.model_validate(settings.model_dump() | {"max_per_article": cap})
    return element_table(article, config=settings)


def summary_payload(
    article: Article, *, plan: bool = True, config_dir: Path = CONFIG_DIR
) -> dict[str, Any]:
    settings = config.load(config_dir)
    entry = settings.models.summarizer
    return build_summary_request(
        article,
        a_table(article, config_dir=config_dir),
        model_id=entry.id,
        server=entry.server,
        sampling=entry.sampling,
        markers=a_markers(),
        plan=plan,
        prompt_files=settings.app.prompt_files,
        config_dir=settings.config_dir,
    )
