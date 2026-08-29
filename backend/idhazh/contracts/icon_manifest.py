"""The icon set the published surface may draw from (`frontend/src/lib/icons/manifest.json`).

The manifest is generated from the committed source SVGs, never hand-written,
and it exists so the set is a closed vocabulary rather than whatever somebody
pasted into a component. A page names a mark by id; an id that is not here does
not resolve, and `icons.spec.ts` fails the build in both directions - an icon
nothing uses, and a use of an icon that does not exist.

Licence travels with the set. An icon is somebody's work, and the one place
that fact cannot be lost is the contract the build validates.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Slug


class IconManifest(Contract):
    """What was generated, from where, under which licence."""

    __schema_stem__: ClassVar[str] = "icon-manifest"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-29",
            change="Initial shape: the generated icon set, its source and its licence.",
            why=(
                "The surface had two inline SVGs and no system, so a mark was whatever "
                "a component happened to hold. Making the set a contract is what stops "
                "an id being invented at a call site, and what keeps the licence "
                "attached to the artwork rather than to a comment somewhere."
            ),
        ),
    )

    source: str
    licence: str
    icons: list[Slug]

    @model_validator(mode="after")
    def _ids_are_distinct_and_present(self) -> Self:
        if not self.icons:
            raise ValueError("the icon set may not be empty")
        if len(set(self.icons)) != len(self.icons):
            raise ValueError("icon ids must be distinct")
        if self.icons != sorted(self.icons):
            raise ValueError("icon ids must be sorted, so a diff shows an addition not a reorder")
        return self
