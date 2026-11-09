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
    save_settings,
)
from supervise_apis import start_apis, stop_apis, wait_for_apis
from write_reports import deliver_reports

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    event = json.load(sys.stdin)
    inputs = read_inputs(event, dict(os.environ))
    output = Path(os.environ["TEXT_ANALYSIS_OUTPUT_DIRECTORY"])
    summary = Path(os.environ["GITHUB_STEP_SUMMARY"])
    artifact_names = (
        os.environ["TEXT_ANALYSIS_SPACY_ARTIFACT"],
        os.environ["TEXT_ANALYSIS_GLINER_ARTIFACT"],
    )

    spacy = Outcome(error="The spaCy API did not become ready.")
    gliner = Outcome(error="The GLiNER API did not become ready.")
    cleanup_error: str | None = None
    process = None
    settings = None
    try:
        settings = save_settings(ROOT, output)
        labels = gliner_labels(settings)
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
    except (OSError, ValueError):
        cleanup_error = "The API configuration, process or native artifacts could not be prepared."
    finally:
        if process is not None and settings is not None:
            try:
                stop_apis(process, settings.listener)
            except (OSError, RuntimeError):
                cleanup_error = "The API process did not shut down cleanly."

    delivery_failed = deliver_reports(
        output,
        summary,
        inputs.text,
        artifact_names,
        spacy_error=spacy.error,
        gliner_error=gliner.error,
        process_error=cleanup_error,
    )
    return int(delivery_failed or spacy.incomplete)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        print("Text-analysis reporting failed; inspect the run configuration.", file=sys.stderr)
        raise SystemExit(1) from None
