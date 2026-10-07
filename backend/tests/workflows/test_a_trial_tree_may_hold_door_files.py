"""May a trial tree carry the raw files the ledger door writes, and nothing else under `raw/`?

A test case run files its item-health, scores and host-fingerprint rows through
the ledger door, so the tree the commit job checks holds
`<root>/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.<format>` files beside the day
trees and traces. The check in `backend/utilities/pipeline_test_ledgers.py` is
the control for everything downstream of fetched text (Guardrail #11), so every
tree here is built by the door itself under a trial root the committed config
declares, and then one file at a time is put where no door writer puts it.
"""

from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from conftest import (
    CONFIG_DIR,
    read_text,
    seed_host_fingerprint,
    seed_item_health,
    seed_scores,
    writer_identity,
)

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import traces
from utilities import pipeline_test_ledgers

pytestmark = pytest.mark.workflow

#: The UTC day and the run every row here belongs to. Each tree is built under
#: `tmp_path`, so no test reads the committed state tree.
DAY: Final = "2026-09-22"
RUN_ID: Final = f"{DAY}-40000000001"


def _a_trial_tree(tmp_path: Path) -> tuple[Path, Path, frozenset[str]]:
    """The tree the commit job checks, the first declared trial root in it, and every root.

    The roots are read from the committed `config/pipeline-tests.json` inside the
    test, the way the check's own caller reads them, so a renamed test case moves
    these trees with it.
    """
    roots = pipeline_test_ledgers._roots(CONFIG_DIR)
    tree = tmp_path / ledger.STATE_DIRNAME
    return tree, tree / roots[0], frozenset(roots)


def _census_row(number: int) -> ItemHealthRow:
    """One published item of the test case run, as a work shard's census files it."""
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=DAY,
        run_id=RUN_ID,
        item_id=f"ai-{number:010d}",
        url_key=f"{number:064x}",
        canonical_url=f"https://example.com/items/{number}",
        vertical="ai",
        source_id="a-source",
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
    )


def _machine_row() -> HostFingerprintRow:
    """The machine the test case run's work job drew."""
    return HostFingerprintRow(
        version=HostFingerprintRow.schema_version(),
        date=DAY,
        run_id=RUN_ID,
        job=ServerJob.WORK,
        shard=0,
        cpu_model="AMD EPYC 7763 64-Core Processor",
    )


def _measurement() -> EvalRow:
    """One scored summary from the test case run."""
    return EvalRow(
        version=EvalRow.schema_version(),
        date=DAY,
        run_id=RUN_ID,
        item_id="ai-0000000001",
        url_key=f"{1:064x}",
        source_url="https://example.com/items/1",
        title="A story",
        vertical="ai",
        model_id="a-model",
        summary_attempt=1,
        hhem=0.9,
        hhem_full=0.9,
        hhem_delta=0.0,
        truncation_flagged=False,
        compression=0.2,
        extractiveness=0.4,
        band=ConfidenceBand.HIGH,
        summary_words=60,
        pipeline_fingerprint="b" * 64,
        output_digest="c" * 64,
        scorer_version="hhem-2.1",
        scored_at=f"{DAY}T06:10:00Z",
    )


def _file_census(root: Path) -> int:
    """Two census rows, filed through the door the way a work shard files them."""
    return seed_item_health(root, DAY, [_census_row(1), _census_row(2)])


def _file_machine(root: Path) -> int:
    """One machine row, filed through the door under the work job's own writer."""
    return seed_host_fingerprint(root, [_machine_row()])


def _file_measurement(root: Path) -> int:
    """One eval row, filed by the real eval writer."""
    return seed_scores(root, [_measurement()], run_id=RUN_ID)


