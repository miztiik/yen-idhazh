"""How command logs get a UTC timestamp on stderr."""

from __future__ import annotations

import logging
import sys
import time
from typing import override


class _UtcFormatter(logging.Formatter):
    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        timestamp = time.strftime(datefmt or "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
        return f"{timestamp}.{int(record.msecs):03d}Z"


def configure_command_logging(level: int | str) -> None:
    """Install the command's stderr handler with UTC timestamps."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_UtcFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=level, handlers=[handler])
