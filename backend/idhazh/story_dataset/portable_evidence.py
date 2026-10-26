"""Does a record name local evidence by an absolute path?"""

import re
from typing import Any

from idhazh.contracts.base import Model

LOCAL_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]|file:)", re.IGNORECASE)


def refuse_absolute_evidence(record: Model) -> None:
    """Raise if any `evidence_reference` in the record is a local absolute path.

    Only writes are guarded. A saved record that already holds such a path still
    loads, so an existing checkpoint can still be exported.
    """
    _refuse_in(record.model_dump(mode="json"))


def _refuse_in(node: Any) -> None:
    if isinstance(node, list):
        for child in node:
            _refuse_in(child)
    elif isinstance(node, dict):
        for key, child in node.items():
            if key == "evidence_reference" and _is_local_absolute(child):
                raise ValueError(
                    "evidence_reference must be a relative path, not a local absolute path"
                )
            _refuse_in(child)


def _is_local_absolute(value: object) -> bool:
    return isinstance(value, str) and LOCAL_ABSOLUTE_PATH.match(value) is not None
