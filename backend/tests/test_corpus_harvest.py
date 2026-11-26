"""The harvest, the roll and the two due checks.

No mocks and no network (Guardrail #7). Every article, summary and eval row here is a
committed fixture, and the prompt comes from the shipped prompt builder rather
than from a copy of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from support.refill import refetched, refill_body, refill_published, refill_recorded

from idhazh import corpus
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.summary import Summary
from idhazh.evals.metrics import compression, word_count

DATE = "2026-08-28"


def contract_fixture(stem: str, name: str) -> str:
    return read_text(CONTRACT_FIXTURES_DIR / stem / f"{name}.json")


@pytest.fixture
def app() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


@pytest.fixture
def article() -> Article:
    return Article.from_json(contract_fixture("article", "ok"))


def scored(article: Article, summary_name: str, eval_name: str | None) -> corpus.Scored:
    """One item's three payloads, made to name the same article."""
    summary = Summary.from_json(contract_fixture("summary", summary_name)).model_copy(
        update={"url_key": article.url_key, "item_id": article.item_id}
    )
    row = (
        None
        if eval_name is None
        else EvalRow.from_json(contract_fixture("eval-row", eval_name)).model_copy(
            update={"url_key": article.url_key, "item_id": article.item_id}
        )
    )
    return corpus.Scored(article, summary, row)


def row_at(date: str, key: str, *, answer: str = "a") -> CorpusRow:
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content="s"),
            ChatTurn(role=ChatRole.USER, content="u"),
            ChatTurn(role=ChatRole.ASSISTANT, content=answer),
        ],
        url_key=key * 64,
        date=date,
        model_id="sample-model",
        vertical="sample-topic",
    )


# --- The Oracle: the corpus is the prompt we serve -------------------------


def test_the_system_turn_is_rendered_from_the_prompt_file_the_harvest_is_given(
    app: AppConfig, article: Article, tmp_path: Path
) -> None:
    """A corpus is the prompt that is served, and the served prompt is a configured file.

    A harvest that ignored the location it was handed would teach the default
    prompt to a model that is run under another one.
    """
    target = tmp_path / app.prompt_files.summarize_article
    target.parent.mkdir()
    target.write_text("Quote at most $max_verbatim_words words.", encoding="utf-8")

    rows = corpus.harvest_rows(
        [scored(article, "titled", "high")],
        date=DATE,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
        prompt_files=app.prompt_files,
        config_dir=tmp_path,
    )

    assert [row.system for row in rows] == [
        f"Quote at most {app.summarize.max_verbatim_words} words."
    ]


# --- What a row has to clear to become a training target -------------------


def test_a_summary_with_no_title_is_not_a_target(app: AppConfig, article: Article) -> None:
    """A null title means the drafted one could not be published as written.

    The decoder is made to write a title, so a row without one is not an answer
    the model gives, and training on it would teach a shape the grammar refuses.
    """
    assert (
        corpus.harvest_rows(
            [scored(article, "ok", "high")],
            date=DATE,
            prompt_config=app.summarize,
            evaluation=app.evaluation,
        )
        == []
    )


def test_retired_measurements_do_not_reject_a_training_target(
    app: AppConfig, article: Article
) -> None:
    item = scored(article, "titled", "low-invented-number")
    assert item.row is not None
    copied = item.summary.summary
    assert copied is not None
    source = f"{copied} {article.text} {article.text}"
    extracted = Article.model_validate(
        {
            **article.model_dump(mode="json"),
            "text": source,
            "word_count": len(source.split()),
            "source_word_count": len(source.split()),
        }
    )
    legacy = EvalRow.model_validate(
        {
            **item.row.model_dump(mode="json"),
            "compression": compression(copied, source),
            "summary_words": word_count(copied),
            "source_words": extracted.word_count,
            "source_words_before_cap": extracted.source_word_count,
            "unsupported_numbers": 3,
            "hedge_dropped": True,
            "determinism_violation": True,
            "extractiveness": 1.0,
            "verbatim_run": 1.0,
        }
    )
    harvested = corpus.harvest_rows(
        [item._replace(article=extracted, row=legacy)],
        date=DATE,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )
    assert len(harvested) == 1
    assert "\n\n".join(json.loads(harvested[0].messages[-1].content)["paragraphs"]) == copied


