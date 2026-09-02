"""The span guard: a whole run traced, and not one character of the source in it.

This is the acceptance test for the tracing row, and it is written as an
end-to-end sweep rather than as a unit test of the attribute validator, because
the validator is the SECOND control and asserting only on it would pass a build
where a new call site read `article.text` into a key the validator happens to
accept.

The oracle: run the real work stage over pages that carry a planted sentinel,
capture every attribute of every span and generation the instrumentation would
send, and assert the sentinel appears in none of them. A single leaked character
is a contract break; the rule it guards is in `docs/concepts/telemetry.md`.

Two sentinels, because one of them alone would be a weaker test:

- A SENTENCE, which is what prose looks like and what the shape rule refuses.
- A lowercase, unspaced TOKEN, which the shape rule would happily accept. It is
  there so the test measures the structural control - that no code path reads
  article text into an attribute - and not the regex.

The same sweep runs over all five committed injection canaries in
`backend/tests/test_canaries.py`, which owns those fixtures.

No mocks and no network (Rule #7): the fetcher reads a page this file builds,
and the model is a loopback HTTP server replying with a committed completion.
"""

from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from pytest import MonkeyPatch

from idhazh import cli, config, telemetry
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import RunPlan
from idhazh.fetch import FetchResult

#: What prose looks like. The shape rule refuses it on the space alone.
SENTINEL_SENTENCE: Final = "Kumquat lanternfish barometer, nine four two seven."

#: What prose does not look like. Lowercase, unspaced and inside the character
#: cap, so the shape rule would accept it - which is the point. If this one ever
#: appears, a call site read the article and the regex was never the control.
SENTINEL_TOKEN: Final = "kumquat-lanternfish-barometer-9427"

SENTINELS: Final = (SENTINEL_SENTENCE, SENTINEL_TOKEN)

#: The words a summary the model "wrote" carries. Planted in the reply as well
#: as in the source, because a summary is text the pipeline holds too, and
#: `summary_attributes` is one line away from being able to send it.
SENTINEL_REPLY: Final = "Kumquat lanternfish barometer figures were restated, nine four two seven."


def page_carrying(sentinel: str, *, title: str) -> bytes:
    """A real article page with the sentinel planted in the body and the title.

    Long enough that the extractor keeps it: a page the extractor refuses never
    reaches a summarize span, and a guard that only ever sees a refused item
    proves nothing about the spans that matter.
    """
    filler = (
        "The utility told the commission it would publish quarterly milestones, "
        "naming site work, equipment orders, safety reviews and expected fuel "
        "delivery dates, so residents can follow whether the schedule is moving. "
        "Officials said each update will name the missed date when a milestone "
        "slides, rather than leaving the change to be inferred from a later plan. "
    )
    blocks = [sentinel, filler * 4, sentinel, filler * 4, sentinel]
    body = "".join(f"<p>{html.escape(block)}</p>" for block in blocks)
    return (
        f"<!DOCTYPE html><html><head><title>{html.escape(title)}</title></head>"
        f"<body><article><h1>{html.escape(title)}</h1>{body}</article></body></html>"
    ).encode()


def completion_carrying(sentinel: str) -> bytes:
    """The committed OK completion, with the sentinel written into every field.

    Built from `tests/fixtures/completions/ok.json` rather than typed out here,
    so the reply keeps the shape the decoder is actually constrained to and the
    summarize path runs to the end instead of failing early on a bad draft.
    """
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR.parent / "completions" / "ok.json")
    )
    content: dict[str, Any] = json.loads(payload["choices"][0]["message"]["content"])
    content["title"] = "Kumquat lanternfish barometer figures restated by the regulator"
    content["summary"] = f"{sentinel} {content['summary']}"
    content["key_points"] = [f"{sentinel}", *content["key_points"]]
    payload["choices"][0]["message"]["content"] = json.dumps(content)
    return json.dumps(payload).encode("utf-8")


