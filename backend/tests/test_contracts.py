"""Contract-tier tests: the generated schemas against the models that produced
them, and the models against real committed payloads.

No mocks and no network (Rule #7): every input here is a file in
`tests/fixtures/` or `config/`.
"""

from __future__ import annotations

import ast
import csv
import inspect
import json
import logging
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

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

from idhazh import ledger, source_health
from idhazh.cli import main, stage_validate_days
from idhazh.contracts import canonical_json, derive_url_key
from idhazh.contracts.app_config import (
    PAGES_HARD_CAP_MB,
    SUPERSEDED_COLLECT_NAMES,
    SUPERSEDED_MODELS_NAMES,
    SUPERSEDED_RETENTION_NAMES,
    AppConfig,
    CollectConfig,
    ConsoleConfig,
    EvaluationConfig,
    InferenceConfig,
    ModelsConfig,
    ObservabilityConfig,
    PageWeightConfig,
    RetentionConfig,
    UiConfig,
    VisualSide,
    months_a_window_can_touch,
)
from idhazh.contracts.appearance_config import AppearanceConfig, ChartConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import Contract, StalePayloadError
from idhazh.contracts.console_band import ConsoleBand, ConsoleRoute, RouteId
from idhazh.contracts.console_payloads import CONSOLE_PAYLOADS, payloads_by_stem
from idhazh.contracts.day_metrics import (
    DayBands,
    DayDistribution,
    DayInstrument,
    DayMetrics,
    DayReasons,
    DaySource,
    DayStageTiming,
    DayThroughput,
)
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestVerticalRef, DigestVisual
from idhazh.contracts.digest_view import DigestView, DigestViewItem, DigestViewVisual
from idhazh.contracts.element import (
    JUDGED_FIELDS,
    TIER_ONE_FIELDS,
    TIER_TWO_FIELDS,
    Element,
    ElementKind,
    ElementTable,
    Extractor,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.export import CONTRACTS, expected_filenames, export
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.item_health import (
    FAILURE_CODE_STAGES,
    SOURCE_NEUTRAL_FAILURE_CODES,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.public_eval import PublicEvalRow
from idhazh.contracts.public_feed_health import PublicFeedRow
from idhazh.contracts.public_run_day import PublicRunDay
from idhazh.contracts.public_telemetry import PublicTelemetryRow
from idhazh.contracts.run_manifest import ModelRole, RunManifest, VerticalCount
from idhazh.contracts.run_plan import (
    PUBLISHED_AGE_BANDS,
    PublishedAgeBand,
    RunPlan,
    TimeSource,
    VerticalPlan,
)
from idhazh.contracts.runtime_counters import SERIES, RuntimeCountersRow
from idhazh.contracts.score_archive import ScoreArchive
from idhazh.contracts.sources import Sources
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.contracts.visual import (
    CODE_STAMPED_FIELDS,
    FORBIDDEN_FIELDS,
    MAX_LABELS,
    NUMERIC_FIELDS,
    WORST_CASE_REPLY_CHARACTERS,
    EncodingRole,
    PlanDecision,
    PlanEncodings,
    VisualPlan,
    VisualType,
    numeric_leaves,
    unbounded_leaves,
    worst_case_reply_characters,
)
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.watchlist import EntityKind, Watchlist
from idhazh.extract import TOKENS_PER_WORD
from idhazh.fingerprint import NOT_DIGESTED, digested_inference_fields, text_digest
from idhazh.measured import PROMPT_OVERHEAD_TOKENS as _PROMPT_OVERHEAD
from idhazh.measured import WORST_TOKENS_A_WORD as _WORST_TOKENS
from idhazh.publish_telemetry import PUBLIC_COLUMNS
from idhazh.retention import oldest_month_kept
from utilities import build_canary_day

pytestmark = pytest.mark.contract

BY_STEM: dict[str, type[Contract]] = {c.__schema_stem__: c for c in CONTRACTS}
CONFIG_FILES: dict[str, type[Contract]] = {
    "idhazh.json": AppConfig,
    "sources.json": Sources,
    "taxonomy.json": Taxonomy,
    "watchlist.json": Watchlist,
}
LONG_HEX = re.compile(r"[0-9a-f]{16,}")
#: Four real `GET /metrics` bodies, one per work shard of run `2026-08-26-5`,
#: pulled from that run's `runtime-log-*` artifacts before they expired. Real
#: captures rather than hand-written text (Rule #7): the upstream README at tag
#: b10598 lists neither `prompt_tokens_cached_total` nor the wording that says
#: what `prompt_tokens_total` counts, so only the binary's own output settles it.
METRICS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))
#: The memory sampler's own files and the head of llama-server's own log, one
#: pair per work shard of run `2026-08-29-3`, pulled from that run's
#: `runtime-log-*` artifacts before they expired. Real captures for the same
#: reason the metrics bodies are: the timestamp llama.cpp stamps a log line with
#: is four dot-separated numbers whose units no page states, and only a real
#: capture of a job whose length is known settles which is which.
RSS_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.rss-samples.tsv"))
SERVER_LOG_CAPTURES = sorted((FIXTURES_DIR / "runtime").glob("2026-08-29-3-shard-*.server-head.txt"))
#: One real `/proc/stat` pair, twenty seconds apart, captured on a GitHub-hosted
#: `ubuntu-latest` runner on 2026-08-30. The gap is what makes it an oracle: the
#: tick delta has to reproduce twenty seconds of four processors at 100 Hz, and
#: no hand-written file can be checked that way.
PROC_STAT_AT_START = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-start.txt"
PROC_STAT_AT_END = FIXTURES_DIR / "runtime" / "2026-08-30-probe-proc-stat-at-end.txt"
#: What the probe slept for, what the runner reported to `nproc`, and the
#: kernel's tick rate. Rule #2 fixes the second at 4.
PROBE_SECONDS = 20
PROBE_PROCESSORS = 4
USER_HZ = 100
#: The two pages that spell the item-health failure vocabulary out by hand.
DOC_ITEM_HEALTH = REPO_ROOT / "docs" / "architecture" / "sources" / "item-health.md"
DOC_ONE_URL = REPO_ROOT / "docs" / "how-to" / "troubleshoot-one-url.md"


def backticked(text: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", text))


def paragraph_after(text: str, lead: str) -> str:
    _, found, rest = text.partition(lead)
    assert found, f"the page no longer says {lead!r}"
    return rest.split("\n\n", 2)[1]


# The one `app-config` fixture. Its name is its invariant: every knob in it holds
# a value the committed `config/idhazh.json` does not, so a reader that ignored
# the file and fell back to a default would fail rather than pass.
APP_CONFIG_EVERY_KNOB_DIFFERS: Final = (
    CONTRACT_FIXTURES_DIR / "app-config" / "every-knob-differs-from-the-committed-config.json"
)


def fixture_paths() -> list[Path]:
    return sorted(CONTRACT_FIXTURES_DIR.glob("*/*.json"))


def fixture_id(path: Path) -> str:
    return f"{path.parent.name}/{path.stem}"


def load(path: Path) -> Contract:
    return BY_STEM[path.parent.name].from_json(read_text(path))


# --- The Oracle: round-trip ------------------------------------------------


@pytest.mark.parametrize("path", fixture_paths(), ids=fixture_id)
def test_fixture_round_trips_byte_identically(path: Path) -> None:
    """Serialize, validate, deserialize, re-serialize - same bytes."""
    text = read_text(path)
    once = load(path).to_json()
    assert once == text
    twice = BY_STEM[path.parent.name].from_json(once).to_json()
    assert twice == once


def test_every_contract_has_at_least_one_fixture() -> None:
    covered = {path.parent.name for path in fixture_paths()}
    assert covered == set(BY_STEM), "a contract without a fixture has never been proven to load"


# --- Day facts: additive and non-additive both survive a round trip ---------
#
# Row 21 ships the shape, not the producer or the reader. The generic oracle
# above already round-trips the committed fixture; these build a record in code
# instead of walking committed days (Rule #13), so they can carry the awkward
# case a real archive may never produce - a timed-nothing stage beside timed
# ones, an empty instrument beside a populated one - and prove the two halves of
# Andre's additive/non-additive split read back the way a later reducer needs.


def _day_metrics_sample() -> DayMetrics:
    """One coherent published day, built to satisfy every cross-field invariant."""
    return DayMetrics(
        version=DayMetrics.schema_version(),
        date="2026-08-24",
        revision=5,
        runs=5,
        model_id="qwen35-9b",
        pipeline_fingerprint="a" * 64,
        items_published=6,
        items_planned=8,
        items_failed=2,
        visuals_rendered=2,
        items_truncated=1,
        summaries_scored=5,
        determinism_violations=0,
        extraction_suspect=1,
        sources_present=2,
        addresses_considered=20,
        bands=DayBands(high=4, medium=1, low=1),
        reasons=DayReasons(
            unsupported_number=1,
            not_scored=0,
            lead_missing=1,
            hedge_dropped=0,
            faithfulness=0,
            unattributed=0,
        ),
        throughput=DayThroughput(
            items=5,
            prefill_ms=12000,
            decode_ms=45000,
            input_tokens=21000,
            output_tokens=1800,
            cached_tokens=6000,
        ),
        stage_timing=[
            DayStageTiming(stage=ItemStage.PLAN, timed=0),
            DayStageTiming(
                stage=ItemStage.SUMMARIZE,
                timed=5,
                sum_ms=45000,
                p50_ms=8200,
                p90_ms=12000,
                max_ms=15000,
            ),
        ],
        instruments=[
            DayInstrument(
                column="hhem",
                stat=DayDistribution(
                    count=5, total=4.3, p25=0.78, p50=0.88, p75=0.94, minimum=0.55, maximum=0.99
                ),
            ),
            DayInstrument(column="new_fact_rate", stat=DayDistribution(count=0, total=0.0)),
        ],
        sources=[
            DaySource(source_id="the-hindu", published=4, doubted=1, truncated=1),
            DaySource(source_id="reuters", published=2, doubted=1, truncated=0),
        ],
    )


def test_day_metrics_round_trips_and_a_built_record_reads_back_identically() -> None:
    """A record the producer will write validates, and an additive count and a
    non-additive statistic both read back unchanged (Andre's split)."""
    once = _day_metrics_sample().to_json()
    reloaded = DayMetrics.from_json(once)
    assert reloaded.to_json() == once
    # Additive: stored as the number a reader adds across days.
    assert reloaded.items_published == 6
    assert reloaded.throughput is not None and reloaded.throughput.decode_ms == 45000
    hhem = next(item for item in reloaded.instruments if item.column == "hhem")
    assert hhem.stat.count == 5 and hhem.stat.total == 4.3
    # Non-additive: the day's own value the reader must recombine, not add.
    assert reloaded.sources_present == 2
    assert hhem.stat.p50 == 0.88
    # Decision 4: the revision stamp survives, so a later run can spot a stale record.
    assert reloaded.revision == 5


def test_day_metrics_keeps_an_empty_aggregate_apart_from_a_zero_one() -> None:
    """A timed-nothing stage and an empty instrument keep their absent figures;
    empty is not zero (the all-or-nothing validators), so a reducer never reads a
    missing median as a real 0."""
    reloaded = DayMetrics.from_json(_day_metrics_sample().to_json())
    plan = next(stage for stage in reloaded.stage_timing if stage.stage == ItemStage.PLAN)
    assert plan.timed == 0 and plan.sum_ms is None and plan.p50_ms is None
    empty = next(item for item in reloaded.instruments if item.column == "new_fact_rate")
    assert empty.stat.count == 0 and empty.stat.total == 0.0 and empty.stat.p50 is None


def test_day_metrics_bands_and_reasons_mirror_the_eval_vocabulary() -> None:
    """The day's partitions only hold if its buckets are the eval bands and
    reasons themselves. Coupling them here turns a new band or reason added to
    EvalRow red, rather than letting a doubted item go uncounted."""
    assert set(DayBands.model_fields) == {band.value for band in ConfidenceBand}
    assert set(DayReasons.model_fields) == {reason.value for reason in BandReason} | {"unattributed"}


# --- The Oracle: the span rollup restates no ledger ------------------------
#
# Rule #12 and the telemetry doctrine: the committed span rollup holds a count
# and a duration that no ledger already holds. The check is on column names,
# outside the key, against every committed ledger a span could restate. Item-
# health alone is not enough - the timing a span most resembles is `decision_ms`
# on the visual decision, and the committed-five was chosen around that collision.

#: The key and the stamp a rollup row shares with the ledgers by design - the
#: grain it is filed at, plus the version every contract carries. A shared name
#: here is not a restated measurement, so it is set aside before the check.
_ROLLUP_KEY_AND_STAMP: frozenset[str] = frozenset(
    {"version", "date", "run_id", "shard", "span_name"}
)

#: Every committed ledger a span-rollup row could restate a measurement of, and
#: where it lives. `state/scores/` holds the raw eval rows and, once a month is
#: folded, the archive - a rollup must not restate either.
_LEDGERS_A_ROLLUP_MUST_NOT_RESTATE: dict[str, type[Contract]] = {
    "state/item-health": ItemHealthRow,
    "state/runtime-counters.csv": RuntimeCountersRow,
    "state/scores (raw rows)": EvalRow,
    "state/scores (archived)": ScoreArchive,
    "state/visuals": VisualDecision,
}


def _column_names(contract: type[Contract]) -> frozenset[str]:
    """Every column or field name a ledger spells.

    A CSV ledger row spells its columns in `csv_columns`; a JSON payload like the
    visual decision or the score archive has no CSV form, so its field names are
    what a collision would be measured against.
    """
    columns = getattr(contract, "csv_columns", None)
    if callable(columns):
        return frozenset(columns())
    return frozenset(contract.model_fields)


def _rollup_value_columns() -> frozenset[str]:
    return frozenset(SpanRollupRow.csv_columns()) - _ROLLUP_KEY_AND_STAMP


def test_the_rollup_holds_only_what_no_ledger_holds() -> None:
    value_columns = _rollup_value_columns()
    assert value_columns, "the rollup must carry at least one measurement of its own"
    for where, row_model in _LEDGERS_A_ROLLUP_MUST_NOT_RESTATE.items():
        collision = value_columns & _column_names(row_model)
        assert not collision, f"span-rollup restates {sorted(collision)}, already held by {where}"


def test_the_disjointness_check_catches_a_collision_outside_item_health() -> None:
    """A real collision must turn the Oracle above red, and not only against
    item-health. `decision_ms` is the visual decision's own timing and is absent
    from item-health, so a rollup that named its duration that would be caught
    only by testing state/visuals - which is why the fold commits five span names
    and not the six a naive reading would."""
    assert "decision_ms" in _column_names(VisualDecision)
    assert "decision_ms" not in _column_names(ItemHealthRow)
    pretend_value_columns = _rollup_value_columns() | {"decision_ms"}
    caught = {
        where: sorted(pretend_value_columns & _column_names(row_model))
        for where, row_model in _LEDGERS_A_ROLLUP_MUST_NOT_RESTATE.items()
        if pretend_value_columns & _column_names(row_model)
    }
    assert caught == {"state/visuals": ["decision_ms"]}


# --- The Oracle: two tiers, and only one of them is required ----------------
#
# The element shape splits what code cut out of the bytes from what a labeller
# said about it. Both halves have to be tested. "An element with only its Tier 1
# fields validates" on its own proves nothing, because a shape whose Tier 1
# fields carried defaults would pass it while letting a judgement travel with no
# anchor. The pair is the split.


def _element_payload(path: Path, index: int = 0) -> dict[str, Any]:
    """One element out of a committed table, as a plain dict to mutate."""
    payload: dict[str, Any] = json.loads(read_text(CONTRACT_FIXTURES_DIR / "element-table" / path))
    element: dict[str, Any] = payload["elements"][index]
    return element


def test_an_element_carrying_only_its_tier_one_fields_validates() -> None:
    """The first half of the oracle. Nine keys, no judgement, and it loads."""
    element = {
        name: value
        for name, value in _element_payload(Path("regex-only.json")).items()
        if name in TIER_ONE_FIELDS
    }
    assert set(element) == set(TIER_ONE_FIELDS)
    assert Element.model_validate(element).extractor is Extractor.REGEX


@pytest.mark.parametrize("missing", TIER_ONE_FIELDS)
def test_a_tier_two_field_with_no_tier_one_anchor_is_refused(missing: str) -> None:
    """The second half, and the one that bites. Every Tier 1 field is required,
    so a judged element that has lost any one of its anchors does not load - it
    is not silently accepted with a default standing in for the missing one."""
    element = _element_payload(Path("labelled.json"), index=1)
    assert element["salience"] is not None or element["measure"] is not None
    element.pop(missing)
    with pytest.raises(ValidationError, match=missing):
        Element.model_validate(element)


def test_the_generated_schema_requires_tier_one_and_nothing_else() -> None:
    """The split is machine-checked rather than promised in a docstring."""
    required = ElementTable.json_schema()["$defs"]["Element"]["required"]
    assert sorted(required) == sorted(TIER_ONE_FIELDS)
    assert not set(required) & set(TIER_TWO_FIELDS)


def test_every_element_field_belongs_to_exactly_one_tier() -> None:
    """A field added without a tier is a field with no trust story. The module
    refuses to import in that state; this is the readable half of that guard."""
    assert tuple(Element.model_fields) == TIER_ONE_FIELDS + TIER_TWO_FIELDS
    assert not set(TIER_ONE_FIELDS) & set(TIER_TWO_FIELDS)


def test_the_contract_covers_six_kinds_though_two_have_producers() -> None:
    assert {kind.value for kind in ElementKind} == {
        "quantity",
        "date",
        "entity",
        "place",
        "quote",
        "claim",
    }


# --- The Oracle: span_excerpt is the slice, which is why `raw` cannot be it --


def test_span_excerpt_is_the_verbatim_slice_and_a_cleaned_string_is_refused() -> None:
    """`visual_planner.NumericFact.raw` is `currency + sign + digits`, whitespace
    cleaned, so it drops the magnitude word and the unit. Substituting it for the
    excerpt shortens the string without moving the offsets, and the shape refuses
    that outright - the width of the span and the length of the excerpt are one
    number. This is why one name survives and the third field does not exist."""
    element = _element_payload(Path("regex-only.json"), index=2)
    assert element["span_excerpt"] == "$4.5 billion"
    raw_shaped = dict(element, span_excerpt="$4.5")
    with pytest.raises(ValidationError, match="verbatim slice"):
        Element.model_validate(raw_shaped)


def test_element_id_is_rebuilt_not_trusted() -> None:
    element = _element_payload(Path("regex-only.json"))
    relabelled = dict(element, element_id=f"quantity-0-{element['span_end']}")
    with pytest.raises(ValidationError, match="element_id"):
        Element.model_validate(relabelled)


# --- Invariants the element shape exists to carry ---------------------------


def test_only_a_measured_kind_reads_as_a_value() -> None:
    """A quote has no number, and a shape that let one be written is the shape
    the span exists to make unnecessary."""
    quote = dict(
        _element_payload(Path("labelled.json")),
        kind="quote",
        entity=None,
        salience=None,
        label_source=None,
        ledger_version=None,
        value="7",
    )
    quote["element_id"] = f"quote-{quote['span_start']}-{quote['span_end']}"
    with pytest.raises(ValidationError, match="value"):
        Element.model_validate(quote)


def test_a_date_may_not_carry_a_resolved_relative_reference() -> None:
    """"Three years ago" resolves against a publication date the article never
    wrote. The grammar refuses it at the shape, so no producer can write one by
    accident."""
    date_element = _element_payload(Path("regex-only.json"), index=1)
    assert date_element["kind"] == "date"
    with pytest.raises(ValidationError, match="value"):
        Element.model_validate(dict(date_element, value="three years ago"))


def test_a_judged_field_names_who_judged_it() -> None:
    """Tier 2 is a claim somebody made. A claim with no author cannot be measured
    later, and an author with no claim is a record of nothing."""
    judged = _element_payload(Path("labelled.json"), index=1)
    with pytest.raises(ValidationError, match="label_source"):
        Element.model_validate(dict(judged, label_source=None, ledger_version=None))
    unjudged = {
        name: value for name, value in judged.items() if name not in set(JUDGED_FIELDS)
    }
    with pytest.raises(ValidationError, match="label_source"):
        Element.model_validate(unjudged | {"label_source": "qwen35-9b"})


def test_a_span_past_the_end_of_the_text_is_refused() -> None:
    """The table carries the length of the string its spans index, so the shape
    can refuse an offset that points nowhere without holding the text."""
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["source_text_length"] = payload["elements"][0]["span_end"] - 1
    with pytest.raises(ValidationError, match="ends past"):
        ElementTable.model_validate(payload)


def test_one_kind_and_one_span_is_one_fact() -> None:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["elements"] = [payload["elements"][0], dict(payload["elements"][0])]
    with pytest.raises(ValidationError, match="one address"):
        ElementTable.model_validate(payload)


def test_the_table_reads_in_the_order_the_article_was_written() -> None:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    payload["elements"] = list(reversed(payload["elements"]))
    with pytest.raises(ValidationError, match="span_start"):
        ElementTable.model_validate(payload)


def test_the_element_table_holds_one_hash_for_the_whole_article() -> None:
    """Decision 6, made mechanical: the hash is a field of the table and no
    element carries one. A per-element hash would be redundant against this plus
    the re-slice, on every article for ever."""
    assert "source_text_hash" in ElementTable.model_fields
    assert not [name for name in Element.model_fields if "hash" in name]


# --- The Oracle: the width of a span is not the characters in it ------------
#
# Row 1 checks that `span_excerpt` is as wide as its span, which refuses a
# whitespace-cleaned string outright. Row 4 is the half that check cannot reach:
# the text is not in the payload, so the shape can compare two numbers and never
# two strings. `span_drift` takes the text and cuts it.


def _element_table_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "element-table" / "regex-only.json")
    )
    return payload


