"""Integration-tier tests for the stages that compose the run.

These drive real payloads through config loading, scoring, ledger writing and
assembly, with the faithfulness model standing in as a recorded number - the
model is not what is under test here, the composition is (CLAUDE.md section 13).

No mocks and no network. The recorded score is a float, not a stub object.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import inspect
import itertools
import json
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    REPO_ROOT,
    RecordedEndpoint,
    read_text,
)
from pydantic import ValidationError
from pytest import MonkeyPatch

from idhazh import assemble, cli, config, extract, ledger, rank, summarize, telemetry
from idhazh.classify import calls
from idhazh.contracts.app_config import EvaluationConfig, ExtractConfig, ObservabilityConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import ChangelogEntry, StalePayloadError
from idhazh.contracts.call_cost import CallKind
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_view import DigestView
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.fingerprint import FingerprintRow
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome
from idhazh.contracts.run_manifest import RunManifest, RunRecord
from idhazh.contracts.run_plan import RunPlan, TimeSource, VerticalPlan
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.sources import FeedDef, SourceForm
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision
from idhazh.evals import archive as score_archive
from idhazh.evals import metrics, sampling, writer
from idhazh.evals.hhem import chunks, dual_score, score_over_chunks
from idhazh.evals.score import band, to_eval_row, verdict
from idhazh.fetch import FetchResult
from idhazh.fingerprint import read_ledger, text_digest
from idhazh.ledger import STATE_DIRNAME
from idhazh.llm.server import parse_completion

pytestmark = pytest.mark.slow

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
        premise=FULL_TEXT,
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
        cli._FetchedWorkItem(items[0], sized(2000), "", 0, 0, 0.0, 0),
        cli._FetchedWorkItem(items[1], sized(10), "", 0, 0, 0.0, 1),
        cli._FetchedWorkItem(items[2], sized(800), "", 0, 0, 0.0, 2),
        cli._FetchedWorkItem(items[3], sized(100), "", 0, 0, 0.0, 3),
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


def test_a_wide_gap_does_not_flag_an_article_nobody_cut() -> None:
    """The test that would have caught the rule this column used to carry.

    A 0.33 gap is three times the ceiling the old rule compared against, and the
    fixture article was never cut. The flag reads the payload now, so the wide
    gap has to leave it alone while both faithfulness columns keep the gap.
    """
    built = to_eval_row(
        item=plan().items[0],
        article=article(),
        summary=summary(),
        full_text=FULL_TEXT,
        premise=FULL_TEXT,
        hhem=0.94,
        hhem_full=0.61,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="v",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert not article().truncated
    assert built.hhem_delta == pytest.approx(0.33)
    assert not built.truncation_flagged


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
        premise=sourced,
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


def test_the_row_digests_the_text_the_scorer_was_given() -> None:
    """`output_digest` names the words that came out; this names the words that went in.

    The digest is the shared `text_digest` and not a second convention: sha256
    over the UTF-8 bytes, the full 64 hex characters, exactly as
    `CorpusItem.seen_text_sha256` already spells the same quantity.
    """
    built = row()

    assert built.source_digest == text_digest(FULL_TEXT)
    assert built.source_digest != built.output_digest, "the premise is not the summary"


def test_the_two_source_word_counts_are_one_counter_before_and_after_the_cap() -> None:
    """Built by the real extractor, so the pair is a genuine cut and not two counters.

    `source_seen_word_count` larger than `source_word_count` is impossible when
    one string is a cut of the other. It happened on 590 of the 2,232 rows
    written before this, which is what proved the pair was measuring
    `len(_WORD.findall(t))` against `len(t.split())` on one post-cap string.
    """
    body = " ".join(f"word{n}" for n in range(4000))
    cut = extract.to_article(
        plan().items[0],
        FetchResult(
            FetchOutcome.OK,
            status=200,
            body=f"<html><body><article><p>{body}</p></article></body></html>".encode(),
        ),
        config=ExtractConfig(truncation_cap_tokens=256),
        fetched_at="2026-08-21T06:00:00Z",
    )
    assert cut.truncated, "the fixture must actually be cut, or this proves nothing"

    built = to_eval_row(
        item=plan().items[0],
        article=cut,
        summary=summary(),
        full_text=FULL_TEXT,
        premise=FULL_TEXT,
        hhem=0.91,
        hhem_full=0.89,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="v",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert built.source_word_count == cut.source_word_count == 4000
    assert built.source_seen_word_count == cut.word_count
    assert built.source_seen_word_count < built.source_word_count
    assert built.source_word_count != metrics.word_count(FULL_TEXT), (
        "the column must come off the article, not off whatever full_text was passed"
    )


def test_two_premises_digest_apart_and_the_same_premise_digests_the_same() -> None:
    """A digest that did not separate, or did not repeat, would check nothing.

    The two texts differ by one sentence, which is what truncation moving by a
    paragraph looks like - not by a whole article.
    """

    def scored(premise: str) -> EvalRow:
        return to_eval_row(
            item=plan().items[0],
            article=article(),
            summary=summary(),
            full_text=FULL_TEXT,
            premise=premise,
            hhem=0.91,
            hhem_full=0.89,
            config=EvaluationConfig(),
            date="2026-08-21",
            run_id="2026-08-21-1",
            scorer_version="v",
            scored_at="2026-08-21T06:18:02Z",
        )

    shorter = FULL_TEXT.rsplit(". ", 1)[0] + "."
    assert shorter != FULL_TEXT

    assert scored(FULL_TEXT).source_digest == scored(FULL_TEXT).source_digest
    assert scored(FULL_TEXT).source_digest != scored(shorter).source_digest


def test_the_work_stage_digests_the_same_text_it_scores() -> None:
    """The whole value of the column is that these two are one variable.

    A digest of anything else - the fetched page, the untruncated article, the
    summary - would let a labeller and the scorer disagree about text and read
    as the scorer being wrong. The suite cannot run the real scorer, whose
    weights it may not download (Guardrail #7), so what is checked is the wiring:
    `stage_work` passes one name to `dual_score(seen_text=...)` and to
    `to_eval_row(premise=...)`.
    """
    tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py"))
    stage = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "stage_work"
    )

    def argument(call_name: str, keyword: str) -> str:
        for node in ast.walk(stage):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            spelled = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            if spelled != call_name:
                continue
            for given in node.keywords:
                if given.arg == keyword:
                    assert isinstance(given.value, ast.Name), (
                        f"{call_name}({keyword}=...) is no longer a plain name"
                    )
                    return given.value.id
        raise AssertionError(f"stage_work no longer calls {call_name}({keyword}=...)")

    assert argument("dual_score", "seen_text") == argument("to_eval_row", "premise")


def test_the_work_stage_scores_against_a_different_text_than_it_showed_the_model() -> None:
    """`hhem_full` only means anything when it reads something `hhem` did not.

    Until 2026-08-27 `stage_work` passed one variable to both, so `hhem_delta`
    was exactly 0.0 on all 2,232 committed rows and the detector `dual_score`
    exists to be had never once carried information. Checked as wiring for the
    same reason as the digest test above: the suite may not download the
    scorer's weights (Guardrail #7).
    """
    tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py"))
    stage = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "stage_work"
    )

    def argument(call_name: str, keyword: str) -> str:
        for node in ast.walk(stage):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            spelled = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")
            if spelled != call_name:
                continue
            for given in node.keywords:
                if given.arg == keyword:
                    assert isinstance(given.value, ast.Name), (
                        f"{call_name}({keyword}=...) is no longer a plain name"
                    )
                    return given.value.id
        raise AssertionError(f"stage_work no longer calls {call_name}({keyword}=...)")

    assert argument("dual_score", "seen_text") != argument("dual_score", "full_text")
    assert argument("dual_score", "full_text") == argument("to_eval_row", "full_text")


# --- The ledger --------------------------------------------------------------


def test_the_ledger_writes_its_header_once(tmp_path: Path) -> None:
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    assert writer.append(state, [row(item_id="ai-02", output_digest="b" * 64)]) == 1
    shards = writer.ledger_shards(state)
    assert len(shards) == 1, "both rows are the same month, so they share a shard"
    with shards[0].open(encoding="utf-8") as handle:
        lines = list(csv.reader(handle))
    assert len(lines) == 3
    assert tuple(lines[0]) == writer.columns()


def test_two_months_of_rows_land_in_two_shards(tmp_path: Path) -> None:
    """A run either side of a month boundary writes both, and neither is wrong.

    The row's own `date` files it, not the day the writer happened to run, so a
    replay of an older day cannot put September's rows in August's shard.
    """
    state = tmp_path / "state"
    august = row()
    september = row(date="2026-09-01", run_id="2026-09-01-1", url_key="e" * 64)

    assert writer.append(state, [september, august]) == 2

    assert [shard.stem for shard in writer.ledger_shards(state)] == ["2026-08", "2026-09"]
    assert [record["date"] for record in writer.records(state)] == [august.date, september.date]


def test_a_re_observation_of_the_same_measurement_writes_no_row(tmp_path: Path) -> None:
    """The doc's promise: an item whose inputs did not change writes no row at all.

    A later day can re-plan an address the published ledger has no record of. The
    summary comes back word for word, the scorer reads it with the same
    instrument, and the second row would only inflate the denominator.
    """
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    again = row(date="2026-08-22", run_id="2026-08-22-1", item_id="ai-07")
    assert writer.append(state, [again]) == 0
    with writer.ledger_shards(state)[0].open(encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 2


def test_a_re_observation_in_a_later_month_still_writes_no_row(tmp_path: Path) -> None:
    """Dedupe spans the shards, or sharding would quietly reopen the door.

    The promise is that a count over the ledger is a count of items. A dedupe
    scoped to the shard being written would let August's measurement come back
    in September as a second row about the same thing.
    """
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1

    later = row(date="2026-09-14", run_id="2026-09-14-1", item_id="ai-07")

    assert writer.append(state, [later]) == 0
    assert [shard.stem for shard in writer.ledger_shards(state)] == ["2026-08"]


def test_one_batch_cannot_carry_the_same_measurement_twice(tmp_path: Path) -> None:
    """The guard reads the batch as well as the file, or a fresh ledger dodges it."""
    ledger = tmp_path / "state"
    assert writer.append(ledger, [row(), row(item_id="ai-09")]) == 1


def test_a_measurement_whose_month_was_archived_is_still_not_new(tmp_path: Path) -> None:
    """The dedupe spans the archives too, or deleting a shard reopens the door.

    Sharding was the first way this could break and the fix was to read every
    shard. Archiving is the second: a month past
    `observability.scores_full_grain_months` has no rows left to read at all, so
    a dedupe over the rows alone would call every measurement in it new on the
    day it was deleted - and a count over the ledger would stop being a count of
    items, which is the one thing this ledger promises it is not.
    """
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    shard = writer.ledger_shards(state)[0]
    summary = score_archive.summarise(shard, observation_key=writer.OBSERVATION_KEY)
    score_archive.write(score_archive.archive_path(state, shard.stem), summary)
    shard.unlink()

    assert not writer.ledger_shards(state)
    assert writer.append(state, [row(date="2026-09-14", run_id="2026-09-14-1")]) == 0
    assert not writer.ledger_shards(state), "the archived measurement was written again"


def test_a_changed_output_is_a_new_measurement(tmp_path: Path) -> None:
    """Identical inputs and different words is the defect the ledger exists to catch."""
    ledger = tmp_path / "state"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(output_digest="c" * 64)]) == 1


def test_a_changed_scorer_is_a_new_measurement(tmp_path: Path) -> None:
    """Same words read by a different instrument is a reading worth keeping."""
    ledger = tmp_path / "state"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(scorer_version="hhem-2.2-open@cccccccc")]) == 1


def test_writing_nothing_creates_nothing(tmp_path: Path) -> None:
    ledger = tmp_path / "state"
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
    shards = writer.ledger_shards(REPO_ROOT / STATE_DIRNAME)
    if not shards:
        pytest.skip("no ledger committed yet")
    for shard in shards:
        assert writer.read_header(shard) == writer.columns(), shard.name


def test_the_committed_ledger_still_takes_a_row_today(tmp_path: Path) -> None:
    """The migration, run against the real file rather than a copy of its shape.

    `require_matching_header` compares the header tuple exactly, so the commit
    that gave the contract a `source_digest` column stopped the committed ledger
    loading until the file was widened by the same column. This appends to a byte
    copy of what is committed, which is the run a release blocker would fail.
    """
    committed = writer.ledger_shards(REPO_ROOT / STATE_DIRNAME)
    if not committed:
        pytest.skip("no ledger committed yet")
    state = tmp_path / "state"
    (state / writer.LEDGER_DIRNAME).mkdir(parents=True)
    for shard in committed:
        (state / writer.LEDGER_DIRNAME / shard.name).write_bytes(shard.read_bytes())
    newest = state / writer.LEDGER_DIRNAME / committed[-1].name
    before = newest.read_text(encoding="utf-8").count("\n")

    assert writer.append(state, [row(url_key="d" * 64, date=f"{committed[-1].stem}-01")]) == 1

    assert writer.read_header(newest) == writer.columns()
    assert newest.read_text(encoding="utf-8").count("\n") == before + 1


def test_a_row_older_than_the_premise_column_records_its_absence(tmp_path: Path) -> None:
    """An empty cell, never a digest computed today.

    A row scored before 2026-08-27 recorded no premise. Filling it in now would
    name text nobody read and would make a labeller's disagreement unreadable -
    which is the one thing the column exists to prevent.

    Driven from a row with the column removed. Walking the committed ledger cost
    a parse per row and asserted the ledger STILL HELD a row older than the
    column, which is a fuse timed to the day the last one ages out of retention.
    The cell-count check it carried belongs to `require_matching_header`, which
    refuses a mismatched append at write time - proved below.
    """
    old = row().model_dump(mode="json")
    old.pop("source_digest")

    migrated = EvalRow.model_validate(old)

    assert migrated.source_digest is None


def test_appending_under_a_stale_header_fails_loudly(tmp_path: Path) -> None:
    """Silent corruption is the alternative, and it is unrecoverable once shipped."""
    state = tmp_path / "state"
    writer.append(state, [row()])
    shard = writer.ledger_shards(state)[0]
    kept = shard.read_text(encoding="utf-8").split("\n")
    kept[0] = ",".join(writer.columns()[:-1])
    shard.write_text("\n".join(kept), encoding="utf-8")
    with pytest.raises(ValueError, match="Migrate the ledger"):
        writer.append(state, [row(item_id="ai-02")])


# --- Chunking ----------------------------------------------------------------


def test_a_short_premise_is_one_chunk() -> None:
    assert chunks("a b c", size=10, overlap=2) == ["a b c"]


def test_a_long_premise_is_windowed_with_overlap() -> None:
    text = " ".join(str(n) for n in range(1000))
    windows = chunks(text, size=300, overlap=50)
    assert len(windows) > 1
    assert windows[0].split()[-1] in windows[1].split()[:60], "windows overlap"


def test_every_window_is_the_full_window_and_the_last_one_ends_on_the_last_word() -> None:
    """The aggregation is a max, so a short window is a rival with less to work with.

    Until 2026-08-28 the walk stepped past the end and the leftover became the
    final window. That window was short on every premise longer than one window
    - as little as one word, and 370 words on average against 900-word rivals -
    so every long article was graded with at least one draw from a partial
    premise. Counting the windows cannot see this: the count is the same either
    way on most lengths. The window LENGTHS are what say it.
    """
    geometry = EvaluationConfig()
    size, overlap = geometry.chunk_words, geometry.chunk_overlap_words

    for length in range(size + 1, 4001):
        words = [str(n) for n in range(length)]
        windows = [window.split() for window in chunks(" ".join(words), size, overlap)]
        short = [len(window) for window in windows if len(window) != size]
        assert not short, f"premise of {length} words produced windows of {short} words"
        assert windows[-1][-1] == words[-1], (
            f"premise of {length} words: the last window stops at "
            f"{windows[-1][-1]} rather than {words[-1]}"
        )


def test_anchoring_the_last_window_drops_a_window_on_a_long_article() -> None:
    """Correctness is the reason; the saved scorer pass arrived with the bigger cap.

    At the cap of 2500 committed until 2026-08-29, an article stopped at 1,923
    words. There anchoring fixes the runt and changes no count - 3 windows
    before, 3 after - so it bought correctness and no time. At 3,846 words, which
    is what the cap of 5000 now allows, the unanchored walk needed 6 windows with
    the last of them 96 words long, and anchoring covers the same text in 5. That
    is 16.7 percent less scorer work, and the cap move is what turned it from a
    number to quote later into a live saving.
    """
    geometry = EvaluationConfig()
    size, overlap = geometry.chunk_words, geometry.chunk_overlap_words

    at_cap = chunks(" ".join(str(n) for n in range(1923)), size, overlap)
    doubled = chunks(" ".join(str(n) for n in range(3846)), size, overlap)

    assert len(at_cap) == 3, "the old cap cost the same three passes it always did"
    assert len(doubled) == 5, "six before anchoring, five after"


def test_the_best_chunk_wins_not_the_average() -> None:
    """A mean would drive the score down as the article lengthens and invert the flag."""
    scores = iter([0.1, 0.95, 0.2, 0.15])

    class Recorded:
        def score(self, premise: str, hypothesis: str) -> float:
            del premise, hypothesis
            return next(scores)

    text = " ".join(str(n) for n in range(3000))
    assert score_over_chunks(
        Recorded(), text, "claim", evaluation=EvaluationConfig()
    ) == pytest.approx(0.95)


def test_an_empty_premise_scores_zero_rather_than_raising() -> None:
    class Never:
        def score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
            raise AssertionError("must not be called")

    assert score_over_chunks(Never(), "", "claim", evaluation=EvaluationConfig()) == 0.0


class _Counting:
    """A scorer that answers deterministically and says how often it was asked."""

    def __init__(self) -> None:
        self.premises: list[str] = []

    def score(self, premise: str, hypothesis: str) -> float:
        del hypothesis
        self.premises.append(premise)
        return 0.5 + 0.1 * len(self.premises)


def test_an_untruncated_article_is_scored_once_and_not_twice() -> None:
    """The scorer is deterministic, so a second pass over one string cannot differ.

    About 97 percent of items are never cut, and one pass over a 900-word chunk
    measured 2.88 to 3.08 s on `ubuntu-latest` (2026-08-26, run `2026-08-26-5`,
    n=5). The pass this skips was roughly 2 s an item, or 21 to 24 minutes of
    runner wall-clock a day at the observed 621 to 731 items.
    """
    scorer = _Counting()
    whole = "The plant will close in March, the ministry said on Tuesday."

    seen, full = dual_score(
        scorer,
        seen_text=whole,
        full_text=whole,
        summary="claim",
        evaluation=EvaluationConfig(),
    )

    assert scorer.premises == [whole], "one identical string, one pass"
    assert seen == full


def test_a_truncated_article_is_scored_against_both_texts() -> None:
    """The short-circuit must not swallow the case the column exists for."""
    scorer = _Counting()
    seen_text = "The plant will close in March."
    whole = f"{seen_text} The ministry named June as the original date."

    seen, full = dual_score(
        scorer,
        seen_text=seen_text,
        full_text=whole,
        summary="claim",
        evaluation=EvaluationConfig(),
    )

    assert scorer.premises == [seen_text, whole], "two different strings, two passes"
    assert seen != full


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
    # `model_copy(update=...)` does not validate, so the update has to name a
    # key the model really has. Aimed one level too high it sets an attribute
    # nothing reads, the request keeps the committed 22.1-minute bound, and this
    # test sits on the hanging endpoint until the job's own timeout kills it.
    summarizer = settings.app.models.summarize
    fast_settings = config.Settings(
        app=settings.app.model_copy(
            update={
                "models": settings.app.models.model_copy(
                    update={
                        "summarize": summarizer.model_copy(
                            update={
                                "inference": summarizer.inference.model_copy(
                                    update={"request_timeout_minutes": 0.01}
                                )
                            }
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
    """Point every output root and every committed ledger at the test's own tree.

    The month index is one of them because `stage_assemble` rebuilds it from
    whatever day directory it was given. Its root is derived from `PUBLIC_ROOT`,
    so patching that covers it. Left unpatched it rebuilt the committed index
    from an empty fixture tree and truncated the served vectors to zero bytes - a
    change `git status` shows and a test never asserts on.
    """
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(cli, "FINGERPRINTS", tmp_path / "state" / "fingerprints.csv")


def work_then_assemble(run_plan: RunPlan, settings: config.Settings) -> None:
    """One whole run over captured pages, with no model and no network (Guardrail #7).

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
    with (tmp_path / "state" / "scores" / "2026-08.csv").open(encoding="utf-8", newline="") as handle:
        scored = {record["pipeline_fingerprint"] for record in csv.DictReader(handle)}

    assert scored == {stamp}
    assert set(expansions) == {stamp}
    assert expansions[stamp].first_seen_run == run_plan.run_id
    assert ledger.read_header(committed) == FingerprintRow.csv_columns()


def test_a_traced_work_shard_commits_a_reconciling_span_rollup(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Row #4: tracing on, a work shard folds its own spans into the committed
    rollup and the item row's residual reconciles against the shard wall clock.

    The model is a closed loopback, so the summaries fail - which is fine, the
    fold is over the spans the shard opened (the item, the tagger, the prompt
    render), not over a scored run. `roll_up_spans` raises if the spans claim more
    time than the shard ran, so a residual on the item row is proof they did not.
    The raw trace lands under state/traces/, the committed path the sink now
    writes in place of the gitignored one.
    """
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    settings = config.load(CONFIG_DIR)
    assert settings.app.observability.tracing_enabled, "the committed config traces by default"

    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )

    shard = ledger.span_rollup_path(cli.STATE_ROOT, run_plan.date[:7])
    rows = [
        SpanRollupRow.from_csv_row(raw)
        for raw in csv.DictReader(shard.read_text(encoding="utf-8").splitlines())
    ]
    by_name = {row.span_name: row for row in rows}
    assert RollupSpan.ITEM in by_name, "the shard opened no item span"
    assert len(by_name) >= 2, "only the item span was folded; a sub-step should have too"
    assert set(by_name) <= set(RollupSpan), "a non-committed span reached the rollup"

    item = by_name[RollupSpan.ITEM]
    assert item.unattributed_ms is not None and item.unattributed_ms >= 0
    for name, row in by_name.items():
        rides_on_item = name is RollupSpan.ITEM
        assert (row.unattributed_ms is not None) is rides_on_item

    traces = list((cli.STATE_ROOT / telemetry.TRACES_DIRNAME).rglob("*.jsonl"))
    assert traces, "no committed trace was written under state/traces/"


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


# --- The window between the day write and the published ledger ----------------


def test_a_crash_before_the_published_ledger_costs_the_replay_nothing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """`stage_assemble` writes `digest.json` and appends the published ledger tens
    of lines later, so a run that dies in that gap leaves a committed day the
    ledger never heard of. The plan-time guard reads that ledger, so the next run
    offers every one of those addresses again - and `build_day`'s `already` set is
    what makes the replay cost nothing.

    That is the reason the two docstrings give since 2026-09-12. The reason they
    used to give was link stability, and it is retired: both render paths re-sort
    the day, so the published order reaches no reader.

    The crash is the on-disk state a crash leaves rather than a patched function:
    the day file stays and the day's ledger file is removed. Driven from the
    committed run-plan fixture and never from the archive (CLAUDE.md section 13).
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"
    state = tmp_path / "state"

    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    score_one_item(items_dir, run_plan)
    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    day_path = assemble.day_dir(cli.PUBLIC_ROOT, run_plan.date) / "digest.json"
    published = DigestDay.from_json(read_text(day_path))
    assert published.items, "run 1 published nothing, so there is no window to test"

    ledger.published_path(state, run_plan.date).unlink()
    window = settings.app.collect.published_window_days
    assert not ledger.load_published(state, today=run_plan.date, within_days=window), (
        "the guard still holds these addresses, so this is not the crash the window leaves"
    )

    cli.stage_assemble(
        run_plan.model_copy(update={"run_id": f"{run_plan.date}-2"}),
        settings=settings,
        commit_sha="a" * 40,
        runner="fixture",
    )

    replayed = DigestDay.from_json(read_text(day_path))
    assert [item.item_id for item in replayed.items] == [item.item_id for item in published.items]
    assert {item.introduced_by_run for item in replayed.items} == {1}
    assert cli.already_published(run_plan.date) == {item.item_id for item in replayed.items}


class SteppingClock:
    """A monotonic clock that advances a fixed number of seconds on every read.

    The visual planner is bounded by wall-clock, and a bound that can only be
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


def stage_visual_payloads(run_plan: RunPlan, items_dir: Path, *, text: str) -> None:
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
# and the planner decides every item without a model. That is what keeps this an
# offline test of the bound rather than a test of the model (Guardrail #7).
FACT_FREE_TEXT = (
    "The laboratory said the work continues and gave no figures. A spokesperson "
    "declined to describe the schedule, and no comparison against the previous "
    "release was offered."
)


def test_the_visual_planner_stops_at_its_budget_instead_of_being_killed(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The defect this replaces: the job was cancelled at 60 minutes, a cancelled
    job skips its upload step, and the whole hour's decisions were thrown away.
    """
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_visual_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)
    settings = config.load(CONFIG_DIR)
    one_minute = config.Settings(
        app=settings.app.model_copy(
            update={"run": settings.app.run.model_copy(update={"visual_planner_budget_minutes": 1})}
        ),
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )

    cli.stage_visual_planner(run_plan, settings=one_minute, clock=SteppingClock(10.0))

    decided = sorted(path.name.split(".")[0] for path in items_dir.glob("*.visual.json"))
    assert decided == ["ai-01", "ai-02"], "the budget stopped the stage part-way, by rank"
    decision = VisualDecision.from_json(read_text(items_dir / "ai-01.visual.json"))
    assert decision.decision_ms == 10_000
    assert decision.asked_the_model is False


def test_a_stage_inside_its_budget_decides_every_item(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_visual_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    cli.stage_visual_planner(run_plan, settings=config.load(CONFIG_DIR), clock=SteppingClock(0.0))

    decided = sorted(path.name.split(".")[0] for path in items_dir.glob("*.visual.json"))
    assert decided == [item.item_id for item in run_plan.items]


def test_the_planner_visits_the_best_story_first(tmp_path: Path) -> None:
    """Plan order is vertical-major, so a suffix cut would cost whole verticals."""
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_visual_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    ordered = cli.plannable_items(run_plan, items_dir, published=frozenset())

    assert [entry.item.item_id for entry in ordered] == ["ai-01", "ai-02", "ai-03", "ai-04", "ai-05"]
    assert [entry.item.rank_score for entry in ordered] == sorted(
        (item.rank_score for item in run_plan.items), reverse=True
    )


def test_an_item_the_day_already_published_is_never_decided_again(tmp_path: Path) -> None:
    """`build_day` keeps the published copy and discards the new one, so deciding
    it again is 20 to 40 measured seconds spent on an answer nobody can read.
    """
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_visual_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)

    ordered = cli.plannable_items(run_plan, items_dir, published=frozenset({"ai-01", "ai-03"}))

    assert [entry.item.item_id for entry in ordered] == ["ai-02", "ai-04", "ai-05"]


def test_an_item_without_a_usable_summary_is_never_plannable(tmp_path: Path) -> None:
    run_plan = plan()
    items_dir = tmp_path / "items"
    stage_visual_payloads(run_plan, items_dir, text=FACT_FREE_TEXT)
    failed = Summary.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "summary" / "failed.json")
    ).model_copy(update={"item_id": "ai-01", "url_key": run_plan.items[0].url_key})
    (items_dir / "ai-01.summary.json").write_text(failed.to_json(), encoding="utf-8")

    ordered = cli.plannable_items(run_plan, items_dir, published=frozenset())

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


