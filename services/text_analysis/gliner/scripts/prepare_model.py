"""How does model preparation report source-free outcomes outside the test process?"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Final, NoReturn

from gliner_api.configure_native_diagnostics import require_safe_import_controls

DEFAULT_ROOT: Final = Path(__file__).resolve().parents[4]


class _PreparationArgumentError(ValueError):
    def __init__(self) -> None:
        super().__init__("The model preparation arguments are invalid.")


class _PreparationParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _PreparationArgumentError() from None


class _PreparationArguments(argparse.Namespace):
    root: Path


def _parse_arguments() -> _PreparationArguments:
    parser = _PreparationParser(
        prog="prepare-gliner-model",
        description="Prepare configured GLiNER model assets without claiming API readiness.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Repository root containing the committed GLiNER configuration.",
    )
    return parser.parse_args(namespace=_PreparationArguments())


async def _prepare_assets() -> int:
    from local_api_host.propagate_trace_context import create_root_operation

    from gliner_api.declare_event_contracts import ServiceEventData, ServiceFailureCode
    from gliner_api.emit_events import EventEmitter
    from gliner_api.load_model import prepare_model
    from gliner_api.load_settings import LoggingSettings, load_settings

    emitter = EventEmitter(LoggingSettings())
    enabled = True
    error_code: ServiceFailureCode = "STARTUP_FAILED"
    try:
        require_safe_import_controls()
        arguments = _parse_arguments()
        settings = load_settings(arguments.root)
        enabled = settings.enabled
        await emitter.aclose()
        emitter = EventEmitter(settings.logging)
        if not enabled:
            print("GLiNER model asset preparation is disabled.")
            return 0
        error_code = "MODEL_UNAVAILABLE"
        prepare_model(arguments.root)
        error_code = "LOGGING_FAILED"
        print("GLiNER model assets prepared; API readiness requires native loading.")
        return 0
    except Exception:
        await emitter.emit(
            create_root_operation(),
            "gliner.service.failed",
            ServiceEventData(status="failed", enabled=enabled, error_code=error_code),
        )
        return 1
    finally:
        await emitter.aclose()


def main() -> int:
    """Keep raw dependency, argument, preparation and event exceptions off stderr."""
    try:
        return asyncio.run(_prepare_assets())
    except Exception:
        print("GLiNER model asset preparation failed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
