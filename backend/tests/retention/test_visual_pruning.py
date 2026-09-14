"""Which pictures may be deleted, how are they found, and what does a run say it left?"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import ledger, retention
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.retention import SiteSize, measure, oldest_visual, prune, prune_row, visuals_older_than
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    PRUNE_RUN_ID,
    site,
)

pytestmark = pytest.mark.slow


def test_only_visuals_are_candidates(tmp_path: Path) -> None:
    """A visual is a file named for an item, and nothing else in a day is.

    It was a set of image suffixes until 2026-09-13, when the reader's browser
    took over the drawing and a visual became a `.json` document - the same
    extension the day's own payloads carry. Reading identity instead of
    extension is what keeps those safe, and it needs no list of names to skip.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp", "notes.txt"]})
    found = visuals_older_than(root, date(2026, 8, 21))
    assert [path.name for path in found] == ["old-0000000003.webp"]


def test_the_day_s_own_payloads_are_never_candidates(tmp_path: Path) -> None:
    """`digest.json` is the record that a day happened and is never deleted.

    It sits in the same directory as a visual and now carries the same
    extension, so this is the arm that would have caught the cheap version of
    this change - adding `.json` to a suffix set. `run.json` is here for the
    same reason: it walked straight through the deny-list that named only
    `digest.json`, which is why there is no deny-list any more.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.json"]})
    (root / "2020" / "01" / "01" / "run.json").write_text('{"n": 1}', encoding="utf-8")

    found = visuals_older_than(root, date(2026, 8, 21))

    assert [path.name for path in found] == ["old-0000000003.json"]


def test_an_enabled_policy_keeps_both_of_the_day_s_own_payloads(tmp_path: Path) -> None:
    """The prune runs for real, and the two files it may never touch are still there."""
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.json"]})
    (root / "2020" / "01" / "01" / "run.json").write_text('{"n": 1}', encoding="utf-8")

    result = prune(root, RetentionConfig(image_months=6, dry_run=False), date(2026, 8, 21))

    assert result.deleted == 1
    assert not (root / "2020" / "01" / "01" / "old-0000000003.json").exists()
    assert (root / "2020" / "01" / "01" / "digest.json").exists()
    assert (root / "2020" / "01" / "01" / "run.json").exists()


def test_a_recent_day_is_never_a_candidate(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["new-0000000004.webp"]})
    assert visuals_older_than(root, date(2026, 1, 1)) == []


def test_a_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    config = RetentionConfig(image_months=6, dry_run=True)
    result = prune(root, config, date(2026, 8, 21))
    assert result.considered == 1
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()


def test_an_enabled_policy_deletes_the_old_visual_and_keeps_the_day(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    config = RetentionConfig(image_months=6, dry_run=False)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 1
    assert not (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()
    assert (root / "2020" / "01" / "01" / "digest.json").exists(), "the day survives its picture"


def test_the_fuse_caps_what_one_run_can_delete(tmp_path: Path) -> None:
    """An off-by-one in a date parse must not eat the archive."""
    root = site(tmp_path, {"2020-01-01": [f"p-{n:010d}.webp" for n in range(10)]})
    config = RetentionConfig(image_months=6, dry_run=False, max_deletes_per_run=3)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 3
    assert result.fuse_tripped
    assert result.considered == 10


#: The first published day of the trees the four tests below run against. They
#: are built here rather than read off `frontend/public/digest/`, so what these
#: tests cost never moves with what the pipeline has published (Guardrail #12,
#: section 13).
SCAN_START: Final = date(2019, 1, 1)


#: Days in the big arm. 400 puts fourteen calendar months on the tree and leaves
#: the cutoff a long way inside it, so a walk that stopped early shows up as a
#: missing month rather than as a rounding difference.
SCAN_DAYS: Final = 400


#: Days in the small arm. Both arms hold the same expired days; every day they
#: do not share is inside the window, which is the side the archive grows on.
SCAN_SMALL_DAYS: Final = 260


#: How far into both trees the cutoff falls, in days from `SCAN_START`.
SCAN_EXPIRED_DAYS: Final = 250


#: The cutoff itself, and the expired days it names: 2019-01-01 to 2019-09-07.
SCAN_LIMIT: Final = SCAN_START + timedelta(days=SCAN_EXPIRED_DAYS)


def day_folder(root: Path, day: date) -> Path:
    """Where a published day sits, spelled out apart from the code under test."""
    year, month, number = day.isoformat().split("-")
    return root / year / month / number


def dated_tree(root: Path, *, days: int, pictures: int) -> Path:
    """`days` consecutive published days from `SCAN_START`, `pictures` on each."""
    return site(
        root,
        {
            (SCAN_START + timedelta(days=n)).isoformat(): [f"p-{i:010d}.webp" for i in range(pictures)]
            for n in range(days)
        },
    )


def by_sorting_the_whole_tree(root: Path, limit: date) -> list[Path]:
    """The reference answer: sort every path under the root, then filter.

    This is the shape the scan used to have, written out here so the cheaper one
    has something to be equal to. It may cost whatever it likes - it runs over a
    fixture of fixed size, never over the archive.
    """
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not re.match(ITEM_ID_PATTERN, path.stem):
            continue
        parts = path.relative_to(root).parts
        if len(parts) < 3:
            continue
        try:
            published = date.fromisoformat("-".join(parts[:3]))
        except ValueError:
            continue
        if published < limit:
            found.append(path)
    return found


def directories_opened_during(work: Callable[[], object]) -> list[Path]:
    """Every directory an operation opens, in the order it opened them.

    Counted rather than timed, for the reason `reads_during` above is: a timing
    assertion is flaky and says nothing about what the code read, and what this
    section is about is what gets read. `os.scandir` is the call both
    `Path.iterdir` and `Path.rglob` reach for on this interpreter - checked on
    CPython 3.14.2, 2026-09-07 - and `os.listdir` is patched beside it so a
    rewrite onto that call cannot make the count silently fall to zero.
    """
    opened: list[Path] = []
    real_scandir, real_listdir = os.scandir, os.listdir

    def scandir(path: Any = ".", *args: Any, **kwargs: Any) -> Any:
        opened.append(Path(path))
        return real_scandir(path, *args, **kwargs)

    def listdir(path: Any = ".", *args: Any, **kwargs: Any) -> Any:
        opened.append(Path(path))
        return real_listdir(path, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "scandir", scandir)
        patch.setattr(os, "listdir", listdir)
        work()
    return opened


def opened_by_depth(root: Path, work: Callable[[], object]) -> dict[int, set[str]]:
    """What a scan opened, by how deep under its own root it was.

    Keyed relative to the root so two trees can be compared: depth 3 is a day
    directory, and depths 0 to 2 are the root, a year and a month.
    """
    by_depth: dict[int, set[str]] = {}
    for path in directories_opened_during(work):
        if path != root and root not in path.parents:
            continue
        relative = path.relative_to(root)
        by_depth.setdefault(len(relative.parts), set()).add(relative.as_posix())
    return by_depth


def test_the_scan_finds_exactly_what_sorting_the_whole_tree_found(tmp_path: Path) -> None:
    """The oracle. A cheaper walk that finds a different set is a different policy.

    Order is asserted as well as membership, because `prune` hands the fuse
    `candidates[:max_deletes_per_run]`. The order decides WHICH files a fused run
    deletes, not only how many, so a reordering silently changes what a capped
    run takes and what it leaves for the next one.
    """
    root = dated_tree(tmp_path, days=SCAN_DAYS, pictures=2)

    found = visuals_older_than(root, SCAN_LIMIT)

    assert found == by_sorting_the_whole_tree(root, SCAN_LIMIT)
    assert len(found) == 500, "250 expired days, two pictures on each"
    assert oldest_visual(root) == SCAN_START


def test_the_scan_opens_the_expired_days_and_never_a_day_inside_the_window(
    tmp_path: Path,
) -> None:
    """Guardrail #12, counted. A day the policy keeps is a day the policy need not read.

    The old shape sorted every path under the root, so it opened all 400 day
    directories to select the 250 it wanted - and that count rose every day
    nobody wrote any code.
    """
    root = dated_tree(tmp_path, days=SCAN_DAYS, pictures=1)
    expired = {
        day_folder(root, SCAN_START + timedelta(days=n)).relative_to(root).as_posix()
        for n in range(SCAN_EXPIRED_DAYS)
    }

    opened = opened_by_depth(root, lambda: visuals_older_than(root, SCAN_LIMIT))

    assert opened.get(3, set()) == expired, "the expired days, and only those"
    assert opened.get(4) is None, "a published day holds files, so nothing below it opens"
    assert opened[0] == {"."}
    assert opened[1] == {"2019"}, "2020 begins after the cutoff and is skipped by name"
    assert opened[2] == {f"2019/{month:02d}" for month in range(1, 10)}, (
        "January to September 2019 - the months that can hold a day older than "
        "2019-09-08. October onwards is refused by its name"
    )


def test_a_bigger_archive_does_not_make_the_scan_read_more(tmp_path: Path) -> None:
    """Two trees, the same backlog, and the same reads.

    The large arm carries 140 more published days and 3,080 more files, all of
    them inside the window. Guardrail #12's question is whether a run that changed no
    code costs more because an earlier run appended - so the two scans have to
    open the same directories, not merely find the same files.
    """
    small = dated_tree(tmp_path / "small", days=SCAN_SMALL_DAYS, pictures=1)
    large = dated_tree(tmp_path / "large", days=SCAN_DAYS, pictures=8)

    read_small = opened_by_depth(small, lambda: visuals_older_than(small, SCAN_LIMIT))
    read_large = opened_by_depth(large, lambda: visuals_older_than(large, SCAN_LIMIT))

    assert read_small == read_large
    assert sum(len(names) for names in read_large.values()) == 261, (
        "the root, 2019, nine months and 250 expired days"
    )
    assert len(visuals_older_than(large, SCAN_LIMIT)) == 8 * SCAN_EXPIRED_DAYS
    assert len(visuals_older_than(small, SCAN_LIMIT)) == SCAN_EXPIRED_DAYS


def test_the_oldest_picture_is_found_without_opening_the_rest_of_the_archive(
    tmp_path: Path,
) -> None:
    """The one that costs on every run today.

    `image_months` is 13 and the oldest visual on disk is weeks old, so
    `visuals_older_than` returns nothing until 2027 - and `prune` still asks for
    the oldest picture on every path through
    it, including the one that returns early. That question is answered by the
    first day that still holds a picture, so it stops there.
    """
    root = dated_tree(tmp_path, days=SCAN_DAYS, pictures=1)

    opened = opened_by_depth(root, lambda: oldest_visual(root))

    assert oldest_visual(root) == SCAN_START
    assert opened == {0: {"."}, 1: {"2019"}, 2: {"2019/01"}, 3: {"2019/01/01"}}


def test_a_name_inside_the_dated_tree_that_is_not_a_date_is_a_fault(tmp_path: Path) -> None:
    """Under a year directory the layout is ours, so an unreadable name is a bug.

    A skip here would leave files the cleanup cannot account for, silently, for
    as long as whatever wrote them keeps writing. The root above is the other
    way round and stays that way - see the stray-directory test further down.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    (root / "2020" / "notes.txt").write_bytes(b"x")

    with pytest.raises(ValueError, match=r"2020/notes\.txt is not a month"):
        visuals_older_than(root, date(2026, 8, 21))


