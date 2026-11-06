"""How does one real UniEval process report every planned and completed comparison?"""

import threading
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from hhem_evaluator.contracts.unieval_contract import UNIEVAL_VERSION
from hhem_evaluator.contracts.unieval_error import UnievalError
from hhem_evaluator.contracts.unieval_request import EffectiveUnievalControls
from hhem_evaluator.contracts.unieval_result import UnievalWork
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalBootstrap,
    UnievalCommand,
    UnievalFinished,
    UnievalPrediction,
    UnievalPrepared,
    UnievalReady,
    UnievalStartupFailed,
)
from hhem_evaluator.fail_unieval import UnievalFailure
from hhem_evaluator.load_unieval import UnievalPredictor, load_unieval
from hhem_evaluator.read_process_identity import read_process_identity
from hhem_evaluator.score_unieval import UnievalComparison, prepare_unieval
from hhem_evaluator.shared.exchange_packets import ByteChannel
from hhem_evaluator.shared.quiet_model_output import quiet_model_output
from hhem_evaluator.watch_worker_parent import arm_parent_exit, watch_parent


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
            try:
                arm_parent_exit()
                worker = read_process_identity(
                    generation, bootstrap.settings.worker.max_proc_identity_bytes
                )
                predictor = loader(bootstrap.settings, root)
                ready = UnievalReady(
                    version=UNIEVAL_VERSION, worker=worker, model=predictor.identity
                )
                channel.send_bytes(ready.model_dump_json().encode("utf-8"))
            except Exception:
                failed = UnievalStartupFailed(
                    version=UNIEVAL_VERSION,
                    error=UnievalError.from_code("MODEL_LOAD_FAILED"),
                )
                channel.send_bytes(failed.model_dump_json().encode("utf-8"))
                return
            while True:
                command = UnievalCommand.model_validate_json(channel.recv_bytes(max_command_bytes))
                if command.generation != generation:
                    return
                identity = RequestPacket(
                    version=UNIEVAL_VERSION,
                    execution_id=command.execution_id,
                    generation=generation,
                )
                try:
                    plan = prepare_unieval(command.request, bootstrap.settings, predictor.resources)
                    prepared = UnievalPrepared(
                        **identity.model_dump(),
                        effective_settings=plan.controls,
                        work=plan.work,
                        errors=plan.errors,
                    )
                except UnievalFailure as failure:
                    plan = None
                    prepared = UnievalPrepared(
                        **identity.model_dump(),
                        effective_settings=EffectiveUnievalControls(
                            **{
                                **bootstrap.settings.scoring.model_dump(),
                                "consistency_source_mode": (
                                    command.request.consistency_source_mode
                                    or bootstrap.settings.scoring.consistency_source_mode
                                ),
                            },
                            source_budget_tokens=None,
                        ),
                        work=UnievalWork(),
                        errors=(failure.error,),
                    )
                channel.send_bytes(prepared.model_dump_json().encode("utf-8"))
                if plan is not None:
                    for comparison in plan.comparisons:
                        prediction = score_comparison(predictor, comparison, identity)
                        channel.send_bytes(prediction.model_dump_json().encode("utf-8"))
                channel.send_bytes(
                    UnievalFinished(**identity.model_dump()).model_dump_json().encode("utf-8")
                )
                del command, plan
        except (EOFError, OSError, ValidationError):
            return
        finally:
            channel.close()
            lifetime.close()
