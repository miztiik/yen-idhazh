"""What does a failing scorer or a dead model server cost - the item, or the run?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text
from pytest import MonkeyPatch

from idhazh import cli, config
from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.item_health import FailureCode
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
    assert {summary.failure_code for summary in summaries} == {FailureCode.MODEL_UNREACHABLE}
