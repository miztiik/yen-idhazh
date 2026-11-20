"""Does the client turn the service's answer into mentions, and fail without costing the item?

Every case drives a real loopback server the test owns (`support.analysis_service`) and
reads the client's own answer. Nothing reaches a real service and nothing is patched.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from pathlib import Path

import pytest
from support.analysis_service import RecordedAnalysis, closed_base_url, entities_reply
from support.paths import REPO_ROOT, read_text

from idhazh.anchor_mentions import Mention
from idhazh.ask_text_analysis import ANALYZE_PATH, Outcome, ask_for_mentions
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.text_analysis import TextAnalysisConfig

#: How long a held request is waited on, so the hung-service case ends in a fraction of a second.
SHORT_WAIT_S = 0.3


def logged_answer(caplog: pytest.LogCaptureFixture, level: int) -> dict[str, object]:
    (record,) = (record for record in caplog.records if record.name == "idhazh")
    assert record.levelno == level
    payload = json.loads(record.getMessage().removeprefix("text analysis result "))
    assert isinstance(payload, dict)
    return payload


def test_one_post_carries_the_whole_text_and_the_mentions_come_back_with_three_fields(
    article_ok: Article, caplog: pytest.LogCaptureFixture
) -> None:
    """The request is the service's own, and every label comes back for `label_kinds` to map."""
    text = article_ok.text or ""
    lab = text.index("Example Lab")
    two = text.index("two")
    spans = [("ORG", lab, lab + 11), ("CARDINAL", two, two + 3)]
    caplog.set_level(logging.INFO, logger="idhazh")

    with RecordedAnalysis(lambda _text: spans) as service:
        config = TextAnalysisConfig(base_url=service.base_url, language="zh")
        answer = ask_for_mentions(article_ok, config)

    assert service.sent == [{"text": text, "language": "zh", "features": ["entities"]}]
    assert service.paths == [ANALYZE_PATH]
    assert service.content_types == ["application/json"]
    assert answer.outcome is Outcome.OK and answer.http_status is None
    assert answer.mentions == (Mention("ORG", lab, lab + 11), Mention("CARDINAL", two, two + 3))
    assert logged_answer(caplog, logging.INFO) == {
        "item_id": article_ok.item_id,
        "url_key": article_ok.url_key,
        "outcome": "ok",
        "http_status": None,
        "elapsed_ms": answer.elapsed_ms,
        "dropped_mentions": 0,
        "returned_spans": [
            {"label": "ORG", "start_char": lab, "end_char": lab + 11, "status": "accepted"},
            {"label": "CARDINAL", "start_char": two, "end_char": two + 3, "status": "accepted"},
        ],
    }


