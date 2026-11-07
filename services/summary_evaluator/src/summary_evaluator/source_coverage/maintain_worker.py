"""How is the exact coverage child started, bounded, identified and joined?"""

import asyncio
import multiprocessing
import time
from multiprocessing.process import BaseProcess
from pathlib import Path

from pydantic import ValidationError

from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.shared.exchange_packets import JSON_ESCAPE_MAX_BYTES, ByteChannel
from summary_evaluator.source_coverage.contracts.base import COVERAGE_VERSION
from summary_evaluator.source_coverage.contracts.model_identity import CoverageModelIdentity
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.contracts.worker_message import (
    CoverageBootstrap,
    CoverageCommand,
    CoverageReady,
    CoverageReply,
    CoverageStartupFailed,
)
from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure
from summary_evaluator.source_coverage.run_worker import run_worker


class CoverageSupervisor:
    def __init__(self, settings: CoverageSettings, root: Path) -> None:
        self.settings, self.root = settings, root
        self.process: BaseProcess | None = None
        self.channel: ByteChannel | None = None
        self.lifetime: ByteChannel | None = None
        self.worker: WorkerIdentity | None = None
        self.model: CoverageModelIdentity | None = None
        self.read_task: asyncio.Task[bytes] | None = None
        self.start_task: asyncio.Task[None] | None = None
        self.generation = 0
        self.exit_confirmed = True
        self.last_exit: tuple[int, int] | None = None
        self.bootstrap = CoverageBootstrap(version=COVERAGE_VERSION, settings=settings)
        self.command_limit = (
            len(self.bootstrap.model_dump_json().encode("utf-8"))
            + JSON_ESCAPE_MAX_BYTES * settings.listener.max_body_bytes
        )

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int
    ) -> BaseProcess:
        return multiprocessing.get_context("spawn").Process(
            target=run_worker,
            args=(channel, lifetime, self.root, generation, self.command_limit),
            daemon=False,
        )

    async def start(self) -> None:
        if self.process is not None or not self.exit_confirmed:
            raise CoverageFailure("WORKER_STOP_FAILED")
        self.generation += 1
        context = multiprocessing.get_context("spawn")
        allocated: list[ByteChannel] = []
        try:
            parent, child = context.Pipe(duplex=True)
            allocated.extend((parent, child))
            owner_read, owner_write = context.Pipe(duplex=False)
            allocated.extend((owner_read, owner_write))
            process = self._create_process(child, owner_read, self.generation)
        except (OSError, ValueError, RuntimeError):
            for connection in allocated:
                connection.close()
            raise CoverageFailure("WORKER_EXITED") from None
        self.process, self.channel, self.lifetime = process, parent, owner_write
        self.exit_confirmed = False
        starting = asyncio.create_task(asyncio.to_thread(process.start))
        self.start_task = starting

        def release_inputs(task: asyncio.Task[None]) -> None:
            child.close()
            owner_read.close()

        starting.add_done_callback(release_inputs)
        try:
            async with asyncio.timeout(self.settings.worker.startup_timeout_ms / 1000):
                await asyncio.shield(starting)
                await asyncio.to_thread(
                    parent.send_bytes, self.bootstrap.model_dump_json().encode("utf-8")
                )
                reply = (await self.receive()).root
                if isinstance(reply, CoverageStartupFailed):
                    raise CoverageFailure(reply.code)
                if (
                    not isinstance(reply, CoverageReady)
                    or reply.worker.generation != self.generation
                    or reply.worker.pid != process.pid
                    or reply.model.reference != self.settings.assets.model.reference
                    or reply.model.loaded_revision != self.settings.assets.model.revision
                    or reply.model.tokenizer_revision != self.settings.assets.model.revision
                    or reply.model.code_revision != self.settings.assets.code.revision
                ):
                    raise CoverageFailure("WORKER_PROTOCOL_FAILED")
                self.worker, self.model = reply.worker, reply.model
        except TimeoutError:
            raise CoverageFailure("MODEL_LOAD_FAILED") from None
        except (OSError, EOFError, ValueError, RuntimeError):
            raise CoverageFailure("WORKER_EXITED") from None

    async def send(self, command: CoverageCommand) -> None:
        if self.channel is None or self.model is None:
            raise CoverageFailure("WORKER_NOT_READY")
        encoded = command.model_dump_json().encode("utf-8")
        if len(encoded) > self.command_limit:
            raise CoverageFailure("BODY_TOO_LARGE")
        try:
            await asyncio.to_thread(self.channel.send_bytes, encoded)
        except (OSError, EOFError):
            raise CoverageFailure("WORKER_EXITED") from None

    async def receive(self) -> CoverageReply:
        if self.channel is None or self.read_task is not None:
            raise CoverageFailure("WORKER_PROTOCOL_FAILED")
        task = asyncio.create_task(
            asyncio.to_thread(self.channel.recv_bytes, self.settings.worker.max_reply_bytes)
        )
        self.read_task = task
        try:
            return CoverageReply.model_validate_json(await asyncio.shield(task))
        except ValidationError:
            raise CoverageFailure("WORKER_PROTOCOL_FAILED") from None
        except (OSError, EOFError):
            raise CoverageFailure("WORKER_EXITED") from None
        finally:
            if task.done():
                self.read_task = None

    async def stop(self) -> None:
        process = self.process
        if process is None:
            if not self.exit_confirmed:
                raise CoverageFailure("WORKER_STOP_FAILED")
            return
        if self.lifetime is not None:
            self.lifetime.close()
            self.lifetime = None
        grace = time.monotonic() + self.settings.worker.stop_grace_ms / 1000
        forced = grace + self.settings.worker.forced_stop_ms / 1000
        started = False
        try:
            if self.start_task is not None:
                try:
                    async with asyncio.timeout_at(forced):
                        await asyncio.shield(self.start_task)
                except (OSError, ValueError, RuntimeError):
                    if process.pid is not None:
                        raise
            started = process.pid is not None
            if started:
                await asyncio.to_thread(process.join, max(0, grace - time.monotonic()))
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join, max(0, forced - time.monotonic()))
                if process.is_alive() or process.exitcode is None:
                    raise ValueError("The coverage worker exit is unconfirmed")
                if process.pid is not None:
                    self.last_exit = (process.pid, process.exitcode)
            else:
                process.close()
        except (OSError, ValueError, AssertionError, TimeoutError):
            raise CoverageFailure("WORKER_STOP_FAILED") from None
        finally:
            if self.channel is not None:
                self.channel.close()
                self.channel = None
        if self.read_task is not None:
            try:
                async with asyncio.timeout_at(forced):
                    await asyncio.shield(self.read_task)
            except (OSError, EOFError):
                pass
            except TimeoutError:
                raise CoverageFailure("WORKER_STOP_FAILED") from None
            finally:
                if self.read_task.done():
                    self.read_task = None
        if started:
            process.close()
        self.process, self.start_task = None, None
        self.exit_confirmed = True
        self.worker, self.model = None, None
