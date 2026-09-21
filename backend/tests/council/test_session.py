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

from idhazh import cli, config
from idhazh.council import registry, session
from idhazh.council.deadline import SECONDS_A_MINUTE

from ._tenants import a_venue, forget, written

A_VENUE = "a_paper_venue"

A_SLUG = "a-paper-tenant"

A_DATE = "2026-09-20"

A_RUN = "2026-09-21-35534060762"

#: Every council verb the router carries. Named here so a verb added without a
#: zero-tenant arm fails this file rather than shipping untested.
COUNCIL_VERBS = ("council-prepare", "council-settle")


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable package on the import path, pointed at by the registry."""
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", A_VENUE)
    forget(A_VENUE)
    yield tmp_path
    forget(A_VENUE)


def _config_registering(root: Path, slug: str) -> Path:
    """A whole `config/` in a temp directory, with one slug registered."""
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    raw = json.loads(read_text(target / "idhazh.json"))
    raw["council"]["tenants"] = [slug]
    (target / "idhazh.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8", newline="\n"
    )
    return target


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
def test_a_council_verb_runs_a_night_that_hosts_nobody(verb: str) -> None:
    """The zero-tenant arm, against the config the repository commits.

    A venue with no tenants judges nothing, and that is correct. What it must
    not do is fail: every step of the night still runs, which is what makes the
    council buildable and testable with no judge in the repository.
    """
    assert cli.main([verb, "--date", A_DATE, "--run-id", A_RUN]) == 0


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
    session.settle(council, date=A_DATE, run_id=A_RUN)

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


def test_no_judge_module_is_in_the_import_closure_of_a_council_verb() -> None:
    """The dictum, measured rather than argued.

    What is imported is the module every council verb's body lives in, and what
    is counted is any module under the content-similarity judge or any stage
    named for one.

    Three of that judge's CONTRACTS do arrive, through `idhazh.ledger`, which is
    the one registry of CSV rows and which the tenancy protocol reads its row
    types from. That edge is the ledger's and predates this check; what is held
    here is that no judge's CODE is reachable from a council verb.
    """
    found = _judge_modules_reached(
        "idhazh.council.session", ("idhazh.similarity", "idhazh.stages.judge")
    )

    assert found == [], f"a council verb imports {found}"


def test_the_router_no_longer_carries_a_judges_stage() -> None:
    """The verb names went with the imports, so a string cannot bring them back.

    A static import check parses imports and goes green over a verb name still
    spelled in the router's own tuple, which is how the four judge verbs
    survived the first cut. Both halves are held here.
    """
    found = _judge_modules_reached("idhazh.cli", ("idhazh.stages.judge",))

    assert found == [], f"the router still imports {found}"
    assert not [verb for verb in cli.STAGES if verb.startswith("judge")]
