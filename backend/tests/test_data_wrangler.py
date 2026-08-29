"""The operator's four verbs, run against a real corpus in a temp directory.

No mocks and no network (Rule #7). `verify --tokens` is the one path that
reaches the network, and the test for it is that it cannot run without the flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import corpus
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusMeta, CorpusRow
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


# --- shape -----------------------------------------------------------------


def test_the_wrangler_owns_no_schedule_and_reimplements_no_roll() -> None:
    """A local utility has no alarm on it, so nothing recurring may live here.

    `backfill` does call the harvest, and that is the point: a deliberate replay
    a person runs once is not routine data movement. What it must never do is
    grow its own copy of the roll or its own idea of when to run, because that is
    the copy that drifts from the scheduled one.
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
