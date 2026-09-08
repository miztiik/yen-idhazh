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
from dataclasses import replace
from pathlib import Path
from typing import Final

import pytest
import yaml  # type: ignore[import-untyped]
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig, DriftConfig
from idhazh.drift import (
    Alert,
    Observation,
    Windows,
    assess,
    compare,
    domain_of,
    extraction_is_rotting,
    failure_rate,
    issue_body,
    read_windows,
    report,
    shortfall,
)
from idhazh.evals.writer import ledger_path

# `workflow`, because the program `.github/workflows/drift.yml` ships is asserted here.
pytestmark = pytest.mark.workflow

DRIFT_WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "drift.yml"
COMPARE_STEP: Final = "Compare the windows"
#: The five cells the review reads out of the eval ledger. A row carries about
#: forty; `csv.DictReader` hands the program a mapping, so a fixture that names
#: these five exercises every line of it.
LEDGER_COLUMNS: Final = (
    "date",
    "source_url",
    "hhem",
    "extractiveness",
    "source_word_count",
    "model_id",
    "scorer_version",
    "pipeline_fingerprint",
)


def rows(
    url: str,
    *,
    words: int | None,
    hhem: float | None,
    extractiveness: float | None,
    n: int | None = None,
) -> list[Observation]:
    count = DriftConfig().min_domain_rows if n is None else n
    return [
        Observation(
            f"{url}/{index}",
            hhem,
            extractiveness,
            words,
            model_id="fixture-model",
            scorer_version="fixture-scorer",
            pipeline_fingerprint="fixture-pipeline",
        )
        for index in range(count)
    ]


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


def test_a_busy_domain_cannot_lend_evidence_to_a_sparse_domain() -> None:
    steady = [Observation(f"{OTHER}/{index}", 0.85, 0.2, 1200) for index in range(5)]
    before = [*steady, Observation(HEALTHY, 0.85, 0.2, 1200)]
    after = [*steady, Observation(HEALTHY, 0.9, 0.2, 150)]

    assert compare(after, before, minimum_rows=5) == []


@pytest.mark.parametrize("minimum", [0, 1])
def test_the_domain_floor_cannot_allow_a_single_article(minimum: int) -> None:
    with pytest.raises(ValidationError, match="min_domain_rows"):
        DriftConfig(min_domain_rows=minimum)


def test_repeated_observations_cannot_manufacture_a_domain_sample() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2, n=1) * 20
    after = rows(HEALTHY, words=150, hhem=0.9, extractiveness=0.8, n=1) * 20
    result = assess(after, before, config=DriftConfig())

    assert result.findings == []
    assert result.compared == 0
    assert any("1 recent and 1 baseline" in reason for reason in result.skipped)


def test_the_latest_measured_row_wins_by_article_identity() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    latest = [
        replace(row, url_key=f"article-{index}", scored_at="2026-09-05T12:00:00Z")
        for index, row in enumerate(before)
    ]
    older = [
        replace(
            row,
            source_url=f"{row.source_url}?earlier=1",
            source_word_count=150,
            extractiveness=0.8,
            scored_at="2026-09-05T10:00:00Z",
        )
        for row in latest
    ]

    assert compare([*latest, *older], before) == []
    assert compare([*older, *latest], before) == []


def test_a_later_unmeasured_row_does_not_erase_a_measured_metric() -> None:
    before = rows(HEALTHY, words=1200, hhem=None, extractiveness=0.2)
    measured = rows(HEALTHY, words=150, hhem=None, extractiveness=0.8)
    unmeasured = [
        replace(
            row,
            source_word_count=None,
            extractiveness=None,
            scored_at="2026-09-05T12:00:00Z",
        )
        for row in measured
    ]

    findings = compare([*measured, *unmeasured], before)

    assert {finding.alert for finding in findings} == {
        Alert.SHORTER_SOURCES,
        Alert.MORE_COPYING,
    }