def test_the_published_item_carries_the_plan_rows_own_ranking_signal() -> None:
    """Nothing is recomputed at assemble: the four numbers are the plan's own.

    The published item is built from an article and a summary, and neither of
    them knows why the story was chosen. The plan row is the only place that
    fact still exists by this stage.
    """
    planned = plan().items[0].model_copy(update={"time_source": TimeSource.FEED})
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
        planned=planned,
    )

    assert item.carried_by == planned.carried_by == 3
    assert item.watchlist_hit == planned.watchlist_hit
    assert item.on_front_page == planned.on_front_page
    assert item.rank_score == planned.rank_score == 3.4
    assert item.on_front_page, "the fixture's first item did get an aggregator vote"
    assert item.time_source is TimeSource.FEED


def test_an_item_built_without_a_plan_row_publishes_no_signal_at_all() -> None:
    """Absent is unknown. A default here would be a claim nobody measured."""
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.carried_by is None, "1 would claim a count the run never took"
    assert item.watchlist_hit is None
    assert item.on_front_page is None, "false would deny a vote nobody counted"
    assert item.rank_score is None, "0.0 would put the story bottom of its desk"
    assert item.time_source is None


def cut_article(*, read: int, total: int | None, abstract: bool = False) -> Article:
    """One article cut at `read` words out of `total` before the cap."""
    return article().model_copy(
        update={
            "truncated": True,
            "truncated_at_tokens": 2500,
            "word_count": read,
            "source_word_count": total,
            "source_form": SourceForm.ABSTRACT if abstract else SourceForm.ARTICLE,
        }
    )


