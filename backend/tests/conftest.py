"""Repo-relative paths every backend test resolves against."""

from __future__ import annotations

import csv
import json
import threading
import time
from collections.abc import Iterable
from datetime import date as date_type
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import config, day_shards, ledger
from idhazh.classify.calls import build_label_request
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob, derive_output_digest, derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.element import ElementTable
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.extract import ElementsConfig
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import SourceTier
from idhazh.corpus import Published
from idhazh.elements import element_table
from idhazh.evals import writer as eval_writer
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult
from idhazh.llm.server import TurnMarkers, server_argv
from idhazh.stages import common, compact
from utilities.capture_request_bodies import RENDERINGS, markers_for

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
CONFIG_DIR: Final = REPO_ROOT / "config"
STATE_DIR: Final = REPO_ROOT / "state"
FIXTURES_DIR: Final = REPO_ROOT / "tests" / "fixtures"
CONTRACT_FIXTURES_DIR: Final = FIXTURES_DIR / "contracts"
#: The model file `config/idhazh.json` points at. A test that stands a recorded
#: server up serves this model's renderings, because that is the model the
#: settings it loads name.
INCUMBENT_MODEL: Final = "qwen3.5-9b-q4km.json"


def seed_item_health(state_dir: Path, date: str, rows: Iterable[ItemHealthRow]) -> int:
    """Put an item census on disk the way a finished run leaves it.

    A fixture builder and not a copy of a writer. The pipeline no longer appends
    to this head: a work shard and `assemble` each write a segment and
    `stage_compact` folds them in, so there is no longer one call a test can make
    to reach a settled day file. Every caller of this helper wants the day
    ALREADY settled - it is checking what the planner, the fold or a projection
    does with a census, not how the census got written - so this leaves the fold
    itself to `tests/pipeline/test_compact.py` and puts the finished file there.

    Settled means what the compaction means by it. A day file carrying a heading
    from an earlier build is re-filed onto the current one first, through the
    contract's own reader, and then the first row for an `ITEM_HEALTH_KEY` wins:
    a row repeating a key already in the file is dropped rather than appended.

    The file is the day's own `settled.csv`, which is the name the fold writes
    and the one name in a day directory no writer can take.

    Returns the rows the file gained, so a caller that asserted on the old
    writer's count asserts on the same number.
    """
    path = ledger.item_health_path(state_dir, date) / day_shards.SETTLED_NAME
    columns = ItemHealthRow.csv_columns()
    ledger.migrate_header(
        path, columns, ledger.refiler(ItemHealthRow), carried=ledger.ITEM_HEALTH_CARRIED
    )
    held = ledger.recorded_item_health(path)
    kept: list[dict[str, str]] = []
    for row in rows:
        cells = row.csv_row()
        key = tuple(cells[name] for name in ledger.ITEM_HEALTH_KEY)
        if key in held:
            continue
        held.add(key)
        kept.append(cells)
    if not kept:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            out.writeheader()
        out.writerows({name: cells[name] for name in columns} for cells in kept)
    return len(kept)


def seed_span_rollup(state_dir: Path, date: str, rows: Iterable[SpanRollupRow]) -> int:
    """Put a day's span fold on disk the way a finished run leaves it.

    The same fixture builder as `seed_item_health`, for the same reason: a work
    shard writes its fold to its own file in the day directory and the caller
    here wants the day ALREADY folded - it is checking what a listing, a
    projection or a prune does with the record - so the fold itself stays in
    `tests/pipeline/test_compact.py` and this puts the finished file there.

    Settled means what the compaction means by it: the first row for a
    `SPAN_ROLLUP_KEY` wins, because the row is a fold of one shard's spans and a
    second row for one key adds a count to itself rather than recording a new
    fact.

    Returns the rows the file gained, so a caller that asserted on the old
    writer's count asserts on the same number.
    """
    path = ledger.span_rollup_path(state_dir, date) / day_shards.SETTLED_NAME
    columns = SpanRollupRow.csv_columns()
    ledger.migrate_header(path, columns, ledger.refiler(SpanRollupRow))
    held = ledger.recorded_span_rollup(path)
    kept: list[dict[str, str]] = []
    for row in rows:
        cells = row.csv_row()
        key = tuple(cells[name] for name in ledger.SPAN_ROLLUP_KEY)
        if key in held:
            continue
        held.add(key)
        kept.append(cells)
    if not kept:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            out.writeheader()
        out.writerows({name: cells[name] for name in columns} for cells in kept)
    return len(kept)