def test_a_partial_review_does_not_claim_every_article_was_compared() -> None:
    steady = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    sparse = rows(OTHER, words=150, hhem=0.9, extractiveness=0.8, n=1)
    windows = Windows(
        datetime.date(2026, 8, 2),
        datetime.date(2026, 8, 30),
        datetime.date(2026, 9, 6),
        [*steady, *sparse],
        steady,
        ("2026-08", "2026-09"),
    )

    text, status = report(windows, config=DriftConfig())

    assert status == 0
    assert "no drift in 3 comparable domain/metric series" in text
    assert "no drift across" not in text
    assert "blog.example.org: source length not compared" in text


@pytest.mark.parametrize("field", ["model_id", "scorer_version", "pipeline_fingerprint"])
def test_model_metrics_do_not_compare_different_versions(field: str) -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = [
        replace(
            row,
            model_id="changed" if field == "model_id" else row.model_id,
            scorer_version="changed" if field == "scorer_version" else row.scorer_version,
            pipeline_fingerprint=(
                "changed" if field == "pipeline_fingerprint" else row.pipeline_fingerprint
            ),
        )
        for row in rows(HEALTHY, words=150, hhem=0.9, extractiveness=0.8)
    ]
    findings = compare(after, before)

    assert {finding.alert for finding in findings} == {Alert.SHORTER_SOURCES}


def test_source_lengths_do_not_depend_on_a_faithfulness_score() -> None:
    before = rows(HEALTHY, words=1200, hhem=None, extractiveness=None)
    after = rows(HEALTHY, words=150, hhem=None, extractiveness=None)

    assert {finding.alert for finding in compare(after, before)} == {Alert.SHORTER_SOURCES}


def test_a_missing_version_does_not_invent_a_comparable_model() -> None:
    before = [
        replace(row, model_id="") for row in rows(HEALTHY, words=None, hhem=0.8, extractiveness=0.2)
    ]
    after = [
        replace(row, model_id="") for row in rows(HEALTHY, words=None, hhem=0.8, extractiveness=0.8)
    ]
    result = assess(after, before, config=DriftConfig())

    assert result.findings == []
    assert result.compared == 0
    assert any("identity is missing" in reason for reason in result.skipped)


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


def test_the_length_floor_counts_only_articles_with_a_measured_length() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=None, hhem=0.85, extractiveness=0.2, n=3) + rows(
        HEALTHY, words=180, hhem=0.85, extractiveness=0.2, n=1
    )
    alerts = {finding.alert for finding in compare(after, before)}

    assert Alert.SHORTER_SOURCES not in alerts


# --- The failure this row exists to catch -----------------------------------


def test_a_site_redesign_that_shortens_extraction_fires() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=180, hhem=0.85, extractiveness=0.2)
    alerts = {finding.alert for finding in compare(after, before)}
    assert Alert.SHORTER_SOURCES in alerts


def test_the_conjunction_requests_inspection_rather_than_claiming_a_cause() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=150, hhem=0.9, extractiveness=0.2)
    findings = compare(after, before)
    chrome = [f for f in findings if f.alert is Alert.SCORING_CHROME]
    assert chrome
    assert "faithfulness held" in chrome[0].detail
    assert "possible non-article text" in chrome[0].detail
    assert "inspect extraction" in chrome[0].detail


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

    domains = {finding.domain for finding in compare(after, before, minimum_rows=2)}
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


