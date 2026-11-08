"""How is the independently owned UniEval process started, exchanged with and joined?"""

import asyncio
import multiprocessing
import time
from multiprocessing.process import BaseProcess
from pathlib import Path

from local_api_host.propagate_trace_context import OperationMetadata, create_root_operation
from pydantic import ValidationError

from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.shared.exchange_packets import ByteChannel, encode_packet
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_result import UnievalModelIdentity
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalBootstrap,
    UnievalCommand,
    UnievalFinished,
    UnievalReady,
    UnievalReply,
    UnievalStartupFailed,
    validate_request_reply,
)
from summary_evaluator.unieval.exchange_packets import command_byte_limit
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.unieval_worker import run_unieval_worker


class UnievalSupervisor:
    def __init__(self, settings: UnievalSettings, root: Path) -> None:
        self.settings, self.root = settings, root
        self.process: BaseProcess | None = None
        self.channel: ByteChannel | None = None
        self.lifetime: ByteChannel | None = None
        self.worker: WorkerIdentity | None = None
        self.model: UnievalModelIdentity | None = None
        self.read_task: asyncio.Task[bytes] | None = None
        self.start_task: asyncio.Task[None] | None = None
        self.generation = 0
        self.exit_confirmed = True
        self.last_exit: tuple[int, int] | None = None
        self.bootstrap: UnievalBootstrap | None = None
        self.load_operation: OperationMetadata | None = None
        self.outstanding: UnievalCommand | None = None
        self.command_limit = command_byte_limit(settings, 1)

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int
    ) -> BaseProcess:
        return multiprocessing.get_context("spawn").Process(
            target=run_unieval_worker,
            args=(channel, lifetime, self.root, generation, self.command_limit),
            daemon=False,
        )

    def issue_load(self, operation_metadata: OperationMetadata) -> None:
        """Issue a service-owned load operation while preserving startup callback signatures."""
        if self.process is not None or not self.exit_confirmed:
            raise UnievalFailure(UnievalError.from_code("WORKER_STOP_FAILED"))
        self.load_operation = operation_metadata

    async def start(self) -> None:
        if self.process is not None or not self.exit_confirmed:
            raise UnievalFailure(UnievalError.from_code("WORKER_STOP_FAILED"))
        self.generation += 1
        self.bootstrap = UnievalBootstrap(
            version=UNIEVAL_WORKER_VERSION,
            operation_metadata=self.load_operation or create_root_operation(),
            settings=self.settings,
        )
        self.load_operation = None
        self.command_limit = command_byte_limit(self.settings, self.generation)
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
            raise UnievalFailure(UnievalError.from_code("WORKER_EXITED")) from None
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
                    parent.send_bytes, encode_packet(self.bootstrap, self.command_limit)
                )
                reply = (await self.receive()).root
                if isinstance(reply, UnievalStartupFailed):
                    raise UnievalFailure(reply.error)
                if (
                    not isinstance(reply, UnievalReady)
                    or reply.worker.generation != self.generation
                    or reply.worker.pid != process.pid
                    or reply.model.reference != self.settings.assets.model.reference
                    or reply.model.loaded_revision != self.settings.assets.model.revision
                    or (
                        reply.model.reference_code_revision
                        != self.settings.assets.reference_code_revision
                    )
                ):
                    raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
                self.worker, self.model = reply.worker, reply.model
        except TimeoutError:
            raise UnievalFailure(UnievalError.from_code("MODEL_LOAD_FAILED")) from None
        except (OSError, EOFError, ValueError, RuntimeError):
            raise UnievalFailure(UnievalError.from_code("WORKER_EXITED")) from None

    async def send(self, command: UnievalCommand) -> None:
        if self.channel is None or self.model is None:
            raise UnievalFailure(UnievalError.from_code("WORKER_NOT_READY"))
        if self.outstanding is not None or command.generation != self.generation:
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        try:
            encoded = encode_packet(command, self.command_limit)
            self.outstanding = command
            await asyncio.to_thread(self.channel.send_bytes, encoded)
        except ValueError:
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED")) from None
        except (OSError, EOFError):
            raise UnievalFailure(UnievalError.from_code("WORKER_EXITED")) from None

    async def receive(self) -> UnievalReply:
        if self.channel is None or self.read_task is not None:
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        task = asyncio.create_task(
            asyncio.to_thread(self.channel.recv_bytes, self.settings.worker.max_reply_bytes)
        )
        self.read_task = task
        try:
            encoded = await asyncio.shield(task)
            reply = UnievalReply.model_validate_json(encoded)
            packet = reply.root
            if isinstance(packet, UnievalReady | UnievalStartupFailed):
                if (
                    self.bootstrap is None
                    or self.model is not None
                    or packet.operation_metadata != self.bootstrap.operation_metadata
                ):
                    raise ValueError("Startup outcome does not match its issued load operation")
            elif isinstance(packet, RequestPacket):
                if self.outstanding is None:
                    raise ValueError("No UniEval command is outstanding")
                validate_request_reply(self.outstanding, packet)
                if isinstance(packet, UnievalFinished):
                    self.outstanding = None
            return reply
        except (ValidationError, ValueError):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED")) from None
        except (OSError, EOFError):
            raise UnievalFailure(UnievalError.from_code("WORKER_EXITED")) from None
        finally:
            if task.done():
                self.read_task = None

    async def stop(self) -> None:
        process = self.process
        if process is None:
            if not self.exit_confirmed:
                raise UnievalFailure(UnievalError.from_code("WORKER_STOP_FAILED"))
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
                    raise ValueError("The UniEval worker exit is unconfirmed")
                if process.pid is not None:
                    self.last_exit = (process.pid, process.exitcode)
            else:
                process.close()
        except (OSError, ValueError, AssertionError, TimeoutError):
            raise UnievalFailure(UnievalError.from_code("WORKER_STOP_FAILED")) from None
        finally:
            if self.channel is not None:
                self.channel.close()
                self.channel = None
        pending = self.read_task
        if pending is not None:
            try:
                async with asyncio.timeout_at(forced):
                    await asyncio.shield(pending)
            except (OSError, EOFError):
                pass
            except TimeoutError:
                raise UnievalFailure(UnievalError.from_code("WORKER_STOP_FAILED")) from None
            finally:
                if pending.done():
                    self.read_task = None
        if started:
            process.close()
        self.process, self.start_task = None, None
        self.exit_confirmed = True
        self.worker, self.model = None, None
        self.outstanding = None