def test_the_run_reports_the_backlog_the_fuse_left_behind(tmp_path: Path) -> None:
    """The row's whole point. `deleted` is capped, so `deleted` cannot answer this.

    300 candidates against the shipped 200-file fuse, and the shipped fuse rather
    than a scaled-down one - the question is whether the number an operator
    actually reads can distinguish a finished run from a stuck one.

    A run that deleted 200 and skipped 0 has cleared its backlog. A run that
    deleted 200 and skipped 100 has not. `deleted` is 200 in both.
    """
    root = site(tmp_path, {"2020-01-01": [f"p-{n:010d}.webp" for n in range(300)]})
    config = RetentionConfig(image_months=6, dry_run=False)
    assert config.max_deletes_per_run == 200

    result = prune(root, config, date(2026, 8, 21))

    assert result.deleted == config.max_deletes_per_run
    assert result.skipped_by_fuse == 100, "the 100 the fuse would not let this run reach"
    assert result.fuse_tripped
    assert result.deleted + result.skipped_by_fuse == result.considered == 300

    finished = prune(root, config, date(2026, 8, 21))
    assert finished.deleted == 100
    assert finished.skipped_by_fuse == 0, "a second pass clears what the first could not"
    assert not finished.fuse_tripped


def test_a_dry_run_reports_the_same_backlog_it_would_have_left(tmp_path: Path) -> None:
    """ "Held back by the fuse" and "not deleted because we were pretending" differ.

    Every run that ships today is a dry run, so a `skipped_by_fuse` that counted
    the deletions a dry run declined to make would equal `candidates_found` on
    every row this project will ever write, and the field would say nothing.

    The dry run's own tell is the sum falling short: 0 deleted plus 100 skipped
    against 300 found is a run that reported, and it is readable off the numbers
    without cross-referencing the `dry_run` cell.
    """
    root = site(tmp_path, {"2020-01-01": [f"p-{n:010d}.webp" for n in range(300)]})
    config = RetentionConfig(image_months=6, dry_run=True)

    result = prune(root, config, date(2026, 8, 21))

    assert result.dry_run
    assert result.deleted == 0
    assert result.considered == 300
    assert result.skipped_by_fuse == 100, "the fuse's own count, unchanged by the pretending"
    assert result.deleted + result.skipped_by_fuse < result.considered
    assert len(list(root.rglob("*.webp"))) == 300


