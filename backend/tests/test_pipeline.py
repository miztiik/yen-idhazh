"""Integration-tier tests for the stages that compose the run.

These drive real payloads through config loading, scoring, ledger writing and
assembly, with the faithfulness model standing in as a recorded number - the
model is not what is under test here, the composition is (CLAUDE.md section 13).

No mocks and no network. The recorded score is a float, not a stub object.
"""

from __future__ import annotations

import csv
import socket
import threading
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh import assemble, cli, config
from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.sources import FeedDef
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier
from idhazh.evals import writer
from idhazh.evals.hhem import chunks, score_over_chunks
from idhazh.evals.score import band, to_eval_row
from idhazh.fetch import FetchResult

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
    assert writer.append(ledger, [row(item_id="ai-02")]) == 1
    with ledger.open(encoding="utf-8") as handle:
        lines = list(csv.reader(handle))
    assert len(lines) == 3
    assert tuple(lines[0]) == writer.columns()


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

    assert server.accepted == len(run_plan.items)
    assert len(summaries) == len(run_plan.items)
    assert {summary.status for summary in summaries} == {SummaryStatus.FAILED}
    assert {summary.failure_code for summary in summaries} == {FailureCode.MODEL_UNREACHABLE}


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


def test_the_committed_day_fixture_still_loads() -> None:
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert day.items
