"""Integration-tier tests for the stages that compose the run.

These drive real payloads through config loading, scoring, ledger writing and
assembly, with the faithfulness model standing in as a recorded number - the
model is not what is under test here, the composition is (CLAUDE.md section 13).

No mocks and no network. The recorded score is a float, not a stub object.
"""

from __future__ import annotations

import csv
import json
import socket
import threading
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh import assemble, cli, config, ledger
from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_output_digest
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.fingerprint import FingerprintRow
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome
from idhazh.contracts.route import Route
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.sources import FeedDef, SourceForm
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier
from idhazh.evals import writer
from idhazh.evals.hhem import chunks, score_over_chunks
from idhazh.evals.score import band, to_eval_row, verdict
from idhazh.fetch import FetchResult
from idhazh.fingerprint import read_ledger, text_digest

FULL_TEXT = (
    "Example Lab released a smaller model on Friday, claiming a 34 percent lower cost per "
    "million tokens and 2.1 times the throughput of the model it replaces on commodity "
    "processors. The weights are published under a permissive licence. The company did not "
    "say when the model being replaced will be retired."
)


def article() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


def summary() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


def plan() -> RunPlan:
    return RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))


def row(**overrides: object) -> EvalRow:
    item = plan().items[0]
    built = to_eval_row(
        item=item,
        article=article(),
        summary=summary(),
        full_text=FULL_TEXT,
        hhem=0.91,
        hhem_full=0.89,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-1;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )
    return built.model_copy(update=overrides) if overrides else built


def closed_loopback_endpoint() -> str:
    """Return a loopback port that refused a real socket before the test used it."""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        port = int(server.getsockname()[1])
    return f"http://127.0.0.1:{port}/v1/chat/completions"


def test_work_items_sort_by_summarize_band_and_keep_in_band_order() -> None:
    """Band order groups identical system prompts without changing item identity."""
    settings = config.load(CONFIG_DIR)
    items = plan().items
    base = article()

    def sized(words: int) -> Article:
        # Both counts, because the band follows the source body and the sort
        # has to agree with the prompt it is grouping.
        return base.model_copy(update={"word_count": words, "source_word_count": words})

    candidates = [
        cli._FetchedWorkItem(items[0], sized(2000), 0, 0, 0.0, 0),
        cli._FetchedWorkItem(items[1], sized(10), 0, 0, 0.0, 1),
        cli._FetchedWorkItem(items[2], sized(800), 0, 0, 0.0, 2),
        cli._FetchedWorkItem(items[3], sized(100), 0, 0, 0.0, 3),
    ]

    ordered = sorted(candidates, key=lambda candidate: cli._summarize_band_sort_key(candidate, settings))

    assert [candidate.item.item_id for candidate in ordered] == ["ai-02", "ai-04", "ai-03", "ai-01"]


