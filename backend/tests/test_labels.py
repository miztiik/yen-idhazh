"""The human faithfulness-label instrument.

Two things are asserted here that are not about correctness. One is that the
draw is deterministic, so a queue is reproducible instead of remembered. The
other is that the ledger is hard to fill with a machine - LLM-as-judge is a
project non-goal (`CLAUDE.md` section 0a), and a non-goal that is only
discouraged is not a control.

No mocks and no network (Rule #7): the draw runs over the committed ledger.
"""

from __future__ import annotations

import ast
import sys
from itertools import pairwise
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, STATE_DIR, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.label_row import LabelRow
from idhazh.evals import labels, writer
from utilities import label_queue

#: A pair no run has ever written, so a draw for it is empty on any ledger.
NO_SUCH_PIPELINE = "0" * 64


def ledger() -> list[dict[str, str]]:
    """Every committed row, oldest month first - the population the tool reads.

    A month is a shard boundary and nothing else, so a helper that names one
    file stops agreeing with `label_queue` about what the ledger holds on the
    first of every month. The disagreement lands in the inventory the tool
    prints for an empty pool, which is the one screen an operator reads to tell
    a gate one run-day away from a gate that is unreachable.
    """
    return list(writer.records(STATE_DIR))


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
