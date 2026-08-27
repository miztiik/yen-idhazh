"""Append-only state ledger protections."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from utilities.migrate_published_ledger import narrow
from utilities.reconcile_prefill import TOLERANCE, pool_counters, pool_ledger, reconcile

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FIXTURES = FIXTURES_DIR / "state"
DATE = "2026-08-23"
RUN_ID = "2026-08-23-1"
STAMP = "2026-08-23T06:00:00Z"
URL = "https://example.org/items/one"
URL_KEY = derive_url_key(URL)
#: The one committed run both instruments measured. Its four `runtime-log-*`
#: artifacts were pulled before they expired and its item-health rows are in the
#: committed month shard, so the reconciliation runs on real data with no
#: network and no mocks (Rule #7).
RECONCILED_DATE = "2026-08-26"
RECONCILED_RUN = "2026-08-26-5"


def seen_row() -> SeenRow:
    return SeenRow(
        version=SeenRow.schema_version(),
        url_key=URL_KEY,
        canonical_url=URL,
        first_seen_at=STAMP,
        first_seen_run=RUN_ID,
    )


def published_row() -> PublishedRow:
    return PublishedRow(
        version=PublishedRow.schema_version(),
        url_key=URL_KEY,
        published_on=DATE,
        item_id="ai-01",
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


def stale_header(path: Path, columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns[:-1])
        writer.writerow(["stale"] * (len(columns) - 1))


def test_seen_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.seen_path(state, DATE), SeenRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_seen(state, DATE, [seen_row()])


def test_published_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.published_path(state), PublishedRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_published(state, [published_row()])


def test_feed_health_ledger_rejects_stale_committed_header(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale_header(ledger.health_path(state, DATE), FeedHealthRow.csv_columns())

    with pytest.raises(ValueError, match="Migrate the ledger before appending to it"):
        ledger.append_health(state, DATE, [health_row()])


def test_load_published_answers_the_same_from_either_header(tmp_path: Path) -> None:
    """The reader maps cells by name, so a column nothing reads could leave without it.

    Both fixtures hold the same eleven rows copied out of `state/published.csv`
    before it was narrowed; the second has no `canonical_url`. The header check
    guards the writer only - `require_matching_header` is called from `_append`
    and from nothing on the read path - and that is what made narrowing the row
    one commit rather than an expand-migrate-contract sequence (CLAUDE.md
    section 11). It still runs because a fork or a stale branch can hold a wide
    ledger, and this says what happens when one does.
    """
    wide, narrow_state = tmp_path / "wide", tmp_path / "narrow"
    for state, fixture in ((wide, "published-v1.csv"), (narrow_state, "published-v2.csv")):
        state.mkdir()
        ledger.published_path(state).write_bytes((STATE_FIXTURES / fixture).read_bytes())

    wide_header = ledger.read_header(ledger.published_path(wide))
    narrow_header = ledger.read_header(ledger.published_path(narrow_state))
    assert set(wide_header) - set(narrow_header) == {"canonical_url"}
    assert {"url_key", "published_on"} <= set(narrow_header)

    published = ledger.load_published(wide)
    assert len(published) == 11, "an empty or trimmed ledger would pass the comparison while proving nothing"
    assert published == ledger.load_published(narrow_state)


def test_the_state_ledgers_append_blind_and_the_reads_absorb_a_repeat(tmp_path: Path) -> None:
    """`ledger._append` writes every row it is handed. Its callers own the repeats.

    Pinned because the promise in `ledger._append` names those callers, and a
    dedupe quietly added here would make that docstring wrong while every test
    still passed. The eval ledger is the other half of the contrast: it refuses
    an observation it already holds, because a row there is a measurement rather
    than a fact about a run.
    """
    state = tmp_path / "state"
    assert ledger.append_published(state, [published_row()]) == 1
    assert ledger.append_published(state, [published_row()]) == 1

    with ledger.published_path(state).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2, "the append path does not deduplicate"
    assert ledger.load_published(state) == {URL_KEY: DATE}, "the read keeps the earliest date"

def test_narrowing_the_published_ledger_keeps_every_pair_the_skip_read_uses() -> None:
    """The Oracle for dropping `canonical_url`: same rows, same pairs, same order.

    `load_published` opens `url_key` and `published_on` and nothing else, so a
    rewrite that preserves those two cells cannot make a published address
    plannable again. The fixture is eleven real rows out of the ledger that was
    migrated.
    """
    with (STATE_FIXTURES / "published-v1.csv").open(encoding="utf-8", newline="") as handle:
        wide = handle.read()

    report = narrow(wide)

    assert report.rows_in == 11
    assert report.rows_out == report.rows_in, "a row was lost or invented"
    assert report.bytes_out < report.bytes_in
    read = csv.DictReader(report.text.splitlines())
    assert tuple(read.fieldnames or ()) == PublishedRow.csv_columns()
    before = [(row["url_key"], row["published_on"]) for row in csv.DictReader(wide.splitlines())]
    assert [(row["url_key"], row["published_on"]) for row in read] == before


def test_narrowing_an_already_narrow_published_ledger_is_refused() -> None:
    """Running it twice must not be a way to lose a file it no longer understands."""
    with (STATE_FIXTURES / "published-v2.csv").open(encoding="utf-8", newline="") as handle:
        already = handle.read()

    with pytest.raises(ValueError, match="nothing to migrate"):
        narrow(already)


def test_the_committed_published_ledger_has_the_shape_the_contract_writes() -> None:
    """The read-side migration for the narrowed row is the file itself.

    `require_matching_header` stops the append when the two disagree, so a
    contract narrowed without the ledger being rewritten would take down every
    scheduled run at the last stage of the day (CLAUDE.md section 11).
    """
    header = ledger.read_header(ledger.published_path(REPO_ROOT / "state"))

    assert header == PublishedRow.csv_columns()


def test_committed_state_csv_rows_match_their_headers() -> None:
    mismatches: list[str] = []
    for path in sorted((REPO_ROOT / "state").rglob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.reader(handle) if row]
        if not rows:
            continue
        header_width = len(rows[0])
        relpath = path.relative_to(REPO_ROOT).as_posix()
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != header_width:
                mismatches.append(
                    f"{relpath}:{line_number} has {len(row)} cells; header has {header_width}"
                )

    assert mismatches == []


# --- The server's own counters, and what they are for ----------------------


def counters_row(shard: int, **counters: object) -> RuntimeCountersRow:
    return RuntimeCountersRow.model_validate(
        {
            "date": DATE,
            "run_id": RUN_ID,
            "shard": shard,
            "shards": 4,
            "scraped_at": STAMP,
            **counters,
        }
    )


def test_every_ledger_a_work_shard_stages_exists_in_a_fresh_checkout() -> None:
    """`git add` on a path that is not there aborts the whole commit step.

    The script runs under `set -euo pipefail` and stages all three of the work
    job's ledgers in one call, so a `state/runtime-counters.csv` that only
    appears once the counters stage has succeeded would let a broken scrape cost
    the shard its item-health rows as well - the exact loss the commit step was
    added to prevent. The header ships with the contract instead.
    """
    path = ledger.runtime_counters_path(REPO_ROOT / "state")

    assert path.exists(), "the ledger a work shard stages must exist before the first run"
    assert ledger.read_header(path) == RuntimeCountersRow.csv_columns()


def test_a_re_run_shard_cannot_be_counted_twice(tmp_path: Path) -> None:
    """The cells are cumulative totals, so a second row is not a second fact.

    A re-run of a failed job starts a fresh server and scrapes it again. Nothing
    pools two rows for one shard correctly - the tokens would simply be added to
    themselves - and `merge=union` keeps both lines rather than collapsing them,
    so the filter has to run before the write.
    """
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=100)]) == 1
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=999)]) == 0
    assert ledger.append_runtime_counters(tmp_path, [counters_row(1, prompt_tokens_total=200)]) == 1

    landed = ledger.load_runtime_counters(tmp_path, run_id=RUN_ID)
    assert [row.shard for row in landed] == [0, 1]
    assert [row.prompt_tokens_total for row in landed] == [100, 200]


def test_a_shard_whose_server_was_gone_still_counts_as_a_shard(tmp_path: Path) -> None:
    """Pooling a run has to see the shard that contributed nothing.

    Three shards' tokens quoted as a four-shard run is a number nobody can read.
    An empty scrape writes nulls, not zeroes, so the row says "this shard ran and
    the server did not answer" rather than "this shard read no tokens".
    """
    ledger.append_runtime_counters(
        tmp_path, [counters_row(0, prompt_tokens_total=100, prompt_seconds_total=10.0)]
    )
    ledger.append_runtime_counters(tmp_path, [counters_row(1)])

    pooled = pool_counters(ledger.load_runtime_counters(tmp_path, run_id=RUN_ID))

    assert pooled.parts == 2, "a silent shard is still a shard"
    assert pooled.tokens == 100
    assert pooled.rate == 10.0


def test_the_ledgers_prefill_rate_agrees_with_the_servers_own_counters() -> None:
    """The Oracle for row 9, on one real committed run.

    `docs/architecture/summarize/throughput.md` and the console both publish a
    read rate derived from the item-health ledger, which sums a field copied out
    of one model reply per item. The server counted the same work for itself.
    Until the counters were committed the two could not be held against each
    other at all, which is what Rule #10 forbids.

    The tolerance was written down before either side was read. The four
    `.prom` bodies are real captures from run `2026-08-26-5`'s `runtime-log-*`
    artifacts; the ledger side is the committed `state/item-health/2026-08.csv`.
    """
    rows = [
        RuntimeCountersRow.from_metrics_text(
            path.read_text(encoding="utf-8"),
            date=RECONCILED_DATE,
            run_id=RECONCILED_RUN,
            shard=int(path.stem[-1]),
            shards=4,
            scraped_at="2026-08-26T21:32:30Z",
        )
        for path in sorted((FIXTURES_DIR / "runtime").glob("2026-08-26-5-shard-*.prom"))
    ]
    assert len(rows) == 4, "all four shards, or the run figure is not the run"

    server = pool_counters(rows)
    committed = pool_ledger(
        ledger.item_health_path(REPO_ROOT / "state", RECONCILED_DATE), run_id=RECONCILED_RUN
    )
    assert committed.parts > 100, (
        "the committed ledger no longer holds this run's rows - the oracle has no input"
    )

    gap = abs(committed.rate - server.rate) / server.rate
    assert gap <= TOLERANCE, (
        f"ledger {committed.rate:.4f} tok/s against server {server.rate:.4f} tok/s "
        f"is {gap * 100:.2f} percent apart, outside the {TOLERANCE * 100:.0f} percent bound"
    )


def test_a_run_with_no_committed_snapshot_says_so_rather_than_reporting_zero() -> None:
    """An audit that finds nothing must not read as an audit that found agreement."""
    result = reconcile(REPO_ROOT / "state", run_id="1970-01-01-1")

    assert result.server.parts == 0
    assert "nothing to check against" in result.verdict
