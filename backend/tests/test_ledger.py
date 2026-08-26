"""Append-only state ledger protections."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.seen import PublishedRow, SeenRow
from utilities.migrate_published_ledger import narrow

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FIXTURES = FIXTURES_DIR / "state"
DATE = "2026-08-23"
RUN_ID = "2026-08-23-1"
STAMP = "2026-08-23T06:00:00Z"
URL = "https://example.org/items/one"
URL_KEY = derive_url_key(URL)


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
