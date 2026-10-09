"""Recorded judgments survive another batch and cannot drift to another pair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utilities.record_encoder_judgments import append_decisions, read_frame, read_judgments


def frame_file(tmp_path: Path) -> Path:
    article = {
        "title": "A launch", "summary": "The product launched.",
        "outlet": "example.com", "day": "2026-09-01", "url": "https://example.com/one",
    }
    rows = [
        {"id": pair_id, "group": "encoders_differ", "verdict": "", "note": "",
         "a": article, "b": {**article, "url": "https://example.com/two"}}
        for pair_id in ("p0001", "p0002")
    ]
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps({
        "version": "2026-10-09", "pairs_to_read": 2, "repeated": 0,
        "groups": {}, "taken": {}, "verdicts_allowed": ["same", "different", "cannot_tell"],
        "rows": rows,
    }), encoding="utf-8")
    return path


def decision_file(tmp_path: Path, pair_id: str) -> Path:
    path = tmp_path / "batch.json"
    path.write_text(json.dumps({
        pair_id: {"verdict": "same", "note": "The same product launch.", "confidence": "high"},
    }), encoding="utf-8")
    return path


def test_batches_append_without_changing_old_bytes(tmp_path: Path) -> None:
    pairs = frame_file(tmp_path)
    output = tmp_path / "judgments.jsonl"
    append_decisions(pairs, output, decision_file(tmp_path, "p0001"), "test-model", "model")
    first = output.read_bytes()
    append_decisions(pairs, output, decision_file(tmp_path, "p0002"), "test-model", "model")
    assert output.read_bytes().startswith(first)
    frame, digest = read_frame(pairs)
    records = read_judgments(output, frame, digest)
    assert [record.pair_id for record in records] == ["p0001", "p0002"]
    assert all(record.label_source == "model" and record.human_verdict is None for record in records)


def test_repeated_id_needs_explicit_correction(tmp_path: Path) -> None:
    pairs = frame_file(tmp_path)
    output = tmp_path / "judgments.jsonl"
    batch = decision_file(tmp_path, "p0001")
    append_decisions(pairs, output, batch, "test-model", "model")
    original = output.read_bytes()
    with pytest.raises(ValueError, match="already judged"):
        append_decisions(pairs, output, batch, "test-model", "model")
    assert output.read_bytes() == original
    append_decisions(pairs, output, batch, "reviewer", "human", correction=True)
    frame, digest = read_frame(pairs)
    records = read_judgments(output, frame, digest)
    assert len(records) == 2
    assert records[-1].human_verdict == "same"
    with pytest.raises(ValueError, match="cannot replace a person's review"):
        append_decisions(pairs, output, batch, "test-model", "model", correction=True)


def test_changed_frame_cannot_reuse_old_judgments(tmp_path: Path) -> None:
    pairs = frame_file(tmp_path)
    output = tmp_path / "judgments.jsonl"
    append_decisions(pairs, output, decision_file(tmp_path, "p0001"), "test-model", "model")
    pairs.write_text(
        pairs.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n"
    )
    frame, digest = read_frame(pairs)
    with pytest.raises(ValueError, match="different frame"):
        read_judgments(output, frame, digest)


def test_frame_newlines_cannot_change_when_git_commits_it(tmp_path: Path) -> None:
    pairs = frame_file(tmp_path)
    pairs.write_bytes(pairs.read_bytes() + b"\r\n")
    with pytest.raises(ValueError, match="must use LF"):
        read_frame(pairs)
