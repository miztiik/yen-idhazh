"""Which persisted artifacts and human projection does one live verification emit?"""

from __future__ import annotations

import html
import json
import os
import re
import signal
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter
from text_analysis.declare_api_contracts import (
    AnalysisResult,
    AnalyzeTextRequest,
    LegacyTextAnalysisHealth,
    TextAnalysisHealth,
)

REPORT_VERSION = "2026-11-08"
REPORT_CHANGE = (
    "Split native API evidence from the verification outcome and make cleanup semantic."
)
GITHUB_STEP_SUMMARY_MAX_BYTES = 1_048_576

type CleanupStatus = Literal[
    "not_started",
    "confirmed",
    "forced",
    "unconfirmed",
]
type FailureCode = Literal[
    "INVALID_WORKFLOW_INPUT",
    "TESTED_COMMIT_MISMATCH",
    "SERVER_START_FAILED",
    "SERVER_EXITED_BEFORE_READY",
    "INVALID_HEALTH_RESPONSE",
    "SERVER_NOT_READY",
    "LIVE_PROBE_FAILED",
    "EVENT_CAPTURE_FAILED",
    "EVENT_VALIDATION_FAILED",
    "NATIVE_EVIDENCE_INVALID",
    "PROCESS_GROUP_NOT_STOPPED",
    "UNEXPECTED_PROCESS_EXIT",
    "CLEANUP_FORCED",
    "SUMMARY_TOO_LARGE",
    "ARTIFACT_WRITE_FAILED",
    "VERIFICATION_FAILED",
]

CommitSha = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{40}$"),
]
PositiveDecimalString = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[1-9][0-9]*$"),
]

_REPORT_SCHEMA = {
    "version": REPORT_VERSION,
    "changelog": [
        {
            "version": REPORT_VERSION,
            "change": REPORT_CHANGE,
        }
    ],
}


class _VerificationReportBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        json_schema_extra=_REPORT_SCHEMA,
    )

    version: Literal["2026-11-08"] = REPORT_VERSION
    commit_sha: CommitSha
    run_id: PositiveDecimalString
    run_attempt: int = Field(strict=True, gt=0)
    cleanup: CleanupStatus


class SuccessfulVerificationReport(_VerificationReportBase):
    """Persist only the immutable run identity and confirmed successful outcome."""

    conclusion: Literal["success"] = "success"
    cleanup: Literal["confirmed"] = "confirmed"


class FailedVerificationReport(_VerificationReportBase):
    """Add one declared safe code without retaining native or internal evidence."""

    conclusion: Literal["failure"] = "failure"
    failure_code: FailureCode


type VerificationReport = (
    SuccessfulVerificationReport | FailedVerificationReport
)


@dataclass(frozen=True, slots=True)
class CleanupOutcome:
    status: CleanupStatus
    failure_code: FailureCode | None = None


@dataclass(frozen=True, slots=True)
class NativeEvidence:
    request: AnalyzeTextRequest
    health: TextAnalysisHealth | LegacyTextAnalysisHealth
    analysis: AnalysisResult


@dataclass(frozen=True, slots=True)
class LiveCheckEvidence:
    active_requests: int
    capacity: int
    busy_http_status: int
    busy_queued: bool
    warm_model_load_ms: int


class SummaryLimitExceededError(ValueError):
    """Signal that the complete Markdown projection cannot fit the platform."""


FAILURE_MESSAGES: Mapping[FailureCode, str] = {
    "INVALID_WORKFLOW_INPUT": "The workflow inputs were invalid.",
    "TESTED_COMMIT_MISMATCH": "The tested checkout did not match the selected commit.",
    "SERVER_START_FAILED": "The text-analysis service did not start.",
    "SERVER_EXITED_BEFORE_READY": "The text-analysis service exited before readiness.",
    "INVALID_HEALTH_RESPONSE": "The readiness response was invalid.",
    "SERVER_NOT_READY": "The text-analysis service did not become ready.",
    "LIVE_PROBE_FAILED": "The live API verification failed.",
    "EVENT_CAPTURE_FAILED": "The server event stream could not be captured safely.",
    "EVENT_VALIDATION_FAILED": "The captured server events failed validation.",
    "NATIVE_EVIDENCE_INVALID": "The selected native API evidence failed validation.",
    "PROCESS_GROUP_NOT_STOPPED": "The owned service process did not confirm exit.",
    "UNEXPECTED_PROCESS_EXIT": "The owned service process exited unexpectedly.",
    "CLEANUP_FORCED": "The owned service required forced cleanup.",
    "SUMMARY_TOO_LARGE": (
        "The human summary exceeded GitHub's 1 MiB per-step limit."
    ),
    "ARTIFACT_WRITE_FAILED": "The verification artifacts could not be written safely.",
    "VERIFICATION_FAILED": "The live verification failed.",
}