class HangingLoopbackEndpoint:
    """A real local socket that accepts requests and never writes a response."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._server = socket.socket()
        self._server.bind(("127.0.0.1", 0))
        self._server.listen()
        self._server.settimeout(0.05)
        self._connections: list[socket.socket] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def endpoint(self) -> str:
        port = int(self._server.getsockname()[1])
        return f"http://127.0.0.1:{port}/v1/chat/completions"

    @property
    def accepted(self) -> int:
        return len(self._connections)

    def __enter__(self) -> HangingLoopbackEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._server.close()
        for connection in self._connections:
            connection.close()
        self._thread.join(timeout=1.0)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except OSError:
                continue
            self._connections.append(connection)
            threading.Thread(target=self._hold, args=(connection,), daemon=True).start()

    def _hold(self, connection: socket.socket) -> None:
        try:
            while not self._stop.wait(0.05):
                pass
        finally:
            connection.close()


def captured_article_fetch(_url: str) -> FetchResult:
    page = read_text(FIXTURES_DIR / "pages" / "article.html")
    extra = (
        "<p>The filing also says the utility will publish quarterly milestones, "
        "including site work, equipment orders, safety reviews and expected fuel "
        "delivery dates, so residents can track whether the schedule is moving. "
        "Officials said each update will name the missed date when a milestone "
        "slides, rather than leaving the change to be inferred from a later plan.</p>"
    )
    body = page.replace("</article>", f"{extra}</article>").encode("utf-8")
    return FetchResult(FetchOutcome.OK, status=200, body=body)


# --- Config -----------------------------------------------------------------


def test_a_fresh_clone_loads_its_committed_config() -> None:
    settings = config.load(CONFIG_DIR)
    assert settings.app.run.safety_ceiling_per_run >= 1
    assert settings.sources.feeds
    assert settings.taxonomy.verticals


def test_the_config_that_was_read_travels_with_the_run() -> None:
    """A knob edited between two runs changes every output and is otherwise invisible."""
    digests = config.load(CONFIG_DIR).digests
    assert {digest.path for digest in digests} == {
        "config/idhazh.json",
        "config/sources.json",
        "config/taxonomy.json",
        "config/watchlist.json",
    }
    assert all(len(digest.sha256) == 64 for digest in digests)


def test_a_missing_config_file_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        config.load(tmp_path)


# --- Banding ----------------------------------------------------------------


def test_the_bands_come_from_config() -> None:
    tuned = EvaluationConfig(band_high_min=0.9, band_medium_min=0.6)
    assert (
        band(
            0.95,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.HIGH
    )
    assert (
        band(
            0.7,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.MEDIUM
    )
    assert (
        band(
            0.5,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.LOW
    )


def test_an_invented_number_outvotes_a_perfect_faithfulness_score() -> None:
    """Nothing else in the row can see that defect, so nothing else may outvote it."""
    assert (
        band(
            1.0,
            unsupported_numbers=1,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.LOW
    )


def test_a_band_below_the_top_says_what_is_missing() -> None:
    """A grade tells a reader an item is worse. A reason tells them what to check.

    Both counterweights were already computed and neither reached the page.
    """
    tuned = EvaluationConfig()

    def reason_for(
        faithfulness: float | None,
        *,
        unsupported_numbers: int = 0,
        lead_coverage: float = 1.0,
        hedge_dropped: bool = False,
    ) -> tuple[ConfidenceBand, BandReason | None]:
        return verdict(
            faithfulness,
            unsupported_numbers=unsupported_numbers,
            lead_coverage=lead_coverage,
            hedge_dropped=hedge_dropped,
            config=tuned,
        )

    assert reason_for(0.95) == (ConfidenceBand.HIGH, None), "nothing to explain"
    assert reason_for(0.95, lead_coverage=0.0) == (ConfidenceBand.MEDIUM, BandReason.LEAD_MISSING)
    assert reason_for(0.95, hedge_dropped=True) == (ConfidenceBand.MEDIUM, BandReason.HEDGE_DROPPED)
    assert reason_for(0.6) == (ConfidenceBand.MEDIUM, BandReason.FAITHFULNESS)
    assert reason_for(0.2) == (ConfidenceBand.LOW, BandReason.FAITHFULNESS)
    assert reason_for(None) == (ConfidenceBand.MEDIUM, BandReason.NOT_SCORED)
    assert reason_for(1.0, unsupported_numbers=1) == (
        ConfidenceBand.LOW,
        BandReason.UNSUPPORTED_NUMBER,
    )

    # Both counterweights fail together on real rows. The reader gets one
    # sentence, and dropped facts are the larger loss.
    assert reason_for(0.95, lead_coverage=0.0, hedge_dropped=True) == (
        ConfidenceBand.MEDIUM,
        BandReason.LEAD_MISSING,
    )


def test_the_band_and_its_reason_are_decided_once() -> None:
    """Two code paths would eventually print a reason that is not why."""
    for faithfulness in (None, 0.2, 0.6, 0.95):
        for coverage in (0.0, 1.0):
            for hedged in (False, True):
                assert band(
                    faithfulness,
                    unsupported_numbers=0,
                    lead_coverage=coverage,
                    hedge_dropped=hedged,
                    config=EvaluationConfig(),
                ) is verdict(
                    faithfulness,
                    unsupported_numbers=0,
                    lead_coverage=coverage,
                    hedge_dropped=hedged,
                    config=EvaluationConfig(),
                ).band


# --- The row ----------------------------------------------------------------


def test_a_row_carries_everything_needed_to_read_it_years_later() -> None:
    built = row()
    assert built.source_url.startswith("http")
    assert built.title
    assert built.date == "2026-08-21"
    assert built.scorer_version


def test_the_truncation_gap_is_computed_not_asserted() -> None:
    built = row()
    assert built.hhem_delta == pytest.approx(0.02)
    assert not built.truncation_flagged


def test_a_wide_gap_is_flagged_as_a_truncation_artifact() -> None:
    item = plan().items[0]
    built = to_eval_row(
        item=item,
        article=article(),
        summary=summary(),
        full_text=FULL_TEXT,
        hhem=0.94,
        hhem_full=0.61,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="v",
        scored_at="2026-08-21T06:18:02Z",
    )
    assert built.truncation_flagged


def test_a_copied_brief_is_flagged_as_truncation_not_confidence() -> None:
    copied = "alpha beta gamma delta epsilon zeta eta theta"
    source = article().model_copy(update={"brief": True})
    brief_summary = summary().model_copy(
        update={
            "summary": "alpha beta gamma delta epsilon",
            "key_points": ["short copied point"],
        }
    )
    brief_summary = brief_summary.model_copy(
        update={
            "output_digest": derive_output_digest(
                brief_summary.summary, brief_summary.key_points, title=brief_summary.title
            )
        }
    )

    built = to_eval_row(
        item=plan().items[0],
        article=source,
        summary=brief_summary,
        full_text=copied,
        hhem=0.94,
        hhem_full=0.93,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="v",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert built.band is ConfidenceBand.HIGH
    assert built.verbatim_run > 0.5
    assert built.truncation_flagged


def test_the_row_scores_the_article_and_not_only_the_summary() -> None:
    """The two densities are the only columns that measure the input.

    Checked with a source the summary does not quote, so a value that came from
    the summary instead would read as zero and fail here.
    """
    sourced = (
        "The Ministry of Energy said the plant will close in March, according to a "
        "statement on Tuesday. Officials familiar with the decision claimed the date "
        "was set in June."
    )
    built = to_eval_row(
        item=plan().items[0],
        article=article(),
        summary=summary(),
        full_text=sourced,
        hhem=0.91,
        hhem_full=0.89,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="v",
        scored_at="2026-08-21T06:18:02Z",
    )
    assert built.evidential_density is not None
    assert built.evidential_density > 0.0
    assert built.speculative_density == 0.0, "measured, and measured as none"


# --- The ledger --------------------------------------------------------------


def test_the_ledger_writes_its_header_once(tmp_path: Path) -> None:
    ledger = tmp_path / "state" / "scores.csv"
    assert writer.append(ledger, [row()]) == 1
    assert writer.append(ledger, [row(item_id="ai-02", output_digest="b" * 64)]) == 1
    with ledger.open(encoding="utf-8") as handle:
        lines = list(csv.reader(handle))
    assert len(lines) == 3
    assert tuple(lines[0]) == writer.columns()


def test_a_re_observation_of_the_same_measurement_writes_no_row(tmp_path: Path) -> None:
    """The doc's promise: an item whose inputs did not change writes no row at all.

    A later day can re-plan an address the published ledger has no record of. The
    summary comes back word for word, the scorer reads it with the same
    instrument, and the second row would only inflate the denominator.
    """
    ledger = tmp_path / "state" / "scores.csv"
    assert writer.append(ledger, [row()]) == 1
    again = row(date="2026-08-22", run_id="2026-08-22-1", item_id="ai-07")
    assert writer.append(ledger, [again]) == 0
    with ledger.open(encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 2


def test_one_batch_cannot_carry_the_same_measurement_twice(tmp_path: Path) -> None:
    """The guard reads the batch as well as the file, or a fresh ledger dodges it."""
    ledger = tmp_path / "state" / "scores.csv"
    assert writer.append(ledger, [row(), row(item_id="ai-09")]) == 1


def test_a_changed_output_is_a_new_measurement(tmp_path: Path) -> None:
    """Identical inputs and different words is the defect the ledger exists to catch."""
    ledger = tmp_path / "state" / "scores.csv"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(output_digest="c" * 64)]) == 1


def test_a_changed_scorer_is_a_new_measurement(tmp_path: Path) -> None:
    """Same words read by a different instrument is a reading worth keeping."""
    ledger = tmp_path / "state" / "scores.csv"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(scorer_version="hhem-2.2-open@cccccccc")]) == 1


def test_writing_nothing_creates_nothing(tmp_path: Path) -> None:
    ledger = tmp_path / "state" / "scores.csv"
    assert writer.append(ledger, []) == 0
    assert not ledger.exists()


def test_the_ledger_columns_match_the_contract() -> None:
    assert writer.columns() == EvalRow.csv_columns()


def test_the_committed_ledger_carries_todays_columns() -> None:
    """The header is written once, and the file is appended to forever.

    A contract that grew a column while the committed header did not would put
    more cells on tomorrow's row than the header names, and the dashboard reads
    cells by position.
    """
    ledger = REPO_ROOT / writer.LEDGER_RELPATH
    if not ledger.exists():
        pytest.skip("no ledger committed yet")
    assert writer.read_header(ledger) == writer.columns()


def test_appending_under_a_stale_header_fails_loudly(tmp_path: Path) -> None:
    """Silent corruption is the alternative, and it is unrecoverable once shipped."""
    ledger = tmp_path / "state" / "scores.csv"
    writer.append(ledger, [row()])
    kept = ledger.read_text(encoding="utf-8").split("\n")
    kept[0] = ",".join(writer.columns()[:-1])
    ledger.write_text("\n".join(kept), encoding="utf-8")
    with pytest.raises(ValueError, match="Migrate the ledger"):
        writer.append(ledger, [row(item_id="ai-02")])


# --- Chunking ----------------------------------------------------------------


def test_a_short_premise_is_one_chunk() -> None:
    assert chunks("a b c", size=10) == ["a b c"]


def test_a_long_premise_is_windowed_with_overlap() -> None:
    text = " ".join(str(n) for n in range(1000))
    windows = chunks(text, size=300, overlap=50)
    assert len(windows) > 1
    assert windows[0].split()[-1] in windows[1].split()[:60], "windows overlap"


def test_the_best_chunk_wins_not_the_average() -> None:
    """A mean would drive the score down as the article lengthens and invert the flag."""
    scores = iter([0.1, 0.95, 0.2, 0.15])

    class Recorded:
        def score(self, premise: str, hypothesis: str) -> float:
            del premise, hypothesis
            return next(scores)

    text = " ".join(str(n) for n in range(3000))
    assert score_over_chunks(Recorded(), text, "claim") == pytest.approx(0.95)


def test_an_empty_premise_scores_zero_rather_than_raising() -> None:
    class Never:
        def score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
            raise AssertionError("must not be called")

    assert score_over_chunks(Never(), "", "claim") == 0.0


# --- Assembly ----------------------------------------------------------------


def digest_item(run_n: int = 1):  # type: ignore[no-untyped-def]
    return assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.ANNOUNCEMENT,
        run_n=run_n,
    )


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
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")

    cli.stage_work(
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
    fast_settings = config.Settings(
        app=settings.app.model_copy(
            update={
                "models": settings.app.models.model_copy(
                    update={
                        "inference": settings.app.models.inference.model_copy(
                            update={"request_timeout_minutes": 0.01}
                        )
                    }
                )
            }
        ),
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")

    with HangingLoopbackEndpoint() as server:
        cli.stage_work(
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


# --- The stamp ledger ---------------------------------------------------------


def isolate_ledgers(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Point every output root and every committed ledger at the test's own tree."""
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(cli, "LEDGER", tmp_path / "state" / "scores.csv")
    monkeypatch.setattr(cli, "FINGERPRINTS", tmp_path / "state" / "fingerprints.csv")


