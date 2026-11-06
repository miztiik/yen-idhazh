"""How does an owned model process stop when its parent disappears?"""

import multiprocessing
import os
import signal
import sys
from typing import Final

from summary_evaluator.shared.exchange_packets import ByteChannel
from summary_evaluator.shared.fail_runtime import RuntimeFailure

# Linux assigns this operation in its process-control ABI.
PR_SET_PDEATHSIG: Final = 1


def arm_parent_exit() -> None:
    if sys.platform != "linux":
        return
    import ctypes

    parent = multiprocessing.parent_process()
    if parent is None:
        raise RuntimeFailure("INTERNAL_ERROR")
    library = ctypes.CDLL(None, use_errno=True)
    library.prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    library.prctl.restype = ctypes.c_int
    if library.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        raise RuntimeFailure("INTERNAL_ERROR")
    if os.getppid() != parent.pid:
        os._exit(0)


def watch_parent(lifetime: ByteChannel) -> None:
    try:
        lifetime.recv_bytes(1)
    except (EOFError, OSError):
        pass
    finally:
        os._exit(0)
