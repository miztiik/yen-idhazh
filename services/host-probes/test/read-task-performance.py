"""Verify the exact receipts from the native route through the ordinary Python ledger."""

import json
import sys
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.ledger.keys import door_key


def main() -> None:
    state = Path(sys.argv[1])
    results = json.load(sys.stdin)
    receipts = [result["files"][0] for result in results]
    paths = [state.joinpath(*receipt["path"].split("/")) for receipt in receipts]
    envelopes = [ledger.read_envelope(path) for path in paths]
    for receipt, envelope in zip(receipts, envelopes, strict=True):
        assert envelope.writer == "idhazh_typescript.ledger.parquet"
        assert envelope.identity.producer == "host-probes"
        assert envelope.identity.job is None
        assert str(envelope.file_id) == receipt["file_id"]
        assert str(envelope.unit_id) == receipt["unit_id"]
        assert envelope.content_sha256 == receipt["content_sha256"]
        assert envelope.covers == receipt["covers"]

    kind = LedgerName.TASK_PERFORMANCE
    files = [ledger.load_stored([path], model=TaskPerformanceRow) for path in paths]
    expected = [TaskPerformanceRow.model_validate(result["row"]) for result in results]
    assert [row.row for group in files for row in group] == expected
    assert [len(group) for group in files] == [receipt["row_count"] for receipt in receipts]
    settled = ledger.settle_rows(files, door_key(kind))
    packed = ledger.persist_period(
        state,
        settled,
        model=TaskPerformanceRow,
        ledger=kind,
        period=Period.DAILY,
        covers=expected[0].date,
        identity=envelopes[0].identity,
        built_from=len(paths),
    )
    read_back = ledger.load_stored([packed], model=TaskPerformanceRow)
    expected_by_task = {row.task_name: row for row in expected}
    assert {row.row.task_name: row.row for row in read_back} == expected_by_task


if __name__ == "__main__":
    main()
