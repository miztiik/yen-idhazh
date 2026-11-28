"""Can the native probe client pin only the requested process?"""

from pathlib import Path

import pytest

from idhazh import cli
from idhazh.telemetry import host


@pytest.mark.parametrize("pid", ["0", "-1", "not-a-pid"])
def test_work_cli_refuses_nonpositive_or_malformed_process_identity(pid: str) -> None:
    with pytest.raises(SystemExit) as refused:
        cli.main(["work", "--server-pid", pid])
    assert refused.value.code == 2


def test_process_pin_requires_the_named_live_stat_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(host, "PROC", tmp_path)
    named = tmp_path / "742" / "stat"
    assert host.process_start_ticks(742) is None
    named.parent.mkdir()
    named.write_text(
        "742 (recorded server (ggml)) S 1 742 742 0 -1 0 900 0 7 0 0 0 0 0 20 0 1 0 12345\n",
        encoding="ascii",
    )
    assert host.process_start_ticks(742) == 12345
    named.write_bytes(named.read_bytes().replace(b"742 (", b"743 (", 1))
    assert host.process_start_ticks(742) is None
