"""Which runs draw the scorer, and does a run record the rate it drew under?"""

from __future__ import annotations

import inspect
import itertools
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text
from pytest import MonkeyPatch

from idhazh import assemble, cli, config
from idhazh.contracts.app_config import ObservabilityConfig
from idhazh.contracts.run_manifest import RunManifest, RunRecord
from idhazh.contracts.run_plan import RunPlan
from idhazh.evals import sampling, writer
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.work import stage_work

from ._builders import (
    captured_article_fetch,
    closed_loopback_endpoint,
    isolate_ledgers,
    plan,
    row,
    score_one_item,
    work_then_assemble,
)

pytestmark = pytest.mark.slow


def synthetic_run_ids(count: int = 1000) -> list[str]:
    """Distinct ids in the shape the pipeline mints them: `<date>-<n>`."""
    return [
        f"2026-{index // 155 + 1:02d}-{index % 31 + 1:02d}-{index % 5 + 1}"
        for index in range(count)
    ]

def observed(observability: ObservabilityConfig) -> config.Settings:
    """The committed settings with one observability block swapped in."""
    settings = config.load(CONFIG_DIR)
    return config.Settings(
        app=settings.app.model_copy(update={"observability": observability}),
        models=settings.models,
        appearance=settings.appearance,
        sources=settings.sources,
        taxonomy=settings.taxonomy,
        watchlist=settings.watchlist,
        digests=settings.digests,
    )

def last_record(tmp_path: Path, run_plan: RunPlan) -> RunRecord:
    day_dir = assemble.day_dir(tmp_path / "public" / "digest", run_plan.date)
    return RunManifest.from_json(read_text(day_dir / "run.json")).runs[-1]

def test_a_full_rate_draws_every_run_and_changes_nothing() -> None:
    """A knob whose default moves any behaviour has failed before it ships.

    One is short-circuited rather than compared, because a position near enough
    to one rounds to exactly 1.0 as a float and `1.0 < 1.0` is false.
    """
    assert all(sampling.run_is_sampled(run_id, 1.0) for run_id in synthetic_run_ids())
    assert all(
        cli._scores_this_run(ObservabilityConfig(), run_id=run_id, flag_allows=True)
        for run_id in synthetic_run_ids()
    )

def test_the_same_run_id_draws_the_same_way_every_time() -> None:
    """A selector nobody can reproduce is a ledger nobody can audit a year later."""
    ids = synthetic_run_ids()
    first = [sampling.run_is_sampled(run_id, 0.5) for run_id in ids]
    second = [sampling.run_is_sampled(run_id, 0.5) for run_id in ids]

    assert first == second
    assert all(0.0 <= sampling.position_of(run_id) < 1.0 for run_id in ids)
    assert sampling.position_of("2026-08-21-1") == sampling.position_of("2026-08-21-1")

def test_half_the_rate_draws_about_half_the_runs() -> None:
    """1,000 draws at 0.5 has a standard deviation of 15.8, so 50 is over three of them."""
    drawn = sum(1 for run_id in synthetic_run_ids() if sampling.run_is_sampled(run_id, 0.5))
    assert 450 <= drawn <= 550, f"{drawn} of 1000 drawn at a rate of 0.5"

def test_raising_the_rate_only_ever_adds_runs() -> None:
    """A run scored yesterday still scores today, so a series does not develop a hole."""
    ids = synthetic_run_ids()
    rates = (0.1, 0.25, 0.5, 0.75, 0.9)
    drawn = {
        rate: {run_id for run_id in ids if sampling.run_is_sampled(run_id, rate)} for rate in rates
    }

    for lower, higher in itertools.pairwise(rates):
        assert drawn[lower] < drawn[higher], f"{lower} is not a subset of {higher}"

def test_the_draw_sees_the_run_id_and_the_rate_and_nothing_else() -> None:
    """Blindness is a property of the signature, never of one sample.

    A selector that could see a score would thin the ledger towards whatever it
    preferred, and no later reader could tell that it had.
    """
    assert list(inspect.signature(sampling.run_is_sampled).parameters) == [
        "run_id",
        "sample_rate",
    ]
    assert list(inspect.signature(sampling.position_of).parameters) == ["run_id"]

def test_the_work_stage_gate_and_the_selector_agree() -> None:
    thinned = ObservabilityConfig(sample_rate=0.3)
    for run_id in synthetic_run_ids(200):
        assert cli._scores_this_run(thinned, run_id=run_id, flag_allows=True) is (
            sampling.run_is_sampled(run_id, 0.3)
        )

def test_the_flag_beats_the_file_and_no_flag_turns_the_scorer_back_on() -> None:
    on = ObservabilityConfig()
    off = ObservabilityConfig(evaluation_enabled=False)

    assert cli._scores_this_run(on, run_id="2026-08-21-1", flag_allows=True)
    assert not cli._scores_this_run(on, run_id="2026-08-21-1", flag_allows=False)
    assert not cli._scores_this_run(off, run_id="2026-08-21-1", flag_allows=True)

@pytest.mark.parametrize("rate", [1.0, 0.5, 0.01])
def test_every_run_records_the_rate_it_ran_under(
    tmp_path: Path, monkeypatch: MonkeyPatch, rate: float
) -> None:
    """A rate recorded only when it bites cannot be told from a rate never set.

    Eight hundred rows of a thousand and eight hundred of eight hundred are the
    same eight hundred rows in the ledger, and only the manifest can separate
    them.
    """
    run_plan = plan()
    settings = observed(ObservabilityConfig(sample_rate=rate))
    isolate_ledgers(tmp_path, monkeypatch)

    work_then_assemble(run_plan, settings)
    record = last_record(tmp_path, run_plan)

    assert record.evaluation_sample_rate == rate
    assert record.evaluation_enabled is True
    assert record.evaluation_sampled is sampling.run_is_sampled(run_plan.run_id, rate)

def test_a_run_with_the_scorer_off_writes_no_row_and_names_no_instrument(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Switched off and would not load are different facts, and null is neither."""
    run_plan = plan()
    settings = observed(ObservabilityConfig(evaluation_enabled=False))
    isolate_ledgers(tmp_path, monkeypatch)

    work_then_assemble(run_plan, settings)
    record = last_record(tmp_path, run_plan)

    assert record.evaluation_enabled is False
    assert record.scorer_version is None
    assert not writer.ledger_days(tmp_path / "state")

def test_a_scored_run_names_the_instrument_that_wrote_its_rows(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"

    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    score_one_item(items_dir, run_plan)
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    record = last_record(tmp_path, run_plan)

    assert record.scorer_version == row().scorer_version
    assert record.evaluation_sampled is True