def test_corpus_selection_retains_the_exact_compression_cutoff_without_a_model_gate(
    app: AppConfig, article: Article
) -> None:
    item = scored(article, "titled", "high")
    assert item.row is not None
    cutoff = app.evaluation.corpus_compression_ceiling
    assert corpus.accepts_training_candidate(
        item.row.model_copy(
            update={"hhem": 0.0, "hhem_full": 0.0, "hhem_delta": 0.0, "compression": cutoff - 0.001}
        ),
        evaluation=app.evaluation,
    )
    for changes in ({"compression": cutoff}, {"compression": cutoff + 0.001}, {"extraction_suspect": True}):
        assert not corpus.accepts_training_candidate(
            item.row.model_copy(update=changes), evaluation=app.evaluation
        )


def test_refill_preserves_the_published_answer_and_recounts_source_words(app: AppConfig) -> None:
    article, full_text = refetched(refill_body(), app)
    published = refill_published()
    recorded = refill_recorded(article, published).model_copy(update={"compression": 0.99})
    rebuilt = corpus.rescored(article, full_text, recorded=recorded, published=published)

    assert rebuilt.summary.title == published.title
    assert rebuilt.summary.summary == published.summary
    assert rebuilt.summary.model_id == recorded.model_id
    assert rebuilt.row is not None
    assert rebuilt.row.compression < app.evaluation.corpus_compression_ceiling
    assert rebuilt.row.source_words == article.word_count
    assert rebuilt.row.hhem == recorded.hhem
    assert rebuilt.row.scorer_version == recorded.scorer_version
    assert len(corpus.harvest_rows(
        [rebuilt], date=DATE, prompt_config=app.summarize, evaluation=app.evaluation
    )) == 1


# --- Reading a run's items directory ---------------------------------------


def write_items(items_dir: Path, item: corpus.Scored) -> None:
    """One item's payloads, named the way the work stage names them."""
    item_id = item.article.item_id
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / f"{item_id}.article.json").write_text(
        item.article.to_json(), encoding="utf-8", newline=""
    )
    (items_dir / f"{item_id}.summary.json").write_text(
        item.summary.to_json(), encoding="utf-8", newline=""
    )
    if item.row is not None:
        (items_dir / f"{item_id}.eval.json").write_text(
            item.row.to_json(), encoding="utf-8", newline=""
        )


def test_a_flat_run_directory_and_a_downloaded_artifact_set_read_the_same(
    tmp_path: Path, article: Article
) -> None:
    """A live run writes one directory; a download arrives one directory per shard.

    They are the same run, so the reader has to see them as the same run - which
    is what lets `backfill` replay a finished run from its artifacts alone.
    """
    item = scored(article, "titled", "high")
    flat = tmp_path / "flat"
    nested = tmp_path / "nested"
    write_items(flat, item)
    write_items(nested / "items-2", item)

    assert corpus.scored_from_items(flat) == [item]
    assert corpus.scored_from_items(nested) == [item]


def test_an_article_with_no_summary_is_not_an_item(tmp_path: Path, article: Article) -> None:
    """The work stage writes the article first, so a half-written pair is normal."""
    write_items(tmp_path, scored(article, "titled", "high"))
    (tmp_path / f"{article.item_id}.summary.json").unlink()

    assert corpus.scored_from_items(tmp_path) == []


def test_an_item_with_no_eval_row_is_read_and_then_dropped_later(
    tmp_path: Path, app: AppConfig, article: Article
) -> None:
    """Reading and filtering are different jobs, and only one of them is the corpus's."""
    write_items(tmp_path, scored(article, "titled", None))
    read = corpus.scored_from_items(tmp_path)

    assert len(read) == 1
    assert read[0].row is None
    assert (
        corpus.harvest_rows(
            read, date=DATE, prompt_config=app.summarize, evaluation=app.evaluation
        )
        == []
    )


