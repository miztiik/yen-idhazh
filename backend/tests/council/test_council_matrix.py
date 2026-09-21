"""What does a night fan out to, and what will it commit?

The fan-out is read off the tenants the config registers, so every tenant here
is written by the test that uses it. Nothing in this file imports
`idhazh.similarity` or any judge contract.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.council import registry
from utilities import council_matrix

from ._tenants import a_venue, forget

A_VENUE = "a_paper_venue"

A_DATE = "2026-09-20"

ANOTHER_DATE = "2026-09-19"


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable package on the import path, pointed at by the registry."""
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", A_VENUE)
    forget(A_VENUE)
    yield tmp_path
    forget(A_VENUE)


def _config_registering(root: Path, *, slugs: tuple[str, ...], shards: int | None = None) -> Path:
    """A whole `config/` in a temp directory, with those slugs registered.

    The whole tree, because `config.load` reads five files and cross-checks two
    of them - a config with one file written by hand cannot load for a reason
    the test did not mean to ask about.
    """
    target = root / "config"
    shutil.copytree(CONFIG_DIR, target)
    raw = json.loads(read_text(target / "idhazh.json"))
    raw["council"]["tenants"] = list(slugs)
    if shards is not None:
        raw["council"]["shards"] = shards
    (target / "idhazh.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8", newline="\n"
    )
    return target


def _emitted(
    capsys: pytest.CaptureFixture[str], *, config_root: Path, dates: tuple[str, ...]
) -> dict[str, str]:
    """The key-value lines the utility prints, as a mapping."""
    argv = ["--config-root", str(config_root)]
    for date in dates:
        argv += ["--date", date]
    assert council_matrix.main(argv) == 0
    return dict(
        line.split("=", 1) for line in capsys.readouterr().out.splitlines() if line
    )


def test_a_night_with_no_tenant_fans_out_to_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The committed config's own night, and the one the venue has to survive.

    An empty matrix, no path to stage, and a parallelism Actions can still read -
    the judging job's guard is what stops the empty list reaching the strategy
    evaluator, and it cannot be asked of a job that was never built.
    """
    emitted = _emitted(capsys, config_root=CONFIG_DIR, dates=(A_DATE,))

    assert json.loads(emitted["matrix"]) == []
    assert json.loads(emitted["dates"]) == [A_DATE]
    assert emitted["committed_paths"] == ""
    assert int(emitted["max_parallel"]) >= 1


def test_a_cell_carries_the_tenant_the_date_the_shard_and_that_tenants_width(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Four values, on the cell, because only the cell knows which tenant it is."""
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (2, ("state/paper",))})
    config_root = _config_registering(venue, slugs=("a-paper-tenant",))

    emitted = _emitted(capsys, config_root=config_root, dates=(A_DATE,))

    assert json.loads(emitted["matrix"]) == [
        {"tenant": "a-paper-tenant", "date": A_DATE, "shard": 0, "shards": 2},
        {"tenant": "a-paper-tenant", "date": A_DATE, "shard": 1, "shards": 2},
    ]
    assert emitted["committed_paths"].split() == [
        council_matrix.COUNCIL_STORE,
        "state/paper",
    ], "the venue's own record is staged beside whatever the tenant named"


def test_a_tenant_narrows_the_venues_width_and_cannot_widen_it(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The venue's width is a ceiling and a default, never an instruction.

    A tenant that runs no model answers 1 and takes one job: four jobs for work
    that runs no model would pay four weights restores for nothing. A tenant
    that asked for more than the venue allows gets the venue's number, because
    the ceiling is what a matrix leg costs rather than what a tenant prefers.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={"a-narrow-tenant": (1, ()), "a-greedy-tenant": (8, ())},
    )
    config_root = _config_registering(
        venue, slugs=("a-narrow-tenant", "a-greedy-tenant"), shards=2
    )

    cells = json.loads(
        _emitted(capsys, config_root=config_root, dates=(A_DATE,))["matrix"]
    )

    widths = {cell["tenant"]: cell["shards"] for cell in cells}
    assert widths == {"a-narrow-tenant": 1, "a-greedy-tenant": 2}
    assert [cell["tenant"] for cell in cells] == [
        "a-narrow-tenant",
        "a-greedy-tenant",
        "a-greedy-tenant",
    ]


def test_a_second_date_adds_cells_rather_than_a_third_axis(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repair night is more cells, not a wider tenant.

    The list is emitted flat so a date joining it changes nothing about how a
    tenant's own work is split.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (2, ())})
    config_root = _config_registering(venue, slugs=("a-paper-tenant",))

    emitted = _emitted(capsys, config_root=config_root, dates=(A_DATE, ANOTHER_DATE))
    cells = json.loads(emitted["matrix"])

    assert json.loads(emitted["dates"]) == [A_DATE, ANOTHER_DATE]
    assert len(cells) == 4
    assert sorted({cell["date"] for cell in cells}) == sorted((A_DATE, ANOTHER_DATE))
    assert {cell["shards"] for cell in cells} == {2}


def test_the_wave_is_the_cell_count_under_the_platforms_own_ceiling(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Past the ceiling a job waits its turn, so asking for more buys nothing.

    Below it, the wave is every cell at once: bound to a tenant's shard width
    instead, a night of many cells would run in waves and finish across the
    schedules either side of it.
    """
    slugs = {"tenant-one": (8, ()), "tenant-two": (8, ()), "tenant-three": (8, ())}
    a_venue(venue, package=A_VENUE, slugs=slugs)
    config_root = _config_registering(venue, slugs=tuple(slugs), shards=8)

    emitted = _emitted(capsys, config_root=config_root, dates=(A_DATE,))

    assert len(json.loads(emitted["matrix"])) == 24
    assert int(emitted["max_parallel"]) == council_matrix.PLATFORM_JOB_CEILING


def test_the_staged_paths_are_every_tenants_and_each_one_once(
    venue: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path two tenants both write is staged once.

    `git add` takes a path twice without complaint, so the duplicate costs
    nothing on the runner - what it costs is a reader of the commit step's
    arguments, who has to work out whether the repeat meant something.

    The venue's own store leads the list. It is not a tenant's, and it is staged
    on any night that hosts one, because the council records every unit it ran
    whatever the tenant inside it wrote.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={
            "tenant-one": (1, ("state/paper", "state/shared")),
            "tenant-two": (1, ("state/shared", "state/other")),
        },
    )
    config_root = _config_registering(venue, slugs=("tenant-one", "tenant-two"))

    emitted = _emitted(capsys, config_root=config_root, dates=(A_DATE,))

    assert emitted["committed_paths"].split() == [
        council_matrix.COUNCIL_STORE,
        "state/paper",
        "state/shared",
        "state/other",
    ]


def test_a_date_named_twice_is_judged_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A repeated date would run every tenant's work over that date twice.

    Once in the cells and once in the collecting job's loop, which would ask a
    tenant to settle a date it had already settled.
    """
    emitted = _emitted(capsys, config_root=CONFIG_DIR, dates=(A_DATE, A_DATE))

    assert json.loads(emitted["dates"]) == [A_DATE]
