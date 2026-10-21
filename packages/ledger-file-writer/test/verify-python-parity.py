"""Does Python accept the writer's Parquet files, rows, digest, and identities?"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow.parquet

from idhazh.contracts.feed_ingest_article_assessment import ArticleAssessmentRecord
from idhazh.contracts.feed_ingest_diversity import DiversityMetricRow
from idhazh.contracts.file_envelope import FileEnvelope, Format
from idhazh.ledger import filenames, json_lines, parquet
from idhazh.ledger.persist import file_columns, load_stored


MODELS = {
    "article-assessments": ArticleAssessmentRecord,
    "diversity": DiversityMetricRow,
}


def verify(model_name: str, paths: list[Path]) -> dict[str, Any]:
    model = MODELS[model_name]
    files: list[dict[str, Any]] = []
    for path in paths:
        metadata, stored = parquet.read(path.read_bytes())
        envelope = FileEnvelope.from_metadata(metadata).validate_container(Format.PARQUET)
        loaded = load_stored([path], model=model)
        reconstructed = [
            held.identity.model_dump(mode="json")
            | (held.provenance.model_dump(mode="json") if held.provenance else {})
            | held.row.model_dump(mode="json")
            for held in loaded
        ]
        digest = hashlib.sha256(json_lines.rows_bytes(reconstructed)).hexdigest()
        if digest != envelope.content_sha256:
            raise AssertionError(
                f"{path.name}: stored-row digest differs from Python's canonical bytes "
                f"(writer={envelope.content_sha256}, reader={digest}, "
                f"rows={json_lines.rows_bytes(reconstructed)!r})"
            )
        if len(loaded) != pyarrow.parquet.read_metadata(path).num_rows:
            raise AssertionError(f"{path.name}: footer row count differs from loaded rows")

        expected_unit = filenames.unit_id(
            ledger=envelope.ledger.value,
            covers=envelope.covers,
            run_id=envelope.identity.run_id,
            shard=envelope.identity.shard,
            producer=envelope.identity.producer,
            job=str(envelope.identity.job) if envelope.identity.pipeline_name is None else None,
            pipeline_name=envelope.identity.pipeline_name,
            task_name=envelope.identity.task_name,
        )
        expected_file = filenames.file_id(
            unit=expected_unit,
            attempt=envelope.identity.attempt,
            written_at_ms=envelope.written_at_ms,
        )
        if str(expected_unit) != str(envelope.unit_id) or str(expected_file) != str(envelope.file_id):
            raise AssertionError(f"{path.name}: identifier differs from Python's identity functions")

        actual_schema = pyarrow.parquet.read_schema(path)
        expected_schema = parquet.schema_of(file_columns(model))
        if not actual_schema.equals(expected_schema, check_metadata=False):
            raise AssertionError(
                f"{path.name}: native Arrow schema differs from Python's declared schema "
                f"(actual={actual_schema}, expected={expected_schema})"
            )
        files.append({
            "covers": envelope.covers,
            "tier": envelope.tier.value,
            "period": envelope.period.value if envelope.period else None,
            "row_count": len(loaded),
            "content_sha256": digest,
            "identity": envelope.identity.model_dump(mode="json"),
            "rows": [held.identity.model_dump(mode="json") for held in loaded],
        })
    return {"files": files}


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in MODELS:
        raise SystemExit("usage: verify-python-parity.py <registered-ledger> <parquet-path>...")
    print(json.dumps(verify(sys.argv[1], [Path(value) for value in sys.argv[2:]])))
