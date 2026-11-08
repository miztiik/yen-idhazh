"""Own one live text-analysis process group and write bounded workflow evidence."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import httpx
from declare_spacy_verification import (
    CleanupOutcome,
    FailedVerificationReport,
    FailureCode,
    LiveCheckEvidence,
    NativeEvidence,
    SuccessfulVerificationReport,
    SummaryLimitExceededError,
    VerificationReport,
    classify_cleanup,
    render_summary,
    validate_live_checks,
    validate_native_evidence,
    write_bytes_atomic,
    write_json_atomic,
)
from text_analysis.declare_api_contracts import HEALTH_PATH, TextAnalysisEvent
from text_analysis.declare_service_settings import ServiceSettings
from text_analysis.load_service_settings import load_service_settings

ROOT = Path(__file__).resolve().parents[3]
PROBE_PATH = "./services/text_analysis/scripts/probe-text-analysis.ts"
READINESS_POLL_SECONDS = 0.1
OWNER_EXIT_GRACE_SECONDS = 5
EXPECTED_SERVICE_EVENT_COUNT = 3


class VerificationError(RuntimeError):
    """Keep workflow failure reports fixed and free of request content."""

    def __init__(self, code: FailureCode) -> None:
        super().__init__(code)
        self.code = code


@dataclass(slots=True)
class _EventDrainResult:
    failure_code: FailureCode | None = None
    record_count: int = 0
    artifact_bytes: int = 0
    mirrored_bytes: int = 0
    completed: bool = False
    artifact_closed: bool = False
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
        if result.failure_code is None:
            result.failure_code = "EVENT_CAPTURE_FAILED"
        if result.diagnostic_emitted:
            return
        result.diagnostic_emitted = True
    try:
        sys.stderr.write("text-analysis runner event capture failed\n")
        sys.stderr.flush()
    except (OSError, UnicodeError):
        pass


def _write_all(destination: BinaryIO, content: bytes) -> None:
    view = memoryview(content)
    offset = 0
    while offset < len(view):
        written = destination.write(view[offset:])
        if written is None or written <= 0:
            raise OSError("binary write made no progress")
        offset += written


def _capture_valid_event(
    record: bytes,
    artifact: BinaryIO,
    mirror: BinaryIO,
    max_event_records: int,
    result: _EventDrainResult,
) -> None:
    try:
        record.decode("utf-8")
        TextAnalysisEvent.model_validate_json(record)
        if result.record_count >= max_event_records:
            raise ValueError("event record count exceeded its bound")
        _write_all(artifact, record)
        artifact.flush()
        result.record_count += 1
        result.artifact_bytes += len(record)
        _write_all(mirror, record)
        mirror.flush()
        result.mirrored_bytes += len(record)
    except (OSError, UnicodeError, ValueError):
        _mark_event_capture_failed(result)


def _drain_events(
    source: BinaryIO,
    artifact: BinaryIO,
    mirror: BinaryIO,
    max_event_bytes: int,
    max_event_records: int,
    result: _EventDrainResult,
) -> None:
    discarding_oversized_record = False
    try:
        while True:
            try:
                fragment = source.readline(max_event_bytes + 1)
            except (OSError, ValueError):
                _mark_event_capture_failed(result)
                break
            if not fragment:
                break
            if discarding_oversized_record:
                if fragment.endswith(b"\n"):
                    discarding_oversized_record = False
                continue
            if len(fragment) > max_event_bytes or not fragment.endswith(b"\n"):
                _mark_event_capture_failed(result)
                discarding_oversized_record = not fragment.endswith(b"\n")
                continue
            _capture_valid_event(
                fragment,
                artifact,
                mirror,
                max_event_records,
                result,
            )
    finally:
        try:
            source.close()
        except (OSError, ValueError):
            _mark_event_capture_failed(result)
        try:
            artifact.flush()
        except (OSError, ValueError):
            _mark_event_capture_failed(result)
        try:
            artifact.close()
        except (OSError, ValueError):
            _mark_event_capture_failed(result)
        with result.lock:
            result.artifact_closed = artifact.closed
            result.completed = True


def _join_event_drain(
    drain: threading.Thread,
    timeout_seconds: float,
    result: _EventDrainResult,
) -> bool:
    drain.join(timeout_seconds)
    if drain.is_alive():
        _mark_event_capture_failed(result)
        return False
    return result.completed and result.artifact_closed


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
    failure_code: FailureCode,
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
        raise VerificationError(failure_code)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise VerificationError(failure_code) from None
    if not isinstance(result, dict):
        raise VerificationError(failure_code)
    return result


def _wait_for_readiness(
    process: subprocess.Popen[bytes],
    settings: ServiceSettings,
) -> None:
    base_url = f"http://{settings.listener.host}:{settings.listener.port}"
    deadline = (
        time.monotonic() + settings.listener.shutdown_timeout_ms / 1000 * 4
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
    process: subprocess.Popen[bytes] | None,
    shutdown_timeout_ms: int,
) -> CleanupOutcome:
    if process is None:
        return classify_cleanup(
            process_started=False,
            terminate_sent=False,
            kill_sent=False,
            exit_confirmed=False,
            exit_code=None,
        )

    terminate_sent = False
    kill_sent = False
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            terminate_sent = True
        except ProcessLookupError:
            pass
        try:
            process.wait(
                timeout=shutdown_timeout_ms / 1000 + OWNER_EXIT_GRACE_SECONDS
            )
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                kill_sent = True
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=OWNER_EXIT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                return classify_cleanup(
                    process_started=True,
                    terminate_sent=terminate_sent,
                    kill_sent=kill_sent,
                    exit_confirmed=False,
                    exit_code=None,
                )
    exit_code = process.poll()
    return classify_cleanup(
        process_started=True,
        terminate_sent=terminate_sent,
        kill_sent=kill_sent,
        exit_confirmed=exit_code is not None,
        exit_code=exit_code,
    )


def _expected_event_record_bound(verification: Mapping[str, object]) -> int:
    expected_events = verification.get("expected_events")
    if not isinstance(expected_events, list):
        raise VerificationError("EVENT_VALIDATION_FAILED")
    return len(expected_events) + EXPECTED_SERVICE_EVENT_COUNT


def _event_record_bound(language: str) -> int:
    request_events = 6 + (1 if language == "zh" else 0)
    return request_events + EXPECTED_SERVICE_EVENT_COUNT


def _merged_live_checks(
    verification: Mapping[str, object],
    event_validation: Mapping[str, object],
) -> LiveCheckEvidence:
    live_checks = verification.get("live_checks")
    if not isinstance(live_checks, dict):
        raise VerificationError("LIVE_PROBE_FAILED")
    return validate_live_checks(
        {
            **live_checks,
            "warm_model_load_ms": event_validation.get("warm_model_load_ms"),
        }
    )


def _build_report(
    *,
    failure_code: FailureCode | None,
    commit_sha: str,
    run_id: str,
    run_attempt: int,
    cleanup: CleanupOutcome,
) -> VerificationReport:
    if failure_code is None and cleanup.status == "confirmed":
        return SuccessfulVerificationReport(
            commit_sha=commit_sha,
            run_id=run_id,
            run_attempt=run_attempt,
        )
    return FailedVerificationReport(
        commit_sha=commit_sha,
        run_id=run_id,
        run_attempt=run_attempt,
        cleanup=cleanup.status,
        failure_code=failure_code or cleanup.failure_code or "VERIFICATION_FAILED",
    )


def main() -> None:
    inputs = _workflow_inputs()
    commit_sha = _required_environment("TEXT_ANALYSIS_COMMIT_SHA")
    run_id = _required_environment("TEXT_ANALYSIS_RUN_ID")
    run_attempt_text = _required_environment("TEXT_ANALYSIS_RUN_ATTEMPT")
    server_url = _required_environment("GITHUB_SERVER_URL")
    repository = _required_environment("GITHUB_REPOSITORY")
    evidence_directory = Path(
        _required_environment("TEXT_ANALYSIS_EVIDENCE_DIRECTORY")
    ).resolve()
    summary_path = Path(_required_environment("GITHUB_STEP_SUMMARY")).resolve()
    try:
        run_attempt = int(run_attempt_text)
    except ValueError:
        raise VerificationError("INVALID_WORKFLOW_INPUT") from None
    if (
        len(commit_sha) != 40
        or any(character not in "0123456789abcdef" for character in commit_sha)
    ):
        raise VerificationError("TESTED_COMMIT_MISMATCH")

    evidence_directory.mkdir(parents=True, exist_ok=True)
    events_path = evidence_directory / "events.jsonl"
    report_path = evidence_directory / "report.json"
    request_path = evidence_directory / "analysis-request.json"
    health_path = evidence_directory / "health-response.json"
    analysis_path = evidence_directory / "analysis-response.json"
    report_markdown_path = evidence_directory / "report.md"
    settings = load_service_settings(ROOT)
    base_url = f"http://{settings.listener.host}:{settings.listener.port}"
    event_record_bound = _event_record_bound(inputs["language"])

    failure_code: FailureCode | None = None
    verification_state: dict[str, Any] | None = None
    event_validation: dict[str, Any] | None = None
    native: NativeEvidence | None = None
    checks: LiveCheckEvidence | None = None
    cleanup = CleanupOutcome(status="not_started")
    process: subprocess.Popen[bytes] | None = None
    drain: threading.Thread | None = None
    drain_completed = False
    drain_result = _EventDrainResult()
    events = events_path.open("wb")

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
                    text=False,
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
                        event_record_bound,
                        drain_result,
                    ),
                    name="text-analysis-event-drain",
                    daemon=True,
                )
                try:
                    event_drain.start()
                except RuntimeError:
                    _mark_event_capture_failed(drain_result)
                    raise VerificationError("EVENT_CAPTURE_FAILED") from None
                drain = event_drain
            with _workflow_group("Wait for readiness"):
                _wait_for_readiness(process, settings)
            with _workflow_group("Verify HTTP API"):
                verification_state = _run_probe(
                    {
                        "mode": "verify_api",
                        "base_url": base_url,
                        **inputs,
                    },
                    "LIVE_PROBE_FAILED",
                )
                try:
                    native = validate_native_evidence(verification_state)
                    write_json_atomic(request_path, native.request)
                    write_json_atomic(health_path, native.health)
                    write_json_atomic(analysis_path, native.analysis)
                except (KeyError, OSError, TypeError, ValueError):
                    raise VerificationError("NATIVE_EVIDENCE_INVALID") from None
        except VerificationError as failure:
            failure_code = failure.code
        except OSError:
            failure_code = "SERVER_START_FAILED"
        except Exception:
            failure_code = "VERIFICATION_FAILED"
        finally:
            with _workflow_group("Stop server"):
                try:
                    cleanup = _stop_owned_process(
                        process,
                        settings.listener.shutdown_timeout_ms,
                    )
                except OSError:
                    cleanup = CleanupOutcome(
                        status="unconfirmed",
                        failure_code="PROCESS_GROUP_NOT_STOPPED",
                    )
                if (
                    drain is not None
                    and process is not None
                    and process.stderr is not None
                ):
                    drain_completed = _join_event_drain(
                        drain,
                        settings.listener.shutdown_timeout_ms / 1000
                        + OWNER_EXIT_GRACE_SECONDS,
                        drain_result,
                    )
                elif process is not None and process.stderr is not None:
                    try:
                        process.stderr.close()
                    except (OSError, ValueError):
                        _mark_event_capture_failed(drain_result)
                if drain is None:
                    try:
                        events.flush()
                    except (OSError, ValueError):
                        _mark_event_capture_failed(drain_result)
                    try:
                        events.close()
                    except (OSError, ValueError):
                        _mark_event_capture_failed(drain_result)
    finally:
        if drain is None and not events.closed:
            try:
                events.close()
            except (OSError, ValueError):
                _mark_event_capture_failed(drain_result)

    with _workflow_group("Validate evidence"):
        capture_failed = drain_result.failure_code is not None
        if drain is not None and not drain_completed:
            _mark_event_capture_failed(drain_result)
            capture_failed = True
        if drain_result.failure_code is not None:
            failure_code = "EVENT_CAPTURE_FAILED"
        elif (
            drain_completed
            and (
                drain_result.artifact_bytes == 0
                or drain_result.mirrored_bytes != drain_result.artifact_bytes
            )
        ):
            _mark_event_capture_failed(drain_result)
            failure_code = "EVENT_CAPTURE_FAILED"
            capture_failed = True

        if (
            verification_state is not None
            and drain_completed
            and drain_result.artifact_closed
        ):
            try:
                expected_record_bound = _expected_event_record_bound(
                    verification_state
                )
                if expected_record_bound != event_record_bound:
                    raise VerificationError("EVENT_VALIDATION_FAILED")
                event_validation = _run_probe(
                    {
                        "mode": "validate_events",
                        "events_path": str(events_path),
                        "text": inputs["text"],
                        "verification": verification_state,
                        "max_event_bytes": settings.logging.max_event_bytes,
                        "max_event_records": expected_record_bound,
                    },
                    "EVENT_VALIDATION_FAILED",
                    echo_failure=not capture_failed,
                )
                checks = _merged_live_checks(
                    verification_state,
                    event_validation,
                )
            except (TypeError, ValueError, VerificationError) as failure:
                failure_code = (
                    failure.code
                    if isinstance(failure, VerificationError)
                    else "EVENT_VALIDATION_FAILED"
                )

    if cleanup.failure_code is not None:
        failure_code = cleanup.failure_code
    if native is None or event_validation is None or checks is None:
        failure_code = failure_code or "VERIFICATION_FAILED"

    report = _build_report(
        failure_code=failure_code,
        commit_sha=commit_sha,
        run_id=run_id,
        run_attempt=run_attempt,
        cleanup=cleanup,
    )
    try:
        summary = render_summary(
            conclusion=report.conclusion,
            failure_code=getattr(report, "failure_code", None),
            commit_sha=commit_sha,
            run_id=run_id,
            cleanup=cleanup.status,
            source_text=inputs["text"],
            server_url=server_url,
            repository=repository,
            native=native,
            checks=checks,
        )
    except SummaryLimitExceededError:
        failure_code = "SUMMARY_TOO_LARGE"
        report = _build_report(
            failure_code=failure_code,
            commit_sha=commit_sha,
            run_id=run_id,
            run_attempt=run_attempt,
            cleanup=cleanup,
        )
        summary = render_summary(
            conclusion="failure",
            failure_code=failure_code,
            commit_sha=commit_sha,
            run_id=run_id,
            cleanup=cleanup.status,
            source_text=inputs["text"],
            server_url=server_url,
            repository=repository,
            native=native,
            checks=checks,
            include_source=False,
        )

    try:
        write_json_atomic(report_path, report)
        write_bytes_atomic(report_markdown_path, summary)
        if summary_path.exists() and summary_path.stat().st_size != 0:
            raise OSError("GitHub step summary already contains bytes")
        with summary_path.open("ab") as destination:
            destination.write(summary)
            destination.flush()
            os.fsync(destination.fileno())
    except OSError:
        raise VerificationError("ARTIFACT_WRITE_FAILED") from None

    if report.conclusion != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
