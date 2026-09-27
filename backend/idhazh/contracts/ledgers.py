"""The registry of ledgers under `state/`: which ones exist, and where each one sits.

`config/ledgers.json` is the file; this is its shape. One entry per `LedgerName`
member, carrying the ledger's lifecycle state and the path it occupies.

The entry names and `LedgerName` must be exactly each other, and the refusal that
holds them there is the point of the file. `prune-state` empties every directory
under `state/` the registry does not claim, so a ledger nobody wrote an entry for
used to be a directory a later run silently emptied. It is now a build that will
not start.

Where a ledger lives is here. How its rows settle is not: a dedup key is a tuple
and a preference is a callable, and a callable is not JSON.
"""

from __future__ import annotations

from enum import UNIQUE, StrEnum, verify
from typing import Self

from pydantic import model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.ledger_name import LedgerName


@verify(UNIQUE)
class LedgerState(StrEnum):
    """What a writer may do with a ledger.

    All three are claimed, so all three are protected from the trial-tree sweep.
    The state says what a writer may do, never whether the data survives -
    deleting a ledger's rows for good is something a person does on purpose.
    """

    LIVE = "live"
    PAUSED = "paused"
    RETIRED = "retired"


@verify(UNIQUE)
class Grain(StrEnum):
    """Where a ledger's files sit today, and the enum goes when they sit one way.

    Removal condition: `docs/concepts/telemetry-intent.md` requires every tree
    under `state/` to reach one pattern. A member is deleted by the migration
    that empties it, and the enum with the last of them. Five shapes are recorded
    because all five are really on disk right now, not because five is a design.
    """

    FLAT = "flat"
    DAY_FILE = "day"
    DAY_TREE = "tree"
    MONTH_FILE = "month"
    STAMPED = "stamp"


#: Which of `stem` and `suffix` each grain needs. A flat file is the only one
#: that names itself; a day directory is the only one with no extension.
_NEEDS_A_STEM: dict[Grain, bool] = {
    Grain.FLAT: True,
    Grain.DAY_FILE: False,
    Grain.DAY_TREE: False,
    Grain.MONTH_FILE: False,
    Grain.STAMPED: False,
}
_NEEDS_A_SUFFIX: dict[Grain, bool] = {
    Grain.FLAT: True,
    Grain.DAY_FILE: True,
    Grain.DAY_TREE: False,
    Grain.MONTH_FILE: True,
    Grain.STAMPED: True,
}


class LedgerEntry(Model):
    """One ledger: its typed name, whether it is written, and where it sits."""

    name: LedgerName
    state: LedgerState
    grain: Grain
    prefix: tuple[str, ...]
    stem: str | None = None
    suffix: str | None = None

    @model_validator(mode="after")
    def _the_builders_can_use_this(self) -> Self:
        """Refuse an entry no path could be built from, while an operator is reading.

        Every clause here is a path the builders would otherwise emit wrong: a
        flat file with no name, a day file with no extension, a directory
        carrying one, or a segment that walks out of `state/`.
        """
        for segment in self.prefix:
            if not segment or "/" in segment or "\\" in segment or segment in {".", ".."}:
                raise ValueError(
                    f"{self.name} has {segment!r} in its prefix. A prefix is one directory "
                    "name per element, and it never leaves state/"
                )
        if self.grain is not Grain.FLAT and not self.prefix:
            raise ValueError(
                f"{self.name} files by {self.grain.value} and has no prefix, so its files "
                "would sit loose at the top of state/. Give it a directory"
            )
        if _NEEDS_A_STEM[self.grain] != (self.stem is not None):
            raise ValueError(
                f"{self.name} files by {self.grain.value} and "
                f"{'needs a stem' if _NEEDS_A_STEM[self.grain] else 'is named by its period'}, "
                f"so stem must be {'set' if _NEEDS_A_STEM[self.grain] else 'null'}"
            )
        if _NEEDS_A_SUFFIX[self.grain] != (self.suffix is not None):
            raise ValueError(
                f"{self.name} files by {self.grain.value} and "
                f"{'is a file' if _NEEDS_A_SUFFIX[self.grain] else 'is a directory'}, "
                f"so suffix must be {'set' if _NEEDS_A_SUFFIX[self.grain] else 'null'}"
            )
        return self


class LedgersConfig(Model):
    """Every ledger under `state/`, one entry each."""

    ledgers: list[LedgerEntry]

    @model_validator(mode="after")
    def _every_ledger_exactly_once(self) -> Self:
        """The entries and `LedgerName` are each other, or the build stops naming the gap.

        An entry for a name nobody declared is refused by the field's own type.
        This is the other half: a member with no entry, and a member with two.
        """
        named = [entry.name for entry in self.ledgers]
        missing = sorted(member.value for member in LedgerName if member not in set(named))
        if missing:
            raise ValueError(
                f"no entry for {', '.join(missing)}. Every ledger needs one, because "
                "prune-state empties every directory under state/ the registry does not "
                "claim"
            )
        twice = sorted({name.value for name in named if named.count(name) > 1})
        if twice:
            raise ValueError(
                f"{', '.join(twice)} has more than one entry. One ledger sits in one "
                "place, so two entries are two answers and nothing chooses between them"
            )
        return self

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls.model_validate_json(text)
