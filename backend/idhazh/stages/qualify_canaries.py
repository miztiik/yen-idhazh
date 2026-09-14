"""The five planted attacks alone, against the configured model.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from idhazh import (
    assemble,
    config,
)
from idhazh.contracts.base import canonical_json
from idhazh.contracts.qualification import (
    CanaryObservation,
    GateStatus,
)
from idhazh.evals import qualify
from idhazh.llm.server import (
    DEFAULT_ENDPOINT,
)
from idhazh.stages import common
from idhazh.stages.common import LOG, _run_canaries


def _canary_report(
    observations: Sequence[CanaryObservation], *, root: Path, required: int
) -> int:
    """Write what the attacks did, then say whether the gate holds.

    Split from the calls so the file-out half is reachable without a served
    model. Fail-closed: a gate that cannot speak for every planted attack
    returns non-zero.
    """
    assemble.write_atomic(
        root / "canaries.json",
        canonical_json([observation.model_dump(mode="json") for observation in observations]),
    )
    outcome = qualify.injection_canaries(observations, required=required)
    LOG.info("canary gate %s: %s", outcome.status.value, outcome.measured)
    LOG.info("canary detail: %s", outcome.detail)
    return 0 if outcome.status is GateStatus.PASSED else 1


def stage_qualify_canaries(
    *, settings: config.Settings, date: str, model_endpoint: str = DEFAULT_ENDPOINT
) -> int:
    """The five planted attacks alone, against the configured model.

    The arm was reachable only from inside `stage_qualify` at shard zero, so the
    only way to see what a canary did was a whole qualification (`CLAUDE.md`
    section 4). The fixtures are the file in, `canaries.json` is the file out,
    and the exit code is the gate.
    """
    observations = _run_canaries(settings, endpoint=model_endpoint)
    return _canary_report(
        observations,
        root=common.QUALIFICATION_ROOT / date,
        required=len(sorted(common.CANARY_DIR.glob("*.json"))),
    )