@pytest.mark.parametrize(
    ("spoiled", "status"),
    [
        ({"text": "Other Lab"}, "text_mismatch"),
        ({"start_char": 5_000, "end_char": 5_011}, "invalid_offsets"),
        ({"start_char": -11, "end_char": 0}, "invalid_offsets"),
        ({"start_char": 11, "end_char": 0}, "invalid_offsets"),
    ],
    ids=["other words", "past the end", "negative", "reversed"],
)
def test_a_mention_that_does_not_cut_the_words_it_names_is_dropped_and_its_siblings_stand(
    article_ok: Article,
    spoiled: dict[str, object],
    status: str,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Offsets are believed only when they cut out of `Article.text` the words returned."""
    text = article_ok.text or ""
    reply = json.loads(entities_reply(text, [("ORG", 0, 11)]))
    mentions = reply["features"][0]["data"]["mentions"]
    mentions.append(mentions[0] | spoiled)
    caplog.set_level(logging.WARNING, logger="idhazh")

    with RecordedAnalysis(body=json.dumps(reply).encode()) as service:
        answer = ask_for_mentions(
            article_ok, TextAnalysisConfig(base_url=service.base_url), capture_root=tmp_path
        )

    assert answer.outcome is Outcome.OK
    assert answer.mentions == (Mention("ORG", 0, 11),)
    payload = logged_answer(caplog, logging.WARNING)
    assert payload["item_id"] == article_ok.item_id and payload["dropped_mentions"] == 1
    assert payload["returned_spans"] == [
        {"label": "ORG", "start_char": 0, "end_char": 11, "status": "accepted"},
        {
            "label": "ORG",
            "start_char": mentions[1]["start_char"],
            "end_char": mentions[1]["end_char"],
            "status": status,
        },
    ]
    assert (tmp_path / f"{article_ok.item_id}.text-analysis.log").read_text(
        encoding="utf-8"
    ).splitlines() == caplog.messages


def a_failing_service(kind: str, text: str) -> RecordedAnalysis:
    """One way the service can fail, as a loopback port the test owns."""
    failed = json.loads(entities_reply(text, [("ORG", 0, 11)]))
    failed["features"][0].update(status="failed", data=None)
    bodies = {
        "not json": b"<html>not the service</html>",
        "no feature": json.dumps({"features": []}).encode(),
        "failed feature": json.dumps(failed).encode(),
    }
    if kind == "hung":
        return RecordedAnalysis(hold=True)
    if kind == "dropped":
        return RecordedAnalysis(drop=True)
    if kind == "refused":
        return RecordedAnalysis(status=429, body=b'{"error": {"code": "BUSY"}}')
    return RecordedAnalysis(body=bodies[kind])


@pytest.mark.parametrize(
    ("service", "outcome", "status"),
    [
        ("hung", Outcome.TIMED_OUT, None),
        ("dropped", Outcome.UNREACHABLE, None),
        ("refused", Outcome.REFUSED, 429),
        ("not json", Outcome.MALFORMED, None),
        ("no feature", Outcome.MALFORMED, None),
        ("failed feature", Outcome.MALFORMED, None),
    ],
)
def test_a_service_that_cannot_answer_costs_the_item_its_names_and_one_warning(
    article_ok: Article,
    caplog: pytest.LogCaptureFixture,
    service: str,
    outcome: Outcome,
    status: int | None,
) -> None:
    """Each way the service can fail returns no mentions, names why, and carries no text."""
    text = article_ok.text or ""
    caplog.set_level(logging.WARNING, logger="idhazh")

    with a_failing_service(service, text) as running:
        config = TextAnalysisConfig(
            base_url=running.base_url, request_timeout_seconds=SHORT_WAIT_S
        )
        answer = ask_for_mentions(article_ok, config)

    assert answer.mentions == () and answer.outcome is outcome and answer.http_status == status
    if outcome is Outcome.TIMED_OUT:
        assert answer.elapsed_ms >= int(SHORT_WAIT_S * 1000) - 50
    assert logged_answer(caplog, logging.WARNING) == {
        "item_id": article_ok.item_id,
        "url_key": article_ok.url_key,
        "outcome": outcome.value,
        "http_status": status,
        "elapsed_ms": answer.elapsed_ms,
        "dropped_mentions": 0,
        "returned_spans": [],
    }


def test_a_closed_port_is_unreachable_and_asks_nothing_of_the_item(article_ok: Article) -> None:
    answer = ask_for_mentions(article_ok, TextAnalysisConfig(base_url=closed_base_url()))

    assert answer.mentions == ()
    assert answer.outcome is Outcome.UNREACHABLE


def test_the_text_goes_to_the_committed_address_and_never_to_a_proxy_the_environment_names(
    article_ok: Article, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`http_proxy` moves a destination with nobody reading a diff, so the request ignores it.

    `urlopen` builds one opener the first time any code in the process uses it and keeps
    it, so the test clears that one: a client that fell back to `urlopen` would otherwise
    pass here whenever an earlier test had already used it.
    """
    monkeypatch.setattr(urllib.request, "_opener", None, raising=False)
    with RecordedAnalysis() as proxy, RecordedAnalysis() as service:
        for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
            monkeypatch.setenv(name, proxy.base_url)
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.delenv("NO_PROXY", raising=False)
        answer = ask_for_mentions(article_ok, TextAnalysisConfig(base_url=service.base_url))

    assert answer.outcome is Outcome.OK
    assert len(service.sent) == 1
    assert proxy.sent == []


def test_a_redirect_is_refused_and_the_address_it_names_is_never_sent_the_text(
    article_ok: Article,
) -> None:
    """307 is the status a client re-sends its body on, so it is the one that could leak."""
    with RecordedAnalysis() as target:
        with RecordedAnalysis(location=target.base_url + ANALYZE_PATH) as service:
            answer = ask_for_mentions(article_ok, TextAnalysisConfig(base_url=service.base_url))

    assert len(service.sent) == 1
    assert answer.mentions == () and answer.outcome is Outcome.REFUSED
    assert answer.http_status == 307
    assert target.sent == []


def test_the_client_asks_for_the_route_the_service_declares() -> None:
    """The route is a hand copy of the service's dated family, held in step here."""
    declared = read_text(
        REPO_ROOT / "services" / "text_analysis" / "spacy" / "src" / "text_analysis"
        / "declare_api_contracts.py"
    )
    family = re.search(r'^API_PREFIX = "([^"]+)"$', declared, re.MULTILINE)
    operation = re.search(
        r'^ANALYZE_TEXT_PATH = f"\{API_PREFIX\}(/[^"]+)"$', declared, re.MULTILINE
    )

    assert family is not None and operation is not None
    assert ANALYZE_PATH == family.group(1) + operation.group(1)
