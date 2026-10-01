"""Does the item command retain each pass and inspect only its requested UTC day?"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text, seed_item_health

from idhazh import cli, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.item_health import ItemHealthRow

pytestmark = pytest.mark.contract


def test_item_command_prints_health_and_two_item_spans(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    day = datetime.now(UTC).date().isoformat()
    run_id = f"{day}-1"
    health = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    ).model_copy(update={"date": day, "run_id": run_id})
    state = tmp_path / "state"
    seed_item_health(state, day, [health])
    path = telemetry.committed_trace_path(
        state, run_id=run_id, attempt=1, job=ServerJob.WORK, shard=0
    )
    tracer = telemetry.Tracer(sink=telemetry.FileSink(path), now=lambda: f"{day}T06:00:00Z")
    for child in (telemetry.SpanName.FETCH, telemetry.SpanName.SUMMARIZE):
        with tracer.trace(f"{run_id}-{health.item_id}"), tracer.span(telemetry.SpanName.ITEM):
            with tracer.span(child):
                pass
    with tracer.trace(f"{run_id}-other-item"), tracer.span(telemetry.SpanName.SCORE):
        pass
    tracer.flush()

    assert cli.main([
        "telemetry", "item", health.item_id, "--date", day, "--state-root", str(state)
    ]) == 0
    output = capsys.readouterr().out
    assert f'"item_id": "{health.item_id}"' in output
    assert '"outcome": "ok"' in output
    assert output.count("\nitem [") == 2
    assert "\n  fetch [" in output
    assert "\n  summarize [" in output
    assert "score [" not in output
    assert "other-item" not in output
    assert "attempt 1, job work, shard 0" in output