"""Which real config governs historical migration commands in these tests?"""

from __future__ import annotations

import pytest
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import config


@pytest.fixture(autouse=True)
def historical_cli_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the command at recorded declarations without changing retention validation."""
    monkeypatch.setattr(config, "DEFAULT_CONFIG_DIR", PRE_YEARLY_CONFIG)
