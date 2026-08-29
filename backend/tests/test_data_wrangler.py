"""The operator's six verbs, run against a real corpus in a temp directory.

No mocks and no network (Rule #7). `refill` and `verify --tokens` are the two
paths that reach the network: `refill` takes its fetcher as an argument, so a
test drives it with real captured bytes, and the test for `verify --tokens` is
that it cannot run without the flag.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    REFILL_BODY,
    REFILL_PUBLISHED,
    read_text,
    refetched,
    refill_page,
    refill_recorded,
)

from idhazh import config, corpus
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.corpus import Published
from idhazh.evals import writer
from idhazh.fetch import FetchResult
from utilities import data_wrangler


def row_at(date: str, key: str, vertical: str = "ai", words: int = 8) -> CorpusRow:
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content="system"),
            ChatTurn(role=ChatRole.USER, content=" ".join(["word"] * words)),
            ChatTurn(role=ChatRole.ASSISTANT, content='{"title": "t", "summary": "s"}'),
        ],
        url_key=key * 64,
        date=date,
        model_id="qwen3-5-9b-q4-k-m",
        vertical=vertical,
    )


@pytest.fixture
def window(tmp_path: Path) -> Path:
    """Six rows over three days, two verticals."""
    rows = [
        row_at("2026-08-01", "a"),
        row_at("2026-08-01", "b", vertical="energy"),
        row_at("2026-08-02", "c"),
        row_at("2026-08-02", "d", vertical="energy", words=40),
        row_at("2026-08-03", "e"),
        row_at("2026-08-03", "f"),
    ]
    meta = corpus.census(
        rows, previous=CorpusMeta(version=CorpusMeta.schema_version()), prompt_digest="0" * 64
    )
    corpus.write(tmp_path, rows, meta)
    return tmp_path


def run(window: Path, *argv: str) -> int:
    return data_wrangler.main(["--corpus-dir", str(window), *argv])


@pytest.fixture
def roomy(tmp_path: Path) -> Path:
    """A window with room above `finetune.min_rows`.

    The floor refusal fires whether or not `--yes` was passed, which is correct
    and which also means a six-row window can never reach the dry-run path. So
    the two behaviours are tested on two windows, at the real configured numbers.
    """
    floor = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).finetune.min_rows
    rows = [
        row_at("2026-08-01", "a").model_copy(update={"url_key": f"{n:064x}"})
        for n in range(floor + 5)
    ]
    corpus.write(tmp_path, rows, corpus.read_meta(tmp_path))
    return tmp_path


# --- stats -----------------------------------------------------------------


def test_stats_says_how_many_rows_a_session_would_actually_draw(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`train_rows` is a ceiling, and a session that quietly drew fewer is unattributable."""
    assert run(window, "stats") == 0
    printed = capsys.readouterr().out

    assert "rows                       6 of a 2000-row window" in printed
    assert "2026-08-01 to 2026-08-03" in printed
    assert "a session would draw" in printed
    assert "vertical ai" in printed
    assert "vertical energy" in printed


