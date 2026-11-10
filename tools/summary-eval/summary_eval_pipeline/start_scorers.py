"""How do independent scorer APIs start and verify their actual owned workers?"""

import asyncio
import math
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import httpx
from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation
from summary_evaluator.shared.create_execution_id import create_execution_id

from .control import StartupPacket
from .evaluation import read_owned_health
from .failures import WorkflowError
from .phase_services import ScorerService, guard_work
from .scorer_control import SCORER_CONTROL_VERSION, ScorerReady, ScorerStartupPacket
from .services import OwnedService
from .settings import PipelineSettings


async def start_scorers(
    root: Path,
    client: httpx.AsyncClient,
    apis: Sequence[ScorerService],
    packet: StartupPacket,
    pipeline: PipelineSettings,
    operation: OperationMetadata,
) -> None:
    for api in apis:
        if api.errors:
            continue
        api.started = time.monotonic()
        try:
            api.owner = OwnedService(
                "api",
                [
                    sys.executable, str(root / "tools" / "summary-eval" / "serve.py"),
                    "--root", str(root),
                ],
                root,
                ScorerStartupPacket(
                    version=SCORER_CONTROL_VERSION,
                    scorer=api.scorer,
                    operation_metadata=create_child_operation(operation),
                    startup=packet.model_copy(update={"startup_id": create_execution_id()}),
                ),
                api.worker_settings,
                pipeline,
                api_settings=api.api_settings,
            )
        except WorkflowError as error:
            api.retain_error(error.error)
            api.startup_ms = (time.monotonic() - api.started) * 1000
        except (OSError, ValueError, TypeError):
            api.retain_error(WorkflowError("STARTUP_FAILED", "startup", "api").error)
            api.startup_ms = (time.monotonic() - api.started) * 1000

    async def wait_scorer(api: ScorerService) -> None:
        if api.owner is None or api.started is None:
            return
        deadline = api.started + api.worker_settings.startup_timeout_ms / 1000
        try:
            remaining_ms = math.ceil((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                raise WorkflowError("STARTUP_FAILED", "startup", "api")
            waiting = asyncio.create_task(
                asyncio.to_thread(api.owner.wait_ready, remaining_ms)
            )
            try:
                ready = await asyncio.shield(waiting)
            except asyncio.CancelledError:
                try:
                    await waiting
                except WorkflowError as error:
                    api.retain_error(error.error)
                raise
            if not isinstance(ready, ScorerReady):
                raise WorkflowError("STARTUP_IDENTITY_MISMATCH", "startup", "api")
            await guard_work(
                read_owned_health(
                    client, api.origin, ready.service_instance_id, api.worker_settings,
                    pipeline, api.scorer, deadline=deadline, observe=api.observe_health,
                    operation_metadata=operation,
                ),
                api.owner,
                pipeline,
            )
        except WorkflowError as error:
            api.retain_error(error.error)
        except asyncio.CancelledError:
            api.retain_error(WorkflowError("TASK_CANCELLED", "startup", "api").error)
            raise
        except (OSError, ValueError, KeyError, TypeError):
            api.retain_error(WorkflowError("STARTUP_FAILED", "startup", "api").error)
        finally:
            api.startup_ms = (time.monotonic() - api.started) * 1000

    await asyncio.gather(*(wait_scorer(api) for api in apis))
