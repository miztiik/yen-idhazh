"""The gap figures, each checked against arithmetic written a different way.

The fixture is four published days with one deliberate hole in the middle, so a
gap in calendar days cannot be confused with a gap in published days, and one
item whose summary names an entity its own run did not write - which is the only
way to tell the two arms apart.

The registry is the committed one. The vocabulary a gap is measured against is
the thing under test, and a hand-written stand-in would measure the stand-in.
"""

from __future__ import annotations

import ast
import statistics
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import config
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from utilities.entity_gap import (
    DIGEST_RELDIR,
    Appearances,
    agreement,
    appearances,
    as_published,
    coverage,
    day_paths,
    live_days,
    read_days,
    rematched,
    report,
    unregistered_ids,
)

pytestmark = pytest.mark.slow

WATCHLIST: Final = config.load(CONFIG_DIR).watchlist
ENTITY_IDS: Final = [entity.id for entity in WATCHLIST.entities]
MATCHER: Final = rematched(WATCHLIST.entity_terms())

#: Every module a socket could be opened through, plus the two stages in this
#: package that reach the open web. The utility reads committed files and
#: nothing else, and this is the guard that keeps it that way.
NETWORK_MODULES: Final = frozenset(
    {
        "ftplib",
        "http",
        "httpx",
        "idhazh.discover",
        "idhazh.fetch",
        "requests",
        "smtplib",
        "socket",
        "urllib",
    }
)

#: One fixture item: the entity ids the run wrote, and the words a reader is
#: served. They differ on the last day, which is the only way to tell the two
#: arms apart.
Spec = tuple[list[str], str]

FIXTURE_DAYS: Final[tuple[tuple[str, tuple[Spec, ...]], ...]] = (
    (
        "2026-01-01",
        (
            (["nvidia", "openai"], "OpenAI and Nvidia shipped a thing today."),
            ([], "Nothing named here."),
        ),
    ),
    ("2026-01-02", ((["nvidia", "openai"], "OpenAI and Nvidia shipped another thing."),)),
    ("2026-01-04", ((["openai", "tesla"], "OpenAI and Tesla shipped a thing."),)),
    (
        "2026-01-08",
        (
            (["openai"], "OpenAI works with Nvidia."),
            (["ibm"], "Nothing named here."),
        ),
    ),
)


