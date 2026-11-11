"""Does the row a shard recorded outlive the process that recorded it?

The recorder validates 119 cells an item at a time and used to hand them to a
log line and to nothing else. A log line is a CI artifact that expires, so the
census was rebuilt later out of the article and the summary payloads, which
between them cannot carry most of those cells. These tests read the file the
work stage now leaves beside those payloads, over a real work stage against
captured pages and recorded replies - no network and nothing mocked
(Guardrail #7).

Sibling question, sibling module: `test_work_records.py` asks what a shard SAYS
while it runs. This one asks what SURVIVES it.

Every test uses the bounded fixture plan, so the cost does not move when the
archive grows (Guardrail #12).
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from itertools import count
from pathlib import Path
from typing import Any, Final

import pytest
from pytest import LogCaptureFixture, MonkeyPatch
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh import config
from idhazh.contracts.base import ServerJob
from idhazh.contracts.item_health import FailureCode, ItemHealthRow
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common
from idhazh.stages.work import stage_work
from idhazh.telemetry import host
from idhazh.telemetry.record import HEALTH_SUFFIX

from ._builders import (
    _work_stage,
    a_server_that_refuses_every_completion,
    captured_article_fetch,
    plan,
)
from .test_degrade import headless_page_fetch, headless_plan

LABEL_REPLY: Final = FIXTURES_DIR / "completions" / "label" / "labelled.json"

SUMMARIZE_AND_PLAN_REPLY: Final = (
    FIXTURES_DIR / "completions" / "summarize-and-plan" / "summary-and-plan.json"
)


def worked(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    degraded: bool = False,
    server_pid: int | None = None,
) -> tuple[RunPlan, Path]:
    """One real work stage, and the items directory it wrote."""
    run_plan, items_dir, _ = _work_stage(
        tmp_path,
        monkeypatch,
        replies=(LABEL_REPLY.read_bytes(), SUMMARIZE_AND_PLAN_REPLY.read_bytes()),
        fetcher=headless_page_fetch if degraded else captured_article_fetch,
        run_plan=headless_plan() if degraded else None,
        server_pid=server_pid,
    )
    assert run_plan.items, "an empty plan would exercise no item recording"
    return run_plan, items_dir


def rows(items_dir: Path) -> dict[str, ItemHealthRow]:
    """Every persisted census row, by the item it describes.

    Read inside the test rather than at module scope, so an unexpected shape
    fails the test that wanted it instead of the whole file (CLAUDE.md section
    13).
    """
    return {
        path.name.removesuffix(HEALTH_SUFFIX): ItemHealthRow.from_json(read_text(path))
        for path in sorted(items_dir.glob(f"*{HEALTH_SUFFIX}"))
    }


def closed(caplog: LogCaptureFixture) -> list[dict[str, Any]]:
    """Every `item.done` record the run emitted, parsed.

    Flat records are one JSON object with no `ctx`, so the nested events sharing
    this logger are dropped by shape rather than by name.
    """
    found: list[dict[str, Any]] = []
    for line in caplog.messages:
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if "ctx" not in payload and payload.get("name") == "item.done":
            found.append(payload)
    return found


def test_every_item_the_shard_closed_left_its_row_on_disk(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """One row an item, and no row for an item the plan never named.

    The bijection is the assertion. A file for only some planned items is a shard
    that measured an item and dropped it, which is the defect this payload
    exists to end, and an extra file is a row about an item nobody planned.
    """
    run_plan, items_dir = worked(tmp_path, monkeypatch)

    assert set(rows(items_dir)) == {item.item_id for item in run_plan.items}


def test_the_file_is_the_row_the_shard_reported_cell_for_cell(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """The log and the file have to be one reading, not two.

    The log line is the only account of a shard that anybody trusted before this
    payload existed. If the two ever disagree, a reader has no way to tell which
    one measured the item - so the test compares all 119 cells rather than the
    handful a caller happens to use.
    """
    caplog.set_level(logging.INFO, logger="idhazh")
    run_plan, items_dir = worked(tmp_path, monkeypatch)

    written = rows(items_dir)
    reported = closed(caplog)

    assert len(reported) == len(run_plan.items)
    assert {record["item_id"] for record in reported} == set(written) == {
        item.item_id for item in run_plan.items
    }
    for record in reported:
        said = ItemHealthRow.model_validate(
            {column: record[column] for column in ItemHealthRow.csv_columns()}
        )
        assert json.loads(written[said.item_id].to_json()) == json.loads(said.to_json())


#: Every host cell the sampler names, in the order the item-health doc lists
#: them. Named once so a column added to the sampler moves one line here.
HOST_COLUMNS: Final = (
    "cpu_model",
    "cpu_busy_pct",
    "cpu_busy_max",
    "cpu_busy_min",
    "cpu_steal_pct",
    "load_1m",
    "llama_rss_bytes",
    "llama_rss_anon_bytes",
    "llama_rss_peak_bytes",
    "llama_major_faults",
    "python_rss_bytes",
    "python_rss_anon_bytes",
    "os_mem_available_bytes",
    "os_mem_total_bytes",
    "os_mem_cached_bytes",
    "os_swap_free_bytes",
    "os_swap_total_bytes",
    "os_mem_available_min_bytes",
)


def a_machine_that_answers(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """A `/proc` this test writes, so every host cell fills.

    Nothing here reads the box the suite runs on. None of these paths exists on a
    developer machine, so a test that asked the real host would record every host
    cell empty locally and every one full in CI - which is a test that passes or
    fails on the weather (CLAUDE.md section 13).

    The processor counters climb between reads, because a busy share is the
    difference of two of them and two identical reads are no window at all.
    """
    table = tmp_path / "proc"
    for pid, comm in (("1", "systemd"), ("742", "llama-server")):
        (table / pid).mkdir(parents=True)
        (table / pid / "comm").write_text(f"{comm}\n", encoding="utf-8")
    ticks = count(start=100, step=200)
    spent = count(start=0, step=1000)
    faulted = count(start=7, step=3)

    def built(path: Path) -> str | None:
        if path == host.PROC_STAT:
            moment = next(ticks)
            # A stolen share that climbs with the rest, so the steal cell proves
            # a reading travelled rather than proving a zero appeared.
            return f"cpu  {moment} 0 {moment} {moment * 4} 0 0 0 {moment // 10} 0 0\n"
        if path == host.LOADAVG:
            return "1.53 1.20 0.91 2/312 9931\n"
        if path == host.MEMINFO:
            # Falling headroom, so the floor cell has something below its last
            # reading to find. A runner reports these in kilobytes.
            return (
                "MemTotal:       16373964 kB\n"
                f"MemAvailable:    {9_000_000 - next(spent)} kB\n"
                "Cached:          6100000 kB\n"
                "SwapTotal:       4194300 kB\n"
                "SwapFree:        4194300 kB\n"
            )
        if path.name == "status":
            return "VmRSS:\t 4194304 kB\nVmHWM:\t 5242880 kB\nRssAnon:\t 1048576 kB\n"
        if path.name == "stat":
            # A counter that climbs, so the item's total is a real difference
            # rather than two reads of one number. `majflt` is the tenth cell
            # after the bracketed command.
            return (
                f"742 (llama-server) S 1 742 742 0 -1 0 900 0 {next(faulted)} 0 "
                "0 0 0 0 20 0 1 0 12345\n"
            )
        if path.name == "comm":
            return path.read_text(encoding="utf-8")
        return None

    monkeypatch.setattr(host, "PROC", table)
    monkeypatch.setattr(host, "_text", built)
    monkeypatch.setenv("RUNNER_NAME", "ubuntu-4core-3")


def test_every_host_column_reaches_the_row_the_shard_left_behind(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Eighteen columns that were computed and discarded now outlive the process.

    A throughput number with no machine beside it is not a measurement
    (Guardrail #10), and until the work stage recorded these, whether a slow item
    met a noisy neighbour was unanswerable. The assertion is per item rather than
    per shard, because the shard's average says nothing about the item that was
    slow - which is the entire question these columns exist to answer.
    """
    a_machine_that_answers(monkeypatch, tmp_path / "host")
    _, items_dir = worked(tmp_path, monkeypatch, server_pid=742)

    written = rows(items_dir)

    assert written, "no rows means the loop below asserts nothing"
    for item_id, row in written.items():
        filled = {column for column in HOST_COLUMNS if getattr(row, column) is not None}
        assert filled == set(HOST_COLUMNS), f"{item_id} lost {set(HOST_COLUMNS) - filled}"


