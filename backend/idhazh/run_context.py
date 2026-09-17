"""What the runner says about this execution, as distinct from this machine.

Two modules already read the runner's environment and neither answers this
question. `fingerprint` answers what the determinism stamp needs - which
llama.cpp build decoded the weights, which class of machine ran the work.
`telemetry.host` answers which runner label the job drew. Which attempt is
running is neither: it is a fact about the execution, and it is the one runner
fact a filename depends on.

GitHub keeps `GITHUB_RUN_ID` stable across a re-run and increments
`GITHUB_RUN_ATTEMPT`. A writer that ignores the attempt hands its second try the
path its first already took, so the two collide in exactly the case where they
disagree - the first attempt died part way and the second one finished.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

#: What a machine outside GitHub Actions is. A developer box runs a stage once
#: and cannot race itself, so it is the first attempt by definition.
FIRST_ATTEMPT: Final = 1


def run_attempt(environ: Mapping[str, str] | None = None) -> int:
    """Which attempt at this run is executing, counting from one.

    A value that is not ASCII digits reads as the first attempt rather than
    raising. The variable is the platform's to set and a stage reading it is
    about to write rows; refusing the run over a cell nobody here filled would
    cost those rows to protect a filename.

    `isdigit` alone accepts another script's numerals, which `int` then takes -
    so the name would carry a numeral no later glob can match. The `isascii`
    clause is the load-bearing half, as it is in `day_partition`.
    """
    env = os.environ if environ is None else environ
    raw = env.get("GITHUB_RUN_ATTEMPT", "").strip()
    if not (raw.isascii() and raw.isdigit()):
        return FIRST_ATTEMPT
    return max(int(raw), FIRST_ATTEMPT)
