"""Repo-relative paths every backend test resolves against."""

from __future__ import annotations

from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
SCHEMAS_DIR: Final = REPO_ROOT / "schemas"
CONFIG_DIR: Final = REPO_ROOT / "config"
EVALS_DIR: Final = REPO_ROOT / "evals"
FIXTURES_DIR: Final = REPO_ROOT / "tests" / "fixtures"
CONTRACT_FIXTURES_DIR: Final = FIXTURES_DIR / "contracts"


def read_text(path: Path) -> str:
    """Read without newline translation, so a CRLF drift fails the comparison."""
    return path.read_bytes().decode("utf-8")