def test_the_flag_can_only_make_a_run_report_and_never_delete(tmp_path: Path) -> None:
    """The step's flag is added to `retention.dry_run`, never subtracted from it.

    There is no argument that turns deletion on, which is what keeps the two
    guards independent: a workflow edit alone cannot make this delete.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})
    live = RetentionConfig(image_months=6, dry_run=False)

    assert prune(root, live, date(2026, 8, 21), dry_run=True).deleted == 0
    assert (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()

    shipped = RetentionConfig(image_months=6, dry_run=True)
    assert prune(root, shipped, date(2026, 8, 21), dry_run=False).deleted == 0
    assert (root / "2020" / "01" / "01" / "old-0000000003.webp").exists()


def test_the_bytes_are_the_files_that_actually_left_the_tree(
    tmp_path: Path,
) -> None:
    """`bytes_reclaimed` is what the deletions removed, and it agrees with a fresh walk.

    It used to be the difference between two whole-tree readings, which is a
    second walk of everything ever published to learn the size of two pictures.
    The reading that made that safe - a total cannot inflate past what the tree
    really holds - is kept by the last line here, and by
    `test_the_after_total_counts_only_the_files_that_actually_left` below.
    """
    root = site(tmp_path, {"2020-01-01": ["a-0000000001.webp", "b-0000000002.webp"], "2026-08-20": ["new-0000000004.webp"]})
    config = RetentionConfig(image_months=6, dry_run=False)

    result = prune(root, config, date(2026, 8, 21))

    assert result.deleted == 2
    assert result.bytes_reclaimed == 2000, "the two 1,000-byte pictures and nothing else"
    assert result.bytes_before - result.bytes_after == result.bytes_reclaimed
    assert result.bytes_after == measure(root).bytes_used


def test_a_prune_reaches_its_after_total_without_walking_the_tree_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One reading of the tree a pass, not two.

    The second walk answered a question the pass already knew the answer to: it
    had just removed the files, so it had their sizes. Counted rather than timed,
    because the cost this row is about is what gets read.
    """
    root = site(tmp_path, {"2020-01-01": ["a-0000000001.webp", "b-0000000002.webp"], "2026-08-20": ["new-0000000004.webp"]})
    walked = 0
    unpatched = retention.measure

    def counted(*args: Any, **kwargs: Any) -> SiteSize:
        nonlocal walked
        walked += 1
        return unpatched(*args, **kwargs)

    monkeypatch.setattr(retention, "measure", counted)
    result = prune(root, RetentionConfig(image_months=6, dry_run=False), date(2026, 8, 21))

    assert result.deleted == 2
    assert walked == 1, "the tree is read once and the after-total retracts what left it"
    assert result.bytes_after == unpatched(root).bytes_used


