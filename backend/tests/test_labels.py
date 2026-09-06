"""The human faithfulness-label instrument.

Two things are asserted here that are not about correctness. One is that the
draw is deterministic, so a queue is reproducible instead of remembered. The
other is that the ledger is hard to fill with a machine - LLM-as-judge is a
project non-goal (`CLAUDE.md` section 0a), and a non-goal that is only
discouraged is not a control.

No mocks and no network (Rule #7). The draw runs over a ledger built here, not
over `state/`: measured 2026-09-06 the committed ledger held 6,966 rows over 15
days and grows by about 465 a day, and the tests below read and re-drew over all
of them eighteen times to establish six cases. The draw reads `hhem`,
`scorer_version` and `pipeline_fingerprint` and nothing else, so eighty built
rows carry every combination the tests name - including a short decile and a
second producer at one scorer, which are states the archive cannot be relied on
to hold.
"""

from __future__ import annotations

import ast
import contextlib
import io
import shutil
import sys
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.label_row import LabelRow, LabelTag
from idhazh.evals import labels, writer
from utilities import label_queue

#: A pair no run has ever written, so a draw for it is empty on any ledger.
NO_SUCH_PIPELINE = "0" * 64

#: The producers the built ledger carries. Two scorers, so an older one has a
#: pool to be excluded from; two pipelines at the live scorer, so a pooled draw
#: has a mix to report.
LIVE_SCORER: Final = "hhem-2.1-open@6a30c896;metrics-3;bands=0.80/0.50;lead=0.30"
OLD_SCORER: Final = "hhem-2.0-open@0f1e2d3c;metrics-2;bands=0.80/0.50;lead=0.30"
LIVE_PIPELINE: Final = "1" * 64
OTHER_PIPELINE: Final = "2" * 64

#: One more than `evaluation.label_draw_per_decile`, so a full decile proves the
#: draw stops at the cap.
FULL_DECILE_ROWS: Final = 7

#: Fewer than it, so the top decile proves the draw reports the shortfall rather
#: than borrowing from the decile below.
SHORT_DECILE_ROWS: Final = 3

#: Under the extraction floor, so one row proves a failed extraction stays in
#: the pool instead of being tidied out of the sample.
A_SHORT_SOURCE: Final = 40

#: Where the built ledger lives for the length of this module. A path rather
#: than the rows, because the operator tool reads files.
_WORLD: Path | None = None


def _band_of(hhem: float) -> ConfidenceBand:
    """The bands the scorer strings above declare: 0.80 and 0.50."""
    if hhem >= 0.80:
        return ConfidenceBand.HIGH
    if hhem >= 0.50:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def _an_eval_row(
    base: EvalRow, *, seq: int, decile: int, date: str, scorer: str, pipeline: str, words: int
) -> EvalRow:
    """One row at a chosen decile, distinct from every other row by address."""
    hhem = round(decile / 10 + 0.05, 2)
    return base.model_copy(
        update={
            "item_id": f"ai-{seq:04d}",
            "url_key": f"{seq:064x}",
            "output_digest": f"{seq + 1_000_000:064x}",
            "source_url": f"https://example.test/story/{seq:04d}",
            "title": f"Story {seq:04d}",
            "date": date,
            "run_id": f"{date}-1",
            "scored_at": f"{date}T06:00:00Z",
            "hhem": hhem,
            "hhem_full": hhem,
            "hhem_delta": 0.0,
            "band": _band_of(hhem),
            "scorer_version": scorer,
            "pipeline_fingerprint": pipeline,
            "source_seen_word_count": words,
            "source_word_count": max(words, 1320),
        }
    )


