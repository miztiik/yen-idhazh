"""How does a CLI signal allow an asynchronous task to close its owned children?"""

import asyncio
import contextlib
import signal
from collections.abc import Awaitable, Callable


def run_task[Result](work: Callable[[], Awaitable[Result]]) -> Result:
    async def run() -> Result:
        loop, task = asyncio.get_running_loop(), asyncio.current_task()
        previous = {}
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.getsignal(signum)
            signal.signal(
                signum,
                lambda *_: (
                    loop.call_soon_threadsafe(task.cancel)
                    if task is not None and not task.cancelling()
                    else None
                ),
            )
        try:
            return await work()
        finally:
            for signum, handler in previous.items():
                with contextlib.suppress(ValueError):
                    signal.signal(signum, handler)

    return asyncio.run(run())
