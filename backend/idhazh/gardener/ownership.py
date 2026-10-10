"""Which repository folders may one declared gardener task change?"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from idhazh import ledger
from idhazh.contracts.knobs.gardener import CompactionPolicy, TaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import paths, staging


def contains(path: str, prefix: str) -> bool:
    """Compare whole path segments, never a string prefix."""
    return PurePosixPath(path).is_relative_to(PurePosixPath(prefix))


def owned_prefixes(policy: TaskPolicy, declared: tuple[LedgerName, ...] = ()) -> tuple[str, ...]:
    """Resolve ledger claims from their registry; retain non-ledger collection claims.

    Config still chooses which of a ledger's folders this task owns. Naming a
    ledger does not grant its raw writer's folder to a compact-only fixture.
    """
    if any(folder in ("state", "state/raw", "state/compact") for folder in policy.owns):
        raise ValueError("a task must name its own folders, not a blanket state root")
    expected: list[str] = []
    if isinstance(policy, CompactionPolicy):
        for root in policy.state_roots:
            registry = paths.overlay_registry(PurePosixPath(root).parts[1:])
            expected += [
                builder(Path(ledger.STATE_DIRNAME), policy.ledger, registry=registry).as_posix()
                for builder in (paths.raw_root, paths.compact_folder)
            ]
    else:
        expected += [staging.staged_path(which) for which in declared]
    if not expected:
        return tuple(policy.owns)
    result: list[str] = []
    for folder in policy.owns:
        if not contains(folder, ledger.STATE_DIRNAME):
            result.append(folder)
        elif any(contains(folder, prefix) for prefix in expected):
            result.append(folder)
        else:
            raise ValueError(
                f"{folder} is not an owned folder of the task's declared ledgers: {expected}"
            )
    return tuple(result)
