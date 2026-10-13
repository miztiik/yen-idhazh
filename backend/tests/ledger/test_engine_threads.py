"""Do the ledger door's engine calls leave their native work on the caller?"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from test_host_fingerprint_migration import generated_compact, manifest_document
from test_host_output_verify import LIMITS, render_file

from idhazh import config
from idhazh.contracts.file_envelope import Format
from idhazh.contracts.visual_prune import VisualPruneRow
from utilities import build_canary_day

pytestmark = pytest.mark.contract

_PROBE = """
import json
import sys
from pathlib import Path

import idhazh.ledger.parquet

def thread_count():
    return sum(1 for _ in Path("/proc/self/task").iterdir())

before = thread_count()
operation = sys.argv[1]
if operation == "ledger-read":
    from contextlib import redirect_stdout
    from io import StringIO
    from utilities import build_canary_day

    state = sys.argv[2]
    sys.argv = ["build_canary_day.py", "--scored-keys", "--state", state]
    output = StringIO()
    with redirect_stdout(output):
        exit_code = build_canary_day.main()
    result = {"exit_code": exit_code, "keys": json.loads(output.getvalue())}
elif operation == "host-output-read":
    from idhazh.telemetry.host_output_verify import (
        VerificationLimits,
        read_host_output,
    )

    verified = read_host_output(
        Path(sys.argv[2]),
        root=Path(sys.argv[3]),
        limits=VerificationLimits(**json.loads(sys.argv[4])),
    )
    result = [row.model_dump(mode="json") for row in verified.rows]
elif operation == "host-history-read":
    from idhazh.telemetry.host_history_files import _compact
    from idhazh.telemetry.host_output_verify import VerificationLimits

    _, rows, _ = _compact(
        Path(sys.argv[2]).read_bytes(),
        VerificationLimits(**json.loads(sys.argv[3])),
    )
    result = rows
elif operation == "persist-write":
    from idhazh import ledger
    from idhazh.contracts.base import ServerJob
    from idhazh.contracts.file_envelope import Format, WriterIdentity
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.contracts.visual_prune import VisualPruneRow

    row = VisualPruneRow.model_validate_json(sys.argv[2])
    paths = ledger.persist(
        Path(sys.argv[3]),
        [row],
        ledger=LedgerName.VISUAL_PRUNES,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.visual_prune",
            git_sha="a" * 40,
        ),
        fmt=Format.PARQUET,
    )
    data = paths[0].read_bytes()
    result = {"files": len(paths), "parquet": data.startswith(b"PAR1")}
elif operation == "grouped-build":
    from idhazh import ledger
    from idhazh.contracts.base import ServerJob
    from idhazh.contracts.file_envelope import (
        Format,
        Period,
        RowIdentity,
        WriterIdentity,
    )
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.contracts.visual_prune import VisualPruneRow

    row = VisualPruneRow.model_validate_json(sys.argv[2])
    which = LedgerName.VISUAL_PRUNES
    producer = "gardener.tasks.visual_prune"
    unit = ledger.unit_id(
        ledger=which,
        covers=row.date,
        run_id=row.run_id,
        job=ServerJob.RUN_TASKS,
        shard=0,
        producer=producer,
    )
    stored = ledger.StoredRow(
        identity=RowIdentity(
            ledger=which,
            covers=row.date,
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            unit_id=str(unit),
        ),
        row=row,
    )
    built = ledger.render_grouped_period(
        Path(sys.argv[3]),
        [[stored]],
        model=VisualPruneRow,
        ledger=which,
        period=Period.MONTHLY,
        covers=row.date[:7],
        identity=WriterIdentity(
            run_id="2026-10-12-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.compaction",
            git_sha="b" * 40,
        ),
        built_from=1,
        fmt=Format.PARQUET,
    )
    result = {
        "rows": built.rows,
        "parquet": built.data.startswith(b"PAR1"),
    }
else:
    raise ValueError(f"unknown probe operation: {operation}")

after = thread_count()
print(json.dumps({"before": before, "after": after, "result": result}), flush=True)
"""


def _probe(operation: str, *arguments: str) -> object:
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, operation, *arguments],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.stdout, completed.stderr
    decoded: object = json.loads(completed.stdout)
    assert isinstance(decoded, dict), completed.stdout
    before, after = decoded.get("before"), decoded.get("after")
    assert isinstance(before, int) and isinstance(after, int), decoded
    assert after == before, decoded
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result: object = decoded["result"]
    return result


@pytest.mark.skipif(
    not Path("/proc/self/task").is_dir() or sys.version_info >= (3, 14),
    reason="requires Linux /proc and a Python version where thread unwind can abort",
)
@pytest.mark.parametrize(
    "operation",
    (
        "ledger-read",
        "host-output-read",
        "host-history-read",
        "persist-write",
        "grouped-build",
    ),
)
def test_each_engine_call_keeps_its_threads_on_the_caller(tmp_path: Path, operation: str) -> None:
    row = VisualPruneRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "visual-prune-row" / "fuse-tripped.json")
    )

    if operation == "ledger-read":
        state = tmp_path / "ledger"
        settings = config.load().app.evaluation
        items = build_canary_day.published_items(settings, FIXTURES_DIR / "canaries")
        assert build_canary_day.file_scores(state, items, settings) == len(items)
        raw_files = list(state.rglob("*.parquet"))
        assert len(raw_files) == 1
        assert raw_files[0].read_bytes().startswith(b"PAR1")
        expected = {
            scored.item_id: scored.url_key
            for scored in build_canary_day.score_rows(items, settings)
        }
        assert _probe(operation, str(state)) == {"exit_code": 0, "keys": expected}
    elif operation == "host-output-read":
        root = tmp_path / "host-output"
        path, _, _ = render_file(root, Format.PARQUET)
        rows = _probe(operation, str(path), str(root), json.dumps(asdict(LIMITS)))
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert isinstance(rows[0], dict)
        assert rows[0].get("date") == "2026-10-10"
        assert rows[0].get("cpu_model") == "Recorded CPU \u03b1"
    elif operation == "host-history-read":
        workspace = tmp_path / "host-history"
        workspace.mkdir()
        relative = generated_compact(
            workspace, manifest_document(), Format.PARQUET, compact_only=True
        )
        rows = _probe(
            operation,
            str(workspace / relative),
            json.dumps(asdict(LIMITS)),
        )
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert {row.get("date") for row in rows if isinstance(row, dict)} == {"2026-09-20"}
        assert {row.get("shard") for row in rows if isinstance(row, dict)} == {0, 1}
    elif operation == "persist-write":
        result = _probe(operation, row.model_dump_json(), str(tmp_path / "persist"))
        assert result == {"files": 1, "parquet": True}
    else:
        result = _probe(operation, row.model_dump_json(), str(tmp_path / "grouped"))
        assert result == {"rows": 1, "parquet": True}
