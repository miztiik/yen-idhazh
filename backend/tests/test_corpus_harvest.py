"""The harvest, the roll and the two due checks.

No mocks and no network (Rule #7). Every article, summary and eval row here is a
committed fixture, and the prompt comes from the shipped prompt builder rather
than from a copy of it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import corpus, summarize
from idhazh.contracts.app_config import AppConfig, FinetuneConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.summary import Summary

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


def row_at(date: str, key: str, vertical: str = "ai") -> CorpusRow:
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content="s"),
            ChatTurn(role=ChatRole.USER, content="u"),
            ChatTurn(role=ChatRole.ASSISTANT, content="a"),
        ],
        url_key=key * 64,
        date=date,
        model_id="qwen3-5-9b-q4-k-m",
        vertical=vertical,
    )


# --- The Oracle: the corpus is the prompt we serve -------------------------


def test_the_first_two_turns_are_the_bytes_the_run_really_sends(
    app: AppConfig, article: Article
) -> None:
    """The whole point of the module, asserted directly rather than by token diff.

    A corpus assembled from a rebuilt prompt can drift from the prompt production
    sends and nothing notices until a fine-tuned model underperforms for a reason
    nobody can name. These turns come from `system_prompt` and `user_turn`, which
    is what `build_request` calls, so the two are the same bytes by construction -
    and this is the test that keeps them that way.
    """
    request = summarize.build_request(
        article,
        model_id=app.models.summarize.id,
        inference=app.models.inference,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )
    harvested = corpus.harvest_rows(
        [scored(article, "titled", "high")],
        date=DATE,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )

    assert len(harvested) == 1
    assert [
        {"role": turn.role.value, "content": turn.content}
        for turn in harvested[0].messages[:2]
    ] == request["messages"]


def test_the_band_travels_with_the_article_it_was_chosen_for(app: AppConfig) -> None:
    """A brief and a long read are asked for different lengths.

    A harvest that rendered one band for every row would teach one target length
    for every article, which is the opposite of what the bands exist to do.
    """
    brief = Article.from_json(contract_fixture("article", "brief"))
    long_read = Article.from_json(contract_fixture("article", "ok"))

    rows = corpus.harvest_rows(
        [scored(brief, "titled", "high"), scored(long_read, "titled", "high")],
        date=DATE,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )

    assert len(rows) == 2
    assert rows[0].system != rows[1].system
    assert rows[0].system == summarize.system_prompt(
        app.summarize, source_words=brief.band_source_words, brief=brief.brief
    )


# --- What a row has to clear to become a training target -------------------


def test_a_summary_whose_title_missed_its_range_is_not_a_target(
    app: AppConfig, article: Article
) -> None:
    """A null title means the drafted one was thrown away.

    That row is an example of the model failing the ask, so training on it
    teaches the failure.
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


def test_a_row_that_hedged_or_invented_a_number_is_not_a_target(
    app: AppConfig, article: Article
) -> None:
    """Rejection sampling on the measures a model cannot game by copying."""
    assert (
        corpus.harvest_rows(
            [scored(article, "titled", "low-invented-number")],
            date=DATE,
            prompt_config=app.summarize,
            evaluation=app.evaluation,
        )
        == []
    )


def test_an_unscored_item_is_not_a_target(app: AppConfig, article: Article) -> None:
    """No eval row means no counterweights, and a filter that cannot run is not a filter."""
    assert (
        corpus.harvest_rows(
            [scored(article, "titled", None)],
            date=DATE,
            prompt_config=app.summarize,
            evaluation=app.evaluation,
        )
        == []
    )


def test_the_faithfulness_score_is_never_what_selects_a_row() -> None:
    """It is the alarm this project reads a run by.

    Shape the training data with it and the tuned model has been optimised
    against its own monitor, after which the monitor is measuring something it
    helped produce. Asserted on the source so the rule cannot be undone quietly.
    """
    source = read_text(Path(corpus.__file__))
    body = source.split("def keeps_its_counterweights", 1)[1].split("\ndef ", 1)[0]

    assert "hhem" not in body, "the alarm may veto a model; it may never select a row"


# --- The roll --------------------------------------------------------------


def test_the_roll_evicts_the_oldest_first() -> None:
    """Paired with a date-trailing holdout, this is what keeps a test set intact.

    Evicting at random, or from the newest end, would let the window quietly
    shrink the held-out set every week - and a comparison run on fewer articles
    each month, with nothing anywhere saying so.
    """
    existing = [row_at("2026-08-01", "a"), row_at("2026-08-02", "b")]
    incoming = [row_at("2026-08-28", "c")]

    kept = corpus.roll(existing, incoming, window=2)

    assert [row.date for row in kept] == ["2026-08-02", "2026-08-28"]


def test_the_roll_never_exceeds_the_window() -> None:
    existing = [row_at(f"2026-08-0{n}", chr(ord("a") + n)) for n in range(1, 6)]

    assert len(corpus.roll(existing, [], window=3)) == 3
    assert len(corpus.roll([], existing, window=3)) == 3
    assert len(corpus.roll(existing, existing, window=99)) == len(existing)