def test_the_cut_sentence_names_how_much_of_the_page_we_read() -> None:
    """One word cannot cover both ends of the real range, so the note carries a number.

    Both pairs are measured rows of `state/scores.csv` on 2026-08-29, the
    smallest and the largest of the 22 genuinely cut items: 1,923 words of
    1,948 is a 1.3 percent loss, and 1,923 of 8,442 is a 77.2 percent loss.
    Today both print the same sentence, which is the defect.
    """
    barely = assemble.reader_note(cut_article(read=1923, total=1948))
    mostly = assemble.reader_note(cut_article(read=1923, total=8442))

    assert barely == "We could only read the first 99 percent of this page."
    assert mostly == "We could only read the first 23 percent of this page."
    assert barely != mostly


def test_an_abstract_that_was_also_cut_carries_both_facts() -> None:
    """Returning on the first branch is the exact shape of a silent cut.

    Nothing in extract exempts an abstract from the cap: `truncate_to_tokens`
    runs on every body. It has never fired on one - the longest body the single
    abstract feed produced across 28 rows of `state/item-health/2026-08.csv` on
    2026-08-29 was 330 words against a 1,923-word cut point - so this is latent,
    not live. Latent is not a reason to leave it standing.
    """
    note = assemble.reader_note(cut_article(read=1320, total=5280, abstract=True))

    assert note == (
        "This is a summary of the paper's abstract. The full paper is a PDF. "
        "We could only read the first 25 percent of this page."
    )


