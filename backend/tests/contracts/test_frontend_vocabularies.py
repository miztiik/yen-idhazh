"""Do the frontend's two closed sets still hold what their Python enums hold?

The other half of the control that replaced the generator. `SERVER_JOB` decides
which machine rows a console route can place, and `WATCHED_FLAG` decides how
many instruction-set chips a machine card draws. Both are copied by hand into
`frontend/src/lib/server/host-fingerprint.ts`, and a member that reached one
side and not the other is silent on the page: an unplaced job drops its row,
and a missing flag draws eleven chips where the probe recorded twelve.

Order is asserted as well as membership. The flag chips are drawn in the order
this array holds, so a reordered copy moves the page without moving a fact.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT, read_text

from idhazh.contracts.base import ServerJob
from idhazh.contracts.machine_panels import WatchedFlag

pytestmark = pytest.mark.contract

READER: Final[Path] = REPO_ROOT / "frontend" / "src" / "lib" / "server" / "host-fingerprint.ts"

#: The two enums, by the name the frontend gives each one.
VOCABULARIES: Final[dict[str, tuple[str, ...]]] = {
    "SERVER_JOB": tuple(member.value for member in ServerJob),
    "WATCHED_FLAG": tuple(member.value for member in WatchedFlag),
}


def members(text: str, name: str) -> tuple[str, ...]:
    """What the frontend's `export const <name> = [...] as const;` holds, in order."""
    found = re.search(rf"export const {name} = \[(.*?)\] as const;", text, re.DOTALL)
    assert found, f"{READER.name} no longer declares {name} as a frozen array"
    return tuple(re.findall(r"'([^']*)'", found[1]))


@pytest.mark.parametrize("name", sorted(VOCABULARIES))
def test_the_frontend_copy_holds_exactly_the_enum_s_members(name: str) -> None:
    assert members(read_text(READER), name) == VOCABULARIES[name], (
        f"{name} in {READER.name} has drifted from the Python enum it copies. "
        "Change both, or neither."
    )
