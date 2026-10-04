"""Does every printed path stay relative to the checkout and POSIX?"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.base import ServerJob
from utilities.ledger_migration import (
    path_labels,
    refusals,
)

from ._fixtures import (
    HOST,
    OLD,
    file_hashes,
    plan_named_roots,
    probe_row,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


@pytest.mark.skipif(os.name != "nt", reason="separate Windows drives are required")
def test_label_path_falls_back_to_the_folder_name_on_another_drive() -> None:
    drive = "Z:" if REPO_ROOT.drive.upper() != "Z:" else "Y:"
    assert path_labels.label_path(Path(drive + "\\outside-checkout")) == "outside-checkout"


def test_filesystem_errors_use_relative_posix_labels(tmp_path: Path) -> None:
    folder = tmp_path / "unreadable.csv"
    folder.mkdir()
    with pytest.raises(OSError) as failed:
        folder.open("r", encoding="utf-8")
    message = path_labels.describe_error(failed.value)
    assert folder.name in message
    assert str(tmp_path) not in message
    assert tmp_path.as_posix() not in message
    assert "\\" not in message
    if tmp_path.drive:
        assert tmp_path.drive not in message


@pytest.mark.skipif(os.name != "nt", reason="Windows mandatory file locks are required")
def test_an_unreadable_csv_refusal_does_not_print_an_absolute_path(tmp_path: Path) -> None:
    import msvcrt

    root = tmp_path / "trial"
    source = write_csv(root, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [probe_row(OLD).csv_row()])
    before = file_hashes(tmp_path)
    with source.open("r+b") as handle:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with pytest.raises(refusals.NotProvenError) as refused:
                plan_named_roots([root], HOST)
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    message = str(refused.value)
    assert HOST.value in message and OLD in message
    assert str(tmp_path) not in message and tmp_path.as_posix() not in message
    assert "\\" not in message
    assert file_hashes(tmp_path) == before
