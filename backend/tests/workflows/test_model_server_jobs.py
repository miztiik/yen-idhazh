"""Does the server launcher validate calls and the configured destination first?"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from support.paths import read_text

from idhazh.contracts.base import canonical_json
from utilities import model_runtime

from ._harness import PROBE_URL_VALUE, START_SERVER_MODULE, _copy_config, _isolated_env

pytestmark = pytest.mark.workflow


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "required: verb"),
        (["summarize"], "invalid choice"),
        (["start-server", "--role", "gibberish"], "unrecognized arguments"),
    ],
)
def test_the_launcher_refuses_a_call_it_cannot_serve(
    argv: list[str], message: str, tmp_path: Path
) -> None:
    completed = subprocess.run(
        [sys.executable, str(START_SERVER_MODULE), *argv],
        cwd=tmp_path,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2, completed.stdout
    assert message in completed.stderr


def _a_config_root_posting_to(root: Path, base_url: str) -> Path:
    target = root / "config"
    _copy_config(target)
    payload = json.loads(read_text(target / "idhazh.json"))
    payload["model_server"]["base_url"] = base_url
    (target / "idhazh.json").write_text(
        canonical_json(payload), encoding="utf-8", newline="\n"
    )
    return target


def test_a_server_refuses_a_destination_its_stage_will_not_reach(tmp_path: Path) -> None:
    elsewhere = _a_config_root_posting_to(tmp_path, "http://192.168.1.20:9090")
    with pytest.raises(SystemExit) as refused:
        model_runtime.start_server(elsewhere, "llama-server")
    said = str(refused.value)
    assert "http://127.0.0.1:9090" in said
    assert "http://192.168.1.20:9090" in said
    assert elsewhere.as_posix() in said


def test_refusal_precedes_server_build_and_reads_the_configured_port(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    agreeing = _a_config_root_posting_to(tmp_path, PROBE_URL_VALUE)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        model_runtime.start_server(agreeing, "llama-server")
    assert "port_of_base_url(" in read_text(START_SERVER_MODULE)
