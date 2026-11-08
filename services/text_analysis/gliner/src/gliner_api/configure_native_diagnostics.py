"""How are native diagnostics refused without formatting source-bearing records?"""

from __future__ import annotations

import logging
import os
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from importlib.util import find_spec
from threading import RLock
from typing import Final, Literal, Protocol, cast

NativeFailureCode = Literal["INPUT_UNSUPPORTED", "ANALYSIS_FAILED"]


class NativeDiagnosticError(RuntimeError):
    """Expose only a fixed native failure code and source-free message."""

    def __init__(self, code: NativeFailureCode) -> None:
        self.code = code
        super().__init__("The native model reported a diagnostic failure.")


@dataclass(slots=True)
class _NativeOperationRecord:
    code: NativeFailureCode | None = None

    def refuse(self, code: NativeFailureCode) -> None:
        if self.code != "ANALYSIS_FAILED":
            self.code = code


_CURRENT_OPERATION: Final[ContextVar[_NativeOperationRecord | None]] = ContextVar(
    "gliner_api.native_operation", default=None
)
_CONFIGURATION_LOCK: Final = RLock()

# These are the libraries' diagnostic vocabularies, not model or service settings.
_VERBOSITY_OPTIONS: Final = {
    "HF_HUB_VERBOSITY": frozenset({"debug", "info", "warning", "error", "critical"}),
    "TRANSFORMERS_VERBOSITY": frozenset(
        {"detail", "debug", "info", "warning", "error", "critical"}
    ),
}


@contextmanager
def native_operation() -> Iterator[None]:
    """Refuse a latched diagnostic even when native code catches its exception."""
    parent_record = _CURRENT_OPERATION.get()
    record = _NativeOperationRecord()
    token = _CURRENT_OPERATION.set(record)
    try:
        try:
            yield
        except Warning:
            record.refuse("INPUT_UNSUPPORTED")
        except Exception:
            if record.code is None:
                raise
    finally:
        _CURRENT_OPERATION.reset(token)
        if record.code is not None and parent_record is not None:
            parent_record.refuse(record.code)
    if record.code is not None:
        raise NativeDiagnosticError(record.code) from None


def _refuse_diagnostic(record: logging.LogRecord) -> None:
    if record.levelno < logging.WARNING:
        return
    code: NativeFailureCode = (
        "ANALYSIS_FAILED" if record.levelno >= logging.ERROR else "INPUT_UNSUPPORTED"
    )
    operation = _CURRENT_OPERATION.get()
    if operation is not None:
        operation.refuse(code)
    raise NativeDiagnosticError(code) from None


class _NativeDiagnosticHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _refuse_diagnostic(record)


class _RefuseLibraryDiagnostics(logging.Filter):
    """Refuse native-operation records without intercepting another provider."""

    def filter(self, record: logging.LogRecord) -> bool:
        if _CURRENT_OPERATION.get() is None:
            return True
        _refuse_diagnostic(record)
        return False


class _TransformerLoggingControls(Protocol):
    def set_verbosity(self, verbosity: int) -> None: ...

    def disable_propagation(self) -> None: ...

    def disable_progress_bar(self) -> None: ...


def _install_native_handler() -> None:
    logger = logging.getLogger("gliner2")
    native_handlers = [
        handler for handler in logger.handlers if isinstance(handler, _NativeDiagnosticHandler)
    ]
    handler = native_handlers[0] if native_handlers else _NativeDiagnosticHandler()
    for existing in tuple(logger.handlers):
        if existing is not handler:
            logger.removeHandler(existing)
    logger.addHandler(handler)
    logger.disabled = False
    logger.propagate = False
    logger.setLevel(logging.DEBUG)


def _filter_library_handlers(name: str) -> None:
    for handler in logging.getLogger(name).handlers:
        if not any(isinstance(value, _RefuseLibraryDiagnostics) for value in handler.filters):
            handler.addFilter(_RefuseLibraryDiagnostics())


def require_safe_import_controls() -> None:
    # Invalid verbosity values are otherwise printed through the process root at import.
    for name, options in _VERBOSITY_OPTIONS.items():
        value = os.environ.get(name)
        if value and value not in options:
            raise NativeDiagnosticError("ANALYSIS_FAILED")


def configure_native_diagnostics() -> None:
    """Install idempotent GLiNER controls before importing the local model SDK."""
    with _CONFIGURATION_LOCK, native_operation():
        _install_native_handler()
        warnings.filterwarnings("error", module=r"^gliner2(?:\.|$)")
        require_safe_import_controls()
        _filter_library_handlers("huggingface_hub")
        _filter_library_handlers("transformers")
        try:
            from huggingface_hub.constants import HF_HUB_DISABLE_PROGRESS_BARS
            from huggingface_hub.utils import disable_progress_bars
            from huggingface_hub.utils import logging as hub_logging

            _filter_library_handlers("huggingface_hub")
            hub_logging.set_verbosity(logging.ERROR)
            hub_logging.disable_propagation()
            if HF_HUB_DISABLE_PROGRESS_BARS is False:
                raise NativeDiagnosticError("ANALYSIS_FAILED")
            disable_progress_bars()

            if find_spec("transformers") is not None:
                from transformers.utils import logging as transformer_logging

                _filter_library_handlers("transformers")
                controls = cast(_TransformerLoggingControls, transformer_logging)
                controls.set_verbosity(logging.ERROR)
                controls.disable_propagation()
                controls.disable_progress_bar()
        except NativeDiagnosticError:
            raise
        except Warning:
            raise NativeDiagnosticError("INPUT_UNSUPPORTED") from None
        except Exception:
            raise NativeDiagnosticError("ANALYSIS_FAILED") from None
