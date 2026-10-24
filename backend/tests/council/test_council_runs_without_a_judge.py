"""Does the council run green with every judge deleted from the repository?

The static import routes are read from a fixed list of named source files.
An unlisted dependency fails before the reader opens it. A whole night then
runs against tenants this test wrote, with no judge anywhere in the call.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.contracts.council_run_record import (
    CouncilRunRecord,
    EvaluationStep,
    ShardOutcome,
)
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import night_plan, registry, run_identity, session

from . import _imports
from ._config import copy_config, write_declarations
from ._imports import imported_at_import_time, module_file, static_routes
from ._tenants import a_belated_venue, a_venue, forget, written

A_VENUE: Final = "a_judgeless_venue"

#: One tenant this file writes, and a second that moved in on different nights.
A_SLUG: Final = "a-judgeless-tenant"

ANOTHER_SLUG: Final = "another-judgeless-tenant"

A_SHA: Final = "0735031c2a9e4b8f1d6c3a5e7b9d0f2a4c6e8b1d"

#: The night the run check opens on, and the platform run id it is named after.
#: Far enough after the committed `council.first_night` that the whole repair
#: window is behind it, so a test about a union is not silently a test about the
#: window's floor.
TONIGHT: Final = "2026-09-26"

A_PLATFORM_RUN: Final = "35534060762"

#: Both the judge's declaration and the similarity implementation it routes to.
JUDGE_CODE_PACKAGES: Final = ("idhazh.content_similarity_judge", "idhazh.similarity")

#: The stage modules the content-similarity judge owns, spelled one by one. A
#: stage is named for the work it does rather than for whose loop it is in, so a
#: shared prefix would go blind to three of these four.
JUDGE_STAGE_MODULES: Final = (
    "idhazh.stages.count_verdicts",
    "idhazh.stages.judge_item_pairs",
    "idhazh.stages.pick_item_pairs",
    "idhazh.stages.set_merge_line",
)

#: Every persisted shape a judge owns, spelled one by one for the same reason.
#: Closed-world: a new judge contract joins this tuple, and until it does the
#: checks below cannot see it - so `test_every_judge_contract_named_here_exists`
#: holds the tuple against the tree.
JUDGE_CONTRACT_MODULES: Final = (
    "idhazh.contracts.content_similarity_judge_metrics",
    "idhazh.contracts.knobs.content_similarity_judge",
    "idhazh.contracts.fitted_similarity_threshold",
    "idhazh.contracts.judge_call",
    "idhazh.contracts.merge_line_holdout_score",
    "idhazh.contracts.similarity_holdout_pair",
    "idhazh.contracts.story_similarity_distribution",
    "idhazh.contracts.story_similarity_pair",
)

#: The three judge contracts a council verb still reaches, and the routes they
#: arrive on. Measured by a fresh walk on 2026-09-21, and the owner's ruling the
#: same day is that these three may cross and nothing else may.
#:
#: **Why they are here rather than cut.** Both carriers are modules the two sides
#: genuinely share. `idhazh.ledger` is the one registry of CSV rows and the
#: tenancy protocol reads its row types off it; `idhazh.contracts.knobs.placement`
#: is the knob block `app_config` composes, and `registry` loads `app_config` to
#: ask a tenant whether it can finish the night. Cutting either means moving a
#: shape every stage and the digest pipeline read, which is a row of its own -
#: priced, and not taken with this one.
#:
#: **No judge CODE is on this list and none may join it.** These are declarations
#: a judge deleted from the tree would take with it, which is what makes the
#: exception survivable: the council imports the shape, never the judge.
JUDGE_CONTRACTS_STILL_CROSSING: Final = frozenset(
    {
        "idhazh.contracts.fitted_similarity_threshold",
        "idhazh.contracts.story_similarity_distribution",
        "idhazh.contracts.story_similarity_pair",
    }
)


@pytest.fixture(scope="module")
def reached() -> set[str]:
    """Judge modules reached by the static imports in the named source inputs."""
    routes = static_routes()
    assert routes, "the reader found no imports, so it would pass on nothing"
    return {
        name
        for name in routes
        if any(name == package or name.startswith(f"{package}.") for package in JUDGE_CODE_PACKAGES)
        or name in JUDGE_STAGE_MODULES
        or name in JUDGE_CONTRACT_MODULES
    }


def test_every_judge_module_named_here_is_a_module_this_tree_has() -> None:
    """A closed-world list that has gone stale reads green over a real import.

    Every name below is spelled rather than matched by prefix, so a typo or a
    module that moved would silently drop out of the two checks that use it. This
    is what makes them fail instead.
    """
    named = (*JUDGE_CODE_PACKAGES, *JUDGE_STAGE_MODULES, *JUDGE_CONTRACT_MODULES)
    missing = [name for name in named if module_file(name) is None]

    assert not missing, f"the judge surface names modules this tree does not have: {missing}"
    assert JUDGE_CONTRACTS_STILL_CROSSING <= set(JUDGE_CONTRACT_MODULES)


def test_no_council_verb_reaches_a_judges_code(reached: set[str]) -> None:
    """The dictum: a judge deleted from the tree leaves every council verb running.

    The named source inputs cover the council's verbs and their dependencies.

    What it cannot settle: whether a real judge works. That is what each
    judge-side row's own oracle is for.
    """
    code = reached - JUDGE_CONTRACTS_STILL_CROSSING
    assert not code, (
        "a council verb reaches a judge at import time, so deleting that judge "
        f"would break the venue: {sorted(code)}"
    )


def test_this_file_names_no_judge_either() -> None:
    """The run check must not import a real judge to exercise the venue."""
    mine = imported_at_import_time(Path(__file__), "backend.tests.council.x")
    judges = [
        name
        for name in mine
        if any(name == package or name.startswith(f"{package}.") for package in JUDGE_CODE_PACKAGES)
        or name in JUDGE_STAGE_MODULES
        or name in JUDGE_CONTRACT_MODULES
    ]
    assert mine, "the reader found no imports, so it would pass on nothing"
    assert not judges, f"this file imports {judges}"


def test_an_unlisted_dependency_fails_before_its_source_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "backend" / "idhazh" / "council"
    package.mkdir(parents=True)
    (package / "session.py").write_text("import idhazh.unlisted\n", encoding="ascii")
    (package.parent / "unlisted.py").write_text("this is not valid Python!\n", encoding="ascii")
    monkeypatch.setattr(_imports, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(_imports, "MODULE_NAMES", ("idhazh.council.session",))

    with pytest.raises(AssertionError, match=r"idhazh\.unlisted, outside the named import inputs"):
        static_routes()


def test_a_named_transitive_dependency_keeps_its_import_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "backend" / "idhazh" / "council"
    package.mkdir(parents=True)
    (package / "session.py").write_text("import idhazh.shared\n", encoding="ascii")
    (package.parent / "shared.py").write_text("import idhazh.contract\n", encoding="ascii")
    (package.parent / "contract.py").write_text(
        "def deferred():\n    import idhazh.not_loaded\n", encoding="ascii"
    )
    monkeypatch.setattr(_imports, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        _imports, "MODULE_NAMES", ("idhazh.council.session", "idhazh.shared", "idhazh.contract")
    )

    routes = static_routes()

    assert routes["idhazh.contract"] == (
        "idhazh.council.session",
        "idhazh.shared",
        "idhazh.contract",
    )
    assert set(routes) == set(_imports.MODULE_NAMES)


def test_the_judge_contracts_that_still_cross_cannot_grow(reached: set[str]) -> None:
    """The exception is self-limiting, or it is an invitation.

    Three judge contracts arrive through two modules both sides share, and the
    owner ruled on 2026-09-21 that those three may cross while the routes are
    priced. A list with no upper edge is one the next person extends, so what is
    held here is the exact set: a fourth fails, and so does a third that was cut
    without the list being cut with it.
    """
    crossing = reached & set(JUDGE_CONTRACT_MODULES)

    assert crossing == set(JUDGE_CONTRACTS_STILL_CROSSING), (
        "the judge contracts a council verb reaches are no longer the three the "
        "owner agreed to. Added: "
        f"{sorted(crossing - JUDGE_CONTRACTS_STILL_CROSSING)}; gone: "
        f"{sorted(JUDGE_CONTRACTS_STILL_CROSSING - crossing)}. A new one needs a "
        "ruling, and one that left needs this list shortened in the same commit."
    )


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable tenant package on the import path, and a scratch root off the tree.

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


def _council(
    root: Path,
    *slugs: str,
    repair_dates: int = 1,
    first_night: str | None = None,
    repair_window_nights: int | None = None,
    shards: int | None = None,
) -> CouncilConfig:
    """Load this test's registered tenants and any authored planning controls."""
    target = copy_config(root)
    write_declarations(target, tuple(slugs))
    path = target / "llm_council.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["judge_names"] = list(slugs)
    raw["repair_dates_a_night"] = repair_dates
    for name, value in (
        ("first_night", first_night),
        ("repair_window_nights", repair_window_nights),
        ("shards", shards),
    ):
        if value is not None:
            raw[name] = value
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8", newline="\n")
    council = config.load_council(target)
    return council


