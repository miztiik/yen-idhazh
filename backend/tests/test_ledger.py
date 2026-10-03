"""Append-only state ledger protections."""

from __future__ import annotations

import csv
import io
import json
import tracemalloc
from collections.abc import Collection, Iterator, Sequence
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    FIXTURES_DIR,
    read_text,
    seed_feed_health,
    seed_host_fingerprint,
    seed_item_health,
    writer_identity,
)

from idhazh import config, day_shards, ledger, month_partition
from idhazh.contracts.base import ServerJob, derive_url_key
from idhazh.contracts.call_cost import COST_FIELDS, CallKind
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import (
    DROPPED_CELLS,
    RETIRED_CELLS,
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.validation_row import ValidationRow
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.ledger import ledger_files
from idhazh.telemetry import silicon
from idhazh.telemetry.source_health import feed_reliability, reliability
from utilities import migrate_to_parquet
from utilities.reconcile_prefill import TOLERANCE, reconcile

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FIXTURES = FIXTURES_DIR / "state"
DATE = "2026-08-23"
RUN_ID = "2026-08-23-1"
STAMP = "2026-08-23T06:00:00Z"
URL = "https://example.org/items/one"
URL_KEY = derive_url_key(URL)
#: The one committed run both instruments measured. Its four `runtime-log-*`
#: artifacts were pulled before they expired and its item-health rows were
#: lifted into a committed fixture, so the reconciliation runs on real data with
#: no network and no mocks (Guardrail #7).
RECONCILED_DATE = "2026-08-26"
RECONCILED_RUN = "2026-08-26-5"


def published_row(*, url_key: str = URL_KEY, on: str = DATE) -> PublishedRow:
    return PublishedRow(
        version=PublishedRow.schema_version(),
        url_key=url_key,
        published_on=on,
        item_id="ai-01",
    )


def prune_row(*, on: str = DATE, run: str = "1", before: int = 1000) -> VisualPruneRow:
    """One reporting pass, which is the shape every row the pipeline has written has.

    `policy_months` is -1 and `dry_run` is true because that is what ships: the
    cleanup measures the backlog and deletes nothing.
    """
    return VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=on,
        run_id=f"{on}-{run}",
        policy_months=-1,
        max_deletes_per_run=200,
        dry_run=True,
        candidates_found=0,
        deleted=0,
        skipped_by_fuse=0,
        fuse_tripped=False,
        bytes_reclaimed=0,
        oldest_kept=None,
        payload_bytes_before=before,
        payload_bytes_after=before,
    )


def fingerprint_row(*, on: str = DATE, shard: int = 0, cpu: str = "one") -> HostFingerprintRow:
    """One job's machine, from the committed contract fixture with the key rewritten.

    The fixture is read inside this helper rather than at module scope, so a
    fixture that stops parsing fails the tests that ask for a row instead of
    every test in the file (CLAUDE.md section 13). `cpu_model` is the cell the
    callers vary, because it is outside the key: a repeat may carry a different
    one, and which of the two the reader keeps is what a caller asserts.
    """
    raw = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "host-fingerprint-row" / "every-reading-taken.json")
    )
    return HostFingerprintRow.model_validate(
        raw
        | {
            "version": HostFingerprintRow.schema_version(),
            "date": on,
            "run_id": f"{on}-1",
            "shard": shard,
            "cpu_model": cpu,
        }
    )


def test_a_ledger_that_is_not_a_day_tree_is_refused_by_name(tmp_path: Path) -> None:
    """A wrong ledger is answered at the call, not by writing a path no reader walks.

    One typed name covers every ledger under `state/`, so a caller can now hand a
    segment writer a ledger that files no segments. `published` is a day FILE, so
    this call would have minted a directory where that ledger keeps a file. The
    message carries the ledger because the caller passed a name, and a refusal
    that does not repeat it leaves them reading the traceback for it.
    """
    row = fingerprint_row()

    assert LedgerName.PUBLISHED not in DAY_TREES, "the refused ledger has to be a real one"

    with pytest.raises(ValueError, match="published is not a day tree"):
        ledger.write_segment(
            tmp_path,
            LedgerName.PUBLISHED,
            [row],
            run_id=row.run_id,
            attempt=1,
            job=row.job,
            shard=row.shard,
        )

    assert not list(tmp_path.rglob("*")), "the refusal wrote nothing"


def pair_row(*, on: str = DATE, judged_by_run_id: str | None = None) -> StorySimilarityPair:
    """One judged pair, read from the committed contract fixture and re-dated.

    Read inside the helper rather than at module scope, so a fixture that stops
    parsing fails the test that asked for a row instead of the whole file
    (CLAUDE.md section 13).
    """
    raw = json.loads(
        read_text(
            CONTRACT_FIXTURES_DIR / "story-similarity-pair" / "judged-the-same-in-both-orders.json"
        )
    )
    return StorySimilarityPair.model_validate(
        raw
        | {
            "version": StorySimilarityPair.schema_version(),
            "date": on,
            "run_id": f"{on}-1",
            "judged_by_run_id": judged_by_run_id,
        }
    )


def council_row(*, on: str = DATE) -> CouncilShardOutcome:
    """One recorded unit of council work, read from the committed fixture and re-dated.

    Read inside the helper for the reason `pair_row` gives: a fixture that stops
    parsing fails the test that asked for a row rather than the whole file.
    """
    raw = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "council-shard-outcome" / "a-unit-that-ran-no-model.json")
    )
    return CouncilShardOutcome.model_validate(
        raw
        | {
            "version": CouncilShardOutcome.schema_version(),
            "date": on,
            "run_id": f"{on}-1",
        }
    )


def health_row() -> FeedHealthRow:
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=RUN_ID,
        date=DATE,
        feed_id="example-feed",
        checked_at=STAMP,
        outcome=FetchOutcome.OK,
        status=200,
        items=1,
        detail=None,
    )


def _published(state: Path, on: str, url_keys: Sequence[str], *, run: str = "1") -> int:
    """One assemble run's published rows, filed under its digest day as the stage files them."""
    return ledger.append_published(
        state,
        on,
        [published_row(url_key=url_key, on=on) for url_key in url_keys],
        identity=writer_identity(f"{on}-{run}"),
    )


def test_two_runs_that_publish_one_address_keep_its_earliest_date(tmp_path: Path) -> None:
    """The writer files every row it is handed, and the read keeps the earliest date.

    `stages.assemble._published_rows` leans on both halves: nothing at the write
    collapses a repeat, and a repeat in a later run never moves the day an address
    first ran. Two runs are two work units, so both files are read.
    """
    state = tmp_path / "state"
    assert _published(state, "2026-08-23", [URL_KEY]) == 1
    assert _published(state, "2026-08-24", [URL_KEY]) == 1

    filed = sorted(ledger.raw_root(state, LedgerName.PUBLISHED).rglob("*.parquet"))
    assert len(filed) == 2, "the write does not deduplicate"
    assert _whole_ledger(state) == {URL_KEY: "2026-08-23"}, "the read keeps the earliest date"


def test_a_second_attempt_at_one_plan_replaces_its_first_sights(tmp_path: Path) -> None:
    """A re-run of the plan job replaces its first try's sights, as the door does for any ledger.

    A re-run checks out the commit its run started at, so it cannot see what its
    first try filed and files its own sights. Both are one work unit, and the
    door keeps the file of the higher attempt: an address both tries met takes
    the re-run's later stamp, and one only the first try met is absent until the
    next run that meets it files it again.
    """
    state = tmp_path / "state"
    both, only_first = _address(1), _address(2)

    def sight(url_key: str, at: str) -> SeenRow:
        return SeenRow(
            version=SeenRow.schema_version(),
            url_key=url_key,
            first_seen_at=at,
            first_seen_run=RUN_ID,
        )

    ledger.append_seen(
        state,
        DATE,
        [sight(both, "2026-08-23T06:00:00Z"), sight(only_first, "2026-08-23T06:00:00Z")],
        identity=writer_identity(RUN_ID, attempt=1, job=ServerJob.PLAN),
    )
    ledger.append_seen(
        state,
        DATE,
        [sight(both, "2026-08-23T07:30:00Z")],
        identity=writer_identity(RUN_ID, attempt=2, job=ServerJob.PLAN),
    )

    assert ledger.load_seen(state, today=DATE, within_days=90) == {both: "2026-08-23T07:30:00Z"}


def _a_month_of_publications(state: Path, months: Sequence[str], url_keys: Sequence[str]) -> None:
    """Every address published again on the first day of each month, by one run that day."""
    for month in months:
        _published(state, f"{month}-01", url_keys)


