"""What does the contract refuse of the host-fingerprint window?"""

from __future__ import annotations

import pytest

from idhazh.contracts.knobs.observability import ObservabilityConfig


def test_a_window_below_the_published_copy_is_refused() -> None:
    """The published machine shard is folded from this ledger, so it may not outlive it."""
    with pytest.raises(ValueError, match="host_fingerprint_keep_months"):
        ObservabilityConfig(host_fingerprint_keep_months=13, public_machine_keep_months=14)
