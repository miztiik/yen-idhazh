"""Prove private input cannot escape through responses, events or failure diagnostics."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import DirectRequest, running_service, service_settings

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    EVALUATE_PATH,
    HHEM_HEALTH_PATH,
)


def test_valid_invalid_and_unknown_name_canaries_never_reach_public_output(
    capfd: pytest.CaptureFixture[str],
) -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        private = inputs.cases[3]
        canaries = [
            "PrivateSourceCanary",
            "PrivateSummaryCanary",
            "UnknownPropertyCanary",
            "InvalidValueCanary",
            "MalformedJsonCanary",
            "OriginCanary",
            "HostCanary",
        ]
        async with running_service() as service:
            response = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": private.source_text,
                    "summary_text": private.summary_text,
                },
            )
            assert response.status_code == 200, response.text
            public = [response.text]
            for body in (
                {
                    "source_text": private.source_text,
                    "summary_text": private.summary_text,
                    "UnknownPropertyCanary": "InvalidValueCanary",
                },
                {
                    "source_text": private.source_text,
                    "summary_text": private.summary_text,
                    "chunk_words": "InvalidValueCanary",
                },
                {"source_text": ["InvalidValueCanary"], "summary_text": private.summary_text},
            ):
                failed = await service.client.post(EVALUATE_PATH, json=body)
                assert failed.status_code == 400
                public.append(failed.text)
            unknown = json.loads(public[1])
            assert unknown["errors"][0]["field"] is None
            malformed = await service.client.post(
                EVALUATE_PATH,
                content=b'{"MalformedJsonCanary":',
                headers={"Content-Type": "application/json"},
            )
            assert malformed.status_code == 400
            assert malformed.json()["errors"][0]["code"] == "INVALID_JSON"
            public.append(malformed.text)
            for headers, code in (
                (((b"origin", b"https://OriginCanary.invalid"),), "ORIGIN_FORBIDDEN"),
                (((b"host", b"HostCanary.invalid"),), "HOST_FORBIDDEN"),
            ):
                request = DirectRequest(b"PrivateSourceCanary", headers=headers)
                await request.run(service.app)
                assert request.messages[0]["status"] == 403
                assert request.body_reads == 0
                assert json.loads(request.messages[1]["body"])["errors"][0]["code"] == code
                public.append(request.messages[1]["body"].decode())
            output = "\n".join(public) + service.log.getvalue()
            for canary in canaries:
                assert canary not in output
        captured = capfd.readouterr()
        for canary in canaries:
            assert canary not in captured.out + captured.err

    asyncio.run(check())


def test_streamed_overflow_slow_input_and_capacity_are_bounded_before_parsing() -> None:
    async def check() -> None:
        settings = service_settings(
            listener={"max_body_bytes": 1024, "body_read_timeout_ms": 1000},
            queue={"capacity": 1},
        )
        async with running_service(settings) as service:

            async def overflow() -> AsyncIterator[bytes]:
                yield b"PrivateOverflowCanary" + b"x" * 800
                yield b"x" * 800

            overflowed = await service.client.post(
                EVALUATE_PATH,
                content=overflow(),
                headers={"Content-Type": "application/json"},
            )
            assert overflowed.status_code == 413
            assert "PrivateOverflowCanary" not in overflowed.text
            entered = asyncio.Event()
            never = asyncio.Event()

            async def slow() -> AsyncIterator[bytes]:
                yield b"{"
                entered.set()
                await never.wait()
                yield b"}"

            slow_task = asyncio.create_task(
                service.client.post(
                    EVALUATE_PATH,
                    content=slow(),
                    headers={"Content-Type": "application/json"},
                )
            )
            await entered.wait()
            unread = DirectRequest(b"PrivateUnreadCapacityCanary")
            await unread.run(service.app)
            assert unread.body_reads == 0
            assert unread.messages[0]["status"] == 429
            headers = dict(unread.messages[0]["headers"])
            assert headers[b"retry-after"] == b"2"
            health = await service.client.get(HHEM_HEALTH_PATH)
            assert health.status_code == 200
            assert health.json()["queue_depth"] == 1
            expired = await slow_task
            assert expired.status_code == 408
            assert expired.json()["errors"][0]["code"] == "INPUT_TIMEOUT"
            assert service.app.state.controller.queue.depth == 0
            for headers in (
                {"Content-Type": "text/plain"},
                {"Content-Type": "application/json; charset=iso-8859-1"},
                {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            ):
                response = await service.client.post(
                    EVALUATE_PATH, content=b"PrivateEncodingCanary", headers=headers
                )
                assert response.status_code == 415
                assert "PrivateEncodingCanary" not in response.text
            invalid_utf8 = await service.client.post(
                EVALUATE_PATH,
                content=b"\xff",
                headers={"Content-Type": "application/json"},
            )
            assert invalid_utf8.status_code == 415

    asyncio.run(check())


def test_terminal_logging_failure_preserves_a_score_without_a_false_log_link(
    capfd: pytest.CaptureFixture[str],
) -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        case = inputs.cases[3]
        async with running_service() as service:
            old_pid = service.worker.worker.pid if service.worker.worker is not None else None
            service.log.fail_terminal = True
            response = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": case.source_text,
                    "summary_text": case.summary_text,
                },
            )
            assert response.status_code == 500, response.text
            result = EvaluationResult.model_validate_json(response.content)
            assert result.status == "partial"
            assert result.hhem == predictions.cases[3].score
            assert result.terminal_event_id is None
            assert any(error.code == "LOGGING_FAILED" for error in result.errors)
            assert service.worker.last_exit is not None and service.worker.last_exit[0] == old_pid
            assert service.worker.exit_confirmed and service.worker.process is None
            assert service.app.state.controller.health().status == "failed"
            assert service.worker.generation == 1
            assert "PrivateLoggingFailureCanary" not in response.text + service.log.getvalue()
            assert "PrivateSourceCanary" not in response.text + service.log.getvalue()
        captured = capfd.readouterr()
        assert "PrivateLoggingFailureCanary" not in captured.out + captured.err
        assert "PrivateSourceCanary" not in captured.out + captured.err

    asyncio.run(check())


def test_unavailable_file_mirror_does_not_change_a_completed_score(tmp_path: Path) -> None:
    async def check() -> None:
        occupied = tmp_path / "occupied"
        occupied.write_text("A real file prevents opening the log directory.", encoding="ascii")
        inputs, predictions, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        async with running_service(log_directory=occupied) as service:
            response = await service.client.post(
                EVALUATE_PATH,
                json={"source_text": case.source_text, "summary_text": case.summary_text},
            )
            assert response.status_code == 200
            result = EvaluationResult.model_validate_json(response.content)
            assert result.status == "complete" and result.hhem == predictions.cases[0].score
            assert not result.errors
            health = await service.client.get(API_HEALTH_PATH)
            assert health.status_code == 200 and not health.json()["log_available"]
            assert any(
                envelope.type == "fastapi-server.log.unavailable"
                for envelope in service.log.envelopes
            )

    asyncio.run(check())


def test_child_exception_text_is_not_forwarded(
    capfd: pytest.CaptureFixture[str],
) -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[3]
        async with running_service(scenarios=(Scenario(actions=("raise",)), Scenario())) as service:
            response = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": case.source_text,
                    "summary_text": case.summary_text,
                },
            )
            assert response.status_code == 500
            assert response.json()["errors"][0]["code"] == "MODEL_SCORING_FAILED"
            for canary in ("PrivateSourceCanary", "PrivateSummaryCanary"):
                assert canary not in response.text + service.log.getvalue()
        captured = capfd.readouterr()
        assert "PrivateSourceCanary" not in captured.out + captured.err
        assert "PrivateSummaryCanary" not in captured.out + captured.err

    asyncio.run(check())


def test_disconnect_while_reading_releases_capacity_without_an_http_response() -> None:
    class InterruptedBody(DirectRequest):
        async def receive(self) -> dict[str, object]:
            if not self.body_reads:
                self.body_reads += 1
                entered.set()
                return {"type": "http.request", "body": b"{", "more_body": True}
            await self.disconnected.wait()
            return {"type": "http.disconnect"}

    async def check() -> None:
        async with running_service() as service:
            request = InterruptedBody(b"PrivateDisconnectedBodyCanary")
            active = asyncio.create_task(request.run(service.app))
            await entered.wait()
            assert service.app.state.controller.queue.depth == 1
            request.disconnected.set()
            await active
            assert request.messages == []
            assert service.app.state.controller.queue.depth == 0
            terminal = [
                event
                for event in service.log.events
                if event.operation == "request" and event.phase == "cancelled"
            ]
            assert len(terminal) == 1
            assert terminal[0].details.errors is not None
            assert terminal[0].details.errors[0].code == "CLIENT_DISCONNECTED"

    entered = asyncio.Event()
    asyncio.run(check())
