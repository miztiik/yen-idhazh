"""Do the real consumers reproduce the approved result from the installed bounded history?"""

from __future__ import annotations

import tempfile
from pathlib import Path

from idhazh.contracts.host_migration import HistoryReport
from idhazh.telemetry.host_history_bundle import _replay_migrated_consumers
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_output_verify import _read_bytes


def reconcile_consumers(
    report: HistoryReport, *, workspace: Path, limits: HistoryLimits
) -> None:
    if report.consumer_replay is None:
        raise ValueError("installed consumer reconciliation lacks approved replay evidence")
    artifacts: dict[str, bytes] = {}
    # Project only the approved inputs, not whatever else a later pipeline run added.
    with tempfile.TemporaryDirectory(
        prefix=".d17-consumers-", dir=workspace / report.manifest.isolated_root
    ) as temporary:
        projected = Path(temporary)
        for file in report.files:
            source = file.source
            if source.kind == "receipt":
                continue
            data = _read_bytes(
                workspace.joinpath(*source.path.split("/")),
                root=workspace,
                cap=limits.verification.max_file_bytes,
            )
            target = projected.joinpath(*source.path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if file.candidate_path is not None:
                artifacts[file.candidate_path] = data
        replayed, _ = _replay_migrated_consumers(report, artifacts, workspace=projected)
        if replayed.consumer_replay != report.consumer_replay:
            raise ValueError("installed readers or regenerated dashboard differ from D16 replay")
