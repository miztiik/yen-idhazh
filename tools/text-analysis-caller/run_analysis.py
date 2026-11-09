"""How does a manual run collect and publish both providers' results?"""

import json
import os
import sys
from pathlib import Path

import httpx
from collect_results import (
    Outcome,
    collect_gliner,
    collect_spacy,
    gliner_labels,
    read_inputs,
    write_atomic,
)
from render_report import render_gliner_results, render_report, render_spacy_results
from supervise_apis import start_apis, stop_apis, wait_for_apis
from text_analysis.load_service_settings import load_service_settings

ROOT = Path(__file__).resolve().parents[2]
# GitHub rejects a step summary larger than one MiB.
SUMMARY_MAX_BYTES = 1_048_576


def main() -> int:
    event = json.load(sys.stdin)
    inputs = read_inputs(event, dict(os.environ))
    settings = load_service_settings(ROOT)
    labels = gliner_labels(settings)
    output = Path(os.environ["TEXT_ANALYSIS_OUTPUT_DIRECTORY"])
    summary = Path(os.environ["GITHUB_STEP_SUMMARY"])

    spacy = Outcome(error="The spaCy API did not become ready.")
    gliner = Outcome(error="The GLiNER API did not become ready.")
    cleanup_error: str | None = None
    process = None
    try:
        process = start_apis(ROOT)
        spacy_health, gliner_health = wait_for_apis(process, settings.listener)
        timeout = settings.listener.body_read_timeout_ms / 1000
        with httpx.Client(
            base_url=f"http://{settings.listener.host}:{settings.listener.port}",
            timeout=httpx.Timeout(connect=timeout, read=None, write=timeout, pool=timeout),
            trust_env=False,
        ) as client:
            if spacy_health is not None:
                spacy = collect_spacy(client, inputs, spacy_health, output)
            if gliner_health is not None:
                gliner = collect_gliner(client, inputs, labels, output)
    except OSError:
        cleanup_error = "The API process or result artifacts could not be opened."
    finally:
        if process is not None:
            try:
                stop_apis(process, settings.listener)
            except (OSError, RuntimeError):
                cleanup_error = "The API process did not shut down cleanly."

    try:
        render_spacy_results(inputs.text, spacy.result, spacy_error=spacy.error)
    except ValueError:
        spacy = Outcome(error="The spaCy response could not be rendered.")
    try:
        render_gliner_results(
            inputs.text, gliner.result, gliner_error=gliner.error, gliner_labels=labels
        )
    except ValueError:
        gliner = Outcome(error="The GLiNER response could not be rendered.")

    report = render_report(
        inputs.text,
        spacy.result,
        gliner.result,
        spacy_error=spacy.error,
        gliner_error=gliner.error,
        gliner_labels=labels,
    )
    if cleanup_error:
        report += "\n\n**Process error:** " + cleanup_error + "\n"
    content = report.encode("utf-8")
    write_atomic(output / "report.md", content)
    if len(content) > SUMMARY_MAX_BYTES:
        summary.write_text(
            "The complete analysis report exceeds the GitHub summary size limit. "
            "Download `report.md` from the analysis results artifact.\n",
            encoding="utf-8",
        )
        return 1
    with summary.open("a", encoding="utf-8") as destination:
        destination.write(report)
    return int(bool(spacy.error or spacy.incomplete or gliner.error or cleanup_error))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        print("Text-analysis reporting failed; inspect the run configuration.", file=sys.stderr)
        raise SystemExit(1) from None
