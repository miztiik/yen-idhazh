"""Does a council verb run a night with no judge in it, and hand over its own clock?

The whole of what the venue does with a tenant, driven through the command line
because the wiring is what can be wrong: every other council test hands a unit
an instant of its own, so only a real invocation can say the command line
computes one at all.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh import cli, config, ledger
from idhazh.contracts.council_shard_outcome import (
    SELECTION_UNIT,
    SETTLEMENT_UNIT,
    CouncilShardOutcome,
    ShardOutcome,
)
from idhazh.council import registry, session
from idhazh.council.deadline import SECONDS_A_MINUTE

from ._tenants import a_scripted_venue, a_venue, forget, written

A_VENUE = "a_paper_venue"

A_SLUG = "a-paper-tenant"

ANOTHER_SLUG = "another-paper-tenant"

A_DATE = "2026-09-20"

A_RUN = "2026-09-21-35534060762"

#: Every council verb the router carries. Named here so a verb added without a
#: zero-tenant arm fails this file rather than shipping untested.
COUNCIL_VERBS = ("council-prepare", "council-settle")

#: The stage modules the content-similarity judge owns, spelled one by one. A
#: shared prefix used to stand in for the list, and a stage is now named for the
#: work it does rather than for whose loop it is in - so a prefix would go blind
#: to three of these four and the dictum would read green over a real import.
JUDGE_STAGE_MODULES = (
    "idhazh.stages.pick_item_pairs",
    "idhazh.stages.judge_item_pairs",
    "idhazh.stages.count_verdicts",
    "idhazh.stages.set_merge_line",
)


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable package on the import path, and a scratch root off the checkout.

    The council's own scratch root is a real directory inside the repository, so
    a test that left it alone would write one night's rows into the tree it is
    testing.
    """
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", A_VENUE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "var" / "council")
    forget(A_VENUE)
    yield tmp_path
    forget(A_VENUE)


def _config_registering(root: Path, *slugs: str) -> Path:
    """A whole `config/` in a temp directory, with the named slugs registered."""
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    raw = json.loads(read_text(target / "idhazh.json"))
    raw["council"]["tenants"] = list(slugs)
    (target / "idhazh.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8", newline="\n"
    )
    return target


def _the_councils_record(state_root: Path) -> list[CouncilShardOutcome]:
    """The night's own day file, read back through the contract that wrote it."""
    lines = (
        ledger.council_shard_outcomes_path(state_root, A_DATE)
        .read_text(encoding="utf-8")
        .splitlines()
    )
    columns = lines[0].split(",")
    return [
        CouncilShardOutcome.from_csv_row(dict(zip(columns, line.split(","), strict=True)))
        for line in lines[1:]
    ]


def _a_whole_night(
    config_root: Path, state_root: Path, *, slugs: tuple[str, ...], shards: int, dead: tuple[int, ...]
) -> None:
    """Pick the work, run every unit, then settle - all through the command line."""
    common = ["--date", A_DATE, "--run-id", A_RUN, "--config", str(config_root)]
    assert cli.main(["council-prepare", *common]) == 0
    for slug in slugs:
        for shard in range(shards):
            argv = [
                "council-shard",
                "--tenant",
                slug,
                *common,
                "--shard",
                str(shard),
                "--shards",
                str(shards),
            ]
            if shard in dead:
                with pytest.raises(RuntimeError):
                    cli.main(argv)
            else:
                assert cli.main(argv) == 0
    assert cli.main(["council-settle", *common, "--state-root", str(state_root)]) == 0


def _judge_modules_reached(module: str, prefixes: tuple[str, ...]) -> list[str]:
    """Which judge modules a fresh interpreter pulls in when it imports `module`.

    A subprocess because this suite has already imported most of the tree, so
    `sys.modules` in here would answer a different question.
    """
    probe = (
        f"import {module}, sys, json;"
        "print(json.dumps(sorted(n for n in sys.modules "
        f"if n.startswith({prefixes[0]!r})"
        + "".join(f" or n.startswith({prefix!r})" for prefix in prefixes[1:])
        + ")))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
    )
    found: list[str] = json.loads(completed.stdout)
    return found