def test_the_after_total_counts_only_the_files_that_actually_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hazard a carried total has that two readings did not.

    A total that subtracts every file the pass meant to delete would still be
    written when an unlink did not happen, and nothing would disagree with it. So
    the pass retracts a file only once the file is gone, and one that stayed is
    charged to neither number.
    """
    root = site(tmp_path, {"2020-01-01": ["a-0000000001.webp", "b-0000000002.webp"], "2026-08-20": ["new-0000000004.webp"]})
    stubborn = root / "2020" / "01" / "01" / "b-0000000002.webp"
    unpatched = Path.unlink

    def refuse(self: Path, *args: Any, **kwargs: Any) -> None:
        if self != stubborn:
            unpatched(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse)
    result = prune(root, RetentionConfig(image_months=6, dry_run=False), date(2026, 8, 21))
    monkeypatch.undo()

    assert stubborn.exists(), "the fixture has to leave one file behind or it proves nothing"
    assert result.bytes_reclaimed == 1000, "one picture left the tree, not the two it tried"
    assert result.bytes_after == measure(root).bytes_used


def test_the_oldest_picture_kept_says_whether_the_policy_has_caught_up(tmp_path: Path) -> None:
    """Read against the cutoff, and a tree with no picture at all says so.

    None is a different fact from "the oldest one is recent", and a stand-in date
    would read like the second.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"], "2026-08-20": ["new-0000000004.webp"]})
    config = RetentionConfig(image_months=6, dry_run=False)

    result = prune(root, config, date(2026, 8, 21))

    assert result.cutoff_date is not None
    assert result.oldest_kept == date(2026, 8, 20)
    assert result.oldest_kept >= result.cutoff_date, "nothing older than the line is left"

    text_only = site(tmp_path / "text", {"2026-08-20": []})
    assert prune(text_only, config, date(2026, 8, 21)).oldest_kept is None