def _text_the_table_indexes(payload: dict[str, Any]) -> str:
    """A string of the length the table names, with every excerpt at its own offset."""
    characters = ["."] * payload["source_text_length"]
    for element in payload["elements"]:
        characters[element["span_start"] : element["span_end"]] = element["span_excerpt"]
    return "".join(characters)


def test_a_committed_table_re_slices_against_the_text_its_spans_describe() -> None:
    """The invariant at rest. Without this the two tests below prove nothing."""
    payload = _element_table_payload()
    assert ElementTable.model_validate(payload).span_drift(_text_the_table_indexes(payload)) is None


def test_a_same_width_excerpt_passes_the_shape_and_fails_the_re_slice() -> None:
    """What row 4 adds over row 1, in one comparison.

    `1,200 Mw` is exactly as wide as `1,200 MW`, so the width check has nothing
    to say about it and the element loads. It is still not the characters the
    span holds, and a figure drawn from it would carry an excerpt the article
    never wrote.
    """
    payload = _element_table_payload()
    text = _text_the_table_indexes(payload)
    payload["elements"][0]["span_excerpt"] = "1,200 Mw"

    misread = ElementTable.model_validate(payload)
    assert misread.elements[0].span_excerpt == "1,200 Mw", "the shape accepts it"
    drift = misread.span_drift(text)
    assert drift is not None
    assert drift.startswith(misread.elements[0].element_id)


def test_a_text_that_moved_by_one_character_names_the_first_span_that_moved() -> None:
    """The reason is a log line, so it carries no fetched bytes (Rule #11) - the
    element's own address and the two lengths, which say what moved and by how
    much without quoting a stranger's page back at an operator."""
    payload = _element_table_payload()
    table = ElementTable.model_validate(payload)
    moved = " " + _text_the_table_indexes(payload)

    drift = table.span_drift(moved)
    assert drift is not None
    assert drift.startswith(table.elements[0].element_id)
    assert f"{table.source_text_length} characters" in drift
    assert str(len(moved)) in drift
    assert table.elements[0].span_excerpt not in drift


def test_the_re_slice_added_no_field_to_the_persisted_shape() -> None:
    """The text a span indexes is not in the payload and is not going into it -
    `span_excerpt` is article body text, which no published payload may carry
    (`CLAUDE.md` section 0a). So the check is a method over a text the caller
    already holds, and the shape did not have to move for it."""
    assert callable(ElementTable.span_drift)
    assert "span_drift" not in ElementTable.model_fields
    assert "text" not in ElementTable.model_fields


# --- The visual plan: four prohibitions, each asserted on its own -----------
#
# One combined test passes while three of the four are unenforced, so each gets
# its own arm and each arm names the thing it refuses. Every payload here is a
# committed fixture with one field changed (Rule #7, Rule #12) - nothing walks a
# collection a run appends to.


def _plan_payload(name: str = "bar-chart") -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "visual-plan" / f"{name}.json")
    )
    return payload


def test_a_plan_of_references_and_closed_names_loads() -> None:
    """The happy path, without which the four refusals below prove nothing."""
    plan = VisualPlan.model_validate(_plan_payload())
    assert plan.decision is PlanDecision.VISUAL
    assert plan.type is VisualType.BAR
    drawn = set(plan.labels) | set(plan.annotations)
    drawn |= {i for ids in plan.encodings.filled().values() for i in ids}
    assert drawn <= set(plan.element_ids), "everything drawn is an element the plan declared"


def test_a_plan_carrying_geometry_does_not_load() -> None:
    """Prohibition 1. A pixel binds the plan to one renderer, so there is nowhere
    to put one: geometry is a number, and the schema admits exactly one number."""
    for pixel in ("canvas_width", "x", "y", "width", "font_size", "axis_max"):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            VisualPlan.model_validate(_plan_payload() | {pixel: 800})
    assert numeric_leaves() == NUMERIC_FIELDS == {"confidence"}


def test_a_plan_carrying_a_literal_number_does_not_load() -> None:
    """Prohibition 2. A bar height is reached by citing an element, so the worst
    an injection can do is pick the wrong bars rather than draw the wrong figure.

    Two arms, because the ways in differ: a new field is refused as an unknown
    key, and a number pushed into a reference field is refused by its type.
    """
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualPlan.model_validate(_plan_payload() | {"values": [4200, 3100]})
    with pytest.raises(ValidationError, match="element_ids"):
        VisualPlan.model_validate(_plan_payload() | {"element_ids": [4200, 3100]})
    assert VisualPlan.model_fields["confidence"].metadata, "the one number is bounded to 0..1"
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        VisualPlan.model_validate(_plan_payload() | {"confidence": 4200.0})


def test_a_plan_carrying_authored_text_does_not_load() -> None:
    """Prohibition 3, the half the shape can carry. Code cuts every character a
    reader sees off a chart, so what names a mark is an element reference and a
    typed string is refused by grammar rather than caught by a check."""
    payload = _plan_payload()
    with pytest.raises(ValidationError, match="labels"):
        VisualPlan.model_validate(payload | {"labels": ["Wind capacity, MW"]})
    with pytest.raises(ValidationError, match="annotations"):
        VisualPlan.model_validate(payload | {"annotations": ["the tallest bar"]})
    encodings = payload["encodings"] | {"category": ["Denmark", "Germany"]}
    with pytest.raises(ValidationError, match="encodings"):
        VisualPlan.model_validate(payload | {"encodings": encodings})


def test_a_plan_that_omits_a_role_does_not_load() -> None:
    """Every role name is a key and the decoder may not skip one.

    Optional arrays produced "a confident chart with no bars in it", twice, on
    the first live run - a plan that names `bar` and simply leaves `quantity`
    out reads as a complete answer. Presence is the whole guarantee this shape
    makes: what a `bar` may leave empty is the validator's rule, and a validator
    cannot rule on a key it never received.
    """
    payload = _plan_payload()
    for role in EncodingRole:
        short = {name: ids for name, ids in payload["encodings"].items() if name != role.value}
        with pytest.raises(ValidationError, match=rf"encodings\.{role.value}\b"):
            VisualPlan.model_validate(payload | {"encodings": short})
    with pytest.raises(ValidationError, match="encodings"):
        VisualPlan.model_validate({k: v for k, v in payload.items() if k != "encodings"})


def test_a_role_the_type_cannot_use_is_present_and_empty() -> None:
    """The other half: an inapplicable role loads as `[]` rather than failing.

    A bar has no bins, no size and no second measured axis, so the four-bar
    fixture carries seven empty channels beside its two filled ones. The shape
    accepts every combination it can spell, including one no type would ever
    draw, because ruling which roles a `bar` may fill needs the type's own rule
    set - and that is the validator's, not the schema's.
    """
    payload = _plan_payload()
    assert set(payload["encodings"]) == {role.value for role in EncodingRole}
    plan = VisualPlan.model_validate(payload)
    assert set(plan.encodings.filled()) == {EncodingRole.CATEGORY, EncodingRole.QUANTITY}
    assert plan.encodings.bins == [] and plan.encodings.size == []
    absurd = payload["encodings"] | {"bins": payload["encodings"]["quantity"]}
    assert VisualPlan.model_validate(payload | {"encodings": absurd}).encodings.bins, (
        "a bar with bins in it is a plan the validator refuses and the shape spells"
    )


def test_the_role_vocabulary_and_the_channels_are_one_list_in_one_order() -> None:
    """Two spellings of one list, and the decoder is held to the second.

    The validator reads roles as data off the enum; the model is held to the
    object's fields. Order as well as names, because field order is decode order
    here as it is on the plan itself.
    """
    assert tuple(PlanEncodings.model_fields) == tuple(role.value for role in EncodingRole)
    channels = VisualPlan.json_schema()["$defs"]["PlanEncodings"]
    # `canonical_json` sorts keys, so `required` is the only place in the committed
    # document where the declared order - and so the decode order - survives.
    assert channels["required"] == [role.value for role in EncodingRole]
    assert channels["additionalProperties"] is False, "a role the vocabulary lacks is not a role"


def test_naming_a_mark_has_one_home_and_it_is_not_a_role() -> None:
    """There is no `label` role, and section 12.8 X2 lists one - so this is the
    assertion that keeps the call made rather than re-opened.

    `labels` is the one naming channel: the elements whose own characters name
    the marks and the axes, eight marks and two axes. A `label` role would ask a
    model the same question a second time inside `encodings`, and a model that
    answers twice can answer two ways with no fact to settle which. `event_label`
    is not the same thing - a timeline's `time` channel places a dot and nothing
    else, so the event text is the mark rather than a name for one.
    """
    assert "label" not in PlanEncodings.model_fields
    assert "label" not in {role.value for role in EncodingRole}
    assert "labels" in VisualPlan.model_fields
    assert MAX_LABELS == 10, "eight marks and two axes, which is what naming a mark is for"


def test_required_but_empty_roles_cost_what_the_module_says_they_cost() -> None:
    """Every role being a key is paid for on every reply, so the price is checked.

    Characters are the half a test can hold, and they are exact. The token
    figure beside them in the module docstring came from `llama-tokenize` against
    the Qwen3 vocabulary, which needs weights this repository does not commit
    (Rule #2), so it is recorded there with its hardware and date instead.
    """
    cost = {}
    for stem in ("bar-chart", "declined"):
        body = {
            name: value
            for name, value in _plan_payload(stem).items()
            if name not in CODE_STAMPED_FIELDS
        }
        lean = body | {"encodings": {r: ids for r, ids in body["encodings"].items() if ids}}
        dumped = (json.dumps(b, separators=(",", ":"), sort_keys=True) for b in (body, lean))
        whole, without = (len(text) for text in dumped)
        cost[stem] = whole - without
    assert cost == {"bar-chart": 87, "declined": 114}


def test_a_plan_carrying_alt_text_does_not_load() -> None:
    """Prohibition 4. The compiler assembles alt text out of the element values
    it already holds; the model writing it would be one prose channel restating
    the chart's own data, which no validator can read."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VisualPlan.model_validate(_plan_payload() | {"alt_text": "A bar chart of wind capacity."})
    assert FORBIDDEN_FIELDS == {"alt_text"}
    assert FORBIDDEN_FIELDS.isdisjoint(VisualPlan.model_fields), (
        "the field is named rather than merely absent, so a later widening does not start"
    )


def test_every_decoded_array_and_string_in_the_plan_is_bounded() -> None:
    """A bound with no total is half a decision, so this is what makes the
    worst-case arithmetic in the module docstring true rather than intended.

    `version` is the one exception and it is not decoded: the base contract
    stamps it on read, so no reply spends a character on it.
    """
    assert unbounded_leaves() == {"version"}
    with pytest.raises(ValidationError, match="element_ids"):
        VisualPlan.model_validate(
            _plan_payload() | {"element_ids": [f"quantity-{n}-{n + 4}" for n in range(99)]}
        )


def test_confidence_decodes_after_the_type() -> None:
    """Field order is decode order. Second in the list a confidence conditions
    every field after it, and the model reads its own hedge back as evidence."""
    order = list(VisualPlan.model_fields)
    assert order.index("confidence") > order.index("type")
    assert order.index("purpose") < order.index("type"), "the form is chosen for a reason"


def test_a_plan_that_declines_draws_nothing() -> None:
    """`none` is the common and correct answer, and it is a decision rather than
    an absence - a refusal that carries half a chart is two answers to one
    question."""
    declined = VisualPlan.model_validate(_plan_payload("declined"))
    assert declined.decision is PlanDecision.NONE
    assert declined.why, "a refusal still says why"
    with pytest.raises(ValidationError, match="declines carries no type"):
        VisualPlan.model_validate(_plan_payload("declined") | {"type": "bar"})
    with pytest.raises(ValidationError, match="proposes a visual states its title"):
        VisualPlan.model_validate(_plan_payload() | {"title": None})


def test_a_plan_may_not_draw_an_element_it_never_declared() -> None:
    """The cheap half of "every element exists", asked of the payload alone: a
    role citing an id the plan did not list is the plan disagreeing with itself.
    Whether the id names a real element is the validator's question."""
    payload = _plan_payload()
    with pytest.raises(ValidationError, match="did not declare"):
        VisualPlan.model_validate(payload | {"labels": ["quantity-9001-9008"]})


def test_the_worst_case_reply_length_is_arithmetic_and_the_fixtures_are_a_fraction_of_it() -> None:
    """Row 14's bounds buy one number, and this is the number.

    The ceiling is recomputed from the generated schema, so a bound that moves
    without the docstring's table moving with it fails at import. The two
    committed plans are measured beside it, because a ceiling nothing is
    compared against says nothing about what a reply actually costs.
    """
    assert worst_case_reply_characters() == WORST_CASE_REPLY_CHARACTERS == 3767
    measured = {}
    for stem in ("bar-chart", "declined"):
        decoded = {
            name: value
            for name, value in _plan_payload(stem).items()
            if name not in CODE_STAMPED_FIELDS
        }
        measured[stem] = len(json.dumps(decoded, separators=(",", ":"), sort_keys=True))
    assert measured == {"bar-chart": 838, "declined": 368}
    assert max(measured.values()) < WORST_CASE_REPLY_CHARACTERS // 4


# --- The drift gate --------------------------------------------------------


def test_committed_schemas_match_the_models(tmp_path: Path) -> None:
    export(tmp_path)
    for contract in CONTRACTS:
        name = contract.schema_filename()
        assert read_text(SCHEMAS_DIR / name) == read_text(tmp_path / name), (
            f"{name} is stale - edit the Pydantic model and regenerate, never the schema"
        )


def test_schemas_directory_holds_exactly_the_generated_files() -> None:
    on_disk = {path.name for path in SCHEMAS_DIR.glob("*.json")}
    assert on_disk == expected_filenames()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_schema_is_self_describing(contract: type[Contract]) -> None:
    schema: dict[str, Any] = json.loads(read_text(SCHEMAS_DIR / contract.schema_filename()))
    assert schema["$id"] == contract.schema_filename(), "$id is a relative filename, never a URL"
    assert schema["version"] == schema["changelog"][0]["version"]
    versions = [entry["version"] for entry in schema["changelog"]]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions)
    for entry in schema["changelog"]:
        assert entry["change"] and entry["why"]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__schema_stem__)
def test_version_defaults_to_the_newest_changelog_entry(contract: type[Contract]) -> None:
    assert contract.schema_version() == contract.__changelog__[0].version


def test_an_older_payload_still_validates() -> None:
    """A payload yesterday's run wrote must load today, or it is a release blocker."""
    path = CONTRACT_FIXTURES_DIR / "summary" / "ok.json"
    payload = json.loads(read_text(path))
    payload["version"] = "2026-01-01"
    assert load_summary(payload).version == "2026-01-01"


def load_summary(payload: dict[str, Any]) -> Contract:
    return BY_STEM["summary"].model_validate(payload)


def test_a_payload_written_before_a_field_existed_still_reads() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    A payload from before the summarizer wrote titles has no `title` key at all.
    It must still load, and its committed `output_digest` must still verify -
    which it does because a null title is left out of the digested payload
    rather than digested as null.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["title"]
    assert load_summary(payload).title is None  # type: ignore[attr-defined]


def test_version_is_stamped_when_a_writer_omits_it() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    del payload["version"]
    assert load_summary(payload).version == BY_STEM["summary"].schema_version()