@pytest.mark.parametrize("verb", COUNCIL_VERBS)
def test_a_council_verb_runs_a_night_that_hosts_nobody(verb: str, tmp_path: Path) -> None:
    """The zero-tenant arm, against a config that registers nobody.

    A venue with no tenants judges nothing, and that is correct. What it must
    not do is fail: every step of the night still runs, which is what makes the
    council buildable and testable with no judge in the repository.

    The config is written here rather than read out of `config/`, which has
    registered a judge since 2026-09-21. Reading the committed one would ask
    what that judge does instead of what an empty room does - and would run a
    real night's work over the checkout's own stores on the way.
    """
    empty = _config_registering(tmp_path)

    assert cli.main([verb, "--date", A_DATE, "--run-id", A_RUN, "--config", str(empty)]) == 0


@pytest.mark.parametrize("verb", [*COUNCIL_VERBS, "council-shard"])
def test_a_council_verb_refuses_to_invent_a_run_it_was_not_given(verb: str) -> None:
    """A verb with no name to file under stops at the command line, not two hours in.

    Every value it could reach for belongs to somebody else: a digest run's id
    claims a machine and a clock this night never drew.
    """
    with pytest.raises(SystemExit) as refused:
        cli.main([verb, "--date", A_DATE])

    assert refused.value.code == 2, "argparse refuses a bad command line with 2"


def test_a_shard_with_no_tenant_stops_at_the_command_line() -> None:
    """One cell is one tenant, so a cell that names none has nothing to run.

    Without the refusal the verb would spend a runner - a checkout, an install
    and a multi-gigabyte weights restore - to decide it had been told nothing.
    """
    with pytest.raises(SystemExit) as refused:
        cli.main(["council-shard", "--date", A_DATE, "--run-id", A_RUN])

    assert refused.value.code == 2


def test_the_command_line_hands_the_tenant_the_councils_own_clock(venue: Path) -> None:
    """A bound nothing computes is a bound that never fires on a real night.

    Driven through the entry point rather than the session module, because the
    defect would be in the wiring. What the tenant is handed is checked against
    the committed clocks rather than against a number written here, so raising
    either clock moves the deadline and never this test.
    """
    a_venue(venue, package=A_VENUE, slugs={A_SLUG: (2, ())})
    config_root = _config_registering(venue, A_SLUG)
    council = config.load(config_root).app.council
    window = (
        council.shard_timeout_minutes
        - council.shard_preamble_minutes
        - council.shard_wrap_up_minutes
    ) * SECONDS_A_MINUTE

    before = time.monotonic()
    code = cli.main(
        [
            "council-shard",
            "--tenant",
            A_SLUG,
            "--date",
            A_DATE,
            "--run-id",
            A_RUN,
            "--shard",
            "1",
            "--shards",
            "2",
            "--config",
            str(config_root),
        ]
    )
    after = time.monotonic()

    tenant = written(A_VENUE, A_SLUG).TENANT
    assert code == 0
    assert tenant.ran == [(A_DATE, A_RUN, 1, 2)]
    assert len(tenant.handed) == 1, "one cell is one unit of work"
    assert before + window <= tenant.handed[0] <= after + window, (
        "the instant the tenant was handed is not the one the committed clocks describe"
    )


def test_the_night_runs_every_hosted_tenant_for_the_date_it_was_given(venue: Path) -> None:
    """Pick the work, then settle it, both once a date and both for every tenant."""
    a_venue(venue, package=A_VENUE, slugs={A_SLUG: (1, ())})
    config_root = _config_registering(venue, A_SLUG)
    council = config.load(config_root).app.council

    session.prepare(council, date=A_DATE, run_id=A_RUN)
    session.settle(council, date=A_DATE, run_id=A_RUN, state_dir=venue / "state")

    tenant = written(A_VENUE, A_SLUG).TENANT
    assert tenant.prepared == [A_DATE]
    assert tenant.settled == [A_DATE]


