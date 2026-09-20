"""Does a field added to a model reach the TypeScript the frontend imports?

The gap this closes: before the generator, a column added to a contract moved
`schemas/` and moved nothing in `frontend/`, so a hand-written mirror could go
on describing the old shape and no gate could see it. The first test below is
the oracle for that - it widens a model and asserts the emitted TypeScript
changed - and the two beside it are the drift gate over the committed tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from conftest import read_text
from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract
from idhazh.contracts.export import (
    CONTRACTS,
    expected_type_filenames,
    export_typescript,
)
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.typescript import module_filename, module_text

pytestmark = pytest.mark.contract

TYPES_DIR = Path(__file__).resolve().parents[3] / "frontend" / "src" / "contracts"


class WidenedHostFingerprintRow(HostFingerprintRow):
    """The same row with one more reading on it. Declared here, never exported."""

    __schema_stem__: ClassVar[str] = "host-fingerprint-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = HostFingerprintRow.__changelog__

    probe_watts: float | None = Field(
        default=None, ge=0, description="What the machine drew at the probe."
    )


def test_a_new_column_moves_the_generated_typescript() -> None:
    """The oracle. A field the model gains is a field the frontend's type gains.

    Asserted on the emitted text rather than on a file, so it holds for every
    contract and not only for the one somebody remembered to regenerate.
    """
    before = module_text(HostFingerprintRow)
    after = module_text(WidenedHostFingerprintRow)
    assert "probe_watts" not in before
    assert "probe_watts?: number | null;" in after
    assert after != before


def test_committed_typescript_matches_the_models(tmp_path: Path) -> None:
    export_typescript(tmp_path)
    for contract in CONTRACTS:
        name = module_filename(contract)
        assert read_text(TYPES_DIR / name) == read_text(tmp_path / name), (
            f"{name} is stale - edit the Pydantic model and regenerate, never the TypeScript"
        )


def test_the_contracts_directory_holds_exactly_the_generated_files() -> None:
    on_disk = {path.name for path in TYPES_DIR.glob("*.ts")}
    assert on_disk == expected_type_filenames()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_every_module_names_its_source_and_its_root_type(contract: type[Contract]) -> None:
    text = module_text(contract)
    source = contract.__module__.replace(".", "/")
    assert f"// Generated from `backend/{source}.py`" in text
    assert f"export interface {contract.__name__} {{" in text


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_a_module_is_ascii_lf_and_carries_no_trailing_space(contract: type[Contract]) -> None:
    """What CI's whitespace gate and `CLAUDE.md` section 5 ask of every repo file."""
    text = module_text(contract)
    assert text.isascii()
    assert "\r" not in text
    assert text.endswith("\n")
    assert [line for line in text.split("\n") if line != line.rstrip()] == []


def test_a_closed_vocabulary_ships_as_an_array_a_reader_can_narrow_with() -> None:
    """A union alone cannot be tested against at run time, so the members ship too."""
    text = module_text(HostFingerprintRow)
    assert "export const SERVER_JOB = [" in text
    assert "export type ServerJob = (typeof SERVER_JOB)[number];" in text
