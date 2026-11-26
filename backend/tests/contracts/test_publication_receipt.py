"""Does completed-write evidence round-trip without granting path authority?"""

from pathlib import Path

import pytest
from support.paths import FIXTURES_DIR

from idhazh import atomic_write, completed_writes
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
from utilities import publication_evidence
from utilities.publication_request import IntegrityError


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


def test_legacy_receipt_cannot_claim_a_prefix_reserved_for_a_native_task(tmp_path: Path) -> None:
    job = WriterIdentity(
        run_id="2026-11-26-123", attempt=1, job=ServerJob.WORK, shard=0,
        producer="utilities.digest_publish", git_sha="a" * 40,
    )
    scope = "state/raw/task-performance"
    path = tmp_path / scope / "2026/11/26/native.parquet"
    publication_evidence.save(tmp_path, job, "work", {path: "b" * 64})
    with pytest.raises(IntegrityError, match="reserved for another writer") as refused:
        publication_evidence.read(tmp_path, job, ("work",), excluded=(scope,))
    assert refused.value.paths == (path.relative_to(tmp_path).as_posix(),)
