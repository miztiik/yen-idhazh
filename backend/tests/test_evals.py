"""Check retained measurements, checker identity and historical eval-row reads."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ValidationError
from support.ledger import seed_scores
from support.paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob, derive_url_key
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.knobs.extract import ExtractConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.evals import writer
from idhazh.evals.hhem import (
    HHEM_REVISION,
    HhemScorer,
    _with_transformers_5_tied_weights,
    is_pinned,
    weights_digest,
)
from idhazh.evals.metrics import (
    compression,
    scorer_version,
    word_count,
)
from idhazh.evals.score import to_eval_row
from idhazh.extract import to_article_with_source
from idhazh.fetch import FetchResult


#: The writer every case below files as. `assemble` is the job that scores a
#: whole day and it runs one shard, so this is what a finished run leaves. A
#: case that needs a second writer names its own.
def a_scoring_run(date: str) -> str:
    """The run that scored one UTC day."""
    return f"{date}-1"


def put(
    state: Path,
    rows: Sequence[EvalRow],
    *,
    run_id: str | None = None,
    attempt: int = 1,
) -> int:
    """One writer's measurements, filed the way a finished run files them."""
    return seed_scores(
        state,
        rows,
        run_id=run_id if run_id is not None else a_scoring_run(rows[0].date),
        attempt=attempt,
    )


ARTICLE = (
    "Example Grid ordered four small modular reactors from Northwind Atomics on Tuesday, "
    "in a deal worth 4.2 billion dollars. The first unit is expected to reach the site in "
    "2029, with commissioning slipping to 2031. Regulators in Ontario have not yet approved "
    "the design.\n\n"
    "The order is the largest placed by a Canadian utility since 1994. Northwind said the "
    "reactors would deliver 1200 megawatts in total. A spokesperson declined to say whether "
    "further orders were planned."
)

FAITHFUL = (
    "Example Grid has ordered four small modular reactors from Northwind Atomics in a "
    "4.2 billion dollar deal, with the first unit due at the site in 2029 and commissioning "
    "in 2031. Ontario regulators have not approved the design."
)


_RETIRED_READINGS = {
    "coverage": 0.62,
    "new_fact_rate": 0.5,
    "unsupported_numbers": 3,
    "hedge_dropped": True,
    "extractiveness": 0.95,
    "verbatim_run": 1.0,
    "self_repetition": 0.8,
    "semantic_coverage": 0.1,
    "evidential_density": 0.01,
    "speculative_density": 0.02,
    "determinism_violation": True,
}


def test_historical_eval_json_discards_only_retired_cells() -> None:
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    wide = {**payload, **_RETIRED_READINGS}
    row = EvalRow.model_validate(wide)

    assert _RETIRED_READINGS.keys().isdisjoint(row.model_dump())
    for key in ("version", "hhem", "hhem_full", "hhem_delta", "band", "scorer_version"):
        assert row.model_dump()[key] == payload[key]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EvalRow.model_validate({**wide, "unknown_measurement": 0.2})
    with pytest.raises(ValidationError, match="hhem_delta"):
        EvalRow.model_validate({**wide, "hhem_delta": 0.4})
    with pytest.raises(ValidationError, match="source_words"):
        EvalRow.model_validate({**wide, "source_words": wide["source_words_before_cap"] + 1})


def test_a_committed_shard_under_the_wide_header_still_parses_row_by_row() -> None:
    """The CSV half of the same migration, driven from a bounded fixture.

    A day file an earlier run wrote names both retired headings in its header
    line. `from_csv_row` has to place the cells it still knows and drop the two
    it does not, because the one-time move onto the ledger door reads every old
    CSV day of the eval ledger through it.
    """
    row = EvalRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    wide_cells = {**row.csv_row(), **{key: str(value) for key, value in _RETIRED_READINGS.items()}}
    wide_cells["source_word_count"] = wide_cells.pop("source_words_before_cap")
    wide_cells["source_seen_word_count"] = wide_cells.pop("source_words")

    read_back = EvalRow.from_csv_row(wide_cells)

    assert read_back == row
    assert read_back.csv_row().keys() == set(EvalRow.csv_columns())
    assert _RETIRED_READINGS.keys().isdisjoint(read_back.csv_row())

# --- The article's length, before the cap and after it ------------------------


def _row_for(article: Article) -> EvalRow:
    """One ledger row for one article, with everything else held still."""
    item = RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")).items[
        0
    ]
    written = Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    return to_eval_row(
        item=item,
        article=article,
        summary=written,
        full_text=article.text or "",
        premise=article.text or "",
        hhem=0.91,
        hhem_full=0.91,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )


def test_a_truncated_article_files_two_different_lengths() -> None:
    """The defect this pair exists to expose, and the assertion that was missing.

    Until 2026-08-27 `source_word_count` was `metrics.word_count(full_text)` - a
    regex over word shapes - while `source_seen_word_count` was
    `len(article.text.split())`. Production handed the same truncated string to
    both, so the pair was two counters over one text and the difference between
    them was tokenisation noise, not truncation. On 610 of 2,346 committed rows
    the seen count came out LARGER than the full count. Nothing compared the two
    cells, which is why it survived for months.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    text_words = len((article.text or "").split())
    article = article.model_copy(update={"word_count": text_words})
    row = _row_for(article)

    assert article.truncated, "the fixture has to be an article that was actually cut"
    assert row.source_words_before_cap is not None
    assert row.source_words_before_cap == article.source_word_count
    assert row.source_words is not None
    assert row.source_words == text_words
    assert row.source_words < row.source_words_before_cap, (
        "some source words never reached the model"
    )


def test_an_untruncated_article_reads_the_same_length_twice() -> None:
    """Equal is the truth here: the whole article IS the text the model saw."""
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    expected_length = len((article.text or "").split())
    article = article.model_copy(
        update={"word_count": expected_length, "source_word_count": expected_length}
    )
    row = _row_for(article)

    assert not article.truncated
    assert row.source_words_before_cap == row.source_words == expected_length


def test_the_lengths_do_not_move_when_the_scored_text_does() -> None:
    """Both counts come off the `Article`, so no caller can make them disagree.

    The three production callers pass `article.text` as `full_text`. Feeding a
    different string used to change one cell of the pair and not the other,
    which is exactly how the two ended up counting different things.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    row = _row_for(article)
    other = to_eval_row(
        item=RunPlan.from_json(
            read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
        ).items[0],
        article=article,
        summary=Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")),
        full_text=ARTICLE,
        premise=article.text or "",
        hhem=0.91,
        hhem_full=0.91,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )

    assert other.source_words_before_cap == row.source_words_before_cap
    assert other.source_words == row.source_words


