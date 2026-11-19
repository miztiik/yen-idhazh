"""Does this judge present itself to the council the way the venue asks?

The registration side, and which nights it says it is behind on: the slug the
config names, the object that answers to it, the members the venue calls, and
the nights with no filed pair. Every one of them is asked of the committed
config, because a tenant registered in a temporary file is a tenant the nightly
run does not have.

Nothing here opens a published day. The ledgers it asks about are built by the
test that asks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR

from idhazh import config, ledger
from idhazh.content_similarity_judge import tenant
from idhazh.contracts.base import ServerJob, derive_text_digest, derive_url_key
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.council_invocation import ScheduleRequest
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import PairBucket, StorySimilarityPairVerdict
from idhazh.council import registry
from idhazh.council.tenancy import Tenant
from idhazh.ledger import staging

#: A night the tests ask this judge about. Any date inside a window would do -
#: what is asked is which of them come back, never which one it is.
A_NIGHT: Final = "2026-09-20"

#: The seven members the venue calls, read off the protocol rather than listed,
#: so an eighth is checked here the day it is declared.
PROTOCOL_MEMBERS: Final = tuple(sorted(name for name in vars(Tenant) if not name.startswith("_")))


def test_the_committed_config_registers_this_judge() -> None:
    """The one line that decides whether the nightly run judges anything at all.

    Everything else can land, every gate can pass, and a config naming no slug
    still runs a night that hosts nobody: the venue plans tonight, fans out to no
    cell, and commits nothing.
    """
    registered = config.load_council(CONFIG_DIR).judge_names

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
    settings = config.load(CONFIG_DIR)
    check(settings.app, council=settings.council)


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

    assert tenant.JUDGE_ID == ledger.entry(LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).prefix[0]
    assert tenant.JUDGE_ID == on_the_row
    assert tenant.TENANT.judge_id == tenant.JUDGE_ID


def test_this_judge_splits_its_work_the_way_its_draw_is_dealt() -> None:
    """The selection deals every pair a shard number at the venue's own width.

    A tenant answering anything narrower here leaves the difference unread, with
    every unit reporting success and the day counted as though the missing pairs
    had never been drawn.
    """
    assert tenant.TENANT.shard_count == config.load_council(CONFIG_DIR).shards


def test_this_judge_stages_each_ledger_it_writes_where_the_registry_files_it() -> None:
    """One staged path a ledger, read off the registry, so a ledger that moves moves its path.

    The judged pairs go through the ledger door, so they are staged under
    `state/raw/`. A ledger no night writes any more is staged by nothing, and the
    folders the judge once filed CSV into are staged by nothing either - not by
    name, and not by a parent folder holding them.
    """
    staged = tenant.TENANT.committed_paths
    old_csv_folders = (
        "state/content-similarity-judge/scored-pairs",
        "state/content-similarity-judge/metrics",
        "state/raw/content-similarity-judge/scored-pairs",
        "state/raw/content-similarity-judge/metrics",
        "state/content-similarity-judge/score-distribution.json",
    )

    assert staged == tuple(staging.staged_path(which) for which in tenant.WRITTEN_LEDGERS)
    assert staged == ("state/raw/content-similarity-judge/pair-verdicts",)
    assert not [
        path
        for path in staged
        for old in old_csv_folders
        if old == path or old.startswith(f"{path}/")
    ], "a staged path still covers a folder the judge no longer writes"
    assert all(
        ledger.entry(which).prefix[0] == tenant.JUDGE_ID for which in tenant.WRITTEN_LEDGERS
    ), "this judge stages a ledger outside its own family"


def test_the_collecting_job_needs_no_committed_input_of_this_judge() -> None:
    """It reads tonight's files, which arrive as artifacts, and files rows without reading any."""
    assert tenant.TENANT.publication_inputs(date=A_NIGHT) == ()


def a_filed_night(state: Path, date: str) -> None:
    """One judged pair filed for `date` through the ledger door, the way the save job files it."""
    left, right = sorted(
        (derive_url_key(f"https://left.example/{date}"), derive_url_key(f"https://right.example/{date}"))
    )
    row = StorySimilarityPairVerdict.model_validate(
        {
            "date": date,
            "run_id": f"{date}-9",
            "work_part_index": 0,
            "pair_key": derive_text_digest(left + right),
            "left_url_key": left,
            "right_url_key": right,
            "similarity_score": 0.5,
            "cosine": 0.5,
            "headline": False,
            "scorer_model": "all-minilm-l6-v2-quantized",
            "cosine_weight": 1.0,
            "bucket": PairBucket.FULLY_DISSIMILAR,
            "slice_low": -1.0,
            "slice_high": 0.7,
            "slice_pairs_available": 1,
            "slice_pairs_judged": 1,
            "lower_threshold_in_force": 0.7,
            "upper_threshold_in_force": 0.93,
            "config_versions": '{"judges/content-similarity-judge.json":"2026-11-19"}',
        }
    )
    ledger.persist(
        state,
        [row],
        ledger=LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
        covers=date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.SAVE_COUNCIL_RESULTS,
            shard=0,
            producer="stages.file_pair_verdicts",
            git_sha=SEED_COMMIT,
        ),
    )


def test_this_judge_names_the_nights_with_no_filed_pair_and_no_other(tmp_path: Path) -> None:
    """A night is behind when nothing was filed for it, and one row settles it.

    On a ledger this test built, never the committed one, so the answer does not
    depend on the archive (CLAUDE.md section 13). A date from outside the window is
    a job the venue never priced, so only the window's own nights can come back.
    """
    state = tmp_path / "state"
    a_filed_night(state, "2026-09-18")
    window = ("2026-09-17", "2026-09-18", "2026-09-19", A_NIGHT)

    answered = tenant.TENANT.nights_outstanding(window=window, state_dir=state)

    assert answered == ("2026-09-17", "2026-09-19", A_NIGHT)
    assert set(answered) <= set(window)


@pytest.mark.parametrize(
    ("max_dates", "max_older_dates", "expected"),
    [
        (1, 1, (A_NIGHT,)),
        (3, 0, (A_NIGHT,)),
        (2, 1, (A_NIGHT, "2026-09-19")),
        (3, 2, (A_NIGHT, "2026-09-19", "2026-09-17")),
    ],
)
def test_schedule_chooses_the_anchor_then_the_newest_unfiled_nights_within_both_budgets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_dates: int,
    max_older_dates: int,
    expected: tuple[str, ...],
) -> None:
    """The judge, not its host, selects the dates from what it has filed."""
    a_filed_night(tmp_path / "state", "2026-09-18")
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    request = ScheduleRequest(
        anchor_date=A_NIGHT,
        window=(A_NIGHT, "2026-09-19", "2026-09-18", "2026-09-17"),
        max_dates=max_dates,
        max_older_dates=max_older_dates,
        shards=1,
        shard_seconds=1.0,
    )

    assert tenant.TENANT.schedule(request=request).dates == expected


def test_a_judge_that_has_filed_nothing_is_behind_on_every_night_of_its_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no row filed there is no night it can call read, so the repair budget decides.

    A new judge schedules its anchor and then repairs the newest night behind it,
    one for each date the council's repair budget allows. The thresholds are found from
    the last few nights' pairs, so those nights are the ones it is behind on.
    """
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    request = ScheduleRequest(
        anchor_date=A_NIGHT,
        window=("2026-09-19", A_NIGHT),
        max_dates=2,
        max_older_dates=1,
        shards=1,
        shard_seconds=1.0,
    )

    assert tenant.TENANT.schedule(request=request).dates == (A_NIGHT, "2026-09-19")
