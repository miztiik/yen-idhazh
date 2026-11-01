"""Do real writer failures reach gardener logs without subprocess text?"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.event_log import OneJsonLine
from idhazh.ledger import planner_maintenance as adapter

pytestmark = pytest.mark.contract


def test_scheduler_failure_logs_safe_detail_and_removes_its_stage(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(
        adapter.PlannerMaintenanceFailureError,
    ) as caught:
        adapter.maintain_period(
            tmp_path, LedgerName.ITEM_HEALTH, "daily", "2026-10-20",
            max_raw_files_per_period=100,
        )
    assert caught.value.stage == "validate-request"
    assert caught.value.code == "invalid-contract"
    assert list(tmp_path.iterdir()) == []
    rendered = OneJsonLine().format(caplog.records[-1])
    assert "validate-request" in rendered and "invalid-contract" in rendered
    assert str(tmp_path) not in rendered and ".planner-maintenance-" not in rendered


@pytest.mark.parametrize(
    ("request_text", "stage", "code"),
    (
        ('{"private-article-data":', "decode-request", "invalid-json"),
        (json.dumps({"staging_root": "C:\\private\\article.txt", "article_text": "private"}),
         "validate-request", "invalid-contract"),
    ),
)
def test_real_cli_failure_is_safe_in_python_and_gardener_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, request_text: str, stage: str, code: str,
) -> None:
    completed = subprocess.run(
        ["bun", "run", str(adapter._WRITER_CLI)], cwd=tmp_path,
        input=request_text, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 1 and completed.stdout == ""
    with caplog.at_level(logging.ERROR), pytest.raises(
        adapter.PlannerMaintenanceFailureError,
    ) as caught:
        adapter._check_writer_exit(completed)
    assert caught.value.stage == stage and caught.value.code == code
    assert str(caught.value) == "planner maintenance adapter failed"
    record = caplog.records[-1]
    rendered = OneJsonLine().format(record)
    assert stage in rendered and code in rendered
    assert "private" not in rendered and "private" not in completed.stderr
    assert str(tmp_path) not in rendered


@pytest.mark.parametrize(
    "detail",
    (
        "private raw exception text",
        '{"version":"2026-11-01","status":"failed","stage":"../private","code":"io-error"}',
        '{"version":"2026-11-01","status":"failed","stage":"write-compact","code":[]}',
        '{"version":"2026-11-01","status":"failed","stage":"write-compact","code":"io-error","path":"private"}',
        '{"version":"2026-10-27","status":"failed","stage":"write-compact","code":"io-error"}',
        "private" * 100,
    ),
)
def test_invalid_failure_records_are_discarded(detail: str) -> None:
    assert adapter._failure_detail(detail) is None