def a_day(root: Path, stamp: str, items: Sequence[DigestItem]) -> None:
    """One committed day payload, in the layout `day_paths` globs for."""
    counted = Counter(item.vertical for item in items)
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=stamp,
        generated_at=f"{stamp}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{stamp}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(counted.items())
        ],
        items=list(items),
    )
    path = root / DIGEST_RELDIR / stamp[:4] / stamp[5:7] / stamp[8:10] / "digest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(day.to_json(), encoding="utf-8", newline="")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """The four fixture days, plus a decoy `digest.json` outside the published tree."""
    base = DigestDay.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json")
    ).items[0]
    for stamp, specs in FIXTURE_DAYS:
        items = [
            base.model_copy(
                update={
                    "item_id": f"ai-{index:02d}",
                    "entities": list(entities),
                    "title": words,
                    "summary": words,
                    "key_points": ["The point carries no name of its own."],
                    "visual": None,
                }
            )
            for index, (entities, words) in enumerate(specs, start=1)
        ]
        a_day(tmp_path, stamp, items)
    decoy = tmp_path / "backend" / "var" / "digest.json"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_text("{}", encoding="utf-8")
    return tmp_path


def row_for(rows: Sequence[Appearances], entity_id: str) -> Appearances:
    return next(row for row in rows if row.entity_id == entity_id)


def test_a_gap_is_the_calendar_days_between_two_consecutive_mentions(tree: Path) -> None:
    """The fixture skips 2026-01-03 and 2026-01-05 to 07, so the two grains differ."""
    days = read_days(tree)
    rows = appearances(days, ENTITY_IDS, as_published)

    openai = row_for(rows, "openai")
    assert openai.days == (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 4), date(2026, 1, 8))
    assert openai.gaps == (1, 2, 4)
    assert openai.median_gap_days == 2.0
    assert openai.longest_gap_days == 4
    # Four mentions over four published days would be a gap of 1 every time.
    assert openai.gaps != (1, 1, 1)


def test_the_median_is_the_median_of_the_gaps_a_second_expression_finds(tree: Path) -> None:
    """`statistics.median` against a positional re-read of the fixture spec.

    Indexed rather than paired, so it cannot repeat a mistake `Appearances.gaps`
    makes with `pairwise`.
    """
    rows = appearances(read_days(tree), ENTITY_IDS, as_published)
    by_hand: dict[str, set[date]] = {}
    for stamp, specs in FIXTURE_DAYS:
        for entities, _ in specs:
            for entity_id in entities:
                by_hand.setdefault(entity_id, set()).add(date.fromisoformat(stamp))
    for entity_id, seen in by_hand.items():
        stamps = sorted(seen)
        gaps = [(stamps[index + 1] - stamps[index]).days for index in range(len(stamps) - 1)]
        expected = statistics.median(gaps) if gaps else None
        assert row_for(rows, entity_id).median_gap_days == expected, entity_id


def test_an_entry_mentioned_once_or_never_has_no_gap_and_is_counted_apart(tree: Path) -> None:
    """A median over fewer than two mentions is not a median, so it is None, not zero."""
    rows = appearances(read_days(tree), ENTITY_IDS, as_published)

    once = row_for(rows, "tesla")
    assert len(once.days) == 1
    assert once.gaps == ()
    assert once.median_gap_days is None

    never = row_for(rows, "adani")
    assert never.days == ()
    assert never.median_gap_days is None

    assert len(rows) == len(ENTITY_IDS), "every registry entry gets a row, mentioned or not"
    assert [row.entity_id for row in rows] == sorted(ENTITY_IDS), "id order, so a re-run agrees"


def test_the_two_arms_read_different_words_and_the_gap_moves_with_them(tree: Path) -> None:
    """The last day names Nvidia in the summary only. One arm sees it; the other does not."""
    days = read_days(tree)
    written = row_for(appearances(days, ENTITY_IDS, as_published), "nvidia")
    served = row_for(appearances(days, ENTITY_IDS, MATCHER), "nvidia")

    assert written.days == (date(2026, 1, 1), date(2026, 1, 2))
    assert written.gaps == (1,)
    assert served.days == (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 8))
    assert served.gaps == (1, 6)

    # Seven pairs both arms found, one the run wrote and the summary dropped,
    # one the summary carries and the run did not write.
    assert agreement(days, WATCHLIST.entity_terms()) == (7, 1, 1)


def test_the_rematched_arm_can_only_name_an_entity_the_registry_holds(tree: Path) -> None:
    """The vocabulary is closed, so a hostile page wins a name we already track and no other."""
    found = {slug for day in read_days(tree) for item in day.items for slug in MATCHER(item)}
    assert found <= set(ENTITY_IDS)
    assert found == {"nvidia", "openai", "tesla"}


def test_a_published_id_the_registry_does_not_name_is_reported(tree: Path) -> None:
    days = read_days(tree)
    assert unregistered_ids(days, ENTITY_IDS) == []
    assert unregistered_ids(days, ["openai"]) == ["ibm", "nvidia", "tesla"]


def test_the_coverage_bound_counts_items_not_mentions(tree: Path) -> None:
    """An item naming two entities is one covered item, which is what bounds the rest."""
    days = read_days(tree)
    covered = coverage(days, MATCHER)
    assert [(str(row.day), row.items, row.items_with_an_entity) for row in covered] == [
        ("2026-01-01", 2, 1),
        ("2026-01-02", 1, 1),
        ("2026-01-04", 1, 1),
        ("2026-01-08", 2, 1),
    ]
    assert live_days(days, as_published) == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 4),
        date(2026, 1, 8),
    ]


def test_the_report_names_every_denominator_it_divides_by(tree: Path) -> None:
    text = report(tree, WATCHLIST)
    assert "published days      4, 2026-01-01 to 2026-01-08" in text
    assert "missing days        4 calendar days in that range published nothing" in text
    assert f"registry entries    {len(ENTITY_IDS)}" in text
    assert "the longest gap this record can express is 7 days" in text
    assert "2 of 30 entries were mentioned twice or more" in text

    row = next(line.split() for line in text.splitlines() if line.startswith("openai "))
    assert row == ["openai", "4", "2.0", "4", "4", "2.0", "4"]


def test_two_runs_over_one_tree_print_the_same_bytes() -> None:
    """The Oracle. A pure function of the committed tree, so a re-run is a check."""
    assert day_paths(REPO_ROOT), "the committed record is what this row measures"
    assert report(REPO_ROOT, WATCHLIST) == report(REPO_ROOT, WATCHLIST)


def test_only_a_committed_day_payload_is_read(tree: Path) -> None:
    """A `digest.json` anywhere but the published tree is not part of the record."""
    read = day_paths(tree)
    assert [path.relative_to(tree).as_posix() for path in read] == [
        f"{DIGEST_RELDIR}/2026/01/01/digest.json",
        f"{DIGEST_RELDIR}/2026/01/02/digest.json",
        f"{DIGEST_RELDIR}/2026/01/04/digest.json",
        f"{DIGEST_RELDIR}/2026/01/08/digest.json",
    ]


def test_the_utility_imports_nothing_that_could_open_a_socket() -> None:
    """The other half of the Oracle: it touches no network."""
    source = read_text(REPO_ROOT / "backend" / "utilities" / "entity_gap.py")
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
    assert not {root.split(".")[0] for root in roots} & NETWORK_MODULES
    assert not roots & NETWORK_MODULES