def _built_rows() -> list[EvalRow]:
    """Eighty rows, in the order the shards must hold them.

    `_live_scorer` reads the last row, so the live pair is written last and the
    two it has to be told apart from are written before it.
    """
    base = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    rows: list[EvalRow] = []
    seq = 0

    def add(*, decile: int, date: str, scorer: str, pipeline: str, words: int = 1320) -> None:
        nonlocal seq
        rows.append(
            _an_eval_row(
                base,
                seq=seq,
                decile=decile,
                date=date,
                scorer=scorer,
                pipeline=pipeline,
                words=words,
            )
        )
        seq += 1

    # A scorer that has been retired, on its own day.
    for decile in (0, 2, 4, 6, 8, 9):
        add(decile=decile, date="2026-08-20", scorer=OLD_SCORER, pipeline=LIVE_PIPELINE)

    # A second producer at the live scorer, so a pooled draw mixes two.
    for decile in range(8):
        add(decile=decile, date="2026-09-01", scorer=LIVE_SCORER, pipeline=OTHER_PIPELINE)

    # The live pair. Nine full deciles, one short one, and one failed extraction.
    for decile in range(9):
        for position in range(FULL_DECILE_ROWS):
            add(
                decile=decile,
                date="2026-09-02" if position % 2 == 0 else "2026-09-03",
                scorer=LIVE_SCORER,
                pipeline=LIVE_PIPELINE,
                words=A_SHORT_SOURCE if seq == 20 else 1320,
            )
    for _ in range(SHORT_DECILE_ROWS):
        add(decile=9, date="2026-09-03", scorer=LIVE_SCORER, pipeline=LIVE_PIPELINE)
    return rows


