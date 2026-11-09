"""How is recorded generation process exit confirmed before loading evaluators?"""

import contextlib
import os
import select
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from .contracts import PipelineError
from .failures import WorkflowError
from .settings import PipelineSettings


def stop_pid_file(root: Path, path: Path, pipeline: PipelineSettings) -> None:
    if sys.platform != "linux":
        raise WorkflowError("SERVICE_STOP_FAILED", "cleanup")
    destination = (root / path).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise WorkflowError("SERVICE_STOP_FAILED", "cleanup")
    with destination.open("rb") as stream:
        encoded = stream.read(pipeline.control_max_bytes + 1)
    if len(encoded) > pipeline.control_max_bytes or not encoded.strip().isdigit():
        raise WorkflowError("SERVICE_STOP_FAILED", "cleanup")
    pid = int(encoded)
    if pid <= 1 or pid in (os.getpid(), os.getppid()):
        raise WorkflowError("SERVICE_STOP_FAILED", "cleanup")
    try:
        descriptor = os.pidfd_open(pid)
    except ProcessLookupError:
        destination.unlink()
        return
    try:
        with contextlib.suppress(ProcessLookupError):
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        if not select.select([descriptor], [], [], pipeline.native_shutdown_timeout_ms / 1000)[0]:
            with contextlib.suppress(ProcessLookupError):
                signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            if not select.select([descriptor], [], [], pipeline.native_forced_stop_ms / 1000)[0]:
                raise WorkflowError("SERVICE_STOP_FAILED", "cleanup")
    finally:
        os.close(descriptor)
    destination.unlink()


def stop_generation(
    root: Path, paths: Sequence[Path], pipeline: PipelineSettings,
) -> tuple[PipelineError, ...]:
    errors = []
    for path in paths:
        try:
            stop_pid_file(root, path, pipeline)
        except WorkflowError as error:
            errors.append(error.error)
        except (OSError, ValueError, OverflowError):
            errors.append(WorkflowError("SERVICE_STOP_FAILED", "cleanup").error)
    return tuple(errors)
