"""Does every error a gardener pass meets mean what the plan says it means, built from real errors?

Each case is the error object the standard library really raises - an
`HTTPError` with GitHub's status code, a `URLError` around the reason a
connection failed, a timeout, a file the system refused - built here, with no
network (Guardrail #7). The classifier reads the type and the status code, so
an error built here is the error a pass meets.
"""

from __future__ import annotations

import email.message
import http.client
import io
import json
import urllib.error
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus

import pytest

from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.gardener import error_cause
from idhazh.gardener.error_cause import ErrorCause
from idhazh.gardener.file_listing import OverBudgetError

pytestmark = pytest.mark.contract

#: Where one of the gardener's deletes is sent.
DELETED: str = "https://api.github.com/repos/miztiik/yen-idhazh/actions/artifacts/9472586501"


@contextmanager
def an_answer(status: int) -> Iterator[urllib.error.HTTPError]:
    """GitHub's answer with this status, as `urlopen` raises it, closed once the case is done."""
    answer = urllib.error.HTTPError(
        DELETED, status, HTTPStatus(status).phrase, email.message.Message(), io.BytesIO(b"{}")
    )
    try:
        yield answer
    finally:
        answer.close()


@pytest.mark.parametrize(
    ("status", "cause"),
    [
        pytest.param(404, ErrorCause.GONE, id="404-already-gone"),
        pytest.param(410, ErrorCause.GONE, id="410-gone-for-good"),
        pytest.param(409, ErrorCause.NOT_DELETABLE, id="409-in-use"),
        pytest.param(422, ErrorCause.NOT_DELETABLE, id="422-cannot-process"),
        pytest.param(429, ErrorCause.API_UNAVAILABLE, id="429-too-many-requests"),
        pytest.param(500, ErrorCause.API_UNAVAILABLE, id="500-server-error"),
        pytest.param(502, ErrorCause.API_UNAVAILABLE, id="502-bad-gateway"),
        pytest.param(503, ErrorCause.API_UNAVAILABLE, id="503-unavailable"),
        pytest.param(504, ErrorCause.API_UNAVAILABLE, id="504-gateway-timeout"),
        pytest.param(400, ErrorCause.RAISED, id="400-bad-request"),
        pytest.param(401, ErrorCause.RAISED, id="401-no-token"),
        pytest.param(403, ErrorCause.RAISED, id="403-forbidden"),
    ],
)
def test_each_answer_github_gives_means_one_cause(status: int, cause: ErrorCause) -> None:
    """An `HTTPError` is read first, so a refusal is never mistaken for a lost connection."""
    with an_answer(status) as answer:
        assert isinstance(answer, urllib.error.URLError), "the order of the tests is the point"
        assert error_cause.classify(answer) is cause


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(urllib.error.URLError("nodename nor servname provided"), id="url-error"),
        pytest.param(urllib.error.URLError(TimeoutError("timed out")), id="url-error-timeout"),
        pytest.param(TimeoutError("The read operation timed out"), id="timeout"),
        pytest.param(ConnectionResetError(104, "Connection reset by peer"), id="reset"),
        pytest.param(ConnectionRefusedError(111, "Connection refused"), id="refused"),
        pytest.param(
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            id="remote-disconnected",
        ),
    ],
)
def test_a_connection_that_failed_or_timed_out_is_an_api_that_is_down(error: Exception) -> None:
    assert error_cause.classify(error) is ErrorCause.API_UNAVAILABLE


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(http.client.IncompleteRead(b'{"total_count"'), id="incomplete-read"),
        pytest.param(json.JSONDecodeError("Expecting value", '{"total_count"', 14), id="json"),
        pytest.param(PermissionError(13, "Permission denied"), id="permission"),
        pytest.param(FileNotFoundError(2, "No such file or directory"), id="no-such-file"),
        pytest.param(KeyError("created_at"), id="key"),
        pytest.param(ValueError("a member's day is a YYYY-MM-DD day"), id="value"),
    ],
)
def test_every_other_error_is_a_code_defect(error: Exception) -> None:
    """A cut-off body and a local file the system refused are not GitHub being down."""
    assert error_cause.classify(error) is ErrorCause.RAISED


@pytest.mark.parametrize(
    ("needed", "cause"),
    [
        pytest.param(900_000, ErrorCause.BUDGET_SPENT, id="a-wake-with-room-takes-it"),
        pytest.param(1_048_576, ErrorCause.BUDGET_SPENT, id="exactly-the-budget"),
        pytest.param(1_048_577, ErrorCause.RAISED, id="larger-than-the-whole-budget"),
    ],
)
def test_one_rule_decides_the_download_budget(needed: int, cause: ErrorCause) -> None:
    """More than the whole budget is a defect a person resolves; less waits for a wake with room."""
    spent = OverBudgetError(needed=needed, room=100_000, budget=1_048_576)

    assert error_cause.classify(spent) is cause


@pytest.mark.parametrize(
    ("cause", "fault"),
    [
        (ErrorCause.API_UNAVAILABLE, GardenerFault.API_UNAVAILABLE),
        (ErrorCause.RAISED, GardenerFault.RAISED),
        (ErrorCause.BUDGET_SPENT, GardenerFault.RAISED),
        (ErrorCause.GONE, GardenerFault.RAISED),
        (ErrorCause.NOT_DELETABLE, GardenerFault.RAISED),
    ],
    ids=lambda value: value.value,
)
def test_a_stop_records_api_unavailable_or_raised(
    cause: ErrorCause, fault: GardenerFault
) -> None:
    """A 404 on a read is a wrong request, not a member gone, so a stop for it is a defect."""
    assert error_cause.fault_of(cause) is fault
