"""Build label requests from an article and its real element table."""

from pathlib import Path
from typing import Any, Final

from idhazh import config
from idhazh.classify.calls import build_label_request
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.elements import element_table

from .models import committed_markers
from .paths import CONFIG_DIR, FIXTURES_DIR

LABEL_REPLIES: Final = FIXTURES_DIR / "completions" / "label"
SUMMARIZE_AND_PLAN_REPLIES: Final = FIXTURES_DIR / "completions" / "summarize-and-plan"


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


def label_payload(article: Article, *, config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    entry = config.load(config_dir).models.summarizer
    return build_label_request(
        article,
        a_table(article, config_dir=config_dir),
        model_id=entry.id,
        server=entry.server,
        sampling=entry.sampling,
        markers=committed_markers(config_dir=config_dir),
    )