def test_the_shard_names_one_machine_on_every_row_it_records(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """One `host_facts` call a shard, so two items cannot name two processors.

    The processor cannot change inside a shard, so every row a shard records has
    to name the same one. A second reading per item would open `/proc/cpuinfo`
    again for an answer already taken, and two readings are two answers nobody
    can reconcile.
    """
    a_machine_that_answers(monkeypatch, tmp_path / "host")
    _, items_dir = worked(tmp_path, monkeypatch)

    written = rows(items_dir)

    assert len({row.cpu_model for row in written.values()}) == 1


def test_every_row_a_shard_seals_names_the_job_and_the_worker_that_read_it(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """`machine_job` and `machine_shard` together are the key to this machine's host record.

    A shard is not a key on its own: `plan`, `work` and `assemble` each draw a
    machine and each write shard 0, so three of the four columns resolve to
    three host records rather than one. The work stage is the only place that
    knows both, which is why this asserts on the rows it sealed rather than on
    the census that reads them later.
    """
    a_machine_that_answers(monkeypatch, tmp_path / "host")
    _, items_dir = worked(tmp_path, monkeypatch)

    written = rows(items_dir)

    assert written, "no rows means the loop below asserts nothing"
    assert {(row.machine_job, row.machine_shard) for row in written.values()} == {
        (ServerJob.WORK, 0)
    }


def test_a_headless_item_reaches_the_model_and_leaves_a_row(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An absent source headline is not an extraction failure."""
    run_plan, items_dir = worked(tmp_path, monkeypatch, degraded=True)

    written = rows(items_dir)

    assert set(written) == {item.item_id for item in run_plan.items}
    for planned in run_plan.items[:2]:
        row = written[planned.item_id]
        assert row.code is not FailureCode.NO_TITLE, planned.item_id
        assert row.label_ms is not None, planned.item_id
        assert row.summary_ms is not None, planned.item_id


def test_an_item_the_shard_abandoned_leaves_a_row_too(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An item that never ran is a measurement, and it is the only one there is.

    A shard that stops on its own clock appends nothing to the list it hands the
    slowest-item reading, deliberately - an item that never ran has no duration
    to be slowest. So this branch is the one place the payload cannot be written
    from the list of finished items, and the only proof it was written is a file
    for an item that produced nothing else.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    out_of_time = replace(
        settings,
        app=settings.app.model_copy(
            update={
                "run": settings.app.run.model_copy(
                    update={"shard_timeout_minutes": 1, "shard_wrap_up_minutes": 1}
                )
            }
        ),
    )
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan,
            settings=out_of_time,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )

    written = rows(tmp_path / "run" / run_plan.date / "items")

    assert set(written) == {item.item_id for item in run_plan.items}
    assert {row.code for row in written.values()} == {FailureCode.SHARD_OUT_OF_TIME}


def test_an_empty_shard_needs_no_controller_or_host_instrument(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture,
) -> None:
    settings = config.load(CONFIG_DIR)
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "python")
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    run_plan = RunPlan(
        version=RunPlan.schema_version(), date="2026-09-15",
        run_id="2026-09-15-1", generated_at="2026-09-15T06:00:00Z",
    )

    stage_work(run_plan, settings=settings, scorer=None, shard=1, shards=2)

    assert not (tmp_path / "run").exists()
    assert "model-server PID not supplied" not in caplog.text


@pytest.mark.parametrize("collection", ["on", "host-off", "memory-off", "no-pid"])
def test_controller_identity_reaches_process_fields_only_when_collection_is_enabled(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture, collection: str,
) -> None:
    from idhazh.contracts.base import derive_url_key
    from idhazh.contracts.feed_health import FetchOutcome
    from idhazh.fetch import FetchResult
    from idhazh.telemetry.record import HEALTH_SUFFIX

    from ._builders import isolate_ledgers

    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "off" if collection == "host-off" else "python")
    monkeypatch.setenv("MEMORY_PROFILING", "off" if collection == "memory-off" else "on")
    settings = config.load(CONFIG_DIR)
    settings.app.logging.waiting_heartbeat_seconds = 0
    isolate_ledgers(tmp_path, monkeypatch)
    proc = tmp_path / "proc"
    server = proc / "742"
    server.mkdir(parents=True)
    (server / "stat").write_text(
        "742 (recorded-server) S 1 742 742 0 -1 0 900 0 7 0 0 0 0 0 20 0 1 0 12345\n",
        encoding="ascii",
    )
    (server / "status").write_text(
        "VmRSS: 4096 kB\nVmHWM: 8192 kB\nRssAnon: 2048 kB\n", encoding="ascii",
    )
    monkeypatch.setattr(host, "PROC", proc)
    for name, filename in (("PROC_STAT", "stat"), ("MEMINFO", "meminfo"), ("LOADAVG", "loadavg")):
        monkeypatch.setattr(host, name, proc / filename)
    url = "https://example.com/report"
    run_plan = RunPlan.model_validate({
        "version": RunPlan.schema_version(), "date": "2026-09-15", "run_id": "2026-09-15-1",
        "generated_at": "2026-09-15T06:00:00Z",
        "verticals": [{"id": "ai", "considered": 1, "planned": 1, "eligible_feeds": 1}],
        "items": [{
            "item_id": "ai-01", "url_key": derive_url_key(url), "source_url": url,
            "canonical_url": url, "source_id": "example", "tier": 1, "vertical": "ai",
            "title": "A school publishes its building schedule", "rank_score": 1,
        }],
    })
    paragraphs = (
        "The school published a building schedule on Monday after a public meeting. "
        "Construction will begin in January and finish before the next academic year. "
        "The council said the work would replace classrooms and repair the library.",
        "Residents asked for regular updates on spending and safety. The school agreed "
        "to publish monthly reports naming completed work and any delays. Teachers "
        "will use a nearby building while the repairs continue.",
        "The project includes new heating equipment and wider entrances. Engineers "
        "will check the foundations before the first rooms are closed. The school "
        "said no lessons would be cancelled during the first phase.",
    )
    html = (
        "<html><head><title>A school publishes its building schedule</title></head>"
        "<body><article><h1>A school publishes its building schedule</h1>"
        + "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
        + "</article></body></html>"
    ).encode("ascii")

    def fetch_article(_url: str) -> FetchResult:
        return FetchResult(FetchOutcome.OK, status=200, body=html)

    with a_server_that_refuses_every_completion() as endpoint:
        stage_work(
            run_plan, settings=settings, scorer=None, fetcher=fetch_article,
            model_endpoint=endpoint.endpoint, server_pid=None if collection == "no-pid" else 742,
        )

    path = tmp_path / "run" / run_plan.date / "items" / f"ai-01{HEALTH_SUFFIX}"
    row = ItemHealthRow.from_json(path.read_text(encoding="ascii"))
    assert row.summarize_ms is not None, "the item must reach the process-scoped work window"
    actual = (row.llama_rss_bytes, row.llama_rss_anon_bytes, row.llama_rss_peak_bytes, row.llama_major_faults)
    assert actual == ((4096 * 1024, 2048 * 1024, 8192 * 1024, 0) if collection == "on" else (None,) * 4)
    assert ("model-server PID not supplied" in caplog.text) is (collection == "no-pid")