def test_the_scratch_root_the_workflow_carries_is_the_one_the_council_names() -> None:
    """One answer to where a night's work lands, so the artifact steps cannot drift.

    The workflow uploads and downloads this path by name. A second answer here
    would mean a unit writing where nothing collects from, and the run would look
    like a tenant that produced nothing.
    """
    assert session.scratch_root(A_DATE).as_posix().endswith(
        f"{session.COUNCIL_ROOT_RELPATH}/{A_DATE}"
    )
    assert not Path(session.COUNCIL_ROOT_RELPATH).is_absolute()


def test_a_unit_that_died_leaves_a_gap_the_recorded_width_makes_readable(
    venue: Path, tmp_path: Path
) -> None:
    """The Oracle: three of four units recorded, and the pair says which is missing.

    The outcome vocabulary has no word for a unit that died, and that is the
    design - a unit the platform kills cannot write one either. What an operator
    reads is the count: three rows that each say the work was split four ways.
    """
    a_scripted_venue(venue, package=A_VENUE, slug=A_SLUG, shard_count=4, dead_units=(2,))
    config_root = _config_registering(venue, A_SLUG)
    state_root = tmp_path / "state"

    _a_whole_night(config_root, state_root, slugs=(A_SLUG,), shards=4, dead=(2,))

    recorded = _the_councils_record(state_root)
    ran = [row for row in recorded if row.shard >= 0]

    assert sorted(row.shard for row in recorded) == [SETTLEMENT_UNIT, SELECTION_UNIT, 0, 1, 3]
    assert [row.shard for row in ran] == [0, 1, 3], "the unit that died filed nothing"
    assert {row.shards for row in recorded} == {4}
    assert len(ran) < ran[0].shards, "the pair is what an operator reads as a missing unit"
    assert {row.judge_id for row in recorded} == {A_SLUG}


def test_a_unit_that_stopped_on_its_own_clock_still_has_its_row_filed(
    venue: Path, tmp_path: Path
) -> None:
    """The second Oracle case. A unit that ran out of time is not a unit that vanished.

    The council files the outcome the tenant reported and never infers one from
    its own clock, so this row says `stopped_on_deadline` and carries the cost of
    the work that did get done.
    """
    a_scripted_venue(
        venue,
        package=A_VENUE,
        slug=A_SLUG,
        shard_count=1,
        outcome="stopped_on_deadline",
        model_calls=7,
    )
    config_root = _config_registering(venue, A_SLUG)
    state_root = tmp_path / "state"

    _a_whole_night(config_root, state_root, slugs=(A_SLUG,), shards=1, dead=())

    unit = next(row for row in _the_councils_record(state_root) if row.shard == 0)

    assert unit.outcome is ShardOutcome.STOPPED_ON_DEADLINE
    assert unit.model_calls == 7, "the count comes off what the tenant handed back"
    assert unit.seconds_spent >= 0
    assert unit.started_at.endswith("Z")
    assert unit.run_id == A_RUN


def test_a_tenant_with_no_model_files_empty_cost_cells_and_never_zeros(
    venue: Path, tmp_path: Path
) -> None:
    """Null and zero are different facts, and only the tenant knows which it is.

    Every one of these cells is copied off what the tenant handed back. The
    council opens no store of a tenant's and reads no field of a tenant's
    contract, so a tenant with no model files nothing rather than four zeros.
    """
    a_scripted_venue(venue, package=A_VENUE, slug=A_SLUG, shard_count=1)
    config_root = _config_registering(venue, A_SLUG)
    state_root = tmp_path / "state"

    _a_whole_night(config_root, state_root, slugs=(A_SLUG,), shards=1, dead=())

    unit = next(row for row in _the_councils_record(state_root) if row.shard == 0)

    assert (unit.model_calls, unit.tokens_in, unit.tokens_out, unit.model_seconds) == (
        None,
        None,
        None,
        None,
    )
    assert unit.csv_row()["model_calls"] == "", "an empty cell, never a zero"


