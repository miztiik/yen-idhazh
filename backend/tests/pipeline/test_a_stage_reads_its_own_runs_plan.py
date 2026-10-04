"""Does a stage after the plan read its own run's plan when two runs planned one day?

Two runs of one UTC day can overlap: the daily workflow has no concurrency
group, and a run started by hand can land beside a scheduled one. Both plans
are filed under the same day of the run-plan ledger, so the newest plan of the
day can be the other run's, and a worker that read it would work the wrong
list. A stage told its run by `--execution` reads that run's plan and no other,
and a run with no plan on record stops and says which run it looked for.

Driven from the committed run-plan fixture, filed twice into the test's own
tree - no network, nothing mocked (Guardrail #7).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, writer_identity
from pytest import MonkeyPatch

from idhazh import cli, config, ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common

from ._builders import isolate_ledgers, plan

#: The fixture plan's day, and the two executions that both planned it.
DAY: Final = plan().date
EARLIER: Final = 1
LATER: Final = 2

#: An execution that planned nothing on that day.
UNPLANNED: Final = 3


def _run_id(execution: int) -> str:
    return f"{DAY}-{execution}"


def _file_two_plans(state: Path) -> None:
    """The fixture plan filed as two runs of one day, the later one generated later."""
    recorded = plan().model_dump(mode="json")
    for execution, generated_at in ((EARLIER, f"{DAY}T06:00:04Z"), (LATER, f"{DAY}T10:00:04Z")):
        filed = RunPlan.model_validate(
            {**recorded, "run_id": _run_id(execution), "generated_at": generated_at}
        )
        ledger.persist(
            state,
            [filed],
            ledger=LedgerName.RUN_PLAN,
            covers=DAY,
            identity=writer_identity(filed.run_id),
        )


def test_a_named_run_reads_its_own_plan_when_a_later_run_planned_the_same_day(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    _file_two_plans(common.STATE_ROOT)

    assert common._load_plan(DAY, _run_id(EARLIER)).run_id == _run_id(EARLIER)
    assert common._load_plan(DAY).run_id == _run_id(LATER), (
        "unnamed, the newest plan of the day is read, and here that is the other run's"
    )


def test_a_run_with_no_plan_on_record_stops_and_names_the_run(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    isolate_ledgers(tmp_path, monkeypatch)
    _file_two_plans(common.STATE_ROOT)

    with pytest.raises(FileNotFoundError, match=_run_id(UNPLANNED)):
        common._load_plan(DAY, _run_id(UNPLANNED))


def test_the_execution_a_step_passes_picks_the_plan_it_reads(
    tmp_path: Path, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Asked through the command line, as every workflow step asks.

    The run with no plan is refused although the day holds two, which reading
    the newest plan of the day could never do.
    """
    isolate_ledgers(tmp_path, monkeypatch)
    _file_two_plans(common.STATE_ROOT)

    with pytest.raises(FileNotFoundError, match=_run_id(UNPLANNED)):
        cli.main(["shards", "--date", DAY, "--execution", str(UNPLANNED)])

    assert cli.main(["shards", "--date", DAY, "--execution", str(EARLIER)]) == 0
    expected = cli.shard_count(len(plan().items), run=config.load(CONFIG_DIR).app.run)
    assert capsys.readouterr().out.strip() == str(expected)
