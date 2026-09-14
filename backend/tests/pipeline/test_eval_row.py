"""Does an eval row carry everything needed to read it years from now?"""

from __future__ import annotations

import ast

import pytest
from conftest import REPO_ROOT, read_text

from idhazh import extract
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.knobs.extract import ExtractConfig
from idhazh.evals import metrics
from idhazh.evals.score import to_eval_row
from idhazh.fetch import FetchResult
from idhazh.fingerprint import text_digest

from ._builders import (
    FULL_TEXT,
    article,
    plan,
    row,
    summary,
)

pytestmark = pytest.mark.slow


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
    tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "stages" / "work.py"))
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
    tree = ast.parse(read_text(REPO_ROOT / "backend" / "idhazh" / "stages" / "work.py"))
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
