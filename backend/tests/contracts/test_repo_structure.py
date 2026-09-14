"""Do the repository's own structural rules hold - imports, encoding, paths, ledger columns?"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    REPO_ROOT,
    SCHEMAS_DIR,
    read_text,
)
from pydantic import ValidationError

from idhazh.contracts.article import Article
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.fingerprint import text_digest

from ._fixtures import (
    HEX_DIGEST,
    fixture_paths,
)

pytestmark = pytest.mark.contract


def test_contracts_import_no_other_subpackage() -> None:
    """Contracts are the bottom of the dependency graph (CLAUDE.md section 4)."""
    package = REPO_ROOT / "backend" / "idhazh" / "contracts"
    for module in sorted(package.glob("*.py")):
        tree = ast.parse(read_text(module), filename=str(module))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith("idhazh.") and not name.startswith("idhazh.contracts"):
                    pytest.fail(f"{module.name} imports {name}")


@pytest.mark.parametrize(
    "path",
    sorted(SCHEMAS_DIR.glob("*.json")) + sorted(CONFIG_DIR.glob("*.json")) + fixture_paths(),
    ids=lambda p: p.name,
)
def test_repo_text_is_ascii_and_lf(path: Path) -> None:
    raw = path.read_bytes()
    raw.decode("ascii")
    assert b"\r\n" not in raw


def test_no_hash_appears_in_any_published_path() -> None:
    """Decision 2: an item is addressed <vertical>-<id>, never by a digest."""
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in day.items:
        assert not HEX_DIGEST.search(item.item_id)
        if item.visual is not None and item.visual.data_path is not None:
            assert not HEX_DIGEST.search(item.visual.data_path)
    decision = VisualDecision.from_json(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    assert decision.data_path is not None
    assert not HEX_DIGEST.search(decision.data_path)


def test_an_item_id_reads_in_both_shapes_and_the_pattern_never_contracts() -> None:
    """The read-side migration this widening owes, proved on payloads rather than asserted.

    Every day published before 2026-09-12 addressed its items with ten decimal
    digits, and a published day is frozen. So the decimal branch is not a
    transitional arm that ages out - it stays for as long as one of those days
    survives, and this asserts the branch is still literally in the pattern.
    Driven from two committed fixtures rather than from the archive, because a
    test may not cost more as the archive grows (Guardrail #12).
    """
    assert "[0-9]{2,}" in ITEM_ID_PATTERN, "the decimal branch is never removed"

    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert [item.item_id for item in day.items][:2] == ["ai-01", "energy-01"]

    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "desk-differs-from-vertical.json"))
    old = DigestItem.model_validate(payload)
    assert old.item_id == "energy-9435555854", "a real ten-digit address, read under today's contract"

    new = DigestItem.model_validate({**payload, "item_id": "energy-wfyypy5sgvnwcxd3"})
    assert new.item_id == "energy-wfyypy5sgvnwcxd3"

    for excluded in "ilou":
        with pytest.raises(ValidationError):
            DigestItem.model_validate({**payload, "item_id": f"energy-{excluded}fyypy5sgvnwcxd3"})


def test_the_eval_ledger_columns_are_defined_once() -> None:
    columns = EvalRow.csv_columns()
    assert len(set(columns)) == len(columns)
    for required in ("date", "source_url", "title", "url_key", "band", "version"):
        assert required in columns, "a ledger row must still mean something after a prune"


def test_the_recorded_premise_digest_names_the_article_fixture() -> None:
    """The populated shape, checked against text this repository holds.

    A fixture digest nobody can recompute proves the field parses and nothing
    else. This one is the digest of `article/ok.json`'s sanitized text, so the
    fixture also pins the convention: sha256 over the UTF-8 bytes, all 64 hex
    characters, which is what `text_digest` spells everywhere else.
    """
    source = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    scored = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "premise-recorded.json"))

    assert scored.source_digest == text_digest(source.text or "")
    assert scored.source_digest != scored.output_digest


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
        "shard",
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
        "runner_name",
        "cpu_busy_pct",
        "cpu_busy_max",
        "cpu_busy_min",
        "load_1m",
        "llama_rss_bytes",
        "llama_rss_peak_bytes",
        "python_rss_bytes",
        "cgroup_peak_bytes",
        "model_id",
        "model_quantisation",
        "n_ctx_configured",
        "n_parallel",
        "n_threads",
        "n_batch",
        "max_output_tokens",
        "label_budget_tokens",
        "summary_budget_tokens",
        "run_visual_decision",
        "temperature",
        "failed_field",
        "failed_rule",
    )


def test_the_feed_health_ledger_columns_are_defined_once() -> None:
    """The five columns of 2026-09-02 are appended, so the old header is still a prefix.

    `ledger.require_matching_header` compares the whole list, so a column filed
    beside the one it relates to would put every historical value one place to
    the right under a reader that maps by position. Appending is what keeps the
    narrow header readable as the head of the wide one.
    """
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


def test_a_retirement_names_distinct_runs_and_only_one_cause() -> None:
    """Five failures inside one run is one run's evidence, not five runs' worth.

    `http_410` is the only cause the enum admits, and that is the design rather
    than a starting point: nothing softer than `410 Gone` says the address is
    not coming back (docs/architecture/sources/health.md).
    """
    assert [cause.value for cause in RetirementCause] == ["http_410"]

    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    repeated = row.model_dump(mode="json") | {"evidence_run_ids": ["2026-08-23-1"] * 5}

    with pytest.raises(ValidationError, match="distinct runs"):
        FeedRetirementRow.model_validate(repeated)


def test_a_retirement_row_survives_the_ledger_round_trip() -> None:
    """The evidence list is one cell, so the header cannot grow with the evidence."""
    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    cells = row.csv_row()

    assert cells["evidence_run_ids"].count(" ") == len(row.evidence_run_ids) - 1
    assert "," not in cells["evidence_run_ids"], "a comma would need quoting in a union merge"
    assert FeedRetirementRow.from_csv_row(cells) == row


def test_the_canary_writes_every_column_the_item_health_ledger_defines() -> None:
    """The canary's own copy of the header, held against the contract.

    `frontend/scripts/build-canary.mjs` restates the column names because it is
    JavaScript and the contract is Python. A name added to the row and not to
    that array writes a canary `publish_telemetry` refuses, and until this test
    existed the only thing that caught it was a frontend build in CI.
    """
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == ItemHealthRow.csv_columns()