def _the_nights_record(state_root: Path, date: str) -> list[CouncilRunRecord]:
    """The council's current rows, read back through the ledger door."""
    return ledger.load_days(
        state_root, LedgerName.COUNCIL_RUN_RECORDS, [date], model=CouncilRunRecord
    )


def test_a_whole_night_runs_with_nobody_registered(venue: Path) -> None:
    """The empty case IS the test, and every step of it still runs.

    A venue that only works once somebody has moved in is not a venue. So with
    zero tenants: the name is minted, the guest list resolves, the plan names
    tonight, prepare and settle are no-ops that return cleanly, and the night
    leaves no phantom raw file behind. Six steps, none of them skipped.
    """
    council = _council(venue)
    state_root = venue / "state"

    run_id = run_identity.council_run_id(opened_on=TONIGHT, platform_run_id=A_PLATFORM_RUN)
    hosted = registry.tenants(council.running())
    planned = night_plan.plan_the_night(council, tonight=TONIGHT, hosted=hosted)
    prepared = session.prepare(council, date=TONIGHT, run_id=run_id)
    settled = session.settle(
        council, date=TONIGHT, run_id=run_id, state_dir=state_root, commit_sha=A_SHA
    )

    assert run_id == f"{TONIGHT}-{A_PLATFORM_RUN}"
    assert hosted == ()
    assert planned.judges == (), "a night with nobody registered selects no judge"
    assert prepared == ()
    assert settled == ()
    assert not ledger.raw_root(state_root, LedgerName.COUNCIL_RUN_RECORDS).exists()


