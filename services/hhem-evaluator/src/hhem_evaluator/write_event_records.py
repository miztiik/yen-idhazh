"""How are formatted records written without logging's silent fallback?"""

import logging
from typing import TextIO


class StrictEventHandler(logging.Handler):
    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        self.stream.write(self.format(record) + "\n")
        self.stream.flush()