def test_a_cut_page_of_unknown_length_states_no_scale() -> None:
    """A payload written before `source_word_count` existed cannot name a share.

    142 of the 2,683 rows in `state/scores.csv` carry no pre-cap length on
    2026-08-29. The note degrades to the sentence it already shipped rather
    than inventing a number or dropping the fact.
    """
    assert (
        assemble.reader_note(cut_article(read=1320, total=None))
        == "We could only read the first part of this page."
    )


def test_the_note_never_claims_we_read_the_first_100_percent() -> None:
    """A scale that rounds to all of it says the opposite of what happened."""
    assert (
        assemble.reader_note(cut_article(read=748, total=748))
        == "We could only read the first part of this page."
    )
    assert (
        assemble.reader_note(cut_article(read=1996, total=2000))
        == "We could only read the first part of this page."
    )


def test_an_uncut_article_of_full_length_says_nothing() -> None:
    assert assemble.reader_note(article()) is None


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


def test_an_item_written_before_a_contract_moved_says_so_at_the_stage_that_reads_it(
    tmp_path: Path,
) -> None:
    """The check that would have caught run 33951249328, where it actually bit.

    The visuals job wrote its payloads at 08:23, a field rename merged, and the
    rebuild opened them at 09:03 with the new contract. The stage reported that
    the payloads were invalid. They were not - they were written eight hundred
    seconds before the shape changed under them, and only the stamp can say so.
    """
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    stale = json.loads(article().to_json())
    stale["version"] = "2026-01-01"
    stale["body"] = stale.pop("text")
    (items_dir / "ai-01.article.json").write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(StalePayloadError) as raised:
        list(cli._item_payloads(plan(), items_dir))

    assert "2026-01-01" in str(raised.value)
    assert Article.schema_version() in str(raised.value)


