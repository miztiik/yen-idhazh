"""Does the council find the tenants it was told to host, and refuse the ones it cannot?

Every tenant here is written by the test that uses it, so the search is gated
with no judge in the repository and without a judge's test module. Nothing in
this file imports `idhazh.similarity` or any judge contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.council import registry

from ._tenants import a_venue, forget, written

#: The package each test writes its tenants into. One name, so a test that
#: forgets to drop it fails the next test loudly rather than quietly resolving.
A_VENUE = "a_paper_venue"


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A writable package on the import path, pointed at by the registry."""
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", A_VENUE)
    forget(A_VENUE)
    yield tmp_path
    forget(A_VENUE)


def test_a_venue_with_no_slugs_hosts_nobody() -> None:
    """An empty list is a legal night, and it is the one the repository ships.

    Every step of a council run still happens; nothing is judged. A resolver
    that treated an empty list as a mistake would make a repository with no
    judge in it unable to run its own workflow at all.
    """
    assert registry.tenants(()) == ()


def test_every_slug_the_committed_config_registers_resolves() -> None:
    """Read here rather than named: what matters is that the two sides agree.

    A tenant registers itself by adding a slug to this list, and a slug nothing
    declares is refused by name. Caught here, a typo in that list costs a test
    run; uncaught, it costs a whole night before anything says so.

    The list is not asserted to be any particular length, and no slug in it is
    spelled here. A council test that named a judge would be the roster this
    whole design exists to remove.
    """
    council = config.load(CONFIG_DIR).app.council

    assert [host.judge_id for host in registry.tenants(council.tenants)] == list(
        council.tenants
    )


def test_a_slug_resolves_to_the_module_that_declares_it(venue: Path) -> None:
    """The slug is the whole of what the config carries, and the module answers to it.

    Nothing maps the one to the other in this repository's source. A map would
    make adding a judge a code change, and it would be a roster of who may exist
    wearing a different hat.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (2, ("state/paper",))})

    found = registry.tenant("a-paper-tenant")

    assert found.judge_id == "a-paper-tenant"
    assert found.shard_count == 2
    assert found.committed_paths == ("state/paper",)
    assert found is written(A_VENUE, "a-paper-tenant").TENANT


def test_the_venue_hosts_its_tenants_in_the_order_the_config_names_them(venue: Path) -> None:
    """A venue that ran its tenants in an order it never declared could not be re-run.

    The order is the config's, not the directory listing's, which is why the
    slugs below resolve in the reverse of the order they were written.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={"first-tenant": (1, ()), "second-tenant": (1, ())},
    )

    hosted = registry.tenants(("second-tenant", "first-tenant"))

    assert [one.judge_id for one in hosted] == ["second-tenant", "first-tenant"]


def test_a_slug_nothing_declares_is_refused_by_name(venue: Path) -> None:
    """Refused, never skipped.

    A night that dropped an unrecognised slug would run every step, report
    nothing wrong and judge less than the config asked for - which is exactly
    what a typo in a slug list produces, and it would be invisible.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (1, ())})

    with pytest.raises(SystemExit) as refused:
        registry.tenant("a-paper-tenent")

    said = str(refused.value)
    assert "a-paper-tenent" in said, "the refusal has to name the slug that was not found"
    assert "a-paper-tenant" in said, "and what it did find, or a typo reads as a missing file"


def test_a_package_that_declares_no_tenant_is_never_imported(venue: Path) -> None:
    """The search reads the directory listing, and imports only what it is going to ask.

    The neighbour below raises on import. A search that imported every package
    to ask its name would take the whole run down with it, and one judge's
    broken import would hide every other judge's slug.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={"a-paper-tenant": (1, ())},
        quiet_neighbour="a_package_with_no_tenant",
    )

    assert registry.tenant("a-paper-tenant").judge_id == "a-paper-tenant"


def test_a_tenant_module_that_binds_nothing_says_so(venue: Path) -> None:
    """A module in the right place with the wrong contents fails where it can be read.

    Without this the search walks past it and reports the slug as unknown, which
    sends a reader looking for a missing directory rather than at the file that
    is already there.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (1, ())})
    (venue / A_VENUE / "a_paper_tenant" / "tenant.py").write_text(
        "NOT_A_TENANT = object()\n", encoding="utf-8", newline="\n"
    )

    with pytest.raises(SystemExit, match=registry.TENANT_ATTRIBUTE):
        registry.tenant("a-paper-tenant")


def _that_refuses(venue: Path, slug: str) -> None:
    """Give one written tenant a real check of the night it is being asked to run.

    Nothing is stubbed: the check reads the config it is handed and raises on
    what it read, which is what a judge weighing its own draw against the
    venue's clock does.
    """
    module = venue / A_VENUE / slug.replace("-", "_") / "tenant.py"
    module.write_text(
        module.read_text(encoding="utf-8")
        + "\n\n"
        + "def refuse_a_night_this_tenant_cannot_finish(app):\n"
        + '    raise ValueError(f"{TENANT.judge_id} needs more than '
        + '{app.council.shard_timeout_minutes} minutes")\n',
        encoding="utf-8",
        newline="\n",
    )


def test_a_tenant_refuses_the_night_when_the_council_resolves_it(venue: Path) -> None:
    """Resolving is where a tenant gets to say the work will not fit.

    The planning job resolves every registered slug to build its matrix, so a
    refusal here lands before any job has restored a model's weights. Asserting
    it merely happens "before a model call" would also be true of a point after
    a cache restore and a server start, which is most of what a wasted job
    costs.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (1, ())})
    _that_refuses(venue, "a-paper-tenant")

    with pytest.raises(ValueError, match="a-paper-tenant"):
        registry.tenant("a-paper-tenant", app=AppConfig.model_validate({}))


def test_the_check_reads_the_config_the_caller_named(venue: Path) -> None:
    """The venue hands its own clocks over and reads nothing back out of them.

    The tenant answers against the config it was given, so what the refusal says
    tracks the config in force rather than a number the venue kept.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (1, ())})
    _that_refuses(venue, "a-paper-tenant")
    app = AppConfig.model_validate({"council": {"shard_timeout_minutes": 199}})

    with pytest.raises(ValueError, match=str(app.council.shard_timeout_minutes)):
        registry.tenant("a-paper-tenant", app=app)


def test_a_tenant_nobody_asked_for_cannot_refuse_the_night(venue: Path) -> None:
    """The search imports every declaring module until one matches, and only the match is asked.

    Without this a tenant the config never registered could stop a night it is
    not in - and the search would have to import it either way, so the guard has
    to be on who is asked rather than on who is imported.
    """
    a_venue(
        venue,
        package=A_VENUE,
        slugs={"a-paper-tenant": (1, ()), "z-paper-tenant": (1, ())},
    )
    _that_refuses(venue, "a-paper-tenant")

    assert registry.tenant("z-paper-tenant", app=AppConfig.model_validate({})).judge_id == (
        "z-paper-tenant"
    )


def test_a_tenant_that_declares_no_check_is_asked_nothing(venue: Path) -> None:
    """A tenant whose work has no cost to weigh against the clock declares nothing.

    Optional rather than an eighth member of the protocol: the protocol is what
    a tenant presents while it runs, and this is asked before it does.
    """
    a_venue(venue, package=A_VENUE, slugs={"a-paper-tenant": (1, ())})

    assert registry.tenant("a-paper-tenant", app=AppConfig.model_validate({})).judge_id == (
        "a-paper-tenant"
    )