def test_a_manifest_written_before_the_verbosity_knob_still_reads() -> None:
    """Section 11's release blocker, for the other document the knob reached.

    `log_verbosity` landed on the embedded inference block on 2026-09-09, so
    every manifest published before that day has no such key. The claim that
    those still read is only worth making if something removes the key and
    checks - the canonical fixture carries it, so the fixture alone proves the
    new shape and nothing about the old one.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    stripped = 0
    for run in payload["runs"]:
        for use in run["models"]:
            del use["model_ref"]["inference"]["log_verbosity"]
            stripped += 1
    assert stripped, "the fixture stopped carrying an inference block, so this proves nothing"

    manifest = RunManifest.model_validate(payload)
    for run in manifest.runs:
        for use in run.models:
            assert use.model_ref.inference.log_verbosity is None


# --- Config ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CONFIG_FILES), ids=lambda n: n)
def test_config_file_validates(name: str) -> None:
    CONFIG_FILES[name].from_json(read_text(CONFIG_DIR / name))


def test_a_fresh_clone_runs_on_the_defaults() -> None:
    """Every knob but the model refs has a default, so an empty config is usable."""
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    minimal = AppConfig.model_validate({"models": committed.models.model_dump()})
    assert minimal.run.safety_ceiling_per_run == committed.run.safety_ceiling_per_run
    assert minimal.retention.image_months == -1, "retention ships disabled"
    assert minimal.retention.dry_run is True
    assert minimal.retention.pages_hard_cap_mb == PAGES_HARD_CAP_MB, (
        "an unconfigured clone enforces the platform's own ceiling"
    )


def test_the_config_refuses_a_pages_cap_above_the_platforms_own() -> None:
    """The direction the bound exists for. A cap config can raise is not a cap.

    Rule #2 says the budget is the platform and not a preference. That held while
    the 1024 was a module constant only because nobody edited it, which is not a
    control. It is a control now: the schema refuses the edit, and the message
    names the number it refused, so an operator reading it learns the bound
    rather than only that the file is wrong.
    """
    with pytest.raises(ValidationError) as raised:
        RetentionConfig(pages_hard_cap_mb=PAGES_HARD_CAP_MB + 1)
    assert "less than or equal to 1024" in str(raised.value)

    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["retention"]["pages_hard_cap_mb"] = 2048
    with pytest.raises(ValidationError) as from_file:
        AppConfig.model_validate(raw)
    assert "pages_hard_cap_mb" in str(from_file.value)
    assert "1024" in str(from_file.value)


def test_the_config_takes_a_pages_cap_below_the_platforms_own() -> None:
    """The other arm, and the reason the field is here at all.

    A bound only tested in the direction it permits is not a bound - it is a
    default nobody has pushed on. Lowering is the whole use: it buys an earlier
    and louder failure while there is still headroom to act in. The tuned fixture
    carries 900 so a lowered cap is exercised by every round trip, not only here.
    """
    assert RetentionConfig(pages_hard_cap_mb=1).pages_hard_cap_mb == 1

    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["retention"]["pages_hard_cap_mb"] = 512
    assert AppConfig.model_validate(raw).retention.pages_hard_cap_mb == 512

    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS))
    assert tuned.retention.pages_hard_cap_mb == 900


def test_the_alarm_point_and_the_pages_cap_stay_two_knobs() -> None:
    """One reports and one stops, so one number cannot do both jobs.

    Collapsing them gives a warning nobody may ignore or a failure that arrives
    with no notice. The committed file spells both, 224 MB apart, and the tuned
    fixture moves them independently - which is the shape that proves they are
    two instruments rather than one written twice.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).retention
    assert committed.site_budget_mb == 800
    assert committed.pages_hard_cap_mb == PAGES_HARD_CAP_MB
    assert committed.site_budget_mb < committed.pages_hard_cap_mb

    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS)).retention
    assert (tuned.site_budget_mb, tuned.pages_hard_cap_mb) == (600, 900)


def test_the_runtime_counters_are_on_without_being_asked_for() -> None:
    """A run that did not count is a run that cannot say how close it came.

    llama-server publishes the context high watermark only under `--metrics`.
    Off by default would mean the number exists on the runs nobody thought to
    switch it on for, which is every ordinary day.

    The fresh-clone arm drops the settings block and the weights digest
    together. Those two move as a pair now: an entry that names measured bytes
    under a block declared for nothing is refused.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    models = committed.models.model_dump()
    for entry in models.values():
        del entry["inference"]
        entry["sha256"] = None
    fresh = AppConfig.model_validate({"models": models})

    assert fresh.models.summarize.inference.metrics is True, "a fresh clone must count"
    assert committed.models.summarize.inference.metrics is True, "the committed config must count"


def test_the_wider_window_is_the_summarizers_alone() -> None:
    """Row 3 raised one role, because one role is what was measured.

    The visual planner is different weights with its own settings block, and
    nothing has put a 16,384 window in front of them - so it keeps 8,192. That
    is the whole reason the block sits on the entry rather than on `models`:
    a number measured against one model may not be inherited by another.

    Attention is pinned in the same file. `auto` is a runtime autodetect that
    may resolve differently on other silicon, and a run that cannot name the
    kernel it used cannot be compared with one that can (Rule #10).
    """
    models = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models

    assert models.summarize.inference.n_ctx == 16384
    assert models.summarize.inference.flash_attention == "on"
    assert models.visual_planner.inference.n_ctx == 8192
    assert InferenceConfig().n_ctx == 8192, (
        "the default is the conservative window for weights nobody has measured"
    )


#: What the summarize prompt costs before a word of the article reaches it, and
#: the hardest any published item has tokenized. Both records, their method and
#: what to do when either moves are in `idhazh.measured`.
PROMPT_OVERHEAD_TOKENS: Final = int(_PROMPT_OVERHEAD.value)
WORST_TOKENS_A_WORD: Final = _WORST_TOKENS.value


def _worst_sequence_tokens(committed: AppConfig) -> tuple[int, int]:
    """The longest prompt the cap allows, and that prompt plus a full answer.

    One derivation because the serving window and the training window have to
    agree about it. The cap is spent as words at `TOKENS_PER_WORD`, so an
    article whose prose tokenizes harder than that overruns the budget its own
    cap gave it, and both windows have to cover the article that did rather than
    the one that behaved.
    """
    inference = committed.models.summarize.inference
    cut_words = int(committed.extract.truncation_cap_tokens / TOKENS_PER_WORD)
    worst_prompt = PROMPT_OVERHEAD_TOKENS + int(cut_words * WORST_TOKENS_A_WORD)
    return worst_prompt, worst_prompt + inference.max_output_tokens


def test_the_longest_article_the_cap_allows_still_fits_the_window() -> None:
    """The cap and the window are one decision, and this is where they meet.

    Both sides are read from `config/` (Rule #6), so the assertion survives the
    next move of either. It is the guard that was missing on 2026-09-09: the cap
    went from 5,000 to 10,000 tokens that day and could not have, at the 8,192
    window committed the day before - 14,089 tokens against 8,192 is 172 percent
    of it. Nothing in the tree said so. A doc said so, and a doc does not fail.

    The worst case is built from the measured expansion rather than from
    `TOKENS_PER_WORD`. At the committed cap of 10,000 that is 997 + 12,191 + 900
    = 14,088 tokens of 16,384, which is 86 percent and a margin of 1.16x.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    inference = committed.models.summarize.inference
    worst_prompt, worst_sequence = _worst_sequence_tokens(committed)

    assert worst_sequence <= inference.n_ctx, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through is "
        f"{worst_prompt} prompt tokens, and {inference.max_output_tokens} of answer "
        f"puts the sequence at {worst_sequence} against a window of {inference.n_ctx}. "
        "Raise models.summarize.inference.n_ctx beside the cap, or lower the cap."
    )


def test_the_training_window_covers_the_longest_row_the_cap_allows() -> None:
    """The same sum again, against the window a training session opens.

    A training row is a prompt the pipeline could have sent and an answer it
    could have returned, so it is the same sequence the test above sizes - and
    `finetune.sequence_length` short of it does not fail loudly. The wrangler and
    the notebook DROP an over-length row and count it, never truncate it, which
    is the right refusal and a silent one: at 8,192 against a 10,000-token cap
    the training set lost every article past about 5,500 words while production
    went on summarizing them.

    So the failure this catches is not a crash. It is a model tuned on the short
    half of its own job, found a session too late.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    _, worst_sequence = _worst_sequence_tokens(committed)
    window = committed.finetune.sequence_length

    assert worst_sequence <= window, (
        f"the longest article extract.truncation_cap_tokens "
        f"({committed.extract.truncation_cap_tokens}) lets through makes a "
        f"{worst_sequence}-token training row against finetune.sequence_length of "
        f"{window}, so the wrangler and the notebook would drop it and say so in a "
        "line nobody reads until the adapter is short. Raise "
        "finetune.sequence_length beside the cap, or lower the cap."
    )


def test_a_wider_window_moves_the_stamp_and_the_verbosity_does_not() -> None:
    """The two halves of row 3's digest decision, in one place.

    `n_ctx` is digested, so raising it stamps the work apart from every summary
    written at 8,192 - which is correct, because the prompt those summaries were
    written under could not have carried as much. `log_verbosity` is not, because
    a log level cannot move a logit and digesting it would have invalidated every
    earlier identity the day somebody turned the logging up.
    """
    assert "n_ctx" in digested_inference_fields()
    assert "log_verbosity" in NOT_DIGESTED
    assert NOT_DIGESTED["log_verbosity"].moves_logits is False


def test_the_console_chart_size_is_a_knob_the_frontend_agrees_with() -> None:
    """A prerendered chart has no element to measure, so the size is given to it.

    Three copies of one number, and the test has to hold the two that decide the
    picture. Until 2026-09-05 it held the wrong pair: it compared the contract
    default against `config/idhazh.json` and then against the frontend's own
    fallback, and all three were 600 - while every console page drew at 760,
    because `consoleConfig()` merges `config/appearance.json` last and that file
    said 760. A green gate over three copies of a number nothing draws with is
    worse than no gate, because it reads as coverage.

    So the resolved value leads. `config/appearance.json` is the last merge
    layer, so what it declares is what the server draws at, and a clone with no
    `config/` has to draw the same picture - which means the contract default
    and the frontend's fallback have to be that same number, or a first paint
    somewhere is at a width nothing measured.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    fresh = ConsoleConfig()
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")

    for field in ("chart_width", "chart_height"):
        shipped = getattr(drawn, field)
        assert getattr(fresh, field) == shipped, (
            f"config/appearance.json draws a console chart at {field}={shipped} and a "
            f"clone with no config/ would draw it at {getattr(fresh, field)}"
        )
        mirrored = re.search(rf"{field}:\s*(\d+)", reader)
        assert mirrored is not None, f"the frontend console defaults dropped {field}"
        assert int(mirrored.group(1)) == shipped, (
            f"the frontend's own {field} fallback is {mirrored.group(1)} and the "
            f"console draws at {shipped}"
        )


def test_a_console_chart_may_not_be_narrower_than_its_own_labels() -> None:
    with pytest.raises(ValueError):
        AppConfig.model_validate({"console": {"chart_width": 0}})


def test_the_window_the_console_opens_on_is_one_the_control_can_name() -> None:
    """A default outside the preset list opens the page on a window nothing selects.

    The control is four radio buttons, so a span that is not one of them leaves
    every button unchecked and the operator with no way back to what he is
    looking at.
    """
    with pytest.raises(ValidationError, match="window_presets"):
        ConsoleConfig(default_window_days=21)

    tuned = ConsoleConfig(default_window_days=21, window_presets=[7, 21, 60])
    assert tuned.default_window_days in tuned.window_presets


def test_a_preset_list_that_is_out_of_order_or_out_of_bounds_is_refused() -> None:
    """The presets are the only way the page sets its span.

    So `min_window_days` and `max_window_days` have no other reader, and a
    preset outside them would make both knobs decorative.

    The out-of-bounds arm names its own `min_window_days` rather than leaning on
    the default. The default was 7 until 2026-09-06 and is 1 now, so a case
    written as `[3, 30]` against the default stopped being out of bounds without
    anything about the rule changing - a test that reads as a bound check and
    silently becomes a no-op.
    """
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[30, 7, 90], default_window_days=30)
    with pytest.raises(ValidationError, match="ascending and distinct"):
        ConsoleConfig(window_presets=[7, 7, 30], default_window_days=30)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[3, 30], default_window_days=30, min_window_days=7)
    with pytest.raises(ValidationError, match="min_window_days and max_window_days"):
        ConsoleConfig(window_presets=[30, 400], default_window_days=30)


def test_the_console_window_presets_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem the chart size has, one field along.

    The frontend keeps its own console defaults so a fresh clone renders with no
    `config/`. If the two lists drift, the page draws a button for a window the
    contract would refuse.

    The committed list leads for the same reason it does above: it is the last
    merge layer, so it is the list the control really offers. Measured
    2026-09-06, all three copies read `[1, 7, 14, 30, 90]` - unlike the chart
    size, this one has never drifted.
    """
    offered = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json")).console
    assert offered.window_presets == ConsoleConfig().window_presets, (
        "config/appearance.json offers a window list a clone with no config/ would not"
    )

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"window_presets:\s*\[([\d,\s]+)\]", reader)
    assert mirrored is not None, "the frontend console defaults dropped window_presets"
    assert [int(part) for part in mirrored.group(1).split(",")] == offered.window_presets


def test_the_windows_and_the_reading_marks_are_the_spans_the_committed_config_names() -> None:
    """The six spans row 1 of the constant-cost-reads plan settled, read off disk.

    Each is asserted against `config/` rather than against the model, because a
    default and a committed value are two different facts and only the second is
    what ships. The console reads its window out of `config/appearance.json`,
    which is the last merge layer, and `config/idhazh.json` still carries the
    keys it carried before the split - so where both files name a span, both are
    read here and the pair has to agree.

    Why each number is what it is belongs in the field descriptions and in the
    changelog entry dated 2026-09-06T14:00. This test only holds them still.
    """
    drawn = AppearanceConfig.from_json(read_text(CONFIG_DIR / "appearance.json"))
    legacy = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))

    assert 1 in drawn.console.window_presets, (
        "the console offers no one-day window, so the cheapest read it can do - one "
        "month file and the run that just finished - is unreachable"
    )
    assert drawn.console.min_window_days == 1
    assert drawn.console.max_window_days == 366, (
        "max_window_days is a retention floor: lowering it makes no page cheaper and "
        "authorises deleting month shards the console can still ask for"
    )
    assert drawn.digest.read_mark_days == 14
    assert drawn.digest.archive_recent_days == 14, (
        "the archive lists a different span from the one read marks survive, so it "
        "offers days that come back looking unread"
    )
    assert drawn.digest.read_mark_days == drawn.digest.archive_recent_days

    assert legacy.ui.read_mark_days == drawn.digest.read_mark_days
    assert legacy.console.min_window_days == drawn.console.min_window_days
    assert legacy.console.max_window_days == drawn.console.max_window_days

    # The two knobs this row minted. Nothing reads either yet - rows 8 and 25 of
    # TODO/20260906-constant-cost-reads-plan.md do - so the committed value and
    # the bounds either side of it are the whole of what can be checked today.
    assert drawn.digest.offline_bytes_kept == 20_000_000
    assert drawn.digest.archive_window_days in drawn.console.window_presets


def test_the_offline_cache_takes_a_byte_ceiling_that_can_still_hold_one_day() -> None:
    """A day count cannot bound bytes, and a byte bound must fit a day.

    Measured 2026-09-02 over the 12 served days, one day payload runs 8,231 to
    1,373,593 bytes - a factor of 167 - so fourteen days is anything between
    115 KB and 19 MB and `offline_days_kept` promises the reader nothing about
    size. The floor is what stops the cure being worse: a ceiling under the
    largest day evicts that day as fast as it arrives, so the reader pays the
    download and keeps nothing. The ceiling stops a config edit quietly taking a
    tenth of a gigabyte of somebody's phone.
    """
    for refused in (0, 1_999_999, 100_000_001):
        with pytest.raises(ValidationError, match="offline_bytes_kept"):
            UiConfig(offline_bytes_kept=refused)
    assert UiConfig(offline_bytes_kept=2_000_000).offline_bytes_kept == 2_000_000
    assert UiConfig(offline_bytes_kept=100_000_000).offline_bytes_kept == 100_000_000
    assert UiConfig().offline_bytes_kept == 20_000_000
    assert UiConfig().offline_bytes_kept > 1_373_593, (
        "the ceiling is under the largest day payload measured, so the cache would "
        "evict every large day the moment it arrived"
    )


def test_the_archive_window_names_a_span_the_console_presets_already_offer() -> None:
    """One list of spans in the contract, not two.

    The archive gets a window control in row 25 of
    TODO/20260906-constant-cost-reads-plan.md, and it reuses the console's
    presets. So `archive_window_days` names a member of that list rather than
    declaring a second list of day counts, and both documents refuse a file
    where it does not - which is the same rule `console.default_window_days`
    has had since 2026-08-29.

    Both documents are exercised, because a check on only one of them would pass
    on the file the console does not read. The cost is stated rather than
    hidden: a config that narrows the presets now has to name the archive's span
    inside the narrowed list, exactly as it already had to for
    `default_window_days`.
    """
    appearance = json.loads(read_text(CONFIG_DIR / "appearance.json"))
    narrowed = {
        **appearance,
        "console": {**appearance["console"], "window_presets": [7, 60], "default_window_days": 7},
    }
    with pytest.raises(ValidationError, match="archive_window_days"):
        AppearanceConfig.model_validate(narrowed)
    named = {**narrowed, "digest": {**narrowed["digest"], "archive_window_days": 60}}
    assert AppearanceConfig.model_validate(named).digest.archive_window_days == 60

    pipeline = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    narrowed = {
        **pipeline,
        "console": {**pipeline["console"], "window_presets": [7, 60], "default_window_days": 7},
    }
    with pytest.raises(ValidationError, match="archive_window_days"):
        AppConfig.model_validate(narrowed)
    named = {**narrowed, "ui": {**narrowed["ui"], "archive_window_days": 60}}
    assert AppConfig.model_validate(named).ui.archive_window_days == 60


def test_the_readout_cap_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem again, in the chart block.

    The cap is applied in the browser, off the frontend's own copy. Let the two
    drift and the browser test asserts one number while the contract bounds a
    different one, which is a gate that passes for the wrong reason.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"readout_max_share:\s*([\d.]+)", reader)
    assert mirrored is not None, "the frontend chart defaults dropped readout_max_share"
    assert float(mirrored.group(1)) == ChartConfig().readout_max_share


def test_the_seed_the_shell_carries_is_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on the one digest knob a browser never sees.

    `shell_seed_items` decides how many of a day's stories a prerendered
    document carries, so the build reads it on its own rather than through
    `uiConfig()` - everything that reader returns is inlined into every
    document, and no page reads this number. Two copies of it drift like any
    other pair, and a drift here would put a different number of stories in a
    document than the contract bounds.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const SHELL_SEED_ITEMS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its shell_seed_items fallback"
    assert int(mirrored.group(1)) == UiConfig().shell_seed_items


def test_the_leading_block_is_a_knob_the_frontend_agrees_with() -> None:
    """The third digest knob a browser never sees, and the newest of the three.

    A dated document's seed is the head of the day UNION its leads, because a
    lead is chosen across the whole day and need not sit inside a prefix. So
    this number is the second term of what that document may carry, and
    `frontend/tests/payload-weight.spec.ts` reads it as the bound. A drift here
    would bound a dated document at a count the contract never agreed to.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const LEADING_STORIES = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its leading_stories fallback"
    assert int(mirrored.group(1)) == UiConfig().leading_stories


