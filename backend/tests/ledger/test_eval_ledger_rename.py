"""Does the eval ledger's rename move every file to its new name, row for row, and nothing else?

`tests/fixtures/eval-ledger-rename/state/` is a copy of files the committed
ledger held under its old names: two raw files of one day, two compact days -
one quiet, one holding rows - with their two day listings, their index cut to
those two days and their watermark, and two days of the ID folder.
`late/` holds one more raw file and one more ID file of the same day, as a run
that started before the rename would have filed them after the first move. Each
case copies the tree under `tmp_path` and runs the utility there, so nothing
here reads the committed `state/` (CLAUDE.md section 13).
"""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.evals import writer
from idhazh.ledger import json_lines, parquet
from utilities import eval_ledger_rename as rename

pytestmark = pytest.mark.contract

FIXTURE: Final = FIXTURES_DIR / "eval-ledger-rename"
LEDGER: Final = LedgerName.SUMMARY_QUALITY_EVALS
INDEX: Final = LedgerName.SUMMARY_QUALITY_EVALS_INDEX
#: What a rename may change in an envelope: the name, the digest and the engine.
RENAMED: Final = frozenset({b"ledger", b"content_sha256", b"writer_version"})
#: The day the raw files and the late files cover.
RAW_DAY: Final = "2026-09-30"


def _tree(tmp_path: Path) -> Path:
    """The fixture's old-name tree, copied where a run may change it."""
    state = tmp_path / "state"
    shutil.copytree(FIXTURE / "state", state)
    return state


def _files(root: Path) -> dict[str, bytes]:
    """Every file under one folder, by its POSIX path below it, with its bytes."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _new_roots(state: Path) -> tuple[Path, Path, Path]:
    """The three folders under the new names, in the order `old_roots` gives the old ones."""
    compact = ledger.compact_index_path(state, LEDGER, Period.DAILY).parent.parent
    return ledger.raw_root(state, LEDGER), compact, ledger.tree_root(state, INDEX)


def _new_address(state: Path, relpath: str) -> Path:
    """Where an old file must land: the same place below the folder's new name."""
    old = state / relpath
    for was, now in zip(rename.old_roots(state), _new_roots(state), strict=True):
        if old.is_relative_to(was):
            return now / old.relative_to(was)
    raise AssertionError(f"{relpath} is under none of the three old folders")


def _without(cells: dict[Any, Any], keys: frozenset[Any]) -> dict[Any, Any]:
    return {key: value for key, value in cells.items() if key not in keys}


def _sizes_dropped(payload: dict[str, Any]) -> dict[str, Any]:
    """A listing, index or watermark without its name, and without any entry's size."""
    entries = [_without(entry, frozenset({"bytes"})) for entry in payload.get("entries", [])]
    return _without(payload, frozenset({"ledger"})) | ({"entries": entries} if entries else {})


def _recorded(root: Path) -> set[str]:
    """Every digest the ID files under one folder hold, read straight off each CSV file."""
    held: set[str] = set()
    for path in root.rglob("*.csv"):
        with path.open("r", encoding="utf-8", newline="") as handle:
            held.update(record["observation_digest"] for record in csv.DictReader(handle))
    return held


def test_every_file_moves_under_the_new_names_and_reads_back_cell_for_cell(
    tmp_path: Path,
) -> None:
    """The four passes over the whole tree: read, write, read back, delete.

    Each ledger file holds the same rows in the same order with every cell
    equal but `ledger`, and every envelope key equal but `ledger`,
    `content_sha256` and `writer_version`. Each listing, index and watermark is
    equal but its name and its sizes, and each ID file is the same bytes.
    """
    state = _tree(tmp_path)
    before = _files(state)

    moved = rename.move(state)

    assert not any(root.exists() for root in rename.old_roots(state))
    assert (moved.files, moved.written, moved.already, moved.deleted) == (
        len(before),
        len(before),
        0,
        len(before),
    )
    rows = 0
    for relpath, data in before.items():
        new = _new_address(state, relpath)
        assert new.is_file(), f"{relpath} did not arrive at {new.relative_to(state).as_posix()}"
        if new.suffix == ".parquet":
            was_envelope, was_rows = parquet.read(data)
            now_envelope, now_rows = parquet.read(new.read_bytes())
            rows += len(was_rows)
            assert now_rows == [{**cells, "ledger": LEDGER.value} for cells in was_rows]
            assert _without(now_envelope, RENAMED) == _without(was_envelope, RENAMED)
            assert (was_envelope[b"ledger"], now_envelope[b"ledger"]) == (
                rename.OLD_LEDGER.encode(),
                LEDGER.value.encode(),
            )
        elif new.suffix == ".json":
            was, now = json.loads(data), json.loads(new.read_text(encoding="utf-8"))
            assert (was["ledger"], now["ledger"]) == (rename.OLD_LEDGER, LEDGER.value)
            assert _sizes_dropped(now) == _sizes_dropped(was)
        else:
            assert new.read_bytes() == data, f"{relpath} changed on its way across"
    assert (moved.ledger_files, moved.rows) == (4, rows)


def test_the_new_tree_is_what_this_builds_readers_serve(tmp_path: Path) -> None:
    """After the move the door reads every moved day and the dedupe holds every digest."""
    state = _tree(tmp_path)
    digests = _recorded(state / rename.OLD_INDEX)

    moved = rename.move(state)

    days = ledger.held_days(state, LEDGER)
    assert RAW_DAY in days and "2026-08-22" in days
    served = ledger.load_days(state, LEDGER, ["2026-08-21", "2026-08-22", RAW_DAY], model=EvalRow)
    assert (moved.days, moved.settled_rows) == (3, len(served))
    assert served, "the moved ledger serves no row"
    assert writer.recorded_observations(state) == digests
    assert moved.observations == len(digests)


