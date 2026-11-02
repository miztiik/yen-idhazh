"""How is the one scoring process started, exchanged with and conclusively stopped?"""

import asyncio
import multiprocessing
import time
from multiprocessing.process import BaseProcess
from pathlib import Path

from pydantic import ValidationError

from .contracts.base import SCHEMA_VERSION
from .contracts.error_detail import ErrorDetail
from .contracts.model_identity import ModelIdentity
from .contracts.service_settings import ServiceSettings, StartupContext
from .contracts.worker_identity import WorkerIdentity
from .contracts.worker_message import (
    FrozenAssets,
    ReplyPacket,
    ScoreWindow,
    WindowOutcome,
    WorkerBootstrap,
    WorkerFailed,
    WorkerReady,
    WorkerReply,
    WorkerStarted,
    validate_window_reply,
)
from .exchange_packets import ByteChannel, command_byte_limit, reply_byte_limit
from .fail_evaluation import EvaluationFailure
from .run_worker import run_worker


class WorkerSupervisor:
    """Keep process and pipe ownership distinct from request or caller identities."""

    def __init__(self, settings: ServiceSettings, context: StartupContext, root: Path) -> None:
        self.settings = settings
        self.root = root
        self.bootstrap = WorkerBootstrap(
            version=SCHEMA_VERSION,
            kind="bootstrap",
            settings=settings,
            assets=FrozenAssets(model=settings.hhem.model, foundation=settings.hhem.foundation),
            context=context,
        )
        self.process: BaseProcess | None = None
        self.channel: ByteChannel | None = None
        self.lifetime: ByteChannel | None = None
        self.worker: WorkerIdentity | None = None
        self.model: ModelIdentity | None = None
        self.initial_model: ModelIdentity | None = None
        self.generation = 0
        self.read_task: asyncio.Task[bytes] | None = None
        self.start_task: asyncio.Task[None] | None = None
        self.exit_confirmed = True
        self.last_exit: tuple[int, int] | None = None

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int, max_bytes: int
    ) -> BaseProcess:
        return multiprocessing.get_context("spawn").Process(
            target=run_worker,
            args=(channel, lifetime, self.root, generation, max_bytes),
            daemon=False,
        )

    async def start(self) -> None:
        if not self.exit_confirmed or self.process is not None:
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_STOP_FAILED", "worker"))
        self.generation += 1
        context = multiprocessing.get_context("spawn")
        allocated: list[ByteChannel] = []
        try:
            parent, child = context.Pipe(duplex=True)
            allocated.extend((parent, child))
            owner_read, owner_write = context.Pipe(duplex=False)
            allocated.extend((owner_read, owner_write))
            process = self._create_process(
                child,
                owner_read,
                self.generation,
                command_byte_limit(self.bootstrap, self.generation),
            )
        except (OSError, ValueError, RuntimeError):
            for connection in allocated:
                connection.close()
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_EXITED", "worker")) from None
        self.process, self.channel, self.lifetime = process, parent, owner_write
        self.exit_confirmed = False
        self.worker = None
        self.model = None
        start_task = asyncio.create_task(asyncio.to_thread(process.start))
        self.start_task = start_task

        def release_spawn_inputs(task: asyncio.Task[None]) -> None:
            child.close()
            owner_read.close()

        start_task.add_done_callback(release_spawn_inputs)
        timeout = (
            self.settings.worker.startup_timeout_ms
            if self.generation == 1
            else self.settings.worker.replacement_timeout_ms
        )
        try:
            async with asyncio.timeout(timeout / 1000):
                await asyncio.shield(start_task)
                await asyncio.to_thread(
                    parent.send_bytes, self.bootstrap.model_dump_json().encode("utf-8")
                )
                started = await self._receive()
                if (
                    not isinstance(started, WorkerStarted)
                    or started.worker.generation != self.generation
                    or started.worker.pid != process.pid
                ):
                    raise EvaluationFailure(
                        ErrorDetail.from_code("WORKER_PROTOCOL_FAILED", "worker")
                    )
                self.worker = started.worker
                reply = await self._receive()
                if isinstance(reply, WorkerFailed) and reply.worker == self.worker:
                    raise EvaluationFailure(reply.error)
                if not isinstance(reply, WorkerReady) or reply.worker != self.worker:
                    raise EvaluationFailure(
                        ErrorDetail.from_code("WORKER_PROTOCOL_FAILED", "worker")
                    )
                if self.initial_model is not None and reply.model != self.initial_model:
                    raise EvaluationFailure(
                        ErrorDetail.from_code("MODEL_IDENTITY_CHANGED", "worker", field="model")
                    )
                self.model = reply.model
                if self.initial_model is None:
                    self.initial_model = reply.model
        except TimeoutError:
            raise EvaluationFailure(ErrorDetail.from_code("MODEL_LOAD_FAILED", "worker")) from None
        except (OSError, EOFError, ValueError, RuntimeError):
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_EXITED", "worker")) from None

    async def _receive(self) -> ReplyPacket:
        if self.channel is None or self.read_task is not None:
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_PROTOCOL_FAILED", "worker"))
        task = asyncio.create_task(
            asyncio.to_thread(
                self.channel.recv_bytes, reply_byte_limit(self.bootstrap, self.generation)
            )
        )
        self.read_task = task
        try:
            packet = await asyncio.shield(task)
            return WorkerReply.model_validate_json(packet).root
        except ValidationError:
            raise EvaluationFailure(
                ErrorDetail.from_code("WORKER_PROTOCOL_FAILED", "worker")
            ) from None
        except (EOFError, OSError):
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_EXITED", "worker")) from None
        finally:
            if task.done() and self.read_task is task:
                self.read_task = None

    async def score(self, command: ScoreWindow) -> WindowOutcome:
        if self.channel is None or self.model is None or command.generation != self.generation:
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_NOT_READY", command.comparison))
        try:
            encoded = command.model_dump_json().encode("utf-8")
            if len(encoded) > command_byte_limit(self.bootstrap, self.generation):
                raise EvaluationFailure(
                    ErrorDetail.from_code("WORKER_PROTOCOL_FAILED", command.comparison)
                )
            await asyncio.to_thread(self.channel.send_bytes, encoded)
            reply = await self._receive()
            if not isinstance(reply, WindowOutcome):
                raise ValueError("Expected a window outcome.")
            validate_window_reply(command, reply)
            return reply
        except EvaluationFailure as failure:
            raise EvaluationFailure(
                ErrorDetail.from_code(
                    failure.error.code,
                    command.comparison,
                    field=failure.error.field,
                    window_index=command.window_index,
                )
            ) from None
        except (ValueError, ValidationError):
            raise EvaluationFailure(
                ErrorDetail.from_code(
                    "WORKER_PROTOCOL_FAILED",
                    command.comparison,
                    window_index=command.window_index,
                )
            ) from None
        except (EOFError, OSError):
            raise EvaluationFailure(
                ErrorDetail.from_code(
                    "WORKER_EXITED", command.comparison, window_index=command.window_index
                )
            ) from None

    async def stop(self) -> None:
        process = self.process
        if process is None:
            if not self.exit_confirmed:
                raise EvaluationFailure(ErrorDetail.from_code("WORKER_STOP_FAILED", "worker"))
            return
        if self.lifetime is not None:
            self.lifetime.close()
            self.lifetime = None
        grace_deadline = time.monotonic() + self.settings.worker.stop_grace_ms / 1000
        forced_deadline = grace_deadline + self.settings.worker.forced_stop_ms / 1000
        started = False
        try:
            if self.start_task is not None:
                try:
                    async with asyncio.timeout_at(forced_deadline):
                        await asyncio.shield(self.start_task)
                except (OSError, ValueError, RuntimeError):
                    if process.pid is not None:
                        raise
            started = process.pid is not None
            if started:
                await asyncio.to_thread(process.join, max(0, grace_deadline - time.monotonic()))
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(
                        process.join, max(0, forced_deadline - time.monotonic())
                    )
                if process.is_alive() or process.exitcode is None:
                    raise ValueError("The scoring process exit is unconfirmed.")
                if process.pid is not None:
                    self.last_exit = (process.pid, process.exitcode)
            else:
                # start() failed before an OS process existed.
                process.close()
        except (OSError, ValueError, AssertionError, TimeoutError):
            raise EvaluationFailure(ErrorDetail.from_code("WORKER_STOP_FAILED", "worker")) from None
        finally:
            if self.channel is not None:
                self.channel.close()
                self.channel = None
        pending = self.read_task
        if pending is not None:
            try:
                async with asyncio.timeout_at(forced_deadline):
                    await asyncio.shield(pending)
            except (EOFError, OSError):
                pass
            except TimeoutError:
                raise EvaluationFailure(
                    ErrorDetail.from_code("WORKER_STOP_FAILED", "worker")
                ) from None
            finally:
                if pending.done() and self.read_task is pending:
                    self.read_task = None
        if started:
            process.close()
        self.process = None
        self.start_task = None
        self.exit_confirmed = True
        self.model = None
        self.worker = None
