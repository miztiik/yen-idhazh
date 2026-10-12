"""What wall time and executable bytes did the pinned native release build cost?"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import time
from pathlib import Path

from idhazh.contracts.host_evidence import EVIDENCE_VERSION, CommandMeasurement
from idhazh.telemetry.host_evidence_inputs import (
    ROOT,
    read_bytes,
    resolve,
    settings,
    write_document,
)

BUILD_COMMAND = (
    "cargo",
    "build",
    "--locked",
    "--offline",
    "--release",
    "--bin",
    "idhazh-host-telemetry",
)


def measure(output: Path, git_sha: str) -> CommandMeasurement:
    native, config, _ = settings()
    if not output.absolute().is_relative_to(ROOT / "backend/var") or ".." in output.parts:
        raise ValueError("compile evidence must live in a task-owned generated root")
    resolve(ROOT, output.absolute().relative_to(ROOT).as_posix())
    target = ROOT / "backend/var/rust-host-telemetry"
    if Path(os.environ.get("CARGO_TARGET_DIR", target)).resolve() != target.resolve():
        raise ValueError("build target must be the declared generated native root")
    revision = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=config.worker_timeout_seconds,
        )
        .stdout.decode("ascii")
        .strip()
    )
    if revision != git_sha:
        raise ValueError("compile revision differs from the actual checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    started = time.perf_counter()
    with log_path.open("xb") as log:
        child = subprocess.Popen(
            BUILD_COMMAND,
            cwd=ROOT / "backend/rust/host-telemetry",
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            while child.poll() is None:
                if log_path.stat().st_size > config.max_command_output_bytes:
                    raise ValueError("native build log exceeded its configured cap")
                if time.perf_counter() - started >= config.build_timeout_seconds:
                    raise ValueError("native build exceeded its configured deadline")
                time.sleep(native.limits.poll_ms / 1000)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=native.limits.drain_timeout_ms / 1000)
    wall = time.perf_counter() - started
    with output.with_suffix(".rustc").open("xb") as log:
        subprocess.run(
            ["rustc", "+1.95.0", "--version"],
            stdout=log,
            check=True,
            cwd=ROOT / "backend/rust/host-telemetry",
            timeout=config.worker_timeout_seconds,
        )
    rustc = (
        read_bytes(output.with_suffix(".rustc"), config.max_command_output_bytes).decode().strip()
    )
    binary = ROOT / "backend/var/rust-host-telemetry/release/idhazh-host-telemetry"
    evidence = CommandMeasurement(
        version=EVIDENCE_VERSION,
        command=BUILD_COMMAND,
        wall_seconds=wall,
        exit_code=child.returncode,
        executable_bytes=binary.stat().st_size if binary.is_file() else None,
        executable_sha256=hashlib.sha256(read_bytes(binary, config.max_artifact_bytes)).hexdigest()
        if binary.is_file()
        else None,
        rustc=rustc,
        git_sha=git_sha,
    )
    write_document(output, evidence)
    if evidence.exit_code != 0:
        raise ValueError("native release compilation failed; inspect the retained local log")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()
    measure(args.output, args.git_sha)


if __name__ == "__main__":
    main()
