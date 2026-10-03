"""Do named module sources expose their pytest marks without a tree census?"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from conftest import REPO_ROOT, read_text

from utilities.mark_census import declared_marks, module_marks, modules
from utilities.slow_mark_audit import slow_threshold_seconds, threshold_phrase


def test_named_modules_ignore_unrelated_sources(tmp_path: Path) -> None:
    named = tmp_path / "test_named.py"
    named.write_text("pytestmark = [pytest.mark.contract, pytest.mark.slow]\n", encoding="ascii")
    (tmp_path / "test_unrelated.py").write_text("not valid python", encoding="ascii")
    assert modules([named]) == [named]
    assert module_marks(named, repo_root=tmp_path) == {"contract", "slow"}


def test_a_called_module_mark_is_read(tmp_path: Path) -> None:
    named = tmp_path / "test_called.py"
    named.write_text("pytestmark = pytest.mark.contract(reason='fixture')\n", encoding="ascii")
    assert module_marks(named, repo_root=tmp_path) == {"contract"}


def test_a_named_source_with_no_mark_carries_none(tmp_path: Path) -> None:
    named = tmp_path / "test_unmarked.py"
    named.write_text("def test_one(): pass\n", encoding="ascii")
    assert module_marks(named, repo_root=tmp_path) == frozenset()


def test_a_module_census_needs_named_inputs() -> None:
    with pytest.raises(ValueError, match="at least one"):
        modules([])


def test_the_slow_marker_text_names_the_configured_threshold() -> None:
    manifest = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    descriptions = {
        str(entry).split(":", 1)[0].strip(): str(entry).split(":", 1)[1].strip()
        for entry in manifest["tool"]["pytest"]["ini_options"]["markers"]
    }
    assert "slow" in declared_marks()
    assert threshold_phrase(slow_threshold_seconds()) in descriptions["slow"]
