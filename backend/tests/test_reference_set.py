"""The reference-set harness, run against a real corpus in a temp directory.

No mocks and no network (Rule #7). Nothing here writes a summary - the point of
the harness is that it refuses what a run would refuse, so the tests are mostly
about what it turns away.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import config, corpus, summarize
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
from utilities import reference_set

VERTICALS = ("ai", "energy", "world")


@pytest.fixture
def settings() -> config.Settings:
    return config.load(CONFIG_DIR)


@pytest.fixture
def app() -> AppConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))


def a_row(app: AppConfig, *, band: int, key: str, vertical: str = "ai") -> CorpusRow:
    """One corpus row whose system turn is the real rendered prompt for `band`."""
    asked = app.summarize.bands[band]
    system = summarize.system_prompt(app.summarize, source_words=asked.min_source_words)
    return CorpusRow(
        version=CorpusRow.schema_version(),
        messages=[
            ChatTurn(role=ChatRole.SYSTEM, content=system),
            ChatTurn(role=ChatRole.USER, content="Source form: article\n\nthe body"),
            ChatTurn(role=ChatRole.ASSISTANT, content='{"title": "t", "summary": "s"}'),
        ],
        url_key=key.ljust(64, "0"),
        date="2026-08-24",
        model_id="qwen3-8b-q4-k-m",
        vertical=vertical,
    )


@pytest.fixture
def window(tmp_path: Path, app: AppConfig) -> Path:
    """A corpus spread over three bands and three verticals, plus one rare band."""
    rows = [
        a_row(app, band=1, key=f"a{n:02d}", vertical=VERTICALS[n % 3]) for n in range(12)
    ]
    rows += [a_row(app, band=2, key=f"b{n:02d}", vertical=VERTICALS[n % 3]) for n in range(6)]
    rows.append(a_row(app, band=4, key="c01", vertical="world"))
    path = tmp_path / "corpus"
    corpus.write(
        path,
        rows,
        corpus.census(
            rows, previous=CorpusMeta(version=CorpusMeta.schema_version()), prompt_digest="0" * 64
        ),
    )
    return path


def an_answer(app: AppConfig, band: int) -> str:
    """A target inside `band`'s word range that the decoder would accept."""
    asked = app.summarize.bands[band]
    words = " ".join(["word"] * asked.target_words_min)
    return json.dumps(
        {"title": "A title", "summary": words, "key_points": ["one point", "two point"]}
    )


# --- reading the stratification off a row ----------------------------------


def test_the_band_is_matched_on_the_rendered_prompt_not_parsed_from_it(app: AppConfig) -> None:
    """Equality against what a run would have sent, so a template edit cannot fool it."""
    prompts = reference_set.band_prompts(app.summarize)

    for index, rendered in enumerate(prompts):
        assert reference_set.band_of(rendered, prompts) == index


def test_a_row_written_under_a_prompt_that_has_since_moved_has_no_band(app: AppConfig) -> None:
    """It is dropped rather than guessed. A row whose ask we cannot name is not a task."""
    prompts = reference_set.band_prompts(app.summarize)

    assert reference_set.band_of("a prompt from an older build", prompts) is None


def test_the_source_form_is_read_off_the_line_user_turn_writes_first() -> None:
    assert reference_set.source_form_of("Source form: abstract\n\nbody") == "abstract"
    assert reference_set.source_form_of("no such line") == "unknown"


# --- queue -----------------------------------------------------------------


def test_the_queue_spreads_across_strata_rather_than_taking_the_commonest(
    window: Path, tmp_path: Path, settings: config.Settings
) -> None:
    """A set thin in a band trains a model thin in that band.

    The corpus here is 12 rows of band 1 against 1 of band 4, so a sample that
    just took the first N would hold no band 4 at all.
    """
    reference = tmp_path / "reference"

    assert reference_set.queue(reference, window, settings, count=8) == 0

    bands = {task.band for task in reference_set.read_queue(reference)}
    assert 4 in bands, "the rarest band has to survive the sample"
    assert len(bands) >= 3


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
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig
) -> None:
    """The queue can hold hours of authoring. Extending it may never discard any."""
    reference = tmp_path / "reference"
    reference_set.queue(reference, window, settings, count=4)
    tasks = reference_set.read_queue(reference)
    answered = tasks[0]._replace(assistant=an_answer(app, tasks[0].band))
    reference_set.write_queue(reference, [answered, *tasks[1:]])

    assert reference_set.queue(reference, window, settings, count=8) == 0

    kept = {task.url_key: task.assistant for task in reference_set.read_queue(reference)}
    assert kept[answered.url_key] == answered.assistant
    assert len(kept) == 8


