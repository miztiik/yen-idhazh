"""Payload builders and stage harnesses more than one pipeline module needs."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    RecordedEndpoint,
    _rendered_by_the_template,
    read_text,
)
from pytest import MonkeyPatch

from idhazh import assemble, config
from idhazh.contracts.article import Article
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceKind
from idhazh.evals.score import to_eval_row
from idhazh.fetch import FetchResult
from idhazh.stages import common
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.work import stage_work

FULL_TEXT = (
    "Example Lab released a smaller model on Friday, claiming a 34 percent lower cost per "
    "million tokens and 2.1 times the throughput of the model it replaces on commodity "
    "processors. The weights are published under a permissive licence. The company did not "
    "say when the model being replaced will be retired."
)

def article() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


def summary() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


def plan() -> RunPlan:
    return RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))


def row(**overrides: object) -> EvalRow:
    item = plan().items[0]
    built = to_eval_row(
        item=item,
        article=article(),
        summary=summary(),
        full_text=FULL_TEXT,
        premise=FULL_TEXT,
        hhem=0.91,
        hhem_full=0.89,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-1;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )
    return built.model_copy(update=overrides) if overrides else built


#: The error a llama-server writes while its weights are still loading. A
#: recorded body rather than one typed here, because what the stage reads off it
#: is the server's own error shape (Guardrail #7).
REFUSED_COMPLETION: Final = FIXTURES_DIR / "completions" / "errors" / "server-unavailable.json"


@contextmanager
def a_server_that_refuses_every_completion() -> Iterator[RecordedEndpoint]:
    """A server healthy enough to start a stage, whose every completion is an error.

    A stage reads `/props` and three template renderings before its first item,
    so a closed port no longer reaches the item loop at all: it refuses at
    start-up, which is what production's health check already does. A run where
    the words never arrived is driven from the other end instead - the server
    answers every start-up proof and refuses every completion, so each item
    lands `model_refused` and the stage still writes its record.
    """
    with RecordedEndpoint(503, REFUSED_COMPLETION.read_bytes()) as server:
        yield server


class SilentCompletionEndpoint:
    """A server that proves itself at start-up and then answers no completion.

    It answers the two start-up routes exactly as llama-server does, so the
    stage reaches its first item, and writes nothing at all on the completion
    route.

    `holds` is the difference between the two ways a server goes quiet, and they
    are two different mornings for an operator. Held, the request sits on an
    open line until the caller's own clock ends it, which is `model_timed_out`
    and sends them to the output budget. Dropped, the line closes with nothing
    on it, which is `model_unreachable` and sends them to the process.
    """

    def __init__(self, *, holds: bool) -> None:
        stop = threading.Event()
        asked: list[dict[str, Any]] = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                self._answer(b'{"chat_template": "fixture-template"}')

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                payload = json.loads(raw)
                if self.path.endswith("/apply-template"):
                    self._answer(_rendered_by_the_template(payload))
                    return
                asked.append(payload)
                if holds:
                    stop.wait()
                # Nothing is written either way. A late write to a caller that
                # already gave up raises in this thread and prints a traceback
                # no test asserts on.
                self.close_connection = True

            def _answer(self, body: bytes) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return None

        self._stop = stop
        self._asked = asked
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/v1/chat/completions"

    @property
    def asked(self) -> int:
        """How many completions were posted. A start-up proof is not one of them."""
        return len(self._asked)

    def __enter__(self) -> SilentCompletionEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)

def captured_article_fetch(_url: str) -> FetchResult:
    page = read_text(FIXTURES_DIR / "pages" / "article.html")
    extra = (
        "<p>The filing also says the utility will publish quarterly milestones, "
        "including site work, equipment orders, safety reviews and expected fuel "
        "delivery dates, so residents can track whether the schedule is moving. "
        "Officials said each update will name the missed date when a milestone "
        "slides, rather than leaving the change to be inferred from a later plan.</p>"
    )
    body = page.replace("</article>", f"{extra}</article>").encode("utf-8")
    return FetchResult(FetchOutcome.OK, status=200, body=body)


def drawable_article_fetch(_url: str) -> FetchResult:
    """A captured page a bar chart can actually be drawn from.

    `article.html` states three figures in three units - dollars, megawatts and
    customers - so every bar the validator would accept from it mixes units and
    `units_convertible` refuses it. That is correct behaviour and it makes that
    page unable to answer the question the two-call stage turns on, which is
    whether the two calls still put a picture on disk. This page states four
    figures in one unit, which is the shape `tests/fixtures/visual-validator/`
    already keeps as the plan that passes.
    """
    page = read_text(FIXTURES_DIR / "pages" / "wind.html")
    return FetchResult(FetchOutcome.OK, status=200, body=page.encode("utf-8"))


def digest_item(run_n: int = 1):  # type: ignore[no-untyped-def]
    """A different story for every run, and a later run's story outscores the rest.

    The distinctness is the point, not a convenience. Four of the five daily runs
    add a story the earlier runs could not see, and it often outscores what is
    already on the page. A fixture that handed back one story cannot express
    that shape at all: `build_day` drops an item the day already carries, so a
    two-run test built on it publishes one block and the ordering stage never
    meets a second one. That is why every test in this file stayed green while
    `assemble` ordered across runs, and why `DigestDay` first refused the day in
    production on 2026-09-13 rather than here.

    Run 1 keeps the address the summary fixture declares, so a test that names
    `ai-01` still gets it. The title, the link and the score are derived from the
    run so that two runs are two stories and not one story twice.
    """
    built = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.ANNOUNCEMENT,
        run_n=run_n,
    )
    return built.model_copy(
        update={
            "item_id": f"{built.vertical}-{run_n:02d}",
            "title": f"The story run {run_n} published",
            "source_url": f"{built.source_url}/run-{run_n}",
            "rank_score": float(run_n),
        }
    )


def isolate_ledgers(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Point every output root and every committed ledger at the test's own tree.

    The month index is one of them because `stage_assemble` rebuilds it from
    whatever day directory it was given. Its root is derived from `PUBLIC_ROOT`,
    so patching that covers it. Left unpatched it rebuilt the committed index
    from an empty fixture tree and truncated the served vectors to zero bytes - a
    change `git status` shows and a test never asserts on.
    """
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")


