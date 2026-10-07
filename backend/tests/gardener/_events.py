"""Which gardener events did the code under test log, read off the records and never the text?"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from idhazh.contracts.base import Model
from idhazh.gardener import event_log


def events[E: Model](records: Iterable[logging.LogRecord], kind: type[E]) -> list[E]:
    """Every event of one kind the records carry, in the order they were logged."""
    return [held for record in records if isinstance(held := event_log.payload(record), kind)]


def the_event[E: Model](records: Iterable[logging.LogRecord], kind: type[E]) -> E:
    """The one event of this kind the records carry; a test that logged two of it fails here."""
    (held,) = events(records, kind)
    return held