#: How many times each tree is read before its peak is taken. One read's peak
#: moves by a few kilobytes between runs with what the allocator happens to
#: reuse, about a tenth of this fixture's peak; the highest of several reads is
#: the stable figure, taken the same way for both trees.
PEAK_READS: Final = 3


def _peak_of_load_published(state: Path) -> tuple[dict[str, str], int]:
    """The answer, and the highest traced peak over `PEAK_READS` reads of this tree."""
    peaks: list[int] = []
    published: dict[str, str] = {}
    for _ in range(PEAK_READS):
        tracemalloc.start()
        try:
            published = _whole_ledger(state)
            peaks.append(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
    return published, max(peaks)


def test_load_published_costs_the_answer_and_not_the_file(tmp_path: Path) -> None:
    """Double the source rows behind a fixed answer, and the peak stays flat.

    The published read is the one read over a ledger with no natural bound: its
    committed cover is open, so it reads every day the ledger has ever held. It
    reads one month at a time and folds each into the answer before the next, so
    what it holds at once is one month's rows and the answer, never the history.

    Sixteen addresses make the answer the same in both trees. Two months versus
    four months doubles the source rows from 32 to 64. Both reads have a later
    month to load after the answer is populated, so the peak includes the answer
    and one month's rows. Each peak is the highest of several reads, so the
    allocator's wobble between runs cannot land on one tree only. The 10 percent
    margin then allows per-file allocation noise; a reader holding every month
    still retains twice the source rows.
    The first read is not measured, so a cost paid once per process lands in
    neither number. Both ledgers are built and fixed (Guardrail #12, section 13).
    """
    addresses = [_address(number) for number in range(16)]
    small, large = tmp_path / "small", tmp_path / "large"
    _a_month_of_publications(small, ["2026-01", "2026-02"], addresses)
    _a_month_of_publications(large, ["2026-01", "2026-02", "2026-03", "2026-04"], addresses)
    expected = dict.fromkeys(addresses, "2026-01-01")
    _whole_ledger(small)

    published_small, peak_small = _peak_of_load_published(small)
    published_large, peak_large = _peak_of_load_published(large)

    assert published_small == expected, "the reduction must keep the earliest date"
    assert published_large == expected
    assert peak_large < peak_small * 1.1, (
        f"twice the rows behind the same addresses moved peak from {peak_small} B to "
        f"{peak_large} B, so the read is holding the ledger rather than one month of it"
    )


def _address(number: int) -> str:
    return derive_url_key(f"https://example.org/items/{number}")


def _whole_ledger(state: Path) -> dict[str, str]:
    """The read under the cover the committed config ships: every day the ledger holds.

    Spelled once here because most of these tests are about the reduction and
    not about the cover, and repeating the sentinel at every call site would
    bury the two tests that are about it.
    """
    return ledger.load_published(state, today=None, within_days=UNBOUNDED_WINDOW)


def _tree(root: Path) -> dict[str, bytes]:
    """Every file under `root`, POSIX path to bytes. Bounded by what a test wrote."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_load_published_reads_no_history_from_a_fresh_clone(tmp_path: Path) -> None:
    """A ledger with no file means nothing has published yet, and it is not an error.

    A clone with no history is the state every fresh checkout is in, and an
    empty mapping is what "nothing has run" looks like. Asserted under both
    covers, because a finite one names days that hold nothing and must answer
    the same way rather than fail on the first of them.
    """
    assert _whole_ledger(tmp_path / "state") == {}
    assert ledger.load_published(tmp_path / "state", today=DATE, within_days=91) == {}


def test_load_published_reads_every_day_the_ledger_holds(tmp_path: Path) -> None:
    """The answer is every day the ledger holds.

    Two days of one month and a day of the next, so the read has to cross a
    month rather than stopping at the first one it finished.
    """
    state = tmp_path / "state"
    _published(state, "2026-08-21", [_address(2)])
    _published(state, "2026-08-22", [_address(3)])
    _published(state, "2026-09-03", [_address(4)])

    assert _whole_ledger(state) == {
        _address(2): "2026-08-21",
        _address(3): "2026-08-22",
        _address(4): "2026-09-03",
    }


@pytest.mark.parametrize("earlier_first", [False, True])
def test_load_published_keeps_the_earliest_date_two_days_hold(
    tmp_path: Path, earlier_first: bool
) -> None:
    """One address on two days in two months. The answer cannot follow read order.

    Asserted both ways round because a reader that simply overwrote would pass
    one case and fail the other, and which case it passed would depend on which
    day it happened to read first.
    """
    state = tmp_path / "state"
    key = _address(1)
    early, late = "2026-08-21", "2026-09-03"
    first, second = (early, late) if earlier_first else (late, early)

    _published(state, first, [key])
    _published(state, second, [key])

    assert _whole_ledger(state) == {key: early}


#: Six days over six months, and two addresses that appear twice. Built rather
#: than read off the committed ledger, which could never carry the case these
#: tests are about (Guardrail #12, section 13).
#:
#: `_address(6)` is the one that matters: it was published in April and again in
#: July, so the unwindowed read answers April and a 120-day cover answers July.
#: A cover does not only forget addresses - it moves dates.
_SIX_MONTHS: Final = {
    "2026-04-05": (1, 6),
    "2026-05-02": (2,),
    "2026-06-30": (3,),
    "2026-07-04": (4, 6),
    "2026-08-21": (5,),
    "2026-09-03": (5,),
}
#: The day both cases are anchored on. Fixed, so nothing here expires when the
#: calendar moves past it. 120 days back from it is 2026-05-11.
_ANCHOR: Final = "2026-09-08"


def _six_months(state: Path) -> None:
    """Write the fixture. What it owes is spelled out in each case, not returned here."""
    for on, numbers in _SIX_MONTHS.items():
        _published(state, on, [_address(number) for number in numbers])


def test_the_committed_cover_answers_exactly_what_the_unwindowed_read_answered(
    tmp_path: Path,
) -> None:
    """Oracle, first case: shipping `-1` leaves the guarantee where it was.

    The cover is machinery and this row ships it open, so the assertion that
    matters is the one saying nothing moved: every address the tree holds, at
    the earliest date any day file gives it - which is what an unwindowed read
    of this ledger has always returned.

    The width is read from the committed config rather than spelled here, so
    narrowing it in `config/idhazh.json` reds this test instead of quietly
    changing what a reader is shown.
    """
    state = tmp_path / "state"
    _six_months(state)
    expected = {
        _address(1): "2026-04-05",
        _address(2): "2026-05-02",
        _address(3): "2026-06-30",
        _address(4): "2026-07-04",
        _address(5): "2026-08-21",
        _address(6): "2026-04-05",
    }
    committed = config.load(CONFIG_DIR).app.collect.published_window_days

    assert committed == UNBOUNDED_WINDOW, (
        "the committed cover is open, and the equality below is what that buys"
    )
    assert ledger.load_published(state, today=_ANCHOR, within_days=committed) == expected
    assert _whole_ledger(state) == expected, "and the anchor is not read on that path"


def _asked(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every list of days the reader hands the door's bounded read, in the order it asked.

    A recorder rather than a substitute: it calls the real read and hands back
    what the real read returns, so the mapping under test is the mapping a run
    gets (Guardrail #7). Counting what was asked is the only way to tell the two
    paths apart - both answer the same over a fixture the cover covers, and a
    wall clock would measure the box rather than the read.

    Patched on the module the reader calls it through, so the reader's own call
    is the one recorded.
    """
    real = ledger_files.load_days
    asked: list[list[str]] = []

    def record(state_dir: Path, which: LedgerName, days: Collection[str], **kwargs: Any) -> Any:
        asked.append(list(days))
        return real(state_dir, which, days, **kwargs)

    monkeypatch.setattr(ledger_files, "load_days", record)
    return asked


def test_a_finite_cover_reads_the_days_in_range_and_no_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Oracle, second case: a cover of 120 days never reads an April or a May day.

    Proved by what the reader asked for rather than by how long it took. The
    fixture spans six months, so 120 days back from the anchor cuts it in the
    middle. April and May are out of reach, their two addresses are gone from
    the answer, and the address they shared with July comes back dated July.
    None of that is a bug being caught - it is what a cover is for, and it is
    why `CollectConfig` refuses one no wider than `collect.seen_window_days`.

    The bounded path names its days, so it asks for all 121 of them in one read
    and most hold nothing, which is not a fault: nobody published on those days.
    """
    state = tmp_path / "state"
    _six_months(state)
    asked = _asked(monkeypatch)

    published = ledger.load_published(state, today=_ANCHOR, within_days=120)

    assert published == {
        _address(3): "2026-06-30",
        _address(4): "2026-07-04",
        _address(5): "2026-08-21",
        _address(6): "2026-07-04",
    }, "two addresses forgotten, and a third answering with a later date"
    assert len(asked) == 1, "the whole cover is one bounded read"
    days = asked[0]
    assert len(days) == 121, "one day per day in the cover, and the anchor is one of them"
    assert days[0] == "2026-09-08", "newest first"
    assert days[-1] == "2026-05-11", "120 days back from the anchor"
    assert "2026-04-05" not in days, "April is never read"
    assert "2026-05-02" not in days, "nor is the May day"


def test_the_unbounded_cover_reads_one_held_month_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the count: `-1` reads every month the ledger holds, one at a time.

    Six months hold a day each and six reads are made, each one month's days. No
    month the ledger never held is named, because this path asks the ledger's
    indexes and raw folders what it holds rather than naming a range. A month a
    read is what keeps the peak at one month's rows.
    """
    state = tmp_path / "state"
    _six_months(state)
    asked = _asked(monkeypatch)

    published = ledger.load_published(state, today=None, within_days=UNBOUNDED_WINDOW)

    assert len(published) == 6
    held = sorted({on[:7] for on in _SIX_MONTHS})
    assert asked == [ledger.month_days(month) for month in held]


def test_a_finite_cover_without_the_day_it_is_anchored_on_refuses() -> None:
    """A cover with no anchor is a caller error, and it fails rather than reading nothing.

    Reading nothing would return an empty mapping, which is what a fresh clone
    returns - so the guard would silently stop firing and every address would be
    planned again. The unbounded path takes `None` because it never reads it.
    """
    with pytest.raises(ValueError, match="needs the day it is anchored on"):
        ledger.load_published(Path("state"), today=None, within_days=120)


def test_append_published_files_the_day_it_is_given_and_no_other(tmp_path: Path) -> None:
    """The Oracle: one run writes one file, and it is that run's own day.

    The whole state directory is compared rather than the day alone. A write
    that also touched a neighbouring day, or wrote an index beside its file,
    would pass an assertion about the day and fail here - and touching a day
    nobody is publishing is what a partitioned writer must never do
    (`docs/concepts/partitions.md`). The day is read off the file's own envelope
    as well as its folder, because the envelope is what a reader trusts.
    """
    state = tmp_path / "state"
    date = "2026-09-07"

    landed = _published(state, date, [URL_KEY])

    assert landed == 1
    written = list(_tree(state))
    assert len(written) == 1, f"one file for one run's day, not {written}"
    assert written[0].startswith("raw/published/2026/09/07/")
    assert ledger.read_envelope(state / written[0]).covers == date


def test_a_run_in_a_later_month_leaves_the_earlier_one_byte_identical(
    tmp_path: Path,
) -> None:
    """A closed day is not rewritten, and the bytes say so rather than a count.

    This is the freeze rule read from the writer's side: the run's own date
    picks the folder, so every other day is out of reach. Compared byte for byte
    because a row written into yesterday would leave the file count unchanged.
    """
    state = tmp_path / "state"
    _published(state, "2026-09-30", [URL_KEY])
    september = _tree(state)
    assert september, "nothing was written, so the comparison below would prove nothing"

    _published(state, "2026-10-01", [_address(2)])

    october = _tree(state)
    added = set(october) - set(september)
    assert len(added) == 1 and next(iter(added)).startswith("raw/published/2026/10/01/")
    assert {name: october[name] for name in september} == september


def test_what_the_writer_files_by_day_is_what_the_reader_answers(tmp_path: Path) -> None:
    """The writer's own output is read back, rather than a second spelling of it.

    Both halves are checked together here rather than each against a fixture of
    the other's output: rows this writer really filed, across two days and two
    months, and every address back from one read.
    """
    state = tmp_path / "state"
    _published(state, "2026-08-20", [_address(1)])
    _published(state, "2026-09-07", [_address(2)])

    assert _whole_ledger(state) == {
        _address(1): "2026-08-20",
        _address(2): "2026-09-07",
    }


def carried_row(
    number: int,
    *,
    source_id: str,
    outcome: ItemOutcome = ItemOutcome.OK,
    date: str = DATE,
) -> ItemHealthRow:
    """One item-health row for a distinct address, so a count has something to count."""
    url = f"https://{source_id}.example.org/items/{number}"
    code = None if outcome is ItemOutcome.OK else FailureCode.PAYWALLED
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=date,
        run_id=f"{date}-1",
        item_id=f"ai-{number:010d}",
        url_key=derive_url_key(url),
        canonical_url=url,
        vertical="ai",
        source_id=source_id,
        stage=ItemStage.PUBLISH if outcome is ItemOutcome.OK else ItemStage.EXTRACT,
        outcome=outcome,
        code=code,
    )


