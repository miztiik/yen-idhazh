"""Repo-relative paths every backend test resolves against."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from idhazh.contracts.app_config import InferenceConfig, ModelRef
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.summary import Summary
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
