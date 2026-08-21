"""Detect the failure that per-item scores cannot see.

Per-item scores measure variance within a day. Drift is a movement across
months: extraction quietly breaks on a site redesign, summaries start describing
navigation chrome, and every individual score stays healthy because the summary
is perfectly faithful to the garbage it was given.

Two design points do the work here, and both were arrived at by doing the
arithmetic rather than by picking a round number:

- **Alerts are per-domain, against that domain's own trailing median.** A global
  month-over-month mean cannot fire for weeks when a single site breaks: one
  domain contributing a couple of items a day moves the global mean by a few
  percent, which is under any sane threshold, while that domain is producing
  nothing but chrome.
- **The alert that names the failure directly is a conjunction**: a domain's
  faithfulness staying flat or rising *while* its median source length falls
  sharply. Either signal alone is noisy; together they are the definition of
  "the score is happily rewarding a summary of chrome".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import median
from typing import Final
from urllib.parse import urlsplit

#: Bumped when a rule below changes, because a fired alert has to be
#: interpretable against the rules in force when it fired.
DRIFT_VERSION: Final = "idhazh-drift-1"

WORD_COUNT_DROP: Final = 0.40
EXTRACTIVENESS_RISE: Final = 0.15
FAILURE_RATE_MAX: Final = 0.20


class Alert(StrEnum):
    SHORTER_SOURCES = "shorter_sources"
    MORE_COPYING = "more_copying"
    SCORING_CHROME = "scoring_chrome"


@dataclass(frozen=True, slots=True)
class Observation:
    """One eval row, reduced to what a trend needs."""

    source_url: str
    hhem: float
    extractiveness: float
    source_word_count: int


@dataclass(frozen=True, slots=True)
class Finding:
    alert: Alert
    domain: str
    detail: str


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


def compare(recent: Sequence[Observation], baseline: Sequence[Observation]) -> list[Finding]:
    """Every alert this pair of windows justifies, per domain.

    A domain absent from either window is skipped rather than reported: a source
    that published nothing is row 3's quarantine problem, not a drift signal.
    """
    findings: list[Finding] = []
    now = by_domain(recent)
    before = by_domain(baseline)

    for domain, current in sorted(now.items()):
        earlier = before.get(domain)
        if not earlier:
            continue

        words_now = _median([row.source_word_count for row in current])
        words_before = _median([row.source_word_count for row in earlier])
        shorter = words_before > 0 and words_now < words_before * (1 - WORD_COUNT_DROP)

        extract_now = _median([row.extractiveness for row in current])
        extract_before = _median([row.extractiveness for row in earlier])
        copying = extract_now - extract_before > EXTRACTIVENESS_RISE

        hhem_now = _median([row.hhem for row in current])
        hhem_before = _median([row.hhem for row in earlier])
        score_held = hhem_now >= hhem_before

        if shorter:
            findings.append(
                Finding(
                    Alert.SHORTER_SOURCES,
                    domain,
                    f"median source fell from {words_before:.0f} to {words_now:.0f} words",
                )
            )
        if copying:
            findings.append(
                Finding(
                    Alert.MORE_COPYING,
                    domain,
                    f"extractiveness rose from {extract_before:.2f} to {extract_now:.2f}",
                )
            )
        # The conjunction is the one that names the failure rather than a proxy
        # for it: the score is rewarding a summary of page furniture.
        if shorter and score_held:
            findings.append(
                Finding(
                    Alert.SCORING_CHROME,
                    domain,
                    (
                        f"sources shrank {(1 - words_now / words_before) * 100:.0f}% while "
                        f"faithfulness held at {hhem_now:.2f}"
                    ),
                )
            )
    return findings


def failure_rate(succeeded: int, attempted: int) -> float:
    return 0.0 if attempted <= 0 else 1 - (succeeded / attempted)


def extraction_is_rotting(succeeded: int, attempted: int) -> bool:
    """A host that keeps failing extraction has changed shape, not gone quiet."""
    return failure_rate(succeeded, attempted) > FAILURE_RATE_MAX