def test_the_days_the_archive_lists_are_a_knob_the_frontend_agrees_with() -> None:
    """The same two-copies problem, on another digest knob a browser never sees.

    `archive_recent_days` decides how many days the archive lists as rows of
    their own before the months take over, so the build reads it on its own
    rather than through `uiConfig()`. A drift here would put a different number
    of days on the page than the contract bounds, and on a clone with no
    `config/` there is nothing else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"const ARCHIVE_RECENT_DAYS = (\d+);", reader)
    assert mirrored is not None, "the frontend dropped its archive_recent_days fallback"
    assert int(mirrored.group(1)) == UiConfig().archive_recent_days


def test_the_side_a_figure_sits_on_is_a_knob_the_frontend_agrees_with() -> None:
    """The knob nothing reads yet, pinned to the position the page renders.

    `visual_side` sat in both config files with two different values for a
    week, and nothing caught it because no component branches on it - the
    fallback merge just took one and dropped the other. It is reserved rather
    than dead: a figure gets a column of its own when the render spec is handed
    the width it will occupy (docs/concepts/design-system.md), and until then a
    default that names a position the page does not draw is a wrong answer
    waiting for a reader.

    So the three copies are checked against each other in one place: the
    contract's default, the frontend's fallback for a clone with no `config/`,
    and what `DigestItem.svelte` puts after what.
    """
    assert UiConfig().visual_side is VisualSide.TRAILING

    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    block = re.search(r"const DEFAULTS: UiConfig = \{(.*?)\};", reader, re.DOTALL)
    assert block is not None, "config.ts no longer declares a DEFAULTS block"
    mirrored = re.search(r"visual_side:\s*'(\w+)',", block.group(1))
    assert mirrored is not None, "the frontend dropped its visual_side default"
    assert mirrored.group(1) == UiConfig().visual_side.value

    card = read_text(
        REPO_ROOT / "frontend" / "src" / "lib" / "components" / "DigestItem.svelte"
    )
    assert card.index("<ItemVisual") > card.index("data-item-summary"), (
        "the card draws its figure before the summary, so `trailing` is the wrong default"
    )


def test_the_wait_worth_a_sentence_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem on the one digest knob only a browser reads.

    `payload_slow_ms` bounds a wait that happens in a reader's browser, so a
    fresh clone with no config file resolves it from the frontend's own copy.
    Let the two drift and the sentence about a slow day fires at a moment the
    contract does not bound - and on a clone with no `config/` there is nothing
    else to catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"payload_slow_ms:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its payload_slow_ms default"
    assert int(mirrored.group(1)) == UiConfig().payload_slow_ms


def test_the_seed_covers_what_a_reading_surface_draws_before_a_reader_acts() -> None:
    """The seed is what a document holds once the rest of the day arrives by fetch.

    Every lead is an anchor into the stream, so a document that carries fewer
    stories than the leading block holds is a block whose links scroll to
    nothing. That is the floor, and it is not the whole answer: the leads are
    chosen across the WHOLE day, so a lead can sit at position 300 of the
    published order and outside any prefix. Whichever row moves the item list
    to a browser fetch owns that, and this is the number it starts from.
    """
    ui = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).ui
    assert ui.shell_seed_items >= ui.leading_stories, (
        f"a {ui.shell_seed_items}-story seed cannot hold {ui.leading_stories} leads"
    )


def test_a_shared_subject_is_worth_less_than_a_second_feed_carrying_the_story() -> None:
    """Decision 3's ceiling, derived rather than spelled.

    A second trade-press carrier of one address multiplies that story's
    authority by `1 + repetition_weight`, which on the committed config is a
    flat 0.6 added to the score. A recurring subject must not outrank a story
    two independent feeds carried today, so the shared-subject term stays under
    it. Measured 2026-09-01 over 11 committed days: a second carrier fires on
    4.49 percent of the stories that record one and a shared subject on 12.85
    percent, so the commoner signal is the one that has to be worth less.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    collect = committed.collect
    second_carrier = collect.tier_weights.trade_press * collect.repetition_weight
    assert committed.ui.lead_shared_subject_weight < second_carrier, (
        f"a shared subject is worth {committed.ui.lead_shared_subject_weight} against "
        f"{second_carrier} for a second trade-press carrier"
    )
    assert UiConfig().lead_shared_subject_weight < second_carrier


def test_a_leading_block_that_could_never_draw_is_refused() -> None:
    """A floor above the ceiling fails silently: the block never appears."""
    with pytest.raises(ValidationError, match="leading_min"):
        UiConfig(leading_stories=3, leading_min=4)
    with pytest.raises(ValidationError, match="leading_per_desk"):
        UiConfig(leading_stories=3, leading_per_desk=4)


def test_a_reject_ceiling_under_the_brief_gate_is_refused() -> None:
    """The one edit that would silence a gate instead of tightening it.

    A refused item writes no score, so it leaves the corpus `brief_copying_ceiling`
    reads. Drop the reject to the gate's own number and every item the gate could
    have failed is gone before it looks - the gate stops failing, which reads
    exactly like a pipeline that stopped copying.
    """
    gate = EvaluationConfig().brief_compression_ceiling
    for silenced in (gate, gate / 2):
        with pytest.raises(ValidationError):
            EvaluationConfig(verbatim_reject_ceiling=silenced)
    assert EvaluationConfig(verbatim_reject_ceiling=gate + 0.01).verbatim_reject_ceiling > gate


def test_the_committed_reject_ceiling_leaves_the_brief_gate_a_live_band() -> None:
    """0.75 against a 0.5 gate, so (0.5, 0.75] is a band the gate can still fail in."""
    evaluation = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).evaluation
    assert evaluation.verbatim_reject_ceiling == 0.75
    assert evaluation.brief_compression_ceiling == 0.5


def test_a_fresh_clone_measures_itself_and_the_committed_config_agrees() -> None:
    """Every instrument is on unconfigured, and the committed file did not turn one off.

    Written as an agreement between two configs rather than as three literals: a
    default that is asserted by value is a test that fails the day somebody
    legitimately changes it, which teaches people to edit the test.

    Tracing is the exception and is asserted by value, because its default is
    the claim: it was off until 2026-09-06, when the owner turned it on by
    default. On or off, the committed file and a fresh clone must agree - the
    point of this test is that the shipped config never silently diverges from
    the defaults the code carries.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    fresh = AppConfig.model_validate({"models": committed.models.model_dump()})

    assert fresh.observability == committed.observability
    assert fresh.observability.evaluation_enabled
    assert fresh.observability.telemetry_publish
    assert fresh.observability.runtime_counters_scrape
    assert fresh.observability.tracing_enabled


def test_the_item_health_census_is_not_switchable() -> None:
    """The denominator under every rate this project publishes has no off switch.

    Turning the census off would not thin a measurement, it would make every
    other measurement unreadable - a failure rate with no denominator beside it
    is the exact defect the census exists to prevent. The guard is the switch
    list itself, so adding a fifth boolean fails here and has to be argued for.

    `tracing_enabled` was the fourth, added 2026-08-30 and turned on by default
    2026-09-06. The argument it had to make: it switches an instrument nothing
    else divides by. No page reads a span, no gate consults one, and every rate
    the console prints keeps its denominator whether tracing is on or off - which
    is not true of any of the other three in the same way, and is why it is
    allowed to be a switch at all.
    """
    switches = {
        name
        for name, field in ObservabilityConfig.model_fields.items()
        if field.annotation is bool
    }
    assert switches == {
        "evaluation_enabled",
        "telemetry_publish",
        "runtime_counters_scrape",
        "tracing_enabled",
    }
    assert "census" in (ObservabilityConfig.__doc__ or "")


def test_a_sample_rate_of_zero_is_refused_because_the_toggle_already_says_off() -> None:
    """Two ways to say off is how two ways of saying it end up disagreeing."""
    for refused in (0.0, -0.1, 1.1):
        with pytest.raises(ValidationError):
            ObservabilityConfig(sample_rate=refused)
    assert ObservabilityConfig(sample_rate=1.0).sample_rate == 1.0


def test_the_trace_window_is_a_positive_span_of_days() -> None:
    """The raw-trace window is counted in days, not months.

    A trace is a lookup an operator opens for a recent run, so its window is a
    short span of days rather than a full-grain month count - which is also why
    it is not in `full_grain_months()` above. At least one day, or the day being
    written would have nowhere to land. The value lives in config; this holds the
    floor the model enforces, without asserting a default that would fail the day
    somebody legitimately changes it.
    """
    assert ObservabilityConfig().trace_window_days >= 1
    assert "trace_window_days" not in ObservabilityConfig().full_grain_months()
    with pytest.raises(ValidationError):
        ObservabilityConfig(trace_window_days=0)
    assert ObservabilityConfig(trace_window_days=1).trace_window_days == 1


def test_a_month_may_not_be_deleted_before_it_has_been_downsampled() -> None:
    """A summary has to outlive the full-grain window it replaces, both times."""
    fresh = ObservabilityConfig()
    for summary, full_grain in (
        ("item_health_aggregate_keep_months", "item_health_full_grain_months"),
        ("score_archive_keep_months", "scores_full_grain_months"),
    ):
        keep = getattr(fresh, full_grain)
        for early in (keep, keep - 1):
            with pytest.raises(ValidationError, match=summary):
                ObservabilityConfig(**{summary: early})
        assert ObservabilityConfig(**{summary: keep + 1}) is not None


def test_every_cleanup_age_outlives_the_shards_a_console_read_selects() -> None:
    """The check the old `keep_months` never made, and the reason 13 was wrong.

    `console.max_window_days` is 366, and `ledger.shards_in_window` walks 367
    inclusive days - so a window ending on the first of a month can start on the
    last day of another and open **14** month files. The retired check compared
    `months * 30` against the window, which passed 13 while a reader could still
    ask for a fourteenth shard.
    """
    window = ConsoleConfig().max_window_days
    shards = months_a_window_can_touch(window)
    assert window == 366
    assert shards == 14, "a 366-day read reaches fourteen month shards, not thirteen"
    assert 13 * 30 > window, "the retired check passed 13, which is the whole point"

    fresh = ObservabilityConfig()
    assert set(fresh.full_grain_months()) == {
        "item_health_full_grain_months",
        "feed_health_keep_months",
        "scores_full_grain_months",
        "public_telemetry_keep_months",
        "public_scores_keep_months",
        "public_feed_health_keep_months",
        "public_run_days_keep_months",
        "public_day_metrics_keep_months",
        "public_machine_keep_months",
        "public_span_rollup_keep_months",
    }
    models = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).models.model_dump()
    # Three published payloads are held equal to the ledger they project, so
    # lowering either half has to lower both to reach the shortness check.
    paired = {
        "item_health_full_grain_months": "public_telemetry_keep_months",
        "public_telemetry_keep_months": "item_health_full_grain_months",
        "scores_full_grain_months": "public_scores_keep_months",
        "public_scores_keep_months": "scores_full_grain_months",
        "feed_health_keep_months": "public_feed_health_keep_months",
        "public_feed_health_keep_months": "feed_health_keep_months",
    }
    for name, months in fresh.full_grain_months().items():
        assert months >= shards, f"observability.{name} is shorter than a console read"
        short = {name: months - 1}
        partner = paired.get(name)
        if partner is not None:
            short[partner] = months - 1
        with pytest.raises(ValidationError, match=name):
            AppConfig.model_validate({"models": models, "observability": short})


def test_the_published_copy_lasts_exactly_as_long_as_the_ledger_it_copies() -> None:
    """Either way round leaves a month nothing can answer for."""
    for skew in (-1, 1):
        with pytest.raises(ValidationError, match="public_telemetry_keep_months"):
            ObservabilityConfig(
                item_health_full_grain_months=20, public_telemetry_keep_months=20 + skew
            )
    assert (
        ObservabilityConfig(
            item_health_full_grain_months=20, public_telemetry_keep_months=20
        ).public_telemetry_keep_months
        == 20
    )


def test_a_config_still_carrying_a_removed_knob_is_refused_by_name() -> None:
    """Decision 2: a removed knob fails loudly and names what to use instead.

    Every model here forbids unknown keys, so all three names already failed -
    with "extra inputs are not permitted", which does not tell an operator where
    their number went. Ignoring the key would be worse still: an edit that takes
    no effect is a value somebody believes.

    The old value is not carried forward either. `keep_months` was set against a
    check that compared `months * 30` against the console window instead of the
    shards that window selects, so honouring it would honour the defect.
    """
    for block, removed, successor in (
        ("observability", "keep_months", "item_health_full_grain_months"),
        ("observability", "hard_delete_after_months", "item_health_aggregate_keep_months"),
        ("collect", "quarantine_after_failures", "availability_strikes_before_rest"),
    ):
        model = ObservabilityConfig if block == "observability" else CollectConfig
        with pytest.raises(ValidationError, match=successor) as raised:
            model.model_validate({removed: 13})
        assert f"{block}.{removed}" in str(raised.value)


def test_the_removed_names_are_the_three_this_row_retired() -> None:
    """The map is what the refusal message reads, so it is the map that is asserted."""
    assert dict(SUPERSEDED_COLLECT_NAMES) == {
        "quarantine_after_failures": "availability_strikes_before_rest"
    }
    assert dict(SUPERSEDED_RETENTION_NAMES) == {
        "keep_months": "item_health_full_grain_months",
        "hard_delete_after_months": "item_health_aggregate_keep_months",
    }


def test_an_unrelated_knob_in_a_block_with_no_removed_name_is_untouched() -> None:
    """The refusal fires on the removed name and on nothing else."""
    assert ObservabilityConfig.model_validate({"sample_rate": 0.5}).sample_rate == 0.5
    assert CollectConfig.model_validate({"max_per_source": 3}).max_per_source == 3


def swapped_summarizer() -> dict[str, Any]:
    """The committed config with `models.summarize` pointed at other weights.

    Every field an operator edits to swap a model, and nothing else - which is
    the shape the swap actually takes. It is not a new entry appearing from
    nowhere; it is five strings changed in place under a settings block nobody
    touched.
    """
    raw: dict[str, Any] = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["models"]["summarize"] |= {
        "id": "some-other-model-q4-k-m",
        "repo": "someone/Other-GGUF",
        "file": "Other-Q4_K_M.gguf",
        "revision": "f" * 40,
        "sha256": "1" * 64,
        "hf_base_repo": None,
    }
    return raw


def test_a_model_swap_can_no_longer_inherit_settings_nothing_declared_for_it() -> None:
    """The Oracle: new weights under an untouched settings block are refused.

    Every number in an `inference` block is a measurement about one model on one
    runner. Until this gate, `models.summarize` could name a different
    repository, file, revision and digest with the block left exactly where it
    was and `AppConfig.model_validate` raised nothing - so the run stood a server
    up on numbers derived for weights it never opened and published a whole
    plausible day.
    """
    committed = AppConfig.model_validate(json.loads(read_text(CONFIG_DIR / "idhazh.json")))
    assert committed.models.summarize.inference.declared_for == committed.models.summarize.sha256

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(swapped_summarizer())
    message = str(raised.value)
    assert "models.summarize.inference" in message, "the message names the block"
    assert "1" * 64 in message, "and the weights the entry now names"


def test_an_entry_that_declares_no_settings_of_its_own_is_refused_by_name() -> None:
    """A new entry written with no block of its own does not fall back to one."""
    raw = swapped_summarizer()
    del raw["models"]["summarize"]["inference"]
    with pytest.raises(ValidationError, match=re.escape("models.summarize.inference")):
        AppConfig.model_validate(raw)


def test_the_one_shared_settings_block_is_refused_by_name() -> None:
    """`models.inference` was one block applied to two models. It is gone.

    Refused rather than lifted onto both entries. A lift is the silent
    inheritance this row exists to end: it would hand a swapped entry the
    numbers the previous weights were measured on and raise nothing.
    """
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["models"]["inference"] = {"n_ctx": 8192}
    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(raw)
    assert "models.inference is now models.<role>.inference" in str(raised.value)
    assert dict(SUPERSEDED_MODELS_NAMES) == {"inference": "<role>.inference"}


def test_every_committed_model_entry_declares_the_weights_its_settings_are_for() -> None:
    """The committed file states the pairing rather than implying it."""
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert "inference" not in raw["models"]
    for role in sorted(ModelsConfig.model_fields):
        entry = raw["models"][role]
        assert entry["inference"]["declared_for"] == entry["sha256"], role


def test_a_run_manifest_written_before_the_settings_moved_still_reads() -> None:
    """The read side: a `model_ref` with no settings block opens on the defaults.

    Nineteen manifests sit under `frontend/public/digest/` with the shape
    `model_ref` had yesterday, and `frontend/src/lib/server/payload.ts` opens
    them at every build. A block that could not default would make each of them
    a payload today's build cannot read (`CLAUDE.md` section 11). Proved by
    removing the key rather than by reading a committed day, so it cannot age
    out of retention.
    """
    current = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in current["runs"]:
        for use in run["models"]:
            del use["model_ref"]["inference"]

    older = RunManifest.model_validate(current)
    entry = older.runs[0].models[0].model_ref
    assert entry.inference.declared_for is None
    assert entry.inference.n_ctx == 8192, "the contract default, not a guess"


def test_never_hard_deleting_is_the_default_a_reader_gets() -> None:
    """A summary costs kilobytes and is what makes a year-over-year claim citable."""
    fresh = ObservabilityConfig()
    assert fresh.item_health_aggregate_keep_months is None
    assert fresh.score_archive_keep_months is None


def test_the_committed_config_no_longer_emits_a_removed_name() -> None:
    """The Oracle: the committed file loads, and no lifecycle value is defaulted.

    Defaulted is the failure to catch. A knob deleted from the file and never
    re-spelled under its new name would still load - on the contract's default -
    and nothing would say the operator's number had gone.
    """
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert not set(raw["observability"]) & set(SUPERSEDED_RETENTION_NAMES)
    assert not set(raw["collect"]) & set(SUPERSEDED_COLLECT_NAMES)
    assert raw["observability"]["item_health_full_grain_months"] == 14
    assert raw["observability"]["public_telemetry_keep_months"] == 14

    for successor in (*SUPERSEDED_COLLECT_NAMES.values(), "availability_rest_runs"):
        assert successor in raw["collect"], f"collect.{successor} is defaulted, not set"
    loaded = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    assert loaded.collect.availability_strikes_before_rest == 5


def test_the_rest_rule_reads_the_knob_the_committed_config_spells() -> None:
    """The rename cost the pipeline nothing, and this is where that is checked.

    `discover.resting` took `collect.quarantine_after_failures` until
    2026-09-03. The committed file carried 5 under both names and the tuned
    fixture carried 3 under both, so moving the reader could not move a
    decision - and that is the difference between a rename and a change of
    behaviour.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).collect
    tuned = AppConfig.from_json(read_text(APP_CONFIG_EVERY_KNOB_DIFFERS)).collect
    assert committed.availability_strikes_before_rest == 5
    assert tuned.availability_strikes_before_rest == 3

    source = read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py")
    assert "after_failures=collect.availability_strikes_before_rest" in source


