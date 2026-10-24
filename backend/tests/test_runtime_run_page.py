"""Does one bench dispatch's run page say what it ran and found, and escape what it did not write?"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from utilities import sweep_verdict
from utilities.runtime_run_page import main, render

#: item id -> (headline, summary text, source words or None when not recorded)
ARTICLES: Mapping[str, tuple[str, str, int | None]] = {
    "energy-0000000000": ("Energy headline", "Grid storage grew this year.", 900),
    "energy-0000000001": ("Water headline", "Reservoirs fell in May.", 420),
    "energy-0000000002": ("Trade headline", "Exports rose two percent.", None),
}


def _run(
    repeat: int,
    *,
    texts: Mapping[str, str] | None = None,
    headlines: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    chosen = {item: text for item, (_, text, _) in ARTICLES.items()} | dict(texts or {})
    names = {item: name for item, (name, _, _) in ARTICLES.items()} | dict(headlines or {})
    return {
        "label": "baseline",
        "repeat": repeat,
        "sources": {item: f"source-{item}" for item in ARTICLES},
        "digests": {item: f"digest-{chosen[item]}" for item in ARTICLES},
        "startup_ms": 4000 if repeat == 1 else 3800,
        "work_ms": 600_000,
        "total_ms": 604_000,
        "per_item": [
            {
                "item_id": item,
                "title": names[item],
                "summary": chosen[item],
                "source_url": f"https://example.test/{item}",
                "source_words": words,
                "summarize_ms": 60_000 + repeat * 1000,
            }
            for item, (_, _, words) in ARTICLES.items()
        ],
    }


def _summary(
    runs: list[dict[str, Any]],
    *,
    verdict: str = sweep_verdict.PASSED,
    problems: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "cases": ["baseline"],
        "reference": "baseline",
        "cpu": "AMD EPYC 9V74",
        "repeats": 2,
        "repeats_timed": len(runs),
        "gguf_cache_hit": "false",
        "verdict": verdict,
        "problems": problems or [],
        "results": runs,
    }


def _page(summary: Mapping[str, Any] | None) -> Any:
    return render(summary, candidate_id="candidate", models_file="models/x.json", speed_case="run")


def test_a_passing_run_names_its_configuration_articles_summaries_and_times() -> None:
    page = _page(_summary([_run(1), _run(2)]))

    assert page.annotations[0] == (
        "::notice title=Bench verdict::candidate: passed. 2 of 2 repeats timed, "
        "3 articles, cases baseline."
    )
    assert "Passed." in page.markdown
    assert "| Repeats per case | 2 requested, 2 timed |" in page.markdown
    assert "| llama-bench speed case | run |" in page.markdown
    assert "| A1 | Energy headline | <https://example.test/energy-0000000000> | 900 / 5 | " in (
        page.markdown
    )
    assert "| A3 | Trade headline | <https://example.test/energy-0000000002> | n/a / 4 |" in (
        page.markdown
    )
    assert "| yes |" in page.markdown
    assert "<summary>A2 - Water headline</summary>" in page.markdown
    assert "Reservoirs fell in May" in page.markdown


def test_a_hostile_headline_and_summary_are_escaped_and_never_reach_an_annotation() -> None:
    hostile_headline = "<img src=x onerror=alert(1)> | ![x](y)"
    hostile_summary = "Run `rm -rf /` now, then <script>alert(1)</script>."
    runs = [
        _run(
            repeat,
            texts={"energy-0000000000": hostile_summary},
            headlines={"energy-0000000000": hostile_headline},
        )
        for repeat in (1, 2)
    ]

    page = _page(_summary(runs))

    assert "<img" not in page.markdown
    assert "<script" not in page.markdown
    assert "&#60;img" in page.markdown
    assert "&#124;" in page.markdown
    assert "&#60;script&#62;" in page.markdown
    for annotation in page.annotations:
        assert "img" not in annotation
        assert "script" not in annotation
        assert "rm -rf" not in annotation


def test_output_drift_is_an_error_and_the_page_names_the_articles_that_differed() -> None:
    first = _run(1)
    second = _run(2, texts={"energy-0000000001": "A different sentence."})
    problem = {
        "why": sweep_verdict.REPEAT_OUTPUT_DRIFT,
        "label": "baseline",
        "repeat": 2,
        "expected": first["digests"],
        "actual": second["digests"],
    }

    page = _page(
        _summary([first, second], verdict=sweep_verdict.REJECTED_OUTPUT_DRIFT, problems=[problem])
    )

    assert page.annotations[0].startswith("::error title=Bench verdict::")
    assert sweep_verdict.REJECTED_OUTPUT_DRIFT in page.annotations[0]
    assert "::warning title=Summaries across repeats::2 of 3 articles" in page.annotations[1]
    assert "Rejected: repeats of one case wrote different summaries" in page.markdown
    assert "Its summaries differed from the first repeat" in page.markdown
    assert "Articles: A2." in page.markdown


def test_missing_word_counts_are_marked_unavailable_rather_than_zero() -> None:
    page = _page(_summary([_run(1), _run(2)]))

    assert "| n/a / 4 |" in page.markdown
    assert "| 0 / " not in page.markdown


def test_a_missing_summary_is_a_warning_and_the_page_still_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    page_path = tmp_path / "sweep" / "run-page.md"

    code = main(
        [
            "--summary",
            str(tmp_path / "missing.json"),
            "--page",
            str(page_path),
            "--candidate-id",
            "candidate",
            "--models-file",
            "models/x.json",
            "--speed-case",
            "run",
        ]
    )

    assert code == 0
    assert "No runtime summary was written" in page_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out.startswith("::warning title=Bench run::")


def test_the_program_reads_the_summary_the_sweep_wrote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    summary_path = tmp_path / "runtime-summary.json"
    summary_path.write_text(json.dumps(_summary([_run(1), _run(2)])), encoding="utf-8")
    page_path = tmp_path / "run-page.md"

    code = main(
        [
            "--summary",
            str(summary_path),
            "--page",
            str(page_path),
            "--candidate-id",
            "candidate",
            "--models-file",
            "models/x.json",
            "--speed-case",
            "skip",
        ]
    )

    assert code == 0
    page = page_path.read_text(encoding="utf-8")
    assert "| Repeats per case | 2 requested, 2 timed |" in page
    assert "| llama-bench speed case | skip |" in page
    assert capsys.readouterr().out.startswith("::notice title=Bench verdict::candidate: passed.")
