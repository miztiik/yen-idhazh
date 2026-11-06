"""Drive the real native exec boundary with an owned parent and a private pre-arm pipe."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def emit(packet: dict[str, str | int]) -> None:
    os.write(sys.stdout.fileno(), (json.dumps(packet) + "\n").encode("ascii"))


def main() -> None:
    if sys.platform != "linux":
        raise SystemExit(1)
    mode = sys.argv[1]
    if mode == "native":
        emit({"stage": "native", "pid": os.getpid(), "parent": os.getppid()})
        while True:
            signal.pause()
    if mode == "gate":
        descriptor = int(sys.argv[2])
        emit({"stage": "unarmed", "pid": os.getpid(), "parent": os.getppid()})
        if os.read(descriptor, 1) != b"1":
            raise SystemExit(1)
        os.close(descriptor)
        command = sys.argv[3:]
        os.execv(command[0], command)
    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root / ".github" / "scripts" / "summary-eval-tests"))
    from summary_eval_pipeline.launch_native import parent_bound_command

    command = parent_bound_command([sys.executable, str(Path(__file__).resolve()), "native"])
    descriptor = int(sys.argv[2])
    gated = descriptor >= 0
    if gated:
        command = [sys.executable, str(Path(__file__).resolve()), "gate", str(descriptor), *command]
    child = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        pass_fds=(descriptor,) if gated else (),
    )
    try:
        emit({"stage": "spawned", "pid": child.pid, "owner": os.getpid()})
        sys.stdin.buffer.read(1)
    finally:
        if child.poll() is None:
            child.terminate()
        try:
            code = child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=10)
            raise
        emit({"stage": "closed", "pid": child.pid, "exit_code": code})


if __name__ == "__main__":
    main()