def test_the_console_falls_back_to_the_strike_count_the_pipeline_reads() -> None:
    """The console keeps its own copy of this knob, and nothing held the two together.

    `frontend/src/lib/server/config.ts` names the field it reads out of
    `config/idhazh.json` and the value it uses when there is no file. A rename
    on either side is silent: the console would fall back to its default and
    draw a rule the run does not follow, and no build would fail. This is the
    gate that was missing when the knob was renamed.
    """
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    declared = re.search(r"const COLLECT_DEFAULTS: CollectConfig = \{(.*?)\};", source, re.DOTALL)
    assert declared is not None, "config.ts no longer declares COLLECT_DEFAULTS"
    fallback = dict(re.findall(r"(\w+):\s*(\d+)", declared.group(1)))

    fresh = CollectConfig()
    assert fallback == {"availability_strikes_before_rest": str(fresh.availability_strikes_before_rest)}
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["collect"]
    for name, value in fallback.items():
        assert str(committed[name]) == value, (
            f"config.ts falls back to collect.{name} = {value} and the committed file says "
            f"{committed[name]}"
        )
    for removed in SUPERSEDED_COLLECT_NAMES:
        assert removed not in source, f"config.ts still reads collect.{removed}"


def test_the_published_window_is_unbounded_or_outlives_the_first_sight_store() -> None:
    """The Oracle for the cover setting: `-1`, or strictly longer than the seen window.

    The mistake this makes impossible is a republication. An address the archive
    has forgotten, whose first-sighting row expires in the same week, reads as
    first-seen-today: it clears the freshness gate and goes out as new. So EQUAL
    IS A HOLE, NOT A BOUND - at 90 and 90 the two stores forget the same address
    on the same day and neither one is left holding the evidence. Only two
    answers are safe: never forget, or forget later than the first-sight store
    does.

    `-1` is the only sentinel for unbounded. Not `0`, not `null`, and not a very
    large number - a large number is a cover that silently becomes finite the
    day the archive outgrows it, and it fails quietly at exactly the size where
    the hole matters most.
    """
    fresh = CollectConfig()
    assert fresh.published_window_days == -1, "the machinery ships unbounded"
    assert fresh.seen_window_days == 90

    for refused in (0, 89, 90):
        with pytest.raises(ValidationError) as raised:
            CollectConfig(published_window_days=refused)
        message = str(raised.value)
        assert "collect.seen_window_days, which is 90" in message, message

    for accepted in (-1, 91, 120):
        assert CollectConfig(published_window_days=accepted).published_window_days == accepted

    # Cross-field, so it re-runs when the OTHER number moves. Raising the
    # first-sight window past a finite cover must fail the config rather than
    # open the hole quietly.
    with pytest.raises(ValidationError) as widened:
        CollectConfig(published_window_days=120, seen_window_days=180)
    assert "collect.seen_window_days, which is 180" in str(widened.value)
    assert (
        CollectConfig(published_window_days=120, seen_window_days=119).published_window_days == 120
    )

    # A finite cover under an unbounded first-sight store is not expressible -
    # `seen_window_days` is `ge=1` - so the only pairing left to check is the
    # committed one, and it must ship unbounded.
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    assert raw["collect"]["published_window_days"] == -1, (
        "the committed config must ship the cover unbounded"
    )
    assert (
        AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).collect.published_window_days
        == -1
    )


def test_no_configured_age_deletes_a_shard_a_366_day_read_still_selects() -> None:
    """The oracle: every end date in one 400-year Gregorian cycle.

    A cleanup age is only right if, on every day it could ever run, the oldest
    month it keeps is at or before the oldest month the reader opens. The
    calendar repeats every 400 years, so sweeping one cycle is exhaustive rather
    than a sample - 146,097 end dates, which is every arrangement of leap years,
    month lengths and weekday offsets that can occur.

    The sweep uses the oldest day the window reaches instead of walking all 367
    days per date, and the first thousand dates prove the two agree, so the
    shortcut is checked rather than assumed.
    """
    window = ConsoleConfig().max_window_days
    span = timedelta(days=window)
    start = date(2000, 1, 1)
    cycle = (date(2400, 1, 1) - start).days
    assert cycle == 146_097, "one Gregorian cycle is 146,097 days"

    for offset in range(1000):
        anchor = start + timedelta(days=offset)
        walked = min(ledger.shards_in_window(anchor.isoformat(), window))
        assert walked == (anchor - span).isoformat()[:7]

    kept = ObservabilityConfig().item_health_full_grain_months
    too_short = 0
    for offset in range(cycle):
        anchor = start + timedelta(days=offset)
        oldest_read = (anchor - span).isoformat()[:7]
        assert oldest_month_kept(anchor, kept) <= oldest_read, (
            f"{kept} months on {anchor.isoformat()} keeps back to "
            f"{oldest_month_kept(anchor, kept)}, and the console still reads {oldest_read}"
        )
        if oldest_month_kept(anchor, kept - 1) > oldest_read:
            too_short += 1

    assert too_short > 0, (
        "one month less has to fail somewhere, or the value is not the minimum"
    )


def test_a_config_written_before_observability_existed_still_reads() -> None:
    """Section 11's release blocker: yesterday's file has no such key at all."""
    payload = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    del payload["observability"]
    assert AppConfig.model_validate(payload).observability == ObservabilityConfig()


def test_a_config_spelling_the_old_route_names_reads_as_the_new_ones() -> None:
    """Section 11's release blocker again, on three keys renamed on one day.

    `models.route`, `run.route_budget_minutes` and a `finetune` role naming
    `route` all moved on 2026-09-05. The proof is not that the file has a
    migration in it - it is that the two spellings land on the same object, so a
    config an operator wrote yesterday runs today's build and computes the same
    thing.
    """
    committed = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    yesterday = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    yesterday["models"]["route"] = yesterday["models"].pop("visual_planner")
    yesterday["run"]["route_budget_minutes"] = yesterday["run"].pop(
        "visual_planner_budget_minutes"
    )
    yesterday["finetune"]["student"] = "route"
    assert "route" not in committed["models"], "the committed file spells the new key"
    assert "route_budget_minutes" not in committed["run"]
    assert committed["finetune"]["student"] != "route"

    assert AppConfig.model_validate(yesterday) == AppConfig.model_validate(committed)


def test_a_config_spelling_a_renamed_knob_twice_over_is_refused() -> None:
    """Two spellings of one knob is two sources of truth, and one loses in silence.

    The same file repeating itself is fine - it says one thing twice. The
    refusal is for the file that says two different things, where taking either
    one leaves an operator believing a number nothing reads.
    """
    agreeing = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    agreeing["run"]["route_budget_minutes"] = agreeing["run"]["visual_planner_budget_minutes"]
    assert AppConfig.model_validate(agreeing).run.visual_planner_budget_minutes == 40

    disagreeing = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    disagreeing["run"]["route_budget_minutes"] = (
        disagreeing["run"]["visual_planner_budget_minutes"] + 5
    )
    with pytest.raises(ValidationError, match=re.escape("run.route_budget_minutes is now")):
        AppConfig.model_validate(disagreeing)


