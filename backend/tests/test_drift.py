"""Unit-tier tests for the drift benchmark.

The row's own oracle is injected drift: a detector that has never fired has not
been shown to work. So every test here starts from a degradation and asserts the
alert fires - and the important one asserts that a GLOBAL threshold would have
missed it, which is why the rule is per-domain.

The second oracle is the opposite failure and it is not a unit test: the review
step reporting all clear over a window it never compared. Those tests run the
program `.github/workflows/drift.yml` actually ships, against a ledger written
into a temporary directory, and read its exit code.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.drift import (
    Alert,
    Observation,
    compare,
    domain_of,
    extraction_is_rotting,
    failure_rate,
    shortfall,
)

# `workflow`, because the program `.github/workflows/drift.yml` ships is asserted here.
pytestmark = pytest.mark.workflow

DRIFT_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "drift.yml"
COMPARE_STEP: Final = "Compare the windows"
#: The five cells the review reads out of the eval ledger. A row carries about
#: forty; `csv.DictReader` hands the program a mapping, so a fixture that names
#: these five exercises every line of it.
LEDGER_COLUMNS: Final = ("date", "source_url", "hhem", "extractiveness", "source_word_count")


def rows(
    url: str, *, words: int | None, hhem: float, extractiveness: float, n: int = 4
) -> list[Observation]:
    return [Observation(url, hhem, extractiveness, words) for _ in range(n)]


def lengths(observations: list[Observation]) -> list[int]:
    """Every recorded article length. A row that never recorded one is not a zero."""
    return [row.source_word_count for row in observations if row.source_word_count is not None]


HEALTHY = "https://news.example.com/a"
OTHER = "https://blog.example.org/b"


def test_a_domain_is_the_host_without_www() -> None:
    assert domain_of("https://www.news.example.com/a?b=1") == "news.example.com"


def test_a_healthy_domain_raises_nothing() -> None:
    steady = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    assert compare(steady, steady) == []


# --- A row that does not know how long its article was ------------------------


def test_a_row_with_no_recorded_length_still_carries_its_other_two_signals() -> None:
    """The read-side migration for a nullable `source_word_count`.

    A row written before 2026-08-27 whose article was truncated has no full
    length anywhere. Dropping the whole observation would take its faithfulness
    and its extractiveness with it, so the length rule steps over it and the
    copying rule still sees it.
    """
    before = rows(HEALTHY, words=None, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=None, hhem=0.85, extractiveness=0.9)
    alerts = {finding.alert for finding in compare(after, before)}

    assert Alert.MORE_COPYING in alerts
    assert Alert.SHORTER_SOURCES not in alerts


def test_a_window_that_knows_no_length_does_not_read_as_a_collapse() -> None:
    """Unknown is not zero. A median of nothing must not fire a 100 percent drop."""
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=None, hhem=0.85, extractiveness=0.2)

    assert compare(after, before) == []


def test_the_rows_that_do_know_their_length_still_decide_the_alert() -> None:
    """A mixed window is measured on the half that was measured."""
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=None, hhem=0.85, extractiveness=0.2, n=3) + rows(
        HEALTHY, words=180, hhem=0.85, extractiveness=0.2, n=1
    )
    alerts = {finding.alert for finding in compare(after, before)}

    assert Alert.SHORTER_SOURCES in alerts


# --- The failure this row exists to catch -----------------------------------


def test_a_site_redesign_that_shortens_extraction_fires() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=180, hhem=0.85, extractiveness=0.2)
    alerts = {finding.alert for finding in compare(after, before)}
    assert Alert.SHORTER_SOURCES in alerts


def test_the_conjunction_names_the_failure_rather_than_a_proxy() -> None:
    """Faithfulness holding WHILE sources collapse is a summary of chrome."""
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=150, hhem=0.9, extractiveness=0.2)
    findings = compare(after, before)
    chrome = [f for f in findings if f.alert is Alert.SCORING_CHROME]
    assert chrome
    assert "faithfulness held" in chrome[0].detail


def test_a_global_mean_would_have_missed_it() -> None:
    """The whole reason the rule is per-domain rather than per-corpus."""
    broken_before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=2)
    broken_after = rows(HEALTHY, words=150, hhem=0.85, extractiveness=0.2, n=2)
    healthy = rows(OTHER, words=1400, hhem=0.85, extractiveness=0.2, n=15)

    before = [*broken_before, *healthy]
    after = [*broken_after, *healthy]

    global_before = sum(lengths(before)) / len(before)
    global_after = sum(lengths(after)) / len(after)
    global_move = 1 - global_after / global_before
    assert global_move < 0.15, "a global threshold would not fire on this"

    domains = {finding.domain for finding in compare(after, before)}
    assert "news.example.com" in domains
    assert "blog.example.org" not in domains


def test_a_summary_that_started_copying_fires() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.15)
    after = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.55)
    alerts = {finding.alert for finding in compare(after, before)}
    assert Alert.MORE_COPYING in alerts


def test_a_domain_seen_only_recently_is_not_a_drift_signal() -> None:
    """A new source has no trailing median to have moved away from."""
    assert compare(rows(HEALTHY, words=100, hhem=0.5, extractiveness=0.9), []) == []


def test_a_domain_that_stopped_publishing_is_not_reported_here() -> None:
    """That is feed quarantine's job, not drift's."""
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    assert compare([], before) == []


# --- Extraction failure rate -------------------------------------------------


def test_a_host_that_keeps_failing_has_changed_shape() -> None:
    assert extraction_is_rotting(succeeded=6, attempted=10)


def test_an_occasional_failure_is_not_rot() -> None:
    assert not extraction_is_rotting(succeeded=19, attempted=20)


def test_nothing_attempted_is_not_a_failure() -> None:
    assert failure_rate(0, 0) == 0.0
    assert not extraction_is_rotting(succeeded=0, attempted=0)


# --- A window nobody could compare ------------------------------------------


def test_a_full_pair_of_windows_has_no_shortfall() -> None:
    both = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=5)
    assert shortfall(both, both, 5) is None


def test_an_empty_recent_window_names_the_recent_side() -> None:
    populated = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=5)
    reason = shortfall([], populated, 5)

    assert reason is not None
    assert "recent" in reason
    assert "baseline" not in reason


def test_an_empty_baseline_window_names_the_baseline_side() -> None:
    populated = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=5)
    reason = shortfall(populated, [], 5)

    assert reason is not None
    assert "baseline" in reason
    assert "recent" not in reason


def test_both_sides_empty_names_both() -> None:
    reason = shortfall([], [], 5)

    assert reason is not None
    assert "recent" in reason
    assert "baseline" in reason


def test_a_thin_window_counts_as_nothing_compared() -> None:
    """The floor is a count, not a presence check: four rows is not a trend."""
    populated = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=5)
    thin = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=4)

    assert shortfall(thin, populated, 5) == (
        "the recent window holds 4 of the 5 rows a comparison needs"
    )


# --- The shipped review step -------------------------------------------------


def compare_step() -> dict[str, object]:
    workflow = yaml.safe_load(read_text(DRIFT_WORKFLOW))
    for step in workflow["jobs"]["drift"]["steps"]:
        if step.get("name") == COMPARE_STEP:
            return dict(step)
    raise AssertionError(f"drift.yml no longer has a {COMPARE_STEP!r} step")


def review_program() -> str:
    """The exact bytes the workflow pipes into `python -`.

    Extracted rather than copied. A second copy of this program would pass its
    own tests forever while the shipped one exited 0 on an empty window.
    """
    script = compare_step()["run"]
    assert isinstance(script, str)
    match = re.search(r"<<'PY'[^\n]*\n(.*?)\nPY(?:\n|$)", script, flags=re.DOTALL)
    assert match is not None, "the review step must carry an inline program"
    return match.group(1)


def scheduled_windows() -> dict[str, str]:
    """What a scheduled run puts in the environment: every `|| 'N'` default.

    A schedule passes no inputs, so this is the path that runs 51 weeks a year
    and the one worth testing first.
    """
    env = compare_step()["env"]
    assert isinstance(env, dict)
    resolved: dict[str, str] = {}
    for name, expression in env.items():
        default = re.search(r"\|\|\s*'([^']+)'\s*\}\}", str(expression))
        assert default is not None, f"{name} must carry a literal default for the schedule"
        resolved[str(name)] = default.group(1)
    return resolved


def ledger(directory: Path, *, recent: int, baseline: int) -> None:
    """A ledger holding two windows of identical, healthy rows.

    Identical on both sides on purpose: the second half of this row's oracle is
    that a real comparison finding nothing still exits 0, and a fixture with any
    movement in it could not tell a pass from a lucky threshold.
    """
    today = datetime.date.today()
    written = directory / "state"
    written.mkdir(parents=True, exist_ok=True)
    shard = written / "scores" / "2026-08.csv"
    shard.parent.mkdir(parents=True, exist_ok=True)
    with shard.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
        out.writeheader()
        for age, count in ((1, recent), (14, baseline)):
            for _ in range(count):
                out.writerow(
                    {
                        "date": (today - datetime.timedelta(days=age)).isoformat(),
                        "source_url": HEALTHY,
                        "hhem": "0.85",
                        "extractiveness": "0.20",
                        "source_word_count": "1200",
                    }
                )


def review(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", review_program()],
        cwd=directory,
        env={**os.environ, **scheduled_windows()},
        capture_output=True,
        text=True,
        check=False,
    )


def enough() -> int:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).drift.min_window_rows


def test_the_review_reads_its_floor_from_config() -> None:
    """Rule #6. The shipped program asks config, and carries no number of its own."""
    program = review_program()

    assert "drift.min_window_rows" in program
    assert "from idhazh.config import load" in program
    assert enough() >= 1


