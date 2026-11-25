"""Build a model request from an article and its real numeric evidence."""

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from idhazh import config
from idhazh.anchor_mentions import Mention
from idhazh.ask_text_analysis import Sentence
from idhazh.classify.calls import build_summary_request
from idhazh.classify.chart_candidates import ChartCandidate, chart_candidates
from idhazh.classify.plan_visual_request import chart_forms
from idhazh.contracts.article import Article
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
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

#: Four countries measuring offshore wind awards in the same unit.
WIND_NAMES: Final = ("Denmark", "Germany", "Poland", "Ireland")
WIND_TEXT: Final = (
    "Denmark approved 1200 MW of offshore wind this week, the largest single award the country "
    "has made. Germany approved 900 MW on the same day, and Poland approved 640 MW. Ireland "
    "approved 410 MW, completing the round. None of the four regulators published the prices."
)


def sentences_of(text: str) -> tuple[Sentence, ...]:
    """Finite authored analysis spans, split only at sentence-ending punctuation."""
    return tuple(
        Sentence(found.group(), found.start(), found.end())
        for found in re.finditer(r"\S(?:.*?\S)?(?:[.!?](?=\s|$)|$)", text, re.DOTALL)
    )


def candidates_for(table: ElementTable, text: str) -> tuple[ChartCandidate, ...]:
    """Offer the source's actual sentence offsets, not a value/unit matcher."""
    return chart_candidates(table, text, sentences_of(text))


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


def chart_data_over(
    article: Article,
    text: str,
    names: Sequence[str] = (),
    *,
    others: Sequence[tuple[str, str]] = (),
    visuals: VisualsConfig | None = None,
    config_dir: Path = CONFIG_DIR,
) -> tuple[ElementTable, tuple[VisualType, ...]]:
    """Request evidence through the real element pass; these examples need two readings."""
    app = config.load(config_dir).app
    table = element_table(
        article.model_copy(update={"text": text}),
        config=app.elements,
        mentions=mentions_of(text, names, others),
    )
    forms = chart_forms(table, visuals=visuals or app.visuals)
    assert forms
    return table, forms


def summary_payload(
    article: Article,
    *,
    data: tuple[VisualType, ...] = (),
    config_dir: Path = CONFIG_DIR,
) -> dict[str, Any]:
    settings = config.load(config_dir)
    entry = settings.models.summarizer
    table = element_table(article, config=settings.app.elements)
    return build_summary_request(
        article,
        data,
        model_id=entry.id,
        server=entry.server,
        sampling=entry.sampling,
        markers=a_markers(),
        candidates=candidates_for(table, article.text or ""),
        prompt_files=settings.app.prompt_files,
        config_dir=settings.config_dir,
    )


def chart_reply_fields(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The allowed choices and the JSON object each constrains."""
    return {
        choice["properties"]["type"]["const"]: choice["properties"]
        for choice in schema["properties"]["visual"]["anyOf"]
        if choice.get("type") != "null"
    }
