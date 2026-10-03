"""Does the publication gate name a console payload its own contract refuses?

`frontend/public/telemetry/` is a published mirror a reader's console fetches,
and it was the one producer output no gate opened. A pytest walk over the
committed shards stood in for it, which `CLAUDE.md` section 13 refuses, so the
check belongs to the producer's own gate - where it runs against the tree the
run wrote rather than against whatever the repository has accumulated.

Every fixture below is built in the test from the committed contract fixture.
None of it reads `frontend/public/digest`, whose cost follows what the pipeline
has piled up.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, record_fixture_day

from idhazh.publication_checks import run_publication_checks

A_COMMITTED_DAY = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"


def a_published_day(public_root: Path) -> Path:
    """One published day on disk and in the named inventory.

    The marks the payload names are written as well, because the `pictures`
    check compares the two and a day naming a file that is not there is a fault
    rather than the clean day this test needs.
    """
    payload = json.loads(read_text(A_COMMITTED_DAY))
    year, month, dom = str(payload["date"]).split("-")
    where = public_root / "digest" / year / month / dom
    where.mkdir(parents=True, exist_ok=True)
    for item in payload["items"]:
        visual = item.get("visual")
        if visual and visual.get("data_path"):
            marks = public_root / visual["data_path"]
            marks.parent.mkdir(parents=True, exist_ok=True)
            marks.write_text('{"item_id": "ai-01"}', encoding="utf-8")
    (where / "digest.json").write_text(json.dumps(payload), encoding="utf-8")
    record_fixture_day(public_root, str(payload["date"]), items=len(payload["items"]))
    return where / "digest.json"


def test_a_telemetry_shard_the_contract_refuses_is_named_by_the_gate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The seventh producer, which read back nowhere until 2026-09-13."""
    public = tmp_path / "public"
    a_published_day(public)
    root = public / "digest"
    assert run_publication_checks(root, run_id="2026-08-21-1") == 0, "the day itself has to be clean"

    shard = public / "telemetry" / "2026-08.csv"
    shard.parent.mkdir(parents=True)
    shard.write_text("date,not_the_contract\n2026-08-21,1\n", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        assert run_publication_checks(root, run_id="2026-08-21-1") == 1
    assert "frontend/public/telemetry/2026-08.csv" in caplog.text, "name the file"
    assert "header is" in caplog.text, "and say what the contract wanted instead"
