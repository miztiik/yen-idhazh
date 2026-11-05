"""Which judges and dates does this invocation authorize, without storing a ledger?"""

from __future__ import annotations

import json
import os

from idhazh.contracts.base import DateStamp
from idhazh.contracts.council_invocation import SelectedJudge as SelectedJudge
from idhazh.contracts.council_invocation import Selection as Selection
from idhazh.contracts.knobs.council import CouncilConfig

# These names describe invocation transport, not persisted fields or tunable policy.
ENVIRONMENT_NAME = "COUNCIL_SELECTION"


def for_dates(council: CouncilConfig, dates: tuple[DateStamp, ...]) -> Selection:
    """An explicitly named local date list, without asking about outstanding work."""
    return Selection(
        mode="scheduled",
        judges=tuple(
            SelectedJudge(
                tenant=name,
                status=council.declaration(name).lifecycle_status,
                dates=tuple(dict.fromkeys(dates)),
            )
            for name in council.running()
        ),
    )


def manual(council: CouncilConfig, *, judges: str, day: DateStamp) -> Selection:
    """Validate the entire request before importing even the first selected judge."""
    raw = json.loads(judges)
    if not isinstance(raw, list) or not raw or any(not isinstance(name, str) for name in raw):
        raise ValueError("manual judges must be a nonempty JSON list of names")
    return Selection(
        mode="manual",
        judges=tuple(
            SelectedJudge(
                tenant=name, status=council.declaration(name).lifecycle_status, dates=(day,)
            )
            for name in raw
        ),
    ).check(council)


def from_environment(council: CouncilConfig) -> Selection | None:
    """Absent transport means a local command; present but empty transport is refused."""
    raw = os.environ.get(ENVIRONMENT_NAME)
    if raw is None:
        return None
    try:
        return Selection.model_validate_json(raw).check(council)
    except ValueError as error:
        from idhazh.council.outcome import CouncilExit

        raise SystemExit(CouncilExit.REFUSED) from error