def test_a_switched_off_policy_still_reports_the_tree_it_looked_at(tmp_path: Path) -> None:
    """What ships today. A report of "nothing to do" is not a row worth skipping.

    A ledger written only on the runs that deleted something has no baseline, so
    the first row would arrive on the day the policy started working and there
    would be nothing to compare it against.
    """
    root = site(tmp_path, {"2020-01-01": ["old-0000000003.webp"]})

    result = prune(root, RetentionConfig(), date(2026, 8, 21))

    assert result.cutoff_date is None, "a disabled policy draws no line"
    assert result.considered == 0
    assert result.skipped_by_fuse == 0
    assert result.oldest_kept == date(2020, 1, 1), "the backlog is still reported"
    assert result.bytes_before == result.bytes_after == measure(root).bytes_used


def test_the_row_carries_the_policy_that_produced_it(tmp_path: Path) -> None:
    """Every cell an operator needs to read one run without opening config.

    The policy is on the row rather than looked up, because config moves and a
    row read a year later has to say which policy it was written under.
    """
    root = site(tmp_path, {"2020-01-01": [f"p-{n:010d}.webp" for n in range(300)]})
    config = RetentionConfig(image_months=6, dry_run=False)

    row = prune_row(
        prune(root, config, date(2026, 8, 21)),
        config,
        date_stamp="2026-08-21",
        run_id=PRUNE_RUN_ID,
    )

    assert row.policy_months == 6
    assert row.max_deletes_per_run == 200
    assert row.cutoff_date == "2026-02-22", "six 30-day months back from 2026-08-21"
    assert row.candidates_found == 300
    assert row.deleted == 200
    assert row.skipped_by_fuse == 100
    assert row.fuse_tripped
    assert row.bytes_reclaimed == 200_000
    assert row.payload_bytes_before - row.payload_bytes_after == row.bytes_reclaimed
    assert VisualPruneRow.from_csv_row(row.csv_row()) == row