@pytest.fixture(scope="module", autouse=True)
def _the_built_world(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """One ledger and one config, built once and read by every test below."""
    global _WORLD
    root = tmp_path_factory.mktemp("label-world")
    shutil.copytree(CONFIG_DIR, root / "config")
    landed = writer.append(root / "state", _built_rows())
    assert landed == 80, f"the built ledger deduped down to {landed} rows"
    _WORLD = root
    yield
    _WORLD = None


@pytest.fixture(autouse=True)
def _the_tool_reads_the_built_world(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator tool locates its ledger off one constant, so this moves it."""
    monkeypatch.setattr(label_queue, "REPO_ROOT", world())


def world() -> Path:
    assert _WORLD is not None, "the built world is only there inside a test"
    return _WORLD


def ledger() -> list[dict[str, str]]:
    """Every built row, oldest month first - the population the tool reads.

    Read back through `writer.records` off real shards rather than handed over
    in memory, so a test sees the CSV spelling production sees and a column that
    stops round-tripping fails here.
    """
    return list(writer.records(world() / "state"))


def live_scorer(records: list[dict[str, str]]) -> str:
    return records[-1]["scorer_version"]


def live_pipeline(records: list[dict[str, str]]) -> str:
    return records[-1]["pipeline_fingerprint"]


def a_label(**overrides: object) -> LabelRow:
    payload: dict[str, object] = {
        "label_id": "a1b2c3d4e5f60718",
        "draw_id": "2026-08-24-decile-6",
        "url_key": "a" * 64,
        "source_url": "https://example.com/story",
        "date": "2026-08-24",
        "run_id": "2026-08-24-1",
        "output_digest": "b" * 64,
        "pipeline_fingerprint": "c" * 64,
        "summary_word_count": 90,
        "source_seen_word_count": 900,
        "scorer_version": "hhem-2.1-open@6a30c896;metrics-3;bands=0.80/0.50;lead=0.30",
        "hhem_at_label": 0.91,
        "band_at_label": "high",
        "verdict": "supported",
        "tag": "none",
        "labeller": "naveen",
        "labelled_at": "2026-08-24T12:00:00Z",
        "seconds_spent": 45,
    }
    payload.update(overrides)
    return LabelRow.model_validate(payload)


class TestTheDraw:
    def test_the_same_ledger_and_draw_id_give_the_same_queue(self) -> None:
        """Same rows and same order. Two labellers compare notes by position."""
        records = ledger()
        first = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        second = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        drawn = [row["label_id"] for row in first]
        assert drawn == [row["label_id"] for row in second]
        assert drawn == sorted(drawn), "the queue is not in its promised global key order"

    def test_a_different_draw_id_is_a_different_draw(self) -> None:
        records = ledger()
        first = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        second = labels.draw(
            records,
            draw_id="d2",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        assert {row["label_id"] for row in first} != {row["label_id"] for row in second}

    def test_an_older_scorer_is_not_in_the_pool(self) -> None:
        """A stratum computed across two instruments is not a stratum."""
        records = ledger()
        scorer = live_scorer(records)
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=scorer,
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        assert {row["scorer_version"] for row in drawn} == {scorer}

    def test_another_pipeline_is_not_in_the_pool(self) -> None:
        """A producer change is a covariate. Two producers are two samples."""
        records = ledger()
        pipeline = live_pipeline(records)
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=pipeline,
            per_decile=6,
        )
        assert drawn
        assert {row["pipeline_fingerprint"] for row in drawn} == {pipeline}

    def test_the_scorer_has_no_default_and_the_pipeline_does(self) -> None:
        """The scorer is the stratum being calibrated, so no call site may omit it.

        The pipeline is a covariate. Omitting it pools every producer one scorer
        read, which is the reachable rule - requiring both never once held for
        more than three consecutive run-days.
        """
        records = ledger()
        scorer = live_scorer(records)
        with pytest.raises(TypeError):
            labels.eligible(records)  # type: ignore[call-arg]

        pooled = labels.eligible(records, scorer_version=scorer)
        narrowed = labels.eligible(
            records, scorer_version=scorer, pipeline_fingerprint=live_pipeline(records)
        )
        assert pooled, "one scorer alone must select rows"
        assert len(narrowed) <= len(pooled), "naming a pipeline can only narrow"
        assert {row["scorer_version"] for row in pooled} == {scorer}

    def test_a_pooled_draw_reports_the_producers_it_mixed(self) -> None:
        """The trade Option B makes is only honest when the mix is printed.

        A rate over rows several producers wrote is a prior with wide bounds. The
        strata are what say so, so they are computed from the drawn rows rather
        than from the whole ledger.
        """
        records = ledger()
        pooled = labels.eligible(records, scorer_version=live_scorer(records))
        found = labels.strata(pooled)

        assert found, "a non-empty pool has at least one stratum"
        assert sum(one.rows for one in found) == len(pooled), "every row lands in exactly one"
        assert [one.rows for one in found] == sorted((one.rows for one in found), reverse=True)
        assert len({one.pipeline_fingerprint for one in found}) == len(found), "no duplicates"
        for one in found:
            assert one.first_date <= one.last_date

    def test_a_pair_no_run_wrote_draws_nothing(self) -> None:
        records = ledger()
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=NO_SUCH_PIPELINE,
            per_decile=6,
        )
        assert drawn == []

    def test_no_decile_gets_more_than_it_was_asked_for(self) -> None:
        records = ledger()
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        counts: dict[int, int] = {}
        for row in drawn:
            index = labels.decile_of(float(row["hhem"]))
            counts[index] = counts.get(index, 0) + 1
        assert counts and max(counts.values()) <= 6

    def test_a_short_decile_does_not_borrow_from_a_neighbour(self) -> None:
        """A stratum that quietly includes another stratum's rows is not that stratum."""
        records = ledger()
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        missing = labels.shortfalls(drawn, per_decile=6)
        assert len(drawn) == 60 - sum(missing.values())

    def test_the_queue_is_not_ordered_by_score(self) -> None:
        """A queue sorted by score leaks the gradient to the labeller."""
        records = ledger()
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        scores = [float(row["hhem"]) for row in drawn]
        assert scores != sorted(scores)
        assert scores != sorted(scores, reverse=True)

    def test_the_queue_is_not_emitted_one_decile_at_a_time(self) -> None:
        """The score is hidden; the stratum was not.

        A decile-blocked queue passes a monotonic-score check and still hands the
        labeller the confidence gradient in order, because every row of decile 0
        arrives before every row of decile 1. The test that bites counts runs of
        equal decile: blocked order gives exactly one run per decile, and a
        shuffled queue gives many more.
        """
        records = ledger()
        drawn = labels.draw(
            records,
            draw_id="d1",
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
            per_decile=6,
        )
        deciles = [labels.decile_of(float(row["hhem"])) for row in drawn]
        assert deciles != sorted(deciles), "the queue climbs decile by decile"
        runs = 1 + sum(1 for here, then in pairwise(deciles) if here != then)
        assert runs > len(set(deciles)), "the queue is still emitted one decile at a time"

    def test_a_top_score_lands_in_the_top_decile(self) -> None:
        assert labels.decile_of(1.0) == 9
        assert labels.decile_of(0.0) == 0
        assert labels.decile_of(0.8) == 8

    def test_short_source_rows_stay_in_the_pool(self) -> None:
        """Extraction failures are the sample, not noise to be tidied out of it."""
        records = ledger()
        pool = labels.eligible(
            records,
            scorer_version=live_scorer(records),
            pipeline_fingerprint=live_pipeline(records),
        )
        assert any(int(row["source_seen_word_count"]) < 50 for row in pool)


class TestWhatTheLedgerHolds:
    """The inventory a refusal prints, so an empty pool is a status report."""

    def test_every_pair_is_listed_with_its_rows_and_dates(self) -> None:
        records = ledger()
        found = labels.pairs(records)
        assert {(pair.scorer_version, pair.pipeline_fingerprint) for pair in found} == {
            (row["scorer_version"], row["pipeline_fingerprint"]) for row in records
        }
        assert sum(pair.rows for pair in found) == len(records)
        for pair in found:
            dates = [
                row["date"]
                for row in records
                if row["scorer_version"] == pair.scorer_version
                and row["pipeline_fingerprint"] == pair.pipeline_fingerprint
            ]
            assert (pair.rows, pair.first_date, pair.last_date) == (
                len(dates),
                min(dates),
                max(dates),
            )

    def test_the_pairs_come_back_oldest_first(self) -> None:
        found = labels.pairs(ledger())
        assert [pair.first_date for pair in found] == sorted(pair.first_date for pair in found)


class TestTheOperatorTool:
    def test_the_default_pool_is_every_pipeline_at_the_live_scorer(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Naming no pipeline is the normal case, and the report says so."""
        monkeypatch.setattr(sys, "argv", ["label_queue.py"])
        assert label_queue.main() == 0

        printed = capsys.readouterr().out
        assert "all at this scorer - reported, not filtered" in printed
        assert "eligible rows    0" not in printed

    def test_a_pooled_draw_names_every_producer_it_mixed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The pooled rate is only honest beside the mix that produced it."""
        monkeypatch.setattr(sys, "argv", ["label_queue.py"])
        label_queue.main()

        printed = capsys.readouterr().out
        records = ledger()
        evaluation = config.load(CONFIG_DIR).app.evaluation
        drawn = labels.draw(
            records,
            draw_id=f"{records[-1]['date']}-decile-{evaluation.label_draw_per_decile}",
            scorer_version=live_scorer(records),
            per_decile=evaluation.label_draw_per_decile,
        )
        for one in labels.strata(drawn):
            assert one.pipeline_fingerprint[:12] in printed, "every stratum is named"

    def test_an_empty_pool_exits_non_zero_and_says_what_the_ledger_holds(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence on an empty pool is what makes the gate invisible."""
        monkeypatch.setattr(
            sys, "argv", ["label_queue.py", "--pipeline-fingerprint", NO_SUCH_PIPELINE]
        )
        assert label_queue.main() != 0

        printed = capsys.readouterr().out
        assert "eligible rows    0" in printed
        assert NO_SUCH_PIPELINE in printed
        for pair in labels.pairs(ledger()):
            assert pair.scorer_version in printed
            assert pair.pipeline_fingerprint in printed
            assert f"{pair.rows} rows, {pair.first_date} to {pair.last_date}" in printed

    def test_an_empty_pool_draws_nothing_at_all(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No fallback and no widening: a draw from a pair nobody asked for is not a draw."""
        monkeypatch.setattr(
            sys, "argv", ["label_queue.py", "--pipeline-fingerprint", NO_SUCH_PIPELINE]
        )
        label_queue.main()
        printed = capsys.readouterr().out
        assert "drawn            " not in printed
        assert "NOT YET RECALIBRATABLE" not in printed


class TestTheRow:
    def test_a_supported_summary_carries_no_defect_tag(self) -> None:
        with pytest.raises(ValidationError):
            a_label(verdict="supported", tag="invented_fact")

    def test_an_unsupported_summary_must_name_the_defect(self) -> None:
        with pytest.raises(ValidationError):
            a_label(verdict="unsupported", tag="none")

    def test_a_label_needs_a_human_name(self) -> None:
        with pytest.raises(ValidationError):
            a_label(labeller="")

    def test_the_row_has_nowhere_to_put_a_machine_verdict(self) -> None:
        """The structural control, not the discouragement.

        There is no author field a model could fill and no nullable one it could
        leave blank. Putting a model in this ledger means a schema change with a
        written reason and a Level 5 consultation.
        """
        fields = set(LabelRow.model_fields)
        assert "model_id" not in fields
        assert LabelRow.model_fields["labeller"].is_required()
        with pytest.raises(ValidationError):
            LabelRow.model_validate({**a_label().model_dump(mode="json"), "model_id": "qwen3-8b"})

    def test_a_label_takes_time(self) -> None:
        with pytest.raises(ValidationError):
            a_label(seconds_spent=0)

    def test_the_row_carries_the_counterweights_its_tags_are_measured_against(self) -> None:
        """A label outlives the score row it was drawn from, so it copies these three.

        `state/scores/` keeps `observability.scores_full_grain_months` months of
        item-level rows. Re-joining on `output_digest` stops working the day
        that month is archived, and the three counterweights the tag vocabulary
        mirrors are exactly what would be lost - which is the precision and
        recall the sixty labels are drawn to buy.
        """
        mirrored = {
            "wrong_number": "unsupported_numbers",
            "overstated": "hedge_dropped",
            "not_the_article": "extraction_suspect",
        }
        fields = set(LabelRow.model_fields)

        assert set(mirrored.values()) <= fields
        for tag in mirrored:
            assert tag in {member.value for member in LabelTag}
        row = a_label(unsupported_numbers=2, hedge_dropped=True, extraction_suspect=False)
        assert row.unsupported_numbers == 2
        assert row.hedge_dropped is True
        assert row.extraction_suspect is False

    def test_a_row_written_before_the_counterweights_reads_as_unrecorded(self) -> None:
        """Null means re-join from the ledger, and False would mean it did not fire.

        The read migration for 2026-09-03. `state/labels.csv` has never been
        written, so no row is migrated - but a header written before those
        columns still has to parse, because the alternative is a ledger the
        build cannot open (`CLAUDE.md` section 11).
        """
        old = a_label(version="2026-08-27")
        assert old.unsupported_numbers is None
        assert old.hedge_dropped is None
        assert old.extraction_suspect is None

        cells = old.csv_row()
        for name in ("unsupported_numbers", "hedge_dropped", "extraction_suspect"):
            assert cells[name] == "", "an absent optional is an empty cell, not the word None"
            del cells[name]
        assert LabelRow.from_csv_row(cells) == old

    def test_a_row_written_after_them_round_trips_through_the_file(self) -> None:
        row = a_label(unsupported_numbers=0, hedge_dropped=False, extraction_suspect=True)

        assert LabelRow.from_csv_row(row.csv_row()) == row


class TestTheLedger:
    def test_the_same_person_cannot_label_one_row_twice(self, tmp_path: Path) -> None:
        path = tmp_path / "labels.csv"
        assert labels.append(path, [a_label()]) == 1
        assert labels.append(path, [a_label()]) == 0

    def test_a_second_labeller_on_one_row_is_kept(self, tmp_path: Path) -> None:
        """Two people disagreeing is signal. That is the whole overlap design."""
        path = tmp_path / "labels.csv"
        labels.append(path, [a_label(labeller="naveen")])
        assert labels.append(path, [a_label(labeller="alex")]) == 1

    def test_the_header_matches_the_contract(self, tmp_path: Path) -> None:
        path = tmp_path / "labels.csv"
        labels.append(path, [a_label()])
        assert labels.read_header(path) == LabelRow.csv_columns()

    def test_the_committed_config_names_no_labeller_yet(self) -> None:
        """A fresh clone can draw the queue and read it, and cannot record a verdict."""
        settings = config.load(CONFIG_DIR)
        assert settings.app.evaluation.label_draw_per_decile == 6
        assert settings.app.evaluation.label_min_run_days == 10


class TestTheLoopStaysOpen:
    def test_the_draw_never_imports_a_model(self) -> None:
        """The analysis takes labels as ground truth and scores as the thing measured.

        A dependency assertion survives a refactor by somebody who never read the
        docstring saying so.
        """
        tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "evals" / "labels.py"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("idhazh.llm"), f"labels.py imports {name}"
                assert "hhem" not in name, f"labels.py imports {name}"

    def test_the_operator_tool_offers_no_bulk_path(self) -> None:
        """No `--from-file`, no `--model`, no stdin. One prompt writes one row."""
        source = read_text(REPO_ROOT / "backend" / "utilities" / "label_queue.py")
        for forbidden in ('"--from-file"', '"--model"', "sys.stdin", "readlines("):
            assert forbidden not in source, f"label_queue.py offers {forbidden}"

    def test_the_queue_fills_the_counterweights_rather_than_leaving_them_to_a_re_join(
        self,
    ) -> None:
        """The only writer of this ledger has to copy them, or the column is dead.

        A nullable column nothing fills is a column that reads as unrecorded on
        every row ever written, which is worse than no column - it looks like a
        measurement somebody could take. Read off the syntax tree, so a
        refactor that drops a key fails here rather than in 2027.
        """
        tree = ast.parse(read_text(REPO_ROOT / "backend" / "utilities" / "label_queue.py"))
        filled: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if not isinstance(target, ast.Attribute) or target.attr != "model_validate":
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != "LabelRow":
                continue
            for argument in node.args:
                if isinstance(argument, ast.Dict):
                    filled |= {
                        key.value
                        for key in argument.keys
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }

        assert {"unsupported_numbers", "hedge_dropped", "extraction_suspect"} <= filled
        assert filled == set(LabelRow.model_fields) - {"version"}, (
            "the queue fills every column but the schema stamp, which defaults"
        )

    def test_the_queue_says_which_months_a_draw_can_no_longer_reach(self) -> None:
        """A row count gives no hint that a month was ever there.

        `state/scores/` becomes a summary past
        `observability.scores_full_grain_months`, and a summary holds no row to
        label. The report names those months rather than leaving the operator to
        infer them from a shortfall.
        """
        printed: list[str] = []
        records = ledger()
        settings = config.load(CONFIG_DIR)
        scorer = live_scorer(records)
        queue = labels.draw(
            records,
            draw_id="d1",
            scorer_version=scorer,
            pipeline_fingerprint=None,
            per_decile=settings.app.evaluation.label_draw_per_decile,
        )

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            label_queue.report(
                queue,
                records,
                settings,
                scorer=scorer,
                pipeline=None,
                archived=["2025-11", "2025-12"],
            )
        printed = captured.getvalue().splitlines()

        assert any("aged out" in line and "2025-11, 2025-12" in line for line in printed)
