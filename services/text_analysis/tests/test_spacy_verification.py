"""Which strict artifact and summary invariants protect the live verification?"""

import signal
import unittest

from pydantic import ValidationError

from declare_spacy_verification import (
    GITHUB_STEP_SUMMARY_MAX_BYTES,
    FailedVerificationReport,
    LiveCheckEvidence,
    SuccessfulVerificationReport,
    SummaryLimitExceeded,
    classify_cleanup,
    render_summary,
    validate_native_evidence,
)


def _native_payloads(source_text: str = "A source sentence.") -> dict[str, object]:
    return {
        "analysis_request": {
            "text": source_text,
            "language": "en",
            "model_profile": "md",
            "features": ["entities"],
        },
        "health_response": {
            "enabled": True,
            "status": "ready",
            "active_requests": 0,
            "max_concurrent_requests": 2,
            "pool_ready": True,
            "spacy_version": "3.8.18",
            "default_features": ["entities"],
            "allowed_features": ["entities"],
            "languages": [
                {
                    "language": "en",
                    "enabled": True,
                    "default_profile": "md",
                    "supported_features": ["entities"],
                    "profiles": [
                        {
                            "profile": "md",
                            "package": "model_package",
                            "model_version": "1.0.0",
                        }
                    ],
                }
            ],
        },
        "analysis_response": {
            "status": "complete",
            "language": "en",
            "model": {
                "profile": "md",
                "package": "model_package",
                "model_version": "1.0.0",
                "spacy_version": "3.8.18",
            },
            "features": [
                {
                    "feature": "entities",
                    "status": "complete",
                    "data": {"mentions": []},
                    "error": None,
                }
            ],
        },
    }


class VerificationReportTests(unittest.TestCase):
    def test_success_report_forbids_failure_and_old_evidence_keys(self) -> None:
        payload = {
            "version": "2026-11-08",
            "conclusion": "success",
            "commit_sha": "a" * 40,
            "run_id": "17",
            "run_attempt": 2,
            "cleanup": "confirmed",
        }
        report = SuccessfulVerificationReport.model_validate(payload)
        self.assertEqual(report.model_dump(mode="json"), payload)
        schema = SuccessfulVerificationReport.model_json_schema()
        self.assertEqual(schema["version"], "2026-11-08")
        self.assertEqual(
            schema["changelog"],
            [
                {
                    "version": "2026-11-08",
                    "change": (
                        "Split native API evidence from the verification outcome "
                        "and make cleanup semantic."
                    ),
                }
            ],
        )

        with self.assertRaises(ValidationError):
            SuccessfulVerificationReport.model_validate(
                {**payload, "failure_code": "VERIFICATION_FAILED"}
            )
        with self.assertRaises(ValidationError):
            SuccessfulVerificationReport.model_validate(
                {**payload, "selected_ref": "refs/heads/example"}
            )

    def test_failure_report_requires_one_declared_safe_code(self) -> None:
        report = FailedVerificationReport.model_validate(
            {
                "version": "2026-11-08",
                "conclusion": "failure",
                "commit_sha": "b" * 40,
                "run_id": "18",
                "run_attempt": 1,
                "cleanup": "unconfirmed",
                "failure_code": "PROCESS_GROUP_NOT_STOPPED",
            }
        )
        self.assertEqual(report.failure_code, "PROCESS_GROUP_NOT_STOPPED")
        with self.assertRaises(ValidationError):
            FailedVerificationReport.model_validate(
                {
                    **report.model_dump(mode="json"),
                    "exercise": {},
                }
            )

    def test_sigterm_cleanup_is_semantic_and_persists_no_exit_code(self) -> None:
        cleanup = classify_cleanup(
            process_started=True,
            terminate_sent=True,
            kill_sent=False,
            exit_confirmed=True,
            exit_code=-signal.SIGTERM,
        )
        self.assertEqual(cleanup.status, "confirmed")
        self.assertIsNone(cleanup.failure_code)
        report = SuccessfulVerificationReport(
            commit_sha="c" * 40,
            run_id="19",
            run_attempt=1,
        )
        self.assertNotIn("exit_code", report.model_dump(mode="json"))


class NativeEvidenceTests(unittest.TestCase):
    def test_native_payloads_validate_separately_and_reject_extra_fields(self) -> None:
        native = validate_native_evidence(_native_payloads())
        self.assertEqual(native.request.text, "A source sentence.")
        self.assertEqual(native.health.status, "ready")
        self.assertEqual(native.analysis.status, "complete")

        invalid = _native_payloads()
        request = dict(invalid["analysis_request"])
        request["selected_ref"] = "refs/heads/example"
        invalid["analysis_request"] = request
        with self.assertRaises(ValidationError):
            validate_native_evidence(invalid)


class VerificationSummaryTests(unittest.TestCase):
    def test_source_text_is_html_escaped_with_quotes(self) -> None:
        source_text = '<tag title="x\'&">|line\nnext'
        native = validate_native_evidence(_native_payloads(source_text))
        summary = render_summary(
            conclusion="success",
            failure_code=None,
            commit_sha="d" * 40,
            run_id="20",
            cleanup="confirmed",
            source_text=source_text,
            server_url="https://github.com",
            repository="sample/project",
            native=native,
            checks=LiveCheckEvidence(
                active_requests=2,
                capacity=2,
                busy_http_status=429,
                busy_queued=False,
                warm_model_load_ms=0,
            ),
        ).decode("utf-8")
        self.assertIn(
            "&lt;tag title=&quot;x&#x27;&amp;&quot;&gt;|line\nnext",
            summary,
        )
        self.assertNotIn(source_text, summary)
        self.assertIn("<details><summary>Source text</summary>", summary)

    def test_summary_refuses_the_named_platform_limit(self) -> None:
        native = validate_native_evidence(_native_payloads("x"))
        with self.assertRaises(SummaryLimitExceeded):
            render_summary(
                conclusion="success",
                failure_code=None,
                commit_sha="e" * 40,
                run_id="21",
                cleanup="confirmed",
                source_text="x" * GITHUB_STEP_SUMMARY_MAX_BYTES,
                server_url="https://github.com",
                repository="sample/project",
                native=native,
                checks=LiveCheckEvidence(
                    active_requests=2,
                    capacity=2,
                    busy_http_status=429,
                    busy_queued=False,
                    warm_model_load_ms=0,
                ),
            )


if __name__ == "__main__":
    unittest.main()
