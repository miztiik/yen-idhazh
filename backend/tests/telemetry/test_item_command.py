"""Does the item command retain each pass and inspect only its requested UTC day?"""

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text, seed_item_health

from idhazh import cli, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.telemetry import item

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


def _health(day: str, run: int = 1) -> ItemHealthRow:
    return ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    ).model_copy(update={"date": day, "run_id": f"{day}-{run}"})


def _trace(
    state: Path,
    health: ItemHealthRow,
    *,
    attempt: int = 1,
    job: ServerJob = ServerJob.WORK,
    legacy: bool = False,
) -> Path:
    path = telemetry.committed_trace_path(
        state, run_id=health.run_id, attempt=attempt, job=job, shard=0
    )
    if legacy:
        path = path.with_name(f"{health.run_id.split('-')[-1]}-00.jsonl")
    tracer = telemetry.Tracer(
        sink=telemetry.FileSink(path), now=lambda: f"{health.date}T06:00:00Z"
    )
    for child in (telemetry.SpanName.FETCH, telemetry.SpanName.SUMMARIZE):
        with tracer.trace(f"{health.run_id}-{health.item_id}"), tracer.span(telemetry.SpanName.ITEM):
            with tracer.span(child):
                pass
    tracer.flush()
    return path


def test_every_run_and_attempt_is_labelled_and_sorted_without_repeating_health(tmp_path: Path) -> None:
    day = "2026-09-18"
    health = _health(day)
    later = _health(day, run=2)
    state = tmp_path / "state"
    seed_item_health(state, day, [later, health])
    _trace(state, later)
    _trace(state, health, attempt=2)
    _trace(state, health)
    _trace(state, health, job=ServerJob.ASSEMBLE)

    lines = list(item.report(
        state, item_id=health.item_id, date=day, config_dir=CONFIG_DIR, today=date(2026, 9, 18)
    ))

    groups = [line.split(": ", 1)[0] for line in lines if ", attempt " in line]
    assert groups == [
        f"Run {day}-1, attempt 1, job assemble, shard 0",
        f"Run {day}-1, attempt 1, job work, shard 0",
        f"Run {day}-1, attempt 2, job work, shard 0",
        f"Run {day}-2, attempt 1, job work, shard 0",
    ]
    assert sum("resolved item-health row; attempt not recorded" in line for line in lines) == 2
    assert sum(line.startswith("item [") for line in lines) == 8


def test_legacy_trace_labels_do_not_invent_an_attempt_or_job(tmp_path: Path) -> None:
    health = _health("2026-09-18")
    state = tmp_path / "state"
    _trace(state, health, legacy=True)

    text = "\n".join(item.report(
        state, item_id=health.item_id, date=health.date, config_dir=CONFIG_DIR,
        today=date(2026, 9, 18),
    ))

    assert "attempt unknown, job unknown, shard 0" in text
    assert text.count("\nitem [") == 2
    assert "No item-health row" in text


@pytest.mark.parametrize(("kept_days", "expired"), [(1, True), (3, False)])
def test_the_configured_trace_window_applies_even_when_expired_files_remain(
    tmp_path: Path, kept_days: int, expired: bool
) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, config_dir)
    declaration = config_dir / "gardener" / "traces.json"
    policy = json.loads(read_text(declaration))
    policy["window"] = {"unit": "days", "value": kept_days}
    declaration.write_text(json.dumps(policy), encoding="utf-8", newline="\n")
    state = tmp_path / "state"
    health = _health("2026-09-22")
    seed_item_health(state, health.date, [health])
    trace = _trace(state, health)
    if expired:
        trace.write_text("an expired trace must not be opened\n", encoding="utf-8", newline="\n")

    text = "\n".join(item.report(
        state, item_id=health.item_id, date=health.date, config_dir=config_dir,
        today=date(2026, 9, 24),
    ))

    assert trace.exists()
    assert f'"item_id": "{health.item_id}"' in text
    assert ("outside configured retention" in text) is expired
    assert ("\nitem [" in text) is not expired


def test_trace_discovery_reads_only_the_requested_day(tmp_path: Path) -> None:
    state = tmp_path / "state"
    health = _health("2026-09-18")
    _trace(state, health)
    outside = _trace(state, _health("2026-09-17"))
    outside.write_text("this other day must not be opened\n", encoding="utf-8", newline="\n")

    text = "\n".join(item.report(
        state, item_id=health.item_id, date=health.date, config_dir=CONFIG_DIR,
        today=date(2026, 9, 18),
    ))

    assert text.count("\nitem [") == 2
    assert "2026-09-17" not in text


def test_missing_trace_keeps_the_settled_health_and_names_the_run(tmp_path: Path) -> None:
    state = tmp_path / "state"
    health = _health("2026-09-18")
    seed_item_health(state, health.date, [health])

    text = "\n".join(item.report(
        state, item_id=health.item_id, date=health.date, config_dir=CONFIG_DIR,
        today=date(2026, 9, 18),
    ))

    assert f'"item_id": "{health.item_id}"' in text
    assert f"Run {health.run_id}: no trace for this item" in text


@pytest.mark.parametrize("defect", ["duplicate", "cycle", "invalid duration"])
def test_invalid_trace_records_or_parent_links_are_refused(tmp_path: Path, defect: str) -> None:
    state = tmp_path / "state"
    health = _health("2026-09-18")
    path = _trace(state, health)
    records = [json.loads(line) for line in read_text(path).splitlines()]
    if defect == "duplicate":
        records.append(records[0])
    elif defect == "cycle":
        records[1]["parent_id"] = records[0]["span_id"]
    else:
        records[0]["duration_ms"] = "not a duration"
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8", newline="\n",
    )

    with pytest.raises(ValueError, match=r"duplicate|cycle|invalid trace record"):
        list(item.report(
            state, item_id=health.item_id, date=health.date, config_dir=CONFIG_DIR,
            today=date(2026, 9, 18),
        ))


@pytest.mark.parametrize("arguments", [[], ["--date", "20260918"]])
def test_the_item_cli_requires_an_explicit_canonical_utc_day(
    arguments: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["telemetry", "item", "ai-01", *arguments])

    assert stopped.value.code == 2
    assert "--date" in capsys.readouterr().err