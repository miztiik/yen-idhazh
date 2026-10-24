"""Isolate backend pytest runs and provide shared contract fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import origin_template
import pytest
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.summary import Summary
from idhazh.stages import common


@pytest.fixture(scope="session", autouse=True)
def fixture_git_ceiling() -> Iterator[None]:
    """Keep generated Git fixtures from finding the checkout above them."""
    previous = os.environ.get("GIT_CEILING_DIRECTORIES")
    os.environ["GIT_CEILING_DIRECTORIES"] = os.pathsep.join(
        filter(None, [previous, str(REPO_ROOT)])
    )
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GIT_CEILING_DIRECTORIES", None)
        else:
            os.environ["GIT_CEILING_DIRECTORIES"] = previous


@pytest.fixture
def tmp_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Use short names to leave room for nested Windows fixture paths."""
    return tmp_path_factory.mktemp("t")


@pytest.fixture(scope="session", autouse=True)
def _discard_origin_templates() -> Iterator[None]:
    yield
    origin_template.discard()


@pytest.fixture(autouse=True)
def isolate_committed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect stage traces even when a test only overrides its output directory."""
    monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")


@pytest.fixture
def article_ok() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


@pytest.fixture
def summary_ok() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


@pytest.fixture
def digest_day_ok() -> DigestDay:
    path = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"
    return DigestDay.from_json(read_text(path))
