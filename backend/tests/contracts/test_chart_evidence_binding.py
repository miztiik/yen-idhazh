"""Does the frontend copy read the same chart evidence the three payloads write?"""

from __future__ import annotations

import json
import re

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.chart_evidence import ChartEvidence
from idhazh.contracts.public_run_day import PublicRunDay
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.visual_decision import VisualDecision

pytestmark = pytest.mark.contract

READER = REPO_ROOT / "frontend" / "src" / "lib" / "chart-evidence.ts"


def _frontend_fields() -> dict[str, str]:
    source = read_text(READER)
    match = re.search(r"export interface ChartEvidence \{([^}]+)\}", source)
    assert match is not None, "the frontend must declare its chart evidence copy"
    return dict(re.findall(r"\t(\w+): ([^;]+);", match[1]))


def test_evidence_fields_are_shared_by_every_payload_and_frontend_copy() -> None:
    fields = _frontend_fields()
    assert set(fields) == set(ChartEvidence.model_fields)
    for payload in (VisualDecision, RunManifest, PublicRunDay):
        schema = payload.json_schema()
        assert (
            schema["$defs"]["ChartEvidence"]["properties"]
            == (ChartEvidence.model_json_schema()["properties"])
        )
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "payload.ts")
    assert "chartEvidence: readChartEvidence(run.chart_evidence)" in source


def test_evidence_numeric_types_and_null_rates_match_the_frontend_copy() -> None:
    fields = _frontend_fields()
    for name, node in ChartEvidence.model_json_schema()["properties"].items():
        kinds = {part["type"] for part in node.get("anyOf", [node])}
        assert kinds <= {"integer", "number", "null"}
        assert fields[name] == ("number | null" if "null" in kinds else "number")


def test_an_old_monthly_report_reads_as_unknown_not_as_zero_figures() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "public-run-day" / "five-runs.json"))
    for run in payload["runs"]:
        del run["chart_evidence"]
    old = PublicRunDay.model_validate(payload)
    assert old.runs
    assert all(run.chart_evidence is None for run in old.runs)
