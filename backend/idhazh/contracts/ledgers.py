"""The registry of ledgers under `state/`: which families and ledgers exist, and where each sits.

`config/ledgers.json` is the file; this is its shape. A family is one top-level
folder under `state/`, and it carries what is decided for the folder as a whole:
its lifecycle status, one plain line saying what it holds, and the day it was
onboarded. A ledger is one row shape filed one way at one address, and each
`LedgerName` member is exactly one ledger in exactly one family.

The ledger names and `LedgerName` must be exactly each other, and the refusal
that holds them there is the point of the file. `prune-state` empties every
directory under `state/` the registry does not claim, so a ledger nobody wrote an
entry for used to be a directory a later run silently emptied. It is now a build
that will not start.

Where a ledger lives is here. How its rows settle is not: a dedup key is a tuple
and a preference is a callable, and a callable is not JSON.
"""

from __future__ import annotations

from datetime import date
from enum import UNIQUE, StrEnum, verify
from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.ledger_name import LedgerName


@verify(UNIQUE)
class LedgerLifecycleStatus(StrEnum):
    """Whether a family's ledgers are written: active, paused or retired.

    `active` is written and read. `paused` is not written now and will resume.
    `retired` is no longer written and is not coming back. All three are claimed,
    so all three are protected from the trial-tree sweep: the status says what a
    writer may do, never whether the data survives. Deleting a family's data for
    good is something a person does on purpose.

    Nothing on the write path reads this yet, so a test holds every family at
    `active` until something does.
    """

    ACTIVE = "active"
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


def _upper_snake(name: str) -> str:
    """`content-similarity-judge` -> `CONTENT_SIMILARITY_JUDGE`: a name as Python spells it."""
    return name.replace("-", "_").upper()


class LedgerEntry(Model):
    """One ledger: its typed name, how it files, and where it sits."""

    name: LedgerName
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


class LedgerFamily(Model):
    """One top-level folder under `state/`: its status, what it holds, and its ledgers."""

    name: str = Field(min_length=1)
    lifecycle_status: LedgerLifecycleStatus
    description: str = Field(min_length=1, pattern=r"^[^\r\n]+$")
    onboarded: date
    ledgers: list[LedgerEntry] = Field(min_length=1)


class LedgersConfig(Model):
    """Every family under `state/`, and every ledger in exactly one of them."""

    families: list[LedgerFamily]

    @model_validator(mode="after")
    def _every_family_once(self) -> Self:
        """Two families of one name are two lists claiming one folder.

        Each would carry its own status, so the folder would have two answers to
        whether it is written and nothing would choose between them.
        """
        names = [family.name for family in self.families]
        twice = sorted({name for name in names if names.count(name) > 1})
        if twice:
            raise ValueError(
                f"family {', '.join(twice)} is listed more than once. A family is one "
                "folder under state/, so all of its ledgers go in one list"
            )
        return self

    @model_validator(mode="after")
    def _every_ledger_exactly_once(self) -> Self:
        """The entries and `LedgerName` are each other, or the build stops naming the gap.

        An entry for a name nobody declared is refused by the field's own type.
        This is the other half: a member with no entry, a member listed in two
        families, and a member listed twice in one.
        """
        held_in: dict[LedgerName, list[str]] = {}
        for family in self.families:
            for held in family.ledgers:
                held_in.setdefault(held.name, []).append(family.name)
        missing = sorted(member.value for member in LedgerName if member not in held_in)
        if missing:
            raise ValueError(
                f"no entry for {', '.join(missing)}. Every ledger needs one, because "
                "prune-state empties every directory under state/ the registry does not "
                "claim"
            )
        split = sorted(
            f"{name.value} is listed in families {' and '.join(sorted(set(families)))}"
            for name, families in held_in.items()
            if len(set(families)) > 1
        )
        if split:
            raise ValueError(
                f"{'; '.join(split)}. A ledger belongs to one family, so its status has "
                "one answer"
            )
        twice = sorted(name.value for name, families in held_in.items() if len(families) > 1)
        if twice:
            raise ValueError(
                f"{', '.join(twice)} has more than one entry. One ledger sits in one "
                "place, so two entries are two answers and nothing chooses between them"
            )
        return self

    @model_validator(mode="after")
    def _every_ledger_sits_in_its_family(self) -> Self:
        """A family is the folder its ledgers sit in, so the two names must agree.

        The folder is the first segment of a ledger's prefix. A ledger that is one
        file at the top of `state/` has no prefix, and its family is named by the
        file's stem instead. A ledger filed under one folder and listed in another
        family would take that family's status while sitting somewhere else.
        """
        misplaced: list[str] = []
        for family in self.families:
            for held in family.ledgers:
                top = held.prefix[0] if held.prefix else held.stem
                if top == family.name:
                    continue
                where = f"state/{top}/" if held.prefix else f"state/{held.stem}{held.suffix}"
                misplaced.append(
                    f"{held.name} sits at {where} and is listed in family {family.name}"
                )
        if misplaced:
            raise ValueError(
                f"{'; '.join(sorted(misplaced))}. A family is named for the top-level "
                "folder under state/ its ledgers sit in, or for the stem of a file at "
                "the top of state/"
            )
        return self

    @model_validator(mode="after")
    def _every_member_is_named_for_its_place(self) -> Self:
        """One spelling per ledger: the Python name is built from the family and the value.

        A ledger that is its own family is its value in upper snake case. A
        ledger inside a family puts the family's name first. Checked here rather
        than beside the enum, because the family is a fact only this file holds.
        """
        misnamed: list[str] = []
        for family in self.families:
            for held in family.ledgers:
                spelled = _upper_snake(held.name.value)
                if held.name.value != family.name:
                    spelled = f"{_upper_snake(family.name)}_{spelled}"
                if held.name.name != spelled:
                    misnamed.append(f"LedgerName.{held.name.name} should be {spelled}")
        if misnamed:
            raise ValueError(
                f"{'; '.join(sorted(misnamed))}. A member's Python name is its value in "
                "upper snake case, with its family's name in front when the ledger sits "
                "inside a family"
            )
        return self

    @classmethod
    def from_json(cls, text: str) -> Self:
        return cls.model_validate_json(text)
