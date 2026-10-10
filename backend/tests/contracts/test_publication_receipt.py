"""Does completed-write evidence round-trip without granting path authority?"""

from pathlib import Path

from conftest import FIXTURES_DIR

from idhazh import atomic_write, completed_writes
from idhazh.contracts.publication_receipt import PublicationReceipt


def test_receipt_roundtrip() -> None:
    path = FIXTURES_DIR / "contracts" / "publication-receipt" / "completed.json"
    text = path.read_text(encoding="utf-8")
    receipt = PublicationReceipt.from_json(text)
    assert receipt.to_json() == text
    assert receipt.version == "2026-10-09"
    assert PublicationReceipt.from_json(receipt.to_json()) == receipt


def test_observer_keeps_completed_writes_when_later_work_fails(tmp_path: Path) -> None:
    target = tmp_path / "completed.txt"
    with completed_writes.collect() as evidence:
        atomic_write.write_atomic(target, "completed\n")
    assert list(evidence) == [target.absolute()]
    assert target.read_bytes() == b"completed\n"
