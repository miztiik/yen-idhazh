"""What does an error a gardener pass meets mean: a member already gone, one GitHub will
not delete, an API that is down, a download budget spent, or a code defect?

One pure function answers it, `classify`, and every place a gardener pass
catches an error asks it: the walk that deletes a collection's members
(`one_at_a_time.take`), the GitHub driver's deletes (`github_collections`), the
runner, for an error that escapes a task, the ledger prune, and the
compaction's download budget. So a code defect is `raised` whichever wrapper
caught it, and no wrapper relabels one.

**`HTTPError` is tested first**, because it is a kind of `URLError`, which is a
kind of `OSError`. Tested in another order, a refusal GitHub gave would read as
a connection that failed.

- **404 or 410, `GONE`.** On a delete, the member is already gone, and it
  counts as deleted.
- **409 or 422, `NOT_DELETABLE`.** On a delete, GitHub will not delete the
  member: the pass records its id as `not-deletable`, counts it against the
  ceiling, and goes on.
- **429, any 5xx, `URLError`, `TimeoutError` or `ConnectionError`,
  `API_UNAVAILABLE`.** The pass ends `deferred` with the fault
  `api-unavailable`, and the next wake asks again.
- **`OverBudgetError` no larger than the whole budget, `BUDGET_SPENT`.** A
  compaction step stops at `ceiling` for a wake with room.
- **`OverBudgetError` larger than the whole budget, `RAISED`.** No wake could
  take it, and only a person can raise the budget, so the step ends `failed`.
  A shard whose downloads passed the budget is a defect by the same rule.
- **Any other 4xx, and any other error, `RAISED`.** The pass ends `failed` with
  the fault `raised`, and the job turns red.

**`GONE` and `NOT_DELETABLE` mean something only on a delete.** A 404 on a read
says the request was wrong, not that a member went, so a stop for any cause but
`API_UNAVAILABLE` records the fault `raised` (`fault_of`).

**The answer is read from the error's type and status code alone, never from
its text.** An error's text can carry what the pass read, and the record keeps
none of it (Guardrail #11). Nothing inside a wake asks again: the next wake
already does, and nothing yet says how often GitHub's API is unavailable.
"""

from __future__ import annotations

import urllib.error
from enum import StrEnum
from http import HTTPStatus
from typing import Final

from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.gardener.file_listing import OverBudgetError

#: GitHub's answers to a DELETE whose member is already gone. HTTP's own codes,
#: so they are named here once and no setting may move them.
GONE_STATUSES: Final = frozenset({HTTPStatus.NOT_FOUND, HTTPStatus.GONE})

#: GitHub's answers to a DELETE it refuses for the member itself: one it holds
#: in use, or one it says it cannot process. A reading of GitHub's documentation
#: rather than a measurement: the first time a pass meets one, its answer is
#: recorded as a test fixture.
NOT_DELETABLE_STATUSES: Final = frozenset(
    {HTTPStatus.CONFLICT, HTTPStatus.UNPROCESSABLE_ENTITY}
)

#: The answer that says too many requests were sent: the API is there, and busy.
RATE_LIMITED: Final = HTTPStatus.TOO_MANY_REQUESTS

#: Every status code from this one up to `SERVER_ERRORS_END`, exclusive, is a
#: server error: GitHub's side failed, not the request.
SERVER_ERRORS_START: Final = HTTPStatus.INTERNAL_SERVER_ERROR
SERVER_ERRORS_END: Final = 600


class ErrorCause(StrEnum):
    """What one error means to the pass that met it. Not persisted: `fault_of` gives the word."""

    #: The member a delete named is already gone.
    GONE = "gone"
    #: GitHub will not delete the member a delete named.
    NOT_DELETABLE = "not-deletable"
    #: GitHub's API did not answer, or answered that it could not now.
    API_UNAVAILABLE = "api-unavailable"
    #: A fetch would pass what is left of the shard's download budget, and a
    #: later wake, with its whole budget, has room for it.
    BUDGET_SPENT = "budget-spent"
    #: A code defect, or a refusal only a person can resolve.
    RAISED = "raised"


def classify(error: Exception) -> ErrorCause:
    """What this error means to the pass that met it, from its type and status code alone."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code in GONE_STATUSES:
            return ErrorCause.GONE
        if error.code in NOT_DELETABLE_STATUSES:
            return ErrorCause.NOT_DELETABLE
        if error.code == RATE_LIMITED or SERVER_ERRORS_START <= error.code < SERVER_ERRORS_END:
            return ErrorCause.API_UNAVAILABLE
        return ErrorCause.RAISED
    if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return ErrorCause.API_UNAVAILABLE
    if isinstance(error, OverBudgetError):
        return ErrorCause.RAISED if error.needed > error.budget else ErrorCause.BUDGET_SPENT
    return ErrorCause.RAISED


def fault_of(cause: ErrorCause) -> GardenerFault:
    """The fault a pass stopped by this cause records: `api-unavailable`, or else `raised`.

    Every other cause either never stops a pass where it means what it says -
    a member gone, or not deletable, on a delete - or stops it for a defect.
    """
    if cause is ErrorCause.API_UNAVAILABLE:
        return GardenerFault.API_UNAVAILABLE
    return GardenerFault.RAISED
