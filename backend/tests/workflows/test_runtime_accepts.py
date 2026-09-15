"""Does the pinned build accept every option the contract lets an operator name?"""

from __future__ import annotations

import re
from typing import Final

import pytest
from conftest import FIXTURES_DIR, read_text

from idhazh.contracts.knobs.models import SpeculationType

from ._harness import PINNED_LLAMA_BUILD

pytestmark = pytest.mark.workflow

#: `llama-server --help` as build b10598 printed it, captured by dispatching
#: `.github/workflows/probe.yml` on 2026-09-15 and downloading its artifact.
#: The build is in the filename so that bumping the pin fails the test below
#: rather than quietly checking the new build against the old one's answer.
RECORDED_HELP: Final = FIXTURES_DIR / "runtime" / f"{PINNED_LLAMA_BUILD}-llama-server-help.txt"


def accepted_speculation_types() -> frozenset[str]:
    """The comma list `--spec-type` prints, read out of the recorded help."""
    line = re.search(r"^--spec-type (\S+)$", read_text(RECORDED_HELP), re.MULTILINE)
    assert line, f"{RECORDED_HELP.name} has no --spec-type line to read"
    return frozenset(line.group(1).split(","))


def test_the_pinned_build_accepts_every_speculation_type_the_contract_offers() -> None:
    """A value the contract allows and the build refuses is a dead server, not a slow one.

    `SpeculationType` is a closed choice so that an operator cannot name a kind
    the runtime will not drive. That only works while the list agrees with the
    runtime, and it did not: the Gemma entry named `draft-simple` for a
    multi-token head, the server started, loaded the head, and then failed every
    request on `decode() failed: failed to process speculative batch` - five of
    five, one hour of bench time, run 34941400155.

    Reading a recorded `--help` is what makes this answerable offline
    (Guardrail #7). The recording is keyed on the pinned build, so moving the
    pin without re-running the probe fails here with a missing file rather than
    passing against an answer from a binary nobody runs any more.
    """
    offered = {kind.value for kind in SpeculationType}
    accepted = accepted_speculation_types()

    assert offered <= accepted, (
        f"{PINNED_LLAMA_BUILD} refuses {sorted(offered - accepted)}; "
        f"it accepts {sorted(accepted)}"
    )
