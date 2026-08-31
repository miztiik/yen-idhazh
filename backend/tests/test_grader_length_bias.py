"""The window-geometry comparison: its arithmetic, its control, and how it refuses.

The tool reads whether the faithfulness scorer over-scores or under-scores a
long article, by scoring the same (premise, summary) pair at today's window
geometry and again at a window wide enough to hold the whole premise. Nothing
here needs the real scorer or a real premise: the question is whether the
harness can be trusted with one.

**The load-bearing test is the control.** An item that is a single window under
both geometries is scored over the identical text twice, so its difference must
be exactly zero. Every other row of the report is unreadable until that one
holds, and it must not be able to pass by returning zero everywhere - so the
same run asserts that a multi-window item does move.

No mocks and no network (Rule #7). The two scorers below are real
implementations of the `Scorer` protocol: pure functions of the two texts, which
is what makes their answers predictable enough to check arithmetic against.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.evidence import EvidenceItem
from idhazh.evals import evidence as evidence_writer
from utilities import grader_length_bias as bias

EVIDENCE_FIXTURE = CONTRACT_FIXTURES_DIR / "evidence-item" / "premise-recorded.json"
ROW_FIXTURE = CONTRACT_FIXTURES_DIR / "eval-row" / "premise-recorded.json"

NARROW = EvaluationConfig()
SUMMARY = "the plant closes and the ministry confirmed it"


def a_premise(words: int, *, supporting: str = SUMMARY) -> str:
    """`words` words of filler with the summary's words planted at the very end.

    The plant is at the end on purpose. Under a narrow geometry only the last
    window holds it, which is what makes the two scorers below disagree about
    the direction the geometry pushes the score.
    """
    filler = [f"w{n}" for n in range(max(words - len(supporting.split()), 0))]
    return " ".join([*filler, *supporting.split()])


def an_item(premise: str, summary: str, *, name: str) -> EvidenceItem:
    """A real `EvidenceItem` on the committed fixture's identity, with the texts swapped."""
    payload = json.loads(read_text(EVIDENCE_FIXTURE))
    payload["premise"] = premise
    payload["summary"] = summary
    payload["source_digest"] = derive_text_digest(premise)
    payload["output_digest"] = derive_text_digest(name)
    return EvidenceItem.model_validate(payload)


