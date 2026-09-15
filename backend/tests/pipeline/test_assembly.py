"""What does a failing scorer or a dead model server cost - the item, or the run?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text
from pytest import MonkeyPatch

from idhazh import cli, config
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals.score import band
from idhazh.stages import common
from idhazh.stages.work import stage_work

from ._builders import (
    HangingLoopbackEndpoint,
    captured_article_fetch,
    closed_loopback_endpoint,
    plan,
)

pytestmark = pytest.mark.slow


def test_the_counterweights_alone_never_claim_the_top_band() -> None:
    """Without a faithfulness score there is no basis for claiming high confidence."""
    assert (
        band(
            None,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.MEDIUM
    )


def test_an_invented_number_still_reaches_the_reader_as_low() -> None:
    assert (
        band(
            None,
            unsupported_numbers=1,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.LOW
    )


def test_a_summary_that_dropped_the_lead_reaches_the_reader_as_medium() -> None:
    assert (
        band(
            None,
            unsupported_numbers=0,
            lead_coverage=0.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.MEDIUM
    )


def test_a_scorer_that_will_not_load_costs_rows_not_the_digest(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The first real runner attempt died here: a transformers upgrade broke the
    checkpoint's own modelling code and all four workers exited before
    summarizing anything. Losing the scorer must cost eval rows and nothing else.
    """

    def explode(self: object) -> None:
        raise AttributeError("'HHEMv2ForSequenceClassification' has no 'all_tied_weights_keys'")

    monkeypatch.setattr("idhazh.evals.hhem.HhemScorer.load", explode)
    assert cli._scorer(enabled=True) is None


def test_a_dead_model_server_marks_every_item_without_parsing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    stage_work(
        run_plan,
        settings=config.load(CONFIG_DIR),
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )

    summaries = [
        Summary.from_json(
            read_text(tmp_path / "run" / run_plan.date / "items" / f"{item.item_id}.summary.json")
        )
        for item in run_plan.items
    ]

    assert len(summaries) == len(run_plan.items)
    assert {summary.status for summary in summaries} == {SummaryStatus.FAILED}
    assert {summary.failure_code for summary in summaries} == {FailureCode.MODEL_UNREACHABLE}
    details = [summary.failure_detail or "" for summary in summaries]
    assert all("JSONDecodeError" not in detail for detail in details)
    assert all("shape" not in detail for detail in details)


def test_a_hung_model_request_costs_one_item_not_the_shard(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    # `model_copy(update=...)` does not validate, so the update has to name a
    # key the model really has. Aimed one level too high it sets an attribute
    # nothing reads, the request keeps the committed 22.1-minute bound, and this
    # test sits on the hanging endpoint until the job's own timeout kills it.
    summarizer = settings.models.summarize
    fast_settings = config.Settings(
        app=settings.app,
        models=settings.models.model_copy(
            update={
                "summarize": summarizer.model_copy(
                    update={
                        "inference": summarizer.inference.model_copy(
                            update={"request_timeout_minutes": 0.01}
                        )
                    }
                )
            }
        ),
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    with HangingLoopbackEndpoint() as server:
        stage_work(
            run_plan,
            settings=fast_settings,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )

    summaries = [
        Summary.from_json(
            read_text(tmp_path / "run" / run_plan.date / "items" / f"{item.item_id}.summary.json")
        )
        for item in run_plan.items
    ]

    assert server.accepted == len(run_plan.items) + 1, "one post per item, plus the props read"
    assert len(summaries) == len(run_plan.items)
    assert {summary.status for summary in summaries} == {SummaryStatus.FAILED}
    # Until 2026-09-15 this line read MODEL_UNREACHABLE and passed, because a
    # socket timeout is a TimeoutError and TimeoutError subclasses OSError. The
    # server here accepts every request and answers none, which is the one thing
    # an unreachable server cannot do - so the assertion documented the defect
    # instead of catching it.
    assert {summary.failure_code for summary in summaries} == {FailureCode.MODEL_TIMED_OUT}
    assert all(
        "did not answer" in (summary.failure_detail or "") for summary in summaries
    ), "the detail has to send an operator to the output budget, not to the process"


def test_a_shard_out_of_clock_stops_itself_instead_of_being_killed(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A worker killed on the platform's timeout uploads nothing.

    On 2026-09-15 two of four shards ended that way: every item they had already
    finished died with the ones they had not started, and the day published 66
    stories against a plan of 80. A worker that stops on its own clock writes
    what it has and names what it skipped.

    The whole shard timeout is spent here, so the deadline is already behind the
    first item and the loop stops at the top - which is the arm that matters,
    because it is the one that says the shard chose to stop.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    out_of_time = config.Settings(
        app=settings.app.model_copy(
            update={
                "run": settings.app.run.model_copy(
                    update={"shard_timeout_minutes": 1, "shard_wrap_up_minutes": 1}
                )
            }
        ),
        models=settings.models,
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    stage_work(
        run_plan,
        settings=out_of_time,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )

    written = sorted((tmp_path / "run" / run_plan.date / "items").glob("*.article.json"))
    assert written, "the shard has to write what it fetched before it stops"
    assert not sorted((tmp_path / "run" / run_plan.date / "items").glob("*.summary.json")), (
        "no item should have been sent to the model on a shard with no clock left"
    )
