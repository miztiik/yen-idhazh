"""Verify a real pinned coverage child using named input, bounded pipes and confirmed exit."""

import argparse
import json
import multiprocessing
import platform
import subprocess
from pathlib import Path

from idhazh.contracts.coverage_model_recording import CoverageRecordingInputs

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.exchange_packets import JSON_ESCAPE_MAX_BYTES
from summary_evaluator.source_coverage.contracts.base import COVERAGE_VERSION
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.worker_message import (
    CoverageBootstrap,
    CoverageCommand,
    CoverageCompleted,
    CoverageReady,
    CoverageReply,
)
from summary_evaluator.source_coverage.load_settings import load_settings
from summary_evaluator.source_coverage.run_worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    api = load_scorer_api_settings(root / "config" / "summary-evals" / "api.json", "coverage")
    settings = load_settings(root, api.listener, api.logging)
    inputs = CoverageRecordingInputs.model_validate_json(
        (root / "tests" / "fixtures" / "summary-evaluation" / "coverage-recording-inputs.json")
        .read_bytes()
    )
    selected = inputs.cases[0]
    bootstrap = CoverageBootstrap(version=COVERAGE_VERSION, settings=settings)
    maximum = len(bootstrap.model_dump_json().encode()) + (
        JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes
    )
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    owner_read, owner_write = context.Pipe(duplex=False)
    process = context.Process(
        target=run_worker, args=(child, owner_read, root, 1, maximum), daemon=False
    )
    process.start()
    child.close()
    owner_read.close()
    try:
        parent.send_bytes(bootstrap.model_dump_json().encode())
        if not parent.poll(settings.worker.startup_timeout_ms / 1000):
            raise ValueError("The real coverage child did not become ready within its bound")
        ready = CoverageReply.model_validate_json(
            parent.recv_bytes(settings.worker.max_reply_bytes)
        )
        if not isinstance(ready.root, CoverageReady) or ready.root.worker.pid != process.pid:
            raise ValueError("The real coverage readiness did not identify the owned process")
        execution_id = create_execution_id()
        parent.send_bytes(
            CoverageCommand(
                version=COVERAGE_VERSION,
                execution_id=execution_id,
                generation=1,
                request=CoverageRequest(
                    source_text=selected.source_text, summary_text=selected.summary_text
                ),
            ).model_dump_json().encode()
        )
        if not parent.poll(settings.evaluation.timeout_ms / 1000):
            raise ValueError("The real coverage child did not complete within its bound")
        completed = CoverageReply.model_validate_json(
            parent.recv_bytes(settings.worker.max_reply_bytes)
        )
        if not isinstance(completed.root, CoverageCompleted) or (
            completed.root.execution_id != execution_id or completed.root.generation != 1
        ):
            raise ValueError("The real coverage child did not return a bound complete result")
        owner_write.close()
        process.join(settings.worker.stop_grace_ms / 1000)
        if process.is_alive():
            process.kill()
            process.join(settings.worker.forced_stop_ms / 1000)
        if process.is_alive() or process.exitcode is None:
            raise ValueError("The actual coverage child exit could not be confirmed")
        print(json.dumps({
            "source_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "platform": {"system": platform.system(), "processor": platform.processor()},
            "input_id": selected.id,
            "ready": ready.root.model_dump(mode="json"),
            "completed": completed.root.model_dump(mode="json"),
            "owned_exit": {"pid": process.pid, "exitcode": process.exitcode},
        }))
    finally:
        owner_write.close()
        if process.is_alive():
            process.kill()
            process.join(settings.worker.forced_stop_ms / 1000)
        parent.close()
        process.close()


if __name__ == "__main__":
    main()
