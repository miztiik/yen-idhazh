"""Prove native exec refuses a lost parent and preserves normal same-PID shutdown."""

import ctypes
import json
import os
import select
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

# These are the Linux process-control ABI operations, not runtime settings.
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37


@contextmanager
def adopt_owned_orphans() -> Iterator[None]:
    library = ctypes.CDLL(None, use_errno=True)
    library.prctl.argtypes = [ctypes.c_int, *[ctypes.c_ulong] * 4]
    library.prctl.restype = ctypes.c_int
    previous = ctypes.c_int()
    assert library.prctl(PR_GET_CHILD_SUBREAPER, ctypes.addressof(previous), 0, 0, 0) == 0
    assert library.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    try:
        yield
    finally:
        assert library.prctl(PR_SET_CHILD_SUBREAPER, previous.value, 0, 0, 0) == 0


def read_packet(process: subprocess.Popen[bytes]) -> dict[str, object]:
    assert process.stdout is not None
    deadline = time.monotonic() + 15
    encoded = bytearray()
    while len(encoded) < 1024:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "The owned launch boundary did not report before its deadline."
        ready, _, _ = select.select([process.stdout], [], [], remaining)
        assert ready, "The owned launch boundary did not report before its deadline."
        byte = os.read(process.stdout.fileno(), 1)
        assert byte, "The owned launch process exited before its control packet."
        if byte == b"\n":
            packet: object = json.loads(encoded)
            assert isinstance(packet, dict)
            return {str(key): value for key, value in packet.items()}
        encoded.extend(byte)
    raise AssertionError("The launch control packet exceeded its fixed byte allowance.")


def reap_owned(pid: int) -> int:
    if sys.platform != "linux":
        raise RuntimeError("Requires the Linux child-wait ABI.")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        observed, status = os.waitpid(pid, os.WNOHANG)
        if observed == pid:
            return os.waitstatus_to_exitcode(status)
        time.sleep(0.01)
    raise AssertionError("The exact adopted native child did not exit before its deadline.")


@pytest.mark.skipif(sys.platform != "linux", reason="Requires the Linux parent-death and exec ABI.")
@pytest.mark.parametrize("boundary", ["before_arm", "after_exec", "normal_stop"])
def test_native_launch_owns_the_child_across_parent_loss_and_normal_stop(boundary: str) -> None:
    if sys.platform != "linux":
        raise RuntimeError("Requires the Linux parent-death and exec ABI.")
    gate_read, gate_write = os.pipe()
    child_pid: int | None = None
    reaped = False
    with adopt_owned_orphans():
        owner = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).with_name("native_launch_child.py")),
                "owner",
                str(gate_read) if boundary == "before_arm" else "-1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(gate_read,) if boundary == "before_arm" else (),
        )
        os.close(gate_read)
        try:
            packets = []
            for _ in range(2):
                packet = read_packet(owner)
                packets.append(packet)
                observed_pid = packet.get("pid")
                if isinstance(observed_pid, int):
                    child_pid = observed_pid
            spawned = next(packet for packet in packets if packet["stage"] == "spawned")
            active = next(packet for packet in packets if packet["stage"] != "spawned")
            assert isinstance(spawned["pid"], int)
            child_pid = spawned["pid"]
            assert child_pid != owner.pid and spawned["owner"] == owner.pid
            assert active == {
                "stage": "unarmed" if boundary == "before_arm" else "native",
                "pid": child_pid,
                "parent": owner.pid,
            }
            if boundary == "normal_stop":
                assert owner.stdin is not None
                owner.stdin.write(b"1")
                owner.stdin.flush()
                assert read_packet(owner) == {
                    "stage": "closed",
                    "pid": child_pid,
                    "exit_code": -signal.SIGTERM,
                }
                assert owner.wait(timeout=10) == 0
                reaped = True
            else:
                owner.kill()
                assert owner.wait(timeout=10) == -signal.SIGKILL
                if boundary == "before_arm":
                    os.write(gate_write, b"1")
                assert reap_owned(child_pid) == (1 if boundary == "before_arm" else -signal.SIGKILL)
                reaped = True
        finally:
            os.close(gate_write)
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=10)
            if child_pid is not None and not reaped:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                    reap_owned(child_pid)
                except (ProcessLookupError, ChildProcessError):
                    pass
            for stream in (owner.stdin, owner.stdout):
                if stream is not None:
                    stream.close()
