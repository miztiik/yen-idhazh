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
from support.judged_pairs import a_night_of_pairs
from support.ledger import SEED_COMMIT, seed_compact_index, seed_compact_period, seed_raw_rows
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge import tenant
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_pair_verdicts_filed_on,
    load_threshold_history,
    review_days,
)
from idhazh.contracts.base import ServerJob, derive_text_digest, derive_url_key
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.council_invocation import ScheduleRequest
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import PairBucket, StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
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

    The judged pairs and the row each night files for the two thresholds go through the
    ledger door, so both are staged under `state/raw/`. A ledger no night writes any more is
    staged by nothing, and the folders the judge once filed CSV into are staged by nothing
    either - not by name, and not by a parent folder holding them.
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
    assert staged == (
        "state/raw/content-similarity-judge/pair-verdicts",
        "state/raw/content-similarity-judge/threshold-history",
    )
    assert not [
        path
        for path in staged
        for old in old_csv_folders
        if old == path or old.startswith(f"{path}/")
    ], "a staged path still covers a folder the judge no longer writes"
    assert all(
        ledger.entry(which).prefix[0] == tenant.JUDGE_ID for which in tenant.WRITTEN_LEDGERS
    ), "this judge stages a ledger outside its own family"


#: A night whose review window crosses a month and a year, so the declaration has to name
#: days of two years and three months.
NIGHT: Final = "2027-01-03"
PAIRS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
HISTORY: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY
PAIR_PRODUCER: Final = "stages.file_pair_verdicts"
HISTORY_PRODUCER: Final = "stages.review_thresholds"
NIGHT_FIXTURE: Final = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-threshold-history-row"
    / "a-night-that-held-both-thresholds.json"
)


def test_the_collecting_job_is_told_the_days_the_review_reads_and_no_others() -> None:
    """Seven nights of pairs ending on the night, and the 28 days of history before it.

    The edges are what is pinned. The night six days back is read and the one seven back is
    not. The history reaches the 28th day before the night, and neither the 29th nor the
    night itself, whose own row is what the run is about to file.
    """
    declared = set(tenant.TENANT.publication_inputs(date=NIGHT))
    pairs = "state/raw/content-similarity-judge/pair-verdicts"
    history = "state/raw/content-similarity-judge/threshold-history"

    assert {f"{pairs}/2026/12/28", f"{pairs}/2027/01/03"} <= declared
    assert f"{pairs}/2026/12/27" not in declared
    assert {f"{history}/2026/12/06", f"{history}/2027/01/02"} <= declared
    assert f"{history}/2026/12/05" not in declared
    assert f"{history}/2027/01/03" not in declared


def a_history_row(day: str) -> StorySimilarityThresholdHistoryRow:
    """The committed sample night, filed on `day`."""
    sample = StorySimilarityThresholdHistoryRow.from_json(read_text(NIGHT_FIXTURE))
    return sample.model_copy(update={"date": day, "run_id": f"{day}-9"})


