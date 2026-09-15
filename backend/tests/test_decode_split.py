"""How is the summarize-and-plan call's decode divided between the summary and the picture?

`summary_ms` is the whole call and always was. What was missing is the picture's
share of it, which is the number that says whether a 5x model-time regression
happened in the half a reader came for or in the half that draws a chart.

The property every test here rests on is arithmetic rather than judgement: the
two halves sum to exactly what the server reported, in tokens and in
milliseconds, on every reply. An apportionment that loses a token is an
apportionment nobody can reconcile against the ledger.
"""

from __future__ import annotations

import json

from idhazh.classify import calls
from idhazh.llm.server import Completion


def reply(
    summary_chars: int, plan_chars: int, *, completion_tokens: int, decode_ms: int
) -> Completion:
    """One reply of a known shape, with the two halves sized to order.

    Built rather than recorded, because what is under test is a ratio and a
    recorded reply pins one ratio. The field order is the grammar's - `summary`
    first - which is the whole reason the split is possible.
    """
    body = {
        "summary": {"title": "t", "summary": "s" * max(summary_chars, 1)},
        "visual": {"decision": "visual", "why": "w" * max(plan_chars, 1)},
    }
    return Completion(
        content=json.dumps(body, separators=(",", ":")),
        completion_tokens=completion_tokens,
        decode_ms=decode_ms,
    )


def test_the_two_halves_sum_to_exactly_what_the_server_reported() -> None:
    """The oracle. A token that goes missing here is a token nobody can reconcile."""
    whole = reply(4000, 1000, completion_tokens=1158, decode_ms=378011)

    split = calls.split_the_decode(whole)

    assert split is not None
    assert split.summary_tokens + split.plan_tokens == 1158
    assert split.summary_ms + split.plan_ms == 378011


def test_a_bigger_picture_half_takes_a_bigger_share() -> None:
    """The share is the plan's characters over the whole reply's, and it moves."""
    small = calls.split_the_decode(reply(4000, 200, completion_tokens=1000, decode_ms=100000))
    large = calls.split_the_decode(reply(4000, 4000, completion_tokens=1000, decode_ms=100000))

    assert small is not None
    assert large is not None
    assert large.plan_tokens > small.plan_tokens
    assert large.plan_ms > small.plan_ms


def test_the_milliseconds_follow_the_tokens_rather_than_being_rounded_twice() -> None:
    """Two roundings of one ratio disagree, and then two columns disagree."""
    whole = reply(3000, 1000, completion_tokens=800, decode_ms=240000)

    split = calls.split_the_decode(whole)

    assert split is not None
    assert split.plan_ms == round(240000 * split.plan_tokens / 800)


def test_the_split_says_it_is_an_estimate_on_every_reply() -> None:
    """A column filled only when a number is doubtful reads as clean data elsewhere."""
    split = calls.split_the_decode(reply(4000, 1000, completion_tokens=1158, decode_ms=378011))

    assert split is not None
    assert split.is_estimate is True


def test_a_suppressed_reply_has_no_boundary_and_reports_none() -> None:
    """The reachability gate narrows the grammar to the summary alone."""
    suppressed = Completion(
        content=json.dumps({"title": "t", "summary": "s"}),
        completion_tokens=200,
        decode_ms=60000,
    )

    assert calls.split_the_decode(suppressed) is None


def test_a_decode_the_server_reported_as_nothing_reports_none() -> None:
    """Zero tokens is not a ratio, and dividing by it is how a stage dies."""
    empty = reply(4000, 1000, completion_tokens=0, decode_ms=0)

    assert calls.split_the_decode(empty) is None


def test_a_cut_reply_that_never_closed_its_plan_still_splits() -> None:
    """The summary closes before the plan starts, so the boundary survives the cut.

    This is the same guarantee `recovered_completion` spends, read for a
    different purpose: the bytes after the closed summary object are the plan's,
    whether or not the plan ever finished.
    """
    cut = Completion(
        content='{"summary":{"title":"t","summary":"sssss"},"visual":{"decision":"vis',
        completion_tokens=100,
        decode_ms=30000,
        finish_reason="length",
    )

    split = calls.split_the_decode(cut)

    assert split is not None
    assert split.plan_tokens > 0
    assert split.summary_tokens + split.plan_tokens == 100
