"""How does one owned child load once and return a validated outcome per window?"""

import threading
import time
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.contracts.worker_contract import HHEM_WORKER_VERSION
from summary_evaluator.hhem.contracts.worker_message import (
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerCommand,
    WorkerFailed,
    WorkerReady,
    WorkerStarted,
)
from summary_evaluator.hhem.exchange_packets import reply_byte_limit
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.hhem.load_model import Predictor, load_model
from summary_evaluator.shared.exchange_packets import ByteChannel, encode_packet
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.shared.read_process_identity import read_process_identity
from summary_evaluator.shared.watch_worker_parent import arm_parent_exit, watch_parent


class ModelLoader(Protocol):
    def __call__(self, settings: ServiceSettings, root: Path, *, local_only: bool) -> Predictor: ...


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
        threading.Thread(target=watch_parent, args=(lifetime,), daemon=True).start()
        try:
            bootstrap = WorkerCommand.model_validate_json(
                channel.recv_bytes(max_command_bytes)
            ).root
            if not isinstance(bootstrap, WorkerBootstrap):
                return
            worker = read_process_identity(
                generation, bootstrap.settings.worker.max_proc_identity_bytes
            )
            max_reply_bytes = reply_byte_limit(bootstrap, generation)
            channel.send_bytes(
                encode_packet(
                    WorkerStarted(
                        version=HHEM_WORKER_VERSION,
                        operation_metadata=bootstrap.operation_metadata,
                        kind="worker_started",
                        worker=worker,
                    ),
                    max_reply_bytes,
                )
            )
            try:
                arm_parent_exit()
                predictor = loader(bootstrap.settings, root, local_only=generation > 1)
            except (EvaluationFailure, RuntimeFailure) as failure:
                channel.send_bytes(
                    encode_packet(
                        WorkerFailed(
                            version=HHEM_WORKER_VERSION,
                            operation_metadata=bootstrap.operation_metadata,
                            kind="worker_failed",
                            worker=worker,
                            error=(
                                failure.error
                                if isinstance(failure, EvaluationFailure)
                                else ErrorDetail.from_code(failure.code, "worker")
                            ),
                        ),
                        max_reply_bytes,
                    )
                )
                return
            except Exception:
                channel.send_bytes(
                    encode_packet(
                        WorkerFailed(
                            version=HHEM_WORKER_VERSION,
                            operation_metadata=bootstrap.operation_metadata,
                            kind="worker_failed",
                            worker=worker,
                            error=ErrorDetail.from_code("MODEL_LOAD_FAILED", "worker"),
                        ),
                        max_reply_bytes,
                    )
                )
                return
            channel.send_bytes(
                encode_packet(
                    WorkerReady(
                        version=HHEM_WORKER_VERSION,
                        operation_metadata=bootstrap.operation_metadata,
                        kind="ready",
                        worker=worker,
                        model=predictor.identity,
                    ),
                    max_reply_bytes,
                )
            )
            while True:
                command = WorkerCommand.model_validate_json(
                    channel.recv_bytes(max_command_bytes)
                ).root
                if not isinstance(command, ScoreWindow) or command.generation != generation:
                    return
                outcome = _score(predictor, command)
                channel.send_bytes(encode_packet(outcome, max_reply_bytes))
                del command, outcome
        except (EOFError, OSError, ValueError):
            return
        finally:
            channel.close()
            lifetime.close()