def test_assemble_writes_one_item_health_row_per_planned_item(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
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


def health_rows(state_dir: Path, date: str) -> list[ItemHealthRow]:
    """Every item-health row the committed shard holds, in file order."""
    path = ledger.item_health_path(state_dir, date)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [ItemHealthRow.from_csv_row(record) for record in csv.DictReader(handle)]


def test_a_run_that_dies_before_assemble_keeps_what_its_workers_measured(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle, first half: assemble never runs and the rows are still there.

    Until this stage existed, a shard's verdicts left the runner only inside an
    `items-<shard>` artifact that expires in a day and is skipped entirely when
    the job is cancelled. A run stopped here had measured every item and
    recorded none of it.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"

    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    recorded, _ = cli.stage_record(run_plan, settings=settings)

    rows = health_rows(state, run_plan.date)
    assert recorded == len(rows) == len(run_plan.items)
    assert {row.run_id for row in rows} == {run_plan.run_id}
    assert [row.item_id for row in rows] == [item.item_id for item in run_plan.items]
    assert ledger.read_header(ledger.item_health_path(state, run_plan.date)) == (
        ItemHealthRow.csv_columns()
    )


def test_the_assemble_that_follows_appends_nothing_the_worker_already_recorded(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle, second half: two writers, one row per item per run.

    A repeat is not free. `publish_telemetry` copies every row into the file the
    console reads, and `merge=union` keeps the lines from both sides rather than
    collapsing them - so a second copy is one item counted twice on the
    dashboard, forever, in a ledger that cannot correct a row.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    cli.stage_record(run_plan, settings=settings)
    after_the_worker = health_rows(state, run_plan.date)

    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    rows = health_rows(state, run_plan.date)
    keys = [(row.date, row.run_id, row.item_id) for row in rows]
    assert rows == after_the_worker, "assemble re-wrote rows the worker had already committed"
    assert len(keys) == len(set(keys)) == len(run_plan.items)
    # The dedupe only bites because both writers file under one run id. If the
    # two derivations ever part, every row lands twice.
    assert {row.run_id for row in rows} == {run_plan.run_id}


def test_replaying_a_day_the_worker_already_recorded_appends_no_duplicate(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A run cancelled after its workers is re-run, and the shard files nothing new.

    Nothing published in between, so `_next_run_n` hands the replay the same run
    id - which is exactly what makes its rows the same rows.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    committed = ledger.item_health_path(tmp_path / "state", run_plan.date)
    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    cli.stage_record(run_plan, settings=settings)
    after_one_run = committed.read_bytes()

    replayed, _ = cli.stage_record(run_plan, settings=settings)

    assert replayed == 0
    assert committed.read_bytes() == after_one_run


def test_two_runs_that_start_before_either_publishes_cannot_share_a_run_id(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The defect, and the fix, on the tree that produced it.

    `actions/checkout` pins a job to the commit its run was triggered at, so a
    run that starts while another is still working reads the day exactly as it
    stood before that one published. Counting the runs off it therefore gives
    both of them the same answer - which is what happened on 2026-08-29, when
    runs 33270983446 and 33274853468 both derived `2026-08-29-3` and the ledgers
    keyed on it ended up with six counter rows for four shards.

    Naming the execution is what makes that impossible: GitHub allocates the
    number and nothing a second run can read reproduces it.
    """
    isolate_ledgers(tmp_path, monkeypatch)
    settings = config.load(CONFIG_DIR)
    date = plan().date
    frozen = assemble.day_dir(cli.PUBLIC_ROOT, date)
    frozen.mkdir(parents=True, exist_ok=True)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    assemble.write_atomic(frozen / "digest.json", day.to_json())
    assemble.write_atomic(
        frozen / "run.json",
        assemble.build_manifest(
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
            site_bytes=1,
            site_files=1,
        ).to_json(),
    )

    def planned(execution: int | None) -> str:
        return cli.stage_plan(
            date,
            settings=settings,
            fetcher=lambda _url: FetchResult(outcome=FetchOutcome.TRANSIENT, detail="offline"),
            now=lambda: "2026-08-21T09:00:00Z",
            execution=execution,
            state_dir=tmp_path / "state",
        ).run_id

    # Neither run has published, so the count is the same answer for both.
    assert cli._next_run_n(date) == cli._next_run_n(date) == 2
    assert planned(None) == planned(None), "the count cannot tell two executions apart"

    assert planned(33270983446) == f"{date}-33270983446"
    assert planned(33270983446) != planned(33274853468)


def test_a_shard_records_its_own_items_and_nobody_else_s(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Eight workers run at once, so a shard that recorded the day would file
    rows for items the other seven are still holding."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        shard=0,
        shards=2,
        model_endpoint=closed_loopback_endpoint(),
    )

    cli.stage_record(run_plan, settings=settings, shard=0, shards=2)

    mine = [item.item_id for item in cli.shard_of(run_plan, shard=0, shards=2)]
    assert [row.item_id for row in health_rows(tmp_path / "state", run_plan.date)] == mine
    assert len(mine) < len(run_plan.items)


def test_an_item_whose_summary_is_not_written_yet_is_not_recorded(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An interruption is not a failure, and this ledger cannot correct a row.

    The worker writes an article payload for every item it reaches and a summary
    payload for every item that got as far as the model. An accepted article with
    no summary beside it means the shard stopped mid-item.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_visual_payloads(run_plan, items_dir, text=FULL_TEXT)
    interrupted = run_plan.items[1]
    (items_dir / f"{interrupted.item_id}.summary.json").unlink()

    recorded, _ = cli.stage_record(run_plan, settings=config.load(CONFIG_DIR))

    settled = [item.item_id for item in run_plan.items if item.item_id != interrupted.item_id]
    assert recorded == len(settled)
    assert [row.item_id for row in health_rows(tmp_path / "state", run_plan.date)] == settled
    assert telemetry.is_final(article(), None) is False
    assert telemetry.is_final(None, None) is False


def test_a_shard_commits_what_its_model_server_counted(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle for row 9: the second instrument survives the job that read it.

    Every timing on the item-health ledger is a field copied out of one model
    reply. The server counts the same work for itself, and until this stage
    existed those counters reached only a job log with two days of retention -
    so the read rate two published surfaces quote could be reported and never
    reconciled (Guardrail #10).
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)
    capture = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-3.prom"

    row = cli.stage_counters(run_plan, metrics_path=capture, shard=0, shards=1)

    assert row.prompt_tokens_total == 23411
    assert row.prompt_seconds_total == 2128.08
    committed = ledger.load_runtime_counters(tmp_path / "state", run_id=run_plan.run_id)
    assert committed == [row]
    assert ledger.read_header(ledger.runtime_counters_path(tmp_path / "state")) == (
        RuntimeCountersRow.csv_columns()
    )


def test_a_shard_whose_server_died_still_files_a_row(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """No file at all is a fact about the shard, not an absence of one.

    Pooling a run has to see the shard that contributed nothing, or three
    shards' tokens get quoted as a four-shard run. The cells are null rather
    than zero: the server did not answer, it did not read nothing.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)

    row = cli.stage_counters(run_plan, metrics_path=tmp_path / "never-written.prom")

    assert row.prompt_tokens_total is None
    assert row.run_id == run_plan.run_id
    assert ledger.load_runtime_counters(tmp_path / "state", run_id=run_plan.run_id) == [row]


def test_the_two_ledgers_agree_about_which_shards_ran(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle for the shard column: the per-item file joins the per-run file.

    Read speed varied 1.10x to 4.19x between the shards of one run over the seven
    runs committed on 2026-08-30, so a rate pooled over a run averages away the
    thing an operator needs to see. The join is `(run_id, shard)`, and it only
    works if both files name the same set of workers - two ledgers that disagree
    about how many machines ran cannot be put on one chart.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    capture = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-3.prom"

    for shard in (0, 1):
        cli.stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
            shard=shard,
            shards=2,
            model_endpoint=closed_loopback_endpoint(),
        )
        cli.stage_record(run_plan, settings=settings, shard=shard, shards=2)
        cli.stage_counters(run_plan, metrics_path=capture, shard=shard, shards=2)

    rows = health_rows(state, run_plan.date)
    counted = ledger.load_runtime_counters(state, run_id=run_plan.run_id)

    assert {row.shard for row in rows} == {row.shard for row in counted} == {0, 1}
    assert len(rows) == len(run_plan.items)
    for shard in (0, 1):
        mine = {item.item_id for item in cli.shard_of(run_plan, shard=shard, shards=2)}
        assert {row.item_id for row in rows if row.shard == shard} == mine
        assert mine, "a shard with no items would make the set comparison pass on nothing"


def test_the_census_assemble_adds_names_no_machine(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """One worker of two ran, and the rows for the other half stay unclaimed.

    `shard_of` is deterministic, so assemble could work out which machine each
    missing item was meant for. It must not: the item was not worked, and a
    number there would put items on a machine's bar that the machine never
    touched. Empty is the honest cell, and it is the same cell every row written
    before 2026-08-30 holds.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    cli.stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        shard=0,
        shards=2,
        model_endpoint=closed_loopback_endpoint(),
    )
    cli.stage_record(run_plan, settings=settings, shard=0, shards=2)

    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    rows = health_rows(state, run_plan.date)
    worked = {item.item_id for item in cli.shard_of(run_plan, shard=0, shards=2)}
    assert len(rows) == len(run_plan.items)
    assert {row.item_id for row in rows if row.shard == 0} == worked
    assert {row.item_id for row in rows if row.shard is None} == {
        item.item_id for item in run_plan.items
    } - worked
    assert any(row.shard is None for row in rows), "the run left nothing for assemble to census"


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


def test_a_desk_publishes_why_it_ran_what_it_ran() -> None:
    """The plan counted what the feeds offered and the day used to throw it away.

    Without it a desk that published three stories and a desk whose feeds broke
    look identical on the page, and the reader has no way to tell them apart.
    """
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in day.verticals if ref.id == "ai")
    assert desk.considered == 5, "the day dropped what the plan already counted"
    assert desk.too_old == 0
    assert desk.below_feed_floor is False


def test_a_desk_no_run_ever_planned_invents_no_shortfall() -> None:
    """Absent reads as unknown, never as zero.

    A zero would say the feeds offered this desk nothing, which on a desk that
    published a story is a claim the payload itself contradicts.
    """
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan().model_copy(update={"verticals": []}),
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in day.verticals if ref.id == "ai")
    assert desk.considered is None
    assert desk.too_old is None
    assert desk.below_feed_floor is None


def test_a_desk_keeps_the_strongest_shortfall_any_run_recorded() -> None:
    """The strongest and not the sum, and this is the case that says why.

    Run 2 drops what run 1 published before it counts anything, so it sees a
    smaller pool of the same back-catalogue stories. Summing the runs would
    print a number the feeds never offered.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    wide = base.model_copy(
        update={
            "verticals": [
                VerticalPlan(id="ai", considered=40, planned=5, eligible_feeds=3, too_old=28)
            ]
        }
    )
    narrow = base.model_copy(
        update={
            "verticals": [
                VerticalPlan(id="ai", considered=35, planned=0, eligible_feeds=3, too_old=31)
            ]
        }
    )

    first = assemble.build_day(
        plan=wide,
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=narrow,
        items=[digest_item(run_n=1)],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in second.verticals if ref.id == "ai")
    assert desk.considered == 40, "the second run's smaller pool overwrote the first"
    assert desk.too_old == 31, "a run that found more of the day stale must raise the count"
    assert desk.too_old <= desk.considered, "the sentence would name more dropped than offered"


def test_a_desk_retired_mid_day_keeps_the_explanation_it_already_had() -> None:
    """A desk with items and no entry in today's plan is not a desk with no answer.

    It happens when `config/taxonomy.json` retires a vertical between runs. The
    stories stay on the day, so the sentence under them has to stay true.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    first = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=base.model_copy(update={"verticals": []}),
        items=[digest_item(run_n=1)],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in second.verticals if ref.id == "ai")
    assert desk.considered == 5
    assert desk.below_feed_floor is False


def test_a_run_that_comes_back_as_itself_still_produces_a_day() -> None:
    """`stage_assemble` writes the day, then builds the manifest, then writes it.

    A run that dies in that gap leaves a day carrying its items and a manifest
    that never heard of it, so the next run reads the same number off the
    manifest and appends to a day that already holds work under that number.
    The run reference has to count every item the number introduced, because
    that is what `DigestDay` validates it against.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    crashed = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1).model_copy(update={"item_id": base.items[0].item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    replayed = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1).model_copy(update={"item_id": base.items[1].item_id})],
        previous=crashed,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )

    assert len(replayed.items) == 2, "the replay keeps what its own first attempt published"
    assert [run.n for run in replayed.runs] == [1], "one attempt and its replay are one run"
    assert replayed.runs[0].items_added == 2, (
        "the reference counts what run 1 introduced, not what this attempt added"
    )


def test_a_carried_item_is_not_recorded_as_published_twice() -> None:
    """The join in `_published_rows` is the only thing keeping `published.csv` clean.

    `ledger._append` writes every row it is handed, so a second row for one
    address would stay in the file forever. A day carries yesterday's items
    forward, and the plan a later run built has already dropped their addresses,
    so they fall out of the join instead of being recorded again.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    first, second = base.items[0], base.items[1]
    first_plan = base.model_copy(update={"items": [first]})
    later_plan = base.model_copy(update={"items": [second], "run_id": f"{base.date}-2"})

    day_one = assemble.build_day(
        plan=first_plan,
        items=[digest_item(run_n=1).model_copy(update={"item_id": first.item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    day_two = assemble.build_day(
        plan=later_plan,
        items=[digest_item(run_n=2).model_copy(update={"item_id": second.item_id})],
        previous=day_one,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )

    assert [item.item_id for item in day_two.items] == [first.item_id, second.item_id]
    assert [row.url_key for row in cli._published_rows(day_one, first_plan)] == [first.url_key]
    assert [row.url_key for row in cli._published_rows(day_two, later_plan)] == [second.url_key]


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


def test_the_run_records_the_scoring_shape_that_decided_its_order() -> None:
    """`RANK_VERSION` was read by nothing, so no run had ever recorded it.

    The stage that publishes the order is the stage that names the shape it was
    published under, and it names the constant rather than a string of its own -
    two spellings of one version is the failure this field exists to close.
    """
    settings = config.load(CONFIG_DIR)
    source = read_text(REPO_ROOT / "backend" / "idhazh" / "cli.py")
    assert "rank_version=rank.RANK_VERSION" in source, (
        "the assemble stage stopped recording the scoring shape"
    )

    manifest = assemble.build_manifest(
        plan=plan(),
        day=assemble.build_day(
            plan=plan(),
            items=[digest_item()],
            previous=None,
            taxonomy=settings.taxonomy,
            run_n=1,
            generated_at="2026-08-21T07:00:00Z",
            retention_window_months=-1,
        ),
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
        rank_version=rank.RANK_VERSION,
    )
    assert manifest.runs[-1].rank_version == rank.RANK_VERSION

    # A caller that records nothing writes null, which reads as unknown. It must
    # never read as "the shape this build happens to carry".
    silent = assemble.build_manifest(
        plan=plan(),
        day=manifest_day(settings),
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
    assert silent.runs[-1].rank_version is None


def test_a_run_records_how_many_feeds_a_desk_could_ask_and_against_what_floor() -> None:
    """`below_feed_floor` alone says a desk went dark and neither number that decided it.

    The manifest is the only committed record of a plan - `plan.json` is a
    one-day artifact - so a reader looking at why a desk was absent has nothing
    else to read. Both numbers are carried straight from the plan and computed
    nowhere else, so the run that published cannot disagree with the run that
    decided. A desk whose plan carried no floor writes null, which is unknown
    rather than a floor of zero.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    floored = base.model_copy(
        update={
            "verticals": [
                vertical.model_copy(update={"feed_floor": 35})
                if vertical.id == "ai"
                else vertical
                for vertical in base.verticals
            ]
        }
    )
    manifest = assemble.build_manifest(
        plan=floored,
        day=manifest_day(settings),
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

    counts = {count.id: count for count in manifest.runs[-1].verticals}
    planned = {vertical.id: vertical for vertical in floored.verticals}
    assert counts["ai"].eligible_feeds == planned["ai"].eligible_feeds
    assert counts["ai"].feed_floor == 35
    assert counts["energy"].feed_floor is None


def manifest_day(settings: config.Settings) -> DigestDay:
    return assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )


def test_the_manifest_cannot_record_one_run_twice() -> None:
    """One execution is one record, however many times it reaches this stage.

    `run_id` is the identity of the execution rather than a count of what is
    committed, so an assemble job that runs again reads the same plan and
    computes the same id. It replaces its own record instead of appending a
    second one that planned nothing - the rule `build_day` already applies to
    the day's own run list. The contract refuses the shape either way.
    """
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

    def manifest_after(previous: RunManifest | None, run_id: str) -> RunManifest:
        return assemble.build_manifest(
            plan=plan().model_copy(update={"run_id": run_id}),
            day=day,
            previous=previous,
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

    first = manifest_after(None, "2026-08-21-33270983446")
    replayed = manifest_after(first, "2026-08-21-33270983446")
    assert [run.n for run in replayed.runs] == [1], "one execution and its replay are one run"
    assert [run.run_id for run in replayed.runs] == ["2026-08-21-33270983446"]

    # A different execution is a different run, and takes the next number.
    second = manifest_after(first, "2026-08-21-33274853468")
    assert [run.n for run in second.runs] == [1, 2]

    with pytest.raises(ValidationError, match="numbered from 1 without gaps"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=first.date,
            runs=[first.runs[0], first.runs[0]],
        )
    with pytest.raises(ValidationError, match="numbered from 1 without gaps"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=second.date,
            runs=[second.runs[1], second.runs[0]],
        )
    # And the shape the collision made: two records, correctly numbered, that
    # name one execution between them.
    with pytest.raises(ValidationError, match="cannot share a run_id"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=second.date,
            runs=[
                second.runs[0],
                second.runs[1].model_copy(update={"run_id": second.runs[0].run_id}),
            ],
        )


def test_the_manifest_records_what_the_planner_cost() -> None:
    """The visuals job runs against a 60-minute bound and nothing recorded its cost.

    The stage total and the item count are committed together, because either
    one alone answers no question about the budget (Guardrail #10).
    """
    settings = config.load(CONFIG_DIR)
    decided = VisualDecision.from_json(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    def manifest_for(decisions: list[VisualDecision]) -> RunManifest:
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
            decisions=decisions,
        )

    timed = manifest_for(
        [
            decided.model_copy(update={"decision_ms": 4000}),
            decided.model_copy(update={"decision_ms": 11000}),
        ]
    )
    assert timed.runs[-1].items_decided == 2
    assert timed.runs[-1].decision_ms == 15000

    # The Python names moved on 2026-09-05 and the published keys did not, so the
    # serialised record is checked here rather than only the attributes above.
    written = json.loads(timed.to_json())["runs"][-1]
    assert written["items_routed"] == 2
    assert written["route_ms"] == 15000
    assert "items_decided" not in written and "decision_ms" not in written

    # A planner that never started is not a planner that took no time.
    absent = manifest_for([])
    assert absent.runs[-1].items_decided == 0
    assert absent.runs[-1].decision_ms is None

    # Neither is a payload written before the clock existed.
    unclocked = manifest_for([decided.model_copy(update={"decision_ms": None})])
    assert unclocked.runs[-1].items_decided == 1
    assert unclocked.runs[-1].decision_ms is None

    # The gate changes every denominator: the same charts sit over a smaller
    # decided set. Counting the skips keeps a chart rate from climbing on its own.
    gated = manifest_for(
        [
            decided.model_copy(update={"decision_ms": 4000}),
            decided.model_copy(update={"decision_ms": 1, "asked_the_model": False}),
            decided.model_copy(update={"decision_ms": 1, "asked_the_model": False}),
        ]
    )
    assert gated.runs[-1].items_decided == 3
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


# --- Sampling the scorer, by run ----------------------------------------------


def synthetic_run_ids(count: int = 1000) -> list[str]:
    """Distinct ids in the shape the pipeline mints them: `<date>-<n>`."""
    return [
        f"2026-{index // 155 + 1:02d}-{index % 31 + 1:02d}-{index % 5 + 1}"
        for index in range(count)
    ]


def observed(observability: ObservabilityConfig) -> config.Settings:
    """The committed settings with one observability block swapped in."""
    settings = config.load(CONFIG_DIR)
    return config.Settings(
        app=settings.app.model_copy(update={"observability": observability}),
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )


def last_record(tmp_path: Path, run_plan: RunPlan) -> RunRecord:
    day_dir = assemble.day_dir(tmp_path / "public" / "digest", run_plan.date)
    return RunManifest.from_json(read_text(day_dir / "run.json")).runs[-1]


def test_a_full_rate_draws_every_run_and_changes_nothing() -> None:
    """A knob whose default moves any behaviour has failed before it ships.

    One is short-circuited rather than compared, because a position near enough
    to one rounds to exactly 1.0 as a float and `1.0 < 1.0` is false.
    """
    assert all(sampling.run_is_sampled(run_id, 1.0) for run_id in synthetic_run_ids())
    assert all(
        cli._scores_this_run(ObservabilityConfig(), run_id=run_id, flag_allows=True)
        for run_id in synthetic_run_ids()
    )


def test_the_same_run_id_draws_the_same_way_every_time() -> None:
    """A selector nobody can reproduce is a ledger nobody can audit a year later."""
    ids = synthetic_run_ids()
    first = [sampling.run_is_sampled(run_id, 0.5) for run_id in ids]
    second = [sampling.run_is_sampled(run_id, 0.5) for run_id in ids]

    assert first == second
    assert all(0.0 <= sampling.position_of(run_id) < 1.0 for run_id in ids)
    assert sampling.position_of("2026-08-21-1") == sampling.position_of("2026-08-21-1")


def test_half_the_rate_draws_about_half_the_runs() -> None:
    """1,000 draws at 0.5 has a standard deviation of 15.8, so 50 is over three of them."""
    drawn = sum(1 for run_id in synthetic_run_ids() if sampling.run_is_sampled(run_id, 0.5))
    assert 450 <= drawn <= 550, f"{drawn} of 1000 drawn at a rate of 0.5"


def test_raising_the_rate_only_ever_adds_runs() -> None:
    """A run scored yesterday still scores today, so a series does not develop a hole."""
    ids = synthetic_run_ids()
    rates = (0.1, 0.25, 0.5, 0.75, 0.9)
    drawn = {
        rate: {run_id for run_id in ids if sampling.run_is_sampled(run_id, rate)} for rate in rates
    }

    for lower, higher in itertools.pairwise(rates):
        assert drawn[lower] < drawn[higher], f"{lower} is not a subset of {higher}"


def test_the_draw_sees_the_run_id_and_the_rate_and_nothing_else() -> None:
    """Blindness is a property of the signature, never of one sample.

    A selector that could see a score would thin the ledger towards whatever it
    preferred, and no later reader could tell that it had.
    """
    assert list(inspect.signature(sampling.run_is_sampled).parameters) == [
        "run_id",
        "sample_rate",
    ]
    assert list(inspect.signature(sampling.position_of).parameters) == ["run_id"]


def test_the_work_stage_gate_and_the_selector_agree() -> None:
    thinned = ObservabilityConfig(sample_rate=0.3)
    for run_id in synthetic_run_ids(200):
        assert cli._scores_this_run(thinned, run_id=run_id, flag_allows=True) is (
            sampling.run_is_sampled(run_id, 0.3)
        )


def test_the_flag_beats_the_file_and_no_flag_turns_the_scorer_back_on() -> None:
    on = ObservabilityConfig()
    off = ObservabilityConfig(evaluation_enabled=False)

    assert cli._scores_this_run(on, run_id="2026-08-21-1", flag_allows=True)
    assert not cli._scores_this_run(on, run_id="2026-08-21-1", flag_allows=False)
    assert not cli._scores_this_run(off, run_id="2026-08-21-1", flag_allows=True)


@pytest.mark.parametrize("rate", [1.0, 0.5, 0.01])
def test_every_run_records_the_rate_it_ran_under(
    tmp_path: Path, monkeypatch: MonkeyPatch, rate: float
) -> None:
    """A rate recorded only when it bites cannot be told from a rate never set.

    Eight hundred rows of a thousand and eight hundred of eight hundred are the
    same eight hundred rows in the ledger, and only the manifest can separate
    them.
    """
    run_plan = plan()
    settings = observed(ObservabilityConfig(sample_rate=rate))
    isolate_ledgers(tmp_path, monkeypatch)

    work_then_assemble(run_plan, settings)
    record = last_record(tmp_path, run_plan)

    assert record.evaluation_sample_rate == rate
    assert record.evaluation_enabled is True
    assert record.evaluation_sampled is sampling.run_is_sampled(run_plan.run_id, rate)


def test_a_run_with_the_scorer_off_writes_no_row_and_names_no_instrument(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Switched off and would not load are different facts, and null is neither."""
    run_plan = plan()
    settings = observed(ObservabilityConfig(evaluation_enabled=False))
    isolate_ledgers(tmp_path, monkeypatch)

    work_then_assemble(run_plan, settings)
    record = last_record(tmp_path, run_plan)

    assert record.evaluation_enabled is False
    assert record.scorer_version is None
    assert not writer.ledger_shards(tmp_path / "state")


def test_a_scored_run_names_the_instrument_that_wrote_its_rows(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
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
    score_one_item(items_dir, run_plan)
    cli.stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    record = last_record(tmp_path, run_plan)

    assert record.scorer_version == row().scorer_version
    assert record.evaluation_sampled is True


# --- A frozen day is never re-validated ---------------------------------------
#
# `validate-days` opened every committed day on every publication and on every
# CI run, parsed it and put it through both contracts a reader holds. A
# published day is frozen, so a second reading can only reach the verdict the
# first one did - what can move is the shape the day is read through. That is a
# bill arriving for an answer the tree already holds, and it grows on a day
# nobody writes any code (Guardrail #12).
#
# Every fixture below is built in the test from the committed contract fixture.
# None of it reads `frontend/public/digest`, whose cost follows what the
# pipeline has piled up (CLAUDE.md section 13).

A_COMMITTED_DAY = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"


def a_published_day(public_root: Path, *, pretty: bool = False) -> Path:
    """One published day on disk, in the layout `published_days` globs for.

    The pictures the payload names are drawn as well, because `_picture_faults`
    compares the two and a day naming a file that is not there is a fault rather
    than the clean day these tests need. `pretty` re-serialises the same payload
    over more bytes, which is what a re-encode does to a closed day.
    """
    payload = json.loads(read_text(A_COMMITTED_DAY))
    year, month, dom = str(payload["date"]).split("-")
    where = public_root / "digest" / year / month / dom
    where.mkdir(parents=True, exist_ok=True)
    for item in payload["items"]:
        visual = item.get("visual")
        if visual and visual.get("path"):
            drawing = public_root / visual["path"]
            drawing.parent.mkdir(parents=True, exist_ok=True)
            drawing.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
    (where / "digest.json").write_text(text, encoding="utf-8")
    return where / "digest.json"


def days_opened(root: Path, work: Callable[[], int]) -> tuple[int, set[str]]:
    """What `work` returned, and which files under `root` it opened.

    Measured at the file boundary rather than by timing, so the answer is the
    same on a loaded machine. Both doors into a committed day are watched, and
    the set collapses a file reached through both.

    It takes its own `MonkeyPatch` context rather than the fixture, because a
    caller that has patched something else wants that patch to survive this
    call - `monkeypatch.undo()` undoes everything a test set, not just what the
    helper set.
    """
    seen: set[str] = set()

    def note(path: Path) -> None:
        try:
            seen.add(path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            return

    real_open = Path.open
    real_read = Path.read_bytes

    def spy_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        note(self)
        return real_open(self, *args, **kwargs)

    def spy_read(self: Path) -> bytes:
        note(self)
        return real_read(self)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Path, "open", spy_open)
        patch.setattr(Path, "read_bytes", spy_read)
        return work(), seen


def test_a_day_with_no_receipt_is_validated_and_earns_one(tmp_path: Path) -> None:
    """Arm one, and what every tree looks like the first time this runs.

    Nothing is skipped on trust it has not earned, so a tree with no receipts
    costs exactly what this stage cost before the receipt existed. What it
    leaves behind is the record that makes the next run free, and the record is
    a claim about the payload it read: the length and the digest are taken from
    the bytes that passed.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    day = a_published_day(public)
    root = public / "digest"

    code, opened = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))

    assert code == 0
    assert "2026/08/21/digest.json" in opened, "a day with no receipt has to be read"
    held = cli._receipts_for(state, cli._validator_identity())
    assert set(held) == {"2026-08-21"}
    (receipt,) = held["2026-08-21"]
    assert receipt.payload_bytes == day.stat().st_size
    assert receipt.payload_digest == hashlib.sha256(day.read_bytes()).hexdigest()


def test_an_unchanged_day_under_an_unchanged_validator_is_not_opened(tmp_path: Path) -> None:
    """Arm two, and the whole saving, counted rather than timed.

    A published day cannot stop matching a contract on its own, so the second
    reading of it buys nothing. Measured 2026-09-08 on an Intel Core i7-1265U
    over the 18 committed days: 0.45 s median with nothing recorded against
    0.02 s with every receipt current.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"

    first_code, first = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))
    second_code, second = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))

    assert (first_code, second_code) == (0, 0)
    assert "2026/08/21/digest.json" in first
    assert second == set(), f"a frozen day was opened again: {sorted(second)}"


def test_a_day_whose_payload_moved_is_opened_again(tmp_path: Path) -> None:
    """The receipt is a claim about a payload, never a claim about a date.

    `backfill.yml` re-encodes closed days and then validates with no day named.
    A record keyed on the date alone would wave those days through unread, which
    is the one way this row could weaken the guarantee it is speeding up. The
    recorded length is what `os.stat` answers without opening anything, and a
    re-encode moves it.

    The rewritten day then settles down. The row about the payload that used to
    be there is still in the file - `merge=union` makes the file append-only -
    and it is ignored rather than held against the day, so the next run is free
    again.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert cli.stage_validate_days(root, state_dir=state) == 0

    rewritten = a_published_day(public, pretty=True)
    code, opened = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))
    after, quiet = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))

    assert (code, after) == (0, 0)
    assert "2026/08/21/digest.json" in opened, "a rewritten day was skipped on a stale receipt"
    assert quiet == set(), "the rewritten day never settled down"
    held = cli._receipts_for(state, cli._validator_identity())
    assert len(held["2026-08-21"]) == 2, "the superseded row should still be on file"
    assert cli._proved(held["2026-08-21"], rewritten.stat().st_size)


