"""Do the bounded console declarations name published ledgers and actual row columns?"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

import pytest
from support.paths import REPO_ROOT, read_text

from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep, ShardOutcome
from idhazh.contracts.eval_row import RENAMED_CELLS, EvalRow
from idhazh.contracts.file_envelope import FileEnvelope, RowIdentity, WriterIdentity
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.host_fingerprint import COLUMN_READERS as HOST_READERS
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import COLUMN_READERS as ITEM_READERS
from idhazh.contracts.item_health import MACHINE_CELLS_RENAMED, UNREAD_CELLS, ItemHealthRow
from idhazh.contracts.ledgers import LedgersConfig
from idhazh.contracts.run_shards import RunShards
from idhazh.contracts.story_similarity_diagnostics import (
    MAX_SCORE_BINS,
    JudgeProbabilityEvidence,
    JudgeProbabilityStatus,
    SampleStatus,
    ScoreDriftBaseline,
    ScoreDriftSource,
    ScoreDriftStatus,
    ScorePoolHistogram,
    SliceOutcome,
    SliceOutcomes,
)
from idhazh.contracts.story_similarity_pair_verdict import (
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.contracts.task_performance import TaskPerformanceRow

pytestmark = pytest.mark.contract
LEGACY_HOST_INPUT_COLUMNS: Final = ("cores", "threads", "mhz_max", "mhz_at_probe")

#: Fixed input inventory, in the registry's ownership order.
QUERY_MODULES: Final = ("shared", "pipelines", "model", "machine", "voices", "judgement", "operations", "window")
QUERY_ROOT: Final = "frontend/src/lib/console/queries"
EXPECTED_NAMES: Final = {
    "shared": ("failedRuleQuery",),
    "pipelines": (
        "failureMixQuery", "itemTimeSplitQuery",
        "stageTimingsQuery", "writeCostQuery", "tailTrendQuery", "runTimelineQuery", "slowestArticlesQuery", "articleAgeQuery",
    ),
    "model": (
        "modelThroughputQuery", "itemCostQuery", "callEndingQuery", "faithfulnessQuery",
        "scoreCostQuery",
        "summaryLengthQuery",
    ),
    "machine": (
        "runShardsQuery",
        "slowerMachinesQuery", "platformMixQuery", "servingSpeedQuery",
        "slowerOnSameWorkQuery", "closestToMemoryQuery", "memoryHeldQuery",
        "contextHeadroomQuery", "articleCostQuery", "articleCostHostsQuery",
        "promptReuseQuery", "readAgainstWrittenQuery",
    ),
    "voices": ("feedsFailedQuery", "fetchTimeQuery", "sourceCutsQuery", "whyChosenQuery"),
    "judgement": (
        "judgeHistoryQuery", "judgeDayQuery", "judgeDrawTrialQuery", "judgePairTrialQuery", "judgeCutoffTrialQuery",
        "judgePoolTrialQuery",
    ),
    "operations": ("councilRunsQuery", "gardenerWakeQuery"),
    "window": (),
}

#: Independent transcription of the panel tables, using the row's declared renames.
EXPECTED_COLUMNS: Final[Mapping[str, tuple[str, ...]]] = {
    "runShardsQuery": ("date", "run_id", "shards"),
    "gardenerWakeQuery": (
        "date", "run_id", "attempt", "job", "shard", "task", "work_ended_at", "dry_run",
        "selected", "deleted", "bytes_freed", "stopped_because", "fault", "resume_from",
        "candidates_seen", "handled_through", "recovered",
    ),
    "failedRuleQuery": ("date", "stage", "outcome", "code", "failed_rule"),
    "failureMixQuery": ("date", "stage", "outcome", "code", "failed_rule"),
    "itemTimeSplitQuery": ("date", "item_total_ms", "fetch_ms", "extract_ms", "analyze_ms", "summarize_ms", "label_ms", "summary_ms", "visual_plan_ms", "faithfulness_ms", "stage_gap_ms"),
    "slowerOnSameWorkQuery": ("date", "cpu_model", "prefill_ms", "input_tokens", "cached_tokens", "decode_ms", "output_tokens"),
    "stageTimingsQuery": ("date", "fetch_ms", "extract_ms", "summarize_ms"),
    "itemCostQuery": ("date", "prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens", "label_input_tokens", "label_cached_tokens"),
    "runTimelineQuery": ("run_id", "item_id", "source_id", "machine_shard", "item_index", "item_started_at", "item_ended_at", "queue_wait_ms", "fetch_ms", "robots_ms", "extract_ms", "analyze_ms", "summarize_ms", "label_ms", "summary_ms", "visual_plan_ms", "visual_plan_ms_is_estimate", "faithfulness_ms", "stage_gap_ms", "item_total_ms", "outcome", "stage", "code"),
    "articleAgeQuery": ("published_at", "time_source", "item_started_at", "outcome"),
    "modelThroughputQuery": ("date", "run_id", "model_id", "prefill_ms", "decode_ms", "input_tokens", "cached_tokens", "output_tokens"),
    "callEndingQuery": ("date", "summary_finish_reason", "label_finish_reason"),
    "faithfulnessQuery": ("date", "hhem", "hhem_delta"),
    "writeCostQuery": ("date", "summarize_ms"),
    "scoreCostQuery": ("date", "score_ms"),
    "summaryLengthQuery": ("date", "run_id", "model_id", "summary_words", "compression"),
    "slowerMachinesQuery": (
        "date", "run_id", "machine_job", "machine_pipeline_name", "machine_task_name", "machine_shard",
        "cpu_model", "prefill_ms", "input_tokens", "cached_tokens", "decode_ms", "output_tokens",
    ),
    "platformMixQuery": (
        "version", "date", "run_id", "job", "pipeline_name", "task_name", "shard", "fingerprint", "fingerprint_version",
        "unit_id", "attempt", "cpu_model", "l3_cache_bytes", "cpu_logical_processors",
        "server_prompt_tokens", "server_prompt_seconds",
        *LEGACY_HOST_INPUT_COLUMNS,
    ),
    "servingSpeedQuery": (
        "host_unit_id", "run_id", "attempt", "pipeline_name", "task_name", "task_kind",
        "server_prompt_tokens", "server_prompt_seconds",
    ),
    "slowestArticlesQuery": ("run_id", "item_id", "source_id", "machine_shard", "item_total_ms", "fetch_ms", "extract_ms", "analyze_ms", "summarize_ms", "faithfulness_ms", "stage_gap_ms", "queue_wait_ms"),
    "tailTrendQuery": ("date", "run_id", "summarize_ms"),
    "closestToMemoryQuery": ("date", "item_id", "source_id", "os_mem_total_bytes", "os_mem_available_min_bytes"),
    "memoryHeldQuery": ("date", "item_id", "os_mem_total_bytes", "os_mem_available_bytes", "llama_rss_bytes", "python_rss_bytes", "llama_rss_anon_bytes", "python_rss_anon_bytes", "os_swap_total_bytes", "os_swap_free_bytes"),
    "contextHeadroomQuery": ("date", "summary_input_tokens", "n_ctx_configured", "n_parallel", "truncation_cap_tokens"),
    "articleCostQuery": ("date", "run_id", "attempt", "machine_job", "machine_pipeline_name", "machine_task_name", "machine_shard", "item_index", "item_total_ms", "cpu_busy_pct", "prefill_ms", "decode_ms", "llama_rss_bytes"),
    "articleCostHostsQuery": (
        "version", "date", "run_id", "attempt", "job", "pipeline_name", "task_name", "shard", "cpu_logical_processors",
        *LEGACY_HOST_INPUT_COLUMNS,
    ),
    "promptReuseQuery": ("date", "label_input_tokens", "label_cached_tokens", "summary_input_tokens", "summary_cached_tokens"),
    "readAgainstWrittenQuery": ("date", "run_id", "item_id", "input_tokens", "output_tokens", "prefill_ms", "decode_ms"),
    "feedsFailedQuery": ("date", "source_id", "stage", "outcome", "code", "http_status", "source_form", "tier"),
    "fetchTimeQuery": ("source_id", "fetch_ms", "fetch_connect_ms", "fetch_ttfb_ms", "robots_ms", "retry_total_ms", "retry_count"),
    "sourceCutsQuery": ("date", "source_id", "url_key", "source_words_before_cap", "source_words"),
    "whyChosenQuery": ("date", "run_id", "item_id", "source_id", "selection_score", "authority_score", "tier_score", "feed_weight", "feed_reliability", "recency_bonus", "lens_bonus", "watchlist_bonus", "carriage_step"),
    "councilRunsQuery": (
        "date", "run_id", "attempt", "judge_id", "started_at", "evaluation_step",
        "work_part_index", "work_part_count", "outcome",
    ),
    "judgeDayQuery": (
        "date", "run_id", "attempt", "pairs_drawn", "pairs_returned",
        "runners_reported", "runners_expected", "pairs_dealt", "pairs_valid", "pairs_agreed",
        "disagreement_rate", "pairs_refused", "pairs_unreadable", "pairs_abandoned", "unclear_rate",
        "slice_outcomes", "sample_status", "evaluated_cutoff",
        "sample_tp", "sample_fp", "sample_fn", "sample_tn", "sample_precision", "sample_recall",
        "upper_threshold_before", "upper_cutoff_false_match_share", "upper_cutoff_sample_size",
        "upper_cutoff_brier_score", "cutoff_brier_score",
        "score_drift_baseline", "score_drift_status", "score_psi", "score_wasserstein_distance", "score_ks_distance",
        "judge_probability_evidence", "judge_probability_status", "judge_probability_brier_score",
        "judge_probability_baseline_brier_score", "judge_probability_ece",
    ),
    "judgeDrawTrialQuery": (
        "date", "run_id", "attempt", "pairs_drawn", "pairs_returned", "sample_status", "slice_outcomes",
        "lower_threshold_before", "upper_threshold_before", "lower_threshold_after", "upper_threshold_after",
    ),
    "judgePairTrialQuery": (
        "date", "run_id", "attempt", "pair_key", "similarity_score", "verdict", "verdict_swapped",
        "lower_threshold_in_force", "upper_threshold_in_force", "scorer_model", "cosine_weight",
        "judge_model", "prompt_digest", "grammar_digest", "judge_policy_version", "judge_temperature",
    ),
    "judgeCutoffTrialQuery": (
        "date", "run_id", "attempt", "sample_f0_5", "sample_average_precision",
        "sample_precision_at_recall_90", "sample_recall_90_cutoff", "sample_recall_at_recall_90_cutoff",
        "lower_estimate", "lower_nights_used", "lower_usable_pairs_used", "lower_held_because", "lower_move_limited_by",
        "upper_estimate", "upper_nights_used", "upper_usable_pairs_used", "upper_held_because", "upper_move_limited_by",
    ),
    "judgePoolTrialQuery": ("date", "run_id", "attempt", "score_pool_histogram"),
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
    enabled: Sequence[str],
    columns: Mapping[str, Sequence[str]],
    unread: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    where = f"{query.module}/{query.name}"
    faults = []
    if query.ledger not in enabled:
        faults.append(f"{where}: {query.ledger} is not enabled for the Data explorer")
    if query.ledger not in columns:
        faults.append(f"{where}: {query.ledger} names no declared panel row shape")
        return tuple(faults)
    for name in query.columns:
        legacy_host = query.ledger == "host-fingerprint" and name in LEGACY_HOST_INPUT_COLUMNS
        if name not in columns[query.ledger] and not legacy_host:
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
        "council-run-records": tuple(dict.fromkeys((*CouncilRunRecord.model_fields, *RowIdentity.model_fields))),
        "gardener": tuple(CollectionPruneRow.model_fields),
        "run-shards": tuple(RunShards.model_fields),
        "item-health": (*ItemHealthRow.csv_columns(), "attempt"),
        "host-fingerprint": (*HostFingerprintRow.csv_columns(), "attempt", "unit_id"),
        "task-performance": (*TaskPerformanceRow.model_fields, "attempt"),
        "summary-quality-evals": EvalRow.csv_columns(),
        # The compact ledger keeps the winning writer's envelope attempt next to the row.
        "threshold-history": (*StorySimilarityThresholdHistoryRow.model_fields, "attempt"),
        "pair-verdicts": (*StorySimilarityPairVerdict.model_fields, "attempt"),
    }


def ts_literal(path: str, key: str) -> tuple[str, ...]:
    literal = re.search(rf"const {key} = \[([^\]]+)\]", read_text(REPO_ROOT / path))
    assert literal is not None
    return tuple(re.findall(r"'([^']+)'", literal[1]))


def test_console_run_reports_use_the_producers_vocabulary() -> None:
    council = "frontend/src/lib/console/council-runs.ts"
    gardener = "frontend/src/lib/console/operations/gardener-reports.ts"
    assert ts_literal(council, "COUNCIL_STEPS") == tuple(EvaluationStep)
    assert ts_literal(council, "COUNCIL_OUTCOMES") == tuple(ShardOutcome)
    assert ts_literal(gardener, "GARDENER_STOPS") == tuple(StopReason)
    assert ts_literal(gardener, "GARDENER_RECOVERIES") == tuple(RecoveryNote)


def test_compact_write_projection_uses_native_fields() -> None:
    compact = ts_literal("frontend/src/lib/data/compact-write-footer.ts", "COMPACT_WRITE_FOOTER_KEYS")
    identity = {"run_id", "attempt", "job", "shard", "producer"}
    assert identity <= set(WriterIdentity.model_fields)
    assert set(compact) == {"envelope_version", "tier", "ledger", "period", "covers", "written_at_ms", "built_from", *identity}
    assert set(compact) - identity - {"envelope_version"} <= set(FileEnvelope.model_fields)


def test_judgement_reads_only_the_compact_diagnostic_fields_it_displays() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/console/judge-observations.ts")
    parsed = re.search(r"interface SliceOutcome \{(.*?)\n\}", source, re.S)
    assert parsed is not None
    assert set(re.findall(r"\b(\w+):", parsed[1])) == SliceOutcome.model_fields.keys() - {
        "bucket", "available",
    }
    fields = {
        "judgeSlices": ({"slices"}, SliceOutcomes.model_fields.keys()),
        "judgeDriftBaseline": (
            {"sources", "required_days", "date"},
            (ScoreDriftBaseline.model_fields.keys() - {"share_floor"})
            | (ScoreDriftSource.model_fields.keys() - {"run_id", "histogram_sha256"}),
        ),
        "judgeProbabilityEvidence": (
            {"source_date", "source_run_id", "pairs", "yes", "bins"},
            JudgeProbabilityEvidence.model_fields.keys() - {"fit_sha256"},
        ),
    }
    for name, (used, native) in fields.items():
        assert used == native
        body = source.split(f"export function {name}(", 1)[1].split("\n}", 1)[0]
        for field in native:
            assert re.search(rf"\b{field}\b", body), (name, field)


def test_judgement_names_the_producers_diagnostic_statuses_and_verdicts() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/console/judge-observations.ts")
    for name, native in (
        ("SAMPLE_STATUS", SampleStatus),
        ("DRIFT_STATUS", ScoreDriftStatus),
        ("PROBABILITY_STATUS", JudgeProbabilityStatus),
    ):
        found = re.search(rf"export const {name} = \{{(.*?)\n\}} as const;", source, re.S)
        assert found is not None
        assert set(re.findall(r"^\s*(\w+):", found[1], re.M)) == {entry.value for entry in native}
    verdicts = re.search(r"const VERDICTS = \[(.*?)\] as const;", source)
    assert verdicts is not None
    assert set(re.findall(r"'([^']+)'", verdicts[1])) == {entry.value for entry in SameStoryVerdict}


def test_judgement_pool_reader_uses_the_native_fields_and_bound() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/console/judge-score-pool.ts")
    body = source.split("export function judgePool(", 1)[1].split("\n}", 1)[0]
    assert set(re.findall(r"\bsaved(?:\.|\?\.)([a-z_]\w*)", body)) == ScorePoolHistogram.model_fields.keys()
    bound = re.search(r"^export const MAX_SCORE_BINS = (\d+);$", source, re.M)
    assert bound is not None
    assert int(bound[1]) == MAX_SCORE_BINS


def explorer_ledgers() -> tuple[str, ...]:
    registry = LedgersConfig.from_json(read_text(REPO_ROOT / "config/ledgers.json"))
    return tuple(name.value for name in registry.data_explorer_ledgers)


def test_count_capability_binds_only_the_approved_business_columns() -> None:
    count = QueryDeclaration(
        module="machine", name="runShardsQuery", ledger="run-shards",
        columns=("date", "run_id", "shards"), span="widest",
    )
    assert query_faults(count, explorer_ledgers(), row_columns(), {}) == ()
    assert set(RunShards.model_fields) == {"version", *count.columns}


def test_every_declared_query_uses_a_published_ledger_and_its_actual_row() -> None:
    unread = {"item-health": tuple(name for names in UNREAD_CELLS.values() for name in names)}
    queries = load_queries()
    enabled = explorer_ledgers()
    faults = [
        fault for query in queries
        for fault in query_faults(query, enabled, row_columns(), unread)
    ]
    assert not faults, "\n".join(faults)
    for module in QUERY_MODULES:
        assert tuple(query.name for query in queries if query.module == module) == EXPECTED_NAMES[module]


def test_each_declared_item_and_host_column_has_exactly_the_first_query_owner() -> None:
    readers_by_ledger = {"item-health": ITEM_READERS, "host-fingerprint": HOST_READERS}
    seen: set[tuple[str, str]] = set()
    for query in load_queries():
        if query.ledger not in readers_by_ledger:
            continue
        for column in query.columns:
            if query.ledger == "item-health" and column == "attempt":
                continue  # Writer attempt is stored envelope metadata, not an item measurement.
            if query.ledger == "host-fingerprint" and (
                column in LEGACY_HOST_INPUT_COLUMNS
                or (column in RowIdentity.model_fields and column not in HostFingerprintRow.model_fields)
            ):
                continue
            key = (query.ledger, column)
            if key in seen:
                continue
            seen.add(key)
            readers = [reader for reader, names in readers_by_ledger[query.ledger].items() if column in names]
            assert readers == [f"{QUERY_ROOT}/{query.module}.ts"], (query.name, column, readers)


def test_every_query_declares_exactly_its_planned_columns() -> None:
    # The packed Judgement history test exercises this projection through its consumer.
    assert {
        query.name: query.columns for query in load_queries() if query.name != "judgeHistoryQuery"
    } == EXPECTED_COLUMNS


@pytest.mark.parametrize(
    ("ledger", "column", "fault"),
    (
        ("scores", "date", "scores is not enabled for the Data explorer"),
        ("item-health", "summray_ms", "item-health.summray_ms is not a column"),
        ("item-health", "failed_field", "item-health.failed_field is still in UNREAD_CELLS"),
        ("summary-quality-evals", "summary_word_count", "summary-quality-evals.summary_word_count is not a column"),
    ),
)
def test_validation_names_misspelled_ledgers_columns_and_the_unread_failed_field(
    ledger: str, column: str, fault: str
) -> None:
    query = QueryDeclaration("voices", "fetchTimeQuery", ledger, (column,), "window")
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
    assert set(query.columns) == {*expected, "cpu_logical_processors"}
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
        "date", "run_id", "model_id", "summary_words", "compression"
    )


def test_query_span_and_fetch_predicate_match_the_panel_contracts() -> None:
    queries = load_queries()
    assert {query.name for query in queries if query.span == "widest"} == {
        "runShardsQuery", "platformMixQuery", "servingSpeedQuery", "councilRunsQuery", "gardenerWakeQuery"
    }
    assert {query.name for query in queries if query.span == "newest-day"} == {
        "runTimelineQuery",
        "slowestArticlesQuery", "memoryHeldQuery", "whyChosenQuery",
    }
    text = read_text(REPO_ROOT / QUERY_ROOT / "voices.ts")
    assert "where: [{ column: 'stage', op: '=', value: 'fetch' }]" in text


def test_failed_rule_is_shared_but_only_pipelines_draws_it() -> None:
    queries = load_queries()
    assert len([query for query in queries if query.name == "failedRuleQuery"]) == 1
    assert "export { failedRuleQuery } from './shared';" in read_text(REPO_ROOT / QUERY_ROOT / "pipelines.ts")
    assert "failedRuleQuery" not in read_text(REPO_ROOT / QUERY_ROOT / "model.ts")


def test_real_unread_map_still_refuses_failed_field_without_rejecting_failed_rule() -> None:
    query = next(query for query in load_queries() if query.name == "failedRuleQuery")
    unread = {"item-health": tuple(name for names in UNREAD_CELLS.values() for name in names)}
    assert "failed_field" in unread["item-health"]
    assert "failed_rule" not in unread["item-health"]
    faults = query_faults(
        replace(query, columns=(*query.columns, "failed_field")), ("item-health",), row_columns(), unread
    )
    assert faults == ("shared/failedRuleQuery: item-health.failed_field is still in UNREAD_CELLS",)


def test_query_registry_tracks_the_current_host_schema() -> None:
    assert ItemHealthRow.schema_version() == "2026-11-17"
    assert HostFingerprintRow.schema_version() == "2026-10-26"
    assert "response headers" in (ItemHealthRow.model_fields["fetch_ttfb_ms"].description or "")


@pytest.mark.parametrize(
    ("model", "expected"),
    (
        (ItemHealthRow, "8277ea705d03282109621925f5d86e0c6dfea805fa44edd343dd3fdde5d1250c"),
        (HostFingerprintRow, "04a248a34a14c1165e7c19d577b6cf9e9a31e9753e1fcaf7113d9df9b137fc47"),
    ),
)
def test_registry_tracks_the_declared_persisted_shape(model: type[ItemHealthRow] | type[HostFingerprintRow], expected: str) -> None:
    """The declared query shapes retain exact field order, constraints and defaults."""
    def shape(value: object) -> object:
        if isinstance(value, dict):
            return {key: shape(child) for key, child in value.items() if key != "description"}
        if isinstance(value, list):
            return [shape(child) for child in value]
        return value

    encoded = json.dumps(shape(model.model_json_schema()), separators=(",", ":"), ensure_ascii=True).encode()
    assert hashlib.sha256(encoded).hexdigest() == expected