def test_rolling_the_same_rows_again_changes_nothing() -> None:
    """A re-run of a day must not rewrite every row it touched.

    A corpus that changes when nothing changed cannot be diffed, and a diff is
    the only way anyone reviews what a scheduled job committed.
    """
    existing = [row_at("2026-08-01", "a"), row_at("2026-08-02", "b")]
    once = corpus.roll(existing, existing, window=10)
    twice = corpus.roll(once, existing, window=10)

    assert once == existing
    assert twice == once


def test_the_roll_keeps_the_original_row_for_an_article_it_already_holds() -> None:
    """Identity is the article, not the run that saw it."""
    first = row_at("2026-08-01", "a", vertical="ai")
    again = row_at("2026-08-28", "a", vertical="energy")

    kept = corpus.roll([first], [again], window=10)

    assert kept == [first]


def test_the_roll_orders_by_date_then_address_not_by_arrival() -> None:
    """Two runs that harvest the same items in a different order write one file."""
    rows = [row_at("2026-08-02", "b"), row_at("2026-08-01", "a"), row_at("2026-08-01", "c")]

    assert corpus.roll([], rows, window=10) == corpus.roll([], list(reversed(rows)), window=10)


def test_a_window_of_zero_is_refused_rather_than_emptying_the_corpus() -> None:
    with pytest.raises(ValueError, match="at least one row"):
        corpus.roll([row_at("2026-08-01", "a")], [], window=0)


# --- The roll cannot reach the reference set -------------------------------


def test_the_roll_leaves_the_hand_authored_reference_set_byte_identical(
    tmp_path: Path, app: AppConfig, article: Article
) -> None:
    """The strongest of the three guarantees is that they are different files.

    `write` opens `corpus.jsonl` and `corpus.meta.json` in the directory it was
    handed and nothing else, so it has no way to open the reference set - which
    is authored by a person once and would take twelve hours to rebuild.
    """
    reference = tmp_path / "reference" / "reference.jsonl"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b'{"messages": [], "authored": true}\n')
    before = reference.read_bytes()

    corpus.harvest(
        tmp_path,
        [scored(article, "titled", "high")],
        date=DATE,
        finetune=app.finetune,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )

    assert reference.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "corpus.jsonl",
        "corpus.meta.json",
        "reference",
    ]


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
    """An incremented counter and the file it counts drift, and only one is true."""
    meta = corpus.harvest(
        tmp_path,
        [scored(article, "titled", "high")],
        date=DATE,
        finetune=app.finetune,
        prompt_config=app.summarize,
        evaluation=app.evaluation,
    )

    assert meta.rows == len(corpus.read_rows(tmp_path))
    assert meta.verticals == {article.vertical: 1}
    assert meta.models == {"qwen3-8b-q4-k-m": 1}
    assert meta.first_date == meta.last_date == DATE
    assert meta.harvested_date == DATE
    assert meta.prompt_digest is not None


def test_a_write_leaves_no_half_written_file_behind(tmp_path: Path) -> None:
    """Temp-then-rename, so the corpus on disk is the old one or the new one."""
    corpus.write(tmp_path, [row_at("2026-08-01", "a")], CorpusMeta(version=CorpusMeta.schema_version()))
    corpus.write(tmp_path, [row_at("2026-08-02", "b")], CorpusMeta(version=CorpusMeta.schema_version()))

    assert sorted(p.name for p in tmp_path.iterdir()) == ["corpus.jsonl", "corpus.meta.json"]
    assert corpus.read_rows(tmp_path) == [row_at("2026-08-02", "b")]


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


def test_a_repository_that_has_never_been_pruned_is_due_once_and_then_stamped(
    tmp_path: Path,
) -> None:
    """The stamp is what turns a force-push a day into a force-push a month."""
    assert corpus.prune_is_due(CorpusMeta(version=CorpusMeta.schema_version()), date=DATE, every_days=30)

    corpus.write(tmp_path, [], CorpusMeta(version=CorpusMeta.schema_version()))
    stamped = corpus.stamp_prune(tmp_path, date=DATE)

    assert stamped.pruned_date == DATE
    assert not corpus.prune_is_due(stamped, date=DATE, every_days=30)
    assert corpus.prune_is_due(stamped, date="2026-09-27", every_days=30)


def test_stamping_the_prune_moves_one_field_and_no_other(tmp_path: Path) -> None:
    """It records that a job ran. It is not a second census."""
    before = CorpusMeta(
        version=CorpusMeta.schema_version(),
        rows=3, first_date="2026-08-01", last_date=DATE, verticals={"ai": 3}
    )
    corpus.write(tmp_path, [], before)

    after = corpus.stamp_prune(tmp_path, date=DATE)

    assert after.model_dump(exclude={"pruned_date"}) == before.model_dump(
        exclude={"pruned_date"}
    )
    assert after.pruned_date == DATE


def test_the_committed_seed_lets_a_fresh_clone_run_unconfigured() -> None:
    """`git add corpus` runs under `set -euo pipefail` in the commit step.

    A staged path that does not exist yet aborts that step and takes every
    ledger staged beside it, so the window ships empty rather than absent.
    """
    seed = Path(corpus.__file__).resolve().parents[2] / corpus.CORPUS_ROOT_RELPATH

    assert corpus.read_rows(seed) == []
    assert corpus.read_meta(seed).rows == 0
    assert corpus.read_meta(seed).harvested_date is None
    assert FinetuneConfig().corpus_rows >= 1
