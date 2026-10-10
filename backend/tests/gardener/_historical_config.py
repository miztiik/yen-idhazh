"""Which recorded config preserves the cleanup windows before yearly expiry was enabled?

Retention declarations stay frozen; unrelated appearance fields follow the current contract.
"""

from __future__ import annotations

from typing import Final

from conftest import FIXTURES_DIR

# Recorded from c8251c596, before the owner approved finite yearly retention. The
# retention declarations stay as they were then.
PRE_YEARLY_CONFIG: Final = FIXTURES_DIR / "gardener" / "pre-yearly-retention" / "config"