def test_no_page_number_names_a_route_that_grows_when_a_run_publishes() -> None:
    """This test was the opposite of itself until 2026-09-10, and the inversion is
    the point.

    It used to insist `/archive/` and the three `/console/` routes each carried a
    byte number, on the argument that an unnamed route grows unwatched. What
    actually happened is that those four numbers moved when the pipeline
    published rather than when anybody wrote code, so the gate fired on ordinary
    publishing and the recorded answer was always a bigger number - `/archive/`
    twice in one day on 2026-08-26. Meanwhile `/console/` drifted to 7.2 times
    the page it bounded and stood there four days with the build green. A number
    that cannot tell correct from far-too-loose is not an instrument.

    **The property those numbers were a proxy for is asserted directly**, by
    `frontend/tests/payload-weight.spec.ts`: no document that does not render a
    day may contain a day payload marker. That is the one regression this surface
    has ever had - a layout inlining a day, 313,300 gzipped bytes on 2026-08-26 -
    and the marker check returns the same verdict whatever the archive holds.

    So the assertion is now on absence. `/404` and `/evals/` stay, because they
    pass the test in the name: they move only when a person edits source, never
    when a run appends a day. Owner ruling, 2026-09-10.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    ceilings = committed.page_weight.ceilings_bytes

    assert PageWeightConfig().ceilings_bytes == {}, "the model default must stay empty"
    assert ceilings["/404"] > 0
    assert ceilings["/evals/"] > 0
    for route in ("/archive/", "/console/", "/console/model/", "/console/machine/"):
        assert route not in ceilings, (
            f"{route} has a byte number again. Its weight moves when the pipeline "
            "publishes, so the number has to move too, and the only way past it is to "
            "type a bigger one - which is what got these four deleted. The regression "
            "worth catching here is a day payload inlined by a layout, and "
            "frontend/tests/payload-weight.spec.ts asserts that directly."
        )


def test_the_committed_config_caps_what_a_cold_console_load_fetches() -> None:
    """The page ceilings above cannot see these bytes, and that is why they exist.

    The console stopped inlining its telemetry on 2026-09-09. That took 3.4 MB out
    of a document a ceiling watched and put it into files nothing watched, and a
    reader still waits for them - measured 2026-09-10 in a real browser, a cold
    `/console/` load fetches two telemetry shards worth 303,306 bytes on the wire
    and no other payload at all. A document ceiling now reads as a bound on what
    the console costs a reader, and it is not one.

    `cold_console_load_bytes` bounds the design rather than the data: the per-file
    ceilings say how heavy one shard may be, this says how many of them one
    opening of the page is allowed to want. The two are asserted against each
    other here, because a total below the sum of its parts is a gate that cannot
    be satisfied at the limit and a total far above it is a gate that never fires.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    weight = committed.page_weight
    payloads = weight.payload_ceilings_bytes

    assert PageWeightConfig().payload_ceilings_bytes == {}, "the model default must stay empty"
    assert PageWeightConfig().cold_console_load_bytes == 0, "the model default must stay empty"

    for path in ("console/band.json", "telemetry/"):
        assert path in payloads, (
            f"{path} is fetched by a reader's browser and has no ceiling - the bundle "
            "gate cannot fail a file nobody named, so this one would grow unwatched"
        )

    # The worst case a run of N consecutive days can land in, because February is
    # the shortest month there is. Mirrors the arithmetic in bundle-gate.mjs.
    window = committed.console.default_window_days
    months_touched = 1 + -(-(window - 1) // 28)
    worst = payloads["console/band.json"] + months_touched * payloads["telemetry/"]
    assert weight.cold_console_load_bytes >= worst, (
        "a cold load of every payload sitting exactly on its own ceiling is already "
        f"over cold_console_load_bytes ({worst} against "
        f"{weight.cold_console_load_bytes}) - the two gates contradict each other"
    )
    assert weight.cold_console_load_bytes < worst + payloads["telemetry/"], (
        "cold_console_load_bytes has room for one more telemetry shard than the "
        "default window reaches, so widening console.default_window_days past a "
        "month would not fire it - which is the one thing it exists to catch"
    )


def test_a_page_ceiling_bounds_a_route_and_bounds_it_above_zero() -> None:
    """A ceiling of zero passes nothing and a key that is not a route bounds nothing."""
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(ceilings_bytes={"/evals/": 0})
    with pytest.raises(ValueError, match="is not a route"):
        PageWeightConfig(ceilings_bytes={"evals": 2475})


def test_a_payload_ceiling_bounds_a_path_in_the_build() -> None:
    """The leading slash is what tells the two objects apart.

    A route ceiling has one and a payload ceiling does not, so a number typed
    into the wrong object is refused by shape here rather than discovered later
    as a gate quietly checking nothing.
    """
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry/": 0})
    with pytest.raises(ValueError, match="is a route, not a path"):
        PageWeightConfig(payload_ceilings_bytes={"/telemetry/": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry\\2026-09.csv": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"../telemetry/": 500_000})


def test_every_configured_feed_names_a_declared_vertical() -> None:
    """Retired feeds too - a tombstone still labels published items by vertical."""
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    declared = {vertical.id for vertical in taxonomy.verticals}
    for feed in sources.known_feeds():
        assert feed.vertical in declared, f"feed {feed.id} names an undeclared vertical"


def test_every_vertical_clears_its_own_feed_floor() -> None:
    """A vertical under `min_feeds` plans nothing at all, so this is a live gate.

    `rank.plan_vertical` returns an empty list for a vertical below its floor -
    the desk does not thin out, it goes silent. Nothing else notices: the run
    succeeds, the digest publishes, and one section is simply absent.

    That was one edit away from happening on 2026-08-29. Retiring the 40 feeds
    that had never published anything took `ai` to 28 against a floor of 35 and
    `business-economy` to 12 against 21 - 34 percent of that day's items, gone
    quietly. A throwaway assertion in a migration script caught it; nothing in
    the repository would have. This is that assertion, kept.

    Since 2026-09-02 it counts what a run may lawfully ask rather than what a
    curator left active, which is the count the floor is actually compared
    against - so it reads the committed retirement ledger and the committed
    health record as well as the config. Measured on this checkout 2026-09-02
    the two counts are identical on every desk, because no committed row records
    a permission or a retirement yet.

    It reads the committed config on purpose. The number that decides a run is
    the one in `config/`, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    state = REPO_ROOT / ledger.STATE_DIRNAME
    records = source_health.endpoint_records(
        ledger.load_health(state, today=newest_health_date(state), within_days=400)
    )
    retired = {row.endpoint_key for row in ledger.load_retirements(state)}
    active = Counter(
        feed.vertical for feed in sources.feeds if feed.status is LifecycleStatus.ACTIVE
    )
    for vertical in taxonomy.verticals:
        askable = source_health.eligible(
            sources.feeds, vertical.id, retired_keys=retired, records=records
        )
        assert len(askable) >= vertical.min_feeds, (
            f"{vertical.id} has {len(askable)} feeds it may ask against a floor of "
            f"{vertical.min_feeds}, so it would publish nothing - of "
            f"{active[vertical.id]} a curator left active"
        )


def newest_health_date(state: Path) -> str:
    """The last day the committed record covers, so the read does not move with the clock.

    A window ending at today would make this test's answer depend on when it
    ran, and the question it asks is about committed evidence rather than about
    the hour.
    """
    stems = sorted(path.stem for path in (state / "feed-health").glob("*.csv"))
    return f"{stems[-1]}-28" if stems else "1970-01-01"


def desk(**overrides: Any) -> dict[str, Any]:
    """One vertical of a plan, spelled the way an earlier build wrote it."""
    return {"id": "ai", "considered": 40, "planned": 5, "live_feeds": 3, **overrides}


def test_a_plan_that_spells_live_feeds_still_reads() -> None:
    """The rename landed on 2026-09-02 and the model forbids unknown keys.

    Without the read migration a plan an earlier build wrote would be refused
    outright rather than degrade, which is a release blocker by section 11.
    """
    parsed = VerticalPlan.model_validate(desk())
    assert parsed.eligible_feeds == 3


def test_the_real_payload_an_earlier_build_committed_still_opens() -> None:
    """The same migration, against bytes a build actually wrote and committed.

    `tests/fixtures/superseded/run-plan-live-feeds.json` is the run-plan fixture
    exactly as it stood in the tree before the 2026-09-02 rename, recovered from
    git and kept unedited. A migration checked only against a payload this test
    file builds proves the builder, not the migration - and this is the whole
    reason the migration outlived the config knobs renamed beside it.
    """
    raw = read_text(FIXTURES_DIR / "superseded" / "run-plan-live-feeds.json")
    assert '"live_feeds"' in raw and '"eligible_feeds"' not in raw

    plan = RunPlan.from_json(raw)
    assert [(desk.id, desk.eligible_feeds) for desk in plan.verticals] == [("ai", 3), ("energy", 4)]
    assert all(desk.feed_floor is None for desk in plan.verticals), (
        "no floor is invented for a payload that never carried one"
    )


def test_a_plan_that_never_carried_a_floor_is_given_none() -> None:
    """Absent reads as unknown, never as a floor of zero.

    A zero would say the desk had no floor to clear, which on a payload that
    recorded `below_feed_floor` is a claim the payload itself can contradict.
    """
    assert VerticalPlan.model_validate(desk()).feed_floor is None
    assert VerticalPlan.model_validate(desk(below_feed_floor=True, planned=0)).feed_floor is None


def test_a_plan_may_not_spell_the_count_twice() -> None:
    """The migration maps the old name and never merges two answers.

    A payload carrying both is not an old payload; it is a writer nobody has,
    and quietly preferring one of the two is how a count starts disagreeing
    with itself.
    """
    with pytest.raises(ValidationError):
        VerticalPlan.model_validate(desk(eligible_feeds=9))


def bare_plan(**extra: Any) -> dict[str, Any]:
    """The smallest plan payload that validates, for the fields under test."""
    return {
        "date": "2026-08-21",
        "run_id": "2026-08-21-1",
        "generated_at": "2026-08-21T06:00:04Z",
        **extra,
    }


def test_a_plan_written_before_the_guard_was_counted_reads_as_unknown() -> None:
    """Null is unknown, never a run where the guard refused nothing.

    A zero would say this run was offered addresses the ledger held and refused
    none of them, which is a measurement. A payload written before anything
    counted cannot make it, and inventing one is how an unread number turns into
    an argument about how wide the cover should be.
    """
    built = RunPlan.model_validate(bare_plan())
    assert built.dropped_published is None
    assert built.dropped_published_ages is None


def test_the_guard_count_and_its_bands_are_recorded_together() -> None:
    """Either half alone reads as a measurement while being unable to support one."""
    bands = [band.model_dump(mode="json") for band in PublishedAgeBand.histogram([1, 200])]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=2))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published_ages=bands))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=bands))


def test_every_declared_band_is_written_and_a_short_histogram_is_refused() -> None:
    """An absent band and a band holding nothing are different answers.

    Dropping the empty ones would shorten the payload and lose the finding.
    Measured 2026-09-08 on an Intel Core i7-1265U, over the ledger as it stood at
    the end of 2026-09-07: its 7,600 rows span 16 published days, 2026-08-23 to
    2026-09-07, so every band from 30 days on is a measured zero on every run
    today - and that zero is why nobody can yet say what a finite cover would
    cost.
    """
    bands = PublishedAgeBand.histogram([0, 1, 200])
    assert [(band.from_days, band.to_days) for band in bands] == list(PUBLISHED_AGE_BANDS)
    assert [band.addresses for band in bands] == [1, 1, 0, 0, 0, 1, 0]

    short = [band.model_dump(mode="json") for band in bands if band.addresses]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=short))


def test_a_manifest_written_before_the_floor_was_recorded_reads_as_unknown() -> None:
    """`VerticalCount` never carried either number, so both are null on every
    manifest committed before today - and null is unknown rather than a desk
    with no sources."""
    count = VerticalCount.model_validate({"id": "ai", "planned": 5, "published": 4})
    assert count.eligible_feeds is None
    assert count.feed_floor is None


def test_every_committed_run_manifest_still_reads_today() -> None:
    """The release blocker this class of change carries: a payload yesterday's run
    wrote that today's build cannot open (section 11).

    Driven from the fixture with the two fields removed, not from the committed
    tree. Walking the tree cost one parse per published day and carried a fuse:
    it counted the desks that still LACK the field and failed at zero, so it goes
    red on the day the last unmigrated day ages out of retention - a date on the
    calendar rather than a change anybody made.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    stripped = 0
    for run in payload["runs"]:
        for written in run.get("verticals", []):
            written.pop("eligible_feeds", None)
            written.pop("feed_floor", None)
            stripped += 1
    assert stripped, "the fixture declares no desk, so removing the fields proved nothing"

    parsed = RunManifest.model_validate(payload)
    counts = [count for record in parsed.runs for count in record.verticals]
    assert len(counts) == stripped
    assert all(count.eligible_feeds is None for count in counts)
    assert all(count.feed_floor is None for count in counts)


def test_the_manifest_keeps_the_keys_its_python_names_stopped_matching() -> None:
    """Three Python names moved on 2026-09-05 and no published key was allowed to.

    The rename is a read-side alias, so the payload keeps `items_routed` and
    `route_ms` and the model answers to `items_decided` and `decision_ms`. That
    is a property of the model against one payload, and the committed tree was
    parsed once per published day to re-ask it.
    """
    assert ModelRole.VISUAL_PLANNER.value == "route"

    raw = read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json")
    payload = json.loads(raw)
    carrying = 0
    for run in payload["runs"]:
        if "items_routed" not in run:
            continue
        carrying += 1
    assert carrying, "the fixture carries no items_routed, so the alias is untested"

    parsed = RunManifest.model_validate(payload)
    for record, written in zip(parsed.runs, payload["runs"], strict=True):
        if "items_routed" not in written:
            continue
        assert record.items_decided == written["items_routed"]
        assert record.decision_ms == written["route_ms"]
    # The published key is the contract. A writer that started emitting the
    # Python name would break every reader of every day already committed.
    assert "items_decided" not in raw
    assert "decision_ms" not in raw

    # And the round trip puts the keys back, which is what a reader fetches.
    written_back = json.loads(parsed.to_json())["runs"][-1]
    assert "items_routed" in written_back and "route_ms" in written_back


def test_the_watchlist_stays_inside_its_configured_cap() -> None:
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert len(watchlist.entities) <= config.collect.watchlist_max_entities


# --- Structural rules ------------------------------------------------------


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
    """Decision 2: an item is addressed <vertical>-<NN>, never by a digest."""
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in day.items:
        assert not LONG_HEX.search(item.item_id)
        if item.visual is not None and item.visual.path is not None:
            assert not LONG_HEX.search(item.visual.path)
    decision = VisualDecision.from_json(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    assert decision.asset_path is not None
    assert not LONG_HEX.search(decision.asset_path)


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


def test_the_canary_writes_every_column_the_counters_ledger_defines() -> None:
    """The same guard, over the second header the canary restates.

    The canary gained a `state/runtime-counters.csv` on 2026-08-31, because
    without one the Machine route draws every panel in its empty state and the
    browser suite can assert nothing else. That file is written by hand in
    JavaScript for the same reason the item-health one is, so it needs the same
    guard: a column added to `RuntimeCountersRow` and not to that array writes a
    canary whose cells sit one place to the left, and every backend gate stays
    green while the console reads the wrong number.
    """
    source = read_text(REPO_ROOT / "frontend" / "scripts" / "build-canary.mjs")
    declared = re.search(r"const COUNTER_COLUMNS = \[(.*?)\];", source, re.DOTALL)
    assert declared is not None, "build-canary.mjs no longer declares a COUNTER_COLUMNS array"
    assert tuple(re.findall(r"'([^']+)'", declared.group(1))) == RuntimeCountersRow.csv_columns()


def test_the_canary_writes_every_column_the_feed_health_ledger_defines(tmp_path: Path) -> None:
    """Every column filled by at least one canary feed, not merely present in the header.

    The browser suite runs against this ledger, so a column no canary row fills
    is a console state that suite cannot reach - which is how the five columns
    added on 2026-09-02 would ship drawn only in their empty state.
    """
    build_canary_day.health(tmp_path)
    path = tmp_path / "feed-health" / f"{build_canary_day.DATE[:7]}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert tuple(rows[0]) == FeedHealthRow.csv_columns()
    unfilled = [name for name in FeedHealthRow.csv_columns() if not any(row[name] for row in rows)]
    assert unfilled == [], "a canary column nothing fills is a console state no test can reach"
    assert {row["robots_outcome"] for row in rows} == {"allowed", "denied", "unreachable", ""}


# --- The Oracle: a definition is config, and editing it moves the prompt ----


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


def taxonomy_fixture(stem: str) -> Taxonomy:
    """One of the two fixture vocabularies the definition oracle is driven from."""
    return Taxonomy.from_json(read_text(FIXTURES_DIR / "taxonomy" / f"{stem}.json"))


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
        *((item.id, item.definition) for item in taxonomy.events),
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
    assert len(SOURCE_NEUTRAL_FAILURE_CODES) == 15
    assert FailureCode.NOT_ATTEMPTED in SOURCE_NEUTRAL_FAILURE_CODES
    assert FailureCode.MODEL_UNREACHABLE in SOURCE_NEUTRAL_FAILURE_CODES
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

    Three rows built here rather than the 225 in `state/runtime-counters.csv`,
    which gains one per shard per run (Rule #12). What is under test is the
    arithmetic of an appended column, and three rows prove it exactly as 225 do.

    A widening that MOVED a cell instead of appending one still parses, and every
    number would then be filed under the wrong name. The byte count is what
    catches that: an appended column costs one comma on every line and its own
    name once, and nothing else.
    """
    added = ("n_ctx_configured", "python_peak_rss_bytes", "cgroup_peak_bytes")
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

    expected_delta = len(added) * len(narrow.splitlines()) + sum(len(name) for name in added)
    assert len(wide.encode()) - len(narrow.encode()) == expected_delta

    for row, line in zip(rows, wide.splitlines()[1:], strict=True):
        widened = RuntimeCountersRow.from_csv_row(dict(zip(columns, line.split(","), strict=True)))
        assert widened == row
        assert widened.n_ctx_configured is None
        assert widened.python_peak_rss_bytes is None
        assert widened.cgroup_peak_bytes is None


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


def test_a_host_name_that_could_split_a_row_is_refused() -> None:
    """`state/runtime-counters.csv` merges with the union driver, which is line-based.

    Eight shards append to one branch, and the merge keeps lines rather than
    parsing CSV. A cell holding a newline would be quoted correctly by the writer
    and still split one row in two the first time two shards raced.
    """
    for hostile in ("AMD EPYC\n7763", "AMD EPYC\r7763"):
        with pytest.raises(ValueError, match="cpu_model"):
            RuntimeCountersRow.model_validate(
                {
                    "date": "2026-08-26",
                    "run_id": "2026-08-26-5",
                    "shard": 0,
                    "shards": 4,
                    "scraped_at": "2026-08-26T21:32:30Z",
                    "cpu_model": hostile,
                }
            )


# --- Invariants the shape exists to carry ----------------------------------


def mutate(path: Path, **changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(read_text(path))
    payload.update(changes)
    return payload


def test_url_key_is_rebuilt_not_trusted() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "article" / "ok.json",
        canonical_url="https://blog.example-lab.org/2026/08/other",
    )
    with pytest.raises(ValueError, match="url_key"):
        Article.model_validate(payload)
    payload["url_key"] = derive_url_key(payload["canonical_url"])
    assert Article.model_validate(payload).url_key == derive_url_key(payload["canonical_url"])


def test_an_ok_article_must_carry_text() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "ok.json", text=None)
    with pytest.raises(ValueError, match="title and text"):
        Article.model_validate(payload)


def test_a_failed_article_must_record_why() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "fetch-failed.json", failure_detail=None)
    with pytest.raises(ValueError, match="must record why"):
        Article.model_validate(payload)


def test_truncation_is_flagged_and_located_together() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "article" / "truncated.json", truncated_at_tokens=None)
    with pytest.raises(ValueError, match="truncated"):
        Article.model_validate(payload)


def test_an_item_decided_to_nothing_carries_no_spec() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json", spec="anything")
    with pytest.raises(ValueError, match="no spec"):
        VisualDecision.model_validate(payload)


def test_only_a_rendered_visual_has_an_asset_path() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json", visual_state="absent")
    with pytest.raises(ValueError, match="asset_path"):
        VisualDecision.model_validate(payload)


def test_hhem_delta_is_rebuilt_not_trusted() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json", hhem_delta=0.9)
    with pytest.raises(ValueError, match="hhem_delta"):
        EvalRow.model_validate(payload)


#: The four columns the owner refused to delete on 2026-08-30, and the two things
#: each description has to carry. Every one of them is a cell a reader cannot
#: interpret from its value: a constant that looks like a count, a derived cell
#: that looks like a measurement, a flag that changed meaning on a fixed date, and
#: a timing that is not on the path it sits beside. Each entry is
#: (model, field, unit phrases, reader phrases) and one phrase from each group has
#: to appear, so a later edit cannot quietly strip the unit or the reader back out.
KEPT_COLUMNS: tuple[tuple[type[Contract], str, tuple[str, ...], tuple[str, ...]], ...] = (
    (Summary, "attempt", ("A count, not a duration",), ("Nothing reads it",)),
    (EvalRow, "score_ms", ("Milliseconds",), ("observability.sample_rate",)),
    (EvalRow, "hhem_delta", ("0-to-1 faithfulness scale",), ("no band reads it",)),
    (EvalRow, "truncation_flagged", ("True when",), ("model-work.ts",)),
)


@pytest.mark.parametrize(("model", "field", "units", "readers"), KEPT_COLUMNS)
def test_a_kept_column_says_what_it_holds_and_who_reads_it(
    model: type[Contract], field: str, units: tuple[str, ...], readers: tuple[str, ...]
) -> None:
    """A column kept for history still has to explain itself.

    The owner asked what two of these four meant, which is what a description
    that is not doing its job looks like. A test that only checks the field
    exists would have passed on every one of them.
    """
    described = model.model_fields[field].description or ""
    assert described.strip(), f"{model.__name__}.{field} carries no description"
    assert any(unit in described for unit in units), (
        f"{model.__name__}.{field} does not say what its value is measured in"
    )
    assert any(reader in described for reader in readers), (
        f"{model.__name__}.{field} does not say who reads it"
    )


def test_every_kept_column_reaches_its_generated_schema() -> None:
    """A description a reader never sees is a comment. These are read by people."""
    for model, field, units, readers in KEPT_COLUMNS:
        schema = json.loads(read_text(SCHEMAS_DIR / f"{model.__schema_stem__}.schema.json"))
        described = schema["properties"][field]["description"]
        assert any(unit in described for unit in units)
        assert any(reader in described for reader in readers)


def test_the_model_cannot_have_read_more_words_than_the_article_holds() -> None:
    """The impossible direction, refused.

    610 of 2,346 committed rows carried a seen count LARGER than the full
    count, because the two cells were filled by two different counters over the
    same truncated string. Nothing compared them, so nothing could see it.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1874,
    )
    with pytest.raises(ValueError, match="not more"):
        EvalRow.model_validate(payload)


def test_an_article_shorter_than_the_cap_reads_the_same_length_twice() -> None:
    """Equal is the normal case, not an error: nothing was cut."""
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=1875,
    )
    assert EvalRow.model_validate(payload).source_word_count == 1875


def test_an_eval_row_may_not_know_how_long_its_article_was() -> None:
    """Null and not zero (section 11).

    A row written before 2026-08-27 whose article was truncated has no full
    length anywhere: extract discarded the pre-cap body. Zero would claim the
    article was empty.
    """
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "eval-row" / "truncation-artifact.json",
        source_word_count=None,
    )
    row = EvalRow.model_validate(payload)
    assert row.source_word_count is None
    assert row.source_seen_word_count == 1875, "the seen count is still a measurement"


def test_an_ok_item_health_row_carries_only_recorded_extract_signals() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.UNKNOWN,
        detail="unclassified failure",
    )
    with pytest.raises(ValueError, match="recorded extract signal"):
        ItemHealthRow.model_validate(payload)

    signalled = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json",
        code=FailureCode.NOT_PROSE,
    )
    assert ItemHealthRow.model_validate(signalled).code is FailureCode.NOT_PROSE


def test_item_health_failure_code_must_belong_to_stage() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.HTTP_CLIENT_ERROR,
    )
    with pytest.raises(ValueError, match="does not belong"):
        ItemHealthRow.model_validate(payload)


def test_item_health_http_status_belongs_only_to_fetch() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json", http_status=200)
    with pytest.raises(ValueError, match="http_status"):
        ItemHealthRow.model_validate(payload)


def test_unknown_item_health_failure_carries_the_only_detail() -> None:
    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        code=FailureCode.UNKNOWN,
        detail="source shape did not match a known bucket",
    )
    assert ItemHealthRow.model_validate(payload).code is FailureCode.UNKNOWN

    payload = mutate(
        CONTRACT_FIXTURES_DIR / "item-health-row" / "extract-too-short.json",
        detail="short source",
    )
    with pytest.raises(ValueError, match="detail belongs only"):
        ItemHealthRow.model_validate(payload)


def test_a_retired_entry_must_carry_its_date() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["verticals"][2]["retired_on"] = None
    with pytest.raises(ValueError, match="retired_on"):
        Taxonomy.model_validate(payload)


# --- The registry holds two kinds of entry ---------------------------------


def watchlist_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "watchlist" / "seeded.json")
    )
    return payload


def test_a_subject_needs_neither_a_filer_id_nor_a_feed() -> None:
    """The whole point of the widening.

    A pandemic, a tournament or an export-control regime has no SEC filer id
    and no newsroom of its own. Before `kind` the registry described itself as
    a list of named organisations, so an entry like this had no way in.
    """
    seeded = Watchlist.model_validate(watchlist_payload())
    subject = next(entity for entity in seeded.entities if entity.kind is EntityKind.SUBJECT)
    assert subject.cik is None
    assert subject.feeds == []
    assert subject.aliases, "a subject with no alias is never matched (EntityDef.aliases)"


def test_a_subject_may_not_carry_a_filer_id() -> None:
    """Only an organisation files with the SEC, so the pairing is a data error."""
    payload = watchlist_payload()
    payload["entities"][0]["kind"] = EntityKind.SUBJECT.value
    with pytest.raises(ValueError, match="cik belongs to an organisation"):
        Watchlist.model_validate(payload)


def test_a_watchlist_written_before_the_kind_field_reads_as_organisations() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    Every entry the registry held on 2026-08-31 was a standing organisation, so
    absence has exactly one honest meaning and the change needs no migration.
    """
    payload = watchlist_payload()
    for entity in payload["entities"]:
        del entity["kind"]
    payload["version"] = "2026-08-26"
    older = Watchlist.model_validate(payload)
    assert {entity.kind for entity in older.entities} == {EntityKind.ORGANISATION}


def test_every_committed_registry_entry_is_still_an_organisation() -> None:
    """The row's oracle, and the reason the gap measurement is worth taking.

    A half-life on a company is meaningless - its gap between our own mentions
    is near zero. Until a subject is curated in, the widening carries no
    behaviour, and this test says so out loud rather than leaving it implied.
    """
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert [entity.id for entity in watchlist.entities if entity.kind is EntityKind.SUBJECT] == []


def test_the_committed_watchlist_survives_a_read_and_a_rewrite() -> None:
    """A hand-edited config re-serializes to the bytes on disk.

    Without that, a curator's next edit arrives buried in a whole-file
    reshuffle and the diff stops showing what changed.
    """
    text = read_text(CONFIG_DIR / "watchlist.json")
    assert Watchlist.from_json(text).to_json() == text


# --- Two feed lists, and the line between them ------------------------------


def sources_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json")
    )
    return payload


def test_a_retired_feed_cannot_sit_in_the_live_list() -> None:
    """The split is only real if the shape refuses the old arrangement.

    `feeds` is the list Collect loops. A retired entry there would cost a
    request every run and reach a reader, which is the exact failure the split
    exists to end - so it is a load error, not a filter someone remembers.
    """
    payload = sources_payload()
    payload["feeds"].append(payload["retired"].pop())
    with pytest.raises(ValueError, match="belongs in `retired`"):
        Sources.model_validate(payload)


def test_a_live_feed_cannot_hide_on_the_tombstone_shelf() -> None:
    """The other direction, which is the quieter bug.

    A feed parked in `retired` with an active status is never fetched, and
    nothing says so. It just stops producing, and the config still reads as
    though it were being consulted.
    """
    payload = sources_payload()
    payload["retired"][0]["status"] = "active"
    payload["retired"][0]["retired_on"] = None
    with pytest.raises(ValueError, match="without a retired status"):
        Sources.model_validate(payload)


def test_yesterdays_sources_file_fails_loudly_and_names_the_key() -> None:
    """The migration ruling, pinned.

    `config/sources.json` is written by a person in the same commit as the
    model, so there is no read-side migration and no silent coercion at the
    boundary. What replaces it is a load error that names the key the entry has
    to move to - which is only worth relying on if it is tested.
    """
    legacy = sources_payload()
    legacy["feeds"].extend(legacy.pop("retired"))
    with pytest.raises(ValueError, match="`retired`"):
        Sources.model_validate(legacy)


def test_an_id_is_unique_across_all_three_lists() -> None:
    """A duplicate id is what makes a published `source_id` ambiguous.

    Checking `feeds` alone would have let a tombstone shadow a live feed - two
    titles and two kinds for one id, with the winner decided by list order.
    """
    payload = sources_payload()
    payload["retired"][0]["id"] = payload["feeds"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)

    payload = sources_payload()
    payload["salience"][0]["id"] = payload["retired"][0]["id"]
    with pytest.raises(ValueError, match="distinct"):
        Sources.model_validate(payload)


def test_an_address_is_not_read_twice_under_two_ids() -> None:
    """Retiring a feed and re-adding it under a new id is a real editing move.

    Left unchecked it doubles every request to that host and carries the same
    story twice, which reads as corroboration.
    """
    payload = sources_payload()
    payload["retired"][0]["url"] = payload["feeds"][0]["url"]
    with pytest.raises(ValueError, match="urls must be distinct"):
        Sources.model_validate(payload)


def test_a_tombstone_still_answers_for_the_items_it_published() -> None:
    """`known_feeds` is the union both label maps read (`assemble.py`).

    An item published before a feed retired keeps its `source_id` forever. If
    the id stops resolving, the page shows the raw slug and the item is
    republished as `reporting` - relabelling an announcement as journalism.
    """
    sources = Sources.from_json(read_text(CONTRACT_FIXTURES_DIR / "sources" / "two-verticals.json"))
    known = {feed.id for feed in sources.known_feeds()}
    assert known == {feed.id for feed in sources.feeds} | {feed.id for feed in sources.retired}
    assert "example-defunct-daily" in known


def test_the_lens_vocabulary_may_lose_an_entry_but_never_hold_one_twice() -> None:
    """What survived the retype, and what deliberately did not.

    Until 2026-09-12 `Taxonomy` refused any file that did not label every
    `LensId` exactly once, so a lens could not be dropped without editing
    Python. That check is gone with the enum, and dropping the last lens is now
    a legal config edit - which is the whole point of the row and also the
    reason the reading side had to learn to render an id it cannot name. Two
    ids the same is still a defect, because then one of them decides nothing.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "taxonomy" / "with-tombstones.json"))
    payload["lenses"].pop()
    Taxonomy.model_validate(payload)

    payload["lenses"].append(payload["lenses"][0])
    with pytest.raises(ValueError, match="lens ids must be distinct"):
        Taxonomy.model_validate(payload)


