"""Drive the real caller's pipe ownership without opening an HTTP listener."""

import os
import sys
import threading

from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.contracts.workflow_control import (
    ApiReady,
    HostReady,
    ServiceStopped,
    StartupPacket,
)
from hhem_evaluator.resolve_ids import create_execution_id
from hhem_evaluator.serve_owned_api import watch_parent_lifetime


def main() -> None:
    packet = StartupPacket.model_validate_json(sys.stdin.buffer.readline(16384))
    mode = sys.argv[1]
    if mode == "early_exit":
        return
    ready: ApiReady | HostReady
    if mode == "invalid_event":
        ready = ApiReady(
            version=SCHEMA_VERSION,
            kind="ready",
            service="hhem",
            startup_id=packet.startup_id,
            pid=os.getpid(),
            service_instance_id=create_execution_id(),
        )
        sys.stderr.write("PrivateRawChildCanary\n")
        sys.stderr.flush()
    else:
        ready = HostReady(
            version=SCHEMA_VERSION,
            kind="ready",
            service="host",
            startup_id=create_execution_id() if mode == "mismatch" else packet.startup_id,
            pid=os.getpid(),
            host="127.0.0.1",
            port=3011,
            lifecycle_timeout_ms=1000,
        )
    sys.stdout.write(ready.model_dump_json() + "\n")
    sys.stdout.flush()
    if mode in ("parent_loss", "parent_loss_blocked"):
        stop, finished = threading.Event(), threading.Event()
        threading.Thread(
            target=watch_parent_lifetime,
            args=(sys.stdin.buffer, stop.set, finished, 500),
            daemon=True,
        ).start()
        stop.wait()
        if mode == "parent_loss_blocked":
            threading.Event().wait()
        finished.set()
    else:
        sys.stdin.buffer.read(1)
    if mode == "blocked_close":
        threading.Event().wait()
    stopped = ServiceStopped(
        version=SCHEMA_VERSION,
        kind="stopped",
        service=ready.service,
        startup_id=packet.startup_id,
        pid=os.getpid(),
        clean=True,
        worker_exit_confirmed=None,
    )
    sys.stdout.write(stopped.model_dump_json() + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
