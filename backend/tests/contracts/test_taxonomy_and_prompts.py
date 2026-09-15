"""Is a definition config, and does editing one move the prompt and nothing else?"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.item_health import (
    FAILURE_CODE_STAGES,
    SOURCE_NEUTRAL_FAILURE_CODES,
    TERMINAL_STAGES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.runtime_counters import SERIES, WORK_JOB, RuntimeCountersRow
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.publish_telemetry import PUBLIC_COLUMNS

from ._fixtures import (
    DOC_ITEM_HEALTH,
    DOC_ONE_URL,
    METRICS_CAPTURES,
    PROBE_PROCESSORS,
    PROBE_SECONDS,
    PROC_STAT_AT_END,
    PROC_STAT_AT_START,
    RSS_CAPTURES,
    SERVER_LOG_CAPTURES,
    USER_HZ,
    backticked,
    paragraph_after,
    taxonomy_fixture,
)

pytestmark = pytest.mark.contract


def json_leaves(payload: object, path: str = "") -> dict[str, object]:
    """Every scalar in a payload, addressed, so two payloads can be diffed leaf by leaf."""
    if isinstance(payload, dict):
        return {
            address: leaf
            for key, value in payload.items()
            for address, leaf in json_leaves(value, f"{path}/{key}").items()
        }
    if isinstance(payload, list):
        return {
            address: leaf
            for index, value in enumerate(payload)
            for address, leaf in json_leaves(value, f"{path}[{index}]").items()
        }
    return {path: payload}


def test_editing_one_definition_moves_the_prompt_and_nothing_else() -> None:
    """Change a sentence in the vocabulary file and the model is asked a different question.

    `definitions-a.json` and `definitions-b.json` are the same vocabulary with
    one lens's definition rewritten - proved here rather than promised, by
    walking both payloads and requiring exactly one leaf to differ. Both are
    written through the contract the committed schema is generated from, so
    parsing them is validating against it.

    A vocabulary that needs a code change to move its own definition is not
    config, whatever file it lives in. This test is what says so out loud: no
    Python is edited between the two arms and no schema is regenerated, and the
    block the labelling prompt is built from still moves.
    """
    a = taxonomy_fixture("definitions-a")
    b = taxonomy_fixture("definitions-b")

    left = json_leaves(json.loads(a.to_json()))
    right = json_leaves(json.loads(b.to_json()))
    assert set(left) == set(right), "the two fixtures are not the same vocabulary"
    differing = sorted(address for address in left if left[address] != right[address])
    assert differing == ["/lenses[0]/definition"], "the two fixtures differ somewhere else too"

    assert a.definition_block() != b.definition_block()
    assert a.definition_block().count("\n") == b.definition_block().count("\n")


def test_a_draft_or_retired_entry_reaches_no_prompt() -> None:
    """`status` is a control, not a convention, and the block's bytes are the proof.

    `definitions-a.json` carries a draft vertical a model proposed and a retired
    lens kept as a tombstone. Neither may contribute a byte: a draft is a word
    nobody has approved, and a tombstone is there so a day already carrying it
    still renders. So writing a sentence onto both and re-reading the block has
    to produce the same string, which is the assertion a filter that forgets one
    call site fails and prose cannot catch.
    """
    offered = taxonomy_fixture("definitions-a")
    payload = json.loads(offered.to_json())
    for entry in [*payload["verticals"], *payload["lenses"]]:
        if entry["status"] != LifecycleStatus.ACTIVE.value:
            entry["definition"] = "a sentence no prompt may carry"

    assert Taxonomy.model_validate(payload).definition_block() == offered.definition_block()
    assert "proposed-desk" not in offered.definition_block()
    assert "ai-roi" not in offered.definition_block()


def test_every_offered_entry_of_the_committed_vocabulary_carries_its_sentence() -> None:
    """The rule the contract enforces, held against the file a run really reads.

    An id and a display name tell a model nothing, so a word offered with no
    sentence beside it is a word it cannot read. The committed config is the one
    that decides a run, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    block = taxonomy.definition_block()
    offered = [
        *(
            (item.id, item.definition)
            for item in taxonomy.verticals
            if item.status is LifecycleStatus.ACTIVE
        ),
        *(
            (item.id, item.definition)
            for item in taxonomy.lenses
            if item.status is LifecycleStatus.ACTIVE
        ),
        *(
            (item.id, item.definition)
            for item in taxonomy.events
            if item.status is LifecycleStatus.ACTIVE
        ),
    ]
    for entry_id, definition in offered:
        assert definition, f"{entry_id} is offered to the model with no definition"
        assert definition in block


