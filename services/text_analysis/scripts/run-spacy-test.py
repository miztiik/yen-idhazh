"""Own one live text-analysis process group and write bounded workflow evidence."""

import html
import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Literal, cast

import httpx
from text_analysis.declare_api_contracts import HEALTH_PATH, TextAnalysisEvent
from text_analysis.declare_service_settings import ServiceSettings
from text_analysis.load_service_settings import load_service_settings

ROOT = Path(__file__).resolve().parents[3]
PROBE_PATH = "./services/text_analysis/scripts/probe-text-analysis.ts"
READINESS_POLL_SECONDS = 0.1
OWNER_EXIT_GRACE_SECONDS = 5


class VerificationError(RuntimeError):
    """Keep workflow failure reports fixed and free of request content."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(slots=True)
class _EventDrainResult:
    failed: bool = False
    artifact_bytes: int = 0
    mirrored_bytes: int = 0
    diagnostic_emitted: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


@contextmanager
def _workflow_group(name: str) -> Iterator[None]:
    print(f"::group::{name}", flush=True)
    try:
        yield
    finally:
        print("::endgroup::", flush=True)


def _mark_event_capture_failed(result: _EventDrainResult) -> None:
    with result.lock:
        result.failed = True
        if result.diagnostic_emitted:
            return
        result.diagnostic_emitted = True
    try:
        sys.stderr.write("text-analysis runner event capture failed\n")
        sys.stderr.flush()
    except (OSError, UnicodeError):
        pass


def _mirror_valid_event(
    record: bytes,
    mirror: BinaryIO,
    result: _EventDrainResult,
) -> None:
    try:
        record.decode("utf-8")
        TextAnalysisEvent.model_validate_json(record)
    except (UnicodeDecodeError, ValueError):
        _mark_event_capture_failed(result)
        return
    try:
        written = mirror.write(record)
        if written != len(record):
            raise OSError("short event mirror write")
        mirror.flush()
    except (OSError, UnicodeError, ValueError):
        _mark_event_capture_failed(result)
        return
    result.mirrored_bytes += written


def _drain_events(
    source: BinaryIO,
    artifact: BinaryIO,
    mirror: BinaryIO,
    max_event_bytes: int,
    result: _EventDrainResult,
) -> None:
    pending = bytearray()
    discarding_oversized_record = False
    while True:
        try:
            chunk = os.read(source.fileno(), max_event_bytes)
        except (OSError, ValueError):
            _mark_event_capture_failed(result)
            break
        if not chunk:
            break
        try:
            written = artifact.write(chunk)
            if written != len(chunk):
                raise OSError("short event artifact write")
            result.artifact_bytes += written
        except (OSError, ValueError):
            _mark_event_capture_failed(result)

        cursor = 0
        while cursor < len(chunk):
            if discarding_oversized_record:
                newline = chunk.find(b"\n", cursor)
                if newline < 0:
                    cursor = len(chunk)
                    continue
                discarding_oversized_record = False
                cursor = newline + 1
                continue

            newline = chunk.find(b"\n", cursor)
            if newline < 0:
                remainder = chunk[cursor:]
                if len(pending) + len(remainder) >= max_event_bytes:
                    pending.clear()
                    discarding_oversized_record = True
                    _mark_event_capture_failed(result)
                else:
                    pending.extend(remainder)
                cursor = len(chunk)
                continue

            segment = chunk[cursor : newline + 1]
            if len(pending) + len(segment) > max_event_bytes:
                pending.clear()
                _mark_event_capture_failed(result)
            else:
                pending.extend(segment)
                _mirror_valid_event(bytes(pending), mirror, result)
                pending.clear()
            cursor = newline + 1

    if pending or discarding_oversized_record:
        _mark_event_capture_failed(result)


def _join_event_drain(
    drain: threading.Thread,
    source: BinaryIO,
    timeout_seconds: float,
    result: _EventDrainResult,
) -> None:
    drain.join(timeout_seconds)
    if not drain.is_alive():
        return
    _mark_event_capture_failed(result)
    try:
        source.close()
    except OSError:
        pass
    drain.join(OWNER_EXIT_GRACE_SECONDS)
    if drain.is_alive():
        _mark_event_capture_failed(result)


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value:
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    return value


def _request_text_from_stdin() -> str:
    try:
        event = json.load(sys.stdin)
        inputs = event["inputs"]
        request_text = inputs["text"]
    except (KeyError, TypeError, json.JSONDecodeError):
        raise VerificationError("INVALID_WORKFLOW_INPUT") from None
    if not isinstance(request_text, str) or not request_text:
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    return request_text


def _workflow_inputs() -> dict[str, str]:
    language = _required_environment("TEXT_ANALYSIS_LANGUAGE")
    profile = _required_environment("TEXT_ANALYSIS_PROFILE")
    feature_mode = _required_environment("TEXT_ANALYSIS_FEATURE_MODE")
    custom_features = os.environ.get("TEXT_ANALYSIS_CUSTOM_FEATURES", "")
    request_text = _request_text_from_stdin()
    if language not in ("en", "zh"):
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    if profile not in ("sm", "md", "lg"):
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    if feature_mode not in ("default", "all", "custom"):
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    if feature_mode == "custom":
        if not custom_features:
            raise VerificationError("INVALID_WORKFLOW_INPUT")
    elif custom_features:
        raise VerificationError("INVALID_WORKFLOW_INPUT")
    return {
        "language": language,
        "profile": profile,
        "feature_mode": feature_mode,
        "custom_features": custom_features,
        "text": request_text,
    }


def _run_probe(
    payload: dict[str, Any],
    *,
    echo_failure: bool = True,
) -> dict[str, Any]:
    completed = subprocess.run(
        ["bun", "run", "--no-install", PROBE_PATH],
        cwd=ROOT,
        input=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        if echo_failure and completed.stderr:
            sys.stderr.write(completed.stderr)
        raise VerificationError("LIVE_PROBE_FAILED")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise VerificationError("LIVE_PROBE_FAILED") from None
    if not isinstance(result, dict):
        raise VerificationError("LIVE_PROBE_FAILED")
    return result


def _wait_for_readiness(
    process: subprocess.Popen[bytes],
    settings: ServiceSettings,
) -> None:
    base_url = f"http://{settings.listener.host}:{settings.listener.port}"
    deadline = (
        time.monotonic()
        + settings.listener.shutdown_timeout_ms / 1000 * 4
    )
    timeout = settings.listener.body_read_timeout_ms / 1000
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise VerificationError("SERVER_EXITED_BEFORE_READY")
            try:
                response = client.get(f"{base_url}{HEALTH_PATH}")
            except httpx.HTTPError:
                time.sleep(READINESS_POLL_SECONDS)
                continue
            if response.status_code == 200:
                try:
                    body = response.json()
                except ValueError:
                    raise VerificationError("INVALID_HEALTH_RESPONSE") from None
                if (
                    isinstance(body, dict)
                    and body.get("status") == "ready"
                    and body.get("pool_ready") is True
                ):
                    return
            time.sleep(READINESS_POLL_SECONDS)
    raise VerificationError("SERVER_NOT_READY")


def _stop_owned_process(
    process: subprocess.Popen[bytes],
    shutdown_timeout_ms: int,
) -> dict[str, Any]:
    forced = False
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(
                timeout=shutdown_timeout_ms / 1000 + OWNER_EXIT_GRACE_SECONDS
            )
        except subprocess.TimeoutExpired:
            forced = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=OWNER_EXIT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                raise VerificationError("PROCESS_GROUP_NOT_STOPPED") from None
    exit_code = process.poll()
    if exit_code is None:
        raise VerificationError("PROCESS_GROUP_NOT_STOPPED")
    return {
        "confirmed": True,
        "forced": forced,
        "exit_code": exit_code,
    }


def _escaped_summary(
    conclusion: Literal["success", "failure"],
    inputs: dict[str, str],
    selected_ref: str,
    tested_commit: str,
    workflow_sha: str,
) -> str:
    values = {
        "Conclusion": conclusion,
        "Selected ref": selected_ref,
        "Tested commit": tested_commit,
        "Workflow revision": workflow_sha,
        "Language": inputs["language"],
        "Profile": inputs["profile"],
        "Feature mode": inputs["feature_mode"],
    }
    lines = ["## Text-analysis verification", ""]
    lines.extend(
        f"- **{label}:** {html.escape(value, quote=True)}"
        for label, value in values.items()
    )
    lines.append("")
    lines.append(
        "Machine-readable results and validated events are in the uploaded artifact."
    )
    return "\n".join(lines) + "\n"


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    inputs = _workflow_inputs()
    workflow_sha = _required_environment("TEXT_ANALYSIS_WORKFLOW_SHA")
    selected_ref = _required_environment("TEXT_ANALYSIS_SELECTED_REF")
    selected_sha = _required_environment("TEXT_ANALYSIS_SELECTED_SHA")
    tested_commit = _required_environment("TEXT_ANALYSIS_TESTED_COMMIT")
    run_id = _required_environment("TEXT_ANALYSIS_RUN_ID")
    run_attempt = _required_environment("TEXT_ANALYSIS_RUN_ATTEMPT")
    evidence_directory = Path(
        _required_environment("TEXT_ANALYSIS_EVIDENCE_DIRECTORY")
    ).resolve()
    summary_path = Path(_required_environment("GITHUB_STEP_SUMMARY")).resolve()
    evidence_directory.mkdir(parents=True, exist_ok=True)
    events_path = evidence_directory / "events.jsonl"
    report_path = evidence_directory / "report.json"
    job_summary_path = evidence_directory / "job-summary.md"
    settings = load_service_settings(ROOT)
    if (
        len(selected_sha) != 40
        or any(character not in "0123456789abcdef" for character in selected_sha)
        or selected_sha != tested_commit
    ):
        raise VerificationError("TESTED_COMMIT_MISMATCH")
    base_url = f"http://{settings.listener.host}:{settings.listener.port}"
    report: dict[str, Any] = {
        "version": "2026-11-07",
        "conclusion": "failure",
        "workflow_sha": workflow_sha,
        "selected_ref": selected_ref,
        "selected_sha": selected_sha,
        "tested_commit": tested_commit,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "inputs": {
            "language": inputs["language"],
            "profile": inputs["profile"],
            "feature_mode": inputs["feature_mode"],
            "custom_features": inputs["custom_features"],
            "text_codepoint_count": len(inputs["text"]),
            "text_utf8_byte_count": len(inputs["text"].encode("utf-8")),
        },
    }
    failure_code: str | None = None
    exercise_result: dict[str, Any] = {
        "expected_events": [],
        "no_event_traceparents": [],
        "evidence_texts": [],
    }
    cleanup: dict[str, Any] | None = None

    events = events_path.open("wb")
    process: subprocess.Popen[bytes] | None = None
    drain: threading.Thread | None = None
    drain_result = _EventDrainResult()
    try:
        try:
            with _workflow_group("Start server"):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "text_analysis",
                        "--root",
                        str(ROOT),
                    ],
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                if process.stderr is None:
                    _mark_event_capture_failed(drain_result)
                    raise VerificationError("EVENT_CAPTURE_FAILED")
                mirror = getattr(sys.stderr, "buffer", None)
                if mirror is None:
                    _mark_event_capture_failed(drain_result)
                    raise VerificationError("EVENT_CAPTURE_FAILED")
                event_drain = threading.Thread(
                    target=_drain_events,
                    args=(
                        process.stderr,
                        events,
                        mirror,
                        settings.logging.max_event_bytes,
                        drain_result,
                    ),
                    name="text-analysis-event-drain",
                    daemon=False,
                )
                try:
                    event_drain.start()
                except RuntimeError:
                    _mark_event_capture_failed(drain_result)
                    raise VerificationError("EVENT_CAPTURE_FAILED") from None
                drain = event_drain
            with _workflow_group("Wait for readiness"):
                _wait_for_readiness(process, settings)
            with _workflow_group("Exercise HTTP API"):
                exercise_result = _run_probe(
                    {
                        "mode": "exercise",
                        "base_url": base_url,
                        **inputs,
                    }
                )
                report["exercise"] = exercise_result
        except VerificationError as failure:
            failure_code = failure.code
        except OSError:
            failure_code = "SERVER_START_FAILED"
        except Exception:
            failure_code = "VERIFICATION_FAILED"
        finally:
            with _workflow_group("Stop server"):
                if process is not None:
                    try:
                        cleanup = _stop_owned_process(
                            process,
                            settings.listener.shutdown_timeout_ms,
                        )
                    except (OSError, VerificationError):
                        cleanup = {
                            "confirmed": False,
                            "forced": True,
                            "exit_code": process.poll(),
                        }
                        failure_code = failure_code or "PROCESS_GROUP_NOT_STOPPED"
                if drain is not None and process is not None and process.stderr is not None:
                    _join_event_drain(
                        drain,
                        process.stderr,
                        settings.listener.shutdown_timeout_ms / 1000
                        + OWNER_EXIT_GRACE_SECONDS,
                        drain_result,
                    )
                    try:
                        process.stderr.close()
                    except OSError:
                        _mark_event_capture_failed(drain_result)
                try:
                    events.flush()
                except OSError:
                    _mark_event_capture_failed(drain_result)
                try:
                    events.close()
                except OSError:
                    _mark_event_capture_failed(drain_result)
    finally:
        if not events.closed:
            try:
                events.close()
            except OSError:
                _mark_event_capture_failed(drain_result)

    report["cleanup"] = cleanup
    event_validation: dict[str, Any] | None = None
    with _workflow_group("Validate evidence"):
        capture_failed = drain_result.failed
        if drain_result.failed:
            _mark_event_capture_failed(drain_result)
            failure_code = "EVENT_CAPTURE_FAILED"
        elif failure_code is None and (
            drain_result.artifact_bytes == 0
            or drain_result.mirrored_bytes != drain_result.artifact_bytes
        ):
            _mark_event_capture_failed(drain_result)
            failure_code = "EVENT_CAPTURE_FAILED"
            capture_failed = True
        try:
            event_validation = _run_probe(
                {
                    "mode": "validate_events",
                    "events_path": str(events_path),
                    "text": inputs["text"],
                    "exercise": exercise_result,
                },
                echo_failure=not capture_failed,
            )
            report["event_validation"] = event_validation
        except VerificationError as failure:
            failure_code = failure_code or failure.code

    if (
        failure_code is None
        and cleanup is not None
        and cleanup["confirmed"] is True
        and cleanup["forced"] is False
        and cleanup["exit_code"] in (0, -signal.SIGTERM)
        and event_validation is not None
    ):
        report["conclusion"] = "success"
    else:
        report["failure_code"] = failure_code or "CLEANUP_FAILED"

    summary = _escaped_summary(
        cast(Literal["success", "failure"], report["conclusion"]),
        inputs,
        selected_ref,
        tested_commit,
        workflow_sha,
    )
    job_summary_path.write_text(summary, encoding="utf-8", newline="\n")
    with summary_path.open("a", encoding="utf-8", newline="\n") as destination:
        destination.write(summary)
    _write_report(report_path, report)
    if report["conclusion"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
