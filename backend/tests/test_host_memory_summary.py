"""Does the native artifact reader distinguish absent, incomplete and invalid readings?"""

from pathlib import Path

import pytest

from idhazh.telemetry.host_memory_summary import summarize


def test_absent_samples_are_unavailable_not_zero_memory(tmp_path: Path) -> None:
    sample = tmp_path / "samples.jsonl"
    process = tmp_path / "processes.jsonl"
    assert "not found" in summarize(sample, process, maximum=1024)[0]
    sample.write_bytes(b"")
    assert "unavailable" in summarize(sample, process, maximum=1024)[0]


def test_complete_invalid_record_is_refused(tmp_path: Path) -> None:
    sample = tmp_path / "samples.jsonl"
    sample.write_bytes(b"not JSON\n")
    with pytest.raises(ValueError, match="invalid memory record"):
        summarize(sample, tmp_path / "processes.jsonl", maximum=1024)


def test_interrupted_final_record_is_diagnosed(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    sample = tmp_path / "samples.jsonl"
    sample.write_bytes(b'{"llama_vmhwm_kb":17}\n{"llama')
    output = summarize(sample, tmp_path / "processes.jsonl", maximum=1024)
    assert "peak llama VmHWM 17 kB" in output[0]
    assert "incomplete record" in caplog.text
