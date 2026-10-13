"""Read a bounded, PID-reuse-safe identity for a native monitor target."""

from pathlib import Path

from idhazh.contracts.host_events import ProcessTarget
from idhazh.telemetry.host_evidence_inputs import NativeSettings, read_bytes

# Procfs stat's tail starts at field 3, after the final comm bracket.
START_TICKS_TAIL = 19


def identity(pid: int, native: NativeSettings, proc: Path = Path("/proc")) -> ProcessTarget:
    text = read_bytes(proc / str(pid) / "stat", native.capture_limits.max_proc_text_bytes).decode()
    prefix, bracket, tail = text.rpartition(") ")
    fields = tail.split()
    if (
        not bracket
        or int(prefix.partition(" ")[0]) != pid
        or len(fields) <= START_TICKS_TAIL
    ):
        raise ValueError("malformed process identity")
    return ProcessTarget(pid=pid, start_ticks=int(fields[START_TICKS_TAIL]))
