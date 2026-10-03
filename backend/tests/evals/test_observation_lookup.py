"""An evaluation lookup has bounded routing and refuses ambiguous replay receipts."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, writer_identity
from pydantic import ValidationError

from idhazh import ledger
from idhazh.atomic_write import write_atomic, write_atomic_bytes
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.observation_lookup import (
    ObservationBatch,
    ObservationLookupEntry,
    ObservationLookupNode,
    ObservationLookupPage,
    ObservationLookupReceipt,
    ObservationLookupRoot,
    ObservationLookupSettings,
    ObservationLookupTransaction,
)
from idhazh.evals.lookup_nodes import leaf_bytes, node_path
from idhazh.evals.observation_batches import file_batch, initialize_fresh, lookup_root, row_digest
from idhazh.evals.observation_lookup import ROOT_NAME, TRANSACTION_NAME, ObservationLookup

pytestmark = pytest.mark.contract


def test_a_routing_page_accepts_only_one_hex_digit_per_child() -> None:
    page = ObservationLookupPage.model_validate(
        {
            "prefix": "ab",
            "children": {
                digit: {"kind": "leaf", "sha256": "a" * 64} for digit in "0123456789abcdef"
            },
        }
    )
    assert len(page.children) == 16
    with pytest.raises(ValidationError):
        ObservationLookupPage.model_validate({"prefix": "ab", "children": {"../": "leaf"}})
    with pytest.raises(ValidationError):
        ObservationLookupPage.model_validate({"prefix": "a" * 64, "children": {"0": "leaf"}})


def test_the_root_round_trips_without_a_growing_file_list() -> None:
    root = ObservationLookupRoot.model_validate(
        {
            "generation": "a" * 64,
            "key_fields": ["url_key", "output_digest", "scorer_version"],
            "node": {"kind": "leaf", "sha256": "b" * 64},
            "settings": {},
        }
    )
    assert ObservationLookupRoot.model_validate_json(root.to_json()) == root
    assert "files" not in ObservationLookupRoot.model_fields


@pytest.mark.parametrize("accepted,output", [(1, None), (0, "raw/result.parquet")])
def test_a_receipt_cannot_claim_missing_or_empty_output(accepted: int, output: str | None) -> None:
    with pytest.raises(ValidationError):
        ObservationLookupReceipt.model_validate(
            {
                "batch_id": "a" * 64,
                "payload_sha256": "b" * 64,
                "generation": "c" * 64,
                "accepted": accepted,
                "output_paths": [] if output is None else [output],
            }
        )


@pytest.mark.parametrize("bound", [4096, 17000])
def test_a_leaf_limit_must_hold_whole_sqlite_pages(bound: int) -> None:
    with pytest.raises(ValidationError):
        ObservationLookupSettings(max_leaf_bytes=bound)


def entry(number: int) -> ObservationLookupEntry:
    return ObservationLookupEntry(
        namespace="observation", identity=hashlib.sha256(str(number).encode("ascii")).hexdigest()
    )


def test_a_missing_index_never_falls_back_to_history(tmp_path: Path) -> None:
    with ObservationLookup(tmp_path) as lookup:
        with pytest.raises(FileNotFoundError, match="migrate it explicitly"):
            lookup.recorded([entry(1).identity])


def test_splitting_keeps_every_key_and_caps_every_leaf(tmp_path: Path) -> None:
    settings = ObservationLookupSettings(max_leaf_bytes=16384)
    entries = [entry(number) for number in range(180)]
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(("url_key", "output_digest", "scorer_version"), settings)
        lookup.put(entries, generation="a" * 64)
        assert lookup.recorded(value.identity for value in entries) == {
            value.identity for value in entries
        }
        assert lookup.recorded([entry(9999).identity]) == set()
        assert lookup.manifest().node.kind == "page"
    for path in (tmp_path / "nodes").rglob("*.sqlite"):
        assert path.stat().st_size <= settings.max_leaf_bytes


def test_unrelated_partitions_are_never_opened(tmp_path: Path) -> None:
    entries = [entry(number) for number in range(200)]
    target = entries[0]
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(
            ("url_key", "output_digest", "scorer_version"),
            ObservationLookupSettings(max_leaf_bytes=16384),
        )
        lookup.put(entries, generation="a" * 64)
        opened: set[str] = set()
        active = [False]

        def record_open(event: str, arguments: tuple[object, ...]) -> None:
            if event == "open" and active[0] and isinstance(arguments[0], str):
                opened.add(arguments[0])

        sys.addaudithook(record_open)
        active[0] = True
        try:
            assert lookup.recorded([target.identity]) == {target.identity}
        finally:
            active[0] = False
        before = len(opened)
        unrelated = [
            entry(number) for number in range(200, 600) if entry(number).key[0] != target.key[0]
        ]
        lookup.put(unrelated, generation="b" * 64)
        opened.clear()
        active[0] = True
        try:
            assert lookup.recorded([target.identity]) == {target.identity}
        finally:
            active[0] = False
        assert len(opened) == before
        for path in (tmp_path / "nodes").rglob("*.sqlite"):
            if str(path) not in opened:
                path.unlink()
        assert lookup.recorded([target.identity]) == {target.identity}


def test_a_split_preserves_a_leaf_reused_as_a_child(tmp_path: Path) -> None:
    candidates = [entry(number) for number in range(2400)]
    first = [value for value in candidates if value.key.startswith("a")][:20]
    later = [value for value in candidates if value.key.startswith("b")][:80]
    settings = ObservationLookupSettings(max_leaf_bytes=16384)
    assert len(first) == 20 and len(later) == 80
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, settings)
        lookup.put(first, generation="a" * 64)
        before = lookup.manifest()
        assert before.node.kind == "leaf"
        lookup.put(later, generation="b" * 64)
        assert lookup.manifest().node.kind == "page"
        assert node_path(tmp_path, before.node).is_file()
        assert lookup.recorded(value.identity for value in first + later) == {
            value.identity for value in first + later
        }


@pytest.mark.parametrize("committed", [False, True])
def test_recovery_preserves_a_node_present_in_both_generations(
    tmp_path: Path, committed: bool
) -> None:
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, ObservationLookupSettings())
        before = lookup.manifest()
    after = before.model_copy(update={"generation": "a" * 64})
    transaction = ObservationLookupTransaction.model_validate(
        {
            "before": before.generation,
            "after": after.generation,
            "created": [before.node],
            "superseded": [before.node],
        }
    )
    write_atomic(tmp_path / TRANSACTION_NAME, transaction.to_json())
    if committed:
        write_atomic(tmp_path / ROOT_NAME, after.to_json())
    with ObservationLookup(tmp_path) as lookup:
        assert lookup.recorded([entry(1).identity]) == set()
        assert node_path(tmp_path, before.node).is_file()


def test_a_noop_does_not_replace_the_root(tmp_path: Path) -> None:
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(
            ("url_key", "output_digest", "scorer_version"), ObservationLookupSettings()
        )
        lookup.put([entry(1)], generation="a" * 64)
        manifest = lookup.manifest()
        lookup.put([entry(1)], generation="b" * 64)
        assert lookup.manifest() == manifest
        assert node_path(tmp_path, manifest.node).is_file()


def measurement(number: int = 0) -> EvalRow:
    path = next((CONTRACT_FIXTURES_DIR / "eval-row").glob("*.json"))
    row = EvalRow.read(path)
    return row.model_copy(
        update={
            "date": "2026-10-02",
            "run_id": "2026-10-02-1",
            "url_key": hashlib.sha256(f"url-{number}".encode()).hexdigest(),
            "output_digest": hashlib.sha256(f"output-{number}".encode()).hexdigest(),
        }
    )


def test_a_changed_root_cannot_reuse_its_recovery_generation(tmp_path: Path) -> None:
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, ObservationLookupSettings())
        before = lookup.manifest()
        with pytest.raises(ValueError, match="new generation"):
            lookup.put([entry(1)], generation=before.generation)
        assert lookup.manifest() == before
        assert lookup.recorded([entry(1).identity]) == set()


@pytest.mark.parametrize("committed", [False, True])
def test_recovery_keeps_exactly_the_generation_the_root_names(
    tmp_path: Path, committed: bool
) -> None:
    settings = ObservationLookupSettings()
    with ObservationLookup(tmp_path) as lookup:
        lookup.initialize(ledger.OBSERVATION_KEY, settings)
        before = lookup.manifest()
    payload = leaf_bytes([entry(1)], settings)
    node = ObservationLookupNode(kind="leaf", sha256=hashlib.sha256(payload).hexdigest())
    after = before.model_copy(update={"generation": "a" * 64, "node": node})
    transaction = ObservationLookupTransaction.model_validate(
        {
            "before": before.generation,
            "after": after.generation,
            "created": [node],
            "superseded": [before.node],
        }
    )
    write_atomic(tmp_path / TRANSACTION_NAME, transaction.to_json())
    write_atomic_bytes(node_path(tmp_path, node), payload)
    if committed:
        write_atomic(tmp_path / ROOT_NAME, after.to_json())
    with ObservationLookup(tmp_path) as lookup:
        assert lookup.manifest() == (after if committed else before)
        assert lookup.recorded([entry(1).identity]) == ({entry(1).identity} if committed else set())
    assert node_path(tmp_path, node).exists() == committed
    assert node_path(tmp_path, before.node).exists() != committed
    assert not (tmp_path / TRANSACTION_NAME).exists()


def test_interrupted_initialization_recovers_without_reading_history(tmp_path: Path) -> None:
    state = tmp_path / "state"
    root = lookup_root(state)
    settings = ObservationLookupSettings()
    payload = leaf_bytes([], settings)
    node = ObservationLookupNode(kind="leaf", sha256=hashlib.sha256(payload).hexdigest())
    transaction = ObservationLookupTransaction.model_validate(
        {"before": None, "after": "a" * 64, "created": [node], "superseded": []}
    )
    write_atomic(root / TRANSACTION_NAME, transaction.to_json())
    write_atomic_bytes(node_path(root, node), payload)
    changed = initialize_fresh(state, settings)
    assert root / ROOT_NAME in changed
    assert not (root / TRANSACTION_NAME).exists()
    with ObservationLookup(root) as lookup:
        assert lookup.recorded([entry(1).identity]) == set()


def test_a_batch_is_filed_once_and_receipts_keep_its_output(tmp_path: Path) -> None:
    state = tmp_path / "state"
    rows = [measurement(), measurement(1)]
    identity = writer_identity("2026-10-02-1")
    settings = ObservationLookupSettings()
    assert file_batch(state, rows, identity, settings) == 2
    assert file_batch(state, rows, identity, settings) == 0
    assert file_batch(state, [measurement(2)], identity, settings) == 1
    loaded = ledger.load_ledger_rows(state, LedgerName.SUMMARY_QUALITY_EVALS, model=EvalRow)
    assert {row_digest(row) for row in loaded} == {row_digest(row) for row in [*rows, measurement(2)]}
    batch = ObservationBatch.model_validate({"identity": identity, "rows": rows})
    with ObservationLookup(lookup_root(state)) as lookup:
        receipt = lookup.receipt(batch.batch_id)
        assert receipt is not None
        assert receipt.accepted == 2
        assert receipt.output_paths
        assert all((state / path).is_file() for path in receipt.output_paths)


def test_a_later_month_cannot_admit_an_existing_measurement(tmp_path: Path) -> None:
    state = tmp_path / "state"
    row = measurement()
    settings = ObservationLookupSettings()
    assert file_batch(state, [row], writer_identity("2026-10-02-1"), settings) == 1
    later = row.model_copy(update={"date": "2027-02-01", "run_id": "2027-02-01-2"})
    assert file_batch(state, [later], writer_identity("2027-02-01-2"), settings) == 0


def test_existing_rows_without_a_lookup_require_explicit_migration(tmp_path: Path) -> None:
    state = tmp_path / "state"
    ledger.persist(
        state, [measurement()], ledger=LedgerName.SUMMARY_QUALITY_EVALS,
        covers="2026-10-02", identity=writer_identity("2026-10-02-1"),
    )
    with pytest.raises(FileNotFoundError, match="explicit observation lookup migration"):
        file_batch(state, [measurement()], writer_identity("2026-10-02-2"), ObservationLookupSettings())
