"""What does an error a gardener pass meets mean: a member already gone, one GitHub will
not delete, an API that is down, a download budget spent, manual action, or a code defect?

One pure function answers it, `classify`, and every place a gardener pass
catches an error asks it: the walk that deletes a collection's members
(`one_at_a_time.take`), the GitHub driver's deletes (`github_collections`), the
runner, for an error that escapes a task, the ledger prune, and the
compaction's download budget. So a code defect is `raised` whichever wrapper
caught it, and only an explicit `ManualActionError` is `manual-action`.

**`HTTPError` is tested first**, because it is a kind of `URLError`, which is a
kind of `OSError`. Tested in another order, a refusal GitHub gave would read as
a connection that failed.

- **404 or 410, `GONE`.** On a delete, the member is already gone, and it
  counts as deleted.
- **409 or 422, `NOT_DELETABLE`.** On a delete, GitHub will not delete the
  member: the pass records its id as `not-deletable`, counts it against the
  ceiling, and goes on.
- **A 403 with `x-ratelimit-remaining: 0` or `retry-after`, 429, any 5xx,
  `URLError`, `TimeoutError` or `ConnectionError`, `API_UNAVAILABLE`.** The
  pass ends `deferred` with the fault `api-unavailable`, and the next wake asks
  again.
- **`OverBudgetError` no larger than the whole budget, `BUDGET_SPENT`.** A
  compaction step stops at `ceiling` for a wake with room.
- **`ManualActionError`, `MANUAL_ACTION`.** A named refusal only a person can
  settle. The pass ends `failed` with the fault `manual-action`.
- **`OverBudgetError` larger than the whole budget, `RAISED`.** This raw error
  means an unclassified or aggregate budget failure and remains a code defect.
  A period that explicitly knows it is larger than the whole budget constructs
  `ManualActionError` at that refusal site.
- **Any other 4xx, and any other error, `RAISED`.** The pass ends `failed` with
  the fault `raised`, and the job turns red.

**`GONE` and `NOT_DELETABLE` mean something only on a delete.** A 404 on a read
says the request was wrong, not that a member went, so a stop for any cause but
`API_UNAVAILABLE` or `MANUAL_ACTION` records the fault `raised` (`fault_of`).

**The answer is read from the error's type, status code and the response header
interface, never from its text.** Header names are case-insensitive, and only
the two closed temporary-refusal signals above are read. An error's text can
carry what the pass read, and the record keeps none of it (Guardrail #11).
Nothing inside a wake asks again: the next wake already does, and nothing yet
says how often GitHub's API is unavailable.
"""

from __future__ import annotations

import urllib.error
from enum import StrEnum
from http import HTTPStatus
from typing import Final, assert_never

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

#: GitHub's response header stating how many requests remain in the current
#: rate-limit window. This is a protocol name and cannot vary by deployment.
RATE_LIMIT_REMAINING_HEADER: Final = "x-ratelimit-remaining"

#: HTTP's response header stating that a refusal is temporary. This is a
#: protocol name and cannot vary by deployment.
RETRY_AFTER_HEADER: Final = "retry-after"

#: GitHub's literal response value for an exhausted rate-limit window.
NO_REQUESTS_REMAINING: Final = "0"

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
    #: A named refusal only a person can settle.
    MANUAL_ACTION = "manual-action"
    #: A code defect or an error no named cause classifies.
    RAISED = "raised"


class ManualActionError(ValueError):
    """A named refusal whose data or policy needs a person's decision."""


def _forbidden_is_api_unavailable(error: urllib.error.HTTPError) -> bool:
    """Whether a 403's case-insensitive headers say the API is temporarily unavailable."""
    return error.code == HTTPStatus.FORBIDDEN and (
        error.headers.get(RATE_LIMIT_REMAINING_HEADER) == NO_REQUESTS_REMAINING
        or error.headers.get(RETRY_AFTER_HEADER) is not None
    )


def classify(error: Exception) -> ErrorCause:
    """What this error means, from its type, status and closed response-header signals."""
    if isinstance(error, ManualActionError):
        return ErrorCause.MANUAL_ACTION
    if isinstance(error, urllib.error.HTTPError):
        if error.code in GONE_STATUSES:
            return ErrorCause.GONE
        if error.code in NOT_DELETABLE_STATUSES:
            return ErrorCause.NOT_DELETABLE
        if _forbidden_is_api_unavailable(error):
            return ErrorCause.API_UNAVAILABLE
        if error.code == RATE_LIMITED or SERVER_ERRORS_START <= error.code < SERVER_ERRORS_END:
            return ErrorCause.API_UNAVAILABLE
        return ErrorCause.RAISED
    if isinstance(error, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return ErrorCause.API_UNAVAILABLE
    if isinstance(error, OverBudgetError):
        return ErrorCause.RAISED if error.needed > error.budget else ErrorCause.BUDGET_SPENT
    return ErrorCause.RAISED


def fault_of(cause: ErrorCause) -> GardenerFault:
    """The fault a pass stopped by this cause records.

    A member gone or not deletable means what it says only on a delete, and a
    spent partial budget ends at the ceiling, so a stop for any of those is a
    defect.
    """
    match cause:
        case ErrorCause.API_UNAVAILABLE:
            return GardenerFault.API_UNAVAILABLE
        case ErrorCause.MANUAL_ACTION:
            return GardenerFault.MANUAL_ACTION
        case (
            ErrorCause.GONE
            | ErrorCause.NOT_DELETABLE
            | ErrorCause.BUDGET_SPENT
            | ErrorCause.RAISED
        ):
            return GardenerFault.RAISED
    assert_never(cause)
