"""Repository paths shared by backend test support."""

from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
CONFIG_DIR: Final = REPO_ROOT / "config"
FIXTURES_DIR: Final = REPO_ROOT / "tests" / "fixtures"
CONTRACT_FIXTURES_DIR: Final = FIXTURES_DIR / "contracts"


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")