def classify_cleanup(
    *,
    process_started: bool,
    terminate_sent: bool,
    kill_sent: bool,
    exit_confirmed: bool,
    exit_code: int | None,
) -> CleanupOutcome:
    """Translate process ownership details into one semantic cleanup outcome."""

    if not process_started:
        return CleanupOutcome(status="not_started")
    if not exit_confirmed or exit_code is None:
        return CleanupOutcome(
            status="unconfirmed",
            failure_code="PROCESS_GROUP_NOT_STOPPED",
        )
    if kill_sent:
        return CleanupOutcome(status="forced", failure_code="CLEANUP_FORCED")
    if exit_code == 0 or (terminate_sent and exit_code == -signal.SIGTERM):
        return CleanupOutcome(status="confirmed")
    return CleanupOutcome(
        status="confirmed",
        failure_code="UNEXPECTED_PROCESS_EXIT",
    )


def validate_native_evidence(value: Mapping[str, object]) -> NativeEvidence:
    """Validate freshly produced evidence with the strict current live contracts."""

    return _validate_native_components(
        AnalyzeTextRequest.model_validate_json(
            json.dumps(value["analysis_request"], ensure_ascii=False)
        ),
        TextAnalysisHealth.model_validate_json(
            json.dumps(value["health_response"], ensure_ascii=False)
        ),
        AnalysisResult.model_validate_json(
            json.dumps(value["analysis_response"], ensure_ascii=False)
        ),
    )


def read_retained_native_evidence(value: Mapping[str, object]) -> NativeEvidence:
    """Read exact current or initial evidence without rewriting retained payloads."""

    return _validate_native_components(
        AnalyzeTextRequest.model_validate_json(
            json.dumps(value["analysis_request"], ensure_ascii=False)
        ),
        TypeAdapter(TextAnalysisHealth | LegacyTextAnalysisHealth).validate_json(
            json.dumps(value["health_response"], ensure_ascii=False)
        ),
        AnalysisResult.model_validate_json(
            json.dumps(value["analysis_response"], ensure_ascii=False)
        ),
    )


def _validate_native_components(
    request: AnalyzeTextRequest,
    health: TextAnalysisHealth | LegacyTextAnalysisHealth,
    analysis: AnalysisResult,
) -> NativeEvidence:
    if request.model_profile is None or request.features is None:
        raise ValueError("Selected request must retain resolved profile and features")
    if not set(request.features).issubset(health.allowed_features):
        raise ValueError("Selected request features are not allowed by recorded health")
    if health.status != "ready" or not health.pool_ready:
        raise ValueError("Persisted health evidence must be ready")
    if analysis.language != request.language:
        raise ValueError("Selected request and response languages differ")
    if analysis.model.profile != request.model_profile:
        raise ValueError("Selected request and response profiles differ")
    if tuple(item.feature for item in analysis.features) != request.features:
        raise ValueError("Selected request and response feature order differs")
    capability = next(
        (
            item
            for item in health.languages
            if item.language == request.language and item.enabled
        ),
        None,
    )
    if capability is None:
        raise ValueError("Selected language is not enabled in health evidence")
    configured_profile = next(
        (
            item
            for item in capability.profiles
            if item.profile == request.model_profile
        ),
        None,
    )
    if configured_profile is None:
        raise ValueError("Selected profile is not configured in health evidence")
    if (
        analysis.model.package != configured_profile.package
        or analysis.model.model_version != configured_profile.model_version
        or analysis.model.spacy_version != health.spacy_version
    ):
        raise ValueError("Selected result identity differs from health evidence")
    return NativeEvidence(request=request, health=health, analysis=analysis)


def validate_live_checks(value: Mapping[str, object]) -> LiveCheckEvidence:
    """Keep summary claims tied to the exact assertions the probe completed."""

    evidence = LiveCheckEvidence(
        active_requests=_strict_int(value["active_requests"]),
        capacity=_strict_int(value["capacity"]),
        busy_http_status=_strict_int(value["busy_http_status"]),
        busy_queued=_strict_bool(value["busy_queued"]),
        warm_model_load_ms=_strict_int(value["warm_model_load_ms"]),
    )
    if evidence.active_requests != 2 or evidence.capacity != 2:
        raise ValueError("Concurrency evidence does not prove full capacity")
    if evidence.busy_http_status != 429 or evidence.busy_queued:
        raise ValueError("BUSY evidence does not prove immediate refusal")
    if evidence.warm_model_load_ms != 0:
        raise ValueError("Warm reuse evidence retained a model load")
    return evidence


def render_summary(
    *,
    conclusion: Literal["success", "failure"],
    failure_code: FailureCode | None,
    commit_sha: str,
    run_id: str,
    cleanup: CleanupStatus,
    source_text: str,
    server_url: str,
    repository: str,
    native: NativeEvidence | None,
    checks: LiveCheckEvidence | None,
) -> bytes:
    """Render one escaped result-first projection within GitHub's 1 MiB limit."""

    content = _render_summary_content(
        conclusion=conclusion,
        failure_code=failure_code,
        commit_sha=commit_sha,
        run_id=run_id,
        cleanup=cleanup,
        source_text=source_text,
        server_url=server_url,
        repository=repository,
        native=native,
        checks=checks,
    )
    if len(content) > GITHUB_STEP_SUMMARY_MAX_BYTES:
        raise SummaryLimitExceededError(
            "Rendered summary exceeds GitHub's 1 MiB per-step limit"
        )
    return content


