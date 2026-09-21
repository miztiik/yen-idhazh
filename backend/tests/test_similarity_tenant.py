"""Does this judge present itself to the council the way the venue asks?

The registration side and nothing about what the judge decides: the slug the
config names, the object that answers to it, and the members the venue calls.
Every one of them is asked of the committed config, because a tenant registered
in a temporary file is a tenant the nightly run does not have.

Nothing here opens a store or a published day.
"""

from __future__ import annotations

from typing import Final

import pytest
from conftest import CONFIG_DIR

from idhazh import config, ledger
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.council import registry
from idhazh.council.tenancy import Tenant
from idhazh.similarity import tenant

#: A night the tests ask this judge about. Any date inside a window would do -
#: what is asked is which of them come back, never which one it is.
A_NIGHT: Final = "2026-09-20"

#: The seven members the venue calls, read off the protocol rather than listed,
#: so an eighth is checked here the day it is declared.
PROTOCOL_MEMBERS: Final = tuple(
    sorted(name for name in vars(Tenant) if not name.startswith("_"))
)


def test_the_committed_config_registers_this_judge() -> None:
    """The one line that decides whether the nightly run judges anything at all.

    Everything else can land, every gate can pass, and a config naming no slug
    still runs a night that hosts nobody: the venue plans tonight, fans out to no
    cell, and commits nothing.
    """
    registered = config.load(CONFIG_DIR).app.council.tenants

    assert tenant.JUDGE_ID in registered, (
        f"config/idhazh.json registers {list(registered)} and not '{tenant.JUDGE_ID}', "
        "so the council hosts nobody and every night judges nothing"
    )


def test_the_slug_the_council_reads_leads_back_to_this_module() -> None:
    """The search is what can go wrong, so the search is what is asked.

    A slug nothing declares is refused by name, and a slug that resolves to
    another package's tenant would run somebody else's work under this judge's
    address.
    """
    assert registry.tenant(tenant.JUDGE_ID) is tenant.TENANT
    assert getattr(tenant, registry.TENANT_ATTRIBUTE) is tenant.TENANT


def test_this_judge_gets_its_say_on_a_night_it_could_not_finish() -> None:
    """The check is read off the module, so a module that stopped binding it is silent.

    A draw a unit cannot finish is a job the platform kills with nothing
    uploaded, and this is the one point before the matrix exists where saying so
    costs no runner.
    """
    check = getattr(tenant, registry.TENANT_FIT_CHECK, None)

    assert callable(check), (
        f"{tenant.__name__} binds no {registry.TENANT_FIT_CHECK}, so the council asks "
        "this judge nothing about the night ahead and a draw that cannot finish "
        "reaches a runner"
    )
    check(config.load(CONFIG_DIR).app)


@pytest.mark.parametrize("member", PROTOCOL_MEMBERS)
def test_the_tenant_answers_every_member_the_venue_calls(member: str) -> None:
    """A member the venue calls and this object does not have fails at the call site.

    Structural typing is checked where this module is type-checked; what this
    adds is the same question asked of the object the registry really returns,
    which is how a member lost in a rename is caught without a run.
    """
    assert hasattr(tenant.TENANT, member), (
        f"the council calls {member}() on every tenant it hosts and this one has no "
        "such member, so the night dies on the first unit of this judge's work"
    )


def test_the_slug_is_the_word_this_judges_stores_are_addressed_by() -> None:
    """Three spellings of one word, and a drift between any two loses a row.

    The slug names the directory each unit uploads into, the column every
    instrument row carries, and the prefix under `state/` the whole judge files
    beneath. A collecting job looking in one place for what a unit wrote to
    another finds nothing and says nothing.
    """
    on_the_row = ContentSimilarityJudgeMetrics.model_fields["judge_id"].default

    assert tenant.JUDGE_ID == ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME
    assert tenant.JUDGE_ID == on_the_row
    assert tenant.TENANT.judge_id == tenant.JUDGE_ID


def test_this_judge_splits_its_work_the_way_its_draw_is_dealt() -> None:
    """The selection deals every pair a shard number at the venue's own width.

    A tenant answering anything narrower here leaves the difference unread, with
    every unit reporting success and the day counted as though the missing pairs
    had never been drawn.
    """
    assert tenant.TENANT.shard_count == config.load(CONFIG_DIR).app.council.shards


def test_the_prefix_this_judge_stages_covers_the_store_every_unit_writes() -> None:
    """One prefix, so a store this judge gains later is staged the day it is written.

    A list of the stores as they stand would commit the day a new one is added
    and drop it on every night until somebody noticed.
    """
    under_the_prefix = ledger.content_similarity_judge_metrics_relpath(A_NIGHT)

    assert tenant.TENANT.committed_paths == (
        f"{ledger.STATE_DIRNAME}/{ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME}",
    )
    assert under_the_prefix.startswith(tenant.TENANT.committed_paths[0] + "/")


def test_this_judge_names_no_night_the_council_did_not_ask_about() -> None:
    """A date from outside the window is a job the venue never priced.

    It would reach a runner as silently as a date that was asked for, so the
    planning job refuses one by name - which makes an answer of nothing the one
    that costs a night nothing.
    """
    answered = tenant.TENANT.nights_outstanding(window=(A_NIGHT,))

    assert set(answered) <= {A_NIGHT}
