"""The reference-set harness, run against a real corpus in a temp directory.

No mocks and no network (Guardrail #7). Nothing here writes a summary - the point of
the harness is that it refuses what a run would refuse, so the tests are mostly
about what it turns away.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, corpus, summarize
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import Article
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from idhazh.contracts.sources import SourceForm
from utilities import reference_set

VERTICALS = ("ai", "energy", "world")
#: Three user-turn lengths, in words, that fall in three different doubling strata.
SHORT, MEDIUM, LONG = 100, 1_000, 5_000


@pytest.fixture
def settings() -> config.Settings:
    return config.load(CONFIG_DIR)


@pytest.fixture
def app() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


def a_row(
    app: AppConfig, *, words: int, key: str, vertical: str = "ai", system: str | None = None
) -> CorpusRow:
    """One corpus row whose user turn is `words` words long, under the live prompt by default."""
    prefix = "Source form: article\n\n"
    body = " ".join(["word"] * (words - len(prefix.split())))
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content=system or summarize.system_prompt(app.summarize)),
            ChatTurn(role=ChatRole.USER, content=prefix + body),
            ChatTurn(role=ChatRole.ASSISTANT, content='{"title": "t", "summary": "s"}'),
        ],
        url_key=key.ljust(64, "0"),
        date="2026-08-24",
        model_id="qwen3-8b-q4-k-m",
        vertical=vertical,
    )


def write_corpus(path: Path, rows: list[CorpusRow]) -> Path:
    corpus.write(
        path,
        rows,
        corpus.census(
            rows, previous=CorpusMeta(version=CorpusMeta.schema_version()), prompt_digest="0" * 64
        ),
    )
    return path


@pytest.fixture
def window(tmp_path: Path, app: AppConfig) -> Path:
    """A corpus spread over three lengths and three verticals, plus one rare long article."""
    rows = [
        a_row(app, words=SHORT, key=f"a{n:02d}", vertical=VERTICALS[n % 3]) for n in range(12)
    ]
    rows += [
        a_row(app, words=MEDIUM, key=f"b{n:02d}", vertical=VERTICALS[n % 3]) for n in range(6)
    ]
    rows.append(a_row(app, words=LONG, key="c01", vertical="world"))
    return write_corpus(tmp_path / "corpus", rows)


def an_answer() -> str:
    """A target the decoder would accept."""
    return json.dumps({"title": "A title", "paragraphs": ["a few words"]})


# --- reading the stratification off a row ----------------------------------


def test_the_source_form_is_read_off_the_line_user_turn_writes_first() -> None:
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    abstract = article.model_copy(update={"source_form": SourceForm.ABSTRACT})

    assert reference_set.source_form_of(summarize.user_turn(abstract)) == "abstract"
    assert reference_set.source_form_of("no such line") == "unknown"


# --- queue -----------------------------------------------------------------


def test_the_queue_spreads_across_strata_rather_than_taking_the_commonest(
    window: Path, tmp_path: Path, settings: config.Settings
) -> None:
    """A set thin in one length trains a model thin in that length.

    The corpus here is 12 rows of 100 words against 1 of 5,000, so a sample that
    just took the first N would hold no long article at all.
    """
    reference = tmp_path / "reference"

    assert reference_set.queue(reference, window, settings, count=8) == 0

    lengths = {len(task.user.split()) for task in reference_set.read_queue(reference)}
    assert lengths == {SHORT, MEDIUM, LONG}, "the rarest length has to survive the sample"


def test_the_queue_is_the_same_set_every_time_it_is_built(
    window: Path, tmp_path: Path, settings: config.Settings
) -> None:
    """No random number anywhere, so a re-run tops up instead of reshuffling."""
    first, second = tmp_path / "one", tmp_path / "two"
    reference_set.queue(first, window, settings, count=9)
    reference_set.queue(second, window, settings, count=9)

    assert [task.url_key for task in reference_set.read_queue(first)] == [
        task.url_key for task in reference_set.read_queue(second)
    ]


def test_queueing_again_keeps_an_answer_somebody_already_wrote(
    window: Path, tmp_path: Path, settings: config.Settings
) -> None:
    """The queue can hold hours of authoring. Extending it may never discard any."""
    reference = tmp_path / "reference"
    reference_set.queue(reference, window, settings, count=4)
    tasks = reference_set.read_queue(reference)
    answered = tasks[0]._replace(assistant=an_answer())
    reference_set.write_queue(reference, [answered, *tasks[1:]])

    assert reference_set.queue(reference, window, settings, count=8) == 0

    kept = {task.url_key: task.assistant for task in reference_set.read_queue(reference)}
    assert kept[answered.url_key] == answered.assistant
    assert len(kept) == 8


def test_a_row_written_under_a_prompt_that_has_since_moved_is_not_queued(
    tmp_path: Path, settings: config.Settings, app: AppConfig
) -> None:
    """Its user turn is not one a run would send now, so it is not a task."""
    current = a_row(app, words=SHORT, key="a1")
    older = a_row(app, words=SHORT, key="b1", system="a prompt from an older build")
    corpus_dir = write_corpus(tmp_path / "corpus", [current, older])
    reference = tmp_path / "reference"

    assert reference_set.queue(reference, corpus_dir, settings, count=10) == 0

    assert [task.url_key for task in reference_set.read_queue(reference)] == [current.url_key]


def test_the_test_slice_is_spread_and_not_simply_the_tail() -> None:
    """A test reference that covers four of five strata measures four of five strata."""
    tasks = [
        reference_set.Task(
            url_key=f"{n:064x}",
            date="2026-08-24",
            vertical="ai",
            slice_=reference_set.TRAIN,
            source_form="article",
            user="Source form: article\n\n" + " ".join(["word"] * 10 ** (n % 5)),
            assistant=None,
        )
        for n in range(20)
    ]

    assigned = reference_set.assign_slices(tasks, test_rows=4)

    held = [task for task in assigned if task.slice_ == reference_set.TEST]
    assert len(held) == 4
    assert len({len(task.user.split()) for task in held}) == 4, "the held-back slice spans strata"


# --- check -----------------------------------------------------------------


def queued(
    reference: Path, window: Path, settings: config.Settings, count: int
) -> list[reference_set.Task]:
    reference_set.queue(reference, window, settings, count=count)
    return reference_set.read_queue(reference)


def test_check_refuses_a_target_the_decoder_would_reject(
    window: Path, tmp_path: Path, settings: config.Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A reference the constrained decoder would refuse teaches the model to be refused.

    No title, where the grammar demands one.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 2)
    reference_set.write_queue(
        reference, [tasks[0]._replace(assistant='{"summary": "no title here"}'), tasks[1]]
    )

    assert reference_set.check(reference, tmp_path / "empty", settings, write=False) == 1

    assert "the decoder would reject it" in capsys.readouterr().out


def test_check_refuses_an_article_the_training_window_also_holds(
    window: Path, tmp_path: Path, settings: config.Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One article gets one target.

    Left overlapping, the notebook concatenates both files and trains the same
    article twice with two different answers - our model's and the better one.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 3)
    reference_set.write_queue(reference, [task._replace(assistant=an_answer()) for task in tasks])

    assert reference_set.check(reference, window, settings, write=False) == 1

    printed = capsys.readouterr().out
    assert "in the training window as well" in printed
    assert "data_wrangler.py remove" in printed, "it names the way out, not just the fault"


def test_check_refuses_a_url_key_on_both_sides_of_the_train_test_line(
    window: Path, tmp_path: Path, settings: config.Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    answered = [task._replace(assistant=an_answer()) for task in tasks]
    twinned = answered[0]._replace(
        slice_=reference_set.TEST
        if answered[0].slice_ == reference_set.TRAIN
        else reference_set.TRAIN
    )
    reference_set.write_queue(reference, [*answered, twinned])

    assert reference_set.check(reference, tmp_path / "empty", settings, write=False) == 1

    assert "both sides of the train/test line" in capsys.readouterr().out


def test_check_writes_rows_the_corpus_reader_loads_and_the_prompt_owns(
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig
) -> None:
    """The oracle: a reference row's system turn IS `summarize.system_prompt`.

    Not a copy of one the queue carried, which could have gone stale against a
    prompt edit - it is re-rendered when the row is built.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    reference_set.write_queue(reference, [task._replace(assistant=an_answer()) for task in tasks])

    assert reference_set.check(reference, tmp_path / "empty", settings, write=True) == 0

    lines = reference_set.rows_path(reference).read_text(encoding="utf-8").splitlines()
    rows = [corpus.from_line(line) for line in lines]
    assert len(rows) == 4
    for row in rows:
        assert row.system == summarize.system_prompt(app.summarize)


def test_check_will_not_write_while_anything_is_unresolved(
    window: Path, tmp_path: Path, settings: config.Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A half-checked reference set is the one nobody re-checks."""
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 2)
    reference_set.write_queue(reference, [tasks[0]._replace(assistant="{}"), tasks[1]])

    assert reference_set.check(reference, tmp_path / "empty", settings, write=True) == 1

    assert "refusing to write" in capsys.readouterr().out
    assert not reference_set.rows_path(reference).exists()
