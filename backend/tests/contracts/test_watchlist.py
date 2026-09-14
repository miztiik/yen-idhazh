"""What are the two kinds of watchlist entry, and what does each one owe?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.watchlist import EntityKind, Watchlist

pytestmark = pytest.mark.contract


def watchlist_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "watchlist" / "seeded.json")
    )
    return payload


def test_the_watchlist_stays_inside_its_configured_cap() -> None:
    config = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert len(watchlist.entities) <= config.collect.watchlist_max_entities


def test_a_subject_needs_neither_a_filer_id_nor_a_feed() -> None:
    """The whole point of the widening.

    A pandemic, a tournament or an export-control regime has no SEC filer id
    and no newsroom of its own. Before `kind` the registry described itself as
    a list of named organisations, so an entry like this had no way in.
    """
    seeded = Watchlist.model_validate(watchlist_payload())
    subject = next(entity for entity in seeded.entities if entity.kind is EntityKind.SUBJECT)
    assert subject.cik is None
    assert subject.feeds == []
    assert subject.aliases, "a subject with no alias is never matched (EntityDef.aliases)"


def test_a_subject_may_not_carry_a_filer_id() -> None:
    """Only an organisation files with the SEC, so the pairing is a data error."""
    payload = watchlist_payload()
    payload["entities"][0]["kind"] = EntityKind.SUBJECT.value
    with pytest.raises(ValueError, match="cik belongs to an organisation"):
        Watchlist.model_validate(payload)


def test_a_watchlist_written_before_the_kind_field_reads_as_organisations() -> None:
    """Section 11's release blocker, tested against the key rather than the stamp.

    Every entry the registry held on 2026-08-31 was a standing organisation, so
    absence has exactly one honest meaning and the change needs no migration.
    """
    payload = watchlist_payload()
    for entity in payload["entities"]:
        del entity["kind"]
    payload["version"] = "2026-08-26"
    older = Watchlist.model_validate(payload)
    assert {entity.kind for entity in older.entities} == {EntityKind.ORGANISATION}


def test_every_committed_registry_entry_is_still_an_organisation() -> None:
    """The row's oracle, and the reason the gap measurement is worth taking.

    A half-life on a company is meaningless - its gap between our own mentions
    is near zero. Until a subject is curated in, the widening carries no
    behaviour, and this test says so out loud rather than leaving it implied.
    """
    watchlist = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    assert [entity.id for entity in watchlist.entities if entity.kind is EntityKind.SUBJECT] == []


def test_the_committed_watchlist_survives_a_read_and_a_rewrite() -> None:
    """A hand-edited config re-serializes to the bytes on disk.

    Without that, a curator's next edit arrives buried in a whole-file
    reshuffle and the diff stops showing what changed.
    """
    text = read_text(CONFIG_DIR / "watchlist.json")
    assert Watchlist.from_json(text).to_json() == text
