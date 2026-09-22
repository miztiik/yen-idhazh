"""What happens when a config still spells a knob that was retired."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def refuse_a_removed_knob(block: str, data: Any, names: Mapping[str, str]) -> Any:
    """Fail a config that still spells a removed knob, and say where it went.

    Every model here forbids unknown keys, so a removed name already fails - with
    "extra inputs are not permitted", which does not tell an operator where their
    number went. Ignoring it silently would be worse: that is how somebody comes
    to believe a value nothing reads.

    **An empty replacement means the knob is gone rather than renamed**, because
    the thing it tuned is gone. Pointing at a successor that does not exist is
    the same defect one level down.

    **A replacement that carries a dot is already a whole path** and is printed
    as it stands. A knob does not always land in the block it left - reasoning
    stopped being a decoding setting and became a marker on the entry - so
    prefixing the block onto it would send an operator to
    `models.<role>.inference.thinking_close`, a key that has never existed.
    """
    if not isinstance(data, dict):
        return data
    carried = sorted(name for name in names if name in data)
    if carried:
        spelled = "; ".join(
            f"{block}.{name} is now "
            f"{names[name] if '.' in names[name] else f'{block}.{names[name]}'}"
            if names[name]
            else f"{block}.{name} is gone and nothing replaces it"
            for name in carried
        )
        raise ValueError(
            f"{block} carries a knob that was removed ({spelled}). Rename or delete it - "
            "a knob nothing reads is a number somebody believes"
        )
    return data
