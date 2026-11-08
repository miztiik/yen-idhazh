"""How does one real UniEval process report every planned and completed comparison?"""

import threading
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from summary_evaluator.shared.exchange_packets import ByteChannel, encode_packet
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.shared.read_process_identity import read_process_identity
from summary_evaluator.shared.watch_worker_parent import arm_parent_exit, watch_parent
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_request import EffectiveUnievalControls
from summary_evaluator.unieval.contracts.unieval_result import UnievalWork
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalBootstrap,
    UnievalCommand,
    UnievalFinished,
    UnievalPrediction,
    UnievalPrepared,
    UnievalReady,
    UnievalStartupFailed,
)
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.load_unieval import UnievalPredictor, load_unieval
from summary_evaluator.unieval.resolve_unieval_selection import resolve_unieval_selection
from summary_evaluator.unieval.score_unieval import UnievalComparison, prepare_unieval


class UnievalLoader(Protocol):
    def __call__(self, settings: UnievalSettings, root: Path) -> UnievalPredictor: ...


def score_comparison(
    predictor: UnievalPredictor, comparison: UnievalComparison, identity: RequestPacket
) -> UnievalPrediction:
    score: float | None = None
    error: UnievalError | None = None
    try:
        score = predictor.score(comparison.prompt)
        if type(score) not in (int, float):
            raise UnievalFailure(UnievalError.from_code("INVALID_MODEL_OUTPUT"))
        return UnievalPrediction(
            **identity.model_dump(),
            dimension=comparison.dimension,
            index=comparison.index,
            sentence_index=comparison.sentence_index,
            source_index=comparison.source_index,
            score=score,
            error=None,
        )
    except UnievalFailure as failure:
        error = UnievalError.from_code(failure.error.code, comparison.dimension, comparison.index)
    except ValidationError:
        error = UnievalError.from_code(
            "INVALID_MODEL_OUTPUT", comparison.dimension, comparison.index
        )
    except Exception:
        error = UnievalError.from_code(
            "MODEL_SCORING_FAILED", comparison.dimension, comparison.index
        )
    return UnievalPrediction(
        **identity.model_dump(),
        dimension=comparison.dimension,
        index=comparison.index,
        sentence_index=comparison.sentence_index,
        source_index=comparison.source_index,
        score=None,
        error=error,
    )


def run_unieval_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    max_command_bytes: int,
    *,
    loader: UnievalLoader = load_unieval,
) -> None:
    with quiet_model_output():
        threading.Thread(target=watch_parent, args=(lifetime,), daemon=True).start()
        try:
            bootstrap = UnievalBootstrap.model_validate_json(channel.recv_bytes(max_command_bytes))
            max_reply_bytes = bootstrap.settings.worker.max_reply_bytes
            try:
                arm_parent_exit()
                worker = read_process_identity(
                    generation, bootstrap.settings.worker.max_proc_identity_bytes
                )
                predictor = loader(bootstrap.settings, root)
                ready = UnievalReady(
                    version=UNIEVAL_WORKER_VERSION,
                    operation_metadata=bootstrap.operation_metadata,
                    worker=worker,
                    model=predictor.identity,
                )
                channel.send_bytes(encode_packet(ready, max_reply_bytes))
            except Exception:
                failed = UnievalStartupFailed(
                    version=UNIEVAL_WORKER_VERSION,
                    operation_metadata=bootstrap.operation_metadata,
                    error=UnievalError.from_code("MODEL_LOAD_FAILED"),
                )
                channel.send_bytes(encode_packet(failed, max_reply_bytes))
                return
            while True:
                command = UnievalCommand.model_validate_json(channel.recv_bytes(max_command_bytes))
                if command.generation != generation:
                    return
                identity = RequestPacket(
                    version=UNIEVAL_WORKER_VERSION,
                    operation_metadata=command.operation_metadata,
                    execution_id=command.execution_id,
                    generation=generation,
                )
                try:
                    plan = prepare_unieval(command.request, bootstrap.settings, predictor.resources)
                    prepared = UnievalPrepared(
                        **identity.model_dump(),
                        effective_settings=plan.controls,
                        relevance_skip_reason=plan.relevance_skip_reason,
                        work=plan.work,
                        errors=plan.errors,
                    )
                except UnievalFailure as failure:
                    plan = None
                    controls, relevance_skip_reason = resolve_unieval_selection(
                        command.request, bootstrap.settings.scoring
                    )
                    prepared = UnievalPrepared(
                        **identity.model_dump(),
                        effective_settings=EffectiveUnievalControls(
                            **controls.model_dump(),
                            source_budget_tokens=None,
                        ),
                        relevance_skip_reason=relevance_skip_reason,
                        work=UnievalWork(),
                        errors=(failure.error,),
                    )
                channel.send_bytes(encode_packet(prepared, max_reply_bytes))
                if plan is not None:
                    for comparison in plan.comparisons:
                        prediction = score_comparison(predictor, comparison, identity)
                        channel.send_bytes(encode_packet(prediction, max_reply_bytes))
                channel.send_bytes(
                    encode_packet(UnievalFinished(**identity.model_dump()), max_reply_bytes)
                )
                del command, plan
        except (EOFError, OSError, ValueError):
            return
        finally:
            channel.close()
            lifetime.close()