def work_then_assemble(run_plan: RunPlan, settings: config.Settings) -> None:
    """One whole run over captured pages, with no usable model and no network.

    The summaries fail, which is the point: the record describes the pipeline
    rather than the words, so it has to reach the run record on a day no words
    arrived. The server is a real loopback one replaying recorded bytes, so
    nothing here is mocked (Guardrail #7).
    """
    with a_server_that_refuses_every_completion() as server:
        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
            model_endpoint=server.endpoint,
        )
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")


def score_one_item(items_dir: Path, run_plan: RunPlan) -> None:
    """Stand in for the scorer, which needs weights this suite does not download."""
    item = run_plan.items[0]
    scored = summary().model_copy(update={"item_id": item.item_id, "url_key": item.url_key})
    (items_dir / f"{item.item_id}.summary.json").write_text(scored.to_json(), encoding="utf-8")
    evaluated = row(url_key=item.url_key)
    (items_dir / f"{item.item_id}.eval.json").write_text(evaluated.to_json(), encoding="utf-8")


def _work_stage(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    replies: tuple[bytes, ...],
    fetcher: Callable[[str], FetchResult] = captured_article_fetch,
    run_plan: RunPlan | None = None,
    hold_s: float = 0.0,
) -> tuple[RunPlan, Path, RecordedEndpoint]:
    """One real work stage over captured pages and recorded replies.

    No network and nothing mocked: the pages come off disk and the replies are
    played back by a real loopback server (Guardrail #7). The endpoint comes back
    with it because it holds two different readings of the same run - how many
    requests were sent, and what was in them - and a test wants one or the other.

    `run_plan` is how a caller asks for a shape the committed fixture does not
    carry - an item the day's feeds never produced. Default is the fixture, so
    every existing caller reads the same plan it always did.

    `hold_s` makes the server take its time answering, which is the only way to
    drive a call that waited: the recorded bytes say what the real server spent
    and cannot say how long the caller stood there.
    """
    run_plan = run_plan if run_plan is not None else plan()
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    # The state root too, or a traced work stage writes its trace and its span
    # rollup into the committed `state/` tree and `git status` is what tells you.
    monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")
    with RecordedEndpoint(200, *replies, hold_s=hold_s) as server:
        stage_work(
            run_plan,
            settings=config.load(CONFIG_DIR),
            scorer=None,
            fetcher=fetcher,
            model_endpoint=server.endpoint,
        )
    return run_plan, tmp_path / "run" / run_plan.date / "items", server


def worked(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    replies: tuple[bytes, ...],
    fetcher: Callable[[str], FetchResult] = captured_article_fetch,
) -> tuple[RunPlan, Path, int]:
    """The run, its items on disk, and how many requests the stage sent.

    The third value is what tells two calls an item from one without reading a
    payload either could produce.
    """
    run_plan, items, server = _work_stage(
        tmp_path, monkeypatch, replies=replies, fetcher=fetcher
    )
    return run_plan, items, server.served