#: A generation this ledger has never carried, and that is the point of building
#: it. The names a row cannot do without - the eleven every row fills, the count
#: of calls and the five flat totals its own rule holds to their sum - plus every
#: heading `RETIRED_CELLS` still reads into a current column: the twelve the call
#: rename retired and the two that named the machine before the ledger door took
#: `job` and `shard` for its own writer. It is narrower than any generation the
#: archive holds, so a reader that only ever coped with the shapes the committed
#: days happen to carry fails here.
A_RETIRED_GENERATION: Final = (
    "version",
    "date",
    "run_id",
    "item_id",
    "url_key",
    "canonical_url",
    "vertical",
    "source_id",
    "stage",
    "outcome",
    "code",
    "model_calls",
    *COST_FIELDS,
    *RETIRED_CELLS,
)

#: What each dropped heading held, so the reader is asked to throw a VALUE away
#: rather than only a name. `cgroup_peak_bytes` is empty on every committed row -
#: that is why it was dropped - so the filled cell here is a case the archive has
#: never produced and the only way to prove the cell goes with the heading
#: (`CLAUDE.md` section 13). `max_output_tokens` is the opposite case: it is
#: filled on every committed row, so a reader that kept dropped cells would carry
#: it onto every row it moved.
A_DROPPED_CELL_HELD: Final[dict[str, str]] = {
    "runner_name": "GitHub Actions 1000031786",
    "cgroup_peak_bytes": "15032385536",
    "max_output_tokens": "900",
}


def timed_row(number: int) -> ItemHealthRow:
    """One row a work shard sealed after its label call, so a reader has cells to move.

    Built through `model_validate` rather than `model_copy`, because the
    contract's own rules - a call slot fills whole, the flat cells are its sum,
    and a named job names its shard - are what make this a faithful row of that
    generation rather than a plausible one.
    """
    call = {
        "prefill_ms": 149_761 + number,
        "decode_ms": 389_543 + number,
        "input_tokens": 7_543 + number,
        "output_tokens": 1_290 + number,
        "cached_tokens": 1_676 + number,
    }
    return ItemHealthRow.model_validate(
        carried_row(number, source_id="wire").model_dump(mode="json")
        | {"model_calls": 1, "label_kind": CallKind.LABEL.value}
        | {f"label_{name}": value for name, value in call.items()}
        | call
        | {"machine_job": ServerJob.WORK.value, "machine_shard": 2}
    )


def a_generation(header: tuple[str, ...], rows: Sequence[ledger.CsvRecord]) -> str:
    """One header and its rows, written the way a run on that generation wrote them.

    Every cell comes from the row's own `csv_row`, read back through the name the
    heading had then, so the fixture cannot drift from the contract it is meant
    to predate.
    """
    buffer = io.StringIO()
    out = csv.writer(buffer, lineterminator="\n")
    out.writerow(header)
    for row in rows:
        payload = row.csv_row()
        out.writerow([payload[RETIRED_CELLS.get(name, name)] for name in header])
    return buffer.getvalue()


def an_archived_day(state: Path, day: str, name: str, text: str) -> None:
    """One file of a census day, in the CSV layout the retired writers filed it in.

    Nothing writes that layout any more - the census files through the ledger
    door - but the migration that moves the archive onto the door reads it, so
    a test that wants one on disk builds it where the migration looks.
    """
    root = migrate_to_parquet.csv_root(state, LedgerName.ITEM_HEALTH)
    folder = root / day[:4] / day[5:7] / day[8:10]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8", newline="")


def migrated_reading(state: Path, day: str) -> list[dict[str, str]]:
    """One archived census day, settled, the way the migration reads it before filing it."""
    key = ledger.door_key(LedgerName.ITEM_HEALTH)
    root = migrate_to_parquet.csv_root(state, LedgerName.ITEM_HEALTH)
    return day_shards.settled_day(root, day, key, ItemHealthRow)


