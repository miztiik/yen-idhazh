"""Unit-tier tests for the drift benchmark.

The row's own oracle is injected drift: a detector that has never fired has not
been shown to work. So every test here starts from a degradation and asserts the
alert fires - and the important one asserts that a GLOBAL threshold would have
missed it, which is why the rule is per-domain.
"""

from __future__ import annotations

from idhazh.drift import (
    Alert,
    Observation,
    compare,
    domain_of,
    extraction_is_rotting,
    failure_rate,
)


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