def test_the_issue_body_keeps_findings_when_skipped_details_exceed_githubs_limit() -> None:
    before = rows(HEALTHY, words=1200, hhem=0.85, extractiveness=0.2)
    after = rows(HEALTHY, words=150, hhem=0.9, extractiveness=0.8)
    sparse = [
        row
        for index in range(300)
        for row in rows(f"https://sparse-{index}.example/story", words=150, hhem=0.9, extractiveness=0.2, n=1)
    ]
    windows = Windows(
        datetime.date(2026, 8, 2),
        datetime.date(2026, 8, 30),
        datetime.date(2026, 9, 6),
        [*after, *sparse],
        before,
        ("2026-08", "2026-09"),
    )
    run_url = "https://github.com/example/repository/actions/runs/123"

    full, status = report(windows, config=DriftConfig())
    body = issue_body(windows, config=DriftConfig(), run_url=run_url)

    assert status == 0
    assert len(full.encode("utf-8")) > 65536
    assert len(body.encode("utf-8")) <= 65536
    for alert in Alert:
        assert f"{alert.value} news.example.com:" in body
    assert "900 comparisons had insufficient evidence" in body
    assert "sparse-299.example" in full
    assert "sparse-299.example" not in body
    assert run_url in body
    assert "not evidence of healthy extraction" in body


def test_the_issue_body_links_the_full_report_when_findings_alone_are_too_large() -> None:
    before = [
        row
        for index in range(180)
        for row in rows(f"https://changed-{index}.example/story", words=1200, hhem=0.85, extractiveness=0.2, n=2)
    ]
    after = [replace(row, source_word_count=150, hhem=0.9, extractiveness=0.8) for row in before]
    windows = Windows(
        datetime.date(2026, 8, 2),
        datetime.date(2026, 8, 30),
        datetime.date(2026, 9, 6),
        after,
        before,
        ("2026-08", "2026-09"),
    )
    config = DriftConfig(min_domain_rows=2)
    run_url = "https://github.com/example/repository/actions/runs/123"

    summary, status = report(windows, config=config, include_skipped_details=False)
    body = issue_body(windows, config=config, run_url=run_url)

    assert status == 0
    assert len(summary.encode("utf-8")) > 65536
    assert len(body.encode("utf-8")) <= 65536
    assert "findings exceed GitHub's issue-body limit" in body
    assert run_url in body


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
    today = datetime.datetime.now(datetime.UTC).date()
    write_rows(
        directory,
        [
            {
                "date": (today - datetime.timedelta(days=age)).isoformat(),
                "source_url": f"{HEALTHY}/{age}/{index}",
                "hhem": "0.85",
                "extractiveness": "0.20",
                "source_word_count": "1200",
                "model_id": "fixture-model",
                "scorer_version": "fixture-scorer",
                "pipeline_fingerprint": "fixture-pipeline",
            }
            for age, count in ((1, recent), (14, baseline))
            for index in range(count)
        ],
    )


def write_rows(directory: Path, records: list[dict[str, str]]) -> None:
    grouped: dict[Path, list[dict[str, str]]] = {}
    if not records:
        yesterday = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
        grouped[ledger_path(directory / "state", yesterday.isoformat())] = []
    for record in records:
        grouped.setdefault(ledger_path(directory / "state", record["date"]), []).append(record)
    for shard, values in grouped.items():
        shard.parent.mkdir(parents=True, exist_ok=True)
        with shard.open("w", encoding="utf-8", newline="") as handle:
            out = csv.DictWriter(handle, fieldnames=LEDGER_COLUMNS)
            out.writeheader()
            out.writerows(values)


def review(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", review_program()],
        cwd=directory,
        env={
            **os.environ,
            **scheduled_windows(),
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "example/repository",
            "GITHUB_RUN_ID": "123",
        },
        capture_output=True,
        text=True,
        check=False,
    )


def enough() -> int:
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).drift
    return max(config.min_window_rows, config.min_domain_rows)


def test_the_review_reads_its_floor_from_config() -> None:
    """Rule #6. The shipped program asks config, and carries no number of its own."""
    program = review_program()

    assert "config = load().app.drift" in program
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
    assert "no drift in 3 comparable domain/metric series" in result.stdout


def test_a_ledger_that_is_not_there_is_not_a_green_check(tmp_path: Path) -> None:
    """A run whose checkout carries no ledger cleared nothing either."""
    result = review(tmp_path)

    assert result.returncode != 0, result.stdout
    assert "state/scores/ holds no month" in result.stdout