def test_a_published_item_carrying_a_retired_lens_still_reads() -> None:
    """The read-side half of the retype, on a record a run really wrote.

    `tests/fixtures/digest/retired-lens-item.json` is a verbatim copy of one of
    the 18 committed items carrying `ai-roi`, which `config/taxonomy.json`
    retired on 2026-08-30. Measured 2026-09-12 over the 22 committed days and
    8,922 items: 12 on 2026-08-27, 3 on 2026-08-28 and 3 on 2026-08-29. It is a
    fixture rather than a walk of the archive because a test may not pay for
    what the pipeline has piled up (Rule #12), and because the fixture outlives
    the day those three days age out of retention.

    It also carries a live lens beside the tombstone, so the case it proves is
    the mixed one: a day does not get to keep half of what it said.
    """
    item = DigestItem.model_validate_json(
        read_text(FIXTURES_DIR / "digest" / "retired-lens-item.json")
    )
    assert item.lenses == ["ai-roi", "china"]

    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    retired = {lens.id for lens in taxonomy.lenses if lens.status is LifecycleStatus.RETIRED}
    assert "ai-roi" in retired, "the fixture stopped being the case this test is about"
    assert "ai-roi" not in taxonomy.lens_terms(), "a tombstone must stop matching"


def test_an_id_the_committed_vocabulary_no_longer_names_still_reads() -> None:
    """The migration, stated as the thing it has to survive.

    A closed enum could not read a word `config/taxonomy.json` had stopped
    carrying, so the only safe way to remove a lens was never to remove one. An
    open slug reads it, which is what lets a person delete an entry without
    making every day that published it unreadable. The id is removed from the
    fixture's vocabulary rather than from the committed file, so nothing here
    depends on what config happens to hold today.
    """
    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "retired-lens-item.json"))
    payload["lenses"] = ["ai-roi", "supply-chain"]
    item = DigestItem.model_validate(payload)
    assert item.lenses == ["ai-roi", "supply-chain"]

    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    assert "supply-chain" not in {lens.id for lens in taxonomy.lenses}

    with pytest.raises(ValidationError):
        DigestItem.model_validate({**payload, "lenses": ["Supply Chain"]})


def test_runs_are_append_only() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][1]["n"] = 3
    payload["runs"][1]["run_id"] = "2026-08-21-3"
    with pytest.raises(ValueError, match="without gaps"):
        RunManifest.model_validate(payload)


def test_run_counts_reconcile() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    payload["runs"][0]["items_failed"] = 0
    with pytest.raises(ValueError, match="must equal planned"):
        RunManifest.model_validate(payload)


def test_a_manifest_written_before_charts_were_counted_still_reads() -> None:
    """Section 11's release blocker for `charts_drafted`, tested against the key."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in payload["runs"]:
        del run["charts_drafted"]
    assert [run.charts_drafted for run in RunManifest.model_validate(payload).runs] == [0, 0]


def test_a_published_chart_written_before_the_field_reads_as_a_chart_draft() -> None:
    """A chart on the page was necessarily the chart the model asked for.

    Defaulting the missing key to false would make the manifest report fewer
    drafts than published charts, which is the one thing `charts_drafted` exists
    to measure.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    del payload["drafted_chart"]
    assert VisualDecision.model_validate(payload).drafted_chart is True

    absent = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "none.json"))
    del absent["drafted_chart"]
    assert VisualDecision.model_validate(absent).drafted_chart is False


def test_a_later_run_appends_and_never_reorders() -> None:
    """Row 13's monotonicity rule, made mechanical."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"].insert(0, payload["items"].pop())
    with pytest.raises(ValueError, match="never reorders"):
        DigestDay.model_validate(payload)


def test_a_partial_day_says_so() -> None:
    payload = mutate(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json", partial=False)
    with pytest.raises(ValueError, match="partial"):
        DigestDay.model_validate(payload)


def test_vertical_counts_agree_with_the_items() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["verticals"][0]["count"] = 5
    with pytest.raises(ValueError, match="count disagrees"):
        DigestDay.model_validate(payload)


def test_a_revision_names_the_run_that_wrote_it() -> None:
    """Either both revision fields are set or neither is. One of the two alone is a wrong join."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)

    payload["items"][0]["updated_by_run"] = 2
    assert DigestDay.model_validate(payload).items[0].updated_by_run == 2

    del payload["items"][0]["updated_at"]
    with pytest.raises(ValueError, match="both updated_at and updated_by_run"):
        DigestDay.model_validate(payload)


def test_a_revision_cannot_precede_the_run_that_introduced_the_item() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][2]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][2]["updated_by_run"] = 1
    with pytest.raises(ValueError, match="cannot precede"):
        DigestDay.model_validate(payload)


def test_an_item_cannot_name_a_revising_run_the_day_never_recorded() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["updated_at"] = "2026-08-21T18:00:00Z"
    payload["items"][0]["updated_by_run"] = 3
    with pytest.raises(ValueError, match="revised by a run that is not recorded"):
        DigestDay.model_validate(payload)


def test_a_day_written_before_the_revision_field_still_loads() -> None:
    """Additive and null-defaulted, so no committed payload had to be rewritten."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for item in payload["items"]:
        del item["updated_by_run"]

    day = DigestDay.model_validate(payload)

    assert [item.updated_by_run for item in day.items] == [None] * len(day.items)


# --- the ranking signal and the clock behind published_at ------------------

#: The five the planning step computes and the day payload started carrying on
#: 2026-08-31. Every day published before that omits all five.
RANKING_SIGNAL = ("carried_by", "watchlist_hit", "on_front_page", "rank_score", "time_source")
DESK_SHORTFALL = ("considered", "too_old", "below_feed_floor")


def committed_days() -> list[Path]:
    """Published days a test may read. The newest date is still being written to."""
    return sorted((REPO_ROOT / "frontend" / "public" / "digest").glob("*/*/*/digest.json"))[:-1]


def test_the_published_tree_holds_days_to_migrate() -> None:
    """The denominator for the one check below that still opens a real day.

    `a_day_that_validates` reads the newest committed payload, and an empty tree
    would leave it reading nothing while reporting the same pass as a tree it
    read. The read-side migrations beside it are driven from a fixture instead,
    so they no longer need this. `committed_days` already drops the date still
    being written, so a tree holding only that one date reads as empty here.
    """
    assert committed_days(), "frontend/public/digest holds no finished day"


# --- the guard that replaced the one prerendering used to give free ---------


def a_day_that_validates() -> dict[str, Any]:
    """A finished committed day, taken off the real tree rather than written here.

    A day composed by hand drifts from the one the pipeline writes, and the
    guard under test is about the real file. The test below needs a day longer
    than `ui.shell_seed_items`, which is 15, and the date still being written
    has no floor - one run in on 2026-09-06 it held 78 stories against 374.
    `committed_days` is what keeps that date out of reach.
    """
    day: dict[str, Any] = json.loads(read_text(committed_days()[-1]))
    return day


def a_tree_holding(tmp_path: Path, day: dict[str, Any], date: str = "2026-08-30") -> Path:
    """One committed day on disk, in the layout `published_days` globs for."""
    year, month, dom = date.split("-")
    where = tmp_path / "digest" / year / month / dom
    where.mkdir(parents=True)
    (where / "digest.json").write_text(json.dumps(day), encoding="utf-8")
    return tmp_path / "digest"


def test_a_story_past_the_seed_is_the_one_this_gate_exists_for(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The exact hole the migration opened, and the reason a step replaced a build.

    The story is broken at the END of a day longer than `ui.shell_seed_items`,
    so no prerendered document carries it and no build would ever open it. A
    reader's browser fetches it. The gate has to find it there.
    """
    day = a_day_that_validates()
    seed = UiConfig().shell_seed_items
    assert len(day["items"]) > seed, "a day no longer than the seed proves nothing here"
    day["items"][-1]["key_points"] = []

    root = a_tree_holding(tmp_path, day)
    with caplog.at_level(logging.ERROR):
        assert stage_validate_days(root) == 1
    assert "2026-08-30" in caplog.text, "the failing day has to be named"
    assert "digest-view.schema.json" in caplog.text, "which contract refused it"


def test_a_day_that_is_not_json_at_all_is_named_rather_than_thrown(tmp_path: Path) -> None:
    """Degrade, do not fail: one unreadable file must not stop the other days."""
    root = a_tree_holding(tmp_path, a_day_that_validates(), date="2026-08-29")
    broken = root / "2026" / "08" / "30"
    broken.mkdir(parents=True)
    (broken / "digest.json").write_text("{ not json", encoding="utf-8")

    assert stage_validate_days(root) == 1


def test_a_tree_with_no_committed_day_fails_rather_than_passes(tmp_path: Path) -> None:
    """A run over nothing prints the same line as a run over every day."""
    empty = tmp_path / "digest"
    empty.mkdir()
    assert stage_validate_days(empty) == 1


def test_the_gate_defaults_to_the_one_committed_tree(tmp_path: Path) -> None:
    """Unlike `--site-tree`, which has no default because there are two trees.

    There is exactly one committed digest tree, so a default cannot point at the
    wrong one - and a step nobody has to give a path to is a step nobody gets
    wrong in a workflow.

    One day is named, so this costs one day rather than every day the archive
    has piled up (Rule #12). The receipts go to a directory this test owns: the
    state root defaults to the committed one, and a test that appended to it
    would leave the repository dirty for whoever ran it.
    """
    newest = committed_days()[-1]
    day = "-".join(newest.parts[-4:-1])

    assert main(["validate-days", "--day", day, "--state-root", str(tmp_path)]) == 0


def a_day_missing(names: tuple[str, ...], where: str = "items") -> tuple[str, int]:
    """The committed-day fixture with `names` removed from every `where` entry.

    The read-side migration each of these checks is a property of one payload
    (`CLAUDE.md` section 11), and the committed tree was parsed once per
    published day to re-ask it. Worse, each of those walks counted how many
    entries still LACK the field and failed at zero - a fuse timed to the day the
    last unmigrated payload ages out of retention, which is a date rather than a
    change. Removing the keys here cannot age out.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    stripped = 0
    for entry in payload[where]:
        for name in names:
            entry.pop(name, None)
        stripped += 1
    return json.dumps(payload), stripped


def test_a_committed_day_reads_an_absent_ranking_field_as_unknown() -> None:
    """The read-side migration (`CLAUDE.md` section 11).

    A day written before the five fields existed omits them, and every one must
    come back as `None`. `0` for `carried_by` would claim no feed carried the
    story, `false` for `on_front_page` would claim a vote that was never
    counted, and `0.0` for `rank_score` would put the story bottom of its desk -
    three different false claims dressed as a default.
    """
    text, stripped = a_day_missing(RANKING_SIGNAL)
    assert stripped, "the fixture carries no story, so removing the fields proved nothing"

    day = DigestDay.from_json(text)
    assert len(day.items) == stripped
    for item in day.items:
        for name in RANKING_SIGNAL:
            assert getattr(item, name) is None, f"{item.item_id}: {name} invented"


def test_every_committed_day_revalidates_with_no_shortfall_counts() -> None:
    """The read-side migration for the desk shortfall (`CLAUDE.md` section 11).

    Every day published before 2026-09-02 carries a desk as three keys - id,
    name and count - so the three counts appended later have to be absent and
    have to come back as `None`. A `0` for `considered` would say the sources
    offered that desk nothing, which is the opposite of what a day with 216
    stories on it means.
    """
    text, stripped = a_day_missing(DESK_SHORTFALL, where="verticals")
    assert stripped, "the fixture carries no desk, so removing the counts proved nothing"

    day = DigestDay.from_json(text)
    assert len(day.verticals) == stripped
    for desk in day.verticals:
        for name in DESK_SHORTFALL:
            assert getattr(desk, name) is None, f"{desk.id}: {name} invented"


def test_a_desk_carries_every_shortfall_count_or_none_of_them() -> None:
    """Three fields written by one step, so a desk holding two is a writer bug.

    It also keeps the read side simple: a page asks whether the desk knows why
    it is thin, not whether it knows two thirds of it.
    """
    with pytest.raises(ValueError, match="every shortfall field or none"):
        DigestVerticalRef(id="ai", display_name="AI", count=3, considered=40)

    whole = DigestVerticalRef(
        id="ai", display_name="AI", count=3, considered=40, too_old=31, below_feed_floor=False
    )
    assert whole.considered == 40


def test_a_desk_cannot_drop_more_stories_than_it_considered() -> None:
    """The same bound `VerticalPlan` carries, kept on the field a reader sees.

    The sentence names both numbers, so a payload where the second exceeds the
    first prints a page saying more stories were too old than were ever offered.
    """
    with pytest.raises(ValueError, match="more stories than it considered"):
        DigestVerticalRef(
            id="ai", display_name="AI", count=1, considered=3, too_old=4, below_feed_floor=False
        )


# --- The desk is a field, and the feed's word stays where it is -------------
#
# The oracle of row #6 of TODO/20260910-23-article-classification-plan.md: an
# item whose desk differs from its vertical validates, publishes and renders
# under the desk, with its `item_id` still addressed `<vertical>-`. That
# combination is exactly what repointing `Article.vertical` makes impossible, so
# these prove the choice rather than the code - and they go red the day somebody
# repoints the field.


def _desk_differs_payload() -> dict[str, Any]:
    payload = json.loads(read_text(FIXTURES_DIR / "digest" / "desk-differs-from-vertical.json"))
    assert isinstance(payload, dict)
    return payload


def test_an_item_whose_desk_differs_from_its_vertical_still_carries_its_address() -> None:
    """The whole row in one assertion, on the fixture the row is driven from.

    `energy-9435555854` is an energy feed's story about compute. It publishes
    under the AI desk and keeps the address a reader may already have shared,
    because `item_id` is addressed from the carrying feed's word and that word
    did not move.
    """
    item = DigestItem.model_validate(_desk_differs_payload())
    assert item.vertical == "energy"
    assert item.desk == "ai"
    assert item.item_id.startswith("energy-"), "the published address is the feed's word"


def test_repointing_the_vertical_to_the_desk_is_rejected_at_read_time() -> None:
    """Rejected alternative 1, run rather than described.

    Repointing `vertical` was the earlier draft's plan. The contract's own
    identity rule refuses it on every item whose desk moved - which is why the
    desk is a second field and never a new meaning for the first.
    """
    payload = _desk_differs_payload()
    repointed = {**payload, "vertical": "ai"}
    with pytest.raises(ValueError, match="item_id must be addressed"):
        DigestItem.model_validate(repointed)

    article = json.loads(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    assert article["item_id"].startswith(f"{article['vertical']}-")
    with pytest.raises(ValueError, match="item_id must be addressed"):
        Article.model_validate({**article, "vertical": "energy"})


def test_an_item_published_before_the_desk_existed_reads_as_its_vertical() -> None:
    """The read-side migration, proved by removing the key rather than by waiting.

    Every one of the 22 committed days was written without `desk`. A test that
    counted how many of them still lack it would be timed to go red on the day
    the last one aged out; removing the key from a payload cannot age out.
    """
    payload = _desk_differs_payload()
    del payload["desk"]
    item = DigestItem.model_validate(payload)
    assert item.desk is None, "absent is unknown, never a desk of its own"


def test_a_day_must_list_the_desk_it_published_a_story_under() -> None:
    """A rendered story under a name the payload does not carry is an unnamed page.

    The desk decides the heading, the pill and the topic route, so a day that
    publishes a story under a name its own `verticals` list has never heard of
    draws a page with no display name and no count.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    listed = {ref["id"] for ref in day["verticals"]}
    unlisted = next(name for name in ("world", "india", "business-economy") if name not in listed)
    day["items"][0]["desk"] = unlisted
    with pytest.raises(ValueError, match="names an unlisted desk"):
        DigestDay.model_validate(day)


