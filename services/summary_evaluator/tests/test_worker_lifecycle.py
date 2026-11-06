"""Prove retention, cancellation and one-worker replacement with real owned processes."""

import asyncio
import json

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY, REQUEST_ID
from summary_evaluator_cases.observe_owned_exit import prove_parent_loss
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import (
    DirectRequest,
    RecordedSupervisor,
    running_service,
    service_settings,
)

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.hhem.contracts.worker_message import ScoreWindow
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH, HHEM_HEALTH_PATH
from summary_evaluator.shared.create_execution_id import create_execution_id

QUEUED_ID = "abcdefab-cdef-4abc-8def-abcdefabcdef"
NEXT_ID = "33333333-3333-4333-8333-333333333333"


def test_parent_loss_stops_even_a_blocked_prediction() -> None:
    prove_parent_loss()


def test_oracle_full_timeout_retains_primary_and_preserves_queued_work() -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        primary, _, other, *_ = inputs.cases
        scores = {reply.id: reply.score for reply in predictions.cases}
        settings = service_settings(evaluation={"timeout_ms": 500})
        async with running_service(
            settings,
            (Scenario(actions=("score", "score", "block")), Scenario(hold_loading=True)),
        ) as service:
            initial = service.worker.model
            assert service.worker.worker is not None
            old_pid = service.worker.worker.pid
            assert (await service.worker.handshake())["phase"] == "loading"
            active = asyncio.create_task(
                service.client.post(
                    EVALUATE_PATH,
                    json={
                        "request_id": REQUEST_ID,
                        "source_text": primary.source_text + " " + other.source_text,
                        "summary_text": primary.summary_text,
                        "full_source_text": other.source_text,
                        "chunk_words": 21,
                        "chunk_overlap_words": 0,
                        "hhem_full": True,
                        "include_window_details": True,
                    },
                )
            )
            for index in range(3):
                assert await service.worker.handshake() == {"phase": "prediction", "index": index}
            queued = []
            for request_id in (QUEUED_ID, NEXT_ID):
                queued.append(
                    asyncio.create_task(
                        service.client.post(
                            EVALUATE_PATH,
                            json={
                                "source_text": primary.source_text,
                                "summary_text": primary.summary_text,
                                "request_id": request_id,
                                "correlation_id": request_id.upper(),
                            },
                        )
                    )
                )
                await service.log.wait("queue", "started", request_id)
            before = {
                identity: reservation.deadline
                for identity, reservation in service.app.state.controller.queue.reservations.items()
            }
            assert len(before) == 2
            refused = DirectRequest(b"PrivateQueueOverflowCanary")
            await refused.run(service.app)
            assert refused.messages[0]["status"] == 429 and refused.body_reads == 0
            health = await service.client.get(HHEM_HEALTH_PATH)
            assert health.status_code == 200 and health.json()["queue_depth"] == 2
            # Replacement loading is held only after the active deadline and joined exit.
            assert await service.worker.handshake(2) == {"phase": "loading", "local_only": True}
            replacing = await service.client.get(HHEM_HEALTH_PATH)
            assert replacing.status_code == 503
            assert replacing.json()["status"] == "replacing"
            assert service.worker.confirmed_before_spawn[0][0] == old_pid
            after = {
                identity: reservation.deadline
                for identity, reservation in service.app.state.controller.queue.reservations.items()
            }
            assert after == before
            response = await active
            assert response.status_code == 504, response.text
            result = EvaluationResult.model_validate_json(response.content)
            assert result.status == "partial"
            assert result.hhem == max(scores["supported"], scores["other-source"])
            assert result.hhem_full is None and result.hhem_delta is None
            assert result.windows.primary is not None and result.windows.primary.scored == 2
            assert result.windows.full is not None and result.windows.full.scored == 0
            assert result.window_details is not None and len(result.window_details.primary) == 2
            assert result.worker is not None and result.worker.pid == old_pid
            assert result.model == initial
            await service.worker.release_prediction(2)
            await service.app.state.controller.loading_task
            assert service.worker.model == initial
            completed = await asyncio.gather(*queued)
            assert [item.status_code for item in completed] == [200, 200]
            assert [item.json()["request_id"] for item in completed] == [QUEUED_ID, NEXT_ID]
            assert [item.json()["correlation_id"] for item in completed] == [
                QUEUED_ID.upper(),
                NEXT_ID.upper(),
            ]
            assert {item.json()["execution_id"] for item in completed} == set(before)
            assert all(item.json()["worker"]["generation"] == 2 for item in completed)
            starts = [
                event.request_id
                for event in service.log.events
                if event.operation == "primary" and event.phase == "started"
            ]
            assert starts == [REQUEST_ID, QUEUED_ID, NEXT_ID]
            assert service.app.state.controller.queue.depth == 0
            assert service.worker.worker is not None and service.worker.worker.pid != old_pid
            assert (
                result.terminal_event_id
                == [
                    event.event_id
                    for event in service.log.events
                    if event.execution_id == result.execution_id
                    and event.operation == "request"
                    and event.phase == "failed"
                ][0]
            )

    asyncio.run(check())