@pytest.mark.parametrize("dropped", sorted(DROPPED_CELLS))
def test_an_older_generation_of_the_census_reads_into_todays_row(
    tmp_path: Path, dropped: str
) -> None:
    """Every heading the census retired or dropped still reads, and only into today's row.

    Nothing appends to an item-health CSV any more, so no header is re-filed on
    a write. What is left of the CSV archive is read once, by the migration that
    moves it onto the ledger door, and that read is what these headings still
    owe. Three kinds of heading, one row:

    - a RETIRED heading moved to another column and is read into it: the twelve
      `call_*` cells into the two call slots, and the old `job` and `shard` into
      `machine_job` and `machine_shard`;
    - a DROPPED heading has no replacement, so its cell is gone from the row the
      migration files - `runner_name`, because the host record carries the label
      once a job; `cgroup_peak_bytes`, because the kernel file it was read from is
      absent on every runner this project has probed; `max_output_tokens`,
      because the budgets that actually bounded a decode are still on the row;
    - a column this generation never had reads as absent, never as a number.

    **Driven from the dropped set rather than from one name**, so a column
    dropped later arrives here with its own case instead of relying on somebody
    remembering.
    """
    state = tmp_path / "state"
    row = timed_row(1)
    header = (*A_RETIRED_GENERATION, dropped)
    assert not set(RETIRED_CELLS.values()) & set(header), (
        "the fixture names a column that replaced a retired heading, so it proves nothing"
    )
    payload = row.csv_row()
    buffer = io.StringIO()
    out = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    out.writeheader()
    out.writerow(
        {name: payload[RETIRED_CELLS.get(name, name)] for name in A_RETIRED_GENERATION}
        | {dropped: A_DROPPED_CELL_HELD[dropped]}
    )
    writer = ledger.segment_name(run_id=RUN_ID, attempt=1, job=ServerJob.WORK, shard=2)
    an_archived_day(state, DATE, writer, buffer.getvalue())

    (cells,) = migrated_reading(state, DATE)
    read_back = ItemHealthRow.from_csv_row(cells)

    assert dropped not in cells, "a dropped heading is gone from the row the migration files"
    assert read_back == row, "every retired heading reads into the column that replaced it"
    assert (read_back.machine_job, read_back.machine_shard) == (ServerJob.WORK, 2)
    assert read_back.source_words_before_cap is None, (
        "a column this generation never had is absent, not a number nobody measured"
    )


def test_the_committed_generation_before_the_machine_probe_still_reads(tmp_path: Path) -> None:
    """A day the archive really holds, read the way the migration reads it.

    `state/item-health/2026/09/16/before-partition.csv` as it was committed, two
    rows of it kept. It moves in several directions at once: the machine probe's
    columns are not in it yet, the machine's shard is still under its old heading
    `shard`, and three cells the row has since dropped are still there. The
    built generation above covers each heading on its own; this is the shape a
    real day has, all of them together.

    Read by name on both sides, so a row that lost the wrong cell fails here
    rather than passing a width check that only counts columns.
    """
    state = tmp_path / "state"
    fixture = STATE_FIXTURES / "item-health-before-the-machine-probe-widened-it.csv"
    an_archived_day(state, "2026-09-16", ledger.BEFORE_PARTITION_NAME, read_text(fixture))
    with fixture.open(encoding="utf-8", newline="") as handle:
        committed = list(csv.DictReader(handle))
    header = set(committed[0])
    assert "shard" in header, "the fixture no longer carries the machine's old heading"
    assert DROPPED_CELLS <= header, "the fixture no longer carries the dropped headings"
    renamed = {RETIRED_CELLS[name] for name in header if name in RETIRED_CELLS}
    never = set(ItemHealthRow.csv_columns()) - header - renamed
    assert never, "the fixture has to predate a column or the absent case proves nothing"

    settled = migrated_reading(state, "2026-09-16")

    assert [cells["item_id"] for cells in settled] == [raw["item_id"] for raw in committed]
    both = [name for name in committed[0] if name in ItemHealthRow.model_fields]
    for raw, cells in zip(committed, settled, strict=True):
        assert {name: cells[name] for name in both} == {name: raw[name] for name in both}, (
            "a cell both generations name moved"
        )
        assert cells["machine_shard"] == raw["shard"], "the old heading reads under the new name"
        assert not DROPPED_CELLS & set(cells), "a dropped cell went with its heading"
        assert all(cells[name] == "" for name in never), "a column it never had is absent"
        assert ItemHealthRow.from_csv_row(cells).item_id == raw["item_id"]


#: A feed-health header narrower than the one this checkout writes: the row's
#: first nine columns, without the five that name the address asked and what its
#: robots file said. All five are optional, so a row under this header still
#: reads, and re-filing it has columns to add.
A_NARROWER_FEED_HEALTH_HEADER: Final = (
    "version",
    "run_id",
    "date",
    "feed_id",
    "checked_at",
    "outcome",
    "status",
    "items",
    "detail",
)


def feed_row(feed_id: str) -> FeedHealthRow:
    """One feed's verdict for `DATE`, for a test that needs several feeds in one file."""
    return health_row().model_copy(update={"feed_id": feed_id})


def a_feed_file(state: Path, rows: list[FeedHealthRow]) -> Path:
    """The plan job's feed verdicts for `DATE`, filed by the real writer, and where they landed."""
    assert seed_feed_health(state, DATE, rows) == len(rows)
    return ledger.day_shard_path(
        state,
        LedgerName.FEED_HEALTH,
        date=DATE,
        run_id=RUN_ID,
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
    )


def test_the_older_generation_is_refiled_whichever_block_the_merge_put_first(
    tmp_path: Path,
) -> None:
    """A union merge orders the blocks by which side was being replayed, not by age.

    A merge driver that stacked two header blocks into one file ran on every day
    file under `state/` until 2026-09-19, and the files it made were carried into
    the day directories as they stood - so a committed day can still hold two
    generations, and re-filing it has to read both. The committed day that first
    showed this had the current header first, because the older run was the one
    rebasing. The other order is a merge nobody has made here yet, so it is
    built rather than waited for.
    """
    path = ledger.path(tmp_path / "state", LedgerName.FEED_HEALTH, DATE)
    path = path / ledger.BEFORE_PARTITION_NAME
    path.parent.mkdir(parents=True)
    stranded, settled = feed_row("older-feed"), feed_row("newer-feed")
    path.write_text(
        a_generation(A_NARROWER_FEED_HEALTH_HEADER, [stranded])
        + a_generation(FeedHealthRow.csv_columns(), [settled]),
        encoding="utf-8",
        newline="",
    )

    moved = ledger.migrate_header(path, FeedHealthRow.csv_columns(), ledger.refiler(FeedHealthRow))

    assert moved == 1, "only the row under the older header had to move"
    assert ledger.read_header(path) == FeedHealthRow.csv_columns()
    with path.open(encoding="utf-8", newline="") as handle:
        read_back = [FeedHealthRow.from_csv_row(raw) for raw in csv.DictReader(handle)]
    assert read_back == [stranded, settled]


def test_a_day_file_already_under_the_current_header_is_left_byte_identical(
    tmp_path: Path,
) -> None:
    """A pass with nothing to do leaves no diff, so re-filing a ledger twice rewrites nothing."""
    path = a_feed_file(tmp_path / "state", [health_row()])
    before = path.read_bytes()

    assert (
        ledger.migrate_header(path, FeedHealthRow.csv_columns(), ledger.refiler(FeedHealthRow)) == 0
    )
    assert path.read_bytes() == before


def test_a_file_wider_than_this_checkout_is_refused_and_left_byte_identical(
    tmp_path: Path,
) -> None:
    """Widening only. A narrow writer never re-files a wide file down.

    The case is a pass on a checkout that predates a widening: it holds the
    narrower column list, so re-filing under it would drop every cell the
    widening added - exit 0, nothing printed, and the cells gone. The refusal
    costs that pass the step it was called from, which is the cheaper of the two
    and the one a person can see.

    The narrow side is built rather than checked out: the wide file is what this
    checkout writes, and the narrow reader is the same contract told it may only
    place the columns an earlier generation named.
    """
    path = a_feed_file(tmp_path / "state", [health_row()])
    before = path.read_bytes()

    with pytest.raises(ValueError, match="cannot place"):
        ledger.migrate_header(path, A_NARROWER_FEED_HEALTH_HEADER, ledger.refiler(FeedHealthRow))

    assert path.read_bytes() == before, "not one cell moved"
    with path.open(encoding="utf-8", newline="") as handle:
        assert [FeedHealthRow.from_csv_row(raw) for raw in csv.DictReader(handle)] == [health_row()]