def a_state_with_every_kind_of_source(root: Path) -> dict[str, Path]:
    """Pair verdicts and threshold history written by the real writers, one file of each kind.

    The pairs are December packed as a month, 1 January packed as a day, 2 January recorded
    as quiet with a repair's raw file filed after the record, and the night itself raw. The
    history is a raw file at each end of its window, a packed day between them, and the raw
    files just outside the window on both sides.
    """
    state, made = root / "state", {}

    def pairs_of(day: str) -> list[StorySimilarityPairVerdict]:
        return a_night_of_pairs([(0.71, "YES"), (0.72, "NO")], date=day, first_index=int(day[-2:]))

    def kept(days: tuple[str, ...]) -> list[tuple[str, str, StorySimilarityPairVerdict]]:
        return [(day, f"{day}-9", row) for day in days for row in pairs_of(day)]

    made["december"] = seed_compact_period(
        state, PAIRS, StorySimilarityPairVerdict, Period.MONTHLY, "2026-12",
        kept(("2026-12-20", "2026-12-28", "2026-12-30")), producer=PAIR_PRODUCER,
    )
    made["first of january"] = seed_compact_period(
        state, PAIRS, StorySimilarityPairVerdict, Period.DAILY, "2027-01-01",
        kept(("2027-01-01",)), producer=PAIR_PRODUCER,
    )
    made["pair daily index"] = seed_compact_index(
        state, PAIRS, Period.DAILY,
        [
            CompactEntry(covers="2027-01-01", rows=2, bytes=1),
            CompactEntry(covers="2027-01-02", rows=0, bytes=0, state=EntryState.EMPTY),
        ],
    )
    made["pair monthly index"] = seed_compact_index(
        state, PAIRS, Period.MONTHLY, [CompactEntry(covers="2026-12", rows=6, bytes=1)]
    )
    made["pair yearly index"] = seed_compact_index(state, PAIRS, Period.YEARLY, [])
    for name, day in (("repair", "2027-01-02"), ("night", NIGHT)):
        (made[name],) = seed_raw_rows(
            state, PAIRS, pairs_of(day), covers=day, run_id=f"{day}-9", producer=PAIR_PRODUCER
        )

    made["history packed day"] = seed_compact_period(
        state, HISTORY, StorySimilarityThresholdHistoryRow, Period.DAILY, "2026-12-20",
        [("2026-12-20", "2026-12-20-9", a_history_row("2026-12-20"))], producer=HISTORY_PRODUCER,
    )
    made["history daily index"] = seed_compact_index(
        state, HISTORY, Period.DAILY, [CompactEntry(covers="2026-12-20", rows=1, bytes=1)]
    )
    made["history monthly index"] = seed_compact_index(state, HISTORY, Period.MONTHLY, [])
    made["history yearly index"] = seed_compact_index(state, HISTORY, Period.YEARLY, [])
    for name, day in (
        ("history first day", "2026-12-06"),
        ("history yesterday", "2027-01-02"),
        ("history day 29", "2026-12-05"),
        ("history tonight", NIGHT),
    ):
        (made[name],) = seed_raw_rows(
            state, HISTORY, [a_history_row(day)], covers=day, run_id=f"{day}-9",
            producer=HISTORY_PRODUCER,
        )
    return made


def what_the_review_reads(state: Path) -> tuple[list[StorySimilarityPairVerdict], list[StorySimilarityThresholdHistoryRow]]:
    """The rows the review of NIGHT is handed: earlier nights through the door, tonight's raw."""
    days = review_days(NIGHT, config=judge_settings.load())
    return (
        [
            *load_pair_verdicts(state, days.pair_verdicts),
            *load_pair_verdicts_filed_on(state, NIGHT),
        ],
        load_threshold_history(state, days.threshold_history),
    )


def test_a_checkout_holding_only_the_declared_files_reads_what_the_whole_tree_reads(
    tmp_path: Path,
) -> None:
    """The declaration is enough, and every kind of file in it is one a read depends on.

    A copy holding only the files the declaration covers reads the very rows the whole tree
    does. Leaving out any one file a read goes through - the month, the packed day, the raw
    day, either index, the history's packed day or its raw edge - changes what is read, so the
    declaration names nothing the reads could do without. The yearly indexes are named too
    and no read here needs them, since no year is packed.
    """
    root = tmp_path / "whole"
    made = a_state_with_every_kind_of_source(root)
    declared = tenant.TENANT.publication_inputs(date=NIGHT)
    whole = what_the_review_reads(root / "state")

    def copy_without(name: str | None) -> Path:
        sparse = tmp_path / f"sparse-without-{name}"
        for kind, path in made.items():
            relative = path.relative_to(root).as_posix()
            if kind == name or not any(
                relative == one or relative.startswith(f"{one}/") for one in declared
            ):
                continue
            (sparse / relative).parent.mkdir(parents=True, exist_ok=True)
            (sparse / relative).write_bytes(path.read_bytes())
        return sparse / "state"

    assert {row.date for row in whole[0]} == {"2026-12-28", "2026-12-30", "2027-01-01", NIGHT}
    assert {row.date for row in whole[1]} == {"2026-12-06", "2026-12-20", "2027-01-02"}
    assert what_the_review_reads(copy_without(None)) == whole
    for needed in (
        "december",
        "first of january",
        "night",
        "pair daily index",
        "pair monthly index",
        "history packed day",
        "history daily index",
        "history first day",
        "history yesterday",
    ):
        assert what_the_review_reads(copy_without(needed)) != whole, needed


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