def test_an_absent_items_directory_is_no_items_rather_than_a_crash(tmp_path: Path) -> None:
    assert corpus.scored_from_items(tmp_path / "never-ran") == []


def test_a_row_is_dated_by_its_own_eval_row_not_by_the_caller(
    app: AppConfig, article: Article
) -> None:
    """One backfill can replay several runs, and each row belongs to its own day.

    Dating every row by the argument would stamp a replay of last week's run with
    the day somebody happened to run the replay, and the roll evicts by date.
    """
    item = scored(article, "titled", "high")
    assert item.row is not None
    dated = corpus.Scored(
        item.article, item.summary, item.row.model_copy(update={"date": "2026-08-01"})
    )

    rows = corpus.harvest_rows(
        [dated], date="2026-12-25", prompt_config=app.summarize, evaluation=app.evaluation
    )

    assert [row.date for row in rows] == ["2026-08-01"]


# --- The roll --------------------------------------------------------------


@pytest.mark.parametrize("existing_count", [0, 2, 3])
def test_the_roll_evicts_the_oldest_first(existing_count: int) -> None:
    rows = [row_at("2026-08-01", "a"), row_at("2026-08-02", "b"), row_at("2026-08-28", "c")]

    kept = corpus.roll(rows[:existing_count], rows[existing_count:], window=2)

    assert kept == rows[1:]


def test_the_roll_keeps_the_original_row_for_an_article_it_already_holds() -> None:
    """Identity is the article, not the run that saw it."""
    first = row_at("2026-08-01", "a")
    again = row_at("2026-08-28", "a")

    kept = corpus.roll([first], [again], window=10)

    assert kept == [first]


def test_one_article_twice_in_one_harvest_is_one_row() -> None:
    """The window it is joining is not the only place a repeat can come from.

    Two feeds carrying one article, or one feed listing it twice, hands the roll
    two rows for one address in a single call. Nothing before this point settles
    them: the harvest reads what the day published, and a corpus that holds an
    article twice trains on it twice.
    """
    first = row_at("2026-08-01", "a")
    again = row_at("2026-08-01", "a", answer="a later answer")

    kept = corpus.roll([], [first, again], window=10)

    assert kept == [first]


def test_the_roll_orders_by_date_then_address_not_by_arrival() -> None:
    """Two runs that harvest the same items in a different order write one file."""
    rows = [row_at("2026-08-02", "b"), row_at("2026-08-01", "a"), row_at("2026-08-01", "c")]

    assert corpus.roll([], rows, window=10) == corpus.roll([], list(reversed(rows)), window=10)


def test_a_window_of_zero_is_refused_rather_than_emptying_the_corpus() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        corpus.roll([row_at("2026-08-01", "a")], [], window=0)


# --- The harvest, end to end -----------------------------------------------


def test_harvesting_the_same_day_twice_does_not_move_the_row_count(
    tmp_path: Path, app: AppConfig, article: Article
) -> None:
    """A re-run costs the unfinished work and nothing else (section 1a)."""
    items = [scored(article, "titled", "high")]
    kwargs = {
        "date": DATE,
        "finetune": app.finetune,
        "prompt_config": app.summarize,
        "evaluation": app.evaluation,
    }

    first = corpus.harvest(tmp_path, items, **kwargs)  # type: ignore[arg-type]
    written = (tmp_path / "corpus.jsonl").read_bytes()
    second = corpus.harvest(tmp_path, items, **kwargs)  # type: ignore[arg-type]

    assert first.rows == second.rows == 1
    assert (tmp_path / "corpus.jsonl").read_bytes() == written


