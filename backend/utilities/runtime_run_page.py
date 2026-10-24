"""What one bench dispatch ran and found, as GitHub annotations and a run page.

The sweep writes `runtime-summary.json` whether it passed or was refused, so this
reads that one file and says it two ways: the verdict and its key numbers as
annotations on the run, and a page for the run summary. Nothing here is committed.
A missing summary is a warning on the page, and the program exits zero, because
the step that reports a failure must not turn it into a second failure (CLAUDE.md
section 1a).

Headlines and summaries are text this pipeline wrote from pages on the open web.
They are escaped before they reach the page and never reach an annotation, which
carries counts, identifiers and the verdict only (Guardrail #11).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from utilities import sweep_verdict

SUMMARY_PATH: Final = Path("backend/var/runtime-sweep/runtime-summary.json")
PAGE_PATH: Final = Path("backend/var/runtime-sweep/run-page.md")

#: Characters that would start markdown or HTML if they reached the page raw. They
#: are written as numeric references, which GitHub draws as the character itself.
_MARKUP: Final = frozenset("\\`*_{}[]()#+-.!|:=<>&\"'~")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+")
_HTTPS: Final = re.compile(r"https://[^\s<>|`]+")

#: Our own sentences. Nothing fetched is ever written into one.
VERDICT_SENTENCES: Final = {
    sweep_verdict.PASSED: "Passed.",
    sweep_verdict.REJECTED_INPUT_DRIFT: "Rejected: too few repeats read the same articles.",
    sweep_verdict.REJECTED_OUTPUT_DRIFT: (
        "Rejected: repeats of one case wrote different summaries for the same article."
    ),
}
PROBLEM_SENTENCES: Final = {
    sweep_verdict.INPUT_DRIFT_DROPPED: (
        "Article text changed during the run, so this repeat was dropped from the timings."
    ),
    sweep_verdict.REPEAT_OUTPUT_DRIFT: "Its summaries differed from the first repeat's.",
    sweep_verdict.TOO_FEW_AGREEING: "Too few repeats agreed on the articles they read.",
}
NO_SUMMARY: Final = (
    "No runtime summary was written, so this dispatch has no results. The job log says why."
)


@dataclass(frozen=True)
class RunPage:
    """What GitHub shows on the run as annotations, and what the run summary holds."""

    annotations: list[str]
    markdown: str


@dataclass(frozen=True)
class Article:
    """One article as the page reads it, from the repeats that read the same articles."""

    letter: str
    item_id: str
    headline: str
    source_url: str
    source_words: str
    summary_words: int
    median_seconds: float
    agreed: bool
    texts: tuple[tuple[int, str], ...]


def _text(value: object) -> str:
    """Untrusted text, escaped so GitHub draws it as written and runs none of it."""
    collapsed = _CONTROL.sub(" ", str(value)).strip()
    return "".join(f"&#{ord(char)};" if char in _MARKUP else char for char in collapsed)


def _link(value: str) -> str:
    """An https address as an autolink, anything else as escaped text."""
    return f"<{value}>" if _HTTPS.fullmatch(value) else _text(value)


def _command(value: str) -> str:
    """The escapes a workflow command needs in its message."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _annotation(level: str, title: str, message: str) -> str:
    """One workflow command, with the title escaped as a parameter."""
    parameter = _command(title).replace(":", "%3A").replace(",", "%2C")
    return f"::{level} title={parameter}::{_command(message)}"


def _seconds(milliseconds: Any) -> str:
    return f"{float(milliseconds) / 1000:,.1f} s"


