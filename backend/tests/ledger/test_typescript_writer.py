"""Can Python read declared TypeScript provenance without losing older envelopes?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord
from idhazh.contracts.file_envelope import (
    Compression,
    FileEnvelope,
    Format,
    RowIdentity,
    WriterIdentity,
)
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import arrow_schema, parquet

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("version", ["2026-09-25", "2026-10-14", "2026-10-20"])
def test_older_envelope_footer_roundtrip(version: str) -> None:
    payload = FileEnvelope.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "file-envelope" / "a-raw-file.json")
    ).model_dump(mode="json")
    payload["version"] = version
    envelope = FileEnvelope.model_validate(payload)
    assert FileEnvelope.from_metadata(envelope.as_metadata()) == envelope


def test_typescript_provenance_readback(tmp_path: Path) -> None:
    """PyArrow provides bytes here; engine compatibility is deliberately Row 6's gate."""
    row = CandidateRejectionRecord.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-ingest-rejection" / "empty-feed.json")
    )
    identity = WriterIdentity(
        run_id="2026-10-20-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="fixture.reader",
        git_sha="a" * 40,
    )
    (path,) = ledger.persist(
        tmp_path,
        [row],
        ledger=LedgerName.FEED_HEALTH,
        covers=row.date,
        identity=identity,
        fmt=Format.PARQUET,
    )
    envelope = ledger.read_envelope(path)
    changed = FileEnvelope.model_validate(
        {
            **envelope.model_dump(),
            "writer": "idhazh_typescript.ledger.parquet",
            "writer_version": "fixture-engine",
        }
    )
    _, stored = parquet.read(path.read_bytes())
    columns = arrow_schema.columns_of(CandidateRejectionRecord) + tuple(
        column
        for column in arrow_schema.columns_of(RowIdentity)
        if column.name not in CandidateRejectionRecord.model_fields
    )
    path.write_bytes(
        parquet.render(
            columns,
            stored,
            envelope=changed.as_metadata(),
            compression=Compression.SNAPPY,
        )
    )
    assert ledger.load([path], model=CandidateRejectionRecord) == [row]
    read = ledger.read_envelope(path)
    assert read.writer == "idhazh_typescript.ledger.parquet"
    assert read.content_sha256 == envelope.content_sha256
    assert FileEnvelope.from_metadata(read.as_metadata()) == read
    with pytest.raises(ValueError, match="container"):
        read.validate_container(Format.JSON)
    with pytest.raises(ValueError, match="version"):
        FileEnvelope.model_validate({**read.model_dump(), "version": "2026-10-14"})
    assert read.compression == Compression.SNAPPY
