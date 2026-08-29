"""Repo-relative paths every backend test resolves against."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from idhazh.contracts.app_config import AppConfig, InferenceConfig, ModelRef
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_output_digest, derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceTier
from idhazh.corpus import Published
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult
from idhazh.llm.server import server_argv

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SCHEMAS_DIR: Final = REPO_ROOT / "schemas"
CONFIG_DIR: Final = REPO_ROOT / "config"
STATE_DIR: Final = REPO_ROOT / "state"
FIXTURES_DIR: Final = REPO_ROOT / "tests" / "fixtures"
CONTRACT_FIXTURES_DIR: Final = FIXTURES_DIR / "contracts"


def read_text(path: Path) -> str:
    """Read without newline translation, so a CRLF drift fails the comparison."""
    return path.read_bytes().decode("utf-8")


def llama_server_flags() -> frozenset[str]:
    """Every flag `server_argv` can emit, taken from `server_argv`.

    Two tests hold the one-builder Oracle from opposite sides, and a listed set
    would be a third place a flag has to be remembered. Every optional knob is
    filled in, so a flag that only appears when a knob is set is still counted.
    """
    argv = server_argv(
        binary=Path("bin/llama-server"),
        weights=Path("models/w.gguf"),
        model=ModelRef(id="m", repo="r", file="w.gguf", quantisation="Q4_K_M"),
        inference=InferenceConfig(
            n_parallel=1,
            flash_attention="on",
            load_mode="mmap+mlock",
            cache_type_k="q8_0",
            cache_type_v="q8_0",
            priority=2,
            poll=50,
            n_threads_batch=4,
            startup_warmup=False,
        ),
    )
    # llama-bench and the image bench take these two under the same spelling,
    # so they say nothing about which server a caller started.
    return frozenset(
        token for token in argv if token.startswith("-") and token not in {"--model", "--threads"}
    )


@pytest.fixture
def article_ok() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


@pytest.fixture
def summary_ok() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


@pytest.fixture
def digest_day_ok() -> DigestDay:
    path = next((CONTRACT_FIXTURES_DIR / "digest-day").glob("*.json"))
    return DigestDay.from_json(read_text(path))


# --- One article a refill can rebuild, shared by two test modules ----------

REFILL_URL: Final = "https://grid.example.com/2026/08/winter-outlook"

#: A body that shares the summary's entities and numbers but no three-word run
#: with it. Both halves matter: too little overlap fails `lead_coverage_min`,
#: too much fails `verbatim_reject_ceiling`, and a number the body does not
#: carry fails `unsupported_numbers`.
REFILL_BODY: Final = (
    "The Nordic Grid Authority said its winter reserve margin will stay near 12 "
    "percent into February. Officials called the figure comfortable rather than "
    "generous, and said no rolling outages are planned. The authority has spent "
    "three years adding battery storage across the region and now counts 4 "
    "gigawatts of it. Demand has risen faster than the forecast published last "
    "spring, mostly because of new data centre connections in the south. A "
    "spokesperson said a revised outlook would appear in March and would carry a "
    "longer horizon than usual. Analysts who follow the region said the margin "
    "leaves little room if a cold snap arrives early, though none of them expect "
    "outages before the spring thaw arrives."
)

REFILL_PUBLISHED: Final = Published(
    title="Nordic grid holds its winter margin at 12 percent",
    summary=(
        "The Nordic Grid Authority expects a reserve margin near 12 percent "
        "through February and has ruled out planned outages. Battery capacity "
        "has reached 4 gigawatts. Southern data centre demand overtook the "
        "spring forecast, and a fresh outlook is due in March."
    ),
    key_points=(
        "Reserve margin stays near 12 percent into February",
        "Battery capacity reaches 4 gigawatts",
        "A revised outlook is due in March",
    ),
)


def refill_page(body: str) -> bytes:
    return f"<html><body><article><p>{body}</p></article></body></html>".encode()


def refetched(
    body: str, app: AppConfig, *, url: str = REFILL_URL, item_id: str = "energy-01"
) -> tuple[Article, str]:
    """One page through the real extractor, exactly as a refill sees it."""
    item = PlannedItem(
        item_id=item_id,
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="grid-newsroom",
        tier=SourceTier.INSTITUTION,
        vertical="energy",
        title="Nordic grid publishes its winter outlook",
        rank_score=1.0,
    )
    return to_article_with_source(
        item,
        FetchResult(FetchOutcome.OK, status=200, body=refill_page(body)),
        config=app.extract,
        fetched_at="2026-08-28T00:00:00Z",
    )


def refill_recorded(
    article: Article, published: Published, **overrides: object
) -> EvalRow:
    """A ledger row for this pair, carrying the digest the join checks."""
    base = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    return base.model_copy(
        update={
            "item_id": article.item_id,
            "url_key": article.url_key,
            "source_url": article.canonical_url,
            "title": article.title,
            "vertical": article.vertical,
            "output_digest": derive_output_digest(
                published.summary, list(published.key_points), title=published.title
            ),
            **overrides,
        }
    )
