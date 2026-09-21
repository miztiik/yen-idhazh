"""Which dates does a night plan, and what does it do with nobody in the room?

The plan is the council's, so every tenant here is written by the test that uses
it and nothing in this file imports `idhazh.similarity` or any judge contract.

Every arm runs on a config the test wrote. The committed one registers a judge,
and a judge answers out of a store the pipeline appends to every night, so a
plan run against `config/` would be asserting what the archive holds rather than
what the planner does (CLAUDE.md section 13).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council import night_plan, registry

from ._tenants import a_belated_venue, forget

A_VENUE = "a_belated_venue_package"

#: The night under test, and the two before it. `TONIGHT` is what the planning
#: job decided; the other two are inside the window it asks about.
TONIGHT = "2026-09-26"

LAST_NIGHT = "2026-09-25"

THE_NIGHT_BEFORE = "2026-09-24"


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable package on the import path, pointed at by the registry."""
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", A_VENUE)
    forget(A_VENUE)
    yield tmp_path
    forget(A_VENUE)


def _config_registering(root: Path, *, slugs: tuple[str, ...], **council: object) -> Path:
    """A whole `config/` in a temp directory, with those slugs registered.

    The whole tree, because `config.load` reads five files and cross-checks two
    of them - a config with one file written by hand cannot load for a reason
    the test did not mean to ask about.
    """
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    raw = json.loads(read_text(target / "idhazh.json"))
    raw["council"]["tenants"] = list(slugs)
    raw["council"].update(council)
    (target / "idhazh.json").write_text(json.dumps(raw, indent=2), encoding="utf-8", newline="\n")
    return target


def _planned(capsys: pytest.CaptureFixture[str], argv: list[str]) -> list[str]:
    """The dates the planner prints, read back off its one key-value line."""
    assert night_plan.main(argv) == 0
    printed = dict(
        line.split("=", 1) for line in capsys.readouterr().out.splitlines() if line
    )
    return list(json.loads(printed["dates"]))


def test_a_night_with_no_tenant_registered_plans_tonight_and_nothing_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The night the venue has to survive: nobody to ask, and a plan all the same.

    The council asks and does not look, so with nobody to ask the union is empty
    - and an empty union is a plan of one date rather than a plan of none. A
    night that planned nothing would leave the judging job with no matrix, the
    settle with nothing to loop, and no way to tell that apart from a failure.
    """
    config_root = _config_registering(tmp_path, slugs=())

    planned = _planned(capsys, ["--config-root", str(config_root), "--tonight", TONIGHT])

    assert planned == [TONIGHT]


def test_the_plan_is_the_union_of_what_the_tenants_owe_newest_first(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two tenants, two different answers, one list - and never the intersection.

    One tenant behind on a night is a night with a gap in it, whatever the other
    one managed. Raised to two repairs so both answers fit, which is what makes
    this a union rather than a cap doing the work.
    """
    a_belated_venue(venue, package=A_VENUE, slug="one-judge", behind_on=(LAST_NIGHT,))
    a_belated_venue(
        venue,
        package=A_VENUE,
        slug="another-judge",
        behind_on=(LAST_NIGHT, THE_NIGHT_BEFORE),
    )
    config_root = _config_registering(
        venue, slugs=("one-judge", "another-judge"), repair_dates_a_night=2
    )

    planned = _planned(capsys, ["--config-root", str(config_root), "--tonight", TONIGHT])

    assert planned == [TONIGHT, LAST_NIGHT, THE_NIGHT_BEFORE]