def a_package(directory: Path, items: list[EvidenceItem]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for item in items:
        path = evidence_writer.path_for(directory, item)
        path.write_text(item.to_json(), encoding="utf-8", newline="\n")
    return directory


def a_ledger(state: Path, rows: list[dict[str, object]]) -> Path:
    """The real ledger shape and the real layout: a state directory of shards."""
    names = EvalRow.csv_columns()
    path = state / "scores" / f"{rows[0]['date'] if rows else '2026-08-22'}"[:7]
    path = path.with_suffix(".csv") if path.suffix else Path(f"{path}.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in names})
    return state


def a_ledger_row(
    item: EvidenceItem, *, full_words: int | None, seen_words: int
) -> dict[str, object]:
    payload = EvalRow.from_json(read_text(ROW_FIXTURE)).model_dump(mode="json")
    payload["url_key"] = item.url_key
    payload["pipeline_fingerprint"] = item.pipeline_fingerprint
    payload["output_digest"] = item.output_digest
    payload["scorer_version"] = item.scorer_version
    payload["source_word_count"] = "" if full_words is None else full_words
    payload["source_seen_word_count"] = seen_words
    return payload


class SupportDensity:
    """Higher when the supporting words are a bigger share of the premise.

    This is the best-of-N direction in its simplest honest form: a window
    holding the supporting sentence and little else scores better than the whole
    article holding the same sentence among everything that does not support it.
    The aggregation is a max, so more windows means more chances to draw the
    concentrated one.
    """

    def score(self, premise: str, hypothesis: str) -> float:
        words = premise.split()
        if not words:
            return 0.0
        wanted = set(hypothesis.split())
        return sum(1 for word in words if word in wanted) / len(words)


class SummaryCoverage:
    """Higher when more of the summary is supported by the premise in front of it.

    This is the mark-down-for-depth direction: a summary drawing on two ends of
    an article has no single window supporting all of it, so every window is
    marked down for the half it cannot see, and the whole premise is not.
    """

    def score(self, premise: str, hypothesis: str) -> float:
        wanted = hypothesis.split()
        if not wanted:
            return 0.0
        held = set(premise.split())
        return sum(1 for word in wanted if word in held) / len(wanted)


class TestTheHarnessRefusesRatherThanReportingZero:
    def test_a_missing_package_raises_and_names_the_path(self, tmp_path: Path) -> None:
        """A directory that was never downloaded is not a corpus of zero difference."""
        missing = tmp_path / "never-downloaded"

        with pytest.raises(bias.NoEvidenceError) as raised:
            bias.load_pairs(missing, tmp_path)

        assert "never-downloaded" in str(raised.value)

    def test_an_empty_package_raises_and_says_how_to_fill_it(self, tmp_path: Path) -> None:
        """The pairs are gitignored, so the message has to name the command that gets them."""
        (tmp_path / "evidence-0").mkdir()

        with pytest.raises(bias.NoEvidenceError) as raised:
            bias.load_pairs(tmp_path, tmp_path)

        assert "gh run download" in str(raised.value)

    def test_a_missing_ledger_leaves_the_cut_unknown_rather_than_false(
        self, tmp_path: Path
    ) -> None:
        """Saying an article was not cut is a claim. A tool with no ledger has not made it."""
        a_package(tmp_path, [an_item(a_premise(50), SUMMARY, name="one")])

        (pair,) = bias.load_pairs(tmp_path, tmp_path / "absent.csv")

        assert pair.cut is None


class TestTheControl:
    def test_a_one_slice_item_reads_exactly_zero(self, tmp_path: Path) -> None:
        """The same text scored twice by a deterministic scorer cannot differ.

        Not `approx`. Both geometries hand `chunks()` a premise shorter than the
        window, so both passes score the identical string, and any difference at
        all means the harness compared two different things.
        """
        a_package(tmp_path, [an_item(a_premise(50), SUMMARY, name="short")])
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)

        readings = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)

        assert [r.slices for r in readings] == [1]
        assert readings[0].delta == 0.0

    def test_the_control_is_not_a_scorer_that_always_agrees_with_itself(
        self, tmp_path: Path
    ) -> None:
        """A zero everywhere would pass the control and prove nothing.

        The same scorer, the same run: the one-slice item reads exactly zero and
        the three-slice item does not. That is the difference between an
        instrument that is sound and one that is stuck.
        """
        a_package(
            tmp_path,
            [
                an_item(a_premise(50), SUMMARY, name="short"),
                an_item(a_premise(2000), SUMMARY, name="long"),
            ],
        )
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)

        scored = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)
        readings = {reading.slices: reading.delta for reading in scored}

        assert readings[1] == 0.0
        assert readings[3] != 0.0

    def test_the_wide_geometry_puts_every_item_on_one_slice(self, tmp_path: Path) -> None:
        """Derived from the corpus. A window narrower than the longest premise is not a control."""
        a_package(
            tmp_path,
            [
                an_item(a_premise(50), SUMMARY, name="short"),
                an_item(a_premise(2000), SUMMARY, name="long"),
            ],
        )
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")

        wide = bias.single_slice_geometry(pairs, NARROW)

        assert wide.chunk_words == 2000
        assert [bias.slices_under(pair.premise, wide) for pair in pairs] == [1, 1]


class TestTheTwoDirectionsAreDistinguishable:
    def test_best_of_n_over_scoring_reads_positive(self, tmp_path: Path) -> None:
        """More windows is more draws, and the concentrated draw wins the max."""
        a_package(tmp_path, [an_item(a_premise(2000), SUMMARY, name="long")])
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)

        (reading,) = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)

        assert reading.delta > 0.0

    def test_the_mark_down_for_depth_reads_negative(self, tmp_path: Path) -> None:
        """No single window supports the whole summary, so every window is marked down."""
        premise = "the plant closes " + " ".join(f"w{n}" for n in range(2000))
        premise = premise + " and the ministry confirmed it"
        a_package(tmp_path, [an_item(premise, SUMMARY, name="split")])
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)

        (reading,) = bias.read(SummaryCoverage(), pairs, narrow=NARROW, wide=wide)

        assert reading.delta < 0.0


