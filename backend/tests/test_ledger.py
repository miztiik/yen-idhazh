"""Append-only state ledger protections."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh import cli, ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.evals import writer
from idhazh.evals.writer import OBSERVATION_KEY
from utilities import migrate_score_ledger as migrate
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


def test_the_day_count_is_what_each_feed_put_in_front_of_a_reader(tmp_path: Path) -> None:
    """A slot a feed spent and lost is not a slot it filled.

    The ceiling this feeds is about how much of the day a reader sees from one
    publication. A paywall costs the run a slot, but it puts nothing on the
    page, so charging the feed for it would quarantine a source for a door
    somebody else locked.
    """
    state = tmp_path / "state"
    ledger.append_item_health(
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

    `state/item-health/` is appended by the work shards and by assemble, and
    the committed file has held repeated keys before now. Counting rows would
    charge a feed twice for one story and cut its share of the day in half for
    no reason a reader could see.
    """
    state = tmp_path / "state"
    ledger.append_item_health(state, DATE, [carried_row(1, source_id="wire")])
    twice = carried_row(1, source_id="wire")
    ledger.append_item_health(
        state, DATE, [twice.model_copy(update={"run_id": f"{DATE}-2"})]
    )

    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_yesterdays_share_is_not_todays(tmp_path: Path) -> None:
    """The window is the day. A feed that filled yesterday starts today empty."""
    state = tmp_path / "state"
    yesterday = "2026-08-22"
    ledger.append_item_health(
        state, yesterday, [carried_row(1, source_id="wire", date=yesterday)]
    )
    ledger.append_item_health(state, DATE, [carried_row(2, source_id="wire")])

    assert ledger.load_source_counts(state, yesterday) == {"wire": 1}
    assert ledger.load_source_counts(state, DATE) == {"wire": 1}


def test_a_day_nothing_was_recorded_for_counts_nothing(tmp_path: Path) -> None:
    """A fresh clone has no history, and no history is an empty count."""
    assert ledger.load_source_counts(tmp_path / "state", DATE) == {}


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


def test_an_untruncated_row_recovers_the_article_length_it_already_recorded() -> None:
    """The whole article IS the text the model saw, so the count is not a guess.

    `truncate_to_tokens` returns the body unchanged below the cap, and
    `Article.word_count` counts that same string, so the recovered value is
    exactly what today's writer would put there.
    """
    report = migrate.honest(_scores(source_word_count="1201", source_seen_word_count="1210"))
    row = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_recovered == 1
    assert report.rows_emptied == 0
    assert row["source_word_count"] == "1210", "the seen count was the honest one all along"


def test_a_truncated_row_says_it_does_not_know_rather_than_saying_zero() -> None:
    """Extract discarded the pre-cap body, so the length exists nowhere."""
    report = migrate.honest(
        _scores(source_word_count="1921", source_seen_word_count=str(migrate.SEEN_WORD_CAP))
    )
    row = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_emptied == 1
    assert row["source_word_count"] == ""
    assert row["source_seen_word_count"] == str(migrate.SEEN_WORD_CAP)


def test_the_score_migration_moves_no_cell_it_does_not_own() -> None:
    """The Oracle: every other column comes out byte-identical, row for row."""
    before = _scores(source_word_count="900", source_seen_word_count="905", hhem="0.91")
    report = migrate.honest(before)

    was = next(csv.DictReader(before.splitlines()))
    now = next(csv.DictReader(report.text.splitlines()))

    assert report.rows_in == 1
    assert {name: value for name, value in now.items() if name != "source_word_count"} == {
        name: value for name, value in was.items() if name != "source_word_count"
    }


def test_a_row_the_fixed_pipeline_wrote_is_left_alone() -> None:
    """Selection is by the row's own stamp, so a later run's real count survives."""
    with pytest.raises(ValueError, match="already the whole article"):
        migrate.honest(
            _scores(
                version=migrate.FIXED_FROM,
                source_word_count="5240",
                source_seen_word_count="4310",
            )
        )


def test_the_committed_score_ledger_never_reads_more_than_the_article_holds() -> None:
    """The read-side migration for the nullable column is the file itself.

    Every row the pipeline writes from 2026-08-27 goes through the `EvalRow`
    validator that refuses this shape. The committed rows predate it, so the
    file is what has to prove it.
    """
    path = REPO_ROOT / "state" / "scores" / "2026-08.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        impossible = [
            row["item_id"]
            for row in csv.DictReader(handle)
            if row["source_word_count"]
            and int(row["source_seen_word_count"]) > int(row["source_word_count"])
        ]

    assert impossible == [], f"{len(impossible)} rows say the model read more than the article"


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


# --- The pass that runs after the merge ------------------------------------