def test_an_old_payload_that_was_cut_cannot_say_how_long_the_article_was() -> None:
    """None travels through rather than becoming a length nobody measured.

    `Article.source_word_count` is None on a payload written before extract
    recorded it. When that payload was truncated the pre-cap body is gone, so
    the post-cap count would claim the article was exactly as long as the part
    the model read.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "truncated.json"))
    text_words = len((article.text or "").split())
    article = article.model_copy(update={"word_count": text_words, "source_word_count": None})
    row = _row_for(article)

    assert article.truncated
    assert row.source_words_before_cap is None
    assert row.source_words == text_words, (
        "the seen count is still a measurement"
    )


def test_an_old_payload_that_was_never_cut_knows_its_own_length() -> None:
    """The same recovery the ledger migration makes, at the writer.

    Nothing was cut, so the article IS the text the model saw and the two counts
    are equal by construction. Refusing to say so would throw away a fact.
    """
    article = Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))
    text_words = len((article.text or "").split())
    article = article.model_copy(update={"word_count": text_words, "source_word_count": None})
    row = _row_for(article)

    assert not article.truncated
    assert row.source_words_before_cap == row.source_words == text_words


# --- The flag that says extract cut the body ---------------------------------

_PAGE = FIXTURES_DIR / "pages" / "article.html"
_PAGE_URL = "https://newsroom.example-grid.com/2026/08/reactor-order"
_PAGE_ITEM = PlannedItem(
    item_id="energy-01",
    url_key=derive_url_key(_PAGE_URL),
    source_url=_PAGE_URL,
    canonical_url=_PAGE_URL,
    source_id="grid-newsroom",
    tier=1,
    vertical="energy",
    title="Example Grid orders four small modular reactors",
    rank_score=1.4,
)


def _really_extracted(cap_tokens: int) -> Article:
    """The captured page through the real extractor, at the cap this case asks for.

    Never a hand-written payload. `truncated` typed into a fixture proves only
    that the test agrees with itself, and the defect this column carried was
    exactly a flag that read true about an article nobody had cut.
    """
    return to_article_with_source(
        _PAGE_ITEM,
        FetchResult(FetchOutcome.OK, status=200, body=_PAGE.read_bytes()),
        config=ExtractConfig(truncation_cap_tokens=cap_tokens),
        fetched_at="2026-08-21T06:03:11Z",
    ).article


def _row_for_page(article: Article, *, hhem: float, hhem_full: float) -> EvalRow:
    return to_eval_row(
        item=_PAGE_ITEM,
        article=article,
        summary=Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")),
        full_text=article.text or "",
        premise=article.text or "",
        hhem=hhem,
        hhem_full=hhem_full,
        config=EvaluationConfig(),
        date="2026-08-21",
        run_id="2026-08-21-1",
        scorer_version="hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
        scored_at="2026-08-21T06:18:02Z",
    )


def test_a_page_the_extractor_cut_is_flagged_whatever_the_two_scores_did() -> None:
    """A real cut, and no gap at all between the two faithfulness scores.

    The rule this replaces needed a gap above 0.100 and this case hands it 0.000,
    so the assertion cannot pass on the old rule.
    """
    article = _really_extracted(cap_tokens=256)
    row = _row_for_page(article, hhem=0.91, hhem_full=0.91)

    assert article.source_word_count is not None
    assert article.word_count < article.source_word_count, "the extractor really cut the body"
    assert article.truncated
    assert row.hhem_delta == 0.0
    assert row.truncation_flagged is article.truncated
    assert row.truncation_flagged


def test_a_page_left_whole_is_not_flagged_whatever_the_two_scores_did() -> None:
    """Nothing cut, and a gap three times the ceiling the old rule read.

    This is the defect the column had, in one assertion: on the committed ledger
    the flag was true on exactly one row, and that row read 748 words of a
    748-word article.
    """
    article = _really_extracted(cap_tokens=ExtractConfig().truncation_cap_tokens)
    row = _row_for_page(article, hhem=0.94, hhem_full=0.61)

    assert article.word_count == article.source_word_count, "nothing was cut"
    assert not article.truncated
    assert row.hhem_delta == pytest.approx(0.33)
    assert row.truncation_flagged is article.truncated
    assert not row.truncation_flagged


# --- Recorded, never flagged -------------------------------------------------


def test_compression_is_a_ratio_of_lengths() -> None:
    assert compression(FAITHFUL, ARTICLE) == pytest.approx(
        word_count(FAITHFUL) / word_count(ARTICLE)
    )


def test_compression_of_an_empty_source_does_not_divide_by_zero() -> None:
    assert compression(FAITHFUL, "") == 0.0


def test_a_short_article_is_not_a_defect() -> None:
    """The reason the 0.03-0.20 band was deleted: at a fixed output budget it
    fires on every short article, for a reason that is never about quality."""
    short_source = " ".join(["word"] * 400)
    summary = " ".join(["word"] * 160)
    assert compression(summary, short_source) > 0.20


# --- The version a row is written under --------------------------------------


def test_scorer_version_spells_its_components() -> None:
    version = scorer_version(
        scorer_id="hhem-2.1-open",
        scorer_revision="a1b2c3d4e5f6",
        weights_sha256="9f8e7d6c" + "0" * 56,
        evaluation=EvaluationConfig(),
    )
    assert (
        version == "hhem-2.1-open@a1b2c3d4;weights-9f8e7d6c;metrics-6;"
        "window=900/150/anchored;bands=0.80/0.50"
    )


def test_a_moved_window_moves_the_scorer_version() -> None:
    """A different premise is a different measurement, so rows must not pool.

    Both halves of the geometry count. The size decides how much article one
    score saw; the overlap decides how many windows the max is taken over.
    """
    args = {
        "scorer_id": "hhem-2.1-open",
        "scorer_revision": "a1b2c3d4e5f6",
        "weights_sha256": "9f8e7d6c" + "0" * 56,
    }
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(chunk_words=1800), **args
    )
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(chunk_overlap_words=300), **args
    )


def test_an_overlap_at_or_above_the_window_is_refused() -> None:
    """The chunker clamps the step to one word, so it walks rather than fails.

    A 4,000-word article at a zero step is 3,101 scorer passes instead of six.
    That is a job that never finishes, which is the worst way for a config typo
    to show up.
    """
    with pytest.raises(ValidationError, match="chunk_overlap_words must sit below"):
        EvaluationConfig(chunk_words=900, chunk_overlap_words=900)


def test_a_moved_band_moves_the_scorer_version() -> None:
    """A threshold change makes a derived column mean something else."""
    args = {
        "scorer_id": "hhem-2.1-open",
        "scorer_revision": "a1b2c3d4e5f6",
        "weights_sha256": "9f8e7d6c" + "0" * 56,
    }
    assert scorer_version(evaluation=EvaluationConfig(), **args) != scorer_version(
        evaluation=EvaluationConfig(band_high_min=0.85), **args
    )


def test_the_scorer_version_no_longer_names_a_counterweight_nothing_reads() -> None:
    """It carried a `lead=` component until 2026-09-24.

    The band input behind it is retired, so the string stops naming it - which
    moves every row's `scorer_version` once and restarts the run-day count in
    `evaluation.label_min_run_days`. Pinned here so a later change that puts a
    dead threshold back into the stamp fails rather than lands.
    """
    stamp = scorer_version(
        scorer_id="hhem-2.1-open",
        scorer_revision="a1b2c3d4e5f6",
        weights_sha256="9f8e7d6c" + "0" * 56,
        evaluation=EvaluationConfig(),
    )
    assert "lead=" not in stamp
    assert stamp.endswith("bands=0.80/0.50")


# --- The instrument is pinned, and says so -----------------------------------


def test_the_configured_scorer_revision_is_immutable() -> None:
    """It was the branch name `main` until 2026-08-26. A branch moves, and a
    faithfulness floor read off a moving instrument measures nothing (Guardrail #10)."""
    assert is_pinned(HHEM_REVISION)


def test_the_hhem_adapter_initializes_the_transformers_5_tied_weight_map() -> None:
    """The pinned remote class predates the field Transformers 5 reads while loading."""

    class LegacyHhem:
        _tied_weights_keys: ClassVar[dict[str, str]] = {
            "classifier.weight": "shared.weight"
        }

        def __init__(self, marker: str) -> None:
            self.marker = marker

    compatible = _with_transformers_5_tied_weights(LegacyHhem)
    model = compatible("loaded")

    assert model.marker == "loaded"
    assert model.all_tied_weights_keys == {
        "t5.transformer.encoder.embed_tokens.weight": "t5.transformer.shared.weight",
        "classifier.weight": "shared.weight",
    }


@pytest.mark.parametrize("revision", ["main", "v2.1", "refs/heads/main", ""])
def test_a_pointer_is_not_a_pin(revision: str) -> None:
    assert not is_pinned(revision)


def test_a_scorer_that_never_loaded_cannot_name_its_weights() -> None:
    """The old fallback hashed the name it was asked for, which validated and
    said nothing about the bytes that ran."""
    with pytest.raises(RuntimeError, match="has not loaded"):
        weights_digest(HhemScorer())


# --- Filing measurements -------------------------------------------------------


def test_every_filed_day_and_scorer_is_read_back(tmp_path: Path) -> None:
    """Distinct scorer identities survive filing, including rows from different months."""
    january = [_measurement(number) for number in range(6)]
    february = [
        row.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})
        for row in (_measurement(80), _measurement(81))
    ]
    retaken = january[0].model_copy(update={"scorer_version": "hhem-2.2-open@cccccccc;metrics-4"})
    rows = [*january, retaken, *february]
    state = tmp_path / "state"
    expected = {writer.observation(row.model_dump(mode="json")) for row in rows}

    assert len(expected) == len(rows), "the fixture repeated an observation"
    assert put(state, rows) == len(rows)

    produced = {writer.observation(record) for record in writer.records(state)}
    assert produced == expected
    assert ledger.held_days(state, LedgerName.SUMMARY_QUALITY_EVALS) == [
        "2026-01-09",
        "2026-02-03",
    ]