def seed_feed_health(
    state_dir: Path,
    date: str,
    rows: Iterable[FeedHealthRow],
    *,
    run_id: str | None = None,
    attempt: int = 1,
    job: ServerJob = ServerJob.PLAN,
    shard: int = 0,
) -> int:
    """Put feed verdicts on disk the way the plan job leaves them.

    The real producer, not a copy of it: the plan job is the only writer of this
    tree and it writes one file of its own inside the day directory. A caller
    that needs two writers on one day calls this twice with two identities.

    `run_id` defaults to the first run of the date, which is what a caller that
    does not care about identity wants.
    """
    return ledger.write_segment(
        state_dir,
        ledger.SegmentLedger.HEALTH,
        list(rows),
        run_id=run_id if run_id is not None else f"{date}-1",
        attempt=attempt,
        job=job,
        shard=shard,
    )


def seed_scores(
    state_dir: Path,
    rows: Iterable[EvalRow],
    *,
    run_id: str,
    attempt: int = 1,
    job: ServerJob = ServerJob.ASSEMBLE,
    shard: int = 0,
) -> int:
    """Put measurements on disk the way a finished run leaves them, index and all.

    The real writer, so the index beside the rows is written too - a test that
    put rows down without one would find every measurement offered again as new.
    `run_id` has no default because the index is filed under the run's own day.
    """
    return eval_writer.append_segment(
        state_dir, rows, run_id=run_id, attempt=attempt, job=job, shard=shard
    )


def fold(state_dir: Path, date: str) -> compact.CompactionReport:
    """Fold `date` and every earlier day of every tree into one settled file each.

    A test writes a day and wants it folded in the next line. Production only
    folds a day already closed, so this names a later date rather than moving
    `after_days` to zero - a zero there would fold a day a shard could still be
    writing, which is not a shape a run can reach.
    """
    after_days = RunConfig().settled_fold_after_days
    closed = date_type.fromisoformat(date) + timedelta(days=after_days + 1)
    return compact.stage_compact(state_dir, date=closed.isoformat(), after_days=after_days)


def read_text(path: Path) -> str:
    """Read without newline translation, so a CRLF drift fails the comparison."""
    return path.read_bytes().decode("utf-8")


def a_server(**flags: Any) -> dict[str, Any]:
    """A settings block for a case whose subject is not the settings.

    It carries the one flag configuration load requires and the three the run
    record writes down, so a builder gets a block a person could have written.
    Every other flag is llama-server's own default, which is what a model file
    saying nothing about it means.
    """
    return {
        "--ctx-size": 8192,
        "--batch-size": 512,
        "--ubatch-size": 512,
        "--threads": 4,
        **flags,
    }


def a_request(**values: Any) -> dict[str, Any]:
    """The request half of the same thing, at the values a greedy decode uses."""
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 0,
        "request_timeout_minutes": 22.1,
        **values,
    }


def llama_server_flags() -> frozenset[str]:
    """Every flag a committed entry starts its server with, plus the four in code.

    Read off the entries rather than listed here, because the entries are where
    the flags live: `server_argv` emits the `server` block verbatim and spells
    four of its own. Every committed file is read, so a flag only one model sets
    is still counted.
    """
    emitted: set[str] = set()
    for path in sorted((CONFIG_DIR / "models").glob("*.json")):
        entry = ModelsConfig.from_json(read_text(path)).summarize
        emitted |= set(
            server_argv(
                binary=Path("bin/llama-server"),
                weights=Path("models/w.gguf"),
                model=entry,
                server=entry.server,
            )
        )
    # llama-bench and the image bench take these two under the same spelling,
    # so they say nothing about which server a caller started.
    return frozenset(
        token
        for token in emitted
        if token.startswith("-") and token not in {"--model", "--threads"}
    )