def test_no_committed_ledger_repeats_a_key_it_says_makes_a_row_unique() -> None:
    """The guard. Every reader of these files sums a run and would be wrong here.

    Measured on this checkout 2026-08-31 before the repair: `2026-08-29-3` held
    six counter rows for four shards and 44 repeated `(date, run_id, item_id)`
    item-health keys, because two workflow runs computed that id and neither
    could see what the other had pushed. Summing that run's reading clock over
    the rows gave 19,305.8 seconds against 11,810.3 - 63 percent high.
    """
    repeated: list[str] = []
    state = REPO_ROOT / "state"
    targets = [
        *ledger.keyed_paths(state),
        *((shard, OBSERVATION_KEY) for shard in writer.ledger_shards(state)),
    ]
    for path, key in targets:
        for found, count in sorted(ledger.repeated_keys(path, key).items()):
            relpath = path.relative_to(REPO_ROOT).as_posix()
            repeated.append(f"{relpath}: {'/'.join(found)} has {count} rows, keyed by {key}")

    assert repeated == []


def test_a_repeated_row_is_dropped_and_every_other_byte_is_left_alone(tmp_path: Path) -> None:
    """First row wins, and a kept row is the line that was read.

    The rule is the one every appending caller already states: a re-run's items
    are skipped, so the ledgers keep describing the attempt that got there first.
    Rewriting rather than re-serializing is what makes a clean file a no-op -
    a pass that re-quoted a cell would show up as a diff on every run.
    """
    path = tmp_path / "runtime-counters.csv"
    header = ",".join(RuntimeCountersRow.csv_columns())
    assert ledger.append_runtime_counters(tmp_path, [counters_row(0, prompt_tokens_total=100)]) == 1
    assert ledger.append_runtime_counters(tmp_path, [counters_row(1, prompt_tokens_total=200)]) == 1
    clean = path.read_text(encoding="utf-8")
    assert clean.startswith(header)

    # What the union merge leaves behind: the same key twice, different cells.
    second_scrape = clean.splitlines()[1].replace(",100,", ",999,")
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(f"{second_scrape}\n")
    assert ledger.repeated_keys(path, ledger.RUNTIME_COUNTERS_KEY)

    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 1
    assert path.read_text(encoding="utf-8") == clean
    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 0
    assert path.read_text(encoding="utf-8") == clean


def test_the_pass_leaves_a_ledger_it_cannot_key_alone(tmp_path: Path) -> None:
    """A shard written before the key existed is not a shard to start deleting from.

    Refusing would cost a run the whole commit step it was called from, over a
    file nothing is appending to any more.
    """
    path = tmp_path / "runtime-counters.csv"
    path.write_text("date,shard\n2026-08-29,0\n2026-08-29,0\n", encoding="utf-8", newline="")
    before = path.read_bytes()

    assert ledger.drop_repeated_rows(path, ledger.RUNTIME_COUNTERS_KEY) == 0
    assert path.read_bytes() == before
    assert ledger.drop_repeated_rows(tmp_path / "absent.csv", ledger.RUNTIME_COUNTERS_KEY) == 0


def test_the_keyed_set_names_every_ledger_that_declares_one(tmp_path: Path) -> None:
    """`state/seen/` and `state/feed-health/` are absent on purpose, not by omission.

    Neither declares a key. A second sight is folded by `load_seen` keeping the
    earliest, and a feed's row is one verdict per feed per run - which two runs
    are entitled to write twice, and which nothing here may collapse.
    """
    ledger.append_seen(tmp_path, DATE, [seen_row()])
    ledger.append_health(tmp_path, DATE, [health_row()])
    ledger.append_runtime_counters(tmp_path, [counters_row(0)])
    item_health = ledger.item_health_path(tmp_path, DATE)
    item_health.parent.mkdir(parents=True, exist_ok=True)
    item_health.write_text(",".join(ItemHealthRow.csv_columns()) + "\n", encoding="utf-8")

    keyed = {path.name: key for path, key in ledger.keyed_paths(tmp_path)}

    assert keyed == {
        "runtime-counters.csv": ledger.RUNTIME_COUNTERS_KEY,
        f"{DATE[:7]}.csv": ledger.ITEM_HEALTH_KEY,
    }


def test_the_whole_state_tree_settles_in_one_call(tmp_path: Path) -> None:
    """What the commit step calls between the rebase and the push.

    It returns zero whatever it finds, because a repeat it drops is a repair
    rather than a finding: a non-zero exit inside `commit-and-push.sh` runs under
    `set -euo pipefail` and would abort the commit, costing the run every ledger
    row staged beside the one it just fixed.
    """
    state = tmp_path / "state"
    ledger.append_runtime_counters(state, [counters_row(0, prompt_tokens_total=100)])
    counters = ledger.runtime_counters_path(state)
    with counters.open("a", encoding="utf-8", newline="") as handle:
        handle.write(counters.read_text(encoding="utf-8").splitlines()[1] + "\n")

    assert cli.stage_dedupe_ledgers(state_dir=state) == 0
    assert ledger.repeated_keys(counters, ledger.RUNTIME_COUNTERS_KEY) == {}
    assert len(ledger.load_runtime_counters(state, run_id=RUN_ID)) == 1


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