def _opened_bytes(
    monkeypatch: pytest.MonkeyPatch, root: Path, work: Callable[[], object]
) -> dict[str, int]:
    """What `work` opened under `root`, by relative path, in bytes.

    Measured at the file boundary rather than by timing, so the answer is the
    same on a loaded machine. `Path.open` is where every read in this module
    goes, so a spy on it counts real I/O and mocks nothing (Guardrail #7).
    """
    real = Path.open
    opened: dict[str, int] = {}

    def spy(self: Path, *args: Any, **kwargs: Any) -> Any:
        try:
            relative = self.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = ""
        if relative:
            opened[relative] = opened.get(relative, 0) + (
                self.stat().st_size if self.is_file() else 0
            )
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    try:
        work()
    finally:
        monkeypatch.undo()
    return opened


def _measurement(number: int) -> EvalRow:
    """One fixture-backed eval row with distinct item and measurement identities."""
    return _scored_row(0).model_copy(
        update={
            "item_id": f"ai-{number:05d}",
            "url_key": hashlib.sha256(f"index-url-{number}".encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"index-out-{number}".encode("ascii")).hexdigest(),
        }
    )


def _read_measurements(state: Path) -> list[tuple[str, ...]]:
    """Every measurement the ledger's reader hands back, one entry per row read."""
    return sorted(writer.observation(record) for record in writer.records(state))


