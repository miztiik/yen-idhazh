"""How does the caller own and stop the shared local API process?"""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

import httpx
from gliner_api.declare_api_contracts import HEALTH_PATH as GLINER_HEALTH
from gliner_api.declare_api_contracts import GlinerHealth
from pydantic import ValidationError
from text_analysis.declare_api_contracts import HEALTH_PATH as SPACY_HEALTH
from text_analysis.declare_api_contracts import TextAnalysisHealth
from text_analysis.declare_service_settings import ListenerSettings

# These are process-supervision intervals, not model or report settings.
READINESS_POLL_SECONDS = 0.1
STARTUP_TIMEOUT_MULTIPLIER = 4
EXIT_GRACE_SECONDS = 5


def start_apis(root: Path) -> subprocess.Popen[bytes]:
    """Start the shared assembly in a separate process group."""
    return subprocess.Popen(
        [
            sys.executable,
            str(root / "services/text_analysis/hosting/serve_apis.py"),
            "--root",
            str(root),
        ],
        cwd=root,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_apis(
    process: subprocess.Popen[bytes], listener: ListenerSettings
) -> tuple[TextAnalysisHealth | None, GlinerHealth | None]:
    """Wait for each native readiness response, bounded by the listener deadline."""
    base_url = f"http://{listener.host}:{listener.port}"
    deadline = time.monotonic() + (listener.shutdown_timeout_ms / 1000 * STARTUP_TIMEOUT_MULTIPLIER)
    spacy = None
    gliner = None
    with httpx.Client(
        base_url=base_url,
        timeout=listener.body_read_timeout_ms / 1000,
        trust_env=False,
    ) as client:
        while time.monotonic() < deadline and process.poll() is None:
            if spacy is None:
                try:
                    response = client.get(SPACY_HEALTH)
                    candidate = TextAnalysisHealth.model_validate_json(response.content)
                    if response.status_code == 200 and candidate.status == "ready":
                        spacy = candidate
                except (httpx.HTTPError, ValidationError):
                    pass
            if gliner is None:
                try:
                    response = client.get(GLINER_HEALTH)
                    candidate_gliner = GlinerHealth.model_validate_json(response.content)
                    if response.status_code == 200 and candidate_gliner.status == "ready":
                        gliner = candidate_gliner
                except (httpx.HTTPError, ValidationError):
                    pass
            if spacy is not None and gliner is not None:
                break
            time.sleep(READINESS_POLL_SECONDS)
    return spacy, gliner


def stop_apis(process: subprocess.Popen[bytes], listener: ListenerSettings) -> None:
    """Confirm the owned process exits; surface forced or unexpected shutdown."""
    if process.poll() is not None:
        raise RuntimeError("The API process exited before cleanup.")
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        raise RuntimeError("The API process exited before cleanup.") from None
    try:
        exit_code = process.wait(timeout=listener.shutdown_timeout_ms / 1000 + EXIT_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=EXIT_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            raise RuntimeError("The API process could not be stopped.") from None
        raise RuntimeError("The API process required forced shutdown.") from None
    if exit_code not in (0, -signal.SIGTERM):
        raise RuntimeError("The API process exited unexpectedly during cleanup.")