def test_two_tenants_union_their_nights_and_keep_their_own_width(venue: Path) -> None:
    """One caller says nothing about a union, an order, or a second width.

    The two are behind on overlapping nights and shard to different widths, so
    what is held is that the plan is the UNION rather than either list, that it
    reads newest first, and that each tenant is sized by its own `shard_count`
    rather than by whichever one the venue asked first.
    """
    a_belated_venue(
        venue, package=A_VENUE, slug=A_SLUG, behind_on=("2026-09-25",), shard_count=2
    )
    a_belated_venue(
        venue,
        package=A_VENUE,
        slug=ANOTHER_SLUG,
        behind_on=("2026-09-25", "2026-09-24", "2026-09-23"),
        shard_count=3,
    )
    council = _council(
        venue,
        A_SLUG,
        ANOTHER_SLUG,
        repair_dates=3,
        first_night="2026-09-24",
        repair_window_nights=6,
        shards=5,
    )
    assert (council.first_night, council.repair_window_nights, council.shards) == (
        "2026-09-24",
        6,
        5,
    )

    hosted = registry.tenants(council.running())
    planned = night_plan.plan_the_night(council, tonight=TONIGHT, hosted=hosted)

    assert [host.judge_id for host in hosted] == [A_SLUG, ANOTHER_SLUG]
    assert {judge.tenant: judge.dates for judge in planned.judges} == {
        A_SLUG: (TONIGHT, "2026-09-25"),
        ANOTHER_SLUG: (TONIGHT, "2026-09-25", "2026-09-24"),
    }
    assert [session.shard_width(council, host) for host in hosted] == [2, 3]


def test_the_venue_runs_a_shard_under_its_own_clock_and_files_the_row(venue: Path) -> None:
    """The rest of the night, driven on a tenant that judges nothing at all.

    `PaperTenant` computes every answer it gives and records what it was handed;
    nothing here asserts that it judged, because judging is not what the venue
    does. What is asserted is that the venue handed it a deadline it never asked
    for, and filed its own row on the way out.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={A_SLUG: (2, ("state/a-judgeless-ledger",))},
        poisoned_neighbour="a-broken-unrequested-tenant",
    )
    council = _council(venue, A_SLUG, shards=3)
    state_root = venue / "state"
    run_id = run_identity.council_run_id(opened_on=TONIGHT, platform_run_id=A_PLATFORM_RUN)
    opened = time.monotonic()

    hosted = registry.tenants(council.running())
    assert (
        night_plan.plan_the_night(council, tonight=TONIGHT, hosted=hosted).judges[0].dates[0]
        == TONIGHT
    )
    session.prepare(council, date=TONIGHT, run_id=run_id)
    for shard in range(2):
        result = session.run_shard(
            council,
            slug=A_SLUG,
            date=TONIGHT,
            run_id=run_id,
            shard=shard,
            shards=2,
            started=opened,
        )
        assert result.outcome is ShardOutcome.COMPLETED
    session.settle(council, date=TONIGHT, run_id=run_id, state_dir=state_root, commit_sha=A_SHA)

    handed = written(A_VENUE, A_SLUG).TENANT.handed
    filed = _the_nights_record(state_root, TONIGHT)

    assert len(handed) == 2, "each shard is handed a deadline of its own"
    assert all(instant > opened for instant in handed), "the clock is the council's"
    assert {row.judge_id for row in filed} == {A_SLUG}
    assert sorted((row.evaluation_step, row.work_part_index) for row in filed) == sorted(
        [
            (EvaluationStep.COMBINE_JUDGE_RESULTS, None),
            (EvaluationStep.SELECT_JUDGE_WORK, None),
            (EvaluationStep.EVALUATE_WORK_PART, 0),
            (EvaluationStep.EVALUATE_WORK_PART, 1),
        ]
    ), "two parts, plus the selection and the settlement"