def test_two_tenants_of_one_night_both_keep_their_own_first_unit(
    venue: Path, tmp_path: Path
) -> None:
    """One council run has one run id, so the slug is what tells the two apart.

    Without `judge_id` in the settlement key, tenant B's first unit carries the
    same three cells as tenant A's and the pass that drops repeats would delete
    one of them - a night that ran twice as much work as the record shows.
    """
    for slug in (A_SLUG, ANOTHER_SLUG):
        a_scripted_venue(venue, package=A_VENUE, slug=slug, shard_count=1)
    config_root = _config_registering(venue, A_SLUG, ANOTHER_SLUG)
    state_root = tmp_path / "state"

    _a_whole_night(config_root, state_root, slugs=(A_SLUG, ANOTHER_SLUG), shards=1, dead=())

    recorded = _the_councils_record(state_root)

    assert "judge_id" in ledger.COUNCIL_SHARD_OUTCOME_KEY
    assert sorted((row.judge_id, row.shard) for row in recorded) == [
        (A_SLUG, SETTLEMENT_UNIT),
        (A_SLUG, SELECTION_UNIT),
        (A_SLUG, 0),
        (ANOTHER_SLUG, SETTLEMENT_UNIT),
        (ANOTHER_SLUG, SELECTION_UNIT),
        (ANOTHER_SLUG, 0),
    ]


def test_a_night_that_hosts_nobody_leaves_no_day_file_behind(tmp_path: Path) -> None:
    """A header with no rows under it is a real day to the partition walker.

    Written once, it is a phantom day in the prune target and the day inventory
    for as long as the store exists - so a night with nothing to record writes
    nothing at all. The store's directory is kept by its own `.gitkeep`.
    """
    state_root = tmp_path / "state"
    empty = _config_registering(tmp_path)

    assert (
        cli.main(
            [
                "council-settle",
                "--date",
                A_DATE,
                "--run-id",
                A_RUN,
                "--config",
                str(empty),
                "--state-root",
                str(state_root),
            ]
        )
        == 0
    )

    assert not ledger.council_shard_outcomes_path(state_root, A_DATE).exists()
    assert (REPO_ROOT / ledger.STATE_DIRNAME / ledger.COUNCIL_DIRNAME
            / ledger.SHARD_OUTCOMES_DIRNAME / ".gitkeep").exists()


def test_no_judge_module_is_in_the_import_closure_of_a_council_verb() -> None:
    """The dictum, measured rather than argued.

    What is imported is the module every council verb's body lives in, and what
    is counted is any module under the content-similarity judge and each of the
    four stage modules that judge owns.

    Three of that judge's CONTRACTS do arrive, through `idhazh.ledger`, which is
    the one registry of CSV rows and which the tenancy protocol reads its row
    types from. That edge is the ledger's and predates this check; what is held
    here is that no judge's CODE is reachable from a council verb.

    **This is the RUN-TIME half and it is kept for one reason**: a module pulled
    in by name rather than by an import statement, which no syntax tree resolves.
    `test_council_runs_without_a_judge.py` is the static half - it reads the
    import statements, so it catches a coupling on the commit that adds it, and
    it is the one that holds the three contracts above to exactly three.
    """
    found = _judge_modules_reached(
        "idhazh.council.session", ("idhazh.similarity", *JUDGE_STAGE_MODULES)
    )

    assert found == [], f"a council verb imports {found}"


def test_the_router_no_longer_carries_a_judges_stage() -> None:
    """The verb names went with the imports, so a string cannot bring them back.

    A static import check parses imports and goes green over a verb name still
    spelled in the router's own tuple, which is how the four judge verbs
    survived the first cut. Both halves are held here.
    """
    found = _judge_modules_reached("idhazh.cli", JUDGE_STAGE_MODULES)

    assert found == [], f"the router still imports {found}"
    assert not [verb for verb in cli.STAGES if verb.startswith("judge")]
