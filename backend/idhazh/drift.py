"""Compare measured articles, not row counts or incompatible model scores.

A movement in live article lengths warrants inspection; it does not prove an
extraction failure. A source can publish shorter stories without changing its
page template. Score-dependent comparisons require a matching model and scorer.
Each metric needs enough distinct measured articles on both sides, and an
unmeasured comparison is never reported as healthy.

The pipeline stamp was a third part of that identity until 2026-09-12, and it is
what made the comparison unreachable: the stamp moved on any of seventeen
inputs, so a reworded prompt inside a window split the window in two and both
halves fell under the minimum. Nothing was compared, and nothing compared reads
as no drift at every call site.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from statistics import median
from typing import Final
from urllib.parse import urlsplit

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.knobs.evaluation import DriftConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.day_partition import days_in_window

#: Bumped when a rule below changes, because a fired alert has to be
#: interpretable against the rules in force when it fired.
DRIFT_VERSION: Final = "idhazh-drift-3"

FAILURE_RATE_MAX: Final = 0.20
GITHUB_ISSUE_BODY_MAX_BYTES: Final = 65536

type Series = tuple[str, str]


class Alert(StrEnum):
    SHORTER_SOURCES = "shorter_sources"
    MORE_COPYING = "more_copying"
    SCORING_CHROME = "scoring_chrome"


@dataclass(frozen=True, slots=True)
class Observation:
    """One eval row, reduced to what a trend needs.

    `source_word_count` is None when the ledger does not know how long the
    article was. A row written before 2026-08-27 whose article was truncated is
    the case: the pre-cap body was discarded at extract, so that length exists
    nowhere. Such a row still carries a faithfulness score and an extractiveness
    score, so it is kept and only the length rule steps over it - dropping the
    whole observation would take two working signals away with the missing one.
    """

    source_url: str
    hhem: float | None
    extractiveness: float | None
    source_word_count: int | None
    model_id: str = ""
    scorer_version: str = ""
    url_key: str = ""
    scored_at: str = ""
    date: str = ""

    @property
    def series(self) -> Series:
        return self.model_id, self.scorer_version


@dataclass(frozen=True, slots=True)
class Finding:
    alert: Alert
    domain: str
    detail: str
    series: Series | None = None


@dataclass(frozen=True, slots=True)
class Assessment:
    findings: list[Finding]
    compared: int
    skipped: list[str]


@dataclass(frozen=True, slots=True)
class Windows:
    baseline_start: date
    recent_start: date
    end: date
    recent: list[Observation]
    baseline: list[Observation]
    #: The ledger days this read actually opened, oldest first. A day the ledger
    #: never recorded has no file and is not named here.
    days_read: tuple[str, ...]


def _observation(row: EvalRow) -> Observation:
    """One settled eval row, reduced to what a trend needs. The contract already checked it."""
    return Observation(
        str(row.source_url),
        row.hhem,
        row.extractiveness,
        row.source_words_before_cap,
        model_id=row.model_id,
        scorer_version=row.scorer_version,
        url_key=row.url_key,
        scored_at=row.scored_at or row.date,
        date=row.date,
    )


def read_windows(state_dir: Path, *, today: date, recent_days: int, baseline_days: int) -> Windows:
    """Read only the days touched by two completed-day UTC windows.

    `day_partition.days_in_window` names both ends, so a cover of `n` days reads
    the rows of at most `n + 1` days and reads exactly those days, through the
    ledger door's bounded day read (`ledger.load_days`): each day from the one
    file that serves it, settled on its own.

    A day the ledger never recorded holds no row, which is not a fault: a run
    that scored nothing that day wrote nothing that day.
    """
    if recent_days < 1 or baseline_days < 1:
        raise ValueError("recent_days and baseline_days must each be at least one")
    recent_start = today - timedelta(days=recent_days)
    baseline_start = recent_start - timedelta(days=baseline_days)
    recent: list[Observation] = []
    baseline: list[Observation] = []
    dates = days_in_window(
        (today - timedelta(days=1)).isoformat(), recent_days + baseline_days - 1
    )
    rows = ledger.load_days(state_dir, LedgerName.SCORES, dates, model=EvalRow)
    for row in rows:
        when = date.fromisoformat(row.date)
        if not baseline_start <= when < today:
            continue
        if when >= recent_start:
            recent.append(_observation(row))
        else:
            baseline.append(_observation(row))
    days_read = tuple(sorted({row.date for row in rows}))
    return Windows(baseline_start, recent_start, today, recent, baseline, days_read)


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def by_domain(rows: Sequence[Observation]) -> dict[str, list[Observation]]:
    grouped: dict[str, list[Observation]] = {}
    for row in rows:
        grouped.setdefault(domain_of(row.source_url), []).append(row)
    return grouped


def _median(values: Sequence[float]) -> float:
    return float(median(values)) if values else 0.0


def _median_words(rows: Sequence[Observation]) -> float:
    """The median over the rows that know their own length. Zero when none do.

    A zero reads as "no comparison" downstream, because both length rules are
    guarded on `words_before > 0`. That is the honest answer for a window made
    entirely of rows whose article length was never recorded.
    """
    return _median([row.source_word_count for row in rows if row.source_word_count is not None])


def _distinct(rows: Sequence[Observation]) -> list[Observation]:
    """Keep the latest measured row per article; ties keep the first row."""
    selected: dict[str, Observation] = {}
    for row in rows:
        key = row.url_key or row.source_url
        previous = selected.get(key)
        if previous is None or row.scored_at > previous.scored_at:
            selected[key] = row
    return list(selected.values())


def _too_few(
    current: Sequence[Observation], earlier: Sequence[Observation], minimum: int
) -> str | None:
    if min(len(current), len(earlier)) < minimum:
        return (
            f"insufficient evidence: {len(current)} recent and {len(earlier)} baseline "
            f"distinct articles; need {minimum} on each side"
        )
    return None


def _counts(current: Sequence[Observation], earlier: Sequence[Observation]) -> str:
    return f"{len(earlier)} baseline and {len(current)} recent distinct articles"


def _shorter(current: Sequence[Observation], earlier: Sequence[Observation], drop: float) -> bool:
    before = _median_words(earlier)
    now = _median_words(current)
    return before > 0 and now > 0 and now < before * (1 - drop)


def assess(
    recent: Sequence[Observation],
    baseline: Sequence[Observation],
    *,
    config: DriftConfig,
    minimum_rows: int | None = None,
) -> Assessment:
    minimum = config.min_domain_rows if minimum_rows is None else minimum_rows
    if minimum < 2:
        raise ValueError("a domain comparison needs at least two distinct articles")
    findings: list[Finding] = []
    skipped: list[str] = []
    compared = 0
    now = by_domain(recent)
    before = by_domain(baseline)

    for domain in sorted(now.keys() | before.keys()):
        current = now.get(domain, [])
        earlier = before.get(domain, [])
        current_words = _distinct([row for row in current if row.source_word_count is not None])
        earlier_words = _distinct([row for row in earlier if row.source_word_count is not None])
        reason = _too_few(current_words, earlier_words, minimum)
        if reason:
            skipped.append(f"{domain}: source length not compared; {reason}")
        else:
            compared += 1
            if _shorter(current_words, earlier_words, config.source_word_count_drop):
                findings.append(
                    Finding(
                        Alert.SHORTER_SOURCES,
                        domain,
                        f"median source fell from {_median_words(earlier_words):.0f} to "
                        f"{_median_words(current_words):.0f} words; "
                        f"{_counts(current_words, earlier_words)}; inspect extracted text",
                    )
                )

        for series in sorted({row.series for row in current}):
            if not all(series):
                skipped.append(
                    f"{domain}: model-dependent metrics not compared; model or scorer "
                    "identity is missing"
                )
                continue
            current_series = [row for row in current if row.series == series]
            earlier_series = [row for row in earlier if row.series == series]
            label = f"{domain} [{series[0]}, scorer {series[1]}]"
            current_copy = _distinct(
                [row for row in current_series if row.extractiveness is not None]
            )
            earlier_copy = _distinct(
                [row for row in earlier_series if row.extractiveness is not None]
            )
            reason = _too_few(current_copy, earlier_copy, minimum)
            if reason:
                skipped.append(f"{label}: copying not compared; {reason}")
            else:
                compared += 1
                extract_now = _median(
                    [row.extractiveness for row in current_copy if row.extractiveness is not None]
                )
                extract_before = _median(
                    [row.extractiveness for row in earlier_copy if row.extractiveness is not None]
                )
                if extract_now - extract_before > config.extractiveness_rise:
                    findings.append(
                        Finding(
                            Alert.MORE_COPYING,
                            domain,
                            f"copied four-word-phrase share rose from {extract_before:.2f} "
                            f"to {extract_now:.2f}; {_counts(current_copy, earlier_copy)}",
                            series,
                        )
                    )

            current_pair = _distinct(
                [
                    row
                    for row in current_series
                    if row.hhem is not None and row.source_word_count is not None
                ]
            )
            earlier_pair = _distinct(
                [
                    row
                    for row in earlier_series
                    if row.hhem is not None and row.source_word_count is not None
                ]
            )
            reason = _too_few(current_pair, earlier_pair, minimum)
            if reason:
                skipped.append(f"{label}: length with faithfulness not compared; {reason}")
                continue
            compared += 1
            hhem_now = _median([row.hhem for row in current_pair if row.hhem is not None])
            hhem_before = _median([row.hhem for row in earlier_pair if row.hhem is not None])
            if (
                _shorter(current_pair, earlier_pair, config.source_word_count_drop)
                and hhem_now >= hhem_before
            ):
                findings.append(
                    Finding(
                        Alert.SCORING_CHROME,
                        domain,
                        "possible non-article text: median source fell from "
                        f"{_median_words(earlier_pair):.0f} to {_median_words(current_pair):.0f} "
                        f"words while faithfulness held or rose from {hhem_before:.2f} "
                        f"to {hhem_now:.2f}; {_counts(current_pair, earlier_pair)}; "
                        "inspect extraction before diagnosing a failure",
                        series,
                    )
                )
    return Assessment(findings, compared, skipped)


def compare(
    recent: Sequence[Observation],
    baseline: Sequence[Observation],
    *,
    minimum_rows: int | None = None,
    config: DriftConfig | None = None,
) -> list[Finding]:
    """Findings only; operational callers use `assess` to also report coverage."""
    return assess(
        recent, baseline, config=config or DriftConfig(), minimum_rows=minimum_rows
    ).findings


def failure_rate(succeeded: int, attempted: int) -> float:
    return 0.0 if attempted <= 0 else 1 - (succeeded / attempted)


def extraction_is_rotting(succeeded: int, attempted: int) -> bool:
    """A host that keeps failing extraction has changed shape, not gone quiet."""
    return failure_rate(succeeded, attempted) > FAILURE_RATE_MAX


def shortfall(
    recent: Sequence[Observation], baseline: Sequence[Observation], minimum: int
) -> str | None:
    """Why this pair of windows could not be compared, or None when it could.

    `compare` returns no findings for an empty window, and no findings reads as
    "no drift" at every call site that has ever existed. Those are opposite
    facts: turn the scorer off for a week and the only automated watchman for
    slow extraction failure reports all clear, every day, under a green check.

    The sentence names the side that was thin and its count, because "nothing to
    compare" is a different repair from "no drift" and the operator has to know
    which one arrived.
    """
    counts = (
        (side, len(_distinct(rows))) for side, rows in (("recent", recent), ("baseline", baseline))
    )
    thin = [
        f"the {side} window holds {count} of the {minimum} rows a comparison needs"
        for side, count in counts
        if count < minimum
    ]
    return "; ".join(thin) if thin else None


def report(
    windows: Windows, *, config: DriftConfig, include_skipped_details: bool = True
) -> tuple[str, int]:
    """Plain-text operator report and exit code; findings do not stop publication."""
    recent_end = windows.end - timedelta(days=1)
    baseline_end = windows.recent_start - timedelta(days=1)
    lines = [
        f"Drift review {windows.end} ({DRIFT_VERSION})",
        f"Recent: {windows.recent_start} through {recent_end} UTC.",
        f"Baseline: {windows.baseline_start} through {baseline_end} UTC.",
        "Only completed UTC days are included. Live article changes are signals, not diagnoses.",
        f"Each domain metric needs {config.min_domain_rows} distinct measured articles per side.",
        f"Alerts: source length falls over {config.source_word_count_drop:.0%}; "
        f"copied four-word-phrase share rises over {config.extractiveness_rise:.2f}.",
    ]
    for side, observations in (("Recent", windows.recent), ("Baseline", windows.baseline)):
        recorded_dates = sorted({row.date for row in observations})
        span = f"{recorded_dates[0]} through {recorded_dates[-1]}" if recorded_dates else "none"
        unknown = sum(row.source_word_count is None for row in observations)
        lines.append(
            f"{side}: {len(observations)} rows, {len(_distinct(observations))} distinct articles; "
            f"{unknown} rows do not record the article's length; recorded dates: {span}."
        )
    if not windows.days_read:
        lines.append(
            f"The {LedgerName.SCORES.value} ledger holds no day in the requested window "
            "- nothing was compared"
        )
        return "\n".join(lines), 1
    thin = shortfall(windows.recent, windows.baseline, config.min_window_rows)
    if thin:
        lines.append(f"nothing was compared: {thin}")
        return "\n".join(lines), 1

    result = assess(windows.recent, windows.baseline, config=config)
    lines.append(
        f"Compared {result.compared} domain/metric series; "
        f"{len(result.skipped)} comparisons had insufficient evidence or missing identity."
    )
    if not result.compared:
        lines.append("nothing was compared: no domain metric had enough comparable evidence")
    elif not result.findings:
        lines.append(f"no drift in {result.compared} comparable domain/metric series")
    for finding in result.findings:
        lines.append(f"{finding.alert.value} {finding.domain}: {finding.detail}")
        if finding.series is not None:
            model, scorer = finding.series
            lines.append(f"  model: {model}; scorer: {scorer}")
    if result.skipped and include_skipped_details:
        lines.extend(("", "Not compared (not evidence of healthy extraction):", *result.skipped))
    return "\n".join(lines), 0 if result.compared else 1


def issue_body(windows: Windows, *, config: DriftConfig, run_url: str) -> str:
    """Bound the GitHub notice; the linked run log keeps every comparison."""
    text, _ = report(windows, config=config, include_skipped_details=False)
    link = (
        f"Full report: {run_url}\n"
        "The run log includes every finding and skipped comparison. "
        "Skipped comparisons are not evidence of healthy extraction."
    )
    body = f"{text}\n\n{link}"
    if len(body.encode("utf-8")) > GITHUB_ISSUE_BODY_MAX_BYTES:
        return (
            f"Drift review {windows.end} ({DRIFT_VERSION})\n"
            "The detailed findings exceed GitHub's issue-body limit. "
            "Read the full report before diagnosing a failure.\n\n"
            f"{link}"
        )
    return body