def _measurements_of(rows: Sequence[EvalRow]) -> list[tuple[str, ...]]:
    """The measurements these rows are, one entry per distinct measurement."""
    return sorted({writer.observation(row.model_dump(mode="json")) for row in rows})


@pytest.mark.parametrize(
    ("job", "attempt"),
    [
        pytest.param(ServerJob.ASSEMBLE, 1, id="assemble-after-the-shard"),
        pytest.param(ServerJob.WORK, 2, id="the-shard-re-run"),
    ],
)
def test_one_measurement_filed_twice_on_one_day_is_read_once(
    tmp_path: Path, job: ServerJob, attempt: int
) -> None:
    """A work shard files its rows, then assemble or a re-run of the shard files them again.

    Both files stay on disk, and the reader keeps one row per measurement a day:
    assemble's copy is a second work unit whose repeats the key removes, and a
    re-run replaces its first try.
    """
    state = tmp_path / "state"
    rows = [_measurement(number) for number in range(4)]
    run_id = a_scoring_run(rows[0].date)
    again = [*rows, _measurement(9)]

    assert seed_scores(state, rows, run_id=run_id, job=ServerJob.WORK) == len(rows)
    assert seed_scores(state, again, run_id=run_id, job=job, attempt=attempt) == len(again)

    assert len(ledger.list_raw_files(state, LedgerName.SUMMARY_QUALITY_EVALS)) == 2
    assert _read_measurements(state) == _measurements_of(again), "one measurement was read twice"


def test_a_repeat_on_another_day_is_kept_under_each_day_and_once_in_the_whole_ledger(
    tmp_path: Path,
) -> None:
    """The same words filed on two days: each day keeps its row, and a read of every day keeps one.

    Accepted on purpose: no index recognises a measurement across days, so a
    named day's read still shows what that day filed, while a whole-ledger read
    settles once and keeps the earlier row.
    """
    state = tmp_path / "state"
    original = _measurement(0)
    later = original.model_copy(update={"date": "2026-02-03", "run_id": "2026-02-03-1"})

    assert put(state, [original]) == 1
    assert put(state, [later]) == 1
    days = [original.date, later.date]
    assert ledger.load_days(
        state, LedgerName.SUMMARY_QUALITY_EVALS, days, model=EvalRow
    ) == [original, later]
    assert list(writer.records(state)) == [original.csv_row()]


def test_two_copies_in_one_write_are_read_once(tmp_path: Path) -> None:
    state = tmp_path / "state"
    row = _measurement(0)

    assert put(state, [row, row]) == 2
    assert list(writer.records(state)) == [row.csv_row()]


def test_filing_opens_no_file_already_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guardrail #12, as files rather than as a clock.

    The writer adds one new file a day and reads nothing first, so no history
    it has filed before can make the next write cost more. The second write is
    another run's, so it is a work unit of its own rather than a re-run that
    replaces the first.
    """
    state = tmp_path / "state"
    first = [_measurement(number) for number in range(3)]
    put(state, first)
    before = {path.relative_to(state).as_posix() for path in state.rglob("*") if path.is_file()}
    assert before, "nothing was filed first, so this proves nothing"

    opened = _opened_bytes(
        monkeypatch, state, lambda: put(state, [_measurement(9)], run_id="2026-01-09-2")
    )

    assert not set(opened) & before, f"the writer read {sorted(set(opened) & before)} first"
    assert _read_measurements(state) == _measurements_of([*first, _measurement(9)])


def _scored_row(number: int) -> EvalRow:
    """One eval row off the committed fixture, unique in every key field."""
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.55 + number / 20, 4)
    return EvalRow.model_validate(
        {
            **base,
            "date": "2026-01-09",
            "run_id": "2026-01-09-1",
            "item_id": f"ai-{number:02d}",
            "url_key": hashlib.sha256(f"url-{number}".encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{number}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": ConfidenceBand.HIGH.value
            if faithfulness >= 0.80
            else ConfidenceBand.MEDIUM.value,
            "scored_at": "2026-01-09T06:18:02Z",
        }
    )
