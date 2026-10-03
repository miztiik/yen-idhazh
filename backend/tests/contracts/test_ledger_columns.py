"""Do ledger serializers and the canary writer keep the declared column names and order?"""

from __future__ import annotations

import re

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.item_health import ItemHealthRow

pytestmark = pytest.mark.contract


def test_the_eval_ledger_columns_are_defined_once() -> None:
    columns = EvalRow.csv_columns()
    assert len(set(columns)) == len(columns)
    for required in ("date", "source_url", "title", "url_key", "band", "version"):
        assert required in columns, "a ledger row must still mean something after a prune"


def test_the_item_health_ledger_columns_are_defined_once() -> None:
    assert ItemHealthRow.csv_columns() == (
        "version",
        "date",
        "run_id",
        "item_id",
        "url_key",
        "canonical_url",
        "vertical",
        "source_id",
        "stage",
        "outcome",
        "code",
        "http_status",
        "source_chars",
        "source_words",
        "summary_words",
        "detail",
        "fetch_ms",
        "extract_ms",
        "summarize_ms",
        "prefill_ms",
        "decode_ms",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "source_words_before_cap",
        "machine_shard",
        "machine_job",
        "span_integrity",
        "elements_found",
        "element_class",
        "model_calls",
        "label_kind",
        "label_prefill_ms",
        "label_decode_ms",
        "label_input_tokens",
        "label_output_tokens",
        "label_cached_tokens",
        "summary_kind",
        "summary_prefill_ms",
        "summary_decode_ms",
        "summary_input_tokens",
        "summary_output_tokens",
        "summary_cached_tokens",
        "truncation_cap_tokens",
        "selection_score",
        "authority_score",
        "tier_score",
        "feed_weight",
        "feed_reliability",
        "lens_bonus",
        "recency_bonus",
        "carriage_step",
        "watchlist_bonus",
        "carried_by",
        "watchlist_hit",
        "on_front_page",
        "tier",
        "source_form",
        "published_at",
        "time_source",
        "item_started_at",
        "item_ended_at",
        "item_index",
        "shard_item_count",
        "queue_wait_ms",
        "fetch_connect_ms",
        "fetch_ttfb_ms",
        "robots_ms",
        "retry_count",
        "retry_total_ms",
        "label_ms",
        "summary_ms",
        "visual_plan_ms",
        "visual_plan_ms_is_estimate",
        "faithfulness_ms",
        "model_wait_ms",
        "item_total_ms",
        "stage_gap_ms",
        "visual_plan_tokens_written",
        "label_cache_pct",
        "summary_cache_pct",
        "slot_id",
        "kv_tokens_at_start",
        "prefix_shared_with_previous",
        "label_prefill_tokens_per_s",
        "label_decode_tokens_per_s",
        "summary_prefill_tokens_per_s",
        "summary_decode_tokens_per_s",
        "label_finish_reason",
        "summary_finish_reason",
        "recovered",
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
        "model_id",
        "model_quantisation",
        "n_ctx_configured",
        "n_parallel",
        "n_threads",
        "n_batch",
        "weights_pinned",
        "label_budget_tokens",
        "summary_budget_tokens",
        "run_visual_decision",
        "temperature",
        "failed_field",
        "failed_rule",
        "os_mem_available_bytes",
        "os_mem_total_bytes",
        "os_mem_cached_bytes",
        "os_swap_free_bytes",
        "os_swap_total_bytes",
        "os_mem_available_min_bytes",
    )


def test_the_feed_health_ledger_columns_are_defined_once() -> None:
    """Appending columns keeps an older positional header readable as a prefix."""
    assert FeedHealthRow.csv_columns() == (
        "version",
        "run_id",
        "date",
        "feed_id",
        "checked_at",
        "outcome",
        "status",
        "items",
        "detail",
        "endpoint_key",
        "robots_outcome",
        "robots_checked_at",
        "robots_status",
        "target_attempted",
    )


def test_the_canary_writes_every_column_the_item_health_ledger_defines() -> None:
    """The JavaScript canary's header must match the Python row it writes."""
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == ItemHealthRow.csv_columns()