def test_the_frontend_names_every_committed_lens_including_a_tombstone() -> None:
    """The page's own copy of the lens display names, held against the config.

    `frontend/src/lib/payload/lenses.ts` restates them because it is TypeScript
    and the vocabulary is JSON, and it holds them rather than taking them
    through `data` so the names are not repeated inside every prerendered day
    page. Drift either way is a defect a build never catches.

    **Every** committed lens, retired ones included, and that is the half that
    changed on 2026-09-12. Omitting a tombstone did not keep it off the page so
    much as make the page stop saying what a frozen day said: `ai-roi` was
    retired on 2026-08-30 and is carried by 18 committed items, and all 18
    rendered one chip fewer than their payload held. A retired lens keeps its
    name here; deleting the entry from config is what takes the name away, and
    the page then falls back to the raw id rather than to silence.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "lenses.ts")
    declared = re.search(r"LENS_NAMES: Readonly<Record<string, string>> = \{(.*?)\};", source, re.DOTALL)
    assert declared is not None, "lenses.ts no longer declares LENS_NAMES"
    named = dict(re.findall(r"'?([a-z0-9-]+)'?: '([^']+)'", declared.group(1)))
    committed = {lens.id: lens.display_name for lens in taxonomy.lenses}
    assert named == committed, "the page and config/taxonomy.json disagree about the lens names"


def test_the_console_reads_a_prefix_of_the_published_telemetry_columns() -> None:
    """The browser's copy of the projection header, held against the writer.

    `frontend/src/lib/charts/series.ts` restates `PUBLIC_COLUMNS` because it is
    TypeScript and the writer is Python, and its header check reads a prefix on
    purpose - a browser holding a cached bundle keeps working when a column is
    appended. So this test allows an append and refuses an insert, a rename or a
    reorder at any position the browser reads, and refuses a name the writer
    never writes. Nothing else ties the two lists together.
    """
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "charts" / "series.ts")
    declared = re.search(
        r"export const TELEMETRY_COLUMNS = \[(.*?)\] as const;", source, re.DOTALL
    )
    assert declared is not None, "series.ts no longer declares a TELEMETRY_COLUMNS array"
    names = tuple(re.findall(r"'([^']+)'", declared.group(1)))
    assert names, "TELEMETRY_COLUMNS matched but held no column names"
    assert names == PUBLIC_COLUMNS[: len(names)], (
        "series.ts and publish_telemetry.py disagree about the telemetry header: "
        f"the console reads {list(names)}, the writer writes "
        f"{list(PUBLIC_COLUMNS[: len(names)])} in those positions"
    )


def test_the_console_fallback_bands_match_the_committed_ladder() -> None:
    """The console's fallback length ladder, held against the file it stands in for.

    `summarizeConfig()` in `frontend/src/lib/server/config.ts` returns
    `SUMMARIZE_DEFAULTS` when `config/idhazh.json` cannot be read, and those
    bands draw the compression plot's target zone and set its y axis. A stale
    copy draws a wrong chart and says nothing, so the copy is pinned here.
    """
    committed: list[dict[str, int]] = json.loads(read_text(CONFIG_DIR / "idhazh.json"))[
        "summarize"
    ]["bands"]
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    declared = re.search(
        r"const SUMMARIZE_DEFAULTS: SummarizeConfig = \{\s*bands: \[(.*?)\]\s*\};",
        source,
        re.DOTALL,
    )
    assert declared is not None, "config.ts no longer declares a SUMMARIZE_DEFAULTS ladder"
    fallback = [
        {name: int(value) for name, value in re.findall(r"(\w+): (\d+)", band)}
        for band in re.findall(r"\{([^{}]*)\}", declared.group(1))
    ]
    assert fallback, "SUMMARIZE_DEFAULTS matched but held no bands"
    keys = (
        "min_source_words",
        "target_words_min",
        "target_words_max",
        "key_points_min",
        "key_points_max",
    )
    expected = [{key: band[key] for key in keys} for band in committed]
    assert fallback == expected, (
        "config.ts and config/idhazh.json disagree about the summary bands: "
        f"the console falls back to {fallback}, the committed ladder is {expected}"
    )


def test_recorded_item_health_codes_never_count_against_a_source() -> None:
    assert len(SOURCE_NEUTRAL_FAILURE_CODES) == 17
    assert FailureCode.NOT_ATTEMPTED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_UNREACHABLE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_REFUSED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.NOT_PROSE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.BOILERPLATE in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.HTTP_CLIENT_ERROR not in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_is_the_models_fault_and_never_the_feeds(code: FailureCode) -> None:
    """A wire service publishing short briefs must not be quarantined for our model.

    `collect.availability_strikes_before_rest` is 5, so leaving either code out
    of the source-neutral set would take a working feed off the list on the fifth
    copy.
    """
    assert FAILURE_CODE_STAGES[code] == frozenset({ItemStage.SUMMARIZE})
    assert code in SOURCE_NEUTRAL_FAILURE_CODES


@pytest.mark.parametrize(
    "code", [FailureCode.COPIED_SOURCE, FailureCode.LEAKED_ADDRESS], ids=lambda c: c.value
)
def test_a_refused_reply_survives_the_ledger_round_trip(code: FailureCode) -> None:
    """The census row is the only durable record of a dropped item, so it must read back."""
    published = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    row = published.model_copy(
        update={
            "stage": ItemStage.SUMMARIZE,
            "outcome": ItemOutcome.FAILED,
            "code": code,
            "summary_words": 44,
        }
    )

    restored = ItemHealthRow.from_csv_row(row.csv_row())
    assert restored.code is code
    assert restored.summary_words == 44
    assert restored.counts_against_source is False
    assert restored == row


def test_a_prompt_that_did_not_fit_is_our_budget_and_not_the_sources_fault() -> None:
    """The article was long. The context window and the truncation cap are ours."""
    assert FailureCode.CONTEXT_EXCEEDED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FAILURE_CODE_STAGES[FailureCode.CONTEXT_EXCEEDED] == frozenset({ItemStage.SUMMARIZE})


def test_an_item_health_row_written_before_the_context_code_still_reads() -> None:
    """Section 11's release blocker for an additive enum member.

    A row this month's ledger already holds carries the previous schema stamp
    and a code minted before today. It must still load, and it must still read
    as source-neutral, or a committed ledger stops parsing on the day the
    vocabulary grows.
    """
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "summarize-model-unreachable.json")
    )

    assert row.version == "2026-08-24T18:30"
    assert row.version != ItemHealthRow.schema_version()
    assert row.code is FailureCode.MODEL_UNREACHABLE
    assert row.counts_against_source is False
    assert ItemHealthRow.from_csv_row(row.csv_row()) == row


def test_item_health_csv_round_trip_uses_empty_cells_for_absent_values() -> None:
    row = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    )
    cells = row.csv_row()
    assert cells["code"] == ""
    assert cells["http_status"] == ""
    assert ItemHealthRow.from_csv_row(cells) == row


def test_no_failure_code_admits_a_stage_an_item_cannot_stop_at() -> None:
    """A code's stage set is the gate a new stage name has to get past.

    `unknown` mapped to `frozenset(ItemStage)`, so any name added to the enum for
    any reason became a legal census row the day it was declared - one line, and
    the only one, between a stage vocabulary and a ledger that accepts it.
    `ItemStage` is also the type of `telemetry.event(src=...)` and of
    `DayStageTiming.stage`, and neither of those means an ending, so names that
    no row may carry now exist and this is what keeps them out.
    """
    for code, stages in FAILURE_CODE_STAGES.items():
        assert stages <= TERMINAL_STAGES, f"{code.value} admits a stage no item stops at"


@pytest.mark.parametrize("stage", sorted(set(ItemStage) - TERMINAL_STAGES))
def test_the_census_refuses_a_stage_an_item_cannot_stop_at(stage: ItemStage) -> None:
    """`stage` answers where the item STOPPED, so a step it passed through is a lie.

    An item whose picture failed still reaches the digest. A `visual` row here
    would say it did not, and would take one off the `publish` count that
    `publish_day_metrics` and the console read off this same file.

    Parametrized over whatever is not terminal rather than over `visual`, so the
    next stage name added for a log line or a clock arrives here already asked
    the question instead of arriving unnoticed.
    """
    payload = ItemHealthRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json")
    ).model_dump(mode="json")
    payload["stage"] = stage.value

    with pytest.raises(ValidationError, match="where an item stopped"):
        ItemHealthRow.model_validate(payload)


def test_the_pages_that_name_the_summarize_codes_still_agree_with_the_enum() -> None:
    """Two pages enumerate the summarize codes by hand, and neither is generated.

    `copied_source` and `leaked_address` were minted on 2026-08-27 and both pages
    kept the old list for a day, so each one asserted a vocabulary the code had
    already outgrown. `unknown` is excluded because it belongs to every stage and
    `to_summary` never returns it.
    """
    summarize_only = {
        code.value
        for code, stages in FAILURE_CODE_STAGES.items()
        if stages == frozenset({ItemStage.SUMMARIZE})
    }

    tabled = re.findall(r"^\| `summarize` \|(.+)\|$", read_text(DOC_ITEM_HEALTH), re.MULTILINE)
    assert len(tabled) == 1, "the item-health stage table no longer has one summarize row"
    assert backticked(tabled[0]) == summarize_only

    listed = re.findall(r"^\| Summary `([a-z_]+)`", read_text(DOC_ONE_URL), re.MULTILINE)
    assert set(listed) == summarize_only
    assert len(listed) == len(summarize_only), "the one-URL page lists a code twice"


def test_the_item_health_page_splits_the_codes_the_way_the_contract_does() -> None:
    """The source-neutral split is a promise about which feed gets quarantined."""
    text = read_text(DOC_ITEM_HEALTH)
    neutral = {code.value for code in SOURCE_NEUTRAL_FAILURE_CODES}

    assert backticked(paragraph_after(text, "never count against a source:")) == neutral
    assert backticked(paragraph_after(text, "can count against the source:")) == {
        code.value for code in FailureCode
    } - neutral


def test_the_runtime_counters_columns_are_defined_once() -> None:
    assert RuntimeCountersRow.csv_columns() == (
        "version",
        "date",
        "run_id",
        "shard",
        "shards",
        "scraped_at",
        "prompt_tokens_total",
        "prompt_tokens_cached_total",
        "prompt_seconds_total",
        "tokens_predicted_total",
        "tokens_predicted_seconds_total",
        "n_decode_total",
        "n_tokens_max",
        "n_busy_slots_per_decode",
        "job_seconds",
        "cpu_model",
        "cpu_busy_pct",
        "peak_rss_bytes",
        "model_load_ms",
        "n_ctx_configured",
        "python_peak_rss_bytes",
        "cgroup_peak_bytes",
        "job",
    )


@pytest.mark.parametrize("path", METRICS_CAPTURES, ids=lambda p: p.stem)
def test_the_server_agrees_with_itself_about_what_a_prompt_token_is(path: Path) -> None:
    """The Oracle for the definition: the server's own rate over its own counters.

    llama-server publishes `prompt_tokens_seconds` as well as the two counters it
    is made of. If `prompt_tokens_total` counted cached tokens too, the published
    gauge and the counters would disagree - so this reproduces the gauge from the
    counters and proves the field means what the row says it means: prompt tokens
    the model actually read, which is the ledger's `input_tokens - cached_tokens`.
    """
    text = read_text(path)
    row = RuntimeCountersRow.from_metrics_text(
        text,
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=int(path.stem[-1]),
        shards=len(METRICS_CAPTURES),
        scraped_at="2026-08-26T21:12:05Z",
    )
    published = {
        line.split(" ")[0]: float(line.split(" ")[1])
        for line in text.splitlines()
        if line.startswith("llamacpp:")
    }

    assert row.prompt_tokens_total is not None
    assert row.prompt_seconds_total is not None
    reproduced = row.prompt_tokens_total / row.prompt_seconds_total
    # The gauge is printed to six significant figures, so the comparison is too.
    assert reproduced == pytest.approx(published["llamacpp:prompt_tokens_seconds"], rel=1e-5)
    assert row.prompt_tokens_cached_total is not None
    assert row.prompt_tokens_cached_total > 0, "a capture with no cache hits proves nothing here"


def test_a_series_this_build_does_not_publish_is_null_and_never_zero() -> None:
    """A rename has to look like a missing column, not like a server that read nothing."""
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
    )
    for field in SERIES.values():
        assert getattr(row, field) is None
    cells = row.csv_row()
    assert all(cells[field] == "" for field in SERIES.values())
    assert RuntimeCountersRow.from_csv_row(cells) == row


def test_a_count_that_stops_being_whole_raises_instead_of_truncating() -> None:
    """A silently truncated counter is a wrong number that nothing can spot later."""
    with pytest.raises(ValueError, match="prompt_tokens_total"):
        RuntimeCountersRow.from_metrics_text(
            "llamacpp:prompt_tokens_total 23411.5\n",
            date="2026-08-26",
            run_id="2026-08-26-5",
            shard=0,
            shards=4,
            scraped_at="2026-08-26T21:32:30Z",
        )


def test_a_shard_index_must_sit_inside_the_run_it_names() -> None:
    with pytest.raises(ValueError, match="below the shard count"):
        RuntimeCountersRow.model_validate(
            {
                "date": "2026-08-26",
                "run_id": "2026-08-26-5",
                "shard": 4,
                "shards": 4,
                "scraped_at": "2026-08-26T21:32:30Z",
            }
        )


def test_the_shard_clock_is_measured_against_the_scrape_that_carries_it() -> None:
    """The rollback trigger reads this cell, so it may not be a second opinion.

    `job_seconds` and `scraped_at` describe the same instant from two ends. The
    row works the difference out for itself rather than taking a caller's
    arithmetic, so the two cells cannot end up saying different things about one
    scrape.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
        # 2026-08-26T20:00:00Z, an hour and 32.5 minutes before the scrape.
        job_started_at=1787774400,
        cpu_model="  AMD EPYC 7763 64-Core Processor  ",
    )

    assert row.job_seconds == 5550
    assert row.cpu_model == "AMD EPYC 7763 64-Core Processor"
    assert RuntimeCountersRow.from_csv_row(row.csv_row()) == row