def test_the_census_is_recounted_from_the_window_never_incremented(
    tmp_path: Path, app: AppConfig, article: Article
) -> None:
    """Census values must come from saved rows, not from prior metadata."""
    item = scored(article, "titled", "high")
    assert item.row is not None
    expected_date = item.row.date
    meta = corpus.harvest(
        tmp_path,
        [item],
        date=DATE,
        finetune=app.finetune,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )
    rows = corpus.read_rows(tmp_path)

    assert rows
    expected_models = {item.summary.model_id: len(rows)}
    assert meta.rows == len(rows)
    assert meta.models == expected_models
    # The row carries its eval row's date, not the harvest argument.
    assert meta.first_date == meta.last_date == expected_date
    assert meta.harvested_date == DATE
    assert meta.prompt_digest is not None
    stale = meta.model_copy(
        update={"models": {item.summary.model_id: len(rows) + 1}}
    )
    recounted = corpus.census(rows, previous=stale, prompt_digest=meta.prompt_digest)
    assert recounted.models == expected_models


def test_a_write_replaces_the_file_and_preserves_escaped_text(tmp_path: Path) -> None:
    meta = CorpusMeta(version=CorpusMeta.schema_version())
    answer = 'quote " backslash \\ newline \n tab \t carriage \r nul \x00 accent \u00e9'
    rows = [row_at("2026-08-02", "b", answer=answer), row_at("2026-08-03", "c")]
    corpus.write(tmp_path, [row_at("2026-08-01", "a")], meta)
    corpus.write(tmp_path, rows, meta)

    raw = (tmp_path / "corpus.jsonl").read_bytes()
    assert raw.count(b"\n") == len(rows)
    assert b"\r" not in raw
    assert corpus.read_rows(tmp_path) == rows


def test_an_absent_corpus_reads_as_empty_rather_than_raising(tmp_path: Path) -> None:
    """A fresh clone has no window yet, and that is not an error."""
    assert corpus.read_rows(tmp_path) == []
    assert corpus.read_holdout(tmp_path) == frozenset()
    assert corpus.read_meta(tmp_path).rows == 0


# --- The two due checks ----------------------------------------------------


def test_a_corpus_that_has_never_been_harvested_is_always_due() -> None:
    assert corpus.harvest_is_due(CorpusMeta(version=CorpusMeta.schema_version()), date=DATE, every_days=7)


@pytest.mark.parametrize(
    ("last", "every", "expected"),
    [
        ("2026-08-27", 7, False),
        ("2026-08-22", 7, False),
        ("2026-08-21", 7, True),
        ("2026-07-01", 7, True),
        ("2026-08-27", 1, True),
        ("2026-08-28", 1, False),
    ],
)
def test_the_harvest_cadence_is_counted_in_days_between_two_committed_dates(
    last: str, every: int, expected: bool
) -> None:
    """No clock in the answer, so a job that woke late still harvests.

    A cron line could not express this at all: `on.schedule` is parsed before
    any step runs, so no config value reaches it, and 5-field cron has no
    every-N-days field.
    """
    meta = CorpusMeta(version=CorpusMeta.schema_version(), harvested_date=last)

    assert corpus.harvest_is_due(meta, date=DATE, every_days=every) is expected


def test_recording_the_run_moves_one_field_and_no_other(tmp_path: Path) -> None:
    """It records that a job ran. It is not a second census."""
    before = CorpusMeta(
        version=CorpusMeta.schema_version(),
        rows=3, first_date="2026-08-01", last_date=DATE,
    )
    corpus.write(tmp_path, [], before)

    after = corpus.record_run(tmp_path, date=DATE)

    assert after.model_dump(exclude={"last_run"}) == before.model_dump(exclude={"last_run"})
    assert after.last_run == DATE


def test_a_census_that_lost_count_is_refused() -> None:
    """The harvest is the last place anything holds the window and its census.

    Driven directly, because `census` recounts from the window and so cannot
    disagree with it through `harvest`. The shape being refused is a counted
    field that stopped being recounted, which is a change to code.
    """
    rows = [row_at("2026-08-01", "a"), row_at("2026-08-02", "b")]
    counted = corpus.census(
        rows, previous=CorpusMeta(version=CorpusMeta.schema_version()), prompt_digest="d"
    )

    corpus.refuse_a_miscounted_census(rows, counted)

    with pytest.raises(ValueError, match="the census does not count its own window"):
        corpus.refuse_a_miscounted_census(rows, counted.model_copy(update={"rows": len(rows) - 1}))
