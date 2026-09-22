"""Does the qualification gate summarize the way the digest summarizes?"""

from __future__ import annotations

import test_qualify as built
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh import config
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.qualification import (
    GateStatus,
    ItemObservation,
    QualificationShard,
)
from idhazh.contracts.summary import Summary
from idhazh.evals import qualification_summary
from idhazh.evals.qualify import schema_validity
from idhazh.llm.server import Completion
from idhazh.stages import qualify


def an_article() -> Article:
    """The contract fixture, read inside the test that wants it (section 13)."""
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


def a_summary() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


def a_reply(
    *,
    reasoning: str = "",
    finish_reason: str = "stop",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    prefill_ms: int = 0,
    decode_ms: int = 0,
) -> Completion:
    """One reply carrying only the fields an observation reads."""
    return Completion(
        content='{"summary": "x"}',
        reasoning=reasoning,
        finish_reason=finish_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
    )


def folded(*replies: Completion | None) -> ItemObservation:
    """One item's observation, through the real fold."""
    return qualify._observe(
        an_article(),
        a_summary(),
        replies,
        repeat=1,
        server=built.SERVER,
        seconds=1.0,
    )


def test_the_switch_and_the_number_a_shard_records_cannot_disagree() -> None:
    """A shard claiming one call while making two invites a false comparison.

    Two shards are comparable only when they measured the same work, and
    `calls_per_item` is the only thing in the payload that says whether they
    did (CLAUDE.md Guardrail #10). One function owns the mapping, so a later
    edit cannot move the behaviour without moving the number.
    """
    assert qualify.calls_per_item(RunConfig(qualify_on_the_production_path=True)) == 2
    assert qualify.calls_per_item(RunConfig(qualify_on_the_production_path=False)) == 1


def test_the_committed_config_qualifies_on_the_path_the_digest_runs() -> None:
    """A gate that clears a call path nothing publishes has cleared nothing."""
    assert config.load().app.run.qualify_on_the_production_path is True


def test_a_budget_met_in_the_first_call_counts_the_item_as_cut() -> None:
    """A pair whose first decode was truncated did not finish.

    The schema gate reads a `stop` as a clean completion. Taking the last
    reply's word for it would report a cut item as clean on every pair where
    the label call ran out of budget and the summarize call did not - which is
    the common shape, because the label reply is the long one.
    """
    assert folded(a_reply(finish_reason="length"), a_reply()).finish_reason == "length"


def test_the_token_counts_are_the_pairs_sum_rather_than_one_calls() -> None:
    """Both calls really spent what they spent.

    Recording one call's numbers for an item that made two halves the item's
    cost, and a shard's cost readings are what size the job budget.
    """
    observation = folded(
        a_reply(prompt_tokens=1100, completion_tokens=400),
        a_reply(prompt_tokens=1600, completion_tokens=250),
    )

    assert observation.prompt_tokens == 2700
    assert observation.completion_tokens == 650


def test_a_reasoning_channel_opened_in_either_call_is_one_the_item_used() -> None:
    """The leak is that the model reasoned at all, not which call it did it in."""
    assert folded(a_reply(reasoning="  thinking  "), a_reply()).reasoning_channel_used is True


def test_a_call_that_never_happened_contributes_nothing_and_raises_nothing() -> None:
    """An item that died between the calls still records the call that ran.

    `two_calls_one_item` hands back None for the call it never made. Counting
    that as a reply would record a zero-token stop for a call that does not
    exist; refusing to fold it would lose the one that does.
    """
    observation = folded(a_reply(prompt_tokens=900, completion_tokens=120), None)

    assert observation.prompt_tokens == 900
    assert observation.completion_tokens == 120


def test_an_item_with_no_reply_at_all_still_produces_an_observation() -> None:
    """A failure that vanishes from the record takes the denominator with it.

    It names no reason, and until 2026-09-16 it named `stop`. The fold stands a
    bare `Completion` in for the replies that never arrived, and that stand-in
    inherited a default of `stop` - so an item the server never answered was
    counted by `schema_validity` as an attempt that decoded cleanly.
    """
    observation = folded(None, None)

    assert observation.prompt_tokens == 0
    assert observation.finish_reason is None
    assert schema_validity([observation]).status is GateStatus.FAILED


def test_the_job_page_says_which_path_produced_its_numbers_before_the_table() -> None:
    """A reader who finds the footnote afterwards has already compared wrongly."""
    page = qualification_summary.render_shard(built.a_passing_shard(calls_per_item=2))
    before_the_table = page.split("| Reading | Value |")[0]

    assert "2 calls per item" in before_the_table
    assert "the path the digest runs" in before_the_table


def test_a_single_call_page_says_the_digest_does_not_run_that_path() -> None:
    """The losing side of the switch has to be as legible as the winning one."""
    page = qualification_summary.render_shard(built.a_passing_shard(calls_per_item=1))

    assert "One call per item" in page
    assert "the digest does not run" in page


def test_a_shard_written_before_the_switch_reads_as_one_call() -> None:
    """The read-side migration, proved by leaving the key out.

    A shard is a workflow artifact rather than a committed file, so nothing on
    disk needs migrating - but a re-read of an artifact from an older run must
    not silently become a two-call reading.
    """
    payload = built.a_passing_shard().model_dump(mode="json")
    del payload["calls_per_item"]

    assert QualificationShard.model_validate(payload).calls_per_item == 1


def test_an_observation_keeps_prefill_and_decode_apart() -> None:
    """One rate over both describes neither: prefill scales with the article and
    decode with the summary. The pair is summed, because the item paid for both."""
    observation = folded(
        a_reply(prefill_ms=4000, decode_ms=1000),
        a_reply(prefill_ms=500, decode_ms=9000),
    )

    assert observation.prefill_ms == 4500
    assert observation.decode_ms == 10000


def test_a_runtime_that_reported_no_timings_leaves_them_null() -> None:
    """A zero would read as a call that took no time to prefill. Null says unknown."""
    observation = folded(a_reply())

    assert observation.prefill_ms is None
    assert observation.decode_ms is None


def test_a_shard_written_before_the_split_still_reads() -> None:
    """The read-side migration, proved by leaving the keys out rather than by
    counting how many committed payloads still lack them."""
    payload = built.a_passing_shard().model_dump(mode="json")
    for observation in payload["observations"]:
        del observation["prefill_ms"]
        del observation["decode_ms"]

    restored = QualificationShard.model_validate(payload)

    assert all(o.prefill_ms is None and o.decode_ms is None for o in restored.observations)