@pytest.mark.parametrize(
    ("recent", "baseline", "empty"),
    [
        (0, 1, ("recent",)),
        (1, 0, ("baseline",)),
        (0, 0, ("recent", "baseline")),
    ],
    ids=["empty recent", "empty baseline", "both empty"],
)
def test_the_review_fails_when_it_compared_nothing(
    tmp_path: Path, recent: int, baseline: int, empty: tuple[str, ...]
) -> None:
    """The defect this row exists to close.

    `compare` walks the domains a window holds and an empty window holds none,
    so it returns no findings - and no findings printed "no drift across 0
    recent and 0 baseline rows" under a green check. Turn the scorer off for a
    week and the only automated watchman for slow extraction failure reported
    all clear every day.
    """
    ledger(tmp_path, recent=enough() * recent, baseline=enough() * baseline)
    result = review(tmp_path)

    assert result.returncode != 0, result.stdout
    assert "nothing was compared" in result.stdout
    assert "no drift" not in result.stdout
    for side in ("recent", "baseline"):
        named = f"the {side} window holds 0" in result.stdout
        assert named is (side in empty), f"{side} was named {named}, and it should not have been"


def test_a_populated_pair_of_windows_with_no_drift_still_passes(tmp_path: Path) -> None:
    """The other half of the oracle: the fix must not turn healthy into broken."""
    ledger(tmp_path, recent=enough(), baseline=enough())
    result = review(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "nothing was compared" not in result.stdout
    assert f"no drift across {enough()} recent and {enough()} baseline rows" in result.stdout


def test_a_ledger_that_is_not_there_is_not_a_green_check(tmp_path: Path) -> None:
    """A run whose checkout carries no ledger cleared nothing either."""
    result = review(tmp_path)

    assert result.returncode != 0, result.stdout
    assert "state/scores/ holds no month" in result.stdout


def test_the_review_still_fires_on_real_drift(tmp_path: Path) -> None:
    """A populated pair that HAS moved still reaches the alert, past the new floor."""
    today = datetime.date.today()
    written = tmp_path / "state"
    written.mkdir(parents=True)
    shard = written / "scores" / "2026-08.csv"
    shard.parent.mkdir(parents=True, exist_ok=True)
    with shard.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
        out.writeheader()
        for age, words in ((1, 150), (14, 1200)):
            for _ in range(enough()):
                out.writerow(
                    {
                        "date": (today - datetime.timedelta(days=age)).isoformat(),
                        "source_url": HEALTHY,
                        "hhem": "0.85",
                        "extractiveness": "0.20",
                        "source_word_count": str(words),
                    }
                )

    result = review(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert Alert.SCORING_CHROME.value in result.stdout
