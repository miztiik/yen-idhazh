"""Has the generated contract layer stayed deleted?

A ratchet, and the only test here that could not pass before the deletion it
guards. `schemas/` and `frontend/src/contracts/` held 66 files each, written by
`idhazh.contracts.export` on every contract change to serve six names in two
frontend modules. What replaced them is a hand copy held in step by
`test_frontend_field_set.py` and `test_frontend_vocabularies.py`.

The failure this refuses is the layer coming back one file at a time: an
exporter re-added for one contract, a directory recreated to hold one schema an
editor plugin wanted. Either is cheap to write and turns the two tests above
from the control into a second opinion.

Asking a contract for its schema is untouched and stays untouched.
`Contract.json_schema()` computes one on demand; what went is the command that
wrote them all to disk.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT

pytestmark = pytest.mark.contract

#: The two trees, and what each one held.
DELETED_TREES: Final[dict[str, Path]] = {
    "one generated JSON Schema per contract": REPO_ROOT / "schemas",
    "one generated TypeScript module per contract": REPO_ROOT / "frontend" / "src" / "contracts",
}

#: The generator, and the emitter it drove.
DELETED_MODULES: Final[tuple[str, ...]] = (
    "idhazh.contracts.export",
    "idhazh.contracts.typescript",
)


@pytest.mark.parametrize("held", sorted(DELETED_TREES))
def test_the_generated_tree_is_not_back(held: str) -> None:
    tree = DELETED_TREES[held]
    assert not tree.exists(), (
        f"{tree.name}/ is back, holding {held}. The frontend copy is held in step by "
        "test_frontend_field_set.py and test_frontend_vocabularies.py; a generated tree "
        "beside it is a second answer to the same question."
    )


@pytest.mark.parametrize("name", DELETED_MODULES)
def test_the_generator_is_not_importable(name: str) -> None:
    assert importlib.util.find_spec(name) is None, (
        f"{name} exists again. `Contract.json_schema()` is how a schema is asked for."
    )
