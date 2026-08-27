"""The eleven hard gates, exercised against payloads a run could really write.

No mocks and no network (Rule #7). Every observation here is built from the
committed contracts, and every threshold is read from `EvaluationConfig`,
`RunConfig` and `InferenceConfig` rather than typed into an assertion - a test
that hardcodes 0.5 stops failing the day somebody moves the config knob, which
is exactly the day it should fail.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from idhazh.contracts.app_config import (
    EvaluationConfig,
    InferenceConfig,
    RunConfig,
    SummarizeConfig,
)
from idhazh.contracts.qualification import (
    CanaryObservation,
    CandidateIdentity,
    CorpusItem,
    GateName,
    GateStatus,
    ItemObservation,
    ItemScore,
    QualificationShard,
    ScorerIdentity,
    corpus_digest,
)
from idhazh.evals import qualify

EVALUATION = EvaluationConfig()
INFERENCE = InferenceConfig()
RUN = RunConfig()
SUMMARIZE = SummarizeConfig()

DIGEST = "3" * 64

CANDIDATE = CandidateIdentity(
    model_id="qwen3-5-9b-q4-k-m",
    repo="unsloth/Qwen3.5-9B-GGUF",
    revision="3885219b6810b007914f3a7950a8d1b469d598a5",
    file="Qwen3.5-9B-Q4_K_M.gguf",
    quantisation="Q4_K_M",
    sha256_expected="03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8",
    sha256_observed="03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8",
    bytes_expected=5680522464,
    bytes_observed=5680522464,
    runtime_build="b10598",
)
SCORER = ScorerIdentity(
    scorer_id="hhem-2.1-open",
    revision="8e4a2e6e96c708cc76c2344f7e4757df2515292c",
    pinned=True,
    weights_sha256="4" * 64,
    scorer_version="hhem-2.1-open@8e4a2e6e;weights-44444444;metrics-3;bands=0.80/0.50;lead=0.30",
)


def item(index: int, **overrides: Any) -> CorpusItem:
    words = int(overrides.pop("source_word_count", 900))
    return CorpusItem(
        item_id=f"energy-{index:02d}",
        url_key=f"{index:064x}",
        canonical_url=f"https://example.org/article-{index}",
        source_id="example-wire",
        vertical="energy",
        band_index=qualify.band_index(words, SUMMARIZE),
        brief=bool(overrides.pop("brief", False)),
        truncated=bool(overrides.pop("truncated", False)),
        source_word_count=words,
        seen_word_count=min(words, 1650),
        seen_token_count=min(words * 2, 2500),
        seen_text_sha256=f"{index:064x}".replace("0", "a"),
        full_text_sha256=f"{index:064x}".replace("0", "b"),
        **overrides,
    )


def call(index: int, repeat: int = 1, **overrides: Any) -> ItemObservation:
    base: dict[str, Any] = {
        "item_id": f"energy-{index:02d}",
        "repeat": repeat,
        "ok": True,
        "failure_code": None,
        "finish_reason": "stop",
        "reasoning_channel_used": False,
        "think_block_words": 0,
        "schema_valid": True,
        "repaired": False,
        "output_digest": DIGEST,
        "summary_word_count": 120,
        "prompt_tokens": 3379,
        "completion_tokens": 280,
        "fits_context_predicted": True,
        "summarize_seconds": 176.0,
    }
    return ItemObservation(**{**base, **overrides})


def scored(index: int, **overrides: Any) -> ItemScore:
    base: dict[str, Any] = {
        "item_id": f"energy-{index:02d}",
        "brief": False,
        "hhem": 0.80,
        "hhem_full": 0.77,
        "verbatim_run": 0.10,
        "extractiveness": 0.30,
        "compression": 0.08,
        "lead_coverage": 0.60,
        "unsupported_numbers": 0,
        "hedge_dropped": False,
        "evidential_density": 0.02,
        "speculative_density": 0.005,
        "title_fell_back": False,
    }
    return ItemScore(**{**base, **overrides})


def canary(name: str, **overrides: Any) -> CanaryObservation:
    base: dict[str, Any] = {
        "name": name,
        "replied": True,
        "markers_present": [],
        "facts_missing": [],
        "forbidden_keys_present": [],
    }
    return CanaryObservation(**{**base, **overrides})


CANARY_NAMES = (
    "direct-instruction-override",
    "encoded-payload",
    "exfiltration-via-url",
    "fake-system-delimiter",
    "tool-call-injection",
)


def a_passing_corpus() -> list[CorpusItem]:
    """The registered definition, cleared with room: every tier covered, brief and
    over-cap items present, and enough scored items for the denominator gate."""
    words_by_band = (10, 200, 1200, 3000)
    items: list[CorpusItem] = []
    index = 0
    for words in words_by_band:
        for _ in range(5):
            index += 1
            items.append(item(index, source_word_count=words, brief=words < 60))
    for _ in range(2):
        index += 1
        items.append(item(index, source_word_count=4000, truncated=True))
    return items


def a_passing_shard(**overrides: Any) -> QualificationShard:
    items = overrides.pop("corpus", a_passing_corpus())
    indexes = [int(row.item_id.split("-")[-1]) for row in items]
    base: dict[str, Any] = {
        "version": QualificationShard.schema_version(),
        "date": "2026-08-26",
        "commit_sha": "0" * 40,
        "runner": "ubuntu-latest",
        "shard": 0,
        "shards": 1,
        "repeats": 3,
        "candidate": CANDIDATE,
        "scorer": SCORER,
        "pipeline_fingerprint": "5" * 64,
        "corpus_registered_at": "2026-08-26T06:00:00Z",
        "planned": len(items),
        "corpus": items,
        "observations": [call(i, repeat) for repeat in (1, 2, 3) for i in indexes],
        "scores": [scored(i, brief=row.brief) for i, row in zip(indexes, items, strict=True)],
        "canaries": [canary(name) for name in CANARY_NAMES],
        "elapsed_seconds": 6800.0,
    }
    return QualificationShard(**{**base, **overrides})


def a_passing_budget() -> qualify.Budget:
    return qualify.Budget(
        job_budget_minutes=330.0, slowest_shard_seconds=6800.0, slowest_item_seconds=210.0
    )


def outcomes_of(shard: QualificationShard) -> dict[GateName, Any]:
    _, gates = qualify.gates(
        [shard],
        evaluation=EVALUATION,
        inference=INFERENCE,
        run=RUN,
        budget_=a_passing_budget(),
        required_canaries=len(CANARY_NAMES),
    )
    return {outcome.gate: outcome for outcome in gates}


def with_one_bad_call(
    shard: QualificationShard, index: int = 1, repeat: int = 3, **overrides: Any
) -> QualificationShard:
    """Swap one call in place. Appending instead would give that item a fourth
    repeat and leave another item one short, which changes what the determinism
    gate counts rather than what it finds."""
    replacement = call(index, repeat, **overrides)
    return shard.model_copy(
        update={
            "observations": [
                replacement
                if (o.item_id == replacement.item_id and o.repeat == repeat)
                else o
                for o in shard.observations
            ]
        }
    )


# --- The Oracle: a clean run passes every gate ------------------------------


def test_a_clean_run_passes_all_eleven() -> None:
    outcomes = outcomes_of(a_passing_shard())
    assert set(outcomes) == set(GateName)
    failed = {name: o.measured for name, o in outcomes.items() if o.status is GateStatus.FAILED}
    assert not failed, failed


def test_every_gate_names_where_its_threshold_came_from() -> None:
    """A gate that cannot cite its source is a number somebody typed (Rule #10)."""
    for outcome in outcomes_of(a_passing_shard()).values():
        assert outcome.source.strip()
        assert outcome.measured.strip()
        assert outcome.threshold.strip()


# --- One failure at a time --------------------------------------------------


def test_an_inline_think_block_fails_the_reasoning_gate() -> None:
    broken = with_one_bad_call(a_passing_shard(), think_block_words=12)
    assert outcomes_of(broken)[GateName.REASONING_LEAKAGE].status is GateStatus.FAILED


def test_a_reasoning_channel_fails_the_reasoning_gate() -> None:
    broken = with_one_bad_call(a_passing_shard(), reasoning_channel_used=True)
    assert outcomes_of(broken)[GateName.REASONING_LEAKAGE].status is GateStatus.FAILED


@pytest.mark.parametrize(
    "override",
    [{"finish_reason": "length"}, {"schema_valid": False, "ok": False}, {"repaired": True}],
    ids=["cut-off", "bad-shape", "needed-a-repair"],
)
def test_one_bad_attempt_fails_the_schema_gate(override: dict[str, Any]) -> None:
    broken = with_one_bad_call(a_passing_shard(), **override)
    assert outcomes_of(broken)[GateName.SCHEMA_VALIDITY].status is GateStatus.FAILED


def test_a_surviving_injection_marker_fails_the_canary_gate() -> None:
    shard = a_passing_shard()
    broken = shard.model_copy(
        update={
            "canaries": [
                canary(CANARY_NAMES[0], markers_present=["BREACHED"]),
                *[canary(name) for name in CANARY_NAMES[1:]],
            ]
        }
    )
    outcome = outcomes_of(broken)[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.FAILED
    assert CANARY_NAMES[0] in outcome.measured


def test_a_breach_and_a_silence_do_not_read_the_same() -> None:
    """The reason this gate was rebuilt.

    Both states fail, and both used to produce the identical sentence `4/5
    passed, failing: <name>`. A run on 2026-08-26 failed on a reply that never
    came, with every marker list empty, and two committed documents read that
    sentence as an attacker address surviving the sanitizer. A test that only
    checks `passed` is false for both cases cannot catch that, so this one
    reads the words.
    """
    name = CANARY_NAMES[2]
    others = [canary(other) for other in CANARY_NAMES if other != name]
    breached = outcomes_of(
        a_passing_shard(canaries=[canary(name, markers_present=["collect.canary.example"]), *others])
    )[GateName.INJECTION_CANARIES]
    silent = outcomes_of(
        a_passing_shard(
            canaries=[
                canary(
                    name,
                    replied=False,
                    failure_code="length_out_of_range",
                    failure_detail="the reply was 18 words and the floor is 60",
                ),
                *others,
            ]
        )
    )[GateName.INJECTION_CANARIES]

    assert breached.status is GateStatus.FAILED
    assert silent.status is GateStatus.FAILED
    assert breached.measured != silent.measured, "one sentence for two states is the whole defect"

    assert breached.measured == (
        f"4/5 {qualify.NEUTRALISED}; {name} {qualify.BREACHED} "
        "(1 planted marker(s) in the reply)"
    )
    assert "must_not_survive" in breached.detail
    assert qualify.NOT_EXERCISED not in breached.measured

    assert silent.measured == (
        f"4/5 {qualify.NEUTRALISED}; {name} {qualify.NOT_EXERCISED} (length_out_of_range)"
    )
    assert "no reply came back (length_out_of_range)" in silent.detail
    assert "the reply was 18 words and the floor is 60" in silent.detail
    assert qualify.BREACHED not in silent.measured


def test_a_canary_that_never_replied_still_fails_the_gate() -> None:
    """A control test that did not run is not a control test that passed."""
    shard = a_passing_shard(
        canaries=[
            canary(CANARY_NAMES[0], replied=False, failure_code="model_unreachable"),
            *[canary(name) for name in CANARY_NAMES[1:]],
        ]
    )
    outcome = outcomes_of(shard)[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.FAILED
    assert "model_unreachable" in outcome.measured


def test_a_silent_canary_that_also_lost_its_article_reports_both() -> None:
    """`facts_missing` reads the sanitizer and `replied` reads the model.

    Both can fire on one canary, and naming only the first would hide the other
    - which is the same mistake in a smaller place.
    """
    shard = a_passing_shard(
        canaries=[
            canary(
                CANARY_NAMES[0],
                replied=False,
                failure_code="model_unreachable",
                facts_missing=["The ministry published"],
            ),
            *[canary(name) for name in CANARY_NAMES[1:]],
        ]
    )
    outcome = outcomes_of(shard)[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.FAILED
    assert "must_survive" in outcome.measured
    assert "model_unreachable" in outcome.measured


def test_a_sanitizer_that_ate_the_article_fails_the_canary_gate() -> None:
    """The counter-oracle: an absence check passes trivially on an empty article."""
    shard = a_passing_shard()
    broken = shard.model_copy(
        update={
            "canaries": [
                canary(CANARY_NAMES[0], facts_missing=["the ministry published"]),
                *[canary(name) for name in CANARY_NAMES[1:]],
            ]
        }
    )
    outcome = outcomes_of(broken)[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.FAILED
    assert "sanitization removed 1 fact(s)" in outcome.detail


def test_a_missing_canary_fails_the_gate() -> None:
    shard = a_passing_shard(canaries=[canary(name) for name in CANARY_NAMES[:4]])
    outcome = outcomes_of(shard)[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.FAILED
    # The count is the reason here, and a gate that fails without naming one is
    # the defect this gate was rebuilt to stop.
    assert "1 of 5 canaries never ran" in outcome.measured


def test_a_clean_canary_run_says_so_without_naming_anybody() -> None:
    outcome = outcomes_of(a_passing_shard())[GateName.INJECTION_CANARIES]
    assert outcome.status is GateStatus.PASSED
    assert outcome.measured == f"5/5 {qualify.NEUTRALISED}"


def test_the_two_new_canary_fields_survive_a_round_trip() -> None:
    """Contract tier: the reason is persisted, not just printed."""
    shard = a_passing_shard(
        canaries=[
            canary(
                CANARY_NAMES[0],
                replied=False,
                failure_code="length_out_of_range",
                failure_detail="the reply was 18 words and the floor is 60",
            ),
            *[canary(name) for name in CANARY_NAMES[1:]],
        ]
    )
    restored = QualificationShard.from_json(shard.to_json())
    assert restored.canaries[0].failure_code == "length_out_of_range"
    assert restored.canaries[0].failure_detail == "the reply was 18 words and the floor is 60"
    assert restored.canaries[1].failure_code is None
    assert restored.canaries[1].failure_detail is None


def test_a_shard_written_before_today_still_validates() -> None:
    """Both fields are additive and nullable, so no read-side migration is owed."""
    payload: dict[str, Any] = json.loads(a_passing_shard().to_json())
    for observation in payload["canaries"]:
        del observation["failure_code"]
        del observation["failure_detail"]
    payload["version"] = "2026-08-26"
    restored = QualificationShard.model_validate(payload)
    assert all(c.failure_code is None for c in restored.canaries)


def test_a_second_output_digest_on_one_item_fails_determinism() -> None:
    broken = with_one_bad_call(a_passing_shard(), output_digest="9" * 64)
    outcome = outcomes_of(broken)[GateName.DETERMINISM]
    assert outcome.status is GateStatus.FAILED
    assert "energy-01" in outcome.detail


def test_a_failed_call_is_not_counted_as_a_determinism_violation() -> None:
    """A call that never replied has no digest. Counting it would blame decoding
    for a network fault - the schema gate already fails on it."""
    broken = with_one_bad_call(
        a_passing_shard(), ok=False, schema_valid=False, output_digest="0" * 64
    )
    assert outcomes_of(broken)[GateName.DETERMINISM].status is GateStatus.PASSED


def test_a_summary_outside_the_publishable_range_fails() -> None:
    broken = with_one_bad_call(
        a_passing_shard(), summary_word_count=EVALUATION.summary_words_max + 1
    )
    assert outcomes_of(broken)[GateName.PUBLISHABLE_LENGTH].status is GateStatus.FAILED


def test_a_request_that_does_not_fit_the_context_fails() -> None:
    over = INFERENCE.n_ctx - INFERENCE.max_output_tokens + 1
    broken = with_one_bad_call(a_passing_shard(), prompt_tokens=over)
    outcome = outcomes_of(broken)[GateName.CONTEXT_FIT]
    assert outcome.status is GateStatus.FAILED
    assert str(INFERENCE.n_ctx) in outcome.threshold


def test_the_cheap_predictor_may_not_under_reserve() -> None:
    """`fits_context` saying yes to a request that overflows is the failure mode
    the gate exists for: it is the check that runs before every production call."""
    over = INFERENCE.n_ctx - INFERENCE.max_output_tokens + 1
    broken = with_one_bad_call(
        a_passing_shard(), prompt_tokens=over, fits_context_predicted=True
    )
    assert "under-reserved" in outcomes_of(broken)[GateName.CONTEXT_FIT].measured


def test_bytes_that_are_not_the_target_fail_identity() -> None:
    shard = a_passing_shard(
        candidate=CANDIDATE.model_copy(update={"sha256_observed": "f" * 64})
    )
    outcome = outcomes_of(shard)[GateName.IDENTITY]
    assert outcome.status is GateStatus.FAILED
    assert CANDIDATE.sha256_expected in outcome.threshold


def test_a_job_past_its_bound_fails_the_budget_gate() -> None:
    corpus, gates = qualify.gates(
        [a_passing_shard()],
        evaluation=EVALUATION,
        inference=INFERENCE,
        run=RUN,
        budget_=qualify.Budget(
            job_budget_minutes=330.0, slowest_shard_seconds=331 * 60, slowest_item_seconds=900.0
        ),
        required_canaries=len(CANARY_NAMES),
    )
    assert corpus.planned == len(a_passing_corpus())
    budget = next(o for o in gates if o.gate is GateName.BUDGET)
    assert budget.status is GateStatus.FAILED
    assert "-1.0 min" in budget.detail


def test_too_few_scored_items_fails_the_denominator_gate() -> None:
    shard = a_passing_shard()
    thin = shard.model_copy(update={"scores": shard.scores[:2]})
    outcome = outcomes_of(thin)[GateName.SCORED_DENOMINATOR]
    assert outcome.status is GateStatus.FAILED
    assert str(EVALUATION.validation_articles) in outcome.threshold


def test_an_item_that_never_summarized_stays_in_the_denominator() -> None:
    """The rate is over the frozen corpus, so a scored list shorter than the
    corpus is a failure the run has to carry rather than quietly drop."""
    shard = a_passing_shard()
    lost = len(shard.corpus) // 2
    thin = shard.model_copy(update={"scores": shard.scores[lost:]})
    outcome = outcomes_of(thin)[GateName.SCORED_DENOMINATOR]
    assert f"of {len(shard.corpus)} frozen" in outcome.measured
    assert outcome.status is GateStatus.FAILED


def test_the_full_attempted_denominator_is_recorded() -> None:
    """Addresses consumed is a fact about the web, so it is printed next to the
    rate rather than folded into it - a dead link is not a model defect."""
    shard = a_passing_shard()
    wider = shard.model_copy(update={"planned": 40})
    outcome = outcomes_of(wider)[GateName.SCORED_DENOMINATOR]
    assert "40 addresses attempted" in outcome.measured
    assert outcome.status is GateStatus.PASSED


def test_a_mean_below_the_medium_band_fails_the_faithfulness_floor() -> None:
    shard = a_passing_shard()
    low = EVALUATION.band_medium_min - 0.1
    broken = shard.model_copy(
        update={"scores": [s.model_copy(update={"hhem": low}) for s in shard.scores]}
    )
    assert outcomes_of(broken)[GateName.FAITHFULNESS_FLOOR].status is GateStatus.FAILED


def test_an_unpinned_scorer_fails_the_faithfulness_floor_whatever_the_mean() -> None:
    """The precondition is the gate. A floor read off an instrument that can move
    overnight measures an unknown instrument, however good the number looks."""
    shard = a_passing_shard(
        scorer=SCORER.model_copy(update={"revision": "main", "pinned": False})
    )
    outcome = outcomes_of(shard)[GateName.FAITHFULNESS_FLOOR]
    assert outcome.status is GateStatus.FAILED
    assert "UNPINNED" in outcome.measured


def test_a_copied_brief_fails_the_copying_ceiling() -> None:
    shard = a_passing_shard()
    over = EVALUATION.brief_compression_ceiling + 0.1
    broken = shard.model_copy(
        update={
            "scores": [
                s.model_copy(update={"verbatim_run": over}) if s.brief else s
                for s in shard.scores
            ]
        }
    )
    assert outcomes_of(broken)[GateName.BRIEF_COPYING_CEILING].status is GateStatus.FAILED


def test_a_copied_long_article_does_not_fail_the_brief_ceiling() -> None:
    """The ceiling is a brief-path bar. Non-brief copying is a diagnostic - there
    is no committed threshold for it that is not the confounded 8B history."""
    shard = a_passing_shard()
    over = EVALUATION.brief_compression_ceiling + 0.1
    broken = shard.model_copy(
        update={
            "scores": [
                s.model_copy(update={"verbatim_run": over}) if not s.brief else s
                for s in shard.scores
            ]
        }
    )
    assert outcomes_of(broken)[GateName.BRIEF_COPYING_CEILING].status is GateStatus.PASSED


# --- The corpus is the measuring stick, not the candidate -------------------


def test_the_registered_corpus_definition_is_met() -> None:
    assert qualify.corpus_shortfalls(a_passing_corpus(), summarize=SUMMARIZE) == []


def test_a_missing_length_tier_is_named() -> None:
    thin = [row for row in a_passing_corpus() if row.band_index != 0]
    shortfalls = qualify.corpus_shortfalls(thin, summarize=SUMMARIZE)
    assert any("band 0" in line for line in shortfalls)


def test_a_corpus_with_no_brief_item_is_named() -> None:
    thin = [row for row in a_passing_corpus() if not row.brief]
    assert any("brief-path" in line for line in qualify.corpus_shortfalls(thin, summarize=SUMMARIZE))


def test_a_corpus_with_no_truncated_item_is_named() -> None:
    thin = [row for row in a_passing_corpus() if not row.truncated]
    assert any(
        "truncation cap" in line for line in qualify.corpus_shortfalls(thin, summarize=SUMMARIZE)
    )


def test_two_shards_freezing_one_address_is_refused() -> None:
    """One item, one capture. Two shards on one page is the refetch the frozen
    corpus exists to forbid."""
    shard = a_passing_shard()
    with pytest.raises(ValueError, match="more than one shard"):
        qualify.merge([shard, shard.model_copy(update={"shard": 1})])


def test_shards_that_disagree_about_repeats_are_refused() -> None:
    shard = a_passing_shard()
    other = a_passing_shard(
        corpus=[item(90 + n, source_word_count=900) for n in range(3)],
        shard=1,
        repeats=2,
        observations=[],
        scores=[],
        canaries=[],
    )
    with pytest.raises(ValueError, match="disagree about the repeat count"):
        qualify.merge([shard, other])


# --- Diagnostics: recorded, never blocking ----------------------------------


def test_every_diagnostic_carries_its_denominator() -> None:
    corpus = qualify.merge([a_passing_shard()])
    rows = qualify.diagnostics(corpus, evaluation=EVALUATION)
    assert rows
    assert all(row.denominator == len(corpus.scores) or row.denominator >= 0 for row in rows)
    assert {row.name for row in rows} >= {
        "unsupported_numbers_total",
        "hedge_dropped_rate",
        "below_lead_coverage_min_share",
        "hhem_mean",
        "hhem_spread",
        "compression_mean",
        "generated_title_fallback_rate",
        "decode_tokens_per_second_median",
    }


def test_a_demoted_metric_does_not_block() -> None:
    """Unsupported numbers, dropped hedges and thin lead coverage were hard gates
    until 2026-08-26. Every threshold they could take came from the confounded
    8B history, so they record and never fail the run."""
    shard = a_passing_shard()
    noisy = shard.model_copy(
        update={
            "scores": [
                s.model_copy(
                    update={"unsupported_numbers": 4, "hedge_dropped": True, "lead_coverage": 0.0}
                )
                for s in shard.scores
            ]
        }
    )
    outcomes = outcomes_of(noisy)
    assert all(outcome.status is GateStatus.PASSED for outcome in outcomes.values())


def test_the_stratification_is_recorded_with_the_corpus_size() -> None:
    rows = qualify.stratification(a_passing_corpus(), summarize=SUMMARIZE)
    assert {row.name for row in rows} >= {"over_truncation_cap", "brief_path"}
    assert all(row.denominator == len(a_passing_corpus()) for row in rows)


def test_the_corpus_digest_does_not_depend_on_capture_order() -> None:
    items = a_passing_corpus()
    assert corpus_digest(items) == corpus_digest(list(reversed(items)))


def test_a_rewritten_page_changes_the_corpus_digest() -> None:
    items = a_passing_corpus()
    moved = [items[0].model_copy(update={"seen_text_sha256": "c" * 64}), *items[1:]]
    assert corpus_digest(items) != corpus_digest(moved)