def test_queued_expiry_and_disconnect_do_not_stop_the_active_worker() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        body = {"source_text": case.source_text, "summary_text": case.summary_text}
        settings = service_settings(queue={"wait_timeout_ms": 1000})
        async with running_service(settings, (Scenario(actions=("hold",)),)) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            active = asyncio.create_task(service.client.post(EVALUATE_PATH, json=body))
            assert (await service.worker.handshake())["phase"] == "prediction"
            original = service.worker.worker
            waiting = asyncio.create_task(
                service.client.post(EVALUATE_PATH, json={**body, "request_id": QUEUED_ID})
            )
            await service.log.wait("queue", "started", QUEUED_ID)
            expired = await waiting
            assert expired.status_code == 503
            assert expired.headers["Retry-After"] == str(settings.queue.retry_after_seconds)
            assert expired.json()["errors"][0]["code"] == "QUEUE_TIMEOUT"
            request = DirectRequest(json.dumps({**body, "request_id": NEXT_ID}).encode())
            disconnected = asyncio.create_task(request.run(service.app))
            await service.log.wait("queue", "started", NEXT_ID)
            request.disconnected.set()
            await disconnected
            assert request.messages == []
            assert service.worker.worker == original
            assert not service.worker.confirmed_before_spawn
            assert service.app.state.controller.queue.depth == 0
            await service.worker.release_prediction()
            assert (await active).status_code == 200
            terminal = [
                event
                for event in service.log.events
                if event.operation == "request"
                and event.request_id == NEXT_ID
                and event.phase == "cancelled"
            ]
            assert len(terminal) == 1
            cause = next(
                event
                for event in service.log.events
                if event.event_id == terminal[0].caused_by_event_id
            )
            assert cause.operation == "queue" and cause.phase == "cancelled"

    asyncio.run(check())


def test_active_disconnect_stops_only_its_worker_and_sends_no_response() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        body = {"source_text": case.source_text, "summary_text": case.summary_text}
        async with running_service(scenarios=(Scenario(actions=("block",)), Scenario())) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            request = DirectRequest(json.dumps({**body, "request_id": REQUEST_ID}).encode())
            active = asyncio.create_task(request.run(service.app))
            assert (await service.worker.handshake())["phase"] == "prediction"
            assert service.worker.worker is not None
            old_pid = service.worker.worker.pid
            queued = asyncio.create_task(
                service.client.post(EVALUATE_PATH, json={**body, "request_id": QUEUED_ID})
            )
            await service.log.wait("queue", "started", QUEUED_ID)
            request.disconnected.set()
            await active
            assert request.messages == []
            await service.worker.spawn_events[2].wait()
            assert service.worker.confirmed_before_spawn[0][0] == old_pid
            finished = await queued
            assert finished.status_code == 200
            assert finished.json()["request_id"] == QUEUED_ID
            assert finished.json()["worker"]["generation"] == 2
            terminal = [
                event
                for event in service.log.events
                if event.operation == "request"
                and event.request_id == REQUEST_ID
                and event.phase == "cancelled"
            ]
            assert len(terminal) == 1
            cause = next(
                event
                for event in service.log.events
                if event.event_id == terminal[0].caused_by_event_id
            )
            assert cause.operation == "primary" and cause.phase == "cancelled"

    asyncio.run(check())


def test_primary_timeout_does_not_report_an_unfinished_maximum() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case, _, other, *_ = inputs.cases
        async with running_service(
            service_settings(evaluation={"timeout_ms": 500}),
            (Scenario(actions=("score", "block")), Scenario()),
        ) as service:
            response = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": case.source_text + " " + other.source_text,
                    "summary_text": case.summary_text,
                    "include_window_details": True,
                    "chunk_words": 21,
                    "chunk_overlap_words": 0,
                },
            )
            assert response.status_code == 504, response.text
            result = EvaluationResult.model_validate_json(response.content)
            assert result.status == "failed" and result.hhem is None
            assert result.windows.primary is not None and result.windows.primary.scored == 1
            assert result.window_details is not None and len(result.window_details.primary) == 1
            await service.app.state.controller.loading_task
            assert service.worker.generation == 2

    asyncio.run(check())