@pytest.mark.parametrize(
    ("which", "file_rows"),
    [
        pytest.param(LedgerName.ITEM_HEALTH, _file_census, id="item-health"),
        pytest.param(LedgerName.HOST_FINGERPRINT, _file_machine, id="host-fingerprint"),
        pytest.param(
            LedgerName.SUMMARY_QUALITY_EVALS, _file_measurement, id="summary-quality-evals"
        ),
    ],
)
def test_the_check_passes_the_raw_files_a_test_case_run_files(
    tmp_path: Path, which: LedgerName, file_rows: Callable[[Path], int]
) -> None:
    """A test case run's door files are pushed, not refused.

    A check that knew only day trees and traces named every one of them a
    stray, so no dispatch could push its ledgers. The raw file is asserted to
    exist first, so a door that wrote nothing cannot pass this by leaving the
    check nothing to read.
    """
    tree, root, roots = _a_trial_tree(tmp_path)
    assert file_rows(root), f"no {which.value} row was filed"
    assert ledger.list_raw_files(root, which), f"the door wrote no raw {which.value} file"

    gathered = tmp_path / "trial-ledgers"
    pipeline_test_ledgers.gather(tree, gathered, roots=sorted(roots), days=[DAY])
    assert pipeline_test_ledgers.refusals(gathered, roots=roots) == []


def test_a_trace_still_passes_beside_the_door_files(tmp_path: Path) -> None:
    """A trace remains allowed beside raw ledger files."""
    tree, root, roots = _a_trial_tree(tmp_path)
    assert _file_census(root)
    assert _file_machine(root)
    trace = traces.committed_trace_path(
        root, run_id=RUN_ID, attempt=1, job=ServerJob.WORK, shard=0
    )
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_bytes(b'{"kind":"span","name":"item","duration_ms":1}\n')

    assert pipeline_test_ledgers.refusals(tree, roots=roots) == []


def test_a_door_file_under_a_root_no_test_case_declares_is_refused(tmp_path: Path) -> None:
    """A good raw file does not make its folder a trial root: the root is checked first."""
    tree, root, roots = _a_trial_tree(tmp_path)
    assert _file_census(root)
    stray = tree / "a-tenant"
    shutil.copytree(root, stray)
    [copied] = [path for path in stray.rglob("*") if path.is_file()]

    refused = pipeline_test_ledgers.refusals(tree, roots=roots)

    assert len(refused) == 1, refused
    assert copied.relative_to(tree).as_posix() in refused[0], refused


