"""Does `slow_mark_audit.py` read a JUnit report into disagreements correctly?

Everything here is driven by `tests/fixtures/junit/sample-report.xml`, a small
hand-written JUnit XML report standing in for a real pytest run - no network,
no subprocess, no mocks. The module list it is matched against is also a fixed
list of made-up paths, never a walk of `backend/tests`, so these tests never
depend on the repository's own test tree staying a fixed shape.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FIXTURES_DIR, REPO_ROOT

from utilities.slow_mark_audit import (
    average_seconds_by_module,
    disagreements,
    slow_threshold_seconds,
    threshold_phrase,
)

SAMPLE_REPORT: Path = FIXTURES_DIR / "junit" / "sample-report.xml"

#: Stands in for `mark_census.modules()`: three made-up test modules, one of
#: them nested inside a package, none of which need to exist on disk.
KNOWN_MODULES: list[Path] = [
    REPO_ROOT / "backend" / "tests" / "test_alpha.py",
    REPO_ROOT / "backend" / "tests" / "test_beta.py",
    REPO_ROOT / "backend" / "tests" / "pipeline" / "test_gamma.py",
]


def test_averages_a_module_s_testcases_and_excludes_skipped_ones() -> None:
    averages = average_seconds_by_module(SAMPLE_REPORT, known_modules=KNOWN_MODULES)

    assert averages["test_alpha"] == 1.0
    assert averages["test_beta"] == 0.2
    # test_gamma's second testcase is skipped and reports 9.00s; averaging it
    # in would read as slow for the wrong reason.
    assert averages["test_gamma"] == 3.3


def test_a_nested_class_s_testcase_still_resolves_to_its_module() -> None:
    averages = average_seconds_by_module(SAMPLE_REPORT, known_modules=KNOWN_MODULES)
    assert "test_gamma" in averages


def test_disagreements_names_both_directions_at_the_boundary() -> None:
    averages = average_seconds_by_module(SAMPLE_REPORT, known_modules=KNOWN_MODULES)

    # test_alpha measures exactly at the threshold and is marked slow: at or
    # under the threshold always reads as "should not be marked".
    should_be_marked, should_not_be_marked = disagreements(
        averages, threshold=1.0, marked=frozenset({"test_alpha"})
    )

    assert should_be_marked == [("test_gamma", 3.3)]
    assert should_not_be_marked == [("test_alpha", 1.0)]
    # test_beta agrees (unmarked, under threshold) and names neither list.


def test_agreement_on_every_module_reports_no_disagreements() -> None:
    averages = average_seconds_by_module(SAMPLE_REPORT, known_modules=KNOWN_MODULES)
    should_be_marked, should_not_be_marked = disagreements(
        averages, threshold=1.0, marked=frozenset({"test_gamma"})
    )
    assert should_be_marked == []
    assert should_not_be_marked == []


def test_slow_threshold_seconds_reads_the_configured_value(tmp_path: Path) -> None:
    config = tmp_path / "test-marks.json"
    config.write_text('{"slow_threshold_seconds": 2.5}', encoding="utf-8")
    assert slow_threshold_seconds(config) == 2.5


def test_threshold_phrase_matches_the_pyproject_wording_at_one_second() -> None:
    assert threshold_phrase(1.0) == "a second"


def test_threshold_phrase_names_a_whole_number_of_seconds() -> None:
    assert threshold_phrase(3.0) == "3 seconds"


def test_threshold_phrase_names_a_fractional_number_of_seconds() -> None:
    assert threshold_phrase(1.5) == "1.5 seconds"
