"""Do real byte-pipe workers retain genuine metric parity and stop with their actual owner?"""

import json
import multiprocessing
import os
from pathlib import Path

from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_cases import CoverageScenario, run_recorded_coverage_worker
from summary_evaluator_cases.coverage_recordings import coverage_settings, read_coverage_recordings
from summary_evaluator_cases.observe_owned_exit import observe_exit

from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.exchange_packets import JSON_ESCAPE_MAX_BYTES, ByteChannel
from summary_evaluator.source_coverage.contracts.base import COVERAGE_VERSION
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.contracts.worker_message import (
    CoverageBootstrap,
    CoverageCommand,
    CoverageCompleted,
    CoverageReady,
    CoverageReply,
)


def test_real_worker_byte_pipe_replays_exact_metrics_and_owned_identity() -> None:
    inputs, recording = read_coverage_recordings()
    settings = coverage_settings()
    bootstrap = CoverageBootstrap(version=COVERAGE_VERSION, settings=settings)
    maximum = len(bootstrap.model_dump_json().encode()) + (
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner_read, owner_write = context.Pipe(duplex=False)
    control_parent, control_child = context.Pipe(duplex=True)
    process = context.Process(
        target=run_recorded_coverage_worker,
        args=(child, owner_read, REPOSITORY, 1, maximum, CoverageScenario(), control_child),
        daemon=False,
    )
    process.start()
    child.close()
    owner_read.close()
    control_child.close()
    try:
        parent.send_bytes(bootstrap.model_dump_json().encode())
        assert parent.poll(30)
        ready = CoverageReply.model_validate_json(
            parent.recv_bytes(settings.worker.max_reply_bytes)
        )
        assert isinstance(ready.root, CoverageReady)
        assert ready.root.worker.pid == process.pid
        assert ready.root.worker.generation == 1
        assert ready.root.model.loaded_revision == recording.provenance.loaded_model_revision
        request = CoverageRequest(
            source_text=inputs.cases[0].source_text, summary_text=inputs.cases[0].summary_text
        )
        execution_id = create_execution_id()
        parent.send_bytes(
            CoverageCommand(
                version=COVERAGE_VERSION, execution_id=execution_id, generation=1, request=request
            ).model_dump_json().encode()
        )
        assert parent.poll(30)
        result = CoverageReply.model_validate_json(
            parent.recv_bytes(settings.worker.max_reply_bytes)
        )
        assert isinstance(result.root, CoverageCompleted)
        assert result.root.execution_id == execution_id
        assert result.root.metrics.model_dump(mode="json") == recording.cases[0].expected_metrics
        assert not result.root.warnings
        owner_write.close()
        process.join(5)
        assert not process.is_alive() and process.exitcode == 0
    finally:
        owner_write.close()
        if process.is_alive():
            process.kill()
            process.join(5)
        parent.close()
        control_parent.close()
        process.close()


def _vanishing_coverage_owner(control: ByteChannel, encoded: bytes, root: Path) -> None:
    settings = CoverageSettings.model_validate_json(encoded)
    bootstrap = CoverageBootstrap(version=COVERAGE_VERSION, settings=settings)
    maximum = len(bootstrap.model_dump_json().encode()) + (
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner_read, owner_write = context.Pipe(duplex=False)
    phase_parent, phase_child = context.Pipe(duplex=True)
    process = context.Process(
        target=run_recorded_coverage_worker,
        args=(
            child, owner_read, root, 1, maximum,
            CoverageScenario(block_dimension="fluency"), phase_child,
        ),
        daemon=False,
    )
    process.start()
    child.close()
    owner_read.close()
    phase_child.close()
    parent.send_bytes(bootstrap.model_dump_json().encode())
    assert parent.poll(30)
    ready = CoverageReply.model_validate_json(parent.recv_bytes(settings.worker.max_reply_bytes))
    assert isinstance(ready.root, CoverageReady)
    inputs, _ = read_coverage_recordings()
    parent.send_bytes(
        CoverageCommand(
            version=COVERAGE_VERSION,
            execution_id=create_execution_id(),
            generation=1,
            request=CoverageRequest(
                source_text=inputs.cases[0].source_text, summary_text=inputs.cases[0].summary_text
            ),
        ).model_dump_json().encode()
    )
    assert phase_parent.poll(30)
    phase_parent.recv_bytes(1024)
    assert phase_parent.poll(30)
    assert json.loads(phase_parent.recv_bytes(1024))["dimension"] == "fluency"
    control.send_bytes(json.dumps({"pid": ready.root.worker.pid}).encode())
    control.recv_bytes(1)
    os._exit(0)


def test_actual_owner_exit_stops_a_blocked_coverage_model_call() -> None:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner = context.Process(
        target=_vanishing_coverage_owner,
        args=(child, coverage_settings().model_dump_json().encode(), REPOSITORY),
        daemon=False,
    )
    observation = None
    owner.start()
    child.close()
    try:
        assert parent.poll(30)
        pid = json.loads(parent.recv_bytes(1024))["pid"]
        observation = observe_exit(pid)
        parent.send_bytes(b"1")
        owner.join(5)
        assert not owner.is_alive() and owner.exitcode == 0
        assert observation.wait(5), "The actual blocked coverage child survived its owner"
    finally:
        if owner.is_alive():
            owner.kill()
            owner.join(5)
        if observation is not None:
            if not observation.wait(0):
                observation.stop()
                assert observation.wait(5)
            observation.close()
        parent.close()
        owner.close()
