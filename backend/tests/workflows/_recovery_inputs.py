"""What saved plan and worker archives does a recovery test start from?"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from pathlib import Path

from pipeline._builders import article, plan, summary

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from utilities.digest_recovery_download import SourceRun


def zipped(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


def saved_inputs(root: Path, source: str) -> tuple[RunPlan, SourceRun, dict[str, bytes]]:
    saved = plan(item_count=2)
    counts = Counter(item.vertical for item in saved.items)
    saved = RunPlan.model_validate(
        {
            **saved.model_dump(),
            "shards": 2,
            "verticals": [
                {**vertical.model_dump(), "planned": counts[vertical.id]}
                for vertical in saved.verticals
            ],
        }
    )
    identity = WriterIdentity(
        run_id=saved.run_id,
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="stages.plan",
        git_sha=source,
    )
    paths = ledger.persist(
        root / "saved-state",
        [saved],
        ledger=LedgerName.RUN_PLAN,
        covers=saved.date,
        identity=identity,
    )
    archives = {
        "plan": zipped({path.name: path.read_bytes() for path in paths}),
        "items-0": zipped(
            {
                f"{saved.items[0].item_id}.article.json": article().to_json().encode(),
                f"{saved.items[0].item_id}.summary.json": summary().to_json().encode(),
            }
        ),
    }
    source_run = SourceRun(
        id=1,
        run_attempt=1,
        head_sha=source,
        path=".github/workflows/digest.yml",
        status="completed",
        conclusion="failure",
        run_started_at=saved.generated_at,
    )
    return saved, source_run, archives
