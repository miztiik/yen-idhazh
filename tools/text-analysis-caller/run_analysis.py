"""How does a manual run collect and publish both providers' results?"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from capture_events import ApiEventCapture
from collect_classifications import collect_classifications
from collect_operations import Outcome, collect_gliner_operations
from collect_results import (
    collect_gliner,
    collect_spacy,
    read_inputs,
    save_settings,
)
from supervise_apis import EXIT_GRACE_SECONDS, start_apis, stop_apis, wait_for_apis
from write_reports import deliver_reports

ROOT = Path(__file__).resolve().parents[2]


async def main() -> int:
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
    classification = Outcome(error="The GLiNER API did not become ready for classification.")
    process_errors: list[str] = []
    process = None
    settings = None
    capture = None
    try:
        settings = save_settings(ROOT, output)
        capture = ApiEventCapture(output, sys.stderr.buffer)
        process = start_apis(ROOT)
        capture.start(process.stderr)
        spacy_health, gliner_health = await asyncio.to_thread(
            wait_for_apis, process, settings.listener
        )
        timeout = settings.listener.body_read_timeout_ms / 1000
        async with httpx.AsyncClient(
            base_url=f"http://{settings.listener.host}:{settings.listener.port}",
            timeout=httpx.Timeout(connect=timeout, read=None, write=timeout, pool=timeout),
            trust_env=False,
        ) as client:
            if spacy_health is not None:
                spacy = await collect_spacy(client, inputs, spacy_health, output)
            if gliner_health is not None:
                gliner, classification = await collect_gliner_operations(
                    collect_gliner(client, inputs, settings, output),
                    collect_classifications(client, inputs, ROOT, output),
                )
    except (OSError, ValueError):
        process_errors.append(
            "The API configuration, process or native artifacts could not be prepared."
        )
    finally:
        if process is not None and settings is not None:
            try:
                await asyncio.to_thread(stop_apis, process, settings.listener)
            except (OSError, RuntimeError):
                process_errors.append("The API process did not shut down cleanly.")
        if capture is not None:
            capture_error = await capture.finish(EXIT_GRACE_SECONDS)
            if capture_error is not None:
                process_errors.append(capture_error)

    delivery_failed = deliver_reports(
        output,
        summary,
        inputs.text,
        artifact_names,
        spacy_error=spacy.error,
        gliner_error=gliner.error,
        classification_error=classification.error,
        process_error=" ".join(process_errors) or None,
    )
    return int(delivery_failed or spacy.incomplete)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        print("Text-analysis reporting failed; inspect the run configuration.", file=sys.stderr)
        raise SystemExit(1) from None
