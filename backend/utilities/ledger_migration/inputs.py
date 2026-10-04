"""Which named roots, ledgers, UTC months, run and commit does one migration take?

A named root that is not an existing directory is refused before anything is read.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from idhazh import config
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration.path_labels import describe_error, label_path
from utilities.ledger_migration.refusals import NotProvenError


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrationInputs:
    """The immutable named roots, ledgers, months and writer inputs of one migration."""

    state_dirs: Sequence[Path]
    which: Sequence[LedgerName]
    run_id: str
    git_sha: str
    today: date
    config_dir: Path = config.DEFAULT_CONFIG_DIR
    months: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "state_dirs", tuple(dict.fromkeys(path.resolve() for path in self.state_dirs))
        )
        object.__setattr__(self, "which", tuple(dict.fromkeys(self.which)))
        object.__setattr__(self, "months", tuple(self.months))


def require_root(state_dir: Path) -> None:
    """Refuse a named root that is not an existing directory."""
    try:
        exists = state_dir.is_dir()
    except OSError as refusal:
        raise NotProvenError(f"{label_path(state_dir)}: {describe_error(refusal)}") from refusal
    if not exists:
        raise NotProvenError(f"{label_path(state_dir)}: not an existing directory")
