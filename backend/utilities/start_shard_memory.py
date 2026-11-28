"""Start the native shard memory sampler and verify its first sample before returning."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from utilities.memory_profiling_control import resolve

_LOG = Path("memory-sampler.log")
_READY = Path("backend/var/shard-memory/ready")
_START_GRACE_SECONDS = 2.0
_LOG_LIMIT_BYTES = 1 << 20
_LOG_TAIL_LINES = 20


def main() -> None:
    if not resolve(os.environ.get("MEMORY_PROFILING", "inherit"), Path("config")):
        print("Shard memory diagnostics configured off")
        return
    if _READY.parent.exists():
        raise SystemExit("shard memory control already exists")
    with _LOG.open("wb") as log:
        child = subprocess.Popen(
            [
                "bun", "run", "--no-install", "services/host-probes/src/index.ts",
                "--sample-shard-memory",
            ],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
    try:
        child.wait(timeout=_START_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        if _READY.is_file():
            print("TypeScript shard memory sampler started")
            return
        child.terminate()
        raise SystemExit(
            "TypeScript shard memory sampler did not confirm its first sample"
        ) from None
    with _LOG.open("rb") as log:
        text = log.read(_LOG_LIMIT_BYTES).decode("utf-8", errors="replace")
    tail = "\n".join(text.splitlines()[-_LOG_TAIL_LINES:])
    raise SystemExit(f"the sampler exited {child.returncode} before it took a sample\n{tail}")


if __name__ == "__main__":
    main()
