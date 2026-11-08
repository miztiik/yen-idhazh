"""Stage one actual machine-helper invocation without external metadata or model work."""

import contextlib
import json
import queue
import subprocess
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from summary_eval_pipeline.contracts import WORKFLOW_VERSION, RunIdentity
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.model_selection import select_model, stage_configuration
from summary_eval_pipeline.settings import PipelineSettings, load_pipeline_settings
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator_cases.contract_examples import REPOSITORY

from summary_eval_tests.test_host_profile_reader_parity import required_bun


@contextlib.contextmanager
def reserved_loopback_listener() -> Iterator[tuple[int, subprocess.Popen[bytes]]]:
    process = subprocess.Popen(
        [
            required_bun(),
            "-e",
            'import {createServer} from "node:net"; const server=createServer(); '
            'await new Promise((resolve,reject)=>{server.once("error",reject);'
            'server.listen(0,"127.0.0.1",resolve)}); const address=server.address(); '
            'if(address===null||typeof address==="string") throw new Error("Missing port"); '
            "console.log(address.port); for await(const part of Bun.stdin.stream()){} "
            "await new Promise((resolve,reject)=>server.close("
            "error=>error?reject(error):resolve()));",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    ready: queue.Queue[bytes] = queue.Queue(1)

    def read_port() -> None:
        assert process.stdout is not None
        ready.put(process.stdout.readline(32))

    reader = threading.Thread(target=read_port, daemon=True)
    reader.start()
    try:
        try:
            encoded = ready.get(timeout=30)
        except queue.Empty:
            raise AssertionError(
                "The owned loopback reservation did not report its port."
            ) from None
        port = int(encoded.strip())
        assert 0 < port < 65536
        yield port, process
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            raise
        reader.join(timeout=10)
        if process.stdout is not None:
            process.stdout.close()


def available_loopback_port() -> int:
    with reserved_loopback_listener() as (port, _):
        return port


def stage_machine_run(
    root: Path,
) -> tuple[StartupPacket, PipelineSettings]:
    pipeline = load_pipeline_settings(REPOSITORY)
    (root / "config" / "summary-evals").mkdir(parents=True)
    (root / "config" / "summary-evals" / "workflow.json").write_bytes(
        (REPOSITORY / "config" / "summary-evals" / "workflow.json").read_bytes()
    )
    authored = json.loads(
        (root / "config" / "summary-evals" / "workflow.json").read_bytes()
    )
    prompt_file = authored["generation_prompt_file"]
    (root / "config" / prompt_file).parent.mkdir(parents=True, exist_ok=True)
    (root / "config" / prompt_file).write_bytes(
        (REPOSITORY / "config" / prompt_file).read_bytes()
    )
    runtime = root / pipeline.output_directory
    stage_configuration(REPOSITORY, runtime, select_model(REPOSITORY, ""))
    listener = runtime / "config" / "hono-server.json"
    settings = json.loads(listener.read_bytes())
    settings["listeners"]["machine"]["port"] = available_loopback_port()
    listener.write_text(json.dumps(settings), encoding="utf-8")
    fingerprint = runtime / "config" / "host-fingerprints.json"
    controls = json.loads(fingerprint.read_bytes())
    controls["metadata_url"] = None
    fingerprint.write_text(json.dumps(controls), encoding="utf-8")
    run = RunIdentity(
        run_id="123456",
        attempt=1,
        git_sha="a" * 40,
        started_at=datetime.now(UTC),
    )
    packet = StartupPacket(
        version=WORKFLOW_VERSION,
        startup_id=create_execution_id(),
        context=StartupContext(
            run_id=f"{run.started_at:%Y-%m-%d}-{run.run_id}",
            pipeline_name=pipeline.pipeline_name,
            task_name=f"{pipeline.task_name}-generation",
        ),
        git_sha=run.git_sha,
        attempt=run.attempt,
        request_id=create_execution_id(),
        correlation_id=create_execution_id(),
        phase="generation",
        run=run,
    )
    return packet, pipeline
