"""Is every ledger registry entry backed by a writer that exists?"""

from __future__ import annotations

import pytest

from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger.staging import REGISTRY

pytestmark = pytest.mark.workflow


def test_every_store_is_registered_and_each_named_writer_resolves() -> None:
    missing = sorted(set(LedgerName) - set(REGISTRY), key=lambda name: name.value)
    assert not missing, (
        f"{', '.join(name.value for name in missing)} has no row in "
        "idhazh.ledger.staging.REGISTRY, so it has no declared writer."
    )
    unresolved: list[str] = []
    for name, staging in sorted(REGISTRY.items(), key=lambda item: item[0].value):
        if staging.symbol is None:
            continue
        module_name, _, attr = staging.symbol.rpartition(".")
        try:
            module = __import__(module_name, fromlist=[attr])
        except ImportError as error:
            unresolved.append(f"{name.value}: {staging.symbol} does not import ({error})")
            continue
        if not hasattr(module, attr):
            unresolved.append(
                f"{name.value}: {staging.symbol} names no attribute {attr!r} on {module_name}"
            )
    assert not unresolved, "\n".join(unresolved)