def test_a_shard_with_no_stamp_and_no_host_reports_absence_not_zero() -> None:
    """A job whose stamp went missing and a job that took no time are not one fact.

    The stamp comes from a workflow step, and a stage that runs anywhere else -
    a developer machine, a re-run of one shard - has neither it nor
    `/proc/cpuinfo`. Both cells stay empty there, and an empty cell reads back as
    absent (`job_seconds is None`) rather than as `0`.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-26",
        run_id="2026-08-26-5",
        shard=0,
        shards=4,
        scraped_at="2026-08-26T21:32:30Z",
        cpu_model="",
    )
    cells = row.csv_row()

    assert row.job_seconds is None
    assert row.cpu_model is None
    assert cells["job_seconds"] == ""
    assert cells["cpu_model"] == ""
    assert RuntimeCountersRow.from_csv_row(cells) == row


def _aggregate_cpu_line(text: str) -> list[int]:
    """The ten counters on the one `cpu ` line of a /proc/stat capture."""
    aggregate = [line for line in text.splitlines() if line.split()[:1] == ["cpu"]]
    assert len(aggregate) == 1, "a /proc/stat capture has exactly one aggregate cpu line"
    return [int(cell) for cell in aggregate[0].split()[1:]]


def test_every_runtime_capture_an_oracle_reads_is_committed() -> None:
    """A parametrized oracle over an empty glob is green and proves nothing.

    `.gitignore` carries `*.log`, so the first spelling of the server-log
    capture was ignored the moment it was named after the file it came from -
    and the test over it collected zero cases without saying so.
    """
    assert len(METRICS_CAPTURES) == 4
    assert len(RSS_CAPTURES) == 4
    assert len(SERVER_LOG_CAPTURES) == 4
    for path in (PROC_STAT_AT_START, PROC_STAT_AT_END):
        assert path.is_file(), path.name


def test_the_processor_busy_share_is_read_from_a_real_proc_stat_pair() -> None:
    """The Oracle for `cpu_busy_pct`: the capture proves its own window.

    Twenty seconds of four processors at 100 Hz is 8,000 ticks. A real pair
    reproduces that, and a hand-written pair only does so by arithmetic somebody
    already did - which is the same arithmetic under test. The busy share itself
    is worked out here from the raw text, field by field, so this cannot pass by
    agreeing with the contract about a mistake.

    The reading is near zero because the probe slept through its own window. The
    shape is what is under test; the expected value on a work shard is near 100.
    """
    at_start = read_text(PROC_STAT_AT_START)
    at_end = read_text(PROC_STAT_AT_END)
    start = _aggregate_cpu_line(at_start)
    end = _aggregate_cpu_line(at_end)
    # guest sits inside user and guest_nice inside nice, so a plain sum of the
    # line counts both twice. idle and iowait are the processors standing free.
    available = (sum(end) - end[8] - end[9]) - (sum(start) - start[8] - start[9])
    idle = (end[3] + end[4]) - (start[3] + start[4])

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-30",
        run_id="2026-08-30-1",
        shard=0,
        shards=4,
        scraped_at="2026-08-30T02:45:02Z",
        cpu_stat_at_start=at_start,
        cpu_stat_at_end=at_end,
    )

    assert available == pytest.approx(PROBE_SECONDS * PROBE_PROCESSORS * USER_HZ, rel=0.01)
    assert row.cpu_busy_pct == pytest.approx(100 * (available - idle) / available, abs=0.005)
    assert RuntimeCountersRow.from_csv_row(row.csv_row()) == row


@pytest.mark.parametrize("path", RSS_CAPTURES, ids=lambda p: p.name)
def test_the_memory_high_point_is_the_highest_the_sampler_saw(path: Path) -> None:
    """The Oracle for `peak_rss_bytes`: the column is found by name, in bytes.

    `VmHWM` is a high-water mark, so the last sample carries the whole life of
    the process - but a sample can come back blank, and a column can move. The
    expected value is worked out here off the sampler's own header rather than
    off a position, which is the failure this would otherwise hide.
    """
    text = read_text(path)
    rows = [line.split("\t") for line in text.splitlines()]
    column = rows[0].index("llama_vmhwm_kb")
    peaks = [int(cells[column]) for cells in rows[1:] if cells[column].strip().isdigit()]

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(RSS_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        rss_samples=text,
    )

    assert row.peak_rss_bytes == max(peaks) * 1024
    # The unit is what a wrong answer gets wrong. A 9B at `n_ctx` 8192 holds
    # gigabytes, so kilobytes read as bytes would land a thousandfold low.
    assert row.peak_rss_bytes > 8 * 1024**3


@pytest.mark.parametrize("path", SERVER_LOG_CAPTURES, ids=lambda p: p.name)
def test_the_model_load_time_is_the_gap_between_the_servers_own_two_lines(path: Path) -> None:
    """The Oracle for `model_load_ms`: llama.cpp's stamp decoded from a real job.

    The stamp is four dot-separated numbers and no page says what they are. The
    third field reaches 809 on a real line, so it cannot be seconds-in-a-minute;
    the last field steps by 15 between two lines printed back to back, and the
    first field of the last line of a 99-minute job reads 99. That fixes it as
    minutes, seconds, milliseconds, microseconds - and only a capture of a job
    whose length is known settles it.
    """
    text = read_text(path)
    stamps: dict[str, int] = {}
    for line in text.splitlines():
        for marker in ("load_model: loading model", "llama_server: model loaded"):
            if marker in line and marker not in stamps:
                minutes, seconds, milli, micro = (int(p) for p in line.split(" ")[0].split("."))
                stamps[marker] = (((minutes * 60) + seconds) * 1000 + milli) * 1000 + micro
    assert len(stamps) == 2, f"{path.name} does not bracket a model load"

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(SERVER_LOG_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        server_log=text,
    )

    expected = stamps["llama_server: model loaded"] - stamps["load_model: loading model"]
    assert row.model_load_ms == expected / 1000
    # Seconds, not minutes and not microseconds. A unit slip is the one mistake
    # a gap between two stamps can make and still look plausible.
    assert 1000 < row.model_load_ms < 60_000


@pytest.mark.parametrize("path", SERVER_LOG_CAPTURES, ids=lambda p: p.name)
def test_the_window_that_produced_the_memory_figure_is_read_off_the_servers_own_line(
    path: Path,
) -> None:
    """The Oracle for `n_ctx_configured`: what a sequence got, not what the argv asked for.

    `--ctx-size` is the request. This is the window one sequence actually
    received, and the two differ whenever `kv_unified` is off and the server runs
    more than one slot - so only the server's own line settles it. The expected
    value is cut out of the capture here rather than written down, which is what
    stops this passing by agreeing with the contract about a mistake.
    """
    text = read_text(path)
    printed = [line for line in text.splitlines() if "load_model: initializing" in line]
    assert len(printed) == 1, f"{path.name} does not print the initializing line exactly once"
    expected = int(printed[0].split("n_ctx_slot = ")[1].split(",")[0])

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(SERVER_LOG_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        server_log=text,
    )

    assert row.n_ctx_configured == expected
    # The window run 2026-08-29-3 actually ran under. These captures are frozen,
    # so this does not move when the configured window does - it is here to say
    # which window the memory figures of that run belong to, because a later run
    # on a different window is not comparable with them.
    assert expected == 8192


@pytest.mark.parametrize("path", RSS_CAPTURES, ids=lambda p: p.name)
def test_the_python_high_water_mark_is_absent_from_a_capture_taken_before_it_existed(
    path: Path,
) -> None:
    """A column the sampler never took reads as unknown, never as a job with no python in it.

    These four captures are from 2026-08-29 and the sampler began writing
    `python_vmhwm_kb` on 2026-09-08, so the assertion is about the DATA rather
    than about the column list - which is the failure a widening usually hides.
    """
    text = read_text(path)
    assert "python_vmhwm_kb" not in text.splitlines()[0].split("\t")

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=int(path.name.split("shard-")[1][0]),
        shards=len(RSS_CAPTURES),
        scraped_at="2026-08-29T23:15:35Z",
        rss_samples=text,
    )

    assert row.python_peak_rss_bytes is None
    # Its sibling in the same file still reads, so this is one missing column and
    # not an unreadable capture.
    assert row.peak_rss_bytes is not None


def test_the_python_high_water_mark_is_the_highest_the_sampler_saw() -> None:
    """The Oracle for `python_peak_rss_bytes`, over the shape the sampler writes from today.

    Built rather than captured, for the reason `CLAUDE.md` section 13 allows one:
    `/proc` exists on the runner and on no machine this project is written on,
    and the column dates from this commit, so no capture carries it. What is
    built is the awkward case a capture may never produce - the peak arriving in
    the middle rather than last, one sample the sampler could not read at all,
    and the new column written to the RIGHT of `python_procs`, which is where
    appending puts it.
    """
    text = "\n".join(
        (
            "ts\tllama_vmrss_kb\tllama_vmhwm_kb\tpython_vmrss_kb\tpython_procs\tpython_vmhwm_kb",
            "2026-09-08T00:00:00Z\t8000000\t8000000\t900000\t2\t900000",
            "2026-09-08T00:00:15Z\t9000000\t9000000\t1700000\t4\t1800000",
            "2026-09-08T00:00:30Z\t9000000\t9000000\t\t0\t",
            "2026-09-08T00:00:45Z\t9500000\t9500000\t400000\t1\t1200000",
        )
    )

    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-09-08",
        run_id="2026-09-08-1",
        shard=0,
        shards=4,
        scraped_at="2026-09-08T00:01:00Z",
        rss_samples=text,
    )

    assert row.python_peak_rss_bytes == 1_800_000 * 1024
    # Both peaks are found by name, so two high-water columns in one file cannot
    # be swapped and the one that arrived last is still the one read.
    assert row.peak_rss_bytes == 9_500_000 * 1024


def test_the_cgroup_peak_reads_the_line_the_shard_job_writes_and_the_word_it_writes_instead() -> (
    None
):
    """The Oracle for `cgroup_peak_bytes`: its producer is a step in this repository.

    llama-server does not report this and no capture of it can, because the file
    is the kernel's. What can be checked is that the reader and the one step that
    writes the file agree about the line, and that the word that step writes when
    the kernel file is missing leaves the cell empty rather than raising.
    `/sys/fs/cgroup/memory.peak` has measured absent on a GitHub-hosted runner
    every time this project has looked, so `unavailable` is the arm to expect.
    """
    workflow = read_text(REPO_ROOT / ".github" / "workflows" / "digest.yml")
    assert "cgroup_memory_peak_bytes=$(cat /sys/fs/cgroup/memory.peak)" in workflow
    assert "cgroup_memory_peak_bytes=unavailable" in workflow

    def read(memory_peak: str) -> RuntimeCountersRow:
        return RuntimeCountersRow.from_metrics_text(
            "",
            date="2026-09-08",
            run_id="2026-09-08-1",
            shard=0,
            shards=4,
            scraped_at="2026-09-08T00:01:00Z",
            memory_peak=memory_peak,
        )

    assert read("cgroup_memory_peak_bytes=15032385536\n").cgroup_peak_bytes == 15032385536
    assert read("cgroup_memory_peak_bytes=unavailable\n").cgroup_peak_bytes is None
    assert read("").cgroup_peak_bytes is None


def test_widening_the_counters_ledger_costs_only_the_new_commas_and_the_new_names() -> None:
    """The Oracle for the widening: every old row re-reads, and the bytes account for themselves.

    Three rows built here rather than the 293 in `state/runtime-counters.csv`,
    which gains one per job per shard per run (Guardrail #12). What is under test is
    the arithmetic of an appended column, and three rows prove it exactly as 293
    do.

    A widening that MOVED a cell instead of appending one still parses, and every
    number would then be filed under the wrong name. The byte count is what
    catches that: an appended column costs one comma on every line, its own name
    once, and whatever each row writes into it - nothing at all for a cell a
    metrics body cannot fill, and four characters for `job`, which is defaulted
    rather than left empty.
    """
    added = ("n_ctx_configured", "python_peak_rss_bytes", "cgroup_peak_bytes", "job")
    columns = RuntimeCountersRow.csv_columns()
    assert columns[-len(added) :] == added, "a new column is appended, never inserted"
    narrow_columns = columns[: -len(added)]

    rows = [
        RuntimeCountersRow.from_metrics_text(
            read_text(path),
            date="2026-08-26",
            run_id="2026-08-26-5",
            shard=index,
            shards=len(METRICS_CAPTURES),
            scraped_at="2026-08-26T21:32:30Z",
        )
        for index, path in enumerate(METRICS_CAPTURES[:3])
    ]
    cells = [row.csv_row() for row in rows]
    # Splitting on a comma is only safe because no cell here holds one, which is
    # the same reason `cpu_model` is refused a newline.
    assert not any("," in value for row in cells for value in row.values())
    narrow = "".join(
        f"{','.join(line)}\n"
        for line in [narrow_columns, *([row[name] for name in narrow_columns] for row in cells)]
    )
    wide = "".join(
        f"{','.join(line)}\n"
        for line in [columns, *([row[name] for name in columns] for row in cells)]
    )

    expected_delta = (
        len(added) * len(narrow.splitlines())
        + sum(len(name) for name in added)
        + sum(len(row[name]) for row in cells for name in added)
    )
    assert len(wide.encode()) - len(narrow.encode()) == expected_delta

    for row, line in zip(rows, wide.splitlines()[1:], strict=True):
        widened = RuntimeCountersRow.from_csv_row(dict(zip(columns, line.split(","), strict=True)))
        assert widened == row
        assert widened.n_ctx_configured is None
        assert widened.python_peak_rss_bytes is None
        assert widened.cgroup_peak_bytes is None
        assert widened.job == WORK_JOB


def test_a_shard_whose_host_readings_never_arrived_reports_absence_not_zero() -> None:
    """A machine nobody read and a machine that did nothing are not one fact.

    The readings come from workflow steps and from files a job writes as it
    goes. A stage run anywhere else - a developer machine, a re-run of one shard
    whose first step never fired - has none of them, and one end of the
    processor window on its own says nothing either.
    """
    row = RuntimeCountersRow.from_metrics_text(
        "",
        date="2026-08-29",
        run_id="2026-08-29-3",
        shard=0,
        shards=4,
        scraped_at="2026-08-29T23:15:35Z",
        cpu_stat_at_start="",
        cpu_stat_at_end="cpu  2088 1 1373 304131 3508 0 30 0 0 0",
        rss_samples="",
        # The two lines under the markers llama.cpp uses today, renamed. A build
        # that renames one leaves the cell empty rather than reporting a load
        # that took no time.
        server_log="0.00.011.682 I srv    load_model: opening weights\n",
        memory_peak="cgroup_memory_peak_bytes=unavailable\n",
    )
    cells = row.csv_row()

    assert row.cpu_busy_pct is None
    assert row.peak_rss_bytes is None
    assert row.model_load_ms is None
    assert row.n_ctx_configured is None
    assert row.python_peak_rss_bytes is None
    assert row.cgroup_peak_bytes is None
    assert cells["cpu_busy_pct"] == ""
    assert cells["peak_rss_bytes"] == ""
    assert cells["model_load_ms"] == ""
    assert cells["n_ctx_configured"] == ""
    assert cells["python_peak_rss_bytes"] == ""
    assert cells["cgroup_peak_bytes"] == ""
    assert RuntimeCountersRow.from_csv_row(cells) == row


def test_a_host_name_that_could_split_a_row_is_folded_onto_one_line() -> None:
    """`state/runtime-counters.csv` merges with the union driver, which is line-based.

    Eight shards append to one branch, and the merge keeps lines rather than
    parsing CSV. A cell holding a newline would be quoted correctly by the writer
    and still split one row in two the first time two shards raced.

    The column refused such a value until 2026-09-15 and now folds it. Refusing
    kept the file safe by losing the row - a whole run's counters thrown away
    over a processor name nobody chose, read out of a kernel file. Folding keeps
    both: the row lands, and it is one physical line.
    """
    for hostile in ("AMD EPYC\n7763", "AMD EPYC\r7763"):
        row = RuntimeCountersRow.model_validate(
            {
                "date": "2026-08-26",
                "run_id": "2026-08-26-5",
                "shard": 0,
                "shards": 4,
                "scraped_at": "2026-08-26T21:32:30Z",
                "cpu_model": hostile,
            }
        )

        assert row.cpu_model == "AMD EPYC 7763"
        assert len(row.csv_row()["cpu_model"].splitlines()) == 1
