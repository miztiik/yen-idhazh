"""A published day accounts for every story it planned.

Contract tier (CLAUDE.md section 13). The rule is the
`planned-items-reconciliation` check under
`idhazh.publication_checks.checks.reconciliation`, and it runs inside
`idhazh check-publication`, which `ci.yml` runs on every change and
`digest.yml` runs before every publish.

**An empty day is not the fault, which is the whole difficulty.** Two empty days
are normal and this refuses neither: a day that planned nothing found no new
article, and a day where everything failed publishes empty and says `partial`,
because a run that publishes nothing on a bad day is a run whose bad days are
invisible. 2026-09-14 is the second kind - 80 planned, 80 failed, nothing
published - and it has to stay publishable. The third empty day is the one
nothing can write honestly, and it is the only one refused here.

Every case is built rather than read off a committed day. The committed archive
holds one of the three shapes and has never held the refused one, so a test over
it would prove the rule fires on nothing (Guardrail #12, section 13).

The gate is asked through its own entry point rather than through the check's
internals, because what a reader is protected by is the exit code a workflow
step reads - not a list a test could assemble differently.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, record_fixture_day

from idhazh.publication_checks import run_publication_checks

pytestmark = [pytest.mark.contract]

#: A real pipeline-written day. Every case below starts from it and empties it,
#: so the version stamp, the date and the run list stay what the producer writes.
FIXTURE = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"
DATE: str = str(json.loads(read_text(FIXTURE))["date"])


def a_day_publishing_nothing(planned: int, failed: int) -> dict[str, Any]:
    """The fixture day with every story taken out of it, and a plan of `planned`.

    `partial` is not a free choice: `DigestDay` pins it to `items_failed > 0`,
    so setting it from `failed` is restating the contract rather than deciding
    anything.
    """
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    payload["items"] = []
    payload["verticals"] = []
    payload["leads"] = []
    payload["items_planned"] = planned
    payload["items_failed"] = failed
    payload["partial"] = failed > 0
    for run in payload["runs"]:
        run["items_added"] = 0
    return payload


def written(public_root: Path, payload: dict[str, Any]) -> Path:
    year, month, day = DATE.split("-")
    where = public_root / "digest" / year / month / day
    where.mkdir(parents=True, exist_ok=True)
    file = where / "digest.json"
    file.write_text(json.dumps(payload), encoding="utf-8")
    record_fixture_day(public_root, DATE, items=len(payload["items"]))
    return file


def faults_for(
    public_root: Path, payload: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> list[str]:
    """Every sentence the gate says about a tree holding that one day."""
    written(public_root, payload)
    with caplog.at_level(logging.ERROR):
        run_publication_checks(public_root / "digest", run_id="2026-08-21-1")
    return [record.getMessage() for record in caplog.records]


def test_a_day_that_planned_nothing_and_published_nothing_reports_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A quiet day: the pipeline found no new article.

    `backend/utilities/build_canary_day.py::quiet_day` writes nineteen of these
    and the console paints them amber, which is the correct reading. A rule that
    refused an empty day would refuse all nineteen.
    """
    assert faults_for(tmp_path, a_day_publishing_nothing(planned=0, failed=0), caplog) == []


def test_a_day_where_everything_failed_stays_publishable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """2026-09-14's shape. Refusing it would delete the record of a bad day.

    `digest.yml` gives the assemble job `if: always()` on purpose, so the day
    lands even when every worker refused. This rule must not undo that: the
    reader sees an empty day, the console sees 80 planned against 80 failed,
    and the run summary carries the `::error::` annotation `stage_assemble`
    prints.
    """
    assert faults_for(tmp_path, a_day_publishing_nothing(planned=80, failed=80), caplog) == []


def test_a_day_that_accounts_for_none_of_its_plan_is_refused(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The case nothing can write honestly, and the archive has never held it.

    `ItemOutcome` has two members, so a story the pipeline touched is `ok` or
    `failed`. A day holding neither has lost its whole plan with nothing
    recording where it went - and on the page and on the console it looks
    exactly like a quiet day, which is what makes it worth stopping.
    """
    faults = faults_for(tmp_path, a_day_publishing_nothing(planned=80, failed=0), caplog)

    assert any("accounts for none of them" in fault for fault in faults), faults
    assert any("80" in fault for fault in faults), faults


def test_a_day_that_published_its_stories_reports_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The denominator.

    A checker that passes everything reads exactly like one that passes a
    correct day, so the unmodified fixture is asserted on its own.
    """
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    payload["leads"] = []
    for item in payload["items"]:
        item["visual"] = None

    assert faults_for(tmp_path, payload, caplog) == []


def test_the_stage_stops_the_publish_rather_than_logging_and_passing(tmp_path: Path) -> None:
    """A rule that only writes a log line is not a gate."""
    written(tmp_path, a_day_publishing_nothing(planned=80, failed=0))

    assert run_publication_checks(tmp_path / "digest", run_id="2026-08-21-1") == 1
