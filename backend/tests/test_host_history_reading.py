"""Do Python readers keep stored host provenance without enabling another collector?"""

from pathlib import Path

import pytest
from conftest import writer_identity
from test_ledger import fingerprint_row

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName

pytestmark = pytest.mark.contract


def test_recorded_host_writer_stays_readable_without_rewriting_history(tmp_path: Path) -> None:
    row = fingerprint_row(on="2026-10-14")
    assert row.job is not None
    identity = writer_identity(
        row.run_id, job=ServerJob(row.job), shard=row.shard, producer="telemetry.silicon"
    )
    written = ledger.persist(
        tmp_path / "state", [row], ledger=LedgerName.HOST_FINGERPRINT,
        covers=row.date, identity=identity, fmt=Format.JSON,
    )
    assert len(written) == 1
    path = written[0]
    original = path.read_bytes()
    assert ledger.load([path], model=HostFingerprintRow) == [row]
    assert path.read_bytes() == original
