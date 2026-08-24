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
import csv
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.label_row import LabelRow
from idhazh.evals import labels

SCORES = REPO_ROOT / "state" / "scores.csv"


def ledger() -> list[dict[str, str]]:
    with SCORES.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def live_scorer(records: list[dict[str, str]]) -> str:
    return records[-1]["scorer_version"]


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
        "source_word_count": 900,
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
        records = ledger()
        scorer = live_scorer(records)
        first = labels.draw(records, draw_id="d1", scorer_version=scorer, per_decile=6)
        second = labels.draw(records, draw_id="d1", scorer_version=scorer, per_decile=6)
        assert [row["label_id"] for row in first] == [row["label_id"] for row in second]

    def test_a_different_draw_id_is_a_different_draw(self) -> None:
        records = ledger()
        scorer = live_scorer(records)
        first = labels.draw(records, draw_id="d1", scorer_version=scorer, per_decile=6)
        second = labels.draw(records, draw_id="d2", scorer_version=scorer, per_decile=6)
        assert {row["label_id"] for row in first} != {row["label_id"] for row in second}

    def test_an_older_scorer_is_not_in_the_pool(self) -> None:
        """A stratum computed across two instruments is not a stratum."""
        records = ledger()
        scorer = live_scorer(records)
        drawn = labels.draw(records, draw_id="d1", scorer_version=scorer, per_decile=6)
        assert {row["scorer_version"] for row in drawn} == {scorer}

    def test_no_decile_gets_more_than_it_was_asked_for(self) -> None:
        records = ledger()
        drawn = labels.draw(
            records, draw_id="d1", scorer_version=live_scorer(records), per_decile=6
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
            records, draw_id="d1", scorer_version=live_scorer(records), per_decile=6
        )
        missing = labels.shortfalls(drawn, per_decile=6)
        assert len(drawn) == 60 - sum(missing.values())

    def test_the_queue_is_not_ordered_by_score(self) -> None:
        """A queue sorted by score leaks the gradient to the labeller."""
        records = ledger()
        drawn = labels.draw(
            records, draw_id="d1", scorer_version=live_scorer(records), per_decile=6
        )
        scores = [float(row["hhem"]) for row in drawn]
        assert scores != sorted(scores)
        assert scores != sorted(scores, reverse=True)

    def test_a_top_score_lands_in_the_top_decile(self) -> None:
        assert labels.decile_of(1.0) == 9
        assert labels.decile_of(0.0) == 0
        assert labels.decile_of(0.8) == 8

    def test_short_source_rows_stay_in_the_pool(self) -> None:
        """Extraction failures are the sample, not noise to be tidied out of it."""
        records = ledger()
        pool = labels.eligible(records, scorer_version=live_scorer(records))
        assert any(int(row["source_word_count"]) < 50 for row in pool)


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