def test_a_named_day_is_opened_even_when_it_carries_a_receipt(tmp_path: Path) -> None:
    """Naming a day is how a run says it just wrote that day.

    The publishing job names the date it published, and the receipt on file at
    that moment is about the payload that stood there before this run replaced
    it. So a named day is read, and the receipt is never consulted for it.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert cli.stage_validate_days(root, state_dir=state) == 0

    code, opened = days_opened(
        root, lambda: cli.stage_validate_days(root, ["2026-08-21"], state_dir=state)
    )

    assert code == 0
    assert "2026/08/21/digest.json" in opened


def test_the_validator_identity_moves_when_a_rule_moves() -> None:
    """Arm three, first half: what the receipt is keyed on cannot go stale by hand.

    A hand-maintained version is a check that stops checking on the day somebody
    forgets to bump it, and it fails silently - the gate goes on printing a
    pass. So the identity is derived from the two generated schemas and the
    source of the functions that do the checking.

    The replacement here returns exactly what the shipped rule returns, so the
    only thing that moved is the source. That is the point: the receipt is a
    claim about the rules a day was read under, not about the verdict they
    happened to reach.
    """
    before = cli._validator_identity()
    shipped = cli._picture_faults

    def reworded(public_root: Path, day: DigestDay) -> list[str]:
        """The shipped rule under another name. Same verdict, different source."""
        return shipped(public_root, day)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli, "_picture_faults", reworded)
        assert cli._validator_identity() != before


def test_the_validator_identity_moves_when_a_contract_moves() -> None:
    """Arm three, second half: a shape change invalidates every receipt too.

    Section 11 makes a changelog entry mandatory for any change to a persisted
    shape, and that entry lands in the generated schema. Digesting the schema is
    what ties a receipt to the contract the day was read through, so a widened
    field cannot be waved past on a record earned under the old one.
    """
    before = cli._validator_identity()
    moved = (
        ChangelogEntry(version="2099-01-01", change="a shape change", why="this test's own"),
        *DigestView.__changelog__,
    )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(DigestView, "__changelog__", moved)
        assert cli._validator_identity() != before


def test_a_moved_validator_reopens_every_day_once(tmp_path: Path) -> None:
    """Arm three, and the reason an uninvalidatable receipt is worse than none.

    The receipt is earned, the day goes unread, and then the rules move. Every
    day is opened again - not on a window and not one at a time - and the sweep
    that does it leaves a fresh record, so it happens once rather than on every
    later run.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    a_published_day(public)
    root = public / "digest"
    assert cli.stage_validate_days(root, state_dir=state) == 0
    _, quiet = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))
    assert quiet == set()

    shipped = cli._picture_faults

    def reworded(public_root: Path, day: DigestDay) -> list[str]:
        """The shipped rule under another name. Same verdict, different source."""
        return shipped(public_root, day)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli, "_picture_faults", reworded)
        first, reopened = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))
        second, again = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))

    assert (first, second) == (0, 0)
    assert "2026/08/21/digest.json" in reopened, "a moved rule left the archive unread"
    assert again == set(), "the sweep after a rule change has to happen once"