def test_the_row_refuses_arithmetic_that_does_not_add_up() -> None:
    """The cells are cross-checked, so a hand-written row cannot claim two things.

    Both directions, because a rule tested one way is not a rule: a live run's
    deletions and skips have to account for everything it found, and a dry run
    has to have deleted nothing.
    """
    honest: dict[str, Any] = {
        "date": "2026-08-21",
        "run_id": PRUNE_RUN_ID,
        "policy_months": 6,
        "max_deletes_per_run": 200,
        "dry_run": False,
        "cutoff_date": "2025-02-22",
        "candidates_found": 300,
        "deleted": 200,
        "skipped_by_fuse": 100,
        "fuse_tripped": True,
        "bytes_reclaimed": 200_000,
        "oldest_kept": "2025-03-01",
        "payload_bytes_before": 500_000,
        "payload_bytes_after": 300_000,
    }
    assert VisualPruneRow(**honest).candidates_found == 300

    with pytest.raises(ValueError, match="add up"):
        VisualPruneRow(**{**honest, "skipped_by_fuse": 0, "fuse_tripped": False})
    with pytest.raises(ValueError, match="say the same thing"):
        VisualPruneRow(**{**honest, "fuse_tripped": False})
    with pytest.raises(ValueError, match="difference"):
        VisualPruneRow(**{**honest, "bytes_reclaimed": 1})
    with pytest.raises(ValueError, match="deletes nothing"):
        VisualPruneRow(**{**honest, "dry_run": True})
    with pytest.raises(ValueError, match="no cutoff"):
        VisualPruneRow(**{**honest, "policy_months": -1})


def test_the_step_commits_one_row_a_run_and_names_what_it_left(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """End to end through the stage, on the shipped policy and on a live one.

    `state_dir` and `digest_root` are named together, so nothing here can reach
    the committed archive.
    """
    state = tmp_path / "state"
    digest = site(tmp_path / "public", {"2020-01-01": [f"p-{n:010d}.webp" for n in range(300)]})

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(image_months=6, dry_run=False),
                run_id=PRUNE_RUN_ID,
                today=date(2026, 8, 21),
                state_dir=state,
                digest_root=digest,
            )
            == 0
        )

    written = ledger.visual_prunes_path(state, "2026-08-21")
    assert ledger.read_header(written) == VisualPruneRow.csv_columns()
    rows = ledger.load_visual_prunes(state)
    assert len(rows) == 1
    assert (rows[0].deleted, rows[0].skipped_by_fuse) == (200, 100)
    assert "100 held back by the 200-file fuse" in caplog.text

    repeat = stage_prune_state(
        observability=ObservabilityConfig(),
        collect=CollectConfig(),
        retention_config=RetentionConfig(image_months=6, dry_run=False),
        run_id=PRUNE_RUN_ID,
        today=date(2026, 8, 21),
        state_dir=state,
        digest_root=digest,
    )
    assert repeat == 0
    assert len(ledger.load_visual_prunes(state)) == 1, (
        "a second attempt at one execution is one cleanup written twice"
    )


def test_the_step_leaves_the_pictures_alone_when_no_tree_is_named(tmp_path: Path) -> None:
    """The pairing that stops a test run cleaning the committed archive.

    `digest_root` defaults to the real tree only beside the real state tree,
    exactly as `public_root` does and for the same reason.
    """
    state = tmp_path / "state"

    assert (
        stage_prune_state(
            observability=ObservabilityConfig(),
            collect=CollectConfig(),
            retention_config=RetentionConfig(image_months=6, dry_run=False),
            run_id=PRUNE_RUN_ID,
            today=date(2026, 8, 21),
            state_dir=state,
        )
        == 0
    )
    assert not ledger.visual_prunes_path(state, "2026-08-21").exists()


def test_a_directory_that_is_not_a_date_is_left_alone(tmp_path: Path) -> None:
    """The root is the boundary of the day tree, so the root is where it stops.

    A root can hold things that are not published days - this one holds a brand
    directory - and none of them is the prune's business. Inside a year the rule
    inverts, because inside a year the layout is ours: see the fault test above.
    """
    stray = tmp_path / "assets" / "brand"
    stray.mkdir(parents=True)
    (stray / "logo.svg").write_bytes(b"x" * 10)
    config = RetentionConfig(image_months=1, dry_run=False)
    assert prune(tmp_path, config, date(2026, 8, 21)).deleted == 0
    assert (stray / "logo.svg").exists()
