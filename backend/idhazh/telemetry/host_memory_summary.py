"""Summarize the native monitor's memory samples without collecting new readings."""

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from idhazh.telemetry.host_evidence_inputs import read_bytes

_LOG = logging.getLogger("idhazh")


def _records(path: Path, maximum: int) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    records: list[dict[str, Any]] = []
    text = read_bytes(path, maximum).decode("utf-8")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            if index == len(lines) - 1 and not text.endswith("\n"):
                _LOG.warning("memory artifact ended with an incomplete record: %s", path.name)
                continue
            raise ValueError(f"{path.name}: invalid memory record {index + 1}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}: memory record {index + 1} must be an object")
        records.append(record)
    return records


def summarize(sample_file: Path, process_file: Path, *, maximum: int) -> list[str]:
    samples = _records(sample_file, maximum)
    output: list[str] = []
    if samples is None:
        output.append(f"{sample_file.name} not found")
    elif not samples:
        output.append(f"{sample_file.name}: memory readings unavailable (0 samples)")
    else:
        llama = max((row.get("llama_vmhwm_kb") or 0 for row in samples), default=0)
        python_peak = max((row.get("python_vmhwm_kb") or 0 for row in samples), default=0)
        together = max(
            (
                (row.get("llama_vmrss_kb") or 0) + (row.get("python_vmrss_kb") or 0)
                for row in samples
            ),
            default=0,
        )
        output.append(
            f"peak llama VmHWM {llama} kB, peak python VmHWM {python_peak} kB, "
            f"most the two held at once {together} kB, n={len(samples)} samples"
        )
    roll_call = _records(process_file, maximum)
    if roll_call is None:
        output.append(f"{process_file.name} not found")
        return output
    peak: dict[str, int] = {}
    seen: Counter[str] = Counter()
    for row in roll_call:
        who = f"{row.get('pid')}  {row.get('comm')}  {row.get('exe')}  {row.get('args')}"
        peak[who] = max(peak.get(who, 0), row.get("vmrss_kb") or 0)
        seen[who] += 1
    output.extend(
        f"python {who} peak VmRSS {peak[who]} kB in {seen[who]} samples"
        for who in sorted(peak)
    )
    return output