class _CountedRead:
    """A read handle that says how many lines were taken out of it.

    Instrumentation rather than a mock: every byte still comes off the real file
    through the real handle, and this counts what was asked for. A clock would
    not answer the same question - the machine this runs on is shared, so a
    timing assertion measures the neighbours.
    """

    def __init__(self, handle: Any, tally: list[int]) -> None:
        self._handle = handle
        self._tally = tally

    def __iter__(self) -> Iterator[str]:
        for line in self._handle:
            self._tally[0] += 1
            yield line

    def readlines(self) -> list[str]:
        lines: list[str] = self._handle.readlines()
        self._tally[0] += len(lines)
        return lines

    def readline(self) -> str:
        line: str = self._handle.readline()
        self._tally[0] += 1 if line else 0
        return line

    def read(self, *args: Any) -> str:
        text: str = self._handle.read(*args)
        self._tally[0] += len(text.splitlines())
        return text

    def __enter__(self) -> _CountedRead:
        self._handle.__enter__()
        return self

    def __exit__(self, *exc: object) -> Any:
        return self._handle.__exit__(*exc)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)


def counted_reads(monkeypatch: pytest.MonkeyPatch, path: Path) -> tuple[list[int], list[int]]:
    """Count how often `path` is opened to read, and how many lines come out."""
    opens = [0]
    lines = [0]
    real_open = Path.open

    def opener(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        handle = real_open(self, mode, *args, **kwargs)
        if self != path or "r" not in mode:
            return handle
        opens[0] += 1
        return _CountedRead(handle, lines)

    monkeypatch.setattr(Path, "open", opener)
    return opens, lines


def test_the_header_check_reads_one_line_whatever_the_file_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file already under the contract's header costs a re-file one line.

    Nothing this checkout writes can put a second header into a file: a day
    tree's writer writes its file whole, and `extend_ledger_file` writes a header
    only into a file that does not exist yet. So scanning every line of a file
    whose first line already matches asks a question whose answer cannot have
    moved since the file was written.
    """
    state = tmp_path / "state"
    path = a_feed_file(state, [feed_row(f"feed-{number:02d}") for number in range(2)])
    _, lines = counted_reads(monkeypatch, path)

    assert (
        ledger.migrate_header(path, FeedHealthRow.csv_columns(), ledger.refiler(FeedHealthRow)) == 0
    )

    assert lines[0] == 1, f"the header check read {lines[0]} lines of a 3-line file"


def test_the_day_count_is_what_each_feed_put_in_front_of_a_reader(tmp_path: Path) -> None:
    """A slot a feed spent and lost is not a slot it filled.

    The ceiling this feeds is about how much of the day a reader sees from one
    publication. A paywall costs the run a slot, but it puts nothing on the
    page, so charging the feed for it would quarantine a source for a door
    somebody else locked.
    """
    state = tmp_path / "state"
    seed_item_health(
        state,
        DATE,
        [
            carried_row(1, source_id="wire"),
            carried_row(2, source_id="wire"),
            carried_row(3, source_id="wire", outcome=ItemOutcome.FAILED),
            carried_row(4, source_id="lab"),
        ],
    )

    assert ledger.load_source_counts(state, DATE) == {"wire": 2, "lab": 1}


def test_one_story_recorded_twice_is_counted_once(tmp_path: Path) -> None:
    """Both jobs write this ledger and a replay of the day writes it again.

    The work shards and assemble each file their own census rows for the day,
    and a replay files them again under its own run, so one address can arrive
    twice. Counting rows would charge a feed twice for one story and cut its
    share of the day in half for no reason a reader could see.
    """
    state = tmp_path / "state"
    seed_item_health(state, DATE, [carried_row(1, source_id="wire")])
    twice = carried_row(1, source_id="wire")
    seed_item_health(state, DATE, [twice.model_copy(update={"run_id": f"{DATE}-2"})])

    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_yesterdays_share_is_not_todays(tmp_path: Path) -> None:
    """The window is the day. A feed that filled yesterday starts today empty."""
    state = tmp_path / "state"
    yesterday = "2026-08-22"
    seed_item_health(state, yesterday, [carried_row(1, source_id="wire", date=yesterday)])
    seed_item_health(state, DATE, [carried_row(2, source_id="wire")])

    assert ledger.load_source_counts(state, yesterday) == {"wire": 1}
    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_a_day_nothing_was_recorded_for_counts_nothing(tmp_path: Path) -> None:
    """A fresh clone has no history, and no history is an empty count."""
    assert ledger.load_source_counts(tmp_path / "state", DATE) == {}


def _scores(**cells: str) -> str:
    """One committed-shaped eval ledger, with only the cells a test cares about set."""
    columns = EvalRow.csv_columns()
    base = dict.fromkeys(columns, "0")
    base.update(
        {
            "version": "2026-08-23",
            "date": "2026-08-23",
            "run_id": "2026-08-23-1",
            "item_id": "energy-01",
            "url_key": "a" * 64,
            "source_url": "https://newsroom.example-grid.com/a",
            "title": "A title",
            "vertical": "energy",
            "model_id": "qwen3-8b-q4-k-m",
            "band": "high",
            "scorer_version": "hhem-2.1-open@aaaaaaaa;weights-bbbbbbbb;metrics-3;bands=0.80/0.50",
            "scored_at": "2026-08-23T06:18:02Z",
            "truncation_flagged": "False",
            "hedge_dropped": "False",
            "extraction_suspect": "False",
            "determinism_violation": "False",
        }
    )
    base.update(cells)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerow(base)
    return out.getvalue()


def test_the_two_ledgers_on_the_door_file_under_the_raw_root() -> None:
    """The retirements and the cleanup record moved onto the ledger door together.

    Neither has a CSV address any more: each writer files one file of its own
    under `state/raw/<ledger>/`, and the step that commits it stages `state`
    whole, so no header-only file has to exist before the first row. What is
    asserted is the folder a reader walks, which is the part a code change can
    break.
    """
    state = Path("state")

    assert ledger.raw_root(state, LedgerName.FEED_RETIREMENTS) == Path("state/raw/feed-retirements")
    assert ledger.raw_root(state, LedgerName.VISUAL_PRUNES) == Path("state/raw/visual-prunes")


def test_the_hand_marked_holdout_is_named_where_the_commit_step_stages_it() -> None:
    """The one seeded header left, and it needs one for a reason of its own.

    A person types this file, so on a fresh clone it holds nothing but its
    header - and `git add` on a path that is not there aborts the commit step and
    takes every ledger staged in the same call with it. Whether the checkout
    carries the file is `backend/utilities/check_seeded_ledgers.py`'s question
    (`CLAUDE.md` section 13); what stays here is the path the commit step is
    handed.
    """
    assert (
        ledger.relpath(LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS)
        == "state/content-similarity-judge/holdout-pairs.csv"
    )
    assert ledger.path(Path("state"), LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS) == Path(
        "state/content-similarity-judge/holdout-pairs.csv"
    )


def test_the_judged_pairs_are_filed_under_the_day_they_were_drawn_from() -> None:
    """One nested segment more than every other day tree, and the relpath says so.

    Everything this judge produces hangs off `state/content-similarity-judge/`,
    so the commit step can stage one prefix. That makes this the first ledger
    whose day file sits two
    directories below `state/` rather than one, and a helper that quietly dropped
    the nest would write a tree nothing else in this file can find.
    """
    date = "2026-09-18"
    state = Path("state")

    assert (
        ledger.relpath(LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, date)
        == "state/content-similarity-judge/scored-pairs/2026/09/18.csv"
    )
    assert ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, date) == Path(
        "state/content-similarity-judge/scored-pairs/2026/09/18.csv"
    )


def test_the_fitted_line_is_filed_under_the_day_it_was_fitted_for() -> None:
    """Its sibling's layout, because the guard reads a window of days across both.

    The step-change guard takes a median over the newest fourteen written rows,
    which `day_partition` answers by walking days backwards. A month file would
    make that read open weeks it did not ask for.
    """
    date = "2026-09-18"
    state = Path("state")

    assert (
        ledger.relpath(LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, date)
        == "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv"
    )
    assert ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, date) == Path(
        "state/content-similarity-judge/fitted-thresholds/2026/09/18.csv"
    )


def test_the_score_record_is_one_file_that_never_grows_with_the_archive() -> None:
    """Not a ledger: it is rewritten, and its size is the band rather than the history.

    That is the whole reason the fit reads it instead of the day tree
    (Guardrail #12), so the path carries no date and there is nothing here for a
    partition to place.
    """
    assert ledger.path(
        Path("state"), LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION
    ) == Path("state/content-similarity-judge/score-distribution.json")


# --- The cleanup record, one file per pass ----------------------------------


def prune_identity(*, run_id: str = RUN_ID, attempt: int = 1) -> WriterIdentity:
    """Who wrote one cleanup record: the assemble job's prune pass, as the stage names it."""
    return WriterIdentity(
        run_id=run_id,
        attempt=attempt,
        job=ServerJob.ASSEMBLE,
        shard=0,
        producer="gardener.tasks.visual_prune",
        git_sha="a" * 40,
    )


def file_prune(state: Path, row: VisualPruneRow, *, attempt: int = 1) -> Path:
    """One cleanup pass filed through the door, the way the prune step files it."""
    written = ledger.persist(
        state,
        [row],
        ledger=LedgerName.VISUAL_PRUNES,
        covers=row.date,
        identity=prune_identity(run_id=row.run_id, attempt=attempt),
    )
    assert len(written) == 1
    return written[0]


def test_load_visual_prunes_reads_no_history_from_a_fresh_clone(tmp_path: Path) -> None:
    """A missing raw folder means nothing has ever been cleaned, and it is not a fault.

    Every other reader here answers a fresh clone with an empty result, and this
    one has to as well: the first run of a new checkout reports its own pass
    before any file exists to read.
    """
    assert ledger.load_visual_prunes(tmp_path / "state") == []


def test_a_cleanup_pass_writes_only_its_own_file(tmp_path: Path) -> None:
    """The layout oracle: a pass writes one new file, under the day its date names.

    The second pass crosses a month boundary on purpose, and the first file's
    bytes are compared after it: a writer that shared a file between passes
    would change them.
    """
    state = tmp_path / "state"
    september = file_prune(state, prune_row(on="2026-09-07"))
    frozen = september.read_bytes()

    file_prune(state, prune_row(on="2026-10-01"))

    assert september.read_bytes() == frozen
    root = ledger.raw_root(state, LedgerName.VISUAL_PRUNES)
    days = sorted(path.parent.relative_to(root).as_posix() for path in root.rglob("*.parquet"))
    assert days == ["2026/09/07", "2026/10/01"]


def test_load_visual_prunes_reports_every_day_the_tree_holds_oldest_first(
    tmp_path: Path,
) -> None:
    """The question is the whole series, so the read is every file and the order is time.

    Written out of order and across two months, because "oldest first" is what a
    reader of this ledger uses to answer whether the backlog is shrinking. A walk
    that returned whatever order the filesystem handed back would pass a
    one-month case and mislead on a two-month one.
    """
    state = tmp_path / "state"
    for on in ("2026-10-01", "2026-09-07", "2026-09-06"):
        file_prune(state, prune_row(on=on))

    assert [row.date for row in ledger.load_visual_prunes(state)] == [
        "2026-09-06",
        "2026-09-07",
        "2026-10-01",
    ]


def test_a_second_attempt_replaces_its_first_and_another_run_is_kept(tmp_path: Path) -> None:
    """One row per pass: a re-run of one attempt replaces it, a second run adds its own.

    GitHub re-runs a failed job into the same run id, so the second attempt's
    file carries the first attempt's work unit and only the higher attempt is
    read. A second run of the same day is a different unit, and a different pass.
    """
    state = tmp_path / "state"
    file_prune(state, prune_row(on="2026-09-07", run="1", before=100))
    file_prune(state, prune_row(on="2026-09-07", run="1", before=200), attempt=2)
    file_prune(state, prune_row(on="2026-09-07", run="2", before=300))

    rows = ledger.load_visual_prunes(state)

    assert [(row.run_id, row.payload_bytes_before) for row in rows] == [
        ("2026-09-07-1", 200),
        ("2026-09-07-2", 300),
    ]


def test_load_visual_prunes_skips_a_file_it_cannot_read_and_names_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A report that stopped on one unreadable file would cost a reader the day.

    The file that is not a ledger file sits in a real day folder beside a real
    pass, so the read has to both skip it and keep the pass - and the warning
    has to name it, or a skipped day is a day nobody knows is missing.
    """
    state = tmp_path / "state"
    kept = file_prune(state, prune_row(on="2026-09-07"))
    stray = kept.parent / "not-a-ledger-file.parquet"
    stray.write_bytes(b"this is not a ledger file")

    with caplog.at_level("WARNING"):
        rows = ledger.load_visual_prunes(state)

    assert [row.date for row in rows] == ["2026-09-07"]
    assert "state/raw/visual-prunes/2026/09/07/not-a-ledger-file.parquet" in caplog.text


# --- The pass that runs after the merge ------------------------------------


def council_unit(shard: int, host: str) -> CouncilShardOutcome:
    """One unit of a two-unit night, on the machine `host` names - the cell a repeat varies."""
    return CouncilShardOutcome.model_validate(
        council_row().model_dump(mode="json") | {"shard": shard, "shards": 2, "host_model": host}
    )


def test_a_repeated_row_is_dropped_and_every_other_byte_is_left_alone(tmp_path: Path) -> None:
    """First row wins, and a kept row is the line that was read.

    The rule is the one every appending caller already states: a second attempt
    at one unit of work is skipped, so the ledger keeps describing the attempt
    that got there first. Rewriting rather than re-serializing is what makes a
    clean file a no-op - a pass that re-quoted a cell would show up as a diff on
    every run.

    The council's record is the example because this pass still settles it after
    every append: two units of one night, then a second attempt at the first
    unit that drew another machine.
    """
    assert (
        ledger.append_council_shard_outcomes(
            tmp_path, DATE, [council_unit(0, "first"), council_unit(1, "second")]
        )
        == 2
    )
    path = ledger.path(tmp_path, LedgerName.LLM_COUNCIL_SHARD_OUTCOMES, DATE)
    header = ",".join(CouncilShardOutcome.csv_columns())
    clean = path.read_text(encoding="utf-8")
    assert clean.startswith(header)

    # What a second attempt at one unit leaves behind: the same key twice,
    # different cells. The machine is the last column, so the line ends on it.
    kept = clean.splitlines()[1]
    assert kept.endswith(",first"), "the fixture has to end on the cell the repeat varies"
    second_attempt = kept.removesuffix(",first") + ",third"
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(f"{second_attempt}\n")
    assert ledger.repeated_keys(path, ledger.COUNCIL_SHARD_OUTCOME_KEY)

    assert ledger.drop_repeated_rows(path, ledger.COUNCIL_SHARD_OUTCOME_KEY) == 1
    assert path.read_text(encoding="utf-8") == clean
    assert ledger.drop_repeated_rows(path, ledger.COUNCIL_SHARD_OUTCOME_KEY) == 0
    assert path.read_text(encoding="utf-8") == clean


def test_the_pass_leaves_a_ledger_it_cannot_key_alone(tmp_path: Path) -> None:
    """A row written before the key existed is not a row to start deleting from.

    Refusing would cost a run the whole commit step it was called from, over a
    file whose header no longer names every cell the key reads.
    """
    path = tmp_path / "shard-outcomes.csv"
    path.write_text("date,shard\n2026-08-29,0\n2026-08-29,0\n", encoding="utf-8", newline="")
    before = path.read_bytes()

    assert ledger.drop_repeated_rows(path, ledger.COUNCIL_SHARD_OUTCOME_KEY) == 0
    assert path.read_bytes() == before
    assert ledger.drop_repeated_rows(tmp_path / "absent.csv", ledger.COUNCIL_SHARD_OUTCOME_KEY) == 0


def test_the_keyed_set_names_every_ledger_that_declares_one(tmp_path: Path) -> None:
    """Everything here says what makes two of its rows one record, and is settled.

    Five trees left this set on 2026-09-22 and they are the ones to look for if
    this list ever looks short. Each became a day directory where every writer
    holds its own file, so two files nobody else can write need no settlement to
    tell them apart and the repeat this pass existed to drop is one they can no
    longer make. The feed retirements and the cleanup record left for the same
    reason when they moved under `state/raw/`.

    Both covers name the same ledgers on a tree with one day of each in it. What
    separates them is what a second day would add: to the operator's pass, a
    file; to a run's pass, nothing.

    `state/content-similarity-judge/fitted-thresholds/` is registered before
    anything writes it, which is why it is built here by hand rather than by an append
    call. Its sibling `scored-pairs/` has a writer and is filled by one.
    """
    ledger.append_story_similarity_pairs(tmp_path, DATE, [pair_row()])
    ledger.append_council_shard_outcomes(tmp_path, DATE, [council_row()])
    fitted = ledger.path(tmp_path, LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS, DATE)
    fitted.parent.mkdir(parents=True, exist_ok=True)
    fitted.write_text(",".join(FittedSimilarityThreshold.csv_columns()) + "\n", encoding="utf-8")
    named = [
        (
            f"content-similarity-judge/fitted-thresholds/{DATE[:4]}/{DATE[5:7]}/{DATE[8:10]}.csv",
            ledger.STORY_SIMILARITY_THRESHOLD_KEY,
        ),
        (
            f"content-similarity-judge/scored-pairs/{DATE[:4]}/{DATE[5:7]}/{DATE[8:10]}.csv",
            ledger.STORY_SIMILARITY_PAIR_KEY,
        ),
        (
            f"llm-council/shard-outcomes/{DATE[:4]}/{DATE[5:7]}/{DATE[8:10]}.csv",
            ledger.COUNCIL_SHARD_OUTCOME_KEY,
        ),
    ]

    every = ledger.keyed_paths(tmp_path, date=None)
    this_run = ledger.keyed_paths(tmp_path, date=DATE)

    assert [(target.path.relative_to(tmp_path).as_posix(), target.key) for target in every] == named
    assert [
        (target.path.relative_to(tmp_path).as_posix(), target.key) for target in this_run
    ] == named
    assert not any(
        tree.value in target.path.relative_to(tmp_path).as_posix()
        for tree in DAY_TREES
        for target in every
    ), "a day tree of writer-owned files has nothing for this pass to settle"


def test_a_re_judged_pair_keeps_its_row_and_a_repeated_attempt_does_not(
    tmp_path: Path,
) -> None:
    """`judged_by_run_id` is in the key because `run_id` cannot tell these two apart.

    `run_id` on this row names the DIGEST run that published the day, so two
    judging runs over one date write the identical string. Under a key without
    the judging stamp the settlement would keep the row already in the file and
    drop every fresh verdict, while the record counted the fresh ones - two
    descriptions of one day with nothing able to tell them apart. A second
    attempt at ONE judging run is still one row: both attempts read the same
    pair the same way.
    """
    first = pair_row()
    again = pair_row(judged_by_run_id=f"{DATE}-7")

    assert ledger.append_story_similarity_pairs(tmp_path, DATE, [first]) == 1
    assert ledger.append_story_similarity_pairs(tmp_path, DATE, [again]) == 1
    assert ledger.append_story_similarity_pairs(tmp_path, DATE, [again]) == 0

    kept = ledger.load_story_similarity_pairs(tmp_path, DATE)
    assert [row.judged_by_run_id for row in kept] == [None, f"{DATE}-7"]


def test_a_repeated_fingerprint_and_candidate_verdict_are_settled_when_a_reader_asks(
    tmp_path: Path,
) -> None:
    """The settlement these two ledgers used to get after a merge, taken at read time.

    A job runs on one machine, so two rows under one `(date, run_id, job, shard)`
    are one machine written down twice - and counting a machine twice is what
    would make the fleet distribution lie. Nothing rewrites a file to fix that
    any more: each writer owns its own file, so two of them are two attempts and
    the reader keeps the later one.

    Both ledgers at once, because the rule is the same for both: they left
    `keyed_paths` when each writer got a file of its own. Both now write Parquet
    through the ledger writer.
    """
    state = tmp_path / "state"
    candidate = ValidationRow.model_validate(
        {
            "date": DATE,
            "run_id": RUN_ID,
            "model_id": "candidate-fixture",
            "is_incumbent": False,
            "selected": False,
            "leaderboard_hhem": 0.8,
            "measured_hhem": 0.7,
            "articles": 1,
            "commit_sha": "aaaaaaa",
            "runner": "fixture",
            "verdict": "confirmed",
            "detail": "recorded evaluation",
        }
    )
    for attempt, cpu in enumerate(("first", "second"), start=1):
        assert seed_host_fingerprint(state, [fingerprint_row(cpu=cpu)], attempt=attempt) == 1
        ledger.persist(
            state,
            [candidate.model_copy(update={"articles": 16 * attempt})],
            ledger=LedgerName.CANDIDATE_MODELS,
            covers=DATE,
            identity=writer_identity(RUN_ID, attempt=attempt, job=ServerJob.WORK),
        )

    machines = ledger.load_days(
        state, LedgerName.HOST_FINGERPRINT, [DATE], model=HostFingerprintRow
    )
    candidates = ledger.load_days(
        state,
        LedgerName.CANDIDATE_MODELS,
        [DATE],
        model=ValidationRow,
    )

    assert len(machines) == 1, "one machine, written down twice, is one machine"
    assert machines[0].cpu_model == "second"
    assert len(candidates) == 1, "a second attempt replaces a verdict, it does not add one"
    assert candidates[0].articles == 32


# --- One feed, one run, one result ------------------------------------------


def account(outcome: FetchOutcome, *, items: int = 0, at: str = "06:00:00") -> FeedHealthRow:
    """One attempt's account of one run's read of one feed. Always the same key."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=RUN_ID,
        date=DATE,
        feed_id="example-feed",
        checked_at=f"{DATE}T{at}Z",
        outcome=outcome,
        status=200,
        items=items,
    )


def health_rows(state: Path) -> list[FeedHealthRow]:
    return ledger.load_health(state, today=DATE, within_days=1)


#: Three recorded days are the minimum that leave one outside a two-day window.
PARITY_DAYS: Final = 3
PARITY_WINDOW_DAYS: Final = 2

#: One feed a reading, chosen so the three cases the reliability reduction
#: separates are all present: one that answers, one that never reaches the
#: address, and one that was skipped and so bears no evidence either way.
PARITY_FEEDS: Final = {
    "steady": FetchOutcome.OK,
    "broken": FetchOutcome.TRANSIENT,
    "skipped": FetchOutcome.SKIPPED,
}


def parity_rows(days: int = PARITY_DAYS, *, today: str = DATE) -> list[FeedHealthRow]:
    """`days` consecutive days of readings, one row per feed per day, oldest first.

    The steady feed answers on one of the two named days, so its reliability is
    a fraction rather than 1.0 - a window that reached different days would move
    it, which is what makes the comparison below bite.
    """
    start = date_type.fromisoformat(today) - timedelta(days=days - 1)
    rows: list[FeedHealthRow] = []
    for offset in range(days):
        day = (start + timedelta(days=offset)).isoformat()
        for feed_id, outcome in PARITY_FEEDS.items():
            empty = feed_id == "steady" and offset % 2 == 0
            rows.append(
                FeedHealthRow(
                    version=FeedHealthRow.schema_version(),
                    run_id=f"{day}-1",
                    date=day,
                    feed_id=feed_id,
                    checked_at=f"{day}T06:00:00Z",
                    outcome=outcome,
                    status=200 if outcome is FetchOutcome.OK else None,
                    items=0 if empty or outcome is not FetchOutcome.OK else 5,
                )
            )
    return rows


def month_grain_tree(root: Path, rows: list[FeedHealthRow]) -> None:
    """The ledger as it was filed until 2026-09-13: one `<YYYY-MM>.csv` a month.

    Written here rather than read from the archive, because the layout it
    describes is not in the tree any more - and a parity claim needs both sides
    present at once.
    """
    columns = FeedHealthRow.csv_columns()
    by_month: dict[str, list[FeedHealthRow]] = {}
    for row in rows:
        by_month.setdefault(row.date[:7], []).append(row)
    root.mkdir(parents=True, exist_ok=True)
    for month, held in by_month.items():
        body = ",".join(columns) + "\n"
        body += "".join(
            ",".join(str(row.csv_row()[name]) for name in columns) + "\n" for row in held
        )
        (root / f"{month}.csv").write_text(body, encoding="utf-8", newline="")


def month_grain_read(root: Path, *, today: str, within_days: int) -> list[FeedHealthRow]:
    """`load_health` as it read the month shards, spelled out so both cases exist.

    A deliberate copy of the retired reader rather than a call into it: the claim
    is that the answer did not move, and a claim about two grains needs the old
    one written down somewhere.
    """
    rows: list[FeedHealthRow] = []
    for stem in month_partition.shards_in_window(today, within_days):
        path = root / f"{stem}.csv"
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                try:
                    rows.append(FeedHealthRow.from_csv_row(raw))
                except (KeyError, ValueError):
                    continue
    rows.sort(key=lambda row: (row.date, int(row.run_id.rsplit("-", 1)[1])))
    return rows


def test_the_day_grain_answers_what_the_month_grain_answered_over_the_same_rows(
    tmp_path: Path,
) -> None:
    """The row Oracle. Moving the files moved no reliability figure.

    Built at both grains from ONE row list, so a difference can only come from
    the reading. Three dates cross one month boundary. With a two-day window, the day reader
    excludes the oldest date while the month reader opens both month files and
    includes it. Two dates would not prove the exclusion, so these three are the
    smallest sample that shows the difference.

    The day cover counts RECORDED days, so the days it names are the newest
    two on disk. Every day here recorded one, which is why that set and a
    calendar window over the same tree hold the same dates but for the far end.

    The reliability maps are compared over the SAME rows on both sides, because
    that is the claim worth making: `feed_reliability` is untouched by this row,
    and what could break is which rows reach it.

    The test builds these rows rather than reading the committed ledger
    (`CLAUDE.md` section 13, Guardrail #12).
    """
    today = "2026-10-02"
    rows = parity_rows(today=today)
    day_tree = tmp_path / "day" / "state"
    # One call a day, not one a row: the plan job writes its whole read of the
    # day into one file, and a second call under the same identity replaces it.
    a_day: dict[str, list[FeedHealthRow]] = {}
    for row in rows:
        a_day.setdefault(row.date, []).append(row)
    for date_read, day_rows in a_day.items():
        seed_feed_health(day_tree, date_read, day_rows)
    month_root = ledger.tree_root(tmp_path / "month" / "state", LedgerName.FEED_HEALTH)
    month_grain_tree(month_root, rows)

    window = PARITY_WINDOW_DAYS
    recorded = sorted(
        {
            day_shards.date_of(shard)
            for shard in day_shards.shard_files(
                ledger.tree_root(day_tree, LedgerName.FEED_HEALTH), days=UNBOUNDED_WINDOW
            )
        }
    )
    named = set(recorded[-window:])
    from_days = ledger.load_health(day_tree, today=today, within_days=window)
    from_months = month_grain_read(month_root, today=today, within_days=window)

    assert len(recorded) == PARITY_DAYS
    assert len(named) == window, "the cover counts recorded days, and every day here recorded one"
    assert {row.date for row in from_days} == named, (
        "the day case read a day the window did not name"
    )
    assert len(from_days) == len(named) * len(PARITY_FEEDS)
    assert len(from_months) > len(from_days), (
        "the month shards have to hold rows outside the window or the trade is not shown"
    )
    assert from_days == [row for row in from_months if row.date in named]

    floor = 0.05
    over_the_same_rows = {
        feed_id: feed_reliability(
            [row for row in from_months if row.feed_id == feed_id and row.date in named],
            floor=floor,
        )
        for feed_id in PARITY_FEEDS
    }
    measured = reliability(day_tree, today=today, within_days=window, floor=floor)

    assert measured == over_the_same_rows
    assert 0.0 < measured["steady"] < 1.0, "the fixture has to separate the three feeds"
    assert measured["broken"] == floor
    assert measured["skipped"] == 1.0


def test_a_second_attempt_at_one_run_leaves_one_row_per_feed(tmp_path: Path) -> None:
    """The write-side half. A run is one read of one feed, however often it is run.

    A second attempt at one execution writes its own file, so both attempts are
    on disk and neither had to see the other. What settles them is the read, and
    the later attempt wins - which is the answer the appender used to reach by
    rewriting the file the first attempt wrote.
    """
    assert seed_feed_health(tmp_path, DATE, [account(FetchOutcome.TRANSIENT)]) == 1
    retry = [account(FetchOutcome.TRANSIENT, at="07:00:00")]
    assert seed_feed_health(tmp_path, DATE, retry, attempt=2) == 1

    rows = health_rows(tmp_path)
    assert len(rows) == 1
    assert rows[0].checked_at == f"{DATE}T07:00:00Z"


def test_the_attempt_that_carried_articles_wins_however_late_it_ran(tmp_path: Path) -> None:
    """A retry that got nothing describes the retry, not the feed.

    This is the one ledger here that cannot settle by arrival order. Keeping the
    first row would leave a failure on record for a run that recovered; keeping
    the last would throw the recovery away when the retry came back empty.
    """
    seed_feed_health(tmp_path, DATE, [account(FetchOutcome.TRANSIENT, at="06:00:00")])
    seed_feed_health(tmp_path, DATE, [account(FetchOutcome.OK, items=9, at="07:00:00")], attempt=2)
    assert [(row.outcome, row.items) for row in health_rows(tmp_path)] == [(FetchOutcome.OK, 9)]

    later = tmp_path / "later"
    seed_feed_health(later, DATE, [account(FetchOutcome.OK, items=9, at="06:00:00")])
    seed_feed_health(later, DATE, [account(FetchOutcome.OK, items=0, at="07:00:00")], attempt=2)
    assert [(row.outcome, row.items) for row in health_rows(later)] == [(FetchOutcome.OK, 9)]


# --- The server's own counters, and what they are for ----------------------


def test_the_ledgers_prefill_rate_agrees_with_the_servers_own_counters(tmp_path: Path) -> None:
    """The ledger's prefill rate holds against the server's own counters, on one real captured run.

    `docs/architecture/summarize/throughput.md` and the console both publish a
    read rate derived from the item-health ledger, which sums a field copied out
    of one model reply per item. The server counted the same work for itself.
    Until the counters were captured the two could not be held against each
    other at all, which is what Guardrail #10 forbids.

    The tolerance was written down before either side was read. **Both sides are
    captures**: the four `.prom` bodies come from run `2026-08-26-5`'s
    `runtime-log-*` artifacts, and the 160 ledger rows are that same run's rows,
    lifted byte for byte out of the day file the run committed and kept as a
    fixture in the CSV layout they were committed in. Reading the live ledger
    instead put a fuse on a date nobody chose - the day retention rolled that
    day out of `state/`, this test would have gone red on a pull request that
    did not touch it (`CLAUDE.md` section 13).

    Both sides are filed through the ledger door into this test's own tree - the
    census read the way the migration reads the archive, the counters under the
    job that drew each machine - and the operator's own `reconcile` reads them
    back, so the figure checked is the figure an operator is shown.
    """
    state = tmp_path / "state"
    machines = []
    for path in (
        FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-0.prom",
        FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-1.prom",
        FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-2.prom",
        FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-3.prom",
    ):
        tokens, seconds = silicon.server_prompt_totals(path.read_text(encoding="utf-8"))
        machines.append(
            HostFingerprintRow(
                version=HostFingerprintRow.schema_version(),
                date=RECONCILED_DATE,
                run_id=RECONCILED_RUN,
                shard=int(path.stem[-1]),
                server_prompt_tokens=tokens,
                server_prompt_seconds=seconds,
            )
        )
    assert len(machines) == 4, "all four shards, or the run figure is not the run"
    assert seed_host_fingerprint(state, machines) == 4
    census = [
        ItemHealthRow.from_csv_row(cells)
        for cells in migrated_reading(STATE_FIXTURES / "prefill-oracle", RECONCILED_DATE)
    ]
    assert seed_item_health(state, RECONCILED_DATE, census) == len(census)

    result = reconcile(state, run_id=RECONCILED_RUN)

    assert result.server.parts == 4, "every shard's counters were read back"
    assert result.ledger.parts == 116, (
        "the captured run pools 116 of its 160 rows - the rest recorded no timings. "
        "A different count means the fixture was edited, not that the archive moved"
    )
    gap = abs(result.ledger.rate - result.server.rate) / result.server.rate
    assert gap <= TOLERANCE, (
        f"ledger {result.ledger.rate:.4f} tok/s against server {result.server.rate:.4f} tok/s "
        f"is {gap * 100:.2f} percent apart, outside the {TOLERANCE * 100:.0f} percent bound"
    )


def test_a_run_with_no_committed_snapshot_says_so_rather_than_reporting_zero() -> None:
    """An audit that finds nothing must not read as an audit that found agreement.

    Asked of the same captured tree the oracle above reads, which holds no
    counter snapshot at all - so the empty answer comes from a tree fixed in
    size rather than from a date the real ledger happens not to carry yet.
    """
    result = reconcile(STATE_FIXTURES / "prefill-oracle", run_id="1970-01-01-1")

    assert result.server.parts == 0
    assert "nothing to check against" in result.verdict
