"""How is an explicit invocation selection validated before any plugin runs?"""

from __future__ import annotations

import json
import os

from idhazh import run_context
from idhazh.contracts.base import DateStamp
from idhazh.contracts.council_invocation import SelectedJudge as SelectedJudge
from idhazh.contracts.council_invocation import Selection as Selection
from idhazh.contracts.knobs.council import CouncilConfig

ENVIRONMENT_NAME = "COUNCIL_SELECTION"


def manual(
    council: CouncilConfig,
    *,
    judges: str,
    day: DateStamp,
    run_id: str,
    git_sha: str,
    attempt: int,
) -> Selection:
    """Resolve the whole explicit request before authorizing a single unit."""
    from idhazh.council.registry import tenants

    raw = json.loads(judges)
    if not isinstance(raw, list) or not raw or any(not isinstance(name, str) for name in raw):
        raise ValueError("manual judges must be a nonempty JSON list")
    if len(set(raw)) != len(raw):
        raise ValueError("duplicate selected judge")
    declarations = tuple(council.declaration(name) for name in raw)
    trials = tuple(
        name
        for name, declaration in zip(raw, declarations, strict=True)
        if declaration.lifecycle_status.value == "paused"
    )
    hosted = tenants(raw, council=council, trials=trials)
    return Selection(
        version=Selection.schema_version(),
        run_id=run_id,
        git_sha=git_sha,
        attempt=attempt,
        mode="manual",
        anchor_date=day,
        window=(day,),
        judges=tuple(
            SelectedJudge(
                tenant=host.judge_id,
                status=declaration.lifecycle_status,
                dates=(day,),
                shards=min(host.shard_count, council.shards),
            )
            for host, declaration in zip(hosted, declarations, strict=True)
        ),
    ).check(council)


def from_environment(council: CouncilConfig) -> Selection:
    """Missing or malformed authorization never defaults to a date-based grant."""
    from idhazh.council.outcome import CouncilExit

    try:
        selected = Selection.model_validate_json(os.environ[ENVIRONMENT_NAME]).check(council)
        if selected.attempt != run_context.run_attempt():
            raise ValueError("selection attempt differs from this job")
        return selected
    except (KeyError, ValueError) as error:
        raise SystemExit(CouncilExit.REFUSED) from error
