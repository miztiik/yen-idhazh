"""Does the validate run page say something true with no verdict, and with one?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from utilities import qualification_annotations

pytestmark = pytest.mark.contract


def test_a_run_that_wrote_no_verdict_is_red_on_its_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert qualification_annotations.main(["--report", str(tmp_path / "report.json")]) == 0

    assert capsys.readouterr().out.strip() == qualification_annotations.NO_VERDICT


def test_a_recorded_verdict_is_annotated_from_the_contract_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = CONTRACT_FIXTURES_DIR / "qualification-report" / "qualified.json"

    assert qualification_annotations.main(["--report", str(fixture)]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("::notice title=Qualification verdict::")
    assert not any(line.startswith("::error") for line in lines)