def test_the_review_still_fires_on_real_drift(tmp_path: Path) -> None:
    """A populated pair that HAS moved still reaches the alert, past the new floor."""
    today = datetime.datetime.now(datetime.UTC).date()
    write_rows(
        tmp_path,
        [
            {
                "date": (today - datetime.timedelta(days=age)).isoformat(),
                "source_url": f"{HEALTHY}/{age}/{index}",
                "hhem": "0.85",
                "extractiveness": "0.20",
                "source_word_count": str(words),
                "model_id": "fixture-model",
                "scorer_version": "fixture-scorer",
                "pipeline_fingerprint": "fixture-pipeline",
            }
            for age, words in ((1, 150), (14, 1200))
            for index in range(enough())
        ],
    )

    result = review(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert Alert.SCORING_CHROME.value in result.stdout
    assert "scorer: fixture-scorer" in result.stdout
    body = read_text(tmp_path / "drift-issue.txt")
    assert Alert.SCORING_CHROME.value in body
    assert "https://github.com/example/repository/actions/runs/123" in body
    workflow = yaml.safe_load(read_text(DRIFT_WORKFLOW))
    issue_step = next(
        step for step in workflow["jobs"]["drift"]["steps"]
        if step.get("name") == "Open an issue when something moved"
    )
    assert "--body-file drift-issue.txt" in issue_step["run"]


def test_the_reader_uses_completed_utc_days_and_only_relevant_months(tmp_path: Path) -> None:
    anchor = datetime.date(2026, 1, 5)
    write_rows(
        tmp_path,
        [
            {
                "date": (anchor - datetime.timedelta(days=age)).isoformat(),
                "source_url": f"{HEALTHY}/{age}",
                "hhem": "",
                "extractiveness": "0.2",
                "source_word_count": "100",
            }
            for age in (-1, 0, 1, 7, 8, 35, 36)
        ],
    )
    irrelevant = tmp_path / "state" / "scores" / "2024-01.csv"
    irrelevant.write_bytes(b"not a ledger")

    result = read_windows(tmp_path / "state", today=anchor, recent_days=7, baseline_days=28)

    assert result.months_read == ("2025-12", "2026-01")
    assert {row.date for row in result.recent} == {"2025-12-29", "2026-01-04"}
    assert {row.date for row in result.baseline} == {"2025-12-01", "2025-12-28"}
    assert all(row.hhem is None for row in result.recent + result.baseline)


@pytest.mark.parametrize("metric", ["hhem", "extractiveness", "source_word_count"])
def test_an_invalid_metric_is_reported_instead_of_silently_dropped(
    tmp_path: Path, metric: str
) -> None:
    record = {
        "date": "2026-09-05",
        "source_url": HEALTHY,
        "hhem": "0.9",
        "extractiveness": "0.2",
        "source_word_count": "100",
    }
    record[metric] = "nan"
    write_rows(tmp_path, [record])

    with pytest.raises(ValueError, match="row 2 is invalid for drift"):
        read_windows(
            tmp_path / "state", today=datetime.date(2026, 9, 6), recent_days=7, baseline_days=28
        )


def test_full_windows_with_only_sparse_domains_are_not_a_clean_review(tmp_path: Path) -> None:
    write_rows(
        tmp_path,
        [
            {
                "date": when,
                "source_url": f"https://domain-{index}.example/story",
                "hhem": "0.9",
                "extractiveness": "0.2",
                "source_word_count": "100",
            }
            for when in ("2026-09-05", "2026-08-20")
            for index in range(enough())
        ],
    )
    windows = read_windows(
        tmp_path / "state", today=datetime.date(2026, 9, 6), recent_days=7, baseline_days=28
    )
    text, status = report(windows, config=DriftConfig())

    assert status == 1
    assert "nothing was compared: no domain metric" in text
    assert "no drift" not in text
    assert "source length not compared" in text
