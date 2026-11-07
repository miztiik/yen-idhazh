"""How does one owned coverage process return complete metrics without model-output leakage?"""

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from summary_evaluator.shared.exchange_packets import ByteChannel
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.shared.read_process_identity import read_process_identity
from summary_evaluator.shared.watch_worker_parent import arm_parent_exit, watch_parent
from summary_evaluator.source_coverage.contracts.base import COVERAGE_VERSION
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageMetrics
from summary_evaluator.source_coverage.contracts.model_call import CoverageRuntimeBackend
from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.contracts.worker_message import (
    CoverageBootstrap,
    CoverageCommand,
    CoverageCompleted,
    CoverageFailed,
    CoverageReady,
    CoverageStartupFailed,
)
from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure
from summary_evaluator.source_coverage.load_model import load_model
from summary_evaluator.source_coverage.score_coverage import score_coverage


class CoverageLoader(Protocol):
    def __call__(self, settings: CoverageSettings, root: Path) -> CoverageRuntimeBackend: ...


@dataclass
class WarningCollector:
    values: list[CoverageWarningCode] = field(default_factory=list)

    def __call__(self, code: CoverageWarningCode) -> None:
        if code not in self.values:
            self.values.append(code)


def run_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    max_command_bytes: int,
    *,
    loader: CoverageLoader = load_model,
) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    with quiet_model_output():
        threading.Thread(target=watch_parent, args=(lifetime,), daemon=True).start()
        try:
            bootstrap = CoverageBootstrap.model_validate_json(channel.recv_bytes(max_command_bytes))
            try:
                arm_parent_exit()
                worker = read_process_identity(
                    generation, bootstrap.settings.worker.max_proc_identity_bytes
                )
                backend = loader(bootstrap.settings, root)
                ready = CoverageReady(
                    version=COVERAGE_VERSION, worker=worker, model=backend.identity
                )
                encoded = ready.model_dump_json().encode("utf-8")
                if len(encoded) > bootstrap.settings.worker.max_reply_bytes:
                    return
                channel.send_bytes(encoded)
            except Exception:
                failed = CoverageStartupFailed(version=COVERAGE_VERSION, code="MODEL_LOAD_FAILED")
                channel.send_bytes(failed.model_dump_json().encode("utf-8"))
                return
            while True:
                command = CoverageCommand.model_validate_json(channel.recv_bytes(max_command_bytes))
                if command.generation != generation:
                    return
                warnings = WarningCollector()
                try:
                    metrics = score_coverage(
                        command.request.source_text,
                        command.request.summary_text,
                        bootstrap.settings.preparation,
                        backend,
                        warnings,
                    )
                    validated = CoverageMetrics.model_validate_json(
                        json.dumps(metrics, ensure_ascii=False, allow_nan=False)
                    )
                    reply: CoverageCompleted | CoverageFailed = CoverageCompleted(
                        version=COVERAGE_VERSION,
                        execution_id=command.execution_id,
                        generation=generation,
                        metrics=validated,
                        warnings=tuple(warnings.values),
                    )
                except CoverageFailure as failure:
                    reply = CoverageFailed(
                        version=COVERAGE_VERSION,
                        execution_id=command.execution_id,
                        generation=generation,
                        code=failure.code,
                        warnings=tuple(warnings.values),
                    )
                except (ValidationError, ValueError):
                    reply = CoverageFailed(
                        version=COVERAGE_VERSION,
                        execution_id=command.execution_id,
                        generation=generation,
                        code="INVALID_MODEL_OUTPUT",
                        warnings=tuple(warnings.values),
                    )
                except Exception:
                    reply = CoverageFailed(
                        version=COVERAGE_VERSION,
                        execution_id=command.execution_id,
                        generation=generation,
                        code="MODEL_SCORING_FAILED",
                        warnings=tuple(warnings.values),
                    )
                encoded = reply.model_dump_json().encode("utf-8")
                if len(encoded) > bootstrap.settings.worker.max_reply_bytes:
                    reply = CoverageFailed(
                        version=COVERAGE_VERSION,
                        execution_id=command.execution_id,
                        generation=generation,
                        code="WORKER_PROTOCOL_FAILED",
                    )
                    encoded = reply.model_dump_json().encode("utf-8")
                if len(encoded) > bootstrap.settings.worker.max_reply_bytes:
                    return
                channel.send_bytes(encoded)
                del command, reply, encoded
        except (EOFError, OSError, ValidationError):
            return
        finally:
            channel.close()
            lifetime.close()
