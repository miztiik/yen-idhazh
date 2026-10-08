"""Does the table of old CSV layouts agree with the registry and the declarations?

The table is held against the committed registry and recorded pre-expiry
compaction declarations. A ledger the table does not declare is refused by name.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from types import MappingProxyType
from typing import Final

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.knobs.gardener import CompactionPolicy, ForeverWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.contracts.seen import PublishedRow
from idhazh.contracts.story_similarity_pair import DROPPED_CELLS as PAIR_DROPPED_CELLS
from idhazh.contracts.story_similarity_pair import RENAMED_CELLS as PAIR_RENAMED_CELLS
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from utilities.ledger_migration import (
    csv_cells,
    csv_files,
    csv_layouts,
    refusals,
)

from ._fixtures import (
    EVALS,
    NEW,
    file_hashes,
    fixture_text,
    plan_named_roots,
    read_back,
    run_migration,
    score_row,
    write_csv,
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract

PAIRS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS
METRICS: Final = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS

#: One committed scored-pairs day as it stood before `decode_digest` left: the
#: `shard` heading, and filled cells under every heading the pair row dropped.
OLD_PAIRS: Final = FIXTURES_DIR / "state" / "scored-pairs-carrying-the-decode-digest.csv"


def test_a_declared_shared_day_file_is_read_under_two_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = LedgerName.PUBLISHED
    entry = csv_layouts.CsvLedger(
        LedgerEntry(name=old, grain=Grain.DAY_FILE, prefix=("family", "published"), suffix=".csv"),
        ForeverWindow(unit="forever"),
    )
    monkeypatch.setattr(
        csv_layouts, "CSV_LEDGERS",
        MappingProxyType(dict(csv_layouts.CSV_LEDGERS) | {old: entry}),
    )
    state = tmp_path / "state"
    assert csv_layouts.csv_root(state, old) == state / "family" / "published"
    cells = PublishedRow(
        version=PublishedRow.__changelog__[0].version,
        url_key="a" * 64, published_on=NEW, item_id="an-item-1234567890",
    ).csv_row()
    write_shared_csv(state, old, NEW, [cells])

    (moved,) = run_migration(state, old)
    assert (moved.days, moved.rows) == (1, 1)
    assert ledger.load_published(state, today=NEW, within_days=1) == {cells["url_key"]: NEW}
    source = csv_layouts.csv_root(state, old) / NEW[:4] / NEW[5:7] / f"{NEW[8:10]}.csv"
    assert not source.exists(), "the migrated source day file is retired"


def test_the_retired_council_converter_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(refusals.RefusedError, match="council-run-records: no supported CSV layout"):
        csv_layouts.csv_root(tmp_path, LedgerName.COUNCIL_RUN_RECORDS)


def test_the_eval_ledgers_csv_tree_is_read_where_its_old_name_filed_it(tmp_path: Path) -> None:
    """A re-run of a commit from before the rename writes its CSV day under `scores/`.

    That tree is the one this moves for the eval ledger, whatever the ledger is
    called now, so a late CSV file still reaches the door under the new name.
    """
    state = tmp_path / "state"
    assert csv_layouts.csv_root(state, EVALS) == state / "scores"
    write_csv(state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [score_row(NEW, 1).csv_row()])

    (moved,) = run_migration(state, EVALS)

    assert (moved.days, moved.rows) == (1, 1)
    assert list(read_back(state, EVALS, NEW).values()) == [score_row(NEW, 1).csv_row()]
    assert not (state / "scores").exists()


def test_the_holdout_score_is_read_where_the_recorded_registry_filed_it(tmp_path: Path) -> None:
    """One shared day file inside the judge's folder, so a check finds the file a person committed.

    Declared as a day tree instead, the reader would refuse that file as a day
    folder it cannot read, and no copy or check of the ledger could run.
    """
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES
    recorded = ledger.registry_entries(
        LedgersConfig.from_json((PRE_YEARLY_CONFIG / "ledgers.json").read_text(encoding="utf-8"))
    )
    state = tmp_path / "state"
    committed = state / "content-similarity-judge" / "merge-line-holdout-scores" / "2026" / "09" / "21.csv"
    committed.parent.mkdir(parents=True)
    committed.write_text("date,run_id\n2026-09-21,2026-09-21-1\n", encoding="utf-8", newline="")

    assert csv_layouts.CSV_LEDGERS[which].old_entry == recorded[which]
    assert csv_layouts.CSV_LEDGERS[which].old_headings == {"key_point_weight": None}
    assert csv_files.left(state, [which], months=["2026-09"]) == [committed]


def test_every_unmoved_table_entry_is_the_registry_entry() -> None:
    """A ledger still on CSV sits where the registry files it, so its move changes neither.

    Read off the committed `config/ledgers.json`: a change that files a ledger's
    CSV somewhere else, and leaves its table entry behind, fails here.
    """
    door = set(csv_layouts.door_ledgers(CONFIG_DIR))
    unmoved = [name for name in csv_layouts.CSV_LEDGERS if name not in door]

    assert {name: csv_layouts.CSV_LEDGERS[name].old_entry for name in unmoved} == {
        name: ledger.entry(name) for name in unmoved
    }


def test_the_ledgers_a_run_takes_by_default_are_the_ones_its_own_config_moved() -> None:
    """A run held against the recorded config takes what that config had moved, and no more.

    The holdout score moved after the config was recorded, so the committed
    registry files it through the door and the recorded one still files it as CSV.
    """
    holdout = LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES

    assert holdout in csv_layouts.door_ledgers(CONFIG_DIR)
    assert holdout not in csv_layouts.door_ledgers(PRE_YEARLY_CONFIG)


def test_every_moved_ledger_kept_its_old_window_before_yearly_expiry() -> None:
    """Recorded migration declarations preserve the windows held by the old CSV readers.

    The recorded config holds the ledgers that had moved before yearly expiry, so
    those are the ones checked here. A ledger moved since is declared with the
    approved yearly expiry from its first commit, and
    `backend/tests/contracts/test_gardener_config.py` holds that declaration.
    """
    recorded = ledger.registry_entries(
        LedgersConfig.from_json((PRE_YEARLY_CONFIG / "ledgers.json").read_text(encoding="utf-8"))
    )
    tasks = config.load_gardener(PRE_YEARLY_CONFIG).tasks
    moved = csv_layouts.door_ledgers(PRE_YEARLY_CONFIG)
    short: list[str] = []
    for name in moved:
        policy = tasks[config.compaction_task(name, registry=recorded)]
        assert isinstance(policy, CompactionPolicy), name
        if not config.compaction_reaches(policy, csv_layouts.CSV_LEDGERS[name].old_window):
            short.append(name.value)

    assert moved, "no ledger in the table has moved, so nothing is checked"
    assert short == []


def test_the_judges_two_ledgers_are_read_from_their_shared_day_files(tmp_path: Path) -> None:
    """Each sat as one CSV file a day in the judge's family folder, and nothing deleted it."""
    state = tmp_path / "state"
    for which in (PAIRS, METRICS):
        entry = csv_layouts.require_layout(which)

        assert (entry.grain, entry.suffix) == (Grain.DAY_FILE, ".csv"), which
        assert csv_layouts.csv_root(state, which) == state.joinpath(*ledger.door_folders(which))
        assert isinstance(csv_layouts.CSV_LEDGERS[which].old_window, ForeverWindow), which
        assert which in csv_layouts.door_ledgers(CONFIG_DIR), which


