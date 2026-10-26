"""A record with a local absolute evidence path is refused on save; a relative one is kept."""

from pathlib import Path

import pytest

from idhazh.contracts.base import Model
from idhazh.contracts.story_source import SourceCheck
from idhazh.story_dataset.storage import Store


class Probe(Model):
    source_checks: list[SourceCheck]


def source_check(reference: str | None) -> SourceCheck:
    return SourceCheck(
        url="https://example.com/a",
        checked_at=None,
        state="read",
        finding="ok",
        evidence_reference=reference,
    )


@pytest.mark.parametrize(
    "reference",
    [
        "C:\\Users\\someone\\archive\\a.html",
        "c:/Users/someone/archive/a.html",
        "\\\\server\\share\\a.html",
        "/home/someone/archive/a.html",
        "file:///C:/Users/someone/archive/a.html",
    ],
)
def test_a_record_with_a_local_absolute_evidence_path_is_refused(
    tmp_path: Path, reference: str
) -> None:
    store = Store(tmp_path)
    try:
        with pytest.raises(ValueError, match="relative path") as refused:
            with store.transaction():
                store.append(
                    "pair", "pair-1", "subject", Probe(source_checks=[source_check(reference)])
                )
        assert "someone" not in str(refused.value)
        assert store.records("pair", Probe) == []
    finally:
        store.close()


@pytest.mark.parametrize(
    "reference",
    ["evidence/a.html", "approved-examples.json; check instant was not recorded", None],
)
def test_a_record_with_a_relative_evidence_reference_is_saved(
    tmp_path: Path, reference: str | None
) -> None:
    store = Store(tmp_path)
    try:
        record = Probe(source_checks=[source_check(reference)])
        with store.transaction():
            store.append("pair", "pair-1", "subject", record)
        assert store.records("pair", Probe) == [record]
    finally:
        store.close()