def test_two_receipts_that_disagree_about_one_day_leave_it_unproved(tmp_path: Path) -> None:
    """`merge=union` concatenates, so two runs really can leave two rows.

    Where they disagree about the payload the day has no single claim, and a day
    with no single claim is read rather than trusted. This is what the recorded
    digest is for: the lengths can match while the bytes do not.
    """
    public = tmp_path / "public"
    state = tmp_path / "state"
    day = a_published_day(public)
    root = public / "digest"
    assert cli.stage_validate_days(root, state_dir=state) == 0

    receipts = cli.day_validations_path(state)
    rows = list(csv.DictReader(receipts.read_text(encoding="utf-8").splitlines()))
    disagreeing = {**rows[0], "payload_digest": "b" * 64}
    with receipts.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n").writerow(disagreeing)

    held = cli._receipts_for(state, cli._validator_identity())
    assert not cli._proved(held["2026-08-21"], day.stat().st_size)

    code, opened = days_opened(root, lambda: cli.stage_validate_days(root, state_dir=state))

    assert code == 0
    assert f"2026/08/21/{day.name}" in opened


# --- The desk is a new field, and the feed's word stays where it is ---------
#
# Row #6 of TODO/20260910-23-article-classification-plan.md, at the stage that
# builds a published item and a published day. Every case is built from the
# committed contract fixtures in memory; nothing reads the digest tree.


def relabelled_article() -> Article:
    """An energy feed's story about compute, addressed from the feed's word.

    `model_copy` rather than a new Article, so the url_key and every other field
    stay the fixture's own - the only thing under test is which of the two words
    ends up where.
    """
    return article().model_copy(
        update={"item_id": "energy-01", "vertical": "energy", "desk": "ai"}
    )