def test_the_two_counts_answer_two_questions() -> None:
    """`count` is the feed's word and `desk_count` is what the page draws.

    Decision 5: `count` keeps its meaning because 22 frozen published days
    already carry it and a published day is never rewritten. So a relabelled
    story is counted under its vertical by one number and under its desk by the
    other, and neither is allowed to disagree with the items beside it.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    moved = day["items"][0]
    other = next(ref for ref in day["verticals"] if ref["id"] != moved["vertical"])
    home = next(ref for ref in day["verticals"] if ref["id"] == moved["vertical"])
    moved["desk"] = other["id"]

    for ref in day["verticals"]:
        ref["desk_count"] = ref["count"]
    with pytest.raises(ValueError, match="desk_count disagrees"):
        DigestDay.model_validate(day)

    home["desk_count"] = home["count"] - 1
    other["desk_count"] = other["count"] + 1
    settled = DigestDay.model_validate(day)
    by_id = {ref.id: ref for ref in settled.verticals}
    assert by_id[home["id"]].count == home["count"], "the feed's word still counts the story"
    assert by_id[home["id"]].desk_count == home["count"] - 1, "the page no longer draws it here"
    assert by_id[other["id"]].desk_count == other["count"] + 1


def test_a_day_written_before_desk_count_existed_still_reads() -> None:
    """Additive, so the 22 frozen days validate with the key absent everywhere."""
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    for ref in day["verticals"]:
        ref.pop("desk_count", None)
    for item in day["items"]:
        item.pop("desk", None)
    settled = DigestDay.model_validate(day)
    assert all(ref.desk_count is None for ref in settled.verticals)
    assert all(item.desk is None for item in settled.items)


def test_the_served_day_carries_the_desk_a_page_groups_by() -> None:
    """The browser is what groups stories, so the projection may not drop the desk.

    `DigestView` is the copy a reader's browser fetches. A desk the committed
    day knows and this file drops is a grouping the page cannot make.
    """
    day = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    moved = day["items"][0]
    other = next(ref for ref in day["verticals"] if ref["id"] != moved["vertical"])
    moved["desk"] = other["id"]
    view = DigestView.project(day)
    assert view.items[0].desk == other["id"]
    assert view.items[0].vertical == moved["vertical"]


def test_the_thin_desk_floor_is_a_knob_the_frontend_agrees_with() -> None:
    """The two-copies problem again, on the knob that decides whether a desk speaks.

    The rule runs in the browser off the frontend's own default, so a fresh
    clone with no `config/` resolves it there. Let the two drift and the page
    explains a desk the contract would call healthy, or stays silent on one it
    would call thin - and nothing else would catch it.
    """
    reader = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "server" / "config.ts")
    mirrored = re.search(r"desk_thin_max:\s*(\d+),", reader)
    assert mirrored is not None, "the frontend dropped its desk_thin_max default"
    assert int(mirrored.group(1)) == UiConfig().desk_thin_max


def test_a_published_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestDay.model_validate(payload)


def test_a_published_item_with_no_time_may_only_say_unknown() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "unknown"

    day = DigestDay.model_validate(payload)

    assert day.items[0].time_source is TimeSource.UNKNOWN
    assert day.items[0].published_at is None


def test_a_planned_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "first_seen"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        RunPlan.model_validate(payload)


def test_the_ranking_signal_survives_a_round_trip_with_values_in_it() -> None:
    """The fixture carries nulls, so the populated shape needs its own oracle."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0].update(
        carried_by=3, watchlist_hit=True, on_front_page=True, rank_score=3.4, time_source="feed"
    )

    once = DigestDay.model_validate(payload).to_json()
    twice = DigestDay.from_json(once)

    assert twice.to_json() == once
    assert twice.items[0].carried_by == 3
    assert twice.items[0].rank_score == 3.4
    assert twice.items[0].time_source is TimeSource.FEED


def test_a_story_no_feed_carried_cannot_be_published() -> None:
    """`carried_by` counts the feeds that carried one address, so its floor is 1.

    Null is how a run that did not record the count says so. Zero would be a
    story that arrived from nowhere.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    payload["items"][0]["carried_by"] = 0
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        DigestDay.model_validate(payload)


def test_canonical_json_is_sorted_and_newline_terminated() -> None:
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'


# --- the served day --------------------------------------------------------

#: The projector that writes the served file. It runs in node at build time, so
#: the shape lives here and the behaviour lives there - and these tests are what
#: stop the two halves of one payload drifting across two languages.
PROJECT_TS = REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "project.ts"


def projector_array(name: str) -> list[str]:
    match = re.search(
        rf"export const {name}: readonly string\[\] = \[(.*?)\];", read_text(PROJECT_TS), re.DOTALL
    )
    assert match, f"{name} is no longer a string array in project.ts"
    return re.findall(r"'([a-z_]+)'", match.group(1))


def projector_version() -> str:
    match = re.search(r"export const VIEW_VERSION = '([^']+)';", read_text(PROJECT_TS))
    assert match, "VIEW_VERSION is no longer a string literal in project.ts"
    return match.group(1)


def without_description(shape: dict[str, Any]) -> dict[str, Any]:
    """The same field, minus the prose.

    The served item says what an absent value means to a reader; the published
    item says what the run recorded. Different sentences, same field.
    """
    return {key: value for key, value in shape.items() if key != "description"}


def test_the_projector_writes_exactly_the_shape_the_contract_names() -> None:
    """Rule #3, across a language boundary.

    The file a browser fetches is written by node and described by a Pydantic
    model. Nothing else connects them, so a name added on one side and not the
    other ships a payload that does not match its own schema.
    """
    assert projector_version() == DigestView.schema_version()
    assert set(projector_array("ITEM_FIELDS")) == set(DigestViewItem.model_fields)
    assert set(projector_array("VISUAL_FIELDS")) == set(DigestViewVisual.model_fields)
    assert set(projector_array("DAY_FIELDS")) | {"version"} == set(DigestView.model_fields)


def test_the_block_this_projection_exists_to_drop_can_never_be_served() -> None:
    forbidden = set(projector_array("FORBIDDEN_FIELDS"))
    assert "embeddings" in forbidden, "the vector block is why this projection exists"
    kept = set(DigestViewItem.model_fields) | set(DigestView.model_fields)
    assert forbidden.isdisjoint(kept), f"served and forbidden at once: {sorted(forbidden & kept)}"


def test_a_served_day_written_before_the_day_facts_still_reads() -> None:
    """The widening of 2026-09-09 is additive, and this is what says so.

    A service worker keeps day payloads, so a shell built today can be handed a
    file written under `2026-09-01T09:00` - which carries the items and nothing
    else. It has to validate, and every name added since has to read as unknown
    rather than as a value. A default here would be a false claim about a day:
    `false` for `partial` says the run lost nothing, `0` for `items_failed` says
    the same, and an empty `verticals` says the day had no desk.

    Built here rather than read off a committed day, because the archive is
    re-staged on every build and carries no payload at the older stamp any more
    (`CLAUDE.md` section 13).
    """
    day = DigestView.project(
        json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    )
    older = {"version": "2026-09-01T09:00", "items": json.loads(day.to_json())["items"]}

    read = DigestView.model_validate(older)

    assert read.version == "2026-09-01T09:00"
    assert read.items, "an older payload still carries its stories"
    unknown = {name for name in DigestView.model_fields if name not in {"version", "items"}}
    assert unknown, "the day facts are what this test is about"
    for name in sorted(unknown):
        assert getattr(read, name) is None, f"{name} must read as unknown on an older payload"


def test_the_served_item_is_a_narrowing_of_the_published_one() -> None:
    """A field means one thing, whichever file it is in.

    The served day is a projection, not a second vocabulary. Every name on it is
    a name the published item already has, with the same type and the same
    bounds - so a page reading the fetched file and a page reading the committed
    one cannot disagree about what they read.
    """
    published = DigestItem.model_json_schema()["properties"]
    served = DigestViewItem.model_json_schema()["properties"]

    assert set(served) < set(published), "the served item names a field the published one does not"
    for name, shape in served.items():
        if name == "visual":
            continue
        assert without_description(shape) == without_description(published[name]), name

    # The visual is the one field that is itself narrowed: `kind` is read at
    # build time for the console's chart count and no browser needs it.
    assert set(DigestViewVisual.model_fields) < set(DigestVisual.model_fields)


def test_every_committed_day_serves_a_view_that_validates() -> None:
    """The same migration on the projection a reader's browser fetches.

    A day must project to a payload the served contract accepts, and a field the
    file does not carry must come back unknown rather than as a number the run
    never recorded.
    """
    text, stripped = a_day_missing(RANKING_SIGNAL)
    assert stripped, "the fixture carries no story, so removing the fields proved nothing"

    view = DigestView.project(json.loads(text))
    assert len(view.items) == stripped
    for item in view.items:
        for name in RANKING_SIGNAL:
            assert getattr(item, name) is None, f"{item.item_id}: {name} invented"


def test_a_served_day_refuses_a_field_it_does_not_know() -> None:
    """The build is strict where the shell is tolerant, and that pairing is the design.

    A reader's browser must render a payload from a newer build, so its read is
    `JSON.parse` and nothing else. The build has no such excuse: a key nobody
    declared is a projection that widened without a decision, and it fails here
    rather than shipping.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["a_field_from_a_later_build"] = "a value no shell has ever seen"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DigestView.model_validate(payload)


def test_a_served_day_keeps_the_order_a_reader_already_read() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"].insert(0, payload["items"].pop())
    payload["items"][0]["introduced_by_run"] = 2
    with pytest.raises(ValueError, match="never reorders"):
        DigestView.model_validate(payload)


def test_a_served_item_that_names_a_clock_must_carry_a_time() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    payload["items"][0]["published_at"] = None
    payload["items"][0]["time_source"] = "feed"
    with pytest.raises(ValueError, match="names a clock exactly when"):
        DigestView.model_validate(payload)


def test_a_served_day_written_before_the_version_existed_still_reads() -> None:
    """Section 11's release blocker, at the boundary that cannot be upgraded.

    A shell fetching a file this build did not write is the case the version is
    here for. The payload still loads and the stamp says which shape it is.
    """
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "digest-view" / "one-day.json"))
    del payload["version"]

    assert DigestView.model_validate(payload).version == DigestView.schema_version()


# --- a run's own payload, read back after the contract moved -----------------


def _staged(tmp_path: Path, payload: dict[str, Any], name: str = "x.visual.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _a_decision() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json")
    )
    return payload


def test_a_payload_written_before_a_field_was_renamed_is_named_not_called_invalid(
    tmp_path: Path,
) -> None:
    """The real incident, reduced to its two facts.

    Run 33951249328 wrote its visual decisions at 08:23, a field rename merged,
    and the rebuild at 09:03 read them with the new contract. What it reported
    was three validation errors about fields, which points an operator at the
    payload - and the payload is fine. The stamp is what says otherwise, so the
    stamp is what decides.
    """
    payload = _a_decision()
    payload["version"] = "2026-01-01"
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(StalePayloadError) as raised:
        VisualDecision.read(_staged(tmp_path, payload))

    message = str(raised.value)
    assert "2026-01-01" in message, "the stamp the payload was written under is missing"
    assert VisualDecision.schema_version() in message, "the stamp this build reads is missing"
    assert "re-run the stage that wrote it" in message, "the remedy is missing"
    assert isinstance(raised.value.__cause__, ValidationError), "the parser's own error is lost"


def test_a_payload_stamped_with_this_build_is_still_an_ordinary_validation_error(
    tmp_path: Path,
) -> None:
    """The half that keeps this from being a blanket excuse.

    Identical damage, current stamp. Nothing straddled a contract change here,
    so this is a defect in the payload and it must read like one. A guard that
    caught this too would hide every real bug behind a story about timing.
    """
    payload = _a_decision()
    payload["version"] = VisualDecision.schema_version()
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(ValidationError):
        VisualDecision.read(_staged(tmp_path, payload))


def test_an_older_payload_this_build_can_still_read_just_reads(tmp_path: Path) -> None:
    """Most older payloads are readable, and refusing them would be the worse bug.

    A stamp older than the build's is the normal case after any additive change,
    which is what the base class already promises. The stamp selects which
    failure this would be; it never fails on its own.
    """
    payload = _a_decision()
    payload["version"] = "2026-01-01"

    assert VisualDecision.read(_staged(tmp_path, payload)).version == "2026-01-01"


def test_the_payload_a_stale_error_names_leaves_the_process_posix_and_relative(
    tmp_path: Path,
) -> None:
    """CLAUDE.md section 2, at the one boundary this error crosses."""
    payload = _a_decision()
    payload["version"] = "2026-01-01"
    payload["routed_at"] = payload.pop("decided_at")

    with pytest.raises(StalePayloadError) as raised:
        VisualDecision.read(_staged(tmp_path, payload, "world-01.visual.json"))

    named = raised.value.payload
    assert named == "world-01.visual.json"
    assert "\\" not in named and ":" not in named and not named.startswith("/")


def test_every_contract_can_be_read_through_the_stamped_boundary() -> None:
    """The boundary is on the base class, so no contract can be left out of it.

    Cheap to state and worth stating: the next contract someone adds gets this
    for free, and a subclass that quietly replaced `read` fails here.
    """
    boundary = inspect.getattr_static(Contract, "read")
    for model in CONTRACTS:
        assert inspect.getattr_static(model, "read") is boundary, model.__name__


def test_every_console_read_resolves_to_exactly_one_committed_schema() -> None:
    """The inventory's whole job: no dataset without a shape, no shape twice.

    A dataset the console fetches with no schema file is the gap row 8 exists to
    close - the producer, the consumer and the drift gate would each work out
    their own answer. Two files for one shape is the other failure, and it is
    the one that lets a committed shard stop validating.
    """
    for entry in CONSOLE_PAYLOADS:
        stem = entry.contract.__schema_stem__
        assert (SCHEMAS_DIR / f"{stem}.schema.json").is_file(), entry.reader
        assert entry.contract in CONTRACTS, f"{stem} is not exported"

    stems = payloads_by_stem()
    assert len(stems) == 9, "twelve console reads answer off nine shapes"
    assert set(stems) == {entry.contract.__schema_stem__ for entry in CONSOLE_PAYLOADS}


def test_a_console_payload_says_where_it_is_written_and_why_it_crosses() -> None:
    """An inventory row with no destination is a note, not an instruction.

    Row 9 writes these payloads off this list, so a blank `published_to` would
    be a producer with nowhere to put its file. The path is checked for the form
    CLAUDE.md section 2 allows out of a process, because it is copied into a
    workflow's `REFRESH_PATHS` verbatim.
    """
    for entry in CONSOLE_PAYLOADS:
        assert entry.published_to.startswith("frontend/public/"), entry.reader
        assert "\\" not in entry.published_to and ":" not in entry.published_to
        assert entry.why.endswith("."), entry.reader
        assert entry.reader.strip() == entry.reader and entry.reader


@pytest.mark.parametrize(
    ("projection", "source", "expected"),
    [
        (PublicTelemetryRow, ItemHealthRow, {"canonical_url", "url_key", "detail"}),
        (PublicEvalRow, EvalRow, {"url_key", "source_url", "title"}),
        (PublicFeedRow, FeedHealthRow, {"endpoint_key"}),
    ],
)
def test_a_forbidden_cell_is_on_the_ledger_and_off_the_projection(
    projection: type[Contract], source: type[Contract], expected: set[str]
) -> None:
    """A refusal that names a cell nothing has is decoration.

    Both halves matter. A name absent from the source ledger would be a list
    that has drifted off the thing it guards, and would keep passing while the
    real address column crossed under another name. A name present on the
    projection is the leak itself, and the contract module already refuses that
    at import - this says so a second time where a reader looking for the trust
    boundary will find it (Rule #11).
    """
    entry = payloads_by_stem()[projection.__schema_stem__]
    assert entry.forbidden == expected
    assert expected <= set(source.model_fields), "the list has drifted off its ledger"
    assert not (expected & set(projection.model_fields))


def test_a_published_shape_with_no_refusals_says_so_in_its_own_words() -> None:
    """An empty list is a real answer and it needs a reason on the page.

    Six of the nine shapes forbid nothing, because nothing on them came from the
    open web. That is a claim, so the module making it has to state it - an
    empty `frozenset()` with no sentence beside it reads as a list nobody
    filled in.
    """
    for entry in CONSOLE_PAYLOADS:
        if entry.forbidden:
            continue
        source = inspect.getmodule(entry.contract)
        assert source is not None and source.__doc__ is not None, entry.reader
        prose = f"{source.__doc__}\n{entry.why}".lower()
        assert any(
            phrase in prose
            for phrase in ("never the response body", "no cell", "nothing", "our own")
        ), f"{entry.contract.__name__} forbids nothing and does not say why"


def test_the_band_refuses_a_link_that_could_leave_the_site() -> None:
    """The one cell on the band a browser follows.

    A protocol-relative href is an origin wearing a path's clothes, and a site
    that never calls home (Rule #1) must not be able to grow one. The grammar is
    what refuses it, so a producer cannot compose a link out of fetched text.
    """
    for bad in ("//evil.example/", "https://evil.example/", "/console", "/Console/"):
        with pytest.raises(ValidationError):
            ConsoleRoute(
                id=RouteId.MODEL,
                label="Summaries",
                href=bad,
                description="What the model wrote.",
                worst=None,
                severity=0,
                carries="Feed failures are on Pipelines.",
            )


def test_the_band_refuses_a_worst_route_the_strip_does_not_carry() -> None:
    """The strip is the console's only navigation, so a band pointing off it is
    a link that goes nowhere."""
    band = ConsoleBand.read(CONTRACT_FIXTURES_DIR / "console-band" / "newest-day.json")
    assert band.worst is not None
    payload = band.model_dump(mode="json")
    with pytest.raises(ValidationError, match="not on the strip"):
        ConsoleBand.model_validate(payload | {"routes": []})


def test_the_band_refuses_months_that_run_backwards() -> None:
    """The console pans by index, so a repeat or an inversion reads as a jump
    backwards in time rather than as a malformed payload."""
    band = ConsoleBand.read(CONTRACT_FIXTURES_DIR / "console-band" / "newest-day.json")
    payload = band.model_dump(mode="json")
    for months in (["2026-09", "2026-08"], ["2026-08", "2026-08"]):
        with pytest.raises(ValidationError, match="oldest first"):
            ConsoleBand.model_validate(payload | {"months": months})


def test_a_day_cannot_draw_more_charts_than_it_published() -> None:
    """The charts are a subset of the items, counted from the same payload, so a
    row claiming more is a producer that counted two different trees."""
    day = PublicRunDay.read(CONTRACT_FIXTURES_DIR / "public-run-day" / "five-runs.json")
    payload = day.model_dump(mode="json")
    with pytest.raises(ValidationError, match="claims"):
        PublicRunDay.model_validate(payload | {"published_items": 3, "published_charts": 7})


def test_every_published_month_payload_has_a_non_null_retention_knob() -> None:
    """A payload a run appends to with no age is a directory that grows for ever.

    `item_health_aggregate_keep_months` and `score_archive_keep_months` are null
    today and each says in its own description why. Nothing minted for the
    console may join them: a null default that spreads stops reading as a
    decision (CLAUDE.md Rule #12, and row 8's decision 3).
    """
    observability = ObservabilityConfig()
    monthly = {
        entry.published_to.rsplit("/", 1)[0].removeprefix("frontend/public/")
        for entry in CONSOLE_PAYLOADS
        if "<YYYY-MM>" in entry.published_to
    }
    assert monthly == {
        "telemetry",
        "scores",
        "feed-health",
        "run-days",
        "day-metrics",
        "machine",
        "span-rollup",
    }
    for root in monthly:
        knob = f"public_{root.replace('-', '_')}_keep_months"
        months = getattr(observability, knob)
        assert months is not None, f"observability.{knob} may not be null"
        assert months >= months_a_window_can_touch(ConsoleConfig().max_window_days)