"""Does sampling read the last published build's line without hiding invalid input?"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.ledger import SEED_COMMIT

from idhazh.contracts.run_manifest import RunManifest, RunRecord, RunStatus
from idhazh.similarity.published_line import read_published_line

DATE = "2026-09-18"
FLOOR = 0.94


def a_run(n: int, *, hour: str | None, line: float | None) -> RunRecord:
    return RunRecord(
        run_id=f"{DATE}-{n}", n=n, started_at=f"{DATE}T06:00:00Z",
        completed_at=None if hour is None else f"{DATE}T{hour}:00:00Z",
        status=RunStatus.PARTIAL if hour is None else RunStatus.COMPLETED,
        commit_sha=SEED_COMMIT, runner="test", items_planned=0,
        items_succeeded=0, items_failed=0, site_bytes=0, site_files=0,
        same_story_floor_applied=line,
    )


def write_manifest(path: Path, runs: list[RunRecord]) -> None:
    path.write_text(
        RunManifest(
            version=RunManifest.schema_version(), date=DATE, runs=runs
        ).to_json(),
        encoding="utf-8", newline="\n",
    )


@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        (("08", "18"), 0.92),
        (("18", "08"), 0.91),
        (("18", "18"), 0.92),
        ((None, "18"), 0.92),
        (("18", None), 0.91),
        ((None, None), 0.92),
    ],
)
def test_latest_completion_wins_with_later_list_entry_breaking_ties(
    tmp_path: Path, hours: tuple[str | None, str | None], expected: float
) -> None:
    path = tmp_path / "run.json"
    write_manifest(path, [
        a_run(1, hour=hours[0], line=0.91),
        a_run(2, hour=hours[1], line=0.92),
    ])

    assert read_published_line(DATE, manifest_path=path, floor_min=FLOOR) == expected


@pytest.mark.parametrize("hour", ["18", None])
def test_ties_follow_list_order_even_when_run_ordinals_are_reversed(
    tmp_path: Path, hour: str | None
) -> None:
    path = tmp_path / "run.json"
    write_manifest(path, [
        a_run(2, hour=hour, line=0.92),
        a_run(1, hour=hour, line=0.91),
    ])

    assert read_published_line(DATE, manifest_path=path, floor_min=FLOOR) == 0.91


@pytest.mark.parametrize("line", [0.0, 0.90, 1.0])
def test_a_recorded_line_is_not_clamped_to_the_configured_floor(
    tmp_path: Path, line: float, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "run.json"
    write_manifest(path, [a_run(1, hour="18", line=line)])

    with caplog.at_level(logging.INFO, logger="idhazh"):
        assert read_published_line(DATE, manifest_path=path, floor_min=FLOOR) == line

    assert "legacy-fallback" not in caplog.text


@pytest.mark.parametrize("source", ["missing", "null", "legacy"])
def test_only_absent_manifest_or_legacy_line_uses_the_logged_configured_floor(
    tmp_path: Path, source: str, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "run.json"
    if source != "missing":
        manifest = RunManifest(version=RunManifest.schema_version(), date=DATE, runs=[
            a_run(1, hour="08", line=0.90),
            a_run(2, hour="18", line=None),
        ])
        payload = manifest.model_dump(mode="json")
        if source == "legacy":
            payload["version"] = "2026-09-01"
            del payload["runs"][-1]["same_story_floor_applied"]
        path.write_text(json.dumps(payload), encoding="utf-8", newline="\n")

    with caplog.at_level(logging.INFO, logger="idhazh"):
        assert read_published_line(DATE, manifest_path=path, floor_min=FLOOR) == FLOOR

    reason = "missing_manifest" if source == "missing" else "null_applied_line"
    assert f"date={DATE} legacy-fallback={reason} floor_min={FLOOR}" in caplog.text


@pytest.mark.parametrize(
    "malformation",
    ["json", "empty_runs", "missing_required", "invalid_line", "invalid_completion"],
)
def test_malformed_present_manifest_remains_a_native_validation_error(
    tmp_path: Path, malformation: str, caplog: pytest.LogCaptureFixture
) -> None:
    payload = RunManifest(
        version=RunManifest.schema_version(), date=DATE,
        runs=[a_run(1, hour="18", line=0.90)],
    ).model_dump(mode="json")
    if malformation == "empty_runs":
        payload["runs"] = []
    elif malformation == "missing_required":
        del payload["runs"][0]["commit_sha"]
    elif malformation == "invalid_line":
        payload["runs"][0]["same_story_floor_applied"] = 1.01
    elif malformation == "invalid_completion":
        payload["runs"][0]["completed_at"] = "not-a-time"
    text = "{" if malformation == "json" else json.dumps(payload)
    path = tmp_path / "run.json"
    path.write_text(text, encoding="utf-8", newline="\n")

    with caplog.at_level(logging.INFO, logger="idhazh"):
        with pytest.raises(ValidationError):
            read_published_line(DATE, manifest_path=path, floor_min=FLOOR)

    assert "legacy-fallback" not in caplog.text
