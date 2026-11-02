"""How does one owned child load once and return a validated outcome per window?"""

import multiprocessing
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Final, Protocol

from pydantic import ValidationError

from .contracts.base import SCHEMA_VERSION
from .contracts.error_detail import ErrorDetail
from .contracts.service_settings import ServiceSettings
from .contracts.worker_message import (
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerCommand,
    WorkerFailed,
    WorkerReady,
    WorkerStarted,
)
from .exchange_packets import ByteChannel
from .fail_evaluation import EvaluationFailure
from .load_model import Predictor, load_model, quiet_model_output
from .read_process_identity import read_process_identity

# Linux defines this operation in its process-control ABI.
PR_SET_PDEATHSIG: Final = 1


class ModelLoader(Protocol):
    def __call__(self, settings: ServiceSettings, root: Path, *, local_only: bool) -> Predictor: ...


def _arm_parent_exit() -> None:
    """Make Linux owner loss independent of whether native prediction releases the GIL."""
    if sys.platform != "linux":
        return
    import ctypes

    parent = multiprocessing.parent_process()
    if parent is None:
        raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", "worker"))
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
        raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", "worker"))
    if os.getppid() != parent.pid:
        os._exit(0)


def _watch_parent(lifetime: ByteChannel) -> None:
    try:
        lifetime.recv_bytes(1)
    except (EOFError, OSError):
        pass
    finally:
        # Owner loss is a process boundary, including while native prediction blocks.
        os._exit(0)


def _score(predictor: Predictor, command: ScoreWindow) -> WindowOutcome:
    started = time.monotonic()
    error: ErrorDetail | None = None
    score: float | None = None
    try:
        score = predictor.score(command.source_text, command.summary_text)
        # Validate before sending; booleans, NaN and infinities are not scores.
        if type(score) not in (int, float):
            raise EvaluationFailure(
                ErrorDetail.from_code("INVALID_MODEL_OUTPUT", command.comparison)
            )
        outcome = WindowOutcome(
            **command.model_dump(exclude={"kind", "source_text", "summary_text"}),
            kind="window_scored",
            score=score,
            scoring_ms=(time.monotonic() - started) * 1000,
            error=None,
        )
        return outcome
    except EvaluationFailure as failure:
        error = ErrorDetail.from_code(
            failure.error.code, command.comparison, window_index=command.window_index
        )
    except ValidationError:
        error = ErrorDetail.from_code(
            "INVALID_MODEL_OUTPUT", command.comparison, window_index=command.window_index
        )
    except Exception:
        error = ErrorDetail.from_code(
            "MODEL_SCORING_FAILED", command.comparison, window_index=command.window_index
        )
    return WindowOutcome(
        **command.model_dump(exclude={"kind", "source_text", "summary_text"}),
        kind="window_failed",
        score=None,
        scoring_ms=(time.monotonic() - started) * 1000,
        error=error,
    )


def run_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    max_command_bytes: int,
    *,
    loader: ModelLoader = load_model,
) -> None:
    """Own real pipes and the lifetime watcher; inject only the model-call boundary."""
    with quiet_model_output():
        threading.Thread(target=_watch_parent, args=(lifetime,), daemon=True).start()
        try:
            bootstrap = WorkerCommand.model_validate_json(
                channel.recv_bytes(max_command_bytes)
            ).root
            if not isinstance(bootstrap, WorkerBootstrap):
                return
            worker = read_process_identity(
                generation, bootstrap.settings.worker.max_proc_identity_bytes
            )
            channel.send_bytes(
                WorkerStarted(version=SCHEMA_VERSION, kind="worker_started", worker=worker)
                .model_dump_json()
                .encode("utf-8")
            )
            try:
                _arm_parent_exit()
                predictor = loader(bootstrap.settings, root, local_only=generation > 1)
            except EvaluationFailure as failure:
                channel.send_bytes(
                    WorkerFailed(
                        version=SCHEMA_VERSION,
                        kind="worker_failed",
                        worker=worker,
                        error=failure.error,
                    )
                    .model_dump_json()
                    .encode("utf-8")
                )
                return
            except Exception:
                channel.send_bytes(
                    WorkerFailed(
                        version=SCHEMA_VERSION,
                        kind="worker_failed",
                        worker=worker,
                        error=ErrorDetail.from_code("MODEL_LOAD_FAILED", "worker"),
                    )
                    .model_dump_json()
                    .encode("utf-8")
                )
                return
            channel.send_bytes(
                WorkerReady(
                    version=SCHEMA_VERSION, kind="ready", worker=worker, model=predictor.identity
                )
                .model_dump_json()
                .encode("utf-8")
            )
            while True:
                command = WorkerCommand.model_validate_json(
                    channel.recv_bytes(max_command_bytes)
                ).root
                if not isinstance(command, ScoreWindow) or command.generation != generation:
                    return
                outcome = _score(predictor, command)
                channel.send_bytes(outcome.model_dump_json().encode("utf-8"))
                del command, outcome
        except (EOFError, OSError, ValidationError):
            return
        finally:
            channel.close()
            lifetime.close()