def test_a_published_item_carries_the_desk_and_keeps_the_feeds_address() -> None:
    """The oracle, at the stage that writes the item.

    The desk is what the day publishes it under. `item_id` is addressed from
    `vertical`, which did not move - so a link somebody shared this morning
    still resolves this evening.
    """
    item = assemble.to_digest_item(
        article=relabelled_article(),
        summary=summary().model_copy(update={"item_id": "energy-01"}),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.vertical == "energy"
    assert item.desk == "ai"
    assert item.item_id.startswith("energy-")


def test_an_unlabelled_article_publishes_with_no_desk_at_all() -> None:
    """Nothing fills `desk` yet, and the published item may not invent one.

    Null is unknown, and the page falls back to the vertical. A default here
    would make every item claim a reading of itself that never happened.
    """
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.desk is None


def test_a_story_relabelled_onto_a_desk_that_will_not_render_stays_put() -> None:
    """Decision 8, at the stage that decides it.

    A vertical under its feed floor is collected and never rendered. Letting
    another vertical's stories land there would render a topic the same day's
    payload flags as having planned nothing.
    """
    item = assemble.to_digest_item(
        article=relabelled_article(),
        summary=summary().model_copy(update={"item_id": "energy-01"}),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
        below_floor_desks=frozenset({"ai"}),
    )

    assert item.desk == "energy", "the feed floor is about supply, and supply is per feed"


def test_a_day_lists_both_words_and_counts_each_under_its_own() -> None:
    """`count` is the feed's word; `desk_count` is what the page draws.

    Both names are owed a ref. The vertical needs one because `count` is a
    statement about its feeds, and the desk needs one because the page draws a
    heading, a pill and a route from it - so a day that listed only the desk
    would publish a count with nothing to attach it to, and one that listed only
    the vertical would render a story under a nameless topic.
    """
    day = assemble.build_day(
        plan=plan(),
        items=[
            assemble.to_digest_item(
                article=relabelled_article(),
                summary=summary().model_copy(update={"item_id": "energy-01"}),
                band=row().band,
                source_name="Example Lab",
                source_kind=SourceKind.REPORTING,
                run_n=1,
            )
        ],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    refs = {ref.id: ref for ref in day.verticals}
    assert set(refs) == {"ai", "energy"}
    assert refs["energy"].count == 1, "the feed that carried it still declares energy"
    assert refs["energy"].desk_count == 0, "and the page draws nothing under energy"
    assert refs["ai"].count == 0, "no ai feed carried this story"
    assert refs["ai"].desk_count == 1, "the reader finds it under ai"
    assert refs["ai"].display_name, "a desk a reader can reach needs a name to reach it by"


def test_a_day_nothing_relabelled_publishes_the_same_two_numbers() -> None:
    """The ordinary day, which is every day published so far.

    `desk_count` is written on every day from now on rather than only when it
    differs, so a page never has to ask whether this day is one of the ones that
    said - and on a day nothing relabelled the two numbers agree.
    """
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    assert day.verticals
    for ref in day.verticals:
        assert ref.desk_count == ref.count


# --- The two calls, in the pipeline, behind one flag --------------------------

#: What a `Summary` carries that is a clock rather than a decision. Two runs of
#: one recorded reply agree on everything else, and these five are why "the same
#: bytes" is asserted after they come off rather than over the whole payload.
CLOCKS: Final = ("generated_at", "duration_ms", "fetch_ms", "extract_ms", "summarize_ms")

CALL_ONE_REPLY: Final = FIXTURES_DIR / "completions" / "call-one" / "labelled.json"
CALL_TWO_REPLY: Final = FIXTURES_DIR / "completions" / "call-two" / "summary-and-plan.json"


def two_call_settings(on: bool) -> config.Settings:
    """The committed config with the flag moved and nothing else."""
    settings = config.load(CONFIG_DIR)
    return config.Settings(
        app=settings.app.model_copy(
            update={"run": settings.app.run.model_copy(update={"two_calls_per_item": on})}
        ),
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )


def worked(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    on: bool,
    replies: tuple[bytes, ...],
) -> tuple[RunPlan, Path, int]:
    """One real work stage over captured pages and recorded replies.

    No network and nothing mocked: the pages come off disk and the replies are
    played back by a real loopback server (Guardrail #7). The third value is how
    many requests the stage sent, which is the only way to tell one call an item
    from two without reading a payload that both paths can produce.
    """
    run_plan = plan()
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    with RecordedEndpoint(200, *replies) as server:
        cli.stage_work(
            run_plan,
            settings=two_call_settings(on),
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )
        served = server.served
    return run_plan, tmp_path / "run" / run_plan.date / "items", served


def without_clocks(summary: Summary) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(summary.to_json())
    for field in CLOCKS:
        payload.pop(field, None)
    return payload


def only_stamp(items: Path) -> FingerprintRow:
    """The one pipeline stamp a single-shard run leaves, named by itself.

    More than one means the stage observed two configurations in one shard,
    which is a finding rather than something to pick from.
    """
    stamps = sorted(items.glob("*.fingerprint.json"))
    assert len(stamps) == 1, f"one shard, one stamp, got {[path.name for path in stamps]}"
    return FingerprintRow.read(stamps[0])


class TestTheFlagOffLeavesTodaysPipelineWhereItWas:
    """The acceptance gate. This row lands with the flag off, so the whole of
    what a reader gets on the day it merges is what the flag-off path produces -
    and the change that could move it is invisible in a diff, because the
    pipeline stamp is computed once a shard and written into every payload."""

    def test_one_request_an_item_and_no_second_one(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        reply = (FIXTURES_DIR / "completions" / "ok.json").read_bytes()

        run_plan, _items, served = worked(tmp_path, monkeypatch, on=False, replies=(reply,))

        assert served == len(run_plan.items), "the flag off is one summarizer call an item"

    def test_the_stage_writes_the_summary_the_library_builds(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Same bytes, and the comparison is against `summarize.to_summary` rather
        than against an earlier copy of itself. That is what can fail: the stage
        picks the prompt config, the evaluation bounds and the stamp, and a
        two-call path wired into the wrong branch would change one of the three
        while every payload still validated."""
        reply = (FIXTURES_DIR / "completions" / "ok.json").read_bytes()
        completion = parse_completion(reply.decode("utf-8"))
        settings = two_call_settings(False)

        run_plan, items, _served = worked(tmp_path, monkeypatch, on=False, replies=(reply,))

        for item in run_plan.items:
            written = Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            article = Article.read(items / f"{item.item_id}.article.json")
            expected = summarize.to_summary(
                article,
                completion,
                model_id=settings.app.models.summarize.id,
                pipeline_fingerprint=written.pipeline_fingerprint,
                generated_at=written.generated_at,
                prompt_config=settings.app.summarize,
                evaluation=settings.app.evaluation,
            )
            assert without_clocks(written) == without_clocks(expected)

    def test_the_stamp_still_digests_the_single_call_prompt(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The stamp is what a re-run compares against, so moving it with the flag
        off would re-summarize every item in the archive for nothing."""
        reply = (FIXTURES_DIR / "completions" / "ok.json").read_bytes()
        settings = two_call_settings(False)

        _run_plan, items, _served = worked(tmp_path, monkeypatch, on=False, replies=(reply,))

        assert only_stamp(items).inputs.prompt_sha256 == text_digest(
            summarize.prompt_inputs(settings.app.summarize)
        )

    def test_the_work_stage_writes_no_decision(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """With the flag off nothing in `work` writes a decision, so the separate
        stage is still the only producer - which is what makes the flag
        reversible right up until row #6 deletes the old path."""
        reply = (FIXTURES_DIR / "completions" / "ok.json").read_bytes()

        _run_plan, items, _served = worked(tmp_path, monkeypatch, on=False, replies=(reply,))

        assert not list(items.glob(f"*{PAYLOAD_SUFFIX}"))


class TestTheFlagOnDispatchesBothCalls:
    def test_two_requests_an_item_and_the_cost_is_split_between_them(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Trigger 1's instrument, end to end. `call_1` and `call_2` are what the
        ledger carries per call, and until something dispatched the pair the
        cells could only ever hold one call's numbers."""
        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            on=True,
            replies=(CALL_ONE_REPLY.read_bytes(), CALL_TWO_REPLY.read_bytes()),
        )

        assert served == 2 * len(run_plan.items), "the flag on is two calls an item"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        for summary in written:
            assert summary.call_1 is not None and summary.call_2 is not None
            assert summary.call_1.kind is CallKind.LABEL
            assert summary.call_2.kind is CallKind.SUMMARIZE_AND_PLAN

    def test_every_item_that_publishes_carries_a_decision(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The work stage decides the picture now, so the decision lands beside
        the summary rather than an hour later in another job on another model."""
        run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            on=True,
            replies=(CALL_ONE_REPLY.read_bytes(), CALL_TWO_REPLY.read_bytes()),
        )

        published = [
            item.item_id
            for item in run_plan.items
            if Summary.from_json(
                read_text(items / f"{item.item_id}.summary.json")
            ).status is SummaryStatus.OK
        ]
        assert published, "the recorded pair has to produce at least one publishable item"
        for item_id in published:
            decision = VisualDecision.from_json(read_text(items / f"{item_id}{PAYLOAD_SUFFIX}"))
            assert decision.item_id == item_id
            assert decision.asked_the_model, "call 2 was sent, whatever it answered"
            assert decision.decision_ms is not None

    def test_the_stamp_digests_the_two_prompts_instead(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The two calls render their own bytes, so the turn markers decide what
        the model reads and nothing else in the stamp reaches them. A marker edit
        would move every reply while the ledger said `unchanged`."""
        settings = two_call_settings(True)

        _run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            on=True,
            replies=(CALL_ONE_REPLY.read_bytes(), CALL_TWO_REPLY.read_bytes()),
        )

        stamped = only_stamp(items).inputs.prompt_sha256
        assert stamped == text_digest(
            calls.prompt_inputs(
                settings.app.summarize, inference=settings.app.models.summarize.inference
            )
        )
        assert stamped != text_digest(summarize.prompt_inputs(settings.app.summarize))

    def test_a_labelling_reply_this_build_cannot_read_loses_the_item_loudly(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Plan 11 row #3g's defect, made visible rather than fixed here. Call 2's
        prompt replays call 1's reply verbatim and the reason that is safe is
        that the reply has been held to a closed schema - so a reply that did not
        parse stops the item rather than being sent unchecked."""
        cut = json.loads(read_text(CALL_ONE_REPLY))
        cut["choices"][0]["message"]["content"] = '{"labels": [{"element_id": "quan'
        cut["choices"][0]["finish_reason"] = "length"

        run_plan, items, served = worked(
            tmp_path,
            monkeypatch,
            on=True,
            replies=(json.dumps(cut).encode("utf-8"),),
        )

        assert served == len(run_plan.items), "the second call is never sent"
        written = [
            Summary.from_json(read_text(items / f"{item.item_id}.summary.json"))
            for item in run_plan.items
        ]
        assert {summary.status for summary in written} == {SummaryStatus.FAILED}
        assert {summary.failure_code for summary in written} == {FailureCode.BAD_SHAPE}
        assert not list(items.glob(f"*{PAYLOAD_SUFFIX}")), "a lost item gets no decision"


class TestTheOldPlannerStandsDownWhenTheWorkStageDecided:
    def test_it_decides_nothing_and_overwrites_nothing(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Without this the separate job re-decides every item on the small model
        and overwrites a decision drawn from the article with one drawn from a
        summary of it - silently, because both payloads validate."""
        run_plan, items, _served = worked(
            tmp_path,
            monkeypatch,
            on=True,
            replies=(CALL_ONE_REPLY.read_bytes(), CALL_TWO_REPLY.read_bytes()),
        )
        before = {
            path.name: path.read_bytes() for path in sorted(items.glob(f"*{PAYLOAD_SUFFIX}"))
        }
        assert before, "the two-call path has to have written something to overwrite"

        cli.stage_visual_planner(run_plan, settings=two_call_settings(True))

        after = {path.name: path.read_bytes() for path in sorted(items.glob(f"*{PAYLOAD_SUFFIX}"))}
        assert after == before