class TestTheCutSplitReadsTheArithmetic:
    def test_a_row_whose_seen_length_is_short_of_its_full_length_was_cut(
        self, tmp_path: Path
    ) -> None:
        """`truncation_flagged` changed meaning on 2026-08-28. The two counters did not."""
        cut = an_item(a_premise(50), SUMMARY, name="cut")
        whole = an_item(a_premise(60), SUMMARY, name="whole")
        a_package(tmp_path, [cut, whole])
        ledger = a_ledger(
            tmp_path,
            [
                a_ledger_row(cut, full_words=4000, seen_words=1923),
                a_ledger_row(whole, full_words=600, seen_words=600),
            ],
        )

        by_key = {pair.key: pair.cut for pair in bias.load_pairs(tmp_path, ledger)}

        assert by_key[evidence_writer.key_of(cut.model_dump(mode="json"))] is True
        assert by_key[evidence_writer.key_of(whole.model_dump(mode="json"))] is False

    def test_a_row_with_no_pre_cap_length_is_unknown_not_uncut(self, tmp_path: Path) -> None:
        """The migration emptied 142 rows rather than guessing. An empty cell is not a False."""
        item = an_item(a_premise(50), SUMMARY, name="emptied")
        a_package(tmp_path, [item])
        ledger = a_ledger(
            tmp_path, [a_ledger_row(item, full_words=None, seen_words=1923)]
        )

        (pair,) = bias.load_pairs(tmp_path, ledger)

        assert pair.cut is None


class TestTheReport:
    def test_the_operator_output_is_stable(self, tmp_path: Path) -> None:
        """A report an operator copies into a doc has to read the same twice."""
        items = [
            an_item(a_premise(50), SUMMARY, name="short"),
            an_item(a_premise(2000), SUMMARY, name="long"),
        ]
        a_package(tmp_path, items)
        ledger = a_ledger(
            tmp_path,
            [
                a_ledger_row(items[0], full_words=50, seen_words=50),
                a_ledger_row(items[1], full_words=4000, seen_words=1923),
            ],
        )
        pairs = bias.load_pairs(tmp_path, ledger)
        wide = bias.single_slice_geometry(pairs, NARROW)
        readings = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)

        report = bias.summarise(readings, narrow=NARROW, wide_words=wide.chunk_words)
        lines = bias.lines_for(report)

        assert lines[:3] == [
            "geometry now: 900/150 anchored",
            "geometry wide: 2000 words, every item one slice",
            "today's score minus the single-slice score, by slice count:",
        ]
        assert [group.label for group in report.by_slices] == ["1 slice", "3 slices"]
        assert [(group.label, group.n) for group in report.by_cut] == [
            ("article was cut", 1),
            ("article was not cut", 1),
        ]

    def test_a_group_of_one_has_no_spread_rather_than_a_crash(self, tmp_path: Path) -> None:
        """Rule #10 wants a spread beside every mean. One reading's spread is zero, not an error."""
        a_package(tmp_path, [an_item(a_premise(50), SUMMARY, name="alone")])
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)
        readings = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)

        report = bias.summarise(readings, narrow=NARROW, wide_words=wide.chunk_words)

        assert report.by_slices[0].n == 1
        assert report.by_slices[0].stdev == 0.0

    def test_every_pass_is_timed_so_the_cost_half_is_answerable(self, tmp_path: Path) -> None:
        """Carmack's half of the row: whether a one-slice window is affordable at all."""
        a_package(tmp_path, [an_item(a_premise(2000), SUMMARY, name="long")])
        pairs = bias.load_pairs(tmp_path, tmp_path / "absent.csv")
        wide = bias.single_slice_geometry(pairs, NARROW)
        readings = bias.read(SupportDensity(), pairs, narrow=NARROW, wide=wide)

        report = bias.summarise(readings, narrow=NARROW, wide_words=wide.chunk_words)

        assert report.narrow_seconds_per_pass.n == 1
        assert report.wide_seconds_per_pass.n == 1
        assert report.narrow_seconds_per_pass.mean >= 0.0
