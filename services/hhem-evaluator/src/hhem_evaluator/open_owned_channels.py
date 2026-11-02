"""Which pipes carry only this launcher's validated control packets and events?"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class OwnedChannels:
    control: TextIO
    events: TextIO


@contextmanager
def open_owned_channels() -> Iterator[OwnedChannels]:
    with os.fdopen(
        os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n", buffering=1
    ) as control, os.fdopen(
        os.dup(sys.stderr.fileno()), "w", encoding="utf-8", newline="\n", buffering=1
    ) as events:
        os.set_inheritable(control.fileno(), False)
        os.set_inheritable(events.fileno(), False)
        with open(os.devnull, "w", encoding="utf-8") as discarded:
            os.dup2(discarded.fileno(), sys.stdout.fileno())
            os.dup2(discarded.fileno(), sys.stderr.fileno())
        # Only a child launcher uses this scope. Keep raw stdio discarded
        # through interpreter shutdown, including auxiliary-process diagnostics.
        yield OwnedChannels(control=control, events=events)