def work_then_assemble(run_plan: RunPlan, settings: config.Settings) -> None:
    """One whole run over captured pages, with no model and no network (Rule #7).

    The summaries fail, which is the point: the stamp describes the pipeline
    rather than the words, so it has to reach the ledger on a day the model was
    unreachable too.
    """
    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")


def score_one_item(items_dir: Path, run_plan: RunPlan) -> str:
    """Stand in for the scorer, which needs weights this suite does not download.

    The stamp is the one the work stage has just observed, so the summary and
    the eval payload carry exactly what a scored run would have put on them.
    Returns that stamp.
    """
    stamp_path = next(iter(sorted(items_dir.glob("*.fingerprint.json"))))
    stamp = FingerprintRow.from_json(read_text(stamp_path)).pipeline_fingerprint
    item = run_plan.items[0]
    scored = summary().model_copy(
        update={"item_id": item.item_id, "url_key": item.url_key, "pipeline_fingerprint": stamp}
    )
    (items_dir / f"{item.item_id}.summary.json").write_text(scored.to_json(), encoding="utf-8")
    evaluated = row(url_key=item.url_key, pipeline_fingerprint=stamp)
    (items_dir / f"{item.item_id}.eval.json").write_text(evaluated.to_json(), encoding="utf-8")
    return stamp