@pytest.fixture(autouse=True)
def isolate_committed_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test writes the repository's own state/ tree, whatever stage it runs.

    Tracing is on in the committed config (2026-09-06), so `stage_work` writes a
    span fold under `state/segments/span-rollup/` and both it and
    `stage_visual_planner` write a raw trace under `state/traces/` - committed
    paths keyed off `common.STATE_ROOT`. A stage test that only redirected
    `VAR_ROOT` would otherwise write real committed files. This points
    `STATE_ROOT` at the test's own tree; a test that sets it itself still wins,
    because its `monkeypatch` call runs after this fixture and the last write to
    an attribute is the one that holds.
    """
    monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")


@pytest.fixture
def article_ok() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


@pytest.fixture
def summary_ok() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


@pytest.fixture
def digest_day_ok() -> DigestDay:
    path = next((CONTRACT_FIXTURES_DIR / "digest-day").glob("*.json"))
    return DigestDay.from_json(read_text(path))


# --- One article a refill can rebuild, shared by two test modules ----------

REFILL_URL: Final = "https://grid.example.com/2026/08/winter-outlook"

#: A body that shares the summary's entities and numbers but no three-word run
#: with it. Both halves matter: too little overlap fails `lead_coverage_min`,
#: too much fails `verbatim_reject_ceiling`, and a number the body does not
#: carry fails `unsupported_numbers`.
REFILL_BODY: Final = (
    "The Nordic Grid Authority said its winter reserve margin will stay near 12 "
    "percent into February. Officials called the figure comfortable rather than "
    "generous, and said no rolling outages are planned. The authority has spent "
    "three years adding battery storage across the region and now counts 4 "
    "gigawatts of it. Demand has risen faster than the forecast published last "
    "spring, mostly because of new data centre connections in the south. A "
    "spokesperson said a revised outlook would appear in March and would carry a "
    "longer horizon than usual. Analysts who follow the region said the margin "
    "leaves little room if a cold snap arrives early, though none of them expect "
    "outages before the spring thaw arrives."
)

REFILL_PUBLISHED: Final = Published(
    title="Nordic grid holds its winter margin at 12 percent",
    summary=(
        "The Nordic Grid Authority expects a reserve margin near 12 percent "
        "through February and has ruled out planned outages. Battery capacity "
        "has reached 4 gigawatts. Southern data centre demand overtook the "
        "spring forecast, and a fresh outlook is due in March."
    ),
    key_points=(
        "Reserve margin stays near 12 percent into February",
        "Battery capacity reaches 4 gigawatts",
        "A revised outlook is due in March",
    ),
)


def refill_page(body: str) -> bytes:
    return f"<html><body><article><p>{body}</p></article></body></html>".encode()


def refetched(
    body: str, app: AppConfig, *, url: str = REFILL_URL, item_id: str = "energy-01"
) -> tuple[Article, str]:
    """One page through the real extractor, exactly as a refill sees it."""
    item = PlannedItem(
        item_id=item_id,
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id="grid-newsroom",
        tier=SourceTier.INSTITUTION,
        vertical="energy",
        title="Nordic grid publishes its winter outlook",
        rank_score=1.0,
    )
    return to_article_with_source(
        item,
        FetchResult(FetchOutcome.OK, status=200, body=refill_page(body)),
        config=app.extract,
        fetched_at="2026-08-28T00:00:00Z",
    )


def refill_recorded(
    article: Article, published: Published, **overrides: object
) -> EvalRow:
    """A ledger row for this pair, carrying the digest the join checks."""
    base = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    return base.model_copy(
        update={
            "item_id": article.item_id,
            "url_key": article.url_key,
            "source_url": article.canonical_url,
            "title": article.title,
            "vertical": article.vertical,
            "output_digest": derive_output_digest(
                published.summary, list(published.key_points), title=published.title
            ),
            **overrides,
        }
    )


# --- The two calls that read one article, shared by two test modules ------


def _rendered_by_the_template(body: dict[str, Any]) -> bytes:
    """What the template route answers, off the incumbent's recorded renderings.

    Every stage reads its turn markers off this route before its first item, so
    a recorded server has to answer it or nothing can render a prompt. Which
    rendering comes back is read off the request exactly as a real template
    would read it: three turns is a conversation with a reply already in it, and
    two turns answer differently once a keyword asks for reasoning.

    It draws on no recorded completion. Those bytes are replies a model wrote,
    and a template render is not one.
    """
    recorded = json.loads(RENDERINGS.read_text(encoding="utf-8"))["entries"][INCUMBENT_MODEL]
    asked_to_think = any((body.get("chat_template_kwargs") or {}).values())
    if len(body.get("messages") or []) > 2:
        rendering = "history"
    else:
        rendering = "thinking" if asked_to_think else "plain"
    return json.dumps({"prompt": recorded[rendering]}).encode("utf-8")


class RecordedEndpoint:
    """A real local server that replays recorded llama-server replies in order.

    Nothing is mocked: the caller makes its ordinary POST over a loopback
    socket, and the bytes it reads back are the ones a llama-server wrote
    (Guardrail #7). The stdlib server owns the framing, so the test is about the
    body and not about HTTP.

    More than one body replays them in a cycle, which is what lets a caller that
    makes a fixed number of calls per item be driven over several items: two
    bodies answer the label call and the summarize-and-plan call, then the label call again. `served` is the POST
    count, so a test can assert the pair rather than infer it from what came
    back - and an item that sent one call where the cycle expects two shows up
    there rather than as a reply that will not parse three items later.

    `sent` is every request body, in the order they arrived. A cycle of replies
    cannot tell a caller that ran the label call three times from one that alternated,
    because both read the same bytes back; the requests can, which is what makes
    the item-major rule assertable rather than readable.

    `hold_s` makes the server take its time before answering a POST. It is the
    only way to drive a call that waited without a network: the recorded bytes
    carry whatever the real server said it spent, and nothing in them can say
    how long the caller stood there.
    """

    def __init__(self, status: int, *bodies: bytes, hold_s: float = 0.0) -> None:
        if not bodies:
            raise ValueError("a recorded endpoint replays at least one body")
        served: list[int] = []
        sent: list[dict[str, Any]] = []
        replies = bodies

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                # `/props`, which every stage reads before its first item. A
                # fixed template keeps the pipeline stamp the same across two
                # runs of one test, so a stamp that moved moved for a reason.
                template = b'{"chat_template": "fixture-template"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(template)))
                self.end_headers()
                self.wfile.write(template)

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                payload = json.loads(raw)
                if self.path.endswith("/apply-template"):
                    self._answer(200, _rendered_by_the_template(payload))
                    return
                sent.append(payload)
                body = replies[len(served) % len(replies)]
                served.append(1)
                if hold_s > 0:
                    time.sleep(hold_s)
                self._answer(status, body)

            def _answer(self, code: int, body: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return None

        self._served = served
        self._sent = sent
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def served(self) -> int:
        return len(self._served)

    @property
    def sent(self) -> list[dict[str, Any]]:
        """Every request body this endpoint was posted, in arrival order."""
        return list(self._sent)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}/v1/chat/completions"

    @property
    def base_url(self) -> str:
        """The origin, in the shape `model_server.base_url` takes.

        The port is whichever one the operating system handed out this second,
        so a test that writes this into a config proves the address reached the
        wire from there - no constant in the tree could name it.
        """
        return f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> RecordedEndpoint:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


LABEL_REPLIES = FIXTURES_DIR / "completions" / "label"
SUMMARIZE_AND_PLAN_REPLIES = FIXTURES_DIR / "completions" / "summarize-and-plan"


def a_table(article: Article, text: str | None = None, *, cap: int = 256) -> ElementTable:
    """The candidate pass over an article's own text, or over `text` in its place.

    A prompt is built from an article and a table together and refuses a pair
    that disagree, so a case that renders one passes the article whose text the
    table indexes.
    """
    if text is not None:
        article = article.model_copy(update={"text": text})
    return element_table(article, config=ElementsConfig(max_per_article=cap))


def committed_markers(model_file: str = INCUMBENT_MODEL) -> TurnMarkers:
    """The markers one committed model's own template writes.

    A server derives these at start-up and a test has no server, so the recorded
    renderings under `tests/fixtures/llm/` stand in for one and the production
    parser reads them exactly as it reads a live reply.
    """
    return markers_for(model_file)


def label_payload(article: Article) -> dict[str, Any]:
    entry = config.load(CONFIG_DIR).models.summarize
    return build_label_request(
        article,
        a_table(article),
        model_id="m",
        server=entry.server,
        request=entry.request,
        markers=committed_markers(),
    )
