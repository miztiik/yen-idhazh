"""Do command entry points print the same UTC instant on every machine?"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXED_INSTANT = datetime(2026, 6, 1, 12, 34, 56, tzinfo=UTC)
FIXED_EPOCH = FIXED_INSTANT.timestamp()
EXPECTED_LINE = "2026-06-01T12:34:56.789Z WARNING utc.oracle fixed command message"

_DRIVER = r"""
import logging
import sys
import time

entrypoint, config_dir, state_root, digest_root, fixed_epoch = sys.argv[1:]
if entrypoint == "pipeline":
    from idhazh.cli import main
    result = main([
        "derived-paths", "--config", config_dir, "--day-dir", state_root,
    ])
else:
    from idhazh.cli import main
    result = main([
        "telemetry", "show", "--date", "2026-06-01", "--config", config_dir,
        "--state-root", state_root, "--digest-root", digest_root,
    ])
if result:
    raise SystemExit(result)

if hasattr(time, "tzset"):
    time.tzset()
record = logging.LogRecord(
    "utc.oracle", logging.WARNING, "oracle.py", 7, "fixed command message", (), None,
)
record.created = float(fixed_epoch)
record.msecs = 789
if time.localtime(record.created)[:6] == time.gmtime(record.created)[:6]:
    raise RuntimeError("the logging oracle requires a non-UTC process timezone")
root = logging.getLogger()
root.handle(record)
print(f"oracle-state:{root.level}:{len(root.handlers)}:{root.handlers[0].stream is sys.stderr}")
"""


def _can_run_non_utc_oracle() -> bool:
    return hasattr(time, "tzset") or time.localtime(FIXED_EPOCH)[:6] != time.gmtime(
        FIXED_EPOCH
    )[:6]


@pytest.mark.parametrize(
    ("entrypoint", "timezone_name"),
    [("pipeline", "Pacific/Honolulu"), ("telemetry", "Europe/Paris")],
)
@pytest.mark.skipif(
    not _can_run_non_utc_oracle(),
    reason="this platform cannot set or provide a non-UTC process timezone",
)
def test_real_entrypoints_format_fixed_log_record_in_utc(
    entrypoint: str, timezone_name: str, tmp_path: Path
) -> None:
    """Each real entry point keeps the record's instant, level and destination."""
    state_root = tmp_path / "state"
    digest_root = tmp_path / "digest"
    state_root.mkdir()
    digest_root.mkdir()
    environment = os.environ.copy()
    environment["TZ"] = timezone_name
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT / "backend"), environment.get("PYTHONPATH")) if part
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _DRIVER,
            entrypoint,
            str(REPO_ROOT / "config"),
            str(state_root),
            str(digest_root),
            str(FIXED_EPOCH),
        ],
        check=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=environment,
        text=True,
    )

    assert EXPECTED_LINE in completed.stderr.splitlines()
    assert f"oracle-state:{logging.INFO}:1:True" in completed.stdout.splitlines()
