"""How does a council invocation combine actual outcomes and print its exit code?"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Iterable
from contextvars import ContextVar
from typing import Never

from pydantic import ValidationError

from idhazh.contracts.council_events import CouncilExit as CouncilExit
from idhazh.contracts.council_events import CouncilProgram, ProgramFinished
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.council.tenancy import ShardResult

# Approved precedence and sentences are protocol constants, not tunable policy.
_PRECEDENCE = (CouncilExit.OK, CouncilExit.FAILED, CouncilExit.PUSH_REFUSED, CouncilExit.REFUSED)
_STARTED: ContextVar[bool] = ContextVar("council_unit_started", default=False)


class Parser(argparse.ArgumentParser):
    """Refuse invalid arguments without printing user input or exception text."""

    def error(self, message: str) -> Never:
        raise SystemExit(CouncilExit.REFUSED)


def worst(codes: Iterable[int]) -> CouncilExit:
    return max((CouncilExit(code) for code in codes), key=_PRECEDENCE.index, default=CouncilExit.OK)


def of_results(results: Iterable[ShardResult]) -> CouncilExit:
    return worst(
        CouncilExit.FAILED
        if result.outcome in (ShardOutcome.STOPPED_ON_DEADLINE, ShardOutcome.FAILED)
        else CouncilExit.OK
        for result in results
    )


def start_unit() -> None:
    """Mark real invocation, so a later failure cannot claim it stopped before work."""
    _STARTED.set(True)


def finish(program: CouncilProgram, code: int) -> int:
    from idhazh.council import event_log

    selected = CouncilExit(code)
    event_log.emit(
        ProgramFinished(program=program, code=selected),
        level=logging.INFO if selected is CouncilExit.OK else logging.ERROR,
        force=True,
    )
    return int(selected)


def run(program: CouncilProgram, work: Callable[[], int]) -> int:
    """Guard an entrypoint, keeping library exceptions intact outside the command."""
    from idhazh.council import event_log

    event_log.install()
    token = _STARTED.set(False)
    try:
        try:
            code = work()
        except (Exception, SystemExit, KeyboardInterrupt) as error:
            if isinstance(error, SystemExit) and error.code == 0 and not _STARTED.get():
                code = CouncilExit.OK
            else:
                refused = not _STARTED.get() and (
                    program not in (CouncilProgram.SETTLE, CouncilProgram.PUBLISH)
                    or (isinstance(error, SystemExit) and error.code == CouncilExit.REFUSED)
                    or isinstance(error, ValidationError)
                )
                event_log.failed(error, refused=refused)
                code = CouncilExit.REFUSED if refused else CouncilExit.FAILED
        return finish(program, code)
    finally:
        _STARTED.reset(token)