def test_stale_reply_is_rejected_over_real_worker_byte_pipes() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        worker = RecordedSupervisor(service_settings(), (Scenario(),))
        try:
            await worker.start()
            command = ScoreWindow(
                version=SCHEMA_VERSION,
                kind="score_window",
                execution_id=create_execution_id(),
                generation=1,
                comparison="primary",
                window_index=0,
                start_word=0,
                end_word=len(case.source_text.split()),
                source_text=case.source_text,
                summary_text=case.summary_text,
            )
            assert worker.channel is not None
            # Put a genuine previous-command reply ahead of the next exchange.
            await asyncio.to_thread(worker.channel.send_bytes, command.model_dump_json().encode())
            next_command = command.model_copy(
                update={
                    "window_index": 1,
                    "start_word": command.end_word,
                    "end_word": command.end_word * 2,
                }
            )
            with pytest.raises(EvaluationFailure) as failure:
                await worker.score(next_command)
            assert failure.value.error.code == "WORKER_PROTOCOL_FAILED"
        finally:
            await worker.stop()
            worker.close_controls()
        assert worker.exit_confirmed and worker.last_exit is not None

    asyncio.run(check())


def test_replacement_identity_mismatch_fails_closed() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        primary, _, full, *_ = inputs.cases
        async with running_service(
            scenarios=(Scenario(actions=("score", "invalid")), Scenario(changed_identity=True))
        ) as service:
            response = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": primary.source_text,
                    "summary_text": primary.summary_text,
                    "full_source_text": full.source_text,
                    "hhem_full": True,
                },
            )
            assert response.status_code == 500, response.text
            result = EvaluationResult.model_validate_json(response.content)
            assert result.status == "partial" and result.hhem is not None
            await service.app.state.controller.loading_task
            health = (await service.client.get(HHEM_HEALTH_PATH)).json()
            assert health["status"] == "failed"
            assert health["failure_code"] == "MODEL_IDENTITY_CHANGED"
            assert health["model"] is None
            assert service.worker.process is None and service.worker.exit_confirmed
            assert service.worker.generation == 2

    asyncio.run(check())


def test_unverifiable_process_handle_cannot_start_a_second_model() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        observed: EvaluationResult | None = None
        observed_status: int | None = None
        observed_health: ServiceHealth | None = None
        generation: int | None = None
        replacement_count: int | None = None
        with pytest.raises(EvaluationFailure) as shutdown:
            async with running_service(scenarios=(Scenario(actions=("block",)),)) as service:
                assert (await service.worker.handshake())["phase"] == "loading"
                active = asyncio.create_task(
                    service.client.post(
                        EVALUATE_PATH,
                        json={
                            "source_text": case.source_text,
                            "summary_text": case.summary_text,
                        },
                    )
                )
                assert (await service.worker.handshake())["phase"] == "prediction"
                process = service.worker.process
                assert process is not None
                # The child really exits; closing its OS handle makes later confirmation fail.
                process.kill()
                process.join(5)
                assert not process.is_alive()
                process.close()
                response = await active
                observed_status = response.status_code
                observed = EvaluationResult.model_validate_json(response.content)
                observed_health = service.app.state.controller.health()
                generation = service.worker.generation
                replacement_count = len(service.worker.confirmed_before_spawn)
        assert shutdown.value.error.code == "WORKER_STOP_FAILED"
        assert observed_status == 500
        assert observed is not None
        codes = {error.code for error in observed.errors}
        assert "WORKER_EXITED" in codes and "WORKER_STOP_FAILED" in codes
        assert observed_health is not None and observed_health.status == "failed"
        assert generation == 1 and replacement_count == 0

    asyncio.run(check())


def test_owned_shutdown_stops_blocked_scoring_and_loading() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        async with running_service(scenarios=(Scenario(actions=("block",)),)) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            active = asyncio.create_task(
                service.client.post(
                    EVALUATE_PATH,
                    json={
                        "source_text": case.source_text,
                        "summary_text": case.summary_text,
                    },
                )
            )
            assert (await service.worker.handshake())["phase"] == "prediction"
        assert (await active).status_code == 503
        assert service.worker.exit_confirmed and service.worker.process is None
        async with running_service(
            scenarios=(Scenario(hold_loading=True),), wait_ready=False
        ) as loading:
            assert (await loading.worker.handshake())["phase"] == "loading"
        assert loading.worker.exit_confirmed and loading.worker.process is None
        async with running_service(wait_ready=False) as starting:
            await starting.worker.spawn_events[1].wait()
        assert starting.worker.exit_confirmed and starting.worker.process is None

    asyncio.run(check())