def test_a_second_run_reads_nothing_and_writes_nothing(tmp_path: Path) -> None:
    state = _tree(tmp_path)
    rename.move(state)
    after_one = _files(state)

    assert rename.move(state) == rename.Moved()
    assert _files(state) == after_one


def test_a_file_filed_under_an_old_name_after_the_move_moves_on_the_next_run(
    tmp_path: Path,
) -> None:
    """A run that started before the rename files under the old names; the next run moves it."""
    state = _tree(tmp_path)
    rename.move(state)
    shutil.copytree(FIXTURE / "late", state, dirs_exist_ok=True)
    late = _files(FIXTURE / "late")

    moved = rename.move(state)

    assert (moved.files, moved.written, moved.deleted, moved.ledger_files) == (2, 2, 2, 1)
    assert not any(root.exists() for root in rename.old_roots(state))
    for relpath in late:
        assert _new_address(state, relpath).is_file()
    raw = ledger.list_raw_files(state, LEDGER, days={RAW_DAY})
    assert len(raw) == 3, "the late raw file sits beside the two the first run moved"
    served = ledger.load_days(state, LEDGER, [RAW_DAY], model=EvalRow)
    assert (moved.days, moved.settled_rows) == (1, len(served))


def _occupied(state: Path) -> None:
    """A new address already holds other bytes than the old file becomes."""
    taken = ledger.raw_index_path(state, LEDGER, "2026-08-22")
    taken.parent.mkdir(parents=True)
    taken.write_text("{}\n", encoding="utf-8")


def _unreadable(state: Path) -> None:
    """One old raw file is no longer a parquet file."""
    spoiled = next(rename.old_roots(state)[0].rglob("*.parquet"))
    spoiled.write_bytes(b"PAR1 and then nothing a reader can use")


@pytest.mark.parametrize("spoil", [_occupied, _unreadable], ids=["occupied", "unreadable"])
def test_a_refusal_before_any_write_writes_nothing_and_deletes_nothing(
    tmp_path: Path, spoil: Callable[[Path], None], capsys: pytest.CaptureFixture[str]
) -> None:
    state = _tree(tmp_path)
    spoil(state)
    before = _files(state)

    assert rename.main(["--state-dir", str(state)]) == rename.EXIT_NOT_PROVEN

    assert _files(state) == before
    assert "not proven, nothing deleted" in capsys.readouterr().err


def _cell_changed(state: Path, plan: rename.Plan) -> Path:
    """A written ledger file whose first row lost one cell's value."""
    target = next(each for each in plan.refiled if each.built.rows)
    envelope, rows = parquet.read(target.built.path.read_bytes())
    rows[0] = {**rows[0], "run_id": "2026-01-01-1"}
    target.built.path.write_bytes(json_lines.render(rows, envelope=envelope))
    return target.built.path


def _envelope_changed(state: Path, plan: rename.Plan) -> Path:
    """A written ledger file whose envelope says it was written at another instant."""
    target = plan.refiled[0]
    envelope, rows = parquet.read(target.built.path.read_bytes())
    stamped = envelope | {b"written_at_ms": b"1"}
    target.built.path.write_bytes(json_lines.render(rows, envelope=stamped))
    return target.built.path


def _bytes_changed(state: Path, plan: rename.Plan) -> Path:
    """A moved ID file with one more line than the old one held."""
    target = next(each for each in plan.moves if each.payload is None)
    target.new.write_bytes(target.data + b"x\n")
    return target.new


@pytest.mark.parametrize(
    "spoil",
    [_cell_changed, _envelope_changed, _bytes_changed],
    ids=["cell", "envelope", "id-file"],
)
def test_the_read_back_refuses_a_written_file_that_is_not_the_old_one_renamed(
    tmp_path: Path, spoil: Callable[[Path, rename.Plan], Path]
) -> None:
    """The third pass reads every new file back, so one written wrong stops the run.

    The passes are run one by one, and one written file is spoiled between the
    second and the third, as a write that went wrong would leave it.
    """
    state = _tree(tmp_path)
    before = _files(state)
    plan = rename.plan_move(state)
    rename.write(plan)
    spoiled = spoil(state, plan)

    with pytest.raises(rename.NotProvenError, match="does not read back") as refused:
        rename.prove(state, plan)

    assert spoiled.relative_to(state).as_posix() in str(refused.value)
    assert {relpath: data for relpath, data in _files(state).items() if relpath in before} == before


def test_check_names_every_file_left_under_an_old_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = _tree(tmp_path)
    left = len(_files(state))

    assert rename.main(["--state-dir", str(state), "--check"]) == rename.EXIT_NOT_PROVEN
    assert f"{left} file(s) left under an old name" in capsys.readouterr().out
    assert len(_files(state)) == left, "a check wrote or deleted a file"

    assert rename.main(["--state-dir", str(state)]) == rename.EXIT_MOVED
    assert rename.main(["--state-dir", str(state), "--check"]) == rename.EXIT_MOVED


def test_a_rename_refuses_a_column_the_contract_does_not_declare(tmp_path: Path) -> None:
    """A column the container would drop in silence is refused, so no cell is lost."""
    data = (FIXTURE / "state" / "compact" / rename.OLD_LEDGER / "daily").joinpath(
        "2026", "08", "22.parquet"
    )
    metadata, rows = parquet.read(data.read_bytes())

    with pytest.raises(ValueError, match="does not declare"):
        ledger.render_renamed(
            tmp_path,
            metadata,
            [{**cells, "a_stray_column": "kept nowhere"} for cells in rows],
            model=EvalRow,
            ledger=LEDGER,
        )