def test_an_old_scored_pairs_day_reads_its_part_and_drops_what_the_row_stopped_naming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed shape: `shard`, and three headings the pair row dropped, filled.

    `shard` is read as `work_part_index`, and each dropped heading's filled cell
    goes by declaration. The same file under a table that declares only the
    rename is refused, so no cell is lost without a line saying so.
    """
    state = tmp_path / "state"
    day = "2026-09-18"
    path = csv_layouts.csv_root(state, PAIRS) / day[:4] / day[5:7] / f"{day[8:10]}.csv"
    path.parent.mkdir(parents=True)
    shutil.copyfile(OLD_PAIRS, path)
    with OLD_PAIRS.open(encoding="utf-8", newline="") as handle:
        old = list(csv.DictReader(handle))

    assert csv_files.csv_days(state, PAIRS, months=[day[:7]]) == {day: [path]}
    rows = csv_cells.read_csv_rows(
        state, PAIRS, day, [path], ledger.door_key(PAIRS), StorySimilarityPair
    )

    assert [row["work_part_index"] for row in rows] == [cells["shard"] for cells in old]
    assert all(not set(row) & {"shard", *PAIR_DROPPED_CELLS} for row in rows)
    assert any(cells[name] for cells in old for name in PAIR_DROPPED_CELLS), (
        "the fixture holds no filled cell under a dropped heading, so the drop is unproved"
    )

    rename_only = csv_layouts.CSV_LEDGERS[PAIRS]._replace(old_headings=PAIR_RENAMED_CELLS)
    monkeypatch.setattr(
        csv_layouts,
        "CSV_LEDGERS",
        MappingProxyType(dict(csv_layouts.CSV_LEDGERS) | {PAIRS: rename_only}),
    )
    with pytest.raises(ValueError, match="is not declared"):
        csv_cells.read_csv_rows(
            state, PAIRS, day, [path], ledger.door_key(PAIRS), StorySimilarityPair
        )


def test_an_old_metrics_day_reads_its_part_under_the_new_name(tmp_path: Path) -> None:
    """A metrics day written while the row said `shard` reads back cell for cell."""
    state = tmp_path / "state"
    row = ContentSimilarityJudgeMetrics.from_json(
        fixture_text("content-similarity-judge-metrics", "a-shard-that-read-its-pairs.json")
    )
    cells = row.csv_row()
    old = {("shard" if name == "work_part_index" else name): cell for name, cell in cells.items()}
    path = write_shared_csv(state, METRICS, row.date, [old])

    rows = csv_cells.read_csv_rows(
        state,
        METRICS,
        row.date,
        [path],
        ledger.door_key(METRICS),
        ContentSimilarityJudgeMetrics,
    )

    assert rows == [cells]


def test_a_ledger_with_no_declared_csv_layout_is_refused_by_name(tmp_path: Path) -> None:
    which = LedgerName.VISUAL_PRUNES
    assert which not in csv_layouts.CSV_LEDGERS
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.RefusedError, match=rf"{which.value}: no supported CSV layout"):
        plan_named_roots([tmp_path], which)
    with pytest.raises(refusals.RefusedError, match=which.value):
        csv_layouts.csv_root(tmp_path, which)
    assert file_hashes(tmp_path) == before
