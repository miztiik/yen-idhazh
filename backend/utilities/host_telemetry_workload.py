"""Can one owned Python worker repeat a bounded local CPU and memory workload?"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format, WriterIdentity
from idhazh.contracts.host_events import ProcessTarget
from idhazh.contracts.host_evidence import (
    EVIDENCE_VERSION,
    ReferenceSample,
    SamplerCompletion,
    WorkloadRequest,
    WorkloadResult,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry.host_evidence_inputs import (
    ComparisonSettings,
    isolated_workspace,
    read_model,
    settings,
    write_document,
    write_json,
)
from utilities.host_telemetry_reference import (
    endpoint,
    host_row,
    identity,
    sample_population,
    window_cells,
)


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def execute_work(buffer: bytearray, config: ComparisonSettings) -> str:
    digest = hashlib.sha256()
    for _ in range(config.workload_iterations):
        digest.update(buffer)
    return digest.hexdigest()


def sampler(workspace: Path, sequence: int) -> None:
    native, compare, _ = settings()
    root = workspace / f"reference/samples-{sequence}"
    root.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + compare.worker_timeout_seconds
    taken = 0
    while not (root / "stop").exists():
        if time.monotonic() >= deadline:
            raise ValueError("reference sampler deadline expired")
        record = sample_population(root / f"capture-{taken}", native, compare, now())
        write_document(root / f"sample-{taken}.json", record)
        taken += 1
        time.sleep(compare.sample_interval_seconds)
    write_document(root / "count.json", SamplerCompletion(version=EVIDENCE_VERSION, samples=taken))


def worker(workspace: Path, day: str, run_id: str, git_sha: str, attempt: int) -> None:
    if platform.system() != "Linux":
        raise ValueError("live evidence requires Linux; fixture success is not live evidence")

    native, compare, _ = settings()
    target = identity(os.getpid(), native)
    buffer = bytearray(compare.workload_memory_mib * 1024 * 1024)
    # Touch the complete bounded allocation before references and keep it alive.
    buffer[:] = b"x" * len(buffer)
    write_document(workspace / "worker.json", target)
    sequence = 1
    deadline = time.monotonic() + compare.worker_timeout_seconds
    max_sequence = compare.calibration_runs + 2 + compare.paired_runs * 2
    while time.monotonic() < deadline and sequence <= max_sequence:
        path = workspace / f"requests/{sequence}.json"
        if not path.exists():
            time.sleep(native.limits.poll_ms / 1000)
            continue
        request = read_model(path, WorkloadRequest, native.limits.max_command_bytes)
        if request.sequence != sequence:
            raise ValueError("worker command is out of order")
        if request.mode == "stop":
            write_document(workspace / "worker-stopped.json", target)
            return
        reference = request.mode == "reference"
        sample: subprocess.Popen[bytes] | None = None
        root = workspace / "reference"
        whole_started, whole_cpu = time.perf_counter(), time.process_time()
        whole_utc = datetime.now(UTC)
        child_before = child_cpu()
        opening = endpoint(native, root / f"endpoints-{sequence}/open") if reference else None
        try:
            if reference:
                with (workspace / f"sampler-{sequence}.log").open("wb") as log:
                    sample = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "utilities.host_telemetry_workload",
                            "sample",
                            "--workspace",
                            str(workspace),
                            "--sequence",
                            str(sequence),
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                    )
                write_document(workspace / f"sampler-{sequence}.json", identity(sample.pid, native))
                wait_for(
                    workspace / f"reference/samples-{sequence}/sample-0.json",
                    compare.worker_timeout_seconds,
                    native.limits.poll_ms,
                    child=sample,
                )
            started, cpu = time.perf_counter(), time.process_time()
            digest = execute_work(buffer, compare)
            # Fixed, predeclared pacing makes second-resolution coverage unambiguous.
            remaining = compare.workload_min_seconds - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)
            wall, cpu_seconds = time.perf_counter() - started, time.process_time() - cpu
            host = host_row(root, native, day=day, run_id=run_id, now=now()) if reference else None
            files: list[str] = []
            if host is not None:
                state = root / "state"
                paths = ledger.persist(
                    state,
                    [host],
                    ledger=LedgerName.HOST_FINGERPRINT,
                    covers=day,
                    identity=WriterIdentity(
                        run_id=run_id,
                        attempt=attempt,
                        job=ServerJob.WORK,
                        shard=0,
                        producer="telemetry.silicon",
                        git_sha=git_sha,
                    ),
                    fmt=Format.JSON,
                )
                if not paths:
                    raise ValueError("Python reference did not persist its separate raw file")
                files = [p.relative_to(workspace).as_posix() for p in paths]
            population: tuple[ProcessTarget, ...] = ()
            samples = 0
            if sample is not None:
                write_json(workspace / f"reference/samples-{sequence}/stop", True)
                sample.wait(timeout=compare.worker_timeout_seconds)
                if sample.returncode != 0:
                    raise ValueError("bounded reference sampler failed")
                sample = None
                captured = read_model(
                    workspace / f"reference/samples-{sequence}/sample-0.json",
                    ReferenceSample,
                    native.limits.max_result_bytes,
                )
                population = captured.population
                samples = read_model(
                    workspace / f"reference/samples-{sequence}/count.json",
                    SamplerCompletion,
                    native.limits.max_result_bytes,
                ).samples
            closing = endpoint(native, root / f"endpoints-{sequence}/close") if reference else None
            child_after = child_cpu()
            finished = time.perf_counter()
            clock_skew = abs(
                (datetime.now(UTC) - whole_utc).total_seconds() - (finished - whole_started)
            )
            result = WorkloadResult(
                version=EVIDENCE_VERSION,
                sequence=sequence,
                mode=request.mode,
                target=target,
                wall_seconds=wall,
                clock_skew_seconds=clock_skew,
                cpu_seconds=cpu_seconds,
                instrument_wall_seconds=finished - whole_started - wall,
                instrument_cpu_seconds=(
                    time.process_time() - whole_cpu - cpu_seconds + child_after - child_before
                ),
                digest=digest,
                iterations=compare.workload_iterations,
                samples=samples,
                cells=window_cells(opening, closing)
                if opening is not None and closing is not None
                else None,
                host=host,
                population=population,
                reference_files=tuple(files),
            )
            write_document(workspace / f"responses/{sequence}.json", result)
        finally:
            if sample is not None and sample.poll() is None:
                sample.terminate()
                sample.wait(timeout=compare.worker_timeout_seconds)
        sequence += 1
        deadline = time.monotonic() + compare.worker_timeout_seconds
    raise ValueError("owned workload worker deadline expired")


def child_cpu() -> float:
    if sys.platform == "linux":
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return usage.ru_utime + usage.ru_stime
    raise ValueError("reference child CPU measurements require Linux")


def wait_for(
    path: Path,
    timeout: float,
    poll_ms: int,
    *,
    child: subprocess.Popen[bytes] | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if child is not None and child.poll() is not None:
            raise ValueError(
                f"required evidence {path.name}: producer exited with code {child.returncode}"
            )
        if time.monotonic() >= deadline:
            raise ValueError(f"required evidence did not arrive: {path.name}")
        time.sleep(poll_ms / 1000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verb", choices=("worker", "sample"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--day")
    parser.add_argument("--run-id")
    parser.add_argument("--git-sha")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--sequence", type=int)
    args = parser.parse_args()
    workspace = isolated_workspace(args.workspace)
    if args.verb == "sample":
        if args.sequence is None:
            parser.error("sample requires --sequence")
        sampler(workspace, args.sequence)
    else:
        if not all((args.day, args.run_id, args.git_sha, args.attempt)):
            parser.error("worker requires day, run-id, git-sha and attempt")
        worker(workspace, args.day, args.run_id, args.git_sha, args.attempt)


if __name__ == "__main__":
    main()