def render_oversized_failure_summary(
    *,
    commit_sha: str,
    run_id: str,
    cleanup: CleanupStatus,
    source_text: str,
    server_url: str,
    repository: str,
    native: NativeEvidence | None,
    checks: LiveCheckEvidence | None,
) -> bytes:
    """Keep the complete source in the failed artifact when GitHub cannot render it."""

    return _render_summary_content(
        conclusion="failure",
        failure_code="SUMMARY_TOO_LARGE",
        commit_sha=commit_sha,
        run_id=run_id,
        cleanup=cleanup,
        source_text=source_text,
        server_url=server_url,
        repository=repository,
        native=native,
        checks=checks,
    )


def _render_summary_content(
    *,
    conclusion: Literal["success", "failure"],
    failure_code: FailureCode | None,
    commit_sha: str,
    run_id: str,
    cleanup: CleanupStatus,
    source_text: str,
    server_url: str,
    repository: str,
    native: NativeEvidence | None,
    checks: LiveCheckEvidence | None,
) -> bytes:
    _validate_github_location(server_url, repository)
    if conclusion == "success":
        if failure_code is not None or native is None or checks is None:
            raise ValueError("Successful summary requires complete evidence")
        result_line = "**Live test: PASS** - All required live checks passed."
    else:
        if failure_code is None:
            raise ValueError("Failed summary requires a safe failure code")
        result_line = (
            f"**Live test: FAIL** - {failure_code}: "
            f"{FAILURE_MESSAGES[failure_code]}"
        )

    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
    commit_url = f"{server_url}/{repository}/commit/{commit_sha}"
    lines = [
        "# Text analysis - spaCy live test",
        "",
        result_line,
        "",
        f"[Run {run_id}]({run_url}) | [Commit `{commit_sha}`]({commit_url})",
        "",
        "## Selected analysis",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    if native is None:
        selected_rows = (
            ("Language", "Unavailable"),
            ("Profile", "Unavailable"),
            ("Model package/version", "Unavailable"),
            ("spaCy version", "Unavailable"),
            ("Result status", "Unavailable"),
        )
    else:
        selected_rows = (
            ("Language", native.analysis.language),
            ("Profile", native.analysis.model.profile),
            (
                "Model package/version",
                f"{native.analysis.model.package} {native.analysis.model.model_version}",
            ),
            ("spaCy version", native.analysis.model.spacy_version),
            ("Result status", native.analysis.status),
        )
    lines.extend(
        f"| {_table_text(label)} | {_table_text(value)} |"
        for label, value in selected_rows
    )

    lines.extend(
        [
            "",
            "### Feature results",
            "",
            "| Feature | Result |",
            "| --- | --- |",
        ]
    )
    if native is None:
        lines.append("| Unavailable | No validated analysis response was produced. |")
    else:
        for item in native.analysis.features:
            result = item.status
            if item.error is not None:
                result = f"{result} - {item.error.code}"
            lines.append(
                f"| {_table_text(item.feature)} | {_table_text(result)} |"
            )

    lines.extend(
        [
            "",
            "## Live checks",
            "",
            "| Check | Evidence |",
            "| --- | --- |",
        ]
    )
    if checks is None:
        live_rows = (
            ("Concurrency", "Not completed."),
            ("BUSY refusal", "Not completed."),
            ("Warm model reuse", "Not completed."),
            ("Cleanup", cleanup),
        )
    else:
        live_rows = (
            (
                "Concurrency",
                (
                    f"{checks.active_requests} active requests at configured "
                    f"capacity {checks.capacity}."
                ),
            ),
            (
                "BUSY refusal",
                (
                    f"Third request returned HTTP {checks.busy_http_status}; "
                    "no queue was created."
                ),
            ),
            (
                "Warm model reuse",
                f"Repeated selected request reported {checks.warm_model_load_ms} ms model load.",
            ),
            ("Cleanup", cleanup),
        )
    lines.extend(
        f"| {_table_text(label)} | {_table_text(value)} |"
        for label, value in live_rows
    )

    rendered_source = html.escape(source_text, quote=True)
    lines.extend(
        [
            "",
            "## Input",
            "",
            "<details><summary>Source text</summary><pre><code>"
            f"{rendered_source}"
            "</code></pre></details>",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def write_json_atomic(path: Path, value: BaseModel) -> None:
    """Serialize one validated model and replace its destination atomically."""

    content = (
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    write_bytes_atomic(path, content)


def write_bytes_atomic(path: Path, content: bytes) -> None:
    """Write complete bytes through a same-directory temporary file and rename."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise


def _strict_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Expected a strict integer")
    return value


def _strict_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Expected a strict boolean")
    return value


def _table_text(value: object) -> str:
    return (
        html.escape(str(value), quote=True)
        .replace("|", "&#124;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _validate_github_location(server_url: str, repository: str) -> None:
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", server_url):
        raise ValueError("GitHub server URL is invalid")
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
        repository,
    ):
        raise ValueError("GitHub repository name is invalid")
