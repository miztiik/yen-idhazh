"""Verify original recording provenance before adapting historical model identity."""

import json
from pathlib import Path

import pytest

from .contract_examples import REPOSITORY
from .replay_predictions import read_recordings


def test_historical_fingerprint_bytes_remain_part_of_recording_provenance(tmp_path: Path) -> None:
    directory = tmp_path / "tests" / "fixtures" / "hhem-evaluator"
    directory.mkdir(parents=True)
    original = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator"
    for name in ("model-inputs.json", "model-predictions.json", "model-identity.json"):
        (directory / name).write_bytes((original / name).read_bytes())
    _, predictions, identity = read_recordings(tmp_path)
    assert len(predictions.cases) == 5
    assert "loaded_weights_sha256" not in identity.model_dump()
    payload = json.loads((directory / "model-identity.json").read_bytes())
    payload["loaded_weights_sha256"] = "0" * 64
    (directory / "model-identity.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssertionError, match="do not belong together"):
        read_recordings(tmp_path)
