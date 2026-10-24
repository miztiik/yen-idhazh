"""Build a refill article and the published summary used to check it."""

from __future__ import annotations

import json
from typing import Final

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_output_digest, derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
from idhazh.corpus import Published
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult

from .paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

REFILL_URL: Final = "https://grid.example.com/2026/08/winter-outlook"


def refill_body() -> str:
    return read_text(FIXTURES_DIR / "corpus" / "refill-body.txt").strip()


def refill_published() -> Published:
    raw = json.loads(read_text(FIXTURES_DIR / "corpus" / "refill-published.json"))
    return Published(title=raw["title"], summary=raw["summary"])


def refill_page(body: str) -> bytes:
    return f"<html><body><article><p>{body}</p></article></body></html>".encode()


def refetched(
    body: str,
    app: AppConfig,
    *,
    url: str = REFILL_URL,
    item_id: str = "energy-01",
    form: SourceForm = SourceForm.ARTICLE,
) -> tuple[Article, str]:
    item = PlannedItem(
        item_id=item_id,
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="grid-newsroom",
        tier=1,
        vertical="energy",
        source_form=form,
        title="Nordic grid publishes its winter outlook",
        rank_score=1.0,
    )
    return to_article_with_source(
        item,
        FetchResult(FetchOutcome.OK, status=200, body=refill_page(body)),
        config=app.extract,
        fetched_at="2026-08-28T00:00:00Z",
    )


def refill_recorded(article: Article, published: Published, **overrides: object) -> EvalRow:
    base = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    return base.model_copy(
        update={
            "item_id": article.item_id,
            "url_key": article.url_key,
            "source_url": article.canonical_url,
            "title": article.title,
            "vertical": article.vertical,
            "output_digest": derive_output_digest(published.summary, title=published.title),
            **overrides,
        }
    )