def test_the_test_slice_is_spread_and_not_simply_the_tail(app: AppConfig) -> None:
    """A test reference that covers four of five bands measures four of five bands."""
    tasks = [
        reference_set.Task(
            url_key=f"{n:064x}",
            date="2026-08-24",
            vertical="ai",
            slice_=reference_set.TRAIN,
            band=n % 5,
            target_words_min=30,
            target_words_max=45,
            source_form="article",
            user="Source form: article\n\nbody",
            assistant=None,
        )
        for n in range(20)
    ]

    assigned = reference_set.assign_slices(tasks, test_rows=4)

    held = [task for task in assigned if task.slice_ == reference_set.TEST]
    assert len(held) == 4
    assert len({task.band for task in held}) == 4, "the held-back slice spans bands"


# --- check -----------------------------------------------------------------


def queued(
    reference: Path, window: Path, settings: config.Settings, count: int
) -> list[reference_set.Task]:
    reference_set.queue(reference, window, settings, count=count)
    return reference_set.read_queue(reference)


def test_check_accepts_an_answer_a_run_would_have_accepted(
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    reference_set.write_queue(
        reference, [task._replace(assistant=an_answer(app, task.band)) for task in tasks]
    )

    assert reference_set.check(reference, tmp_path / "empty", settings, write=False) == 0

    assert "answered and valid         4" in capsys.readouterr().out


def test_check_refuses_a_target_the_decoder_would_reject(
    window: Path, tmp_path: Path, settings: config.Settings,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A reference the constrained decoder would refuse teaches the model to be refused.

    One key point, where the grammar demands two. The decoder's rails are on
    characters and list length, which is why the band check below has to exist
    separately - neither rail knows what the system turn asked for.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 2)
    reference_set.write_queue(
        reference, [tasks[0]._replace(assistant='{"summary": "no title here"}'), tasks[1]]
    )

    assert reference_set.check(reference, tmp_path / "empty", settings, write=False) == 1

    assert "the decoder would reject it" in capsys.readouterr().out


def test_check_refuses_a_summary_outside_the_band_it_was_asked_for(
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The band is the ask, and it is tighter than the decoder's own rail.

    The length has to be one `draft_model` accepts, or this would only be
    re-testing the decoder. 150 words clears the global range and still breaks
    any band whose ceiling is below it.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    loose = next(task for task in tasks if task.target_words_max < 150)
    over = json.dumps(
        {
            "title": "A title",
            "summary": " ".join(["word"] * 150),
            "key_points": ["one point", "two point"],
        }
    )
    rest = [task for task in tasks if task.url_key != loose.url_key]
    reference_set.write_queue(reference, [loose._replace(assistant=over), *rest])

    assert reference_set.check(reference, tmp_path / "empty", settings, write=False) == 1

    assert "outside band" in capsys.readouterr().out


def test_check_refuses_an_article_the_training_window_also_holds(
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One article gets one target.

    Left overlapping, the notebook concatenates both files and trains the same
    article twice with two different answers - our model's and the better one.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 3)
    reference_set.write_queue(
        reference, [task._replace(assistant=an_answer(app, task.band)) for task in tasks]
    )

    assert reference_set.check(reference, window, settings, write=False) == 1

    printed = capsys.readouterr().out
    assert "in the training window as well" in printed
    assert "data_wrangler.py remove" in printed, "it names the way out, not just the fault"


def test_check_refuses_a_url_key_on_both_sides_of_the_train_test_line(
    window: Path, tmp_path: Path, settings: config.Settings, app: AppConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    answered = [task._replace(assistant=an_answer(app, task.band)) for task in tasks]
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
    prompt edit - it is re-rendered from the band when the row is built.
    """
    reference = tmp_path / "reference"
    tasks = queued(reference, window, settings, 4)
    reference_set.write_queue(
        reference, [task._replace(assistant=an_answer(app, task.band)) for task in tasks]
    )

    assert reference_set.check(reference, tmp_path / "empty", settings, write=True) == 0

    written = reference_set.rows_path(reference).read_text(encoding="utf-8").splitlines()
    rows = [corpus.from_line(line) for line in written]
    assert len(rows) == 4
    by_key = {task.url_key: task for task in tasks}
    for row in rows:
        band = app.summarize.bands[by_key[row.url_key].band]
        assert row.messages[0].content == summarize.system_prompt(
            app.summarize, source_words=band.min_source_words
        )


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


# --- shape -----------------------------------------------------------------


def test_the_harness_writes_no_summary_and_calls_no_model() -> None:
    """Row 5 decision 2: this is not hosted inference and not LLM-as-judge.

    A person writes the summaries in their editor. If this file ever grows a
    client, the reference set stops being independent of the thing it measures.
    """
    source = read_text(Path(reference_set.__file__))

    assert "http" not in source.replace("https://errors.pydantic.dev", "")
    assert "requests" not in source
    assert "urlopen" not in source
    assert "corpus.roll(" not in source, "the roll never touches the reference set"
