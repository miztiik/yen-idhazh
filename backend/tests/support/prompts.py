"""Build the model's request from an article, its real element table and its real tables."""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from idhazh import config
from idhazh.anchor_mentions import Mention
from idhazh.classify.calls import build_summary_request
from idhazh.classify.pair_names_with_figures import FigureTable, tables_of_figures
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
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

#: Four countries, one figure each, across three sentences: the smallest article a table forms over.
WIND_NAMES: Final = ("Denmark", "Germany", "Poland", "Ireland")
WIND_TEXT: Final = (
    "Denmark approved 1200 MW of offshore wind this week, the largest single award the country "
    "has made. Germany approved 900 MW on the same day, and Poland approved 640 MW. Ireland "
    "approved 410 MW, completing the round. None of the four regulators published the prices."
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


def mentions_of(
    text: str, names: Sequence[str], others: Sequence[tuple[str, str]] = ()
) -> list[Mention]:
    """What the text-analysis service would label: every place each name stands in `text`."""
    labelled = [("GPE", name) for name in names] + list(others)
    return [
        Mention(label, found.start(), found.end())
        for label, name in labelled
        for found in re.finditer(re.escape(name), text)
    ]


def tables_over(
    article: Article,
    text: str,
    names: Sequence[str],
    *,
    others: Sequence[tuple[str, str]] = (),
    visuals: VisualsConfig | None = None,
    config_dir: Path = CONFIG_DIR,
) -> tuple[ElementTable, list[FigureTable]]:
    """The real element pass over `text`, with the service labelling every place a name stands,
    and the tables the builder finds in it."""
    app = config.load(config_dir).app
    table = element_table(
        article.model_copy(update={"text": text}),
        config=app.elements,
        mentions=mentions_of(text, names, others),
    )
    return table, tables_of_figures(text, table, visuals=visuals or app.visuals)


def summary_payload(
    article: Article,
    *,
    tables: Sequence[FigureTable] = (),
    config_dir: Path = CONFIG_DIR,
) -> dict[str, Any]:
    settings = config.load(config_dir)
    entry = settings.models.summarizer
    return build_summary_request(
        article,
        tables,
        model_id=entry.id,
        server=entry.server,
        sampling=entry.sampling,
        markers=a_markers(),
        visuals=settings.app.visuals,
        prompt_files=settings.app.prompt_files,
        config_dir=settings.config_dir,
    )