def _moved(source: Path, destination: Path) -> Path:
    """The file taken from where the door put it, to where it did not."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    return source.rename(destination)


def _copied(source: Path, destination: Path) -> Path:
    """A copy of the file, where the door put nothing."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def _written(destination: Path, data: bytes) -> Path:
    """A file the door did not write, at a path under the trial root."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def _renamed(root: Path, filed: Path) -> Path:
    """Its own folder, under a name that is not its own file id."""
    return _moved(filed, filed.with_name(f"{uuid.UUID(int=1)}{filed.suffix}"))


def _in_the_next_day(root: Path, filed: Path) -> Path:
    """Its own name, in the folder of a day its envelope does not cover."""
    return _moved(
        filed, ledger.raw_path(root, LedgerName.ITEM_HEALTH, "2026-09-23", uuid.UUID(filed.stem))
    )


def _under_another_door_ledger(root: Path, filed: Path) -> Path:
    """Its own name and day, in the folder of a door ledger its envelope does not name."""
    return _moved(
        filed, ledger.raw_path(root, LedgerName.HOST_FINGERPRINT, DAY, uuid.UUID(filed.stem))
    )


def _under_a_day_file_ledger(root: Path, filed: Path) -> Path:
    """A copy under `raw/metrics/`, a ledger that files one CSV file a day."""
    return _copied(
        filed,
        ledger.raw_path(root, LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS, DAY, uuid.UUID(filed.stem)),
    )


def _on_a_day_no_calendar_has(root: Path, filed: Path) -> Path:
    """Its own name under `2026/02/30`, three folders that spell no real day."""
    return _moved(
        filed, ledger.raw_path(root, LedgerName.ITEM_HEALTH, "2026-02-30", uuid.UUID(filed.stem))
    )


def _under_a_two_digit_year(root: Path, filed: Path) -> Path:
    """Its own name under `26/09/22`, which is not a `<YYYY>/<MM>/<DD>` folder."""
    return _moved(
        filed, ledger.raw_root(root, LedgerName.ITEM_HEALTH) / "26" / "09" / "22" / filed.name
    )


def _loose_in_the_ledger_folder(root: Path, filed: Path) -> Path:
    """Directly under `raw/item-health/`, in no day folder at all."""
    return _moved(filed, ledger.raw_root(root, LedgerName.ITEM_HEALTH) / filed.name)


def _a_compact_file(root: Path, filed: Path) -> Path:
    """A copy where a compaction files a day, which a test case run never does."""
    return _copied(filed, ledger.compact_path(root, LedgerName.ITEM_HEALTH, Period.DAILY, DAY))


def _not_a_ledger_file(root: Path, filed: Path) -> Path:
    """Plain text, neither container, under a name the door could have given a file."""
    return _written(
        ledger.raw_path(root, LedgerName.ITEM_HEALTH, DAY, uuid.UUID(int=2)),
        b"not a ledger file\n",
    )


def _a_row_its_contract_refuses(root: Path, filed: Path) -> Path:
    """A JSON-lines file the door wrote, with one row edited to an outcome no item has."""
    [written] = ledger.persist(
        root,
        [_census_row(3)],
        ledger=LedgerName.ITEM_HEALTH,
        covers=DAY,
        identity=writer_identity(RUN_ID, job=ServerJob.WORK, producer="tests.trial:json"),
        fmt=Format.JSON,
    )
    envelope, row, *rest = read_text(written).splitlines(keepends=True)
    cells = json.loads(row)
    cells["outcome"] = "exploded"
    edited = json.dumps(cells, sort_keys=True, separators=(",", ":")) + "\n"
    return _written(written, "".join([envelope, edited, *rest]).encode("ascii"))


@pytest.mark.parametrize(
    "misplace",
    [
        pytest.param(_renamed, id="renamed-away-from-its-file-id"),
        pytest.param(_in_the_next_day, id="moved-into-another-day"),
        pytest.param(_under_another_door_ledger, id="moved-under-another-ledger"),
        pytest.param(_under_a_day_file_ledger, id="a-day-file-ledger"),
        pytest.param(_on_a_day_no_calendar_has, id="a-day-no-calendar-has"),
        pytest.param(_under_a_two_digit_year, id="a-folder-that-is-not-a-year"),
        pytest.param(_loose_in_the_ledger_folder, id="in-no-day-folder"),
        pytest.param(_a_compact_file, id="a-compact-file"),
        pytest.param(_not_a_ledger_file, id="not-a-ledger-file"),
        pytest.param(_a_row_its_contract_refuses, id="a-row-its-contract-refuses"),
    ],
)
def test_the_check_refuses_a_file_the_door_did_not_put_there(
    tmp_path: Path, misplace: Callable[[Path, Path], Path]
) -> None:
    """The oracle for the third shape. A check nothing can fail is not a control.

    Each case starts from one file the door really wrote, then puts one file
    where no door writer puts it: under another name, day or ledger, under a
    ledger the door does not file, outside a real day folder, where only a
    compaction writes, or holding a row its contract refuses. The check has to
    name that file, and only that file, so the good file beside it still passes.
    """
    tree, root, roots = _a_trial_tree(tmp_path)
    [filed] = ledger.persist(
        root,
        [_census_row(1)],
        ledger=LedgerName.ITEM_HEALTH,
        covers=DAY,
        identity=writer_identity(RUN_ID, job=ServerJob.WORK),
    )
    offending = misplace(root, filed).relative_to(root).as_posix()

    refused = pipeline_test_ledgers.refusals(tree, roots=roots)

    assert len(refused) == 1, refused
    assert offending in refused[0], refused
