"""Do Python readers keep stored host provenance without enabling another collector?"""

from pathlib import Path

import pytest
from conftest import writer_identity
from test_ledger import fingerprint_row

from idhazh import ledger
from idhazh.contracts.file_envelope import FileEnvelope, Format
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import json_lines

pytestmark = pytest.mark.contract


def test_recorded_host_writer_stays_readable_without_rewriting_history(tmp_path: Path) -> None:
    row = fingerprint_row(on="2026-10-14")
    identity = writer_identity(row.run_id, job=row.job, shard=row.shard, producer="telemetry.silicon")
    written = ledger.persist(
        tmp_path / "state", [row], ledger=LedgerName.HOST_FINGERPRINT,
        covers=row.date, identity=identity, fmt=Format.JSON,
    )
    assert len(written) == 1
    path = written[0]
    metadata, rows = json_lines.read(path.read_bytes())
    assert metadata[b"writer"] == b"idhazh.ledger.json_lines"
    metadata[b"writer"] = b"idhazh_rust.ledger.json_lines"
    original = json_lines.render(rows, envelope=metadata)
    path.write_bytes(original)
    assert ledger.load([path], model=HostFingerprintRow) == [row]
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="recorded raw host contract"):
        FileEnvelope.from_metadata(metadata | {b"producer": b"other.producer"})