def _comparable(runs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The repeats that read the same articles, which is the set sweep_verdict times."""
    if not runs:
        return []
    agreed, _ = Counter(sweep_verdict.input_key(run) for run in runs).most_common(1)[0]
    return [run for run in runs if sweep_verdict.input_key(run) == agreed]


def _articles(runs: Sequence[Mapping[str, Any]]) -> list[Article]:
    if not runs:
        return []
    lookups = [{entry["item_id"]: entry for entry in run["per_item"]} for run in runs]
    articles = []
    for number, item_id in enumerate(sorted(runs[0]["sources"]), start=1):
        entries = [lookup[item_id] for lookup in lookups]
        texts = tuple(
            (int(run["repeat"]), str(entry["summary"]))
            for run, entry in zip(runs, entries, strict=True)
        )
        agreed = len({run["digests"][item_id] for run in runs}) == 1
        first = entries[0]
        words = first.get("source_words")
        median_ms = statistics.median(float(entry["summarize_ms"]) for entry in entries)
        articles.append(
            Article(
                letter=f"A{number}",
                item_id=item_id,
                headline=str(first.get("title") or ""),
                source_url=str(first.get("source_url") or ""),
                source_words=f"{words:,}" if isinstance(words, int) else "n/a",
                summary_words=len(texts[0][1].split()),
                median_seconds=median_ms / 1000,
                agreed=agreed,
                texts=texts[:1] if agreed else texts,
            )
        )
    return articles


def _problem_rows(problems: Sequence[Mapping[str, Any]], letters: Mapping[str, str]) -> list[str]:
    rows = []
    for problem in problems:
        why = str(problem.get("why", ""))
        labels = problem.get("label") or ", ".join(problem.get("labels", []))
        detail = ""
        if why == sweep_verdict.REPEAT_OUTPUT_DRIFT:
            expected, actual = problem["expected"], problem["actual"]
            differing = [
                letters.get(item, item) for item in expected if expected[item] != actual.get(item)
            ]
            detail = f" Articles: {', '.join(differing)}."
        sentence = PROBLEM_SENTENCES.get(why, "See the job log.")
        repeat = problem.get("repeat", "")
        rows.append(f"| {why} | {labels} | {repeat} | {sentence}{detail} |")
    return rows


def render(
    summary: Mapping[str, Any] | None,
    *,
    candidate_id: str,
    models_file: str,
    speed_case: str,
) -> RunPage:
    """The annotations and the page for one dispatch. Reads no file."""
    heading = f"## Bench run: {_text(candidate_id)}"
    if summary is None:
        return RunPage(
            annotations=[_annotation("warning", "Bench run", NO_SUMMARY)],
            markdown="\n".join([heading, "", NO_SUMMARY, ""]),
        )

    runs = list(summary["results"])
    labels = [str(label) for label in summary["cases"]]
    verdict = str(summary["verdict"])
    timed = _comparable(runs)
    timed_keys = {(str(run["label"]), int(run["repeat"])) for run in timed}
    articles = _articles([run for run in timed if run["label"] == summary["reference"]])
    letters = {article.item_id: article.letter for article in articles}

    annotations = [
        _annotation(
            "notice" if verdict == sweep_verdict.PASSED else "error",
            "Bench verdict",
            f"{candidate_id}: {verdict}. {len(timed)} of {len(runs)} repeats timed, "
            f"{len(articles)} articles, cases {', '.join(labels)}.",
        )
    ]
    if articles:
        same = sum(article.agreed for article in articles)
        annotations.append(
            _annotation(
                "notice" if same == len(articles) else "warning",
                "Summaries across repeats",
                f"{same} of {len(articles)} articles summarized identically in every repeat.",
            )
        )
    if timed:
        first = min(runs, key=lambda run: int(run["repeat"]))
        median = statistics.median(
            float(entry["summarize_ms"]) for run in timed for entry in run["per_item"]
        )
        cold = _seconds(first["startup_ms"])
        server_minutes = sum(float(run["total_ms"]) for run in timed) / 60_000
        annotations.append(
            _annotation(
                "notice",
                "Time",
                f"Median summarize call {median / 1000:,.1f} s. Server time "
                f"{server_minutes:,.1f} min over {len(timed)} timed repeats. "
                f"Cold start {cold}.",
            )
        )

    lines = [
        heading,
        "",
        VERDICT_SENTENCES.get(verdict, "See the verdict in the job log."),
        "",
        "Each repeat starts a fresh server and summarizes the same articles, so the "
        "repeats show whether the model writes the same words twice.",
        "",
        "### Configuration",
        "",
        "| Setting | Value |",
        "| --- | --- |",
        f"| Candidate | {_text(candidate_id)} |",
        f"| Models file | {_text(models_file)} |",
        f"| Repeats per case | {summary['repeats']} requested, {summary['repeats_timed']} timed |",
        f"| Articles per repeat | {len(articles)} |",
        f"| Cases | {_text(', '.join(labels))} |",
        f"| llama-bench speed case | {_text(speed_case)} |",
        f"| Weights from cache | {'yes' if summary.get('gguf_cache_hit') == 'true' else 'no'} |",
        f"| Processor | {_text(summary.get('cpu', 'unrecorded'))} |",
        "",
        "### Articles",
        "",
        "| Id | Headline | Source | Words, source / summary | Summarize, median | "
        "Same wording every repeat |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for article in articles:
        lines.append(
            f"| {article.letter} | {_text(article.headline)} | {_link(article.source_url)} | "
            f"{article.source_words} / {article.summary_words:,} | "
            f"{article.median_seconds:,.1f} s | {'yes' if article.agreed else 'no'} |"
        )

    lines += ["", "### Summaries", ""]
    for article in articles:
        lines += [
            "<details>",
            f"<summary>{article.letter} - {_text(article.headline)}</summary>",
            "",
        ]
        for repeat, text in article.texts:
            prefix = "" if article.agreed else f"Repeat {repeat}: "
            lines += [f"{prefix}{_text(text)}", ""]
        lines += ["</details>", ""]

    problems = list(summary.get("problems", []))
    if problems:
        lines += [
            "### Problems",
            "",
            "| Why | Case | Repeat | What it means |",
            "| --- | --- | ---: | --- |",
            *_problem_rows(problems, letters),
            "",
        ]

    lines += [
        "### Timing",
        "",
        "| Case | Repeat | Timed | Startup | Work | Total |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for run in sorted(runs, key=lambda each: (str(each["label"]), int(each["repeat"]))):
        key = (str(run["label"]), int(run["repeat"]))
        timed_text = "yes" if key in timed_keys else "no"
        lines.append(
            f"| {_text(run['label'])} | {run['repeat']} | {timed_text} | "
            f"{_seconds(run['startup_ms'])} | {_seconds(run['work_ms'])} | "
            f"{_seconds(run['total_ms'])} |"
        )
    lines.append("")
    return RunPage(annotations=annotations, markdown="\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--page", type=Path, default=PAGE_PATH)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--models-file", required=True)
    parser.add_argument("--speed-case", required=True)
    args = parser.parse_args(argv)
    summary = (
        json.loads(args.summary.read_text(encoding="utf-8")) if args.summary.is_file() else None
    )
    page = render(
        summary,
        candidate_id=args.candidate_id,
        models_file=args.models_file,
        speed_case=args.speed_case,
    )
    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(page.markdown, encoding="utf-8", newline="\n")
    for line in page.annotations:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