def test_the_cap_cuts_the_oldest_and_never_tonight(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One repair a night, so the newest gap is the one this night closes.

    Newest first, because a date that can never succeed then holds the ones
    behind it out only until the window slides past it. Oldest first, that one
    date would keep every newer date waiting for as long as it stayed in range.
    """
    a_belated_venue(
        venue,
        package=A_VENUE,
        slug="one-judge",
        behind_on=(LAST_NIGHT, THE_NIGHT_BEFORE),
    )
    config_root = _config_registering(venue, slugs=("one-judge",), repair_dates_a_night=1)

    planned = _planned(capsys, ["--config-root", str(config_root), "--tonight", TONIGHT])

    assert planned == [TONIGHT, LAST_NIGHT]


def test_the_window_is_the_only_thing_a_tenant_is_handed() -> None:
    """The read is bounded by the window the council asked about (Guardrail #12).

    Its length is a knob and its far end is the night before tonight, so the
    cost of asking does not rise as the store fills up. Tonight is not in it: a
    tenant is not behind on a night nothing has judged yet, and one that named
    it would spend a repair slot on the date the night is already for.
    """
    council = CouncilConfig(first_night="2026-01-01", repair_window_nights=3)

    window = night_plan.window_before(council, tonight=TONIGHT)

    assert window == ("2026-09-23", THE_NIGHT_BEFORE, LAST_NIGHT)
    assert TONIGHT not in window
    assert len(window) == council.repair_window_nights


def test_the_window_stops_at_the_councils_first_night() -> None:
    """Before it, a date carries no verdict because nothing was judging.

    Without the floor the first run names every published day it can reach as
    outstanding, and nothing can tell "this night died" from "the council did
    not exist yet".
    """
    council = CouncilConfig(first_night=LAST_NIGHT, repair_window_nights=30)

    assert night_plan.window_before(council, tonight=TONIGHT) == (LAST_NIGHT,)
    assert night_plan.window_before(council, tonight=LAST_NIGHT) == ()


def test_a_tenant_that_names_a_night_nobody_asked_about_is_refused_by_name(
    venue: Path,
) -> None:
    """The council prices the window, so a date from outside one is unbudgeted work.

    Refused rather than dropped: a date this planner accepts becomes a job, an
    artifact name and a store address, and the run finds out about two hours of
    model time later.
    """
    a_belated_venue(
        venue,
        package=A_VENUE,
        slug="one-judge",
        behind_on=(LAST_NIGHT,),
        unasked=("2019-04-01",),
    )
    config_root = _config_registering(venue, slugs=("one-judge",))

    with pytest.raises(SystemExit) as refusal:
        night_plan.main(["--config-root", str(config_root), "--tonight", TONIGHT])

    assert "'one-judge' says it is behind on 2019-04-01" in str(refusal.value)


def test_a_dispatched_date_replaces_the_plan_and_asks_nobody(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A person naming a date is asserting something the plan cannot know.

    So no tenant is asked and no older night rides along - not even one every
    tenant says it owes.
    """
    a_belated_venue(
        venue,
        package=A_VENUE,
        slug="one-judge",
        behind_on=(LAST_NIGHT, THE_NIGHT_BEFORE),
    )
    config_root = _config_registering(venue, slugs=("one-judge",))

    planned = _planned(
        capsys,
        [
            "--config-root",
            str(config_root),
            "--tonight",
            TONIGHT,
            "--dispatched",
            THE_NIGHT_BEFORE,
        ],
    )

    assert planned == [THE_NIGHT_BEFORE]


@pytest.mark.parametrize("given", ["2026-13-45", "yesterday", "2026-09-26T22:00", ""])
def test_a_date_no_contract_accepts_is_refused_before_it_addresses_anything(
    given: str,
) -> None:
    """A typo files rows at an address no reader ever looks at, silently.

    `2026-13-45` is the one the shared `DateStamp` lets through - its pattern
    counts digits and bounds neither the month nor the day - so the calendar is
    checked here too. The empty string is the other one that matters: it reads
    as "no date given" everywhere downstream, and `--tonight` has no default to
    fall back on.
    """
    with pytest.raises(SystemExit) as refusal:
        night_plan.a_date(given, what="--tonight")

    assert "--tonight must be a YYYY-MM-DD date" in str(refusal.value)
