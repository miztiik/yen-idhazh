"""Can a machine card be built that shows only the flags a machine has?

That is the one thing the panel exists to refuse. An empty `flags` cell is a
reading rather than a gap, so a card listing what a machine can do, without
listing what it cannot, answers a different question from the one asked - and
the shape is where that gets refused, because markup is where it gets forgotten.

Every case is built (CLAUDE.md section 13). Nothing here reads a committed
ledger: the archive has never produced a card at all.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idhazh.contracts.host_fingerprint import WATCHED_FLAGS
from idhazh.contracts.machine_panels import (
    UNRECORDED_COLOUR_STOP,
    MachineCard,
    MachineFlag,
    MachineIdentity,
    MachinePanels,
    WatchedFlag,
)

pytestmark = pytest.mark.contract


def _identity(stop: int = 1) -> MachineIdentity:
    return MachineIdentity(key="a1b2c3d4e5f60718", name="Intel Xeon Platinum 8573C", colour_stop=stop)


def _every_flag(*, present: frozenset[str] = frozenset()) -> list[MachineFlag]:
    return [MachineFlag(name=flag, present=flag.value in present) for flag in WatchedFlag]


def test_the_watched_vocabulary_has_exactly_one_home() -> None:
    """The enum restates the probe's tuple; it never holds a second copy of it.

    The module refuses to import on a mismatch, so this asserts the property the
    refusal protects rather than re-running the refusal.
    """
    assert tuple(flag.value for flag in WatchedFlag) == WATCHED_FLAGS
    assert len(WATCHED_FLAGS) == 12


def test_a_card_that_lists_only_what_the_machine_has_is_refused() -> None:
    with pytest.raises(ValidationError, match="every watched flag"):
        MachineCard(
            identity=_identity(),
            flags=[MachineFlag(name=WatchedFlag.AVX2, present=True)],
            flags_recorded=True,
            shards_drawn=4,
            shards_total=8,
        )


def test_a_card_carrying_every_flag_is_accepted_however_few_are_present() -> None:
    """The machine we draw most reports none of the watched AVX-512 entries."""
    card = MachineCard(
        identity=_identity(),
        flags=_every_flag(present=frozenset({"avx2", "f16c", "fma", "sse4_2"})),
        flags_recorded=True,
        shards_drawn=4,
        shards_total=8,
    )
    assert len(card.flags) == 12
    assert [flag.name.value for flag in card.flags] == list(WATCHED_FLAGS)
    assert sum(1 for flag in card.flags if flag.present) == 4


def test_a_card_the_fingerprint_never_reached_carries_no_flags_at_all() -> None:
    """Twelve absent chips would publish "never read" as "reported none of them"."""
    card = MachineCard(identity=_identity(), shards_drawn=1, shards_total=1)
    assert card.flags == []
    assert card.flags_recorded is False


def test_the_flag_order_on_a_card_is_the_probe_order_and_not_the_caller_order() -> None:
    shuffled = list(reversed(_every_flag()))
    with pytest.raises(ValidationError, match="in order"):
        MachineCard(
            identity=_identity(), flags=shuffled, flags_recorded=True, shards_drawn=1, shards_total=1
        )


def test_the_reserved_stop_is_the_last_one_the_ramp_holds() -> None:
    """Eight is the grey. A ninth stop would be a colour nobody has drawn."""
    assert UNRECORDED_COLOUR_STOP == 8
    assert MachineIdentity(key="x", name="Machine not recorded", colour_stop=8).colour_stop == 8
    with pytest.raises(ValidationError):
        MachineIdentity(key="x", name="A ninth machine", colour_stop=9)


def test_an_empty_payload_is_a_real_answer_and_stamps_itself() -> None:
    """Every panel has a day with nothing on it, so nothing here may be required."""
    panels = MachinePanels.model_validate({})
    assert panels.machines == [] and panels.splits == [] and panels.fleet == []
    assert panels.fleet_rows == 0
    assert panels.fingerprint_recording is True
    assert panels.version == MachinePanels.schema_version()