def test_a_run_records_its_stamp_in_the_committed_ledger_exactly_once(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The oracle: every stamp in the committed scores expands to one ledger row."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"

    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    stamp = score_one_item(items_dir, run_plan)
    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    committed = tmp_path / "state" / "fingerprints.csv"
    expansions = read_ledger(committed)
    with (tmp_path / "state" / "scores.csv").open(encoding="utf-8", newline="") as handle:
        scored = {record["pipeline_fingerprint"] for record in csv.DictReader(handle)}

    assert scored == {stamp}
    assert set(expansions) == {stamp}
    assert expansions[stamp].first_seen_run == run_plan.run_id
    assert ledger.read_header(committed) == FingerprintRow.csv_columns()


def test_a_second_run_with_the_same_inputs_appends_no_stamp(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The ledger records what a stamp meant, never how often the job ran."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    work_then_assemble(run_plan, settings)
    committed = tmp_path / "state" / "fingerprints.csv"
    after_one_run = committed.read_bytes()

    work_then_assemble(run_plan, settings)

    assert committed.read_bytes() == after_one_run
    assert len(read_ledger(committed)) == 1


def test_the_stamp_records_the_run_and_never_a_placeholder(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The three fields this row replaced were two literals and a model slug."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    work_then_assemble(run_plan, settings)

    stamped = next(iter(read_ledger(tmp_path / "state" / "fingerprints.csv").values()))

    assert stamped.inputs.runtime_build != "llama-server-local"
    assert stamped.inputs.runner_class != "local"
    assert stamped.inputs.chat_template_sha256 != text_digest(settings.app.models.summarize.id)
    assert stamped.host_cpu.strip()
    assert stamped.first_seen_run == run_plan.run_id


class SteppingClock:
    """A monotonic clock that advances a fixed number of seconds on every read.

    The route stage is bounded by wall-clock, and a bound that can only be
    proved by waiting for it is a bound nobody tests. This spends the budget in
    zero real seconds and makes which items survive it deterministic.
    """

    def __init__(self, step_seconds: float) -> None:
        self._step = step_seconds
        self._now = 0.0

    def __call__(self) -> float:
        now = self._now
        self._now += self._step
        return now


def stage_route_payloads(run_plan: RunPlan, items_dir: Path, *, text: str) -> None:
    """One article and one OK summary per planned item, sharing one body."""
    items_dir.mkdir(parents=True, exist_ok=True)
    for item in run_plan.items:
        base_article = article().model_copy(
            update={
                "item_id": item.item_id,
                "url_key": item.url_key,
                "canonical_url": item.canonical_url,
                "source_url": item.canonical_url,
                "vertical": item.vertical,
                "rank_score": item.rank_score,
                "text": text,
            }
        )
        base_summary = summary().model_copy(
            update={"item_id": item.item_id, "url_key": item.url_key}
        )
        (items_dir / f"{item.item_id}.article.json").write_text(
            base_article.to_json(), encoding="utf-8"
        )
        (items_dir / f"{item.item_id}.summary.json").write_text(
            base_summary.to_json(), encoding="utf-8"
        )


# No quantity in here survives `numeric_facts`, so no enabled kind is reachable
# and the router decides every item without a model. That is what keeps this an
# offline test of the bound rather than a test of the model (Rule #7).
FACT_FREE_TEXT = (
    "The laboratory said the work continues and gave no figures. A spokesperson "
    "declined to describe the schedule, and no comparison against the previous "
    "release was offered."
)


def test_the_route_stage_stops_at_its_budget_instead_of_being_killed(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The defect this replaces: the job was cancelled at 60 minutes, a cancelled
    job skips its upload step, and the whole hour's decisions were thrown away.
    """
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_route_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)
    settings = config.load(CONFIG_DIR)
    one_minute = config.Settings(
        app=settings.app.model_copy(
            update={"run": settings.app.run.model_copy(update={"route_budget_minutes": 1})}
        ),
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )

    cli.stage_route(run_plan, settings=one_minute, clock=SteppingClock(10.0))

    routed = sorted(path.name.split(".")[0] for path in items_dir.glob("*.route.json"))
    assert routed == ["ai-01", "ai-02"], "the budget stopped the stage part-way, by rank"
    decision = Route.from_json(read_text(items_dir / "ai-01.route.json"))
    assert decision.route_ms == 10_000
    assert decision.asked_the_model is False


def test_a_stage_inside_its_budget_routes_every_item(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_route_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    cli.stage_route(run_plan, settings=config.load(CONFIG_DIR), clock=SteppingClock(0.0))

    routed = sorted(path.name.split(".")[0] for path in items_dir.glob("*.route.json"))
    assert routed == [item.item_id for item in run_plan.items]


def test_the_router_visits_the_best_story_first(tmp_path: Path) -> None:
    """Plan order is vertical-major, so a suffix cut would cost whole verticals."""
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_route_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    ordered = cli.routable_items(run_plan, items_dir, published=frozenset())

    assert [entry.item.item_id for entry in ordered] == ["ai-01", "ai-02", "ai-03", "ai-04", "ai-05"]
    assert [entry.item.rank_score for entry in ordered] == sorted(
        (item.rank_score for item in run_plan.items), reverse=True
    )


def test_an_item_the_day_already_published_is_never_routed_again(tmp_path: Path) -> None:
    """`build_day` keeps the published copy and discards the new one, so deciding
    it again is 20 to 40 measured seconds spent on an answer nobody can read.
    """
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_route_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    ordered = cli.routable_items(run_plan, items_dir, published=frozenset({"ai-01", "ai-03"}))

    assert [entry.item.item_id for entry in ordered] == ["ai-02", "ai-04", "ai-05"]


def test_an_item_without_a_usable_summary_is_never_routable(tmp_path: Path) -> None:
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_route_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)
    failed = Summary.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "summary" / "failed.json")
    ).model_copy(update={"item_id": "ai-01", "url_key": run_plan.items[0].url_key})
    (items_dir / "ai-01.summary.json").write_text(failed.to_json(), encoding="utf-8")

    ordered = cli.routable_items(run_plan, items_dir, published=frozenset())

    assert failed.status is not SummaryStatus.OK
    assert "ai-01" not in [entry.item.item_id for entry in ordered]


def test_a_retired_feed_still_labels_the_items_it_published() -> None:
    """Splitting the feed lists must not cost an older item its name or its kind.

    A published item carries a `source_id` forever, and a feed can retire
    between the plan and the assemble of the same day - four times more often
    once the schedule moves to every six hours. Both label maps read the union,
    so the maps that would otherwise fall back to the raw slug and to
    `reporting` never get the chance.

    The fallback is the failure: publishing an announcement as reporting is the
    one thing `kind` was added to prevent.
    """
    sources = config.load(CONFIG_DIR).sources.model_copy(
        update={
            "feeds": [],
            "retired": [
                FeedDef(
                    id="defunct-daily",
                    vertical="ai",
                    title="Defunct Daily",
                    url="https://defunct.example.com/rss",
                    tier=SourceTier.INSTITUTION,
                    kind=SourceKind.ANNOUNCEMENT,
                    status=LifecycleStatus.RETIRED,
                    retired_on="2026-07-04",
                    weight=0.0,
                )
            ],
        }
    )
    assert assemble.source_names(sources)["defunct-daily"] == "Defunct Daily"
    assert assemble.source_kinds(sources)["defunct-daily"] is SourceKind.ANNOUNCEMENT


def test_abstract_items_publish_a_sentence_not_a_badge() -> None:
    item = assemble.to_digest_item(
        article=article().model_copy(update={"source_form": SourceForm.ABSTRACT}),
        summary=summary(),
        band=row().band,
        source_name="NBER",
        source_kind=SourceKind.RESEARCH,
        run_n=1,
    )

    assert item.source_form is SourceForm.ABSTRACT
    assert (
        item.reader_note
        == "This is a summary of the paper's abstract. The full paper is a PDF."
    )


def test_truncated_items_publish_the_partial_read_sentence() -> None:
    item = assemble.to_digest_item(
        article=article().model_copy(update={"truncated": True, "truncated_at_tokens": 2500}),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.reader_note == "We could only read the first part of this page."


def test_a_day_publishes_even_when_items_failed() -> None:
    """A run that publishes nothing on a bad day is a run whose bad days are invisible."""
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    assert day.partial
    assert day.items_failed > 0
    assert len(day.items) == 1


def test_item_payloads_include_an_article_without_a_summary(tmp_path: Path) -> None:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / "ai-01.article.json").write_text(article().to_json(), encoding="utf-8")

    payloads = list(cli._item_payloads(plan(), items_dir))

    assert [payload.planned.item_id for payload in payloads] == [
        item.item_id for item in plan().items
    ]
    assert payloads[0].article == article()
    assert payloads[0].summary is None


def test_assemble_writes_one_item_health_row_per_planned_item(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(cli, "LEDGER", tmp_path / "state" / "scores.csv")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    items_dir.mkdir(parents=True)
    (items_dir / f"{run_plan.items[0].item_id}.article.json").write_text(
        article().to_json(), encoding="utf-8"
    )
    (items_dir / f"{run_plan.items[0].item_id}.summary.json").write_text(
        summary()
        .model_copy(update={"fetch_ms": 111, "extract_ms": 22, "summarize_ms": 333})
        .to_json(),
        encoding="utf-8",
    )

    day = cli.stage_assemble(
        run_plan,
        settings=config.load(CONFIG_DIR),
        commit_sha="a" * 40,
        runner="fixture",
    )

    health_path = ledger.item_health_path(tmp_path / "state", run_plan.date)
    with health_path.open(encoding="utf-8", newline="") as handle:
        rows = [ItemHealthRow.from_csv_row(row) for row in csv.DictReader(handle)]
    failed = sum(1 for row in rows if row.outcome is ItemOutcome.FAILED)
    ok = sum(1 for row in rows if row.outcome is ItemOutcome.OK)
    manifest = RunManifest.from_json(
        read_text(tmp_path / "public" / "digest" / "2026" / "08" / "21" / "run.json")
    )

    with health_path.open(encoding="utf-8", newline="") as handle:
        assert tuple(csv.DictReader(handle).fieldnames or ()) == ItemHealthRow.csv_columns()
    assert len(rows) == len(run_plan.items)
    assert ok > 0
    assert failed > 0
    assert rows[0].fetch_ms == 111
    assert rows[0].extract_ms == 22
    assert rows[0].summarize_ms == 333
    assert {row.code for row in rows if row.outcome is ItemOutcome.FAILED} == {
        FailureCode.NOT_ATTEMPTED
    }
    assert day.items_planned == ok + failed == len(run_plan.items)
    assert manifest.runs[-1].items_planned == ok + failed
    assert manifest.runs[-1].items_failed == failed


def test_a_later_run_appends_and_never_reorders() -> None:
    settings = config.load(CONFIG_DIR)
    first = assemble.build_day(
        plan=plan(),
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=plan(),
        items=[digest_item(run_n=1)],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )
    assert [item.item_id for item in second.items] == [item.item_id for item in first.items]
    assert second.runs[-1].items_added == 0, "an item already published is not published twice"


def test_a_later_run_cannot_rewrite_the_words_a_reader_already_read() -> None:
    """The gate that makes `updated_at` and `updated_by_run` reserved rather than live.

    An item the day already holds is dropped whole, so a second run carrying
    different words for the same address changes nothing a reader can see. If
    this ever stops holding, docs/architecture/publishing/layout.md is wrong and
    has to be corrected in the same commit.
    """
    settings = config.load(CONFIG_DIR)
    original = digest_item(run_n=1)
    first = assemble.build_day(
        plan=plan(),
        items=[original],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    rewritten = original.model_copy(
        update={"summary": "Different words for the same address.", "key_points": ["Rewritten."]}
    )
    second = assemble.build_day(
        plan=plan(),
        items=[rewritten],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    kept = second.items[0]
    assert kept.summary == original.summary
    assert kept.key_points == original.key_points
    assert kept.introduced_by_run == 1
    assert kept.updated_at is None
    assert kept.updated_by_run is None


def test_the_run_that_wrote_an_item_resolves_to_a_recorded_run() -> None:
    """The join to the manifest that names the model lands on a run the day recorded."""
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    recorded = {run.n for run in day.runs}

    assert day.items
    for item in day.items:
        assert assemble.run_that_wrote(item) in recorded
        assert assemble.run_that_wrote(item) == item.introduced_by_run

    revised = day.items[0].model_copy(
        update={"updated_at": "2026-08-21T18:00:00Z", "updated_by_run": 2}
    )

    assert assemble.run_that_wrote(revised) == 2, "a revision is joined to the run that revised it"


def test_the_published_path_carries_no_digest() -> None:
    target = assemble.day_dir(Path("frontend/public/digest"), "2026-08-21")
    assert target.as_posix().endswith("digest/2026/08/21")


def test_a_write_is_atomic(tmp_path: Path) -> None:
    """A file either exists complete or does not exist. There is no half-written item."""
    target = tmp_path / "deep" / "digest.json"
    assemble.write_atomic(target, '{"a": 1}\n')
    assert target.read_bytes() == b'{"a": 1}\n'


def test_the_manifest_records_what_ran_against_what() -> None:
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    manifest = assemble.build_manifest(
        plan=plan(),
        day=day,
        previous=None,
        summaries=[summary()],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.runs[-1].run_id == "2026-08-21-1"
    assert manifest.runs[-1].config_digests
    assert manifest.runs[-1].pipeline_fingerprints


def test_the_manifest_records_what_the_router_cost() -> None:
    """The route job runs against a 60-minute bound and nothing recorded its cost.

    The stage total and the item count are committed together, because either
    one alone answers no question about the budget (Rule #10).
    """
    settings = config.load(CONFIG_DIR)
    routed = Route.from_json(read_text(CONTRACT_FIXTURES_DIR / "route" / "chart-rendered.json"))
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    def manifest_for(routes: list[Route]) -> RunManifest:
        return assemble.build_manifest(
            plan=plan(),
            day=day,
            previous=None,
            summaries=[summary()],
            models=[],
            commit_sha="a" * 40,
            runner="local",
            started_at="2026-08-21T06:00:00Z",
            completed_at="2026-08-21T07:00:00Z",
            config_digests=settings.digests,
            site_bytes=1024,
            site_files=2,
            routes=routes,
        )

    timed = manifest_for(
        [
            routed.model_copy(update={"route_ms": 4000}),
            routed.model_copy(update={"route_ms": 11000}),
        ]
    )
    assert timed.runs[-1].items_routed == 2
    assert timed.runs[-1].route_ms == 15000

    # A router that never started is not a router that took no time.
    absent = manifest_for([])
    assert absent.runs[-1].items_routed == 0
    assert absent.runs[-1].route_ms is None

    # Neither is a payload written before the clock existed.
    unclocked = manifest_for([routed.model_copy(update={"route_ms": None})])
    assert unclocked.runs[-1].items_routed == 1
    assert unclocked.runs[-1].route_ms is None

    # The gate changes every denominator: the same charts sit over a smaller
    # routed set. Counting the skips keeps a chart rate from climbing on its own.
    gated = manifest_for(
        [
            routed.model_copy(update={"route_ms": 4000}),
            routed.model_copy(update={"route_ms": 1, "asked_the_model": False}),
            routed.model_copy(update={"route_ms": 1, "asked_the_model": False}),
        ]
    )
    assert gated.runs[-1].items_routed == 3
    assert gated.runs[-1].items_prefiltered == 2

    # A payload written before the gate existed was always asked.
    assert timed.runs[-1].items_prefiltered == 0


def test_a_later_manifest_counts_verticals_for_its_own_run(tmp_path: Path) -> None:
    settings = config.load(CONFIG_DIR)
    base_plan = plan()
    first_item = base_plan.items[0]
    second_item = base_plan.items[1]
    first_plan = base_plan.model_copy(
        update={
            "items": [first_item],
            "verticals": [base_plan.verticals[0].model_copy(update={"planned": 1})],
        }
    )
    second_plan = base_plan.model_copy(
        update={
            "items": [second_item],
            "run_id": f"{base_plan.date}-2",
            "verticals": [base_plan.verticals[0].model_copy(update={"planned": 1})],
        }
    )
    first_summary = summary().model_copy(
        update={"item_id": first_item.item_id, "url_key": first_item.url_key}
    )
    second_summary = summary().model_copy(
        update={"item_id": second_item.item_id, "url_key": second_item.url_key}
    )
    first_day = assemble.build_day(
        plan=first_plan,
        items=[digest_item(run_n=1).model_copy(update={"item_id": first_item.item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    first_manifest = assemble.build_manifest(
        plan=first_plan,
        day=first_day,
        previous=None,
        summaries=[first_summary],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )
    second_day = assemble.build_day(
        plan=second_plan,
        items=[digest_item(run_n=2).model_copy(update={"item_id": second_item.item_id})],
        previous=first_day,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )
    second_manifest = assemble.build_manifest(
        plan=second_plan,
        day=second_day,
        previous=first_manifest,
        summaries=[second_summary],
        models=[],
        commit_sha="b" * 40,
        runner="local",
        started_at="2026-08-21T12:00:00Z",
        completed_at="2026-08-21T13:00:00Z",
        config_digests=settings.digests,
        site_bytes=2048,
        site_files=3,
    )

    assert len(second_day.items) == 2
    assert second_manifest.runs[-1].verticals[0].planned == 1
    assert second_manifest.runs[-1].verticals[0].published == 1

    old_payload = second_manifest.model_dump(mode="json")
    old_payload["version"] = "2026-08-21T02:00"
    old_payload["runs"][1]["verticals"][0]["published"] = 2
    old_path = tmp_path / "run.json"
    old_path.write_text(json.dumps(old_payload), encoding="utf-8")

    migrated = cli._load_manifest(old_path, day=second_day)

    assert migrated is not None
    assert migrated.version == RunManifest.schema_version()
    assert migrated.runs[-1].verticals[0].published == 1


def test_the_committed_day_fixture_still_loads() -> None:
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert day.items
