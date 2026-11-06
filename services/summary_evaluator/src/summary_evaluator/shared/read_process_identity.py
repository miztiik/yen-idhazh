"""Which start tick belongs to the exact owned scoring PID?"""

import os
import sys
from pathlib import Path

from summary_evaluator.shared.contracts.worker_identity import PinUnavailableReason, WorkerIdentity


def read_process_identity(generation: int, max_bytes: int) -> WorkerIdentity:
    """Read one bounded Linux stat file, or name why its pin is unavailable."""
    pid = os.getpid()
    reason: PinUnavailableReason | None = None
    ticks: str | None = None
    if sys.platform != "linux":
        reason = "unsupported_platform"
    else:
        try:
            with Path(f"/proc/{pid}/stat").open("rb") as stream:
                data = stream.read(max_bytes + 1)
            if len(data) > max_bytes:
                reason = "process_identity_too_large"
            else:
                prefix, separator, suffix = data.rpartition(b") ")
                fields = suffix.split()
                if (
                    not separator
                    or not prefix.startswith(str(pid).encode("ascii") + b" (")
                    or len(fields) <= 19
                    or not fields[19].isdigit()
                ):
                    reason = "process_identity_invalid"
                else:
                    ticks = fields[19].decode("ascii")
        except FileNotFoundError:
            reason = "process_not_found"
        except OSError:
            reason = "process_read_failed"
    return WorkerIdentity(
        generation=generation,
        pid=pid,
        start_ticks=ticks,
        pin_unavailable_reason=reason,
    )
