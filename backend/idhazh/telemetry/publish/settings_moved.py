"""Which recorded inputs and checker versions introduced a value on each UTC day?"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from idhazh.contracts.console_band import (
    BandCheckerMoved,
    BandSettingsMoved,
    CheckerMove,
    SettingsMove,
)
from idhazh.contracts.fingerprint import PipelineInputs


def comparable_inputs(inputs: PipelineInputs) -> dict[str, str]:
    """Flatten validated inputs in field order, then code-point key order."""
    flat: dict[str, str] = {}
    for name, value in inputs.model_dump(mode="json").items():
        if name in {"sampling", "runtime_flags"}:
            for key, held in sorted(value.items()):
                if held is not None and held != "":
                    flat[f"{name}.{key}"] = json.dumps(held, sort_keys=True)
        elif value is not None and value != "":
            flat[name] = json.dumps(value, sort_keys=True)
    return flat


def _compared_from(recorded: Sequence[str], first: str) -> str | None:
    if not recorded:
        return None
    if recorded[0] < first:
        return first
    return (date.fromisoformat(recorded[0]) + timedelta(days=1)).isoformat()


def inputs_moved(
    days: Mapping[str, Sequence[PipelineInputs]], first: str
) -> BandSettingsMoved:
    """Compare each name to its newest earlier day with a nonempty value."""
    previous: dict[str, set[str]] = {}
    recorded: list[str] = []
    changes: list[SettingsMove] = []
    for stamp, runs in sorted(days.items()):
        if not runs:
            continue
        recorded.append(stamp)
        held: dict[str, set[str]] = {}
        for run in runs:
            for name, value in comparable_inputs(run).items():
                held.setdefault(name, set()).add(value)
        moved = [
            name for name, values in held.items()
            if name in previous and not values <= previous[name]
        ]
        fields = list(PipelineInputs.model_fields)
        moved.sort(key=lambda name: (fields.index(name.partition(".")[0]), name))
        if stamp >= first and moved:
            changes.append(SettingsMove(date=stamp, inputs=moved))
        previous.update(held)
    return BandSettingsMoved(
        compared_from=_compared_from(recorded, first), changes=changes
    )


def strip_scorer(version: str) -> str:
    """Keep the scorer itself, not metrics, confidence bands or lead rules."""
    return ";".join(
        part for part in version.split(";")
        if not part.startswith(("metrics-", "bands=", "lead="))
    )


def checker_moved(
    days: Mapping[str, Sequence[str]], first: str
) -> BandCheckerMoved:
    """A new whole checker version may leave the faithfulness scorer unchanged."""
    previous: set[str] | None = None
    recorded: list[str] = []
    changes: list[CheckerMove] = []
    for stamp, versions in sorted(days.items()):
        held = {version for version in versions if version}
        if not held:
            continue
        recorded.append(stamp)
        if stamp >= first and previous is not None and not held <= previous:
            changes.append(CheckerMove(
                date=stamp,
                score_moved=not {strip_scorer(v) for v in held}
                <= {strip_scorer(v) for v in previous},
            ))
        previous = held
    return BandCheckerMoved(
        compared_from=_compared_from(recorded, first), changes=changes
    )
