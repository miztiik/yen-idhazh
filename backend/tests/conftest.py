"""Repo-relative paths every backend test resolves against."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.summary import Summary

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SCHEMAS_DIR: Final = REPO_ROOT / "schemas"
CONFIG_DIR: Final = REPO_ROOT / "config"
STATE_DIR: Final = REPO_ROOT / "state"
FIXTURES_DIR: Final = REPO_ROOT / "tests" / "fixtures"
CONTRACT_FIXTURES_DIR: Final = FIXTURES_DIR / "contracts"


def read_text(path: Path) -> str:
    """Read without newline translation, so a CRLF drift fails the comparison."""
    return path.read_bytes().decode("utf-8")


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