class RecordedCompletionEndpoint:
    """A real loopback server that answers `/props` and replies with one completion.

    A local socket rather than a patched function, because the thing under test
    is what the pipeline SENDS, and a patched `post` would let a leak hide in the
    code the patch replaced.
    """

    def __init__(self, body: bytes) -> None:
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _reply(self, payload: bytes) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:
                self._reply(b'{"chat_template": "fixture-template"}')

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self._reply(body)

            def log_message(self, *_args: Any) -> None:
                return None

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/v1/chat/completions"

    def __enter__(self) -> RecordedCompletionEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


def traced_settings() -> config.Settings:
    """The committed config with tracing switched on, and nothing else moved."""
    settings = config.load(CONFIG_DIR)
    return config.Settings(
        app=settings.app.model_copy(
            update={
                "observability": settings.app.observability.model_copy(
                    update={"tracing_enabled": True}
                )
            }
        ),
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )


def spans_of(trace_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(trace_dir.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def trace_a_run(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    page: bytes,
    reply: bytes,
) -> list[dict[str, Any]]:
    """One real work stage over one planted page, and every span it produced."""
    run_plan = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "TRACE_ROOT", tmp_path / "traces")
    monkeypatch.setattr(cli, "EVIDENCE_ROOT", tmp_path / "evidence")

    with RecordedCompletionEndpoint(reply) as server:
        cli.stage_work(
            run_plan,
            settings=traced_settings(),
            scorer=None,
            fetcher=lambda _url: FetchResult(FetchOutcome.OK, status=200, body=page),
            model_endpoint=server.endpoint,
        )
    return spans_of(tmp_path / "traces")


def assert_nothing_leaked(spans: list[dict[str, Any]], planted: tuple[str, ...]) -> None:
    """The oracle. Every attribute of every span, against every planted string."""
    assert spans, "the sweep captured no spans, so it asserted nothing"
    for span in spans:
        attributes = span["attributes"]
        rendered = json.dumps(span, sort_keys=True)
        for sentinel in planted:
            assert sentinel not in rendered, (
                f"{span['name']} carried the planted text in {sorted(attributes)}"
            )
        for key, value in attributes.items():
            if isinstance(value, str):
                assert len(value) <= telemetry.MAX_ATTRIBUTE_CHARS, (
                    f"{span['name']}.{key} is {len(value)} characters"
                )


# --- The oracle -------------------------------------------------------------


def test_a_traced_run_sends_no_word_of_the_article_or_the_summary(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The row's acceptance test: a whole run, every span, not one planted character.

    Both sentinels are planted in the same run, in the page and in the reply, so
    a leak from the source side and a leak from the model side are the same
    failure of the same assertion.
    """
    spans = trace_a_run(
        tmp_path,
        monkeypatch,
        page=page_carrying(SENTINEL_SENTENCE, title=SENTINEL_TOKEN),
        reply=completion_carrying(SENTINEL_REPLY),
    )
    assert_nothing_leaked(spans, (*SENTINELS, SENTINEL_REPLY))


def test_the_sweep_reaches_every_span_the_pipeline_opens(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The counter-oracle: an absence check over an empty tree passes trivially.

    So this asserts the run really produced the nested tree - the sub-spans
    included, since those are the ones a flat ledger column cannot hold and the
    ones the guard would otherwise never have looked at.
    """
    spans = trace_a_run(
        tmp_path,
        monkeypatch,
        page=page_carrying(SENTINEL_SENTENCE, title=SENTINEL_TOKEN),
        reply=completion_carrying(SENTINEL_REPLY),
    )
    seen = {span["name"] for span in spans}
    assert {
        telemetry.SpanName.ITEM.value,
        telemetry.SpanName.FETCH.value,
        telemetry.SpanName.EXTRACT.value,
        telemetry.SpanName.TAG.value,
        telemetry.SpanName.SUMMARIZE.value,
        telemetry.SpanName.RENDER_PROMPT.value,
        telemetry.SpanName.MODEL_CALL.value,
        telemetry.SpanName.PARSE_REPLY.value,
    } <= seen
    generations = [span for span in spans if span["kind"] == telemetry.SpanKind.GENERATION.value]
    assert generations, "the model call must be a generation, not a plain span"
    carried = set(generations[0]["attributes"])
    assert {"model_id", "input_tokens", "output_tokens", "prefill_ms", "decode_ms"} <= carried


def test_a_sub_span_names_its_parent(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """The nesting is the row. A flat list of spans is the ledger with more steps.

    `tag` inside `extract`, and `model_call` inside `item`, are the two the
    committed columns cannot express: `extract_ms` covers the tagger, and no
    column says the model call happened inside the item at all.
    """
    spans = trace_a_run(
        tmp_path,
        monkeypatch,
        page=page_carrying(SENTINEL_SENTENCE, title=SENTINEL_TOKEN),
        reply=completion_carrying(SENTINEL_REPLY),
    )
    by_id = {span["span_id"]: span for span in spans}
    tags = [span for span in spans if span["name"] == telemetry.SpanName.TAG.value]
    assert tags, "the tagger sub-span never opened"
    for tag_span in tags:
        parent = by_id[tag_span["parent_id"]]
        assert parent["name"] == telemetry.SpanName.EXTRACT.value
        assert by_id[parent["parent_id"]]["name"] == telemetry.SpanName.ITEM.value
        assert parent["trace_id"] == tag_span["trace_id"]


def test_tracing_off_writes_nothing_at_all(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """The committed default. The same run, the same code path, no file."""
    run_plan = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "TRACE_ROOT", tmp_path / "traces")
    monkeypatch.setattr(cli, "EVIDENCE_ROOT", tmp_path / "evidence")
    settings = config.load(CONFIG_DIR)
    assert not settings.app.observability.tracing_enabled

    with RecordedCompletionEndpoint(completion_carrying(SENTINEL_REPLY)) as server:
        cli.stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=lambda _url: FetchResult(
                FetchOutcome.OK,
                status=200,
                body=page_carrying(SENTINEL_SENTENCE, title=SENTINEL_TOKEN),
            ),
            model_endpoint=server.endpoint,
        )

    assert not (tmp_path / "traces").exists()


# --- The second control -----------------------------------------------------


def test_there_is_no_free_text_key_to_put_a_prompt_in() -> None:
    """The structural half: the SDK's own text fields have no name here.

    Langfuse fills `input` and `output` with the prompt and the completion by
    default, and this repository is public. So the vocabulary is closed and
    neither name is in it, along with the three source fields a call site could
    reach for.
    """
    names = {key.value for key in telemetry.AttrKey}
    assert not names & {"input", "output", "prompt", "completion", "text", "title", "url", "detail"}


def test_an_attribute_that_looks_like_prose_is_refused() -> None:
    """The backstop, asserted from both sides so it cannot pass by refusing everything."""
    for refused in (
        SENTINEL_SENTENCE,
        "Example Lab publishes a smaller model",
        "a" * (telemetry.MAX_ATTRIBUTE_CHARS + 1),
        "https://example.test/a",
    ):
        try:
            telemetry.attribute(telemetry.AttrKey.SOURCE_DIGEST, refused)
        except ValueError:
            continue
        raise AssertionError(f"{refused!r} was accepted as a span attribute")

    for allowed in ("0" * 64, "model_unreachable", "ai-01", "2026-08-30-1", "qwen3-8b-q4-k-m"):
        assert telemetry.attribute(telemetry.AttrKey.MODEL_ID, allowed) == allowed
    assert telemetry.attribute(telemetry.AttrKey.INPUT_TOKENS, 1796) == 1796
    assert telemetry.attribute(telemetry.AttrKey.TRUNCATED, True) is True


def test_a_span_records_nothing_for_a_value_nobody_measured() -> None:
    """An empty cell reads as unknown; a zero reads as measured. The ledgers' rule."""
    span = telemetry.OpenSpan("fetch-001")
    span.set(telemetry.AttrKey.HTTP_STATUS, None)
    span.set(telemetry.AttrKey.HTTP_STATUS, 200)
    span.set(telemetry.AttrKey.BODY_BYTES, 0)
    assert dict(span.attributes()) == {"http_status": 200, "body_bytes": 0}


def test_a_named_host_with_no_package_falls_back_to_the_file(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A publish job may not fail on an observability dependency (section 1a).

    `langfuse` is an optional extra, so this is the state CI is always in: the
    variables could be set and the package is not installed. The run keeps its
    file sink and says so in the log.
    """
    monkeypatch.setattr(cli, "TRACE_ROOT", tmp_path / "traces")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-fixture")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-fixture")

    sink = cli.trace_sink(traced_settings(), date="2026-08-30", run_id="2026-08-30-1", shard=0)

    assert isinstance(sink, telemetry.FileSink | telemetry.FanOut)


def test_a_host_is_never_reached_unless_all_three_variables_are_set(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Owner decision, 2026-08-30: a file by default, a host only when named.

    Asserted one variable at a time, because a check written as `if host` would
    pass this with the keys missing and then fail inside the client.
    """
    monkeypatch.setattr(cli, "TRACE_ROOT", tmp_path / "traces")
    for named in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        for variable in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
            monkeypatch.delenv(variable, raising=False)
        monkeypatch.setenv(named, "set")
        sink = cli.trace_sink(traced_settings(), date="2026-08-30", run_id="2026-08-30-1", shard=0)
        assert isinstance(sink, telemetry.FileSink)


class Collect:
    """A sink that keeps what it was given, for the cases that need no file."""

    def __init__(self) -> None:
        self.written: list[telemetry.Span] = []

    def emit(self, span: telemetry.Span) -> None:
        self.written.append(span)

    def flush(self) -> None:
        return None


def test_the_robots_read_is_a_span_inside_the_fetch() -> None:
    """The sub-step that is the whole argument for spans over another column.

    `fetch_ms` is one number covering the robots read and the article read, so
    the first item from a host with a slow robots.txt reads as a slow article
    and the nineteen after it read as fast ones for no stated reason. Nothing
    short of a nested span can say that, and no ledger column should try.

    The address is a loopback one, which `fetch.address_is_dialable` refuses
    before any socket is opened - so this runs the real fetcher with no network
    (Rule #7).
    """
    sink = Collect()
    tracer = telemetry.Tracer(sink=sink, now=lambda: "2026-08-30T06:00:00Z")
    read = cli.live_fetcher(config.load(CONFIG_DIR), tracer=tracer)

    with tracer.trace("2026-08-30-1-ai-01"), tracer.span(telemetry.SpanName.FETCH) as outer:
        result = read("http://127.0.0.1:9/article")
        outer.set(telemetry.AttrKey.OUTCOME, result.outcome.value)

    names = [span.name for span in sink.written]
    assert names == [telemetry.SpanName.ROBOTS, telemetry.SpanName.FETCH]
    robots, fetch_span = sink.written
    assert robots.parent_id == fetch_span.span_id
    assert robots.attributes["robots_cached"] is False
    assert robots.attributes["robots_known"] is False

    with tracer.trace("2026-08-30-1-ai-02"), tracer.span(telemetry.SpanName.FETCH):
        read("http://127.0.0.1:9/another")
    assert sink.written[-2].attributes["robots_cached"] is True


def test_a_span_id_is_unique_across_the_two_passes_of_one_item() -> None:
    """The work stage opens one item's tree twice, in two loops over the shard.

    A counter that restarted per trace would give two different spans the same
    id inside one trace, and a viewer would draw one of them as the other's
    parent.
    """
    sink = Collect()
    tracer = telemetry.Tracer(sink=sink, now=lambda: "2026-08-30T06:00:00Z")
    for _pass in (1, 2):
        with tracer.trace("2026-08-30-1-ai-01"), tracer.span(telemetry.SpanName.ITEM):
            pass

    assert len({span.span_id for span in sink.written}) == 2
    assert {span.trace_id for span in sink.written} == {"2026-08-30-1-ai-01"}
