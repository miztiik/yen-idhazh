"""Does the table of old CSV layouts agree with the registry and the declarations?

The table is held against the committed registry and recorded pre-expiry
compaction declarations. A ledger the table does not declare is refused by name.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest
from conftest import CONFIG_DIR
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import CompactionPolicy, ForeverWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.contracts.seen import PublishedRow
from idhazh.contracts.similarity_holdout_pair import SimilarityHoldoutPair
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
    refusals,
)

from ._fixtures import (
    EVALS,
    NEW,
    file_hashes,
    plan_named_roots,
    read_back,
    run_migration,
    score_row,
    write_csv,
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


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


def test_the_holdout_marks_are_read_from_the_one_file_the_recorded_registry_named(
    tmp_path: Path,
) -> None:
    """One file in the judge's folder held every mark, and each row named its own day.

    The file's path names no day, so the table names the column the day is read
    from. A check of a month finds the file while it holds a row of that month,
    and names the file once however many days it holds.
    """
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS
    recorded = ledger.registry_entries(
        LedgersConfig.from_json((PRE_YEARLY_CONFIG / "ledgers.json").read_text(encoding="utf-8"))
    )
    state = tmp_path / "state"
    committed = state / "content-similarity-judge" / "holdout-pairs.csv"
    committed.parent.mkdir(parents=True)
    committed.write_text(
        "marked_on,note\n2026-09-19,a\n2026-09-20,b\n2026-10-02,c\n", encoding="utf-8", newline=""
    )

    assert csv_layouts.CSV_LEDGERS[which].old_entry == recorded[which]
    assert csv_layouts.CSV_LEDGERS[which].day_column == "marked_on"
    assert "marked_on" in SimilarityHoldoutPair.model_fields
    assert csv_files.csv_days(state, which, months=["2026-09"]) == {
        "2026-09-19": [committed],
        "2026-09-20": [committed],
    }
    assert csv_files.left(state, [which], months=["2026-09", "2026-10"]) == [committed]
    assert csv_files.left(state, [which], months=["2026-08"]) == []


def test_a_one_file_layout_is_read_only_where_the_table_names_its_day_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file whose path names no day cannot be placed on a day without a column that does."""
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS
    undated = csv_layouts.CSV_LEDGERS[which]._replace(day_column=None)
    monkeypatch.setattr(
        csv_layouts,
        "CSV_LEDGERS",
        MappingProxyType(dict(csv_layouts.CSV_LEDGERS) | {which: undated}),
    )

    with pytest.raises(refusals.RefusedError, match="unsupported CSV layout flat"):
        csv_layouts.csv_root(tmp_path, which)


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


def test_a_ledger_with_no_declared_csv_layout_is_refused_by_name(tmp_path: Path) -> None:
    which = LedgerName.VISUAL_PRUNES
    assert which not in csv_layouts.CSV_LEDGERS
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.RefusedError, match=rf"{which.value}: no supported CSV layout"):
        plan_named_roots([tmp_path], which)
    with pytest.raises(refusals.RefusedError, match=which.value):
        csv_layouts.csv_root(tmp_path, which)
    assert file_hashes(tmp_path) == before
