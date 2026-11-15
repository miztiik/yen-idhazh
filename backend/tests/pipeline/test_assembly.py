"""What does a failing scorer or a dead model server cost - the item, or the run?"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import CONFIG_DIR, read_text

from idhazh import assemble, cli, config
from idhazh.contracts.base import derive_output_digest
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.evals import metrics
from idhazh.stages import common
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.work import stage_work

from ._builders import (
    SilentCompletionEndpoint,
    a_server_that_refuses_every_completion,
    article,
    captured_article_fetch,
    isolate_ledgers,
    plan,
    row,
    summary,
)


def _saved_completed_item(tmp_path: Path, monkeypatch: MonkeyPatch) -> RunPlan:
    run_plan = plan(item_count=1)
    isolate_ledgers(tmp_path, monkeypatch)
    items = common.VAR_ROOT / run_plan.date / "items"
    items.mkdir(parents=True)
    source = "Officials reportedly approved 12 reactors."
    text = "Officials approved 99 reactors."
    extracted = article().model_copy(
        update={
            "text": source,
            "word_count": metrics.word_count(source),
            "source_word_count": metrics.word_count(source),
            "truncated": False,
        }
    )
    original = summary()
    written = Summary.model_validate(
        {
            **original.model_dump(),
            "summary": text,
            "output_digest": derive_output_digest(text, title=original.title),
        }
    )
    item_id = run_plan.items[0].item_id
    (items / f"{item_id}.article.json").write_text(extracted.to_json(), encoding="utf-8")
    (items / f"{item_id}.summary.json").write_text(written.to_json(), encoding="utf-8")
    return run_plan


def test_an_item_without_an_eval_is_explicitly_unscored(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = _saved_completed_item(tmp_path, monkeypatch)
    day = stage_assemble(
        run_plan, settings=config.load(CONFIG_DIR), commit_sha="a" * 40, runner="fixture"
    )
    assert [(item.band, item.band_reason) for item in day.items] == [
        (ConfidenceBand.MEDIUM, BandReason.NOT_SCORED)
    ]
    manifest = RunManifest.read(assemble.day_dir(common.PUBLIC_ROOT, run_plan.date) / "run.json")
    assert manifest.runs[-1].scorer_version is None


def test_fresh_publication_uses_an_old_rows_hhem_not_its_mixed_band(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = _saved_completed_item(tmp_path, monkeypatch)
    recorded = row(
        version="2026-09-29",
        band=ConfidenceBand.LOW,
    )
    path = common.VAR_ROOT / run_plan.date / "items" / f"{run_plan.items[0].item_id}.eval.json"
    path.write_text(recorded.to_json(), encoding="utf-8")
    day = stage_assemble(
        run_plan, settings=config.load(CONFIG_DIR), commit_sha="a" * 40, runner="fixture"
    )
    assert [(item.band, item.band_reason) for item in day.items] == [(ConfidenceBand.HIGH, None)]
    assert EvalRow.read(path) == recorded
    manifest = RunManifest.read(assemble.day_dir(common.PUBLIC_ROOT, run_plan.date) / "run.json")
    assert manifest.runs[-1].scorer_version == recorded.scorer_version


@pytest.mark.parametrize(
    ("band", "reason"),
    [
        (ConfidenceBand.LOW, BandReason.UNSUPPORTED_NUMBER),
        (ConfidenceBand.MEDIUM, BandReason.HEDGE_DROPPED),
        (ConfidenceBand.LOW, None),
    ],
)
def test_replaying_a_sealed_fragment_keeps_its_original_confidence_decision(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    band: ConfidenceBand,
    reason: BandReason | None,
) -> None:
    run_plan = _saved_completed_item(tmp_path, monkeypatch)
    settings = config.load(CONFIG_DIR)
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")
    path = assemble.fragment_path(common.STATE_ROOT, date=run_plan.date, run_id=run_plan.run_id)
    fragment = DigestRunFragment.read(path)
    sealed = fragment.model_copy(
        update={
            "version": "2026-10-20",
            "items": [
                item.model_copy(update={"band": band, "band_reason": reason})
                for item in fragment.items
            ],
        }
    )
    path.write_text(sealed.to_json(), encoding="utf-8")
    before = path.read_bytes()

    replayed = stage_assemble(
        run_plan, settings=settings, commit_sha="a" * 40, runner="fixture", reuse_fragment=True
    )

    assert [(item.band, item.band_reason) for item in replayed.items] == [(band, reason)]
    assert path.read_bytes() == before


@pytest.mark.parametrize("changed", [{"summary": "Changed saved content."}, {"item_id": "ai-99"}])
def test_replaying_a_fragment_still_refuses_changed_content_or_identity(
    tmp_path: Path, monkeypatch: MonkeyPatch, changed: dict[str, str]
) -> None:
    run_plan = _saved_completed_item(tmp_path, monkeypatch)
    settings = config.load(CONFIG_DIR)
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")
    path = assemble.fragment_path(common.STATE_ROOT, date=run_plan.date, run_id=run_plan.run_id)
    fragment = DigestRunFragment.read(path)
    altered = fragment.model_copy(
        update={"items": [item.model_copy(update=changed) for item in fragment.items]}
    )
    path.write_text(altered.to_json(), encoding="utf-8")

    with pytest.raises(ValueError, match="retained source fragment does not match"):
        stage_assemble(
            run_plan, settings=settings, commit_sha="a" * 40, runner="fixture", reuse_fragment=True
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
    """The server that dies is the one the stage already started against.

    A server that never came up cannot reach this loop any more: the stage reads
    its turn markers off the model's own template first and refuses when nothing
    answers, which is the same refusal production's health check makes before
    the job. So the death is staged where it can still happen - the start-up
    proofs are answered, and then the line closes on every completion with
    nothing on it, which is the shape a process that died mid-shard leaves.
    """
    run_plan = plan(item_count=2)
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    with SilentCompletionEndpoint(holds=False) as server:
        stage_work(
            run_plan,
            settings=config.load(CONFIG_DIR),
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

    assert len(summaries) == len(run_plan.items)
    assert {summary.status for summary in summaries} == {SummaryStatus.FAILED}
    assert {summary.failure_code for summary in summaries} == {FailureCode.MODEL_UNREACHABLE}
    details = [summary.failure_detail or "" for summary in summaries]
    assert all("JSONDecodeError" not in detail for detail in details)
    assert all("shape" not in detail for detail in details)


def test_a_hung_model_request_costs_one_item_not_the_shard(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan(item_count=2)
    settings = config.load(CONFIG_DIR)
    # `model_copy(update=...)` does not validate, so the update has to name a
    # key the model really has. Aimed one level too high it sets an attribute
    # nothing reads, the entry keeps the committed 22.1-minute bound, and this
    # test sits on the hanging endpoint until the job's own timeout kills it.
    summarizer = settings.models.summarizer
    fast_settings = config.Settings(
        council=settings.council,
        app=settings.app,
        ledgers=settings.ledgers,
        models=settings.models.model_copy(
            update={
                "summarizer": summarizer.model_copy(
                    update={"request_timeout_minutes": 0.001}
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

    with SilentCompletionEndpoint(holds=True) as server:
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

    assert server.asked == len(run_plan.items), "one completion post per item"
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
    first item and the loop stops at the top - which is the branch that matters,
    because it is the one that says the shard chose to stop.
    """
    run_plan = plan(item_count=1)
    settings = config.load(CONFIG_DIR)
    out_of_time = config.Settings(
        council=settings.council,
        app=settings.app.model_copy(
            update={
                "run": settings.app.run.model_copy(
                    update={"shard_timeout_minutes": 1, "shard_wrap_up_minutes": 1}
                )
            }
        ),
        ledgers=settings.ledgers,
        models=settings.models,
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")

    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan,
            settings=out_of_time,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )

    written = sorted((tmp_path / "run" / run_plan.date / "items").glob("*.article.json"))
    assert written, "the shard has to write what it fetched before it stops"
    refused = [
        Summary.read(path)
        for path in sorted((tmp_path / "run" / run_plan.date / "items").glob("*.summary.json"))
    ]
    assert len(refused) == len(written), "every item the shard skipped has to say so"
    assert {summary.failure_code for summary in refused} == {FailureCode.SHARD_OUT_OF_TIME}
    # The census row is built from this payload, so a skipped item with none
    # beside it reads `unknown` with "summary payload missing" - a throughput
    # problem filed as a mystery.
    assert all(summary.call_1 is None for summary in refused), (
        "no item should have been sent to the model on a shard with no clock left"
    )
