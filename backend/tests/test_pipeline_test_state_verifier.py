"""Does the pipeline-test state verifier check named roots without discovering state?"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from utilities.pipeline_test_state_verifier import verify

CASE: Final = "case-2026-10-04"
ROOT: Final = f"state/pipeline-tests/{CASE}"
DAY: Final = "2026-10-04"
MONTH: Final = "2026-10"
RUN_ID: Final = f"{DAY}-1"
WHICH: Final = LedgerName.ITEM_HEALTH


def _root(tmp_path: Path) -> Path:
    """The C1 case root this test builds, with a date-like case slug."""
    return tmp_path / "state" / "pipeline-tests" / CASE


def _row() -> ItemHealthRow:
    """One item-health row, dated into the verifier's named UTC month."""
    return ItemHealthRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json").read_text(encoding="ascii")
    ).model_copy(update={"date": DAY, "run_id": RUN_ID})


def _identity() -> WriterIdentity:
    """The writer identity for the generated raw and compact files."""
    return WriterIdentity(
        run_id=RUN_ID,
        attempt=1,
        job=ServerJob.MIGRATE,
        shard=0,
        producer="tests.pipeline_state_verifier",
        git_sha=SEED_COMMIT,
    )


def _tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A C1 case root with door-written raw and compact files and a compact index."""
    root = _root(tmp_path)
    (raw,) = ledger.persist(root, [_row()], ledger=WHICH, covers=DAY, identity=_identity())
    compact = ledger.persist_period(
        root,
        ledger.load_stored([raw], model=ItemHealthRow),
        model=ItemHealthRow,
        ledger=WHICH,
        period=Period.DAILY,
        covers=DAY,
        identity=_identity(),
        built_from=1,
    )
    index = ledger.compact_index_path(root, WHICH, Period.DAILY)
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=WHICH,
            period=Period.DAILY,
            entries=[CompactEntry(covers=DAY, rows=1, bytes=compact.stat().st_size)],
        ).to_json(),
        encoding="ascii",
        newline="\n",
    )
    return root, raw, index


def _verify(tmp_path: Path) -> None:
    verify(tmp_path, roots=[ROOT], ledgers=[WHICH], months=[MONTH])


def test_verifier_accepts_a_generated_c1_case_root(tmp_path: Path) -> None:
    _tree(tmp_path)

    _verify(tmp_path)


def test_verifier_refuses_one_corrupt_raw_envelope(tmp_path: Path) -> None:
    _root_path, raw, _index = _tree(tmp_path)
    raw.write_bytes(b"not a ledger file\n")

    with pytest.raises(ValueError, match=ROOT):
        _verify(tmp_path)


def test_verifier_refuses_one_corrupt_compact_index(tmp_path: Path) -> None:
    _root_path, _raw, index = _tree(tmp_path)
    index.write_text('{"version":"2026-09-01","entries":"broken"}', encoding="ascii")

    with pytest.raises(ValueError, match=r"daily\.json"):
        _verify(tmp_path)
