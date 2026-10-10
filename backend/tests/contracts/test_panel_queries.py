"""Do the bounded console declarations name published ledgers and actual row columns?"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.eval_row import RENAMED_CELLS, EvalRow
from idhazh.contracts.host_fingerprint import COLUMN_READERS as HOST_READERS
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import COLUMN_READERS as ITEM_READERS
from idhazh.contracts.item_health import MACHINE_CELLS_RENAMED, UNREAD_CELLS, ItemHealthRow
from idhazh.contracts.knobs.ledger import LedgerConfig

pytestmark = pytest.mark.contract

#: Fixed input inventory, in the registry's ownership order.
QUERY_MODULES: Final = ("shared", "pipelines", "model", "machine", "voices", "window")
QUERY_ROOT: Final = "frontend/src/lib/console/queries"
EXPECTED_NAMES: Final = {
    "shared": ("failedRuleQuery",),
    "pipelines": (
        "failureMixQuery", "itemTimeSplitQuery", "slowerOnSameWorkQuery",
        "stageTimingsQuery", "itemCostQuery", "runTimelineQuery", "extractionQuery",
        "extractionScoresQuery", "articleAgeQuery",
    ),
    "model": (
        "modelThroughputQuery", "callEndingQuery", "faithfulnessQuery",
        "sourceDoubtsQuery", "sourceDoubtsItemsQuery", "writeCostQuery", "scoreCostQuery",
        "summaryLengthQuery", "modelChangeQuery", "modelChangeItemsQuery",
    ),
    "machine": (
        "twoClocksQuery", "twoClocksHostsQuery", "processorLostQuery", "diskReadsQuery",
        "machineCardsQuery", "machineCardsItemsQuery", "slowerMachinesQuery", "platformMixQuery",
        "slowestArticlesQuery", "tailTrendQuery", "closestToMemoryQuery", "memoryHeldQuery",
        "contextHeadroomQuery", "articleCostQuery", "articleCostHostsQuery",
        "promptReuseQuery", "readAgainstWrittenQuery",
    ),
    "voices": ("feedsFailedQuery", "fetchTimeQuery", "sourceCutsQuery", "whyChosenQuery", "watchlistQuery"),
    "window": (),
}

#: Independent transcription of the panel tables, using the row's declared renames.
EXPECTED_COLUMNS: Final[Mapping[str, tuple[str, ...]]] = {
    "failedRuleQuery": ("date", "stage", "outcome", "code", "failed_rule"),
    "failureMixQuery": ("date", "stage", "outcome", "code", "failed_rule"),
    "itemTimeSplitQuery": ("date", "item_total_ms", "fetch_ms", "extract_ms", "summarize_ms", "label_ms", "summary_ms", "visual_plan_ms", "faithfulness_ms", "stage_gap_ms"),
    "slowerOnSameWorkQuery": ("date", "cpu_model", "prefill_ms", "input_tokens", "cached_tokens", "decode_ms", "output_tokens"),
    "stageTimingsQuery": ("date", "fetch_ms", "extract_ms", "summarize_ms"),
    "itemCostQuery": ("date", "prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens", "label_input_tokens", "label_cached_tokens"),
    "runTimelineQuery": ("run_id", "item_id", "source_id", "machine_shard", "item_index", "item_started_at", "item_ended_at", "queue_wait_ms", "fetch_ms", "robots_ms", "extract_ms", "label_ms", "summary_ms", "visual_plan_ms", "faithfulness_ms", "stage_gap_ms", "item_total_ms"),
    "extractionQuery": ("date", "stage", "outcome", "code", "url_key", "element_class", "span_integrity", "elements_found"),
    "extractionScoresQuery": ("date", "url_key", "extraction_suspect"),
    "articleAgeQuery": ("published_at", "time_source", "item_started_at", "outcome"),
    "modelThroughputQuery": ("date", "run_id", "model_id", "prefill_ms", "decode_ms", "input_tokens", "cached_tokens", "output_tokens"),
    "callEndingQuery": ("date", "summary_finish_reason", "label_finish_reason"),
    "faithfulnessQuery": ("date", "hhem", "hhem_delta"),
    "sourceDoubtsQuery": ("date", "url_key", "band", "unsupported_numbers", "hedge_dropped", "evidential_density", "speculative_density"),
    "sourceDoubtsItemsQuery": ("url_key", "source_id"),
    "writeCostQuery": ("date", "summarize_ms"),
    "scoreCostQuery": ("date", "score_ms"),
    "summaryLengthQuery": ("date", "run_id", "model_id", "summary_words", "source_words_before_cap", "source_words", "compression"),
    "modelChangeQuery": ("date", "model_id", "summary_words", "source_words_before_cap", "source_words", "extractiveness", "verbatim_run", "band", "unsupported_numbers", "hedge_dropped"),
    "modelChangeItemsQuery": ("date", "summarize_ms", "prefill_ms", "decode_ms", "input_tokens", "cached_tokens", "output_tokens"),
    "twoClocksQuery": ("date", "run_id", "machine_job", "machine_shard", "prefill_ms", "input_tokens", "cached_tokens"),
    "twoClocksHostsQuery": ("date", "run_id", "job", "shard", "server_prompt_tokens", "server_prompt_seconds"),
    "processorLostQuery": ("date", "run_id", "machine_shard", "cpu_steal_pct"),
    "diskReadsQuery": ("date", "run_id", "item_index", "llama_major_faults", "os_mem_cached_bytes", "weights_pinned"),
    "machineCardsQuery": ("date", "run_id", "job", "shard", "fingerprint", "cpu_model", "cpu_family", "cpu_model_number", "cpu_stepping", "microcode", "flags", "l3_cache_bytes", "boot_seconds", "mhz_at_probe", "memcpy_gib_s", "memcpy_probe_mib", "vm_size", "vm_location", "vm_zone", "vm_fault_domain"),
    "machineCardsItemsQuery": ("date", "run_id", "machine_job", "machine_shard", "cpu_model"),
    "slowerMachinesQuery": ("run_id", "cpu_model", "prefill_ms", "input_tokens", "cached_tokens", "decode_ms", "output_tokens"),
    "platformMixQuery": ("date", "run_id", "job", "shard", "fingerprint", "cpu_model", "job_seconds", "server_prompt_tokens", "server_prompt_seconds"),
    "slowestArticlesQuery": ("run_id", "item_id", "source_id", "machine_shard", "item_total_ms", "fetch_ms", "extract_ms", "summarize_ms", "faithfulness_ms", "stage_gap_ms", "queue_wait_ms"),
    "tailTrendQuery": ("date", "run_id", "summarize_ms"),
    "closestToMemoryQuery": ("date", "item_id", "source_id", "os_mem_total_bytes", "os_mem_available_min_bytes", "source_words"),
    "memoryHeldQuery": ("date", "item_id", "os_mem_total_bytes", "os_mem_available_bytes", "llama_rss_bytes", "python_rss_bytes", "llama_rss_anon_bytes", "python_rss_anon_bytes", "os_swap_total_bytes", "os_swap_free_bytes"),
    "contextHeadroomQuery": ("label_input_tokens", "summary_input_tokens", "n_ctx_configured", "n_parallel", "truncation_cap_tokens"),
    "articleCostQuery": ("date", "run_id", "machine_job", "machine_shard", "item_index", "item_total_ms", "cpu_busy_pct", "prefill_ms", "decode_ms", "llama_rss_bytes"),
    "articleCostHostsQuery": ("date", "run_id", "job", "shard", "threads"),
    "promptReuseQuery": ("date", "label_input_tokens", "label_cached_tokens", "label_cache_pct", "label_prefill_tokens_per_s", "summary_input_tokens", "summary_cached_tokens", "summary_cache_pct", "summary_prefill_tokens_per_s"),
    "readAgainstWrittenQuery": ("date", "run_id", "input_tokens", "output_tokens", "prefill_ms", "decode_ms"),
    "feedsFailedQuery": ("date", "source_id", "stage", "outcome", "code", "http_status", "source_form", "tier"),
    "fetchTimeQuery": ("source_id", "fetch_ms", "fetch_connect_ms", "fetch_ttfb_ms", "robots_ms", "retry_total_ms", "retry_count"),
    "sourceCutsQuery": ("date", "source_id", "url_key", "source_words_before_cap", "source_words"),
    "whyChosenQuery": ("date", "run_id", "item_id", "source_id", "selection_score", "authority_score", "tier_score", "feed_weight", "feed_reliability", "recency_bonus", "lens_bonus", "watchlist_bonus", "carriage_step"),
    "watchlistQuery": ("date", "url_key", "watchlist_hit", "on_front_page"),
}


@dataclass(frozen=True)
class QueryDeclaration:
    module: str
    name: str
    ledger: str
    columns: tuple[str, ...]
    span: str


def declarations(text: str, module: str) -> tuple[QueryDeclaration, ...]:
    """Read only the explicit PanelQuery object grammar this row writes."""
    exported = re.findall(r"export const (\w+Query)\s*=", text)
    objects = re.findall(
        r"export const (\w+Query) = \{(.*?)\} as const satisfies PanelQuery;", text, re.S
    )
    assert [name for name, _ in objects] == exported, f"{module}: query must be a literal PanelQuery"
    found: list[QueryDeclaration] = []
    for name, body in objects:
        fields = {}
        for key in ("name", "ledger", "span"):
            match = re.search(rf"\b{key}:\s*'([^']+)'", body)
            assert match is not None, f"{module}/{name}: {key} must be a string literal"
            fields[key] = match[1]
        assert fields["name"] == name, f"{module}/{name}: name must be its exported identifier"
        columns = re.search(r"\bcolumns:\s*\[([^\]]*)\]", body)
        assert columns is not None, f"{module}/{name}: columns must be a literal array"
        assert re.fullmatch(r"\s*'[a-z_][a-z0-9_]*'(?:\s*,\s*'[a-z_][a-z0-9_]*')*\s*,?\s*", columns[1]), (
            f"{module}/{name}: columns must contain only string literals"
        )
        names = tuple(re.findall(r"'([^']+)'", columns[1]))
        assert len(set(names)) == len(names), f"{module}/{name}: a column is declared twice"
        assert fields["span"] in ("window", "newest-day", "widest"), f"{module}/{name}: unknown span"
        for filtered in re.findall(r"\bcolumn:\s*'([^']+)'", body):
            assert filtered in names, f"{module}/{name}: filter column {filtered} is not declared"
        found.append(QueryDeclaration(module, name, fields["ledger"], names, fields["span"]))
    return tuple(found)


def query_faults(
    query: QueryDeclaration,
    published: Sequence[str],
    columns: Mapping[str, Sequence[str]],
    unread: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    where = f"{query.module}/{query.name}"
    faults = []
    if query.ledger not in published:
        faults.append(f"{where}: {query.ledger} is not in LedgerConfig.published")
    if query.ledger not in columns:
        faults.append(f"{where}: {query.ledger} names no declared panel row shape")
        return tuple(faults)
    for name in query.columns:
        if name not in columns[query.ledger]:
            faults.append(f"{where}: {query.ledger}.{name} is not a column of its actual row")
        if name in unread.get(query.ledger, ()):
            faults.append(f"{where}: {query.ledger}.{name} is still in UNREAD_CELLS")
    return tuple(faults)


def load_queries() -> tuple[QueryDeclaration, ...]:
    return tuple(
        query
        for module in QUERY_MODULES
        for query in declarations(read_text(REPO_ROOT / QUERY_ROOT / f"{module}.ts"), module)
    )


def row_columns() -> dict[str, tuple[str, ...]]:
    return {
        "item-health": ItemHealthRow.csv_columns(),
        "host-fingerprint": HostFingerprintRow.csv_columns(),
        "summary-quality-evals": EvalRow.csv_columns(),
    }


def test_every_declared_query_uses_a_published_ledger_and_its_actual_row() -> None:
    config = LedgerConfig.model_validate(json.loads(read_text(REPO_ROOT / "config/idhazh.json"))["ledger"])
    unread = {"item-health": tuple(name for names in UNREAD_CELLS.values() for name in names)}
    queries = load_queries()
    faults = [
        fault for query in queries
        for fault in query_faults(query, config.published, row_columns(), unread)
    ]
    assert not faults, "\n".join(faults)
    for module in QUERY_MODULES:
        assert tuple(query.name for query in queries if query.module == module) == EXPECTED_NAMES[module]


def test_each_declared_item_and_host_column_has_exactly_the_first_query_owner() -> None:
    owners = {"item-health": ITEM_READERS, "host-fingerprint": HOST_READERS}
    seen: set[tuple[str, str]] = set()
    for query in load_queries():
        if query.ledger not in owners:
            continue
        for column in query.columns:
            key = (query.ledger, column)
            if key in seen:
                continue
            seen.add(key)
            readers = [reader for reader, names in owners[query.ledger].items() if column in names]
            assert readers == [f"{QUERY_ROOT}/{query.module}.ts"], (query.name, column, readers)


def test_every_query_declares_exactly_its_planned_columns() -> None:
    assert {query.name: query.columns for query in load_queries()} == EXPECTED_COLUMNS


@pytest.mark.parametrize(
    ("ledger", "column", "fault"),
    (
        ("scores", "date", "scores is not in LedgerConfig.published"),
        ("item-health", "summray_ms", "item-health.summray_ms is not a column"),
        ("item-health", "failed_field", "item-health.failed_field is still in UNREAD_CELLS"),
        ("summary-quality-evals", "summary_word_count", "summary-quality-evals.summary_word_count is not a column"),
    ),
)
def test_validation_names_misspelled_ledgers_columns_and_the_unread_failed_field(
    ledger: str, column: str, fault: str
) -> None:
    query = QueryDeclaration("voices", "watchlistQuery", ledger, (column,), "window")
    faults = query_faults(
        query, ("item-health", "host-fingerprint", "summary-quality-evals"), row_columns(),
        {"item-health": ("failed_field",)},
    )
    assert any(fault in found for found in faults), faults


@pytest.mark.parametrize("columns", ("[]", "dynamicColumns", "['date', anotherColumn]", "['date', 'date']"))
def test_a_query_cannot_hide_its_columns_behind_an_expression(columns: str) -> None:
    text = (
        "export const brokenQuery = { name: 'brokenQuery', ledger: 'item-health', "
        f"columns: {columns}, span: 'window' }} as const satisfies PanelQuery;"
    )
    with pytest.raises(AssertionError, match="brokenQuery"):
        declarations(text, "fixture")


def test_platform_mix_names_exactly_the_shipped_fleet_columns() -> None:
    text = read_text(REPO_ROOT / "frontend/src/lib/charts/fleet.ts")
    match = re.search(r"export const FLEET_COLUMNS = \[([^\]]+)\]", text)
    assert match is not None
    expected = tuple(re.findall(r"'([^']+)'", match[1]))
    query = next(query for query in load_queries() if query.name == "platformMixQuery")
    assert query.columns == expected
    assert query.ledger == "host-fingerprint"


def test_word_and_machine_renames_are_the_actual_contract_mappings() -> None:
    assert {name: RENAMED_CELLS[name] for name in (
        "source_word_count", "source_seen_word_count", "summary_word_count"
    )} == {
        "source_word_count": "source_words_before_cap",
        "source_seen_word_count": "source_words",
        "summary_word_count": "summary_words",
    }
    assert dict(MACHINE_CELLS_RENAMED) == {"job": "machine_job", "shard": "machine_shard"}
    queries = {query.name: query for query in load_queries()}
    assert queries["summaryLengthQuery"].columns == (
        "date", "run_id", "model_id", "summary_words", "source_words_before_cap", "source_words", "compression"
    )
    assert queries["twoClocksQuery"].columns[:4] == ("date", "run_id", "machine_job", "machine_shard")
    assert queries["twoClocksHostsQuery"].columns[:4] == ("date", "run_id", "job", "shard")


def test_query_span_and_fetch_predicate_match_the_panel_contracts() -> None:
    queries = load_queries()
    assert {query.name for query in queries if query.span == "widest"} == {
        "modelChangeQuery", "modelChangeItemsQuery"
    }
    assert {query.name for query in queries if query.span == "newest-day"} == {
        "runTimelineQuery", "twoClocksQuery", "twoClocksHostsQuery", "machineCardsQuery",
        "machineCardsItemsQuery", "slowestArticlesQuery", "memoryHeldQuery", "whyChosenQuery",
    }
    text = read_text(REPO_ROOT / QUERY_ROOT / "voices.ts")
    assert "where: [{ column: 'stage', op: '=', value: 'fetch' }]" in text


def test_failed_rule_has_one_owner_and_both_drawing_routes_reexport_it() -> None:
    queries = load_queries()
    assert len([query for query in queries if query.name == "failedRuleQuery"]) == 1
    for module in ("pipelines", "model"):
        text = read_text(REPO_ROOT / QUERY_ROOT / f"{module}.ts")
        assert "export { failedRuleQuery } from './shared';" in text


def test_real_unread_map_still_refuses_failed_field_without_rejecting_failed_rule() -> None:
    query = next(query for query in load_queries() if query.name == "failedRuleQuery")
    unread = {"item-health": tuple(name for names in UNREAD_CELLS.values() for name in names)}
    assert "failed_field" in unread["item-health"]
    assert "failed_rule" not in unread["item-health"]
    faults = query_faults(
        replace(query, columns=(*query.columns, "failed_field")), ("item-health",), row_columns(), unread
    )
    assert faults == ("shared/failedRuleQuery: item-health.failed_field is still in UNREAD_CELLS",)


def test_registry_only_changes_metadata_and_the_fetch_header_description() -> None:
    assert ItemHealthRow.__changelog__[0].version == "2026-10-10"
    assert HostFingerprintRow.__changelog__[0].version == "2026-10-10"
    assert "not the persisted row" in ItemHealthRow.__changelog__[0].why
    assert "not the persisted row" in HostFingerprintRow.__changelog__[0].why
    assert "response headers" in (ItemHealthRow.model_fields["fetch_ttfb_ms"].description or "")