def test_stats_warns_when_the_prompt_moved_under_the_window(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second way a training session is wasted, and the one nothing else catches."""
    assert run(window, "stats") == 0

    assert "the prompt has moved since this window was harvested" in capsys.readouterr().out


def test_stats_says_when_the_window_is_under_the_floor(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(window, "stats") == 0

    assert "below finetune.min_rows (500)" in capsys.readouterr().out


# --- split -----------------------------------------------------------------


def test_split_holds_out_the_trailing_days_and_writes_only_hashes(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """By date, never at random.

    Production always runs on tomorrow's news. A random split puts the same story
    from three feeds on both sides of the line and reports memorisation as
    success. Only `url_key` values are written, so no article text leaves.
    """
    assert run(window, "split", "--holdout-days", "1") == 0
    held = corpus.read_holdout(window)
    rows = corpus.read_rows(window)

    assert held == {row.url_key for row in rows if row.date == "2026-08-03"}
    assert len(held) == 2
    written = corpus.holdout_path(window).read_bytes()
    assert written.count(b"\n") == 2
    assert b"word" not in written, "the holdout is a set of hashes, not of articles"
    assert "held out 2 of 6 rows over 1 of 3 days" in capsys.readouterr().out


def test_a_training_row_and_a_holdout_row_are_never_the_same_row(window: Path) -> None:
    """Disjointness is a check, not a convention."""
    assert run(window, "split", "--holdout-days", "2") == 0
    held = corpus.read_holdout(window)
    trainable = {row.url_key for row in corpus.read_rows(window) if row.url_key not in held}

    assert held & trainable == set()
    assert held | trainable == {row.url_key for row in corpus.read_rows(window)}


def test_split_defaults_to_the_configured_holdout_days(window: Path) -> None:
    """A knob with no reader is not a knob (Rule #6)."""
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    assert config.finetune.holdout_days > 3

    assert run(window, "split") == 0

    assert len(corpus.read_holdout(window)) == 6, "the window is shorter than the holdout"


# --- verify ----------------------------------------------------------------


def test_verify_passes_on_a_corpus_the_harvest_wrote(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(window, "verify") == 0

    assert "verified" in capsys.readouterr().out


def test_verify_catches_a_row_that_broke_in_two(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure the escaping rule exists to prevent, seen from the other side."""
    path = corpus.rows_path(window)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"date"', '"da\nte"', 1), encoding="utf-8", newline="")

    assert run(window, "verify") == 1

    assert "does not load" in capsys.readouterr().out


def test_verify_catches_a_crlf_rewrite(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Windows trap, named because this repository is developed on Windows."""
    path = corpus.rows_path(window)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert run(window, "verify") == 1

    assert "CRLF" in capsys.readouterr().out


def test_verify_catches_a_missing_final_newline(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without it the next append joins two rows into one unparseable line."""
    path = corpus.rows_path(window)
    path.write_bytes(path.read_bytes().rstrip(b"\n"))

    assert run(window, "verify") == 1

    assert "no newline" in capsys.readouterr().out


def test_verify_catches_the_same_article_twice(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A duplicated target is a target weighted twice, silently."""
    rows = corpus.read_rows(window)
    corpus.write(window, [*rows, rows[0]], corpus.read_meta(window))

    assert run(window, "verify") == 1

    assert "share a url_key" in capsys.readouterr().out


def test_verify_only_reaches_the_network_when_asked(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The token check downloads a tokenizer, so it is a flag and never a default."""
    assert run(window, "verify") == 0

    assert "tokenizer" not in capsys.readouterr().out


# --- remove ----------------------------------------------------------------


def test_remove_prints_what_it_would_do_and_then_stops(
    roomy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unattended deletion of training data is how you lose training data."""
    before = len(corpus.read_rows(roomy))
    assert run(roomy, "remove", "--url-key", f"{7:064x}") == 0
    printed = capsys.readouterr().out

    assert "would remove 000000000000" in printed
    assert "Re-run with --yes" in printed
    assert len(corpus.read_rows(roomy)) == before, "nothing goes without --yes"


def test_remove_with_yes_drops_exactly_the_named_row(
    roomy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = {row.url_key for row in corpus.read_rows(roomy)}

    assert run(roomy, "remove", "--yes", "--url-key", f"{7:064x}") == 0
    after = {row.url_key for row in corpus.read_rows(roomy)}

    assert before - after == {f"{7:064x}"}
    assert corpus.read_meta(roomy).rows == len(after)
    assert "removed 1 rows" in capsys.readouterr().out


def test_remove_refuses_to_take_the_window_below_the_floor(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """And says how far below, because a refusal with no number is not an answer."""
    assert run(window, "remove", "--yes", "--url-key", "a" * 64) == 1
    printed = capsys.readouterr().out

    assert "refusing" in printed
    assert "495 below finetune.min_rows (500)" in printed
    assert len(corpus.read_rows(window)) == 6


def test_remove_leaves_every_other_row_byte_identical(
    window: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A repair that rewrites the rows it was not asked about is not a repair."""
    rows = corpus.read_rows(window)
    lines = {row.url_key: corpus.to_line(row) for row in rows}
    kept = [row for row in rows if row.url_key != "a" * 64]
    corpus.write(window, kept, corpus.read_meta(window))

    assert [corpus.to_line(row) for row in corpus.read_rows(window)] == [
        lines[row.url_key] for row in kept
    ]


def test_remove_says_so_when_no_row_holds_that_address(
    window: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(window, "remove", "--url-key", "9" * 64) == 1

    assert "no row holds url_key 999" in capsys.readouterr().out


# --- refill ----------------------------------------------------------------


@pytest.fixture
def app() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


def a_ledger(tmp_path: Path, rows: Sequence[EvalRow]) -> Path:
    path = tmp_path / "scores.csv"
    writer.append(path, rows)
    return path


def a_digest(tmp_path: Path, *, date: str, items: Sequence[DigestItem]) -> Path:
    """One committed day payload, in the layout `published_days` globs for.

    The run and vertical tallies are derived from the items rather than typed,
    because `DigestDay` cross-checks all three and a hand-typed count only ever
    disagrees.
    """
    verticals = Counter(item.vertical for item in items)
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{date}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(verticals.items())
        ],
        items=list(items),
    )
    root = tmp_path / "digest"
    path = root / date[:4] / date[5:7] / date[8:10] / "digest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(day.to_json(), encoding="utf-8", newline="")
    return root


def a_digest_item(article: Article, published: Published) -> DigestItem:
    base = DigestDay.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    ).items[0]
    return base.model_copy(
        update={
            "item_id": article.item_id,
            "vertical": article.vertical,
            "title": published.title,
            "summary": published.summary,
            "key_points": list(published.key_points),
            "source_url": article.canonical_url,
            "source_id": "grid-newsroom",
            "source_form": article.source_form,
            "introduced_by_run": 1,
            "updated_by_run": None,
            "visual": None,
        }
    )


def serving(pages: dict[str, bytes | None]) -> Callable[[str], FetchResult]:
    """Serve each address its bytes; a `None` is a page that is gone."""

    def read_url(url: str) -> FetchResult:
        body = pages.get(url)
        if body is None:
            return FetchResult(FetchOutcome.PERMANENT, status=404, detail="HTTP 404")
        return FetchResult(FetchOutcome.OK, status=200, body=body)

    return read_url


def test_refill_rebuilds_a_row_from_the_address_the_ledger_recorded(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The claim of the verb: a committed ledger row plus a live page is a row."""
    article, _ = refetched(REFILL_BODY, app)
    recorded = refill_recorded(article, REFILL_PUBLISHED)
    corpus_dir = tmp_path / "corpus"

    code = data_wrangler.refill(
        corpus_dir,
        config.load(CONFIG_DIR),
        ledger_path=a_ledger(tmp_path, [recorded]),
        digest_root=a_digest(
            tmp_path, date=recorded.date, items=[a_digest_item(article, REFILL_PUBLISHED)]
        ),
        limit=None,
        read_url=serving({article.canonical_url: refill_page(REFILL_BODY)}),
    )

    rows = corpus.read_rows(corpus_dir)
    assert code == 0
    assert [row.url_key for row in rows] == [article.url_key]
    assert rows[0].date == recorded.date
    assert "bodies re-fetched          1 of 1" in capsys.readouterr().out


def test_refill_reaches_no_address_it_already_holds_a_row_for(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-fetching what the window already has would spend a network round trip
    to produce a row the roll would then deduplicate away."""
    article, _ = refetched(REFILL_BODY, app)
    recorded = refill_recorded(article, REFILL_PUBLISHED)
    corpus_dir = tmp_path / "corpus"
    ledger_path = a_ledger(tmp_path, [recorded])
    digest_root = a_digest(
        tmp_path, date=recorded.date, items=[a_digest_item(article, REFILL_PUBLISHED)]
    )
    settings = config.load(CONFIG_DIR)
    data_wrangler.refill(
        corpus_dir,
        settings,
        ledger_path=ledger_path,
        digest_root=digest_root,
        limit=None,
        read_url=serving({article.canonical_url: refill_page(REFILL_BODY)}),
    )
    capsys.readouterr()

    def refuse(url: str) -> FetchResult:
        raise AssertionError(f"refill re-fetched an address it already holds: {url}")

    code = data_wrangler.refill(
        corpus_dir,
        settings,
        ledger_path=ledger_path,
        digest_root=digest_root,
        limit=None,
        read_url=refuse,
    )

    assert code == 0
    assert "skipped already in the window" in capsys.readouterr().out
    assert len(corpus.read_rows(corpus_dir)) == 1


def test_refill_drops_an_address_that_no_longer_answers_and_keeps_the_rest(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The open web loses pages. One 404 may not take the other rows down with it."""
    gone_url = "https://grid.example.com/2026/08/removed"
    alive, _ = refetched(REFILL_BODY, app)
    gone, _ = refetched(REFILL_BODY, app, url=gone_url, item_id="energy-02")
    rows = [
        refill_recorded(alive, REFILL_PUBLISHED),
        refill_recorded(gone, REFILL_PUBLISHED),
    ]
    corpus_dir = tmp_path / "corpus"

    code = data_wrangler.refill(
        corpus_dir,
        config.load(CONFIG_DIR),
        ledger_path=a_ledger(tmp_path, rows),
        digest_root=a_digest(
            tmp_path,
            date=rows[0].date,
            items=[
                a_digest_item(alive, REFILL_PUBLISHED),
                a_digest_item(gone, REFILL_PUBLISHED),
            ],
        ),
        limit=None,
        read_url=serving(
            {alive.canonical_url: refill_page(REFILL_BODY), gone_url: None}
        ),
    )
    printed = capsys.readouterr().out

    assert code == 0
    assert [row.url_key for row in corpus.read_rows(corpus_dir)] == [alive.url_key]
    assert "bodies re-fetched          1 of 2" in printed
    assert "no body" in printed


def test_refill_will_not_pair_a_summary_a_later_run_rewrote(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """The published item must recompute to the digest the ledger row recorded."""
    article, _ = refetched(REFILL_BODY, app)
    recorded = refill_recorded(article, REFILL_PUBLISHED)
    rewritten = REFILL_PUBLISHED._replace(summary=REFILL_PUBLISHED.summary + " Updated.")
    corpus_dir = tmp_path / "corpus"

    code = data_wrangler.refill(
        corpus_dir,
        config.load(CONFIG_DIR),
        ledger_path=a_ledger(tmp_path, [recorded]),
        digest_root=a_digest(
            tmp_path, date=recorded.date, items=[a_digest_item(article, rewritten)]
        ),
        limit=None,
        read_url=serving({article.canonical_url: refill_page(REFILL_BODY)}),
    )

    assert code == 0
    assert corpus.read_rows(corpus_dir) == []
    assert "published output is a different one" in capsys.readouterr().out


def test_refill_will_not_reach_for_a_pair_the_run_itself_rejected(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pair the counterweights already failed is dropped before the fetch.

    The saved round trip is the smaller half. The larger half is that the only
    way such a pair could pass on re-measurement is if the page moved under it,
    and a row that needs the article to have changed is not one to teach.
    """
    article, _ = refetched(REFILL_BODY, app)
    recorded = refill_recorded(article, REFILL_PUBLISHED, unsupported_numbers=2)
    corpus_dir = tmp_path / "corpus"

    def refuse(url: str) -> FetchResult:
        raise AssertionError(f"refill fetched a pair the run rejected: {url}")

    code = data_wrangler.refill(
        corpus_dir,
        config.load(CONFIG_DIR),
        ledger_path=a_ledger(tmp_path, [recorded]),
        digest_root=a_digest(
            tmp_path, date=recorded.date, items=[a_digest_item(article, REFILL_PUBLISHED)]
        ),
        limit=None,
        read_url=refuse,
    )

    assert code == 0
    assert corpus.read_rows(corpus_dir) == []
    assert "the run that made it already rejected it" in capsys.readouterr().out


def test_refill_at_a_limit_of_zero_touches_no_address(
    tmp_path: Path, app: AppConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    """How an operator reads the plan before spending an hour of network on it."""
    article, _ = refetched(REFILL_BODY, app)
    recorded = refill_recorded(article, REFILL_PUBLISHED)

    def refuse(url: str) -> FetchResult:
        raise AssertionError(f"a limit of zero fetched {url}")

    code = data_wrangler.refill(
        tmp_path / "corpus",
        config.load(CONFIG_DIR),
        ledger_path=a_ledger(tmp_path, [recorded]),
        digest_root=a_digest(
            tmp_path, date=recorded.date, items=[a_digest_item(article, REFILL_PUBLISHED)]
        ),
        limit=0,
        read_url=refuse,
    )

    assert code == 0
    assert "rebuildable                1" in capsys.readouterr().out


def test_refill_keeps_the_rows_it_had_already_rebuilt_when_it_is_interrupted(
    tmp_path: Path, app: AppConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-fetch of the whole ledger runs for tens of minutes. Stopping it, or
    losing the network half way, may not throw away every fetch that succeeded.

    CLAUDE.md section 1a: a re-run costs only the unfinished items. The window is
    committed every `_COMMIT_EVERY` items through the same temp-file-plus-rename
    write the scheduled harvest uses, so what is already rebuilt survives and the
    next run skips it.
    """
    monkeypatch.setattr(data_wrangler, "_COMMIT_EVERY", 2)
    built = [
        refetched(
            REFILL_BODY,
            app,
            url=f"https://grid.example.com/2026/08/item-{n}",
            item_id=f"energy-{n:02d}",
        )
        for n in range(3)
    ]
    rows = [refill_recorded(article, REFILL_PUBLISHED) for article, _ in built]
    reachable = {built[0][0].canonical_url, built[1][0].canonical_url}
    corpus_dir = tmp_path / "corpus"

    def read_url(url: str) -> FetchResult:
        if url not in reachable:
            raise KeyboardInterrupt("the operator stopped it")
        return FetchResult(FetchOutcome.OK, status=200, body=refill_page(REFILL_BODY))

    with pytest.raises(KeyboardInterrupt):
        data_wrangler.refill(
            corpus_dir,
            config.load(CONFIG_DIR),
            ledger_path=a_ledger(tmp_path, rows),
            digest_root=a_digest(
                tmp_path,
                date=rows[0].date,
                items=[a_digest_item(article, REFILL_PUBLISHED) for article, _ in built],
            ),
            limit=None,
            read_url=read_url,
        )

    kept = {row.url_key for row in corpus.read_rows(corpus_dir)}
    assert kept == {built[0][0].url_key, built[1][0].url_key}
    assert corpus.read_meta(corpus_dir).rows == 2, "the census agrees with the rows"


# --- shape -----------------------------------------------------------------


def test_the_wrangler_owns_no_schedule_and_reimplements_no_roll() -> None:
    """A local utility has no alarm on it, so nothing recurring may live here.

    `backfill` and `refill` do call the harvest, and that is the point: a
    deliberate replay a person runs once is not routine data movement. What they
    must never do is grow their own copy of the roll or their own idea of when to
    run, because that is the copy that drifts from the scheduled one.
    """
    source = read_text(Path(data_wrangler.__file__))

    assert "corpus.roll(" not in source, "the roll has one implementation"
    assert "harvest_is_due" not in source, "the cadence belongs to the scheduled step"
    assert "cron" not in source
    assert "corpus.harvest(" in source, "backfill reuses the shipped harvest"


def test_an_absent_corpus_is_reported_rather_than_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, "verify") == 1

    assert "does not exist" in capsys.readouterr().out
