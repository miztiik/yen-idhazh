"""Unit-tier tests for the retention job and the site-budget alarm.

The prune is the most dangerous code in this repository - it is the only thing
that deletes a published byte - so the tests are written around the ways it goes
wrong rather than the way it goes right.

The telemetry fold at the foot of this file is the second thing that deletes,
and its oracle is stricter for it: the totals recomputed from the aggregate have
to equal the totals recomputed from the shard it replaced, read straight off the
CSV text rather than through the code being checked.

The browser's copy of a folded month and the feed-health shards are the third
and fourth. Neither can be recovered once `prune.yml` has squashed the range it
was committed in, so the tests below hold the order - write the summary, read it
back, then unlink - and hold the two failure states that order exists to prevent:
a copy left behind by a run that died between the two, and a shard deleted on the
strength of a write nobody checked.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger, publish_telemetry, retention, telemetry
from idhazh.cli import main, stage_prune_state, stage_site_weight
from idhazh.contracts.app_config import (
    PAGES_HARD_CAP_MB,
    AppConfig,
    CollectConfig,
    ConsoleConfig,
    ObservabilityConfig,
    RetentionConfig,
)
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.seen import SeenRow
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow, percentile
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.evals import archive as score_archive
from idhazh.evals import writer as score_writer
from idhazh.measured import SITE_GROWTH_KB_A_DAY
from idhazh.measured import WARNING_DAYS_REQUIRED as WARNING_DAYS
from idhazh.retention import (
    BYTES_PER_MB,
    SiteSize,
    TracePruneResult,
    budget_alarm,
    cap_breach,
    count_published_items,
    cutoff,
    daily_growth_bytes,
    days_to_alarm,
    days_to_cap,
    fold_month,
    headroom_mb,
    heaviest_directories,
    measure,
    month_shards,
    oldest_month_kept,
    oldest_visual,
    over_budget,
    over_cap,
    prune,
    prune_feed_health,
    prune_row,
    prune_scores,
    prune_seen,
    prune_telemetry,
    prune_traces,
    visuals_older_than,
)

pytestmark = pytest.mark.slow

#: The widest span the console's control can select, from the config that owns
#: it. The prune may never delete a shard a read that wide names.
CONSOLE_MAX_WINDOW_DAYS: Final = ConsoleConfig().max_window_days

#: The run every row these tests write is filed under. One value, so a test that
#: writes twice is writing a repeat rather than a second run.
RUN_ID: Final = "2026-08-30-33270983446"
#: The same, for the cleanup tests below, which run against the day the rest of
#: that section already uses.
PRUNE_RUN_ID: Final = "2026-08-21-33270983446"


def site(root: Path, days: dict[str, list[str]]) -> Path:
    for day, files in days.items():
        year, month, number = day.split("-")
        folder = root / year / month / number
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "digest.json").write_text(f'{{"date": "{day}"}}', encoding="utf-8")
        for name in files:
            (folder / name).write_bytes(b"x" * 1000)
    return root


#: Both records, and what to do when either bites, are in `idhazh.measured` -
#: the one place a measured number and its provenance live together.
FASTEST_MEASURED_KB_PER_DAY = int(SITE_GROWTH_KB_A_DAY.value)
WARNING_DAYS_REQUIRED = int(WARNING_DAYS.value)


def days_of_warning(budget_mb: int, kb_per_day: int) -> int:
    """Whole days from the alarm to the wall. A partial day is not a day."""
    return (PAGES_HARD_CAP_MB - budget_mb) * 1024 // kb_per_day


# --- The alarm, on from the first run ---------------------------------------


def test_an_absent_site_measures_as_nothing(tmp_path: Path) -> None:
    assert measure(tmp_path / "missing").bytes_used == 0


def test_the_site_is_measured_every_run(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp", "b.webp"]})
    size = measure(root)
    assert size.files == 3
    assert size.bytes_used > 2000


def test_the_alarm_fires_below_the_platform_ceiling(tmp_path: Path) -> None:
    """There has to be room to act between the alarm and the wall."""
    config = RetentionConfig()
    assert config.site_budget_mb < PAGES_HARD_CAP_MB


def test_the_alarm_buys_the_days_it_was_derived_to_buy() -> None:
    """Below the ceiling is not the property that matters. Days of warning is.

    An alarm at 1,023 MB is below the ceiling and buys nobody anything, so the
    inequality above cannot be the whole check.
    """
    config = RetentionConfig()
    bought = days_of_warning(config.site_budget_mb, FASTEST_MEASURED_KB_PER_DAY)
    assert bought >= WARNING_DAYS_REQUIRED, (
        f"{config.site_budget_mb} MB buys {bought} days at "
        f"{FASTEST_MEASURED_KB_PER_DAY} KB/day; re-derive it in "
        f"docs/reference/measurements.md before changing it here"
    )


def test_the_shipped_alarm_point_is_the_derived_one() -> None:
    """The derivation, not the round number. 800 MB buys 14 days at the measured rate.

    It bought 26 while the rate came from the committed payload tree. Against the
    site the tree is eighteen times smaller than, the same 800 MB clears the
    14-day target by one tenth of a day. That is a live gate rather than a
    comfortable one, and it is meant to be read that way.
    """
    assert RetentionConfig().site_budget_mb == 800
    assert days_of_warning(800, FASTEST_MEASURED_KB_PER_DAY) == 14


def test_a_ceiling_hugging_alarm_would_fail_this_check() -> None:
    """The case a bare `< PAGES_HARD_CAP_MB` assertion lets through."""
    assert days_of_warning(PAGES_HARD_CAP_MB - 1, FASTEST_MEASURED_KB_PER_DAY) == 0


def test_the_alarm_only_reports(tmp_path: Path) -> None:
    """It is an alarm, not a gate: it says yes and deletes nothing."""
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    (root / "2026" / "08" / "21" / "big.webp").write_bytes(b"x" * 2 * BYTES_PER_MB)
    before = measure(root)
    assert over_budget(before, RetentionConfig(site_budget_mb=1)) is True
    assert measure(root) == before


def test_a_small_site_is_not_over_budget(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    assert not over_budget(measure(root), RetentionConfig())


def test_the_alarm_speaks_only_when_over_budget(tmp_path: Path) -> None:
    """The words the run logs: None below the budget, a headroom line above it."""
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    (root / "2026" / "08" / "21" / "big.webp").write_bytes(b"x" * 2 * BYTES_PER_MB)
    over = measure(root)
    assert budget_alarm(over, RetentionConfig()) is None
    line = budget_alarm(over, RetentionConfig(site_budget_mb=1))
    assert line is not None
    assert "alarm point" in line
    assert "Pages cap" in line


def test_headroom_is_measured_against_the_hard_cap(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a.webp"]})
    assert headroom_mb(measure(root)) == pytest.approx(PAGES_HARD_CAP_MB, abs=1)


# --- A level is not a date -----------------------------------------------------

#: The item ceiling in force. Read from the config rather than copied beside it:
#: a copy said 160 while the knob said 80, and its own record said it would notice.
ITEMS_PER_DAY = AppConfig.from_json(
    read_text(CONFIG_DIR / "idhazh.json")
).run.safety_ceiling_per_run


def sized_tree(root: Path, weights: dict[str, int]) -> Path:
    """A built tree whose files weigh exactly what they are told to."""
    for relative, count in weights.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x" * count)
    return root


def staged_days(root: Path, days: dict[str, int]) -> Path:
    """Day payloads where the built tree keeps them, carrying a stated item count."""
    for day, count in days.items():
        payload = root / "digest" / day.replace("-", "/") / "digest.json"
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_text(
            json.dumps({"date": day, "items": [{"item_id": str(n)} for n in range(count)]}),
            encoding="utf-8",
        )
    return root


def test_the_split_sums_to_the_total_and_names_what_grew(tmp_path: Path) -> None:
    """One sum cannot say whether the visuals grew or the telemetry did.

    The sum has to be exact. A split that loses bytes somewhere would name the
    wrong directory on the day somebody used it to decide what to cut.
    """
    root = sized_tree(
        tmp_path / "build",
        {
            "index.html": 900,
            "_app/immutable/chunk.js": 40_000,
            "digest/2026/08/21/digest.json": 5_000,
            "digest/2026/08/22/digest.json": 7_000,
            "console/index.html": 9_000,
        },
    )
    size = measure(root)

    assert sum(size.by_directory.values()) == size.bytes_used
    assert size.by_directory == {
        "_app": 40_000,
        "console": 9_000,
        "digest": 12_000,
        "index.html": 900,
    }
    assert size.files == 5
    assert heaviest_directories(size, limit=2) == [("_app", 40_000), ("digest", 12_000)]


def test_published_items_are_counted_from_the_tree_that_was_measured(tmp_path: Path) -> None:
    """Bytes and items have to come from one corpus, or the rate divides two."""
    root = staged_days(tmp_path / "build", {"2026-08-21": 3, "2026-08-22": 5})
    assert count_published_items(root) == 8
    assert count_published_items(tmp_path / "never-built") == 0


# --- The maintained total ------------------------------------------------------


def reads_during(work: Callable[[], object]) -> int:
    """How many files an operation asks for a size.

    Counted rather than timed. A timing assertion is flaky and says nothing about
    what the code read, and what this row is about is what gets read: `measure`
    asks every file in the tree, so its count rises with the archive, and the
    maintained total asks none, so its count does not.
    """
    seen = 0
    real = Path.stat

    def counted(self: Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal seen
        seen += 1
        return real(self, *args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Path, "stat", counted)
        work()
    return seen


def test_a_retracted_deletion_equals_an_independent_walk(tmp_path: Path) -> None:
    """The oracle. A total carried forward has to agree with one taken fresh.

    Both shapes a deletion takes: a file inside a dated directory, where the
    directory survives and keeps its entry, and a file sitting directly under the
    root, where the entry goes with the file.
    """
    root = site(tmp_path, {"2020-01-01": ["a.webp", "b.webp"], "2026-08-20": ["new.webp"]})
    (root / "sitemap.xml").write_bytes(b"x" * 40)
    before = measure(root)

    doomed = [root / "2020" / "01" / "01" / "a.webp", root / "sitemap.xml"]
    sizes = {path: path.stat().st_size for path in doomed}
    for path in doomed:
        path.unlink()

    assert before.minus(root, sizes) == measure(root)


def test_maintaining_the_total_does_not_read_more_as_the_tree_grows(tmp_path: Path) -> None:
    """Guardrail #12, counted. The walk grows with the archive and the retraction does not."""
    small = site(tmp_path / "small", {"2026-08-20": ["a.webp", "b.webp"]})
    large = site(
        tmp_path / "large",
        {f"2026-08-{day:02d}": [f"{n}.webp" for n in range(6)] for day in range(1, 11)},
    )

    walked_small = reads_during(lambda: measure(small))
    walked_large = reads_during(lambda: measure(large))
    assert walked_large > walked_small, (
        "the independent walk is supposed to grow with the tree - it is the audit"
    )

    carried_small = measure(small)
    carried_large = measure(large)
    assert (
        reads_during(lambda: carried_small.minus(small, {small / "2026/08/20/a.webp": 1000})) == 0
    )
    assert (
        reads_during(lambda: carried_large.minus(large, {large / "2026/08/01/0.webp": 1000})) == 0
    )


def test_the_runway_is_headroom_over_the_marginal_rate(tmp_path: Path) -> None:
    """The row's whole point. A megabyte figure is a level, and no level has a date in it.

    Every expected value here is computed from the fixture rather than read back
    off the code, so the test fails if the arithmetic changes shape.
    """
    weight = 6 * BYTES_PER_MB
    root = sized_tree(tmp_path / "build", {"index.html": weight})
    size = measure(root, published_items=300)

    per_item = weight / 300
    rate = per_item * ITEMS_PER_DAY
    assert size.bytes_per_published_item == pytest.approx(per_item)
    assert daily_growth_bytes(size, ITEMS_PER_DAY) == pytest.approx(rate)

    to_cap = (PAGES_HARD_CAP_MB - 6) * BYTES_PER_MB / rate
    assert days_to_cap(size, ITEMS_PER_DAY) == pytest.approx(to_cap)

    config = RetentionConfig()
    to_alarm = (config.site_budget_mb - 6) * BYTES_PER_MB / rate
    assert days_to_alarm(size, config, ITEMS_PER_DAY) == pytest.approx(to_alarm)
    assert to_alarm < to_cap, "the alarm has to arrive before the wall or it buys nothing"


def test_a_runway_from_nothing_raises_rather_than_reading_as_forever(tmp_path: Path) -> None:
    """Zero published items divides into infinite runway, which reads as safety.

    Same defect as the green light on the wrong tree: the comfortable answer is
    the one an absent build produces, so the absent build must not produce one.
    """
    empty = measure(tmp_path / "never-built")
    assert empty.files == 0

    with pytest.raises(ValueError):
        _ = empty.bytes_per_published_item
    with pytest.raises(ValueError):
        days_to_cap(empty, ITEMS_PER_DAY)
    with pytest.raises(ValueError):
        days_to_alarm(empty, RetentionConfig(), ITEMS_PER_DAY)

    real = measure(sized_tree(tmp_path / "build", {"index.html": 1_000}), published_items=10)
    with pytest.raises(ValueError):
        days_to_cap(real, 0)


def test_the_step_reports_the_rate_and_the_runway(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """What a person reads off the run: which directory, how fast, and until when."""
    root = staged_days(tmp_path / "build", {"2026-08-21": 200, "2026-08-22": 200})
    sized_tree(root, {"_app/immutable/chunk.js": 4 * BYTES_PER_MB})

    with caplog.at_level(logging.INFO):
        assert stage_site_weight(root, RetentionConfig(), items_per_day=ITEMS_PER_DAY) == 0

    printed = caplog.text
    assert "site-weight by directory: _app" in printed, "a growing directory has to be named"
    assert "B per published item over 400 items" in printed
    assert "published days to the 800 MB alarm point" in printed
    assert "MB Pages cap" in printed


def test_a_tree_with_no_day_payloads_says_unknown_rather_than_a_comfortable_number(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Reporting, not a gate: it still passes, and it refuses to invent a date."""
    tree = built_site(tmp_path / "build", 3)
    with caplog.at_level(logging.INFO):
        assert stage_site_weight(tree, RetentionConfig(), items_per_day=ITEMS_PER_DAY) == 0
    assert "site-weight runway: unknown" in caplog.text


# --- The alarm has to be able to fire ---------------------------------------


def built_site(root: Path, megabytes: int) -> Path:
    """A stand-in for `frontend/build`: prerendered pages of a stated weight."""
    page = root / "2026-08-24"
    page.mkdir(parents=True, exist_ok=True)
    (page / "index.html").write_bytes(b"x" * megabytes * BYTES_PER_MB)
    return root


def test_a_site_inside_budget_passes_quietly(tmp_path: Path) -> None:
    tree = built_site(tmp_path / "build", 3)
    assert stage_site_weight(tree, RetentionConfig()) == 0


def test_the_alarm_fires_when_the_built_site_crosses_the_alarm_point(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point of the row: the alarm can reach its own threshold.

    A 3 MB tree against a 2 MB alarm point rather than a 1 GB fixture - the
    arithmetic is the same and the fixture fits on a runner.
    """
    tree = built_site(tmp_path / "build", 3)

    assert stage_site_weight(tree, RetentionConfig(site_budget_mb=2)) == 0, (
        "the alarm reports and passes below the cap - those bytes still deploy"
    )
    printed = capsys.readouterr().out
    assert "::warning" in printed, "an alarm nobody sees is the defect this row fixed"
    assert "2 MB alarm point" in printed
    assert f"{PAGES_HARD_CAP_MB} MB Pages cap" in printed


def test_the_gate_fails_when_the_built_site_crosses_the_platform_cap(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Past the cap the bytes cannot be published, so the build stops here.

    The alarm point stays at its shipped 800 MB, so this proves the cap is
    checked on its own rather than as a louder alarm. The cap is lowered to 2 MB
    through config, because that is now the only way to move it - the step reads
    `retention.pages_hard_cap_mb` and takes no override.

    This is also the permitted arm of the bound. `test_contracts.py` holds the
    refusal, and neither arm alone is a bound: one shows the number can be lowered
    and the other shows it cannot be raised.
    """
    tree = built_site(tmp_path / "build", 3)
    with caplog.at_level(logging.ERROR, logger="idhazh"):
        assert stage_site_weight(tree, RetentionConfig(pages_hard_cap_mb=2)) == 1
    assert "2 MB Pages cap" in caplog.text, "the failure names the cap that stopped it"


def test_lowering_the_cap_moves_the_gate_and_the_headroom_it_prints(tmp_path: Path) -> None:
    """The same tree, two caps, two answers - and the alarm point unmoved.

    3 MB of site passes under the shipped 1024 MB cap and fails under a 2 MB one,
    which is the gate firing earlier. The alarm's words follow the cap too, since
    the headroom it prints is headroom to the cap and a lowered cap leaves less.
    What does not move is the alarm point itself: it is a different instrument and
    stays where config put it.
    """
    tree = built_site(tmp_path / "build", 3)
    assert stage_site_weight(tree, RetentionConfig()) == 0
    assert stage_site_weight(tree, RetentionConfig(pages_hard_cap_mb=2)) == 1

    size = measure(tree, published_items=count_published_items(tree))
    shipped = budget_alarm(size, RetentionConfig(site_budget_mb=2))
    lowered = budget_alarm(size, RetentionConfig(site_budget_mb=2, pages_hard_cap_mb=500))
    assert shipped is not None
    assert lowered is not None
    assert "2 MB alarm point" in shipped
    assert "2 MB alarm point" in lowered
    assert f"{PAGES_HARD_CAP_MB} MB Pages cap" in shipped
    assert "500 MB Pages cap" in lowered
    assert shipped != lowered, "the headroom the alarm prints is headroom to the cap in force"


def test_the_cap_line_says_what_it_costs_and_what_to_do() -> None:
    """The two words a person needs are the size and the ceiling it passed."""
    inside = SiteSize(700 * BYTES_PER_MB, 4)
    past = SiteSize(1100 * BYTES_PER_MB, 4)

    assert over_cap(inside) is False
    assert cap_breach(inside) is None

    assert over_cap(past) is True
    line = cap_breach(past)
    assert line is not None
    assert "1100 MB" in line
    assert f"{PAGES_HARD_CAP_MB} MB Pages cap" in line


def test_a_site_measured_as_nothing_fails_rather_than_passes(tmp_path: Path) -> None:
    """Zero bytes clears every ceiling, which reads exactly like a healthy site.

    Both shapes: a tree that was never built, and one that built nothing.
    """
    assert stage_site_weight(tmp_path / "never-built", RetentionConfig()) == 1

    empty = tmp_path / "build"
    empty.mkdir()
    assert stage_site_weight(empty, RetentionConfig()) == 1


def test_the_gate_has_no_default_tree() -> None:
    """A default is how this came to measure the committed payloads.

    `argparse` exits 2 on a usage error, so the run fails rather than measuring
    whichever tree a default happened to name.
    """
    with pytest.raises(SystemExit) as exit_code:
        main(["site-weight"])
    assert exit_code.value.code == 2


def test_the_committed_payload_tree_is_not_the_site(tmp_path: Path) -> None:
    """The two trees the defect confused, measured against each other.

    A day directory of payloads and a built bundle are different sizes on the
    same corpus, so neither can stand in for the other. On this checkout,
    2026-08-27: 7,027,075 bytes of payloads against 128,064,853 bytes of site.
    """
    payloads = site(tmp_path / "public", {"2026-08-24": ["ai-01.svg"]})
    bundle = built_site(tmp_path / "build", 3)
    assert measure(payloads).bytes_used < measure(bundle).bytes_used


# --- Retention ships disabled ------------------------------------------------


def test_retention_is_off_by_default() -> None:
    """A default is a promise, not a placeholder."""
    config = RetentionConfig()
    assert config.image_months == -1
    assert config.dry_run is True
    assert cutoff(date(2026, 8, 21), config.image_months) is None


def test_a_disabled_policy_deletes_nothing(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    result = prune(root, RetentionConfig(), date(2026, 8, 21))
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()


# --- What may be deleted, and what may never be -------------------------------


def test_only_visuals_are_candidates(tmp_path: Path) -> None:
    """The payload is the record that a day happened. Text is never pruned."""
    root = site(tmp_path, {"2020-01-01": ["old.webp", "notes.txt"]})
    found = visuals_older_than(root, date(2026, 8, 21))
    assert [path.name for path in found] == ["old.webp"]


def test_a_recent_day_is_never_a_candidate(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["new.webp"]})
    assert visuals_older_than(root, date(2026, 1, 1)) == []


def test_a_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    config = RetentionConfig(image_months=6, dry_run=True)
    result = prune(root, config, date(2026, 8, 21))
    assert result.considered == 1
    assert result.deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()


def test_an_enabled_policy_deletes_the_old_visual_and_keeps_the_day(tmp_path: Path) -> None:
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    config = RetentionConfig(image_months=6, dry_run=False)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 1
    assert not (root / "2020" / "01" / "01" / "old.webp").exists()
    assert (root / "2020" / "01" / "01" / "digest.json").exists(), "the day survives its picture"


def test_the_fuse_caps_what_one_run_can_delete(tmp_path: Path) -> None:
    """An off-by-one in a date parse must not eat the archive."""
    root = site(tmp_path, {"2020-01-01": [f"{n}.webp" for n in range(10)]})
    config = RetentionConfig(image_months=6, dry_run=False, max_deletes_per_run=3)
    result = prune(root, config, date(2026, 8, 21))
    assert result.deleted == 3
    assert result.fuse_tripped
    assert result.considered == 10


# --- The scan opens the days the policy names, and no others ------------------

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
            (SCAN_START + timedelta(days=n)).isoformat(): [f"{i}.webp" for i in range(pictures)]
            for n in range(days)
        },
    )


def by_sorting_the_whole_tree(root: Path, limit: date) -> list[Path]:
    """The reference answer: sort every path under the root, then filter.

    This is the shape the scan used to have, written out here so the cheaper one
    has something to be equal to. It may cost whatever it likes - it runs over a
    fixture of fixed size, never over the archive.
    """
    pictures = {".png", ".webp", ".jpg", ".jpeg", ".svg"}
    found: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in pictures:
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

    `image_months` is -1 in shipped config, so `visuals_older_than` is never
    called - and `prune` still asks for the oldest picture on every path through
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
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    (root / "2020" / "notes.txt").write_bytes(b"x")

    with pytest.raises(ValueError, match=r"2020/notes\.txt is not a month"):
        visuals_older_than(root, date(2026, 8, 21))


# --- What the run says it did not clear --------------------------------------


def test_the_run_reports_the_backlog_the_fuse_left_behind(tmp_path: Path) -> None:
    """The row's whole point. `deleted` is capped, so `deleted` cannot answer this.

    300 candidates against the shipped 200-file fuse, and the shipped fuse rather
    than a scaled-down one - the question is whether the number an operator
    actually reads can distinguish a finished run from a stuck one.

    A run that deleted 200 and skipped 0 has cleared its backlog. A run that
    deleted 200 and skipped 100 has not. `deleted` is 200 in both.
    """
    root = site(tmp_path, {"2020-01-01": [f"{n}.webp" for n in range(300)]})
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
    root = site(tmp_path, {"2020-01-01": [f"{n}.webp" for n in range(300)]})
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
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})
    live = RetentionConfig(image_months=6, dry_run=False)

    assert prune(root, live, date(2026, 8, 21), dry_run=True).deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()

    shipped = RetentionConfig(image_months=6, dry_run=True)
    assert prune(root, shipped, date(2026, 8, 21), dry_run=False).deleted == 0
    assert (root / "2020" / "01" / "01" / "old.webp").exists()


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
    root = site(tmp_path, {"2020-01-01": ["a.webp", "b.webp"], "2026-08-20": ["new.webp"]})
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
    root = site(tmp_path, {"2020-01-01": ["a.webp", "b.webp"], "2026-08-20": ["new.webp"]})
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
    root = site(tmp_path, {"2020-01-01": ["a.webp", "b.webp"], "2026-08-20": ["new.webp"]})
    stubborn = root / "2020" / "01" / "01" / "b.webp"
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
    root = site(tmp_path, {"2020-01-01": ["old.webp"], "2026-08-20": ["new.webp"]})
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
    root = site(tmp_path, {"2020-01-01": ["old.webp"]})

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
    root = site(tmp_path, {"2020-01-01": [f"{n}.webp" for n in range(300)]})
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
    digest = site(tmp_path / "public", {"2020-01-01": [f"{n}.webp" for n in range(300)]})

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


# --- The telemetry fold ------------------------------------------------------

#: The day the fold is run against in every test below, and the twenty months of
#: history it is run over. Twenty rather than fourteen so both sides of the
#: threshold carry several months: at `item_health_full_grain_months` 14 the fold
#: takes six and leaves fourteen, and a threshold off by one shows up as a shard
#: on the wrong side rather than as an empty result.
TODAY: Final = date(2026, 8, 30)
HISTORY_MONTHS: Final = 20
#: How far down the pipeline each terminal stage got, so a row carries the clocks
#: an item that really stopped there would have carried and no others.
STAGES_REACHED: Final = {
    ItemStage.PLAN: (),
    ItemStage.FETCH: ("fetch_ms",),
    ItemStage.EXTRACT: ("fetch_ms", "extract_ms"),
    ItemStage.SUMMARIZE: ("fetch_ms", "extract_ms", "summarize_ms"),
    ItemStage.PUBLISH: ("fetch_ms", "extract_ms", "summarize_ms"),
}
CLOCK_MS: Final = {"fetch_ms": 900, "extract_ms": 1_400, "summarize_ms": 62_000}
#: A failure code each stage really produces. `plan` is a refusal and `publish`
#: is the census's one unambiguous success, so the two ends differ.
STAGE_FAILURE: Final = {
    ItemStage.PLAN: FailureCode.NOT_ATTEMPTED,
    ItemStage.FETCH: FailureCode.HTTP_SERVER_ERROR,
    ItemStage.EXTRACT: FailureCode.PAYWALLED,
    ItemStage.SUMMARIZE: FailureCode.BAD_SHAPE,
    ItemStage.PUBLISH: None,
}


def months_back(today: date, count: int) -> list[str]:
    """`YYYY-MM` stems, oldest first, ending on the month `today` sits in."""
    total = today.year * 12 + (today.month - 1)
    return [
        f"{(total - offset) // 12:04d}-{(total - offset) % 12 + 1:02d}"
        for offset in reversed(range(count))
    ]


def health_row(*, day: str, run: int, number: int, stage: ItemStage) -> ItemHealthRow:
    """One census row, shaped the way the contract's own validators demand."""
    code = STAGE_FAILURE[stage]
    # A slower item every third one, so a percentile has something to separate.
    stretch = 1 + (number % 3)
    reached = STAGES_REACHED[stage]

    def clock(name: str) -> int | None:
        return CLOCK_MS[name] * stretch if name in reached else None

    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=day,
        run_id=f"{day}-{run}",
        item_id=f"ai-{number:04d}",
        url_key=hashlib.sha256(f"{day}-{number}".encode("ascii")).hexdigest(),
        canonical_url=f"https://example.test/{day}/{number}",
        vertical="ai",
        source_id="example",
        stage=stage,
        outcome=ItemOutcome.OK if code is None else ItemOutcome.FAILED,
        code=code,
        fetch_ms=clock("fetch_ms"),
        extract_ms=clock("extract_ms"),
        summarize_ms=clock("summarize_ms"),
    )


def item_health_history(state_dir: Path, months: list[str]) -> None:
    """A real item-health shard per month, written through the real appender."""
    for index, month in enumerate(months):
        for day_of_month in (4, 17):
            day = f"{month}-{day_of_month:02d}"
            rows = [
                health_row(day=day, run=1, number=index * 100 + position, stage=stage)
                for position, stage in enumerate(ItemStage)
            ]
            # A second run of the same day, so the fold meets the repeated
            # `(date, run_id, item_id)` keys the committed ledger really carries.
            rows.append(
                health_row(day=day, run=2, number=index * 100 + 50, stage=ItemStage.PUBLISH)
            )
            ledger.append_item_health(state_dir, day, rows)


def totals_from_shard(text: str) -> dict[tuple[str, str], tuple[int, int, int]]:
    """Rows, failures and total milliseconds per (date, stage), read off the CSV.

    Recomputed here from the raw text rather than by calling `fold_month`, so the
    oracle cannot pass by agreeing with the code it is checking.
    """
    totals: dict[tuple[str, str], tuple[int, int, int]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        key = (row["date"], row["stage"])
        rows, failures, elapsed = totals.get(key, (0, 0, 0))
        spent = sum(
            int(row[name]) for name in ("fetch_ms", "extract_ms", "summarize_ms") if row[name]
        )
        totals[key] = (rows + 1, failures + (row["outcome"] != "ok"), elapsed + spent)
    return totals


def totals_from_aggregate(
    rows: list[TelemetryAggregateRow],
) -> dict[tuple[str, str], tuple[int, int, int]]:
    return {(row.date, row.stage.value): (row.items, row.failed, row.sum_ms or 0) for row in rows}


def a_state_tree(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    item_health_history(state, months_back(TODAY, HISTORY_MONTHS))
    return state


def test_the_fold_keeps_the_configured_window_at_full_grain(tmp_path: Path) -> None:
    """Every shard inside the window is byte-identical, and every shard outside is gone."""
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    before = {
        path.stem: path.read_bytes() for path in month_shards(state / ledger.ITEM_HEALTH_DIRNAME)
    }
    assert len(before) == HISTORY_MONTHS

    result = prune_telemetry(state, config, TODAY)

    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    assert config.item_health_full_grain_months == 14, (
        "a 366-day console read can open fourteen month shards"
    )
    assert kept == "2025-07", "fourteen months ending in August 2026 starts in July 2025"
    assert list(result.folded) == sorted(stem for stem in before if stem < kept)
    assert len(result.folded) == HISTORY_MONTHS - config.item_health_full_grain_months
    for stem, bytes_before in before.items():
        shard = ledger.item_health_path(state, f"{stem}-01")
        if stem < kept:
            assert not shard.exists(), f"{stem} is past the window and must be gone"
        else:
            assert shard.read_bytes() == bytes_before, f"{stem} is inside the window"


def test_the_fold_loses_no_total(tmp_path: Path) -> None:
    """The grain changes; the answer does not. A fold that loses a total is a failed fold."""
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    doomed = {
        path.stem: path.read_text(encoding="utf-8")
        for path in month_shards(state / ledger.ITEM_HEALTH_DIRNAME)
        if path.stem < kept
    }
    assert doomed, "the fixture has to reach past the window or this proves nothing"

    prune_telemetry(state, config, TODAY)

    for stem, text in doomed.items():
        folded = ledger.load_telemetry_aggregate(ledger.telemetry_aggregate_path(state, stem))
        assert totals_from_aggregate(folded) == totals_from_shard(text), (
            f"{stem} lost a total in the fold"
        )


def test_the_fold_keeps_a_repeated_row_rather_than_deciding_for_a_reader(
    tmp_path: Path,
) -> None:
    """The committed ledger carries repeated keys, and the fold reproduces them.

    Run `2026-08-29-3` really did leave 212 item-health rows for 168 items.
    Collapsing them at fold time would make the aggregate disagree with the file
    it replaced, and nobody could then say which of the two was right.
    """
    day = "2024-01-04"
    state = tmp_path / "state"
    rows = [health_row(day=day, run=run, number=7, stage=ItemStage.PUBLISH) for run in (1, 2)]
    ledger.append_item_health(state, day, rows)

    folded = fold_month(ledger.load_item_health_shard(ledger.item_health_path(state, day)))

    assert [row.items for row in folded] == [2]
    assert folded[0].timed == 2
    slowest = folded[0].max_ms
    assert slowest is not None
    assert folded[0].sum_ms == 2 * slowest, "both copies of one item, added"


def test_a_group_that_timed_nothing_says_so_rather_than_saying_zero(tmp_path: Path) -> None:
    """An instrument that did not run writes an empty cell. Empty is not zero."""
    day = "2024-01-04"
    state = tmp_path / "state"
    ledger.append_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PLAN)]
    )

    folded = fold_month(ledger.load_item_health_shard(ledger.item_health_path(state, day)))

    assert [row.stage for row in folded] == [ItemStage.PLAN]
    assert folded[0].items == 1
    assert folded[0].timed == 0
    assert (folded[0].p50_ms, folded[0].p90_ms, folded[0].max_ms, folded[0].sum_ms) == (
        None,
        None,
        None,
        None,
    )
    assert folded[0].csv_row()["p50_ms"] == ""


def test_a_percentile_is_a_number_some_item_really_took(tmp_path: Path) -> None:
    """Nearest rank, never interpolation. An invented millisecond count cannot be checked."""
    assert percentile([5], 0.5) == 5
    assert percentile([5], 0.9) == 5
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile([1, 2, 3, 4], 0.9) == 4
    assert percentile(list(range(1, 11)), 0.9) == 9
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_a_dry_run_changes_nothing_on_disk(tmp_path: Path) -> None:
    state = a_state_tree(tmp_path)
    before = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*.csv"))
    }

    result = prune_telemetry(state, ObservabilityConfig(), TODAY, dry_run=True)

    after = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*.csv"))
    }
    assert result.dry_run is True
    assert result.folded, "it still has to report what it would have done"
    assert result.rows_folded > 0
    assert after == before
    assert not (state / ledger.TELEMETRY_AGGREGATE_DIRNAME).exists()


def test_the_aggregate_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path,
) -> None:
    """`console.max_window_days` is 366, so a shard has to answer for a year.

    Running the fold twenty times over must never remove an aggregate while
    `item_health_aggregate_keep_months` is null, which is what ships.
    """
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig()
    assert config.item_health_aggregate_keep_months is None

    first = prune_telemetry(state, config, TODAY)
    written = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
    again = prune_telemetry(state, config, TODAY)

    assert written == sorted(first.folded)
    assert again.folded == (), "the shards are gone, so a second fold has nothing to do"
    assert again.hard_deleted == ()
    assert (
        sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
        == written
    )


def test_a_hard_delete_takes_the_aggregate_only_after_the_fold_has_had_it(
    tmp_path: Path,
) -> None:
    """The escape hatch, for the day the owner wants the bytes back.

    The config refuses a threshold at or below the full-grain window, so a month
    is always folded before it can be deleted - this proves the deletion happens
    at the threshold the config does allow.
    """
    state = a_state_tree(tmp_path)
    config = ObservabilityConfig(item_health_aggregate_keep_months=16)
    prune_telemetry(state, ObservabilityConfig(), TODAY)
    before = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))

    result = prune_telemetry(state, config, TODAY)

    boundary = oldest_month_kept(TODAY, 16)
    assert sorted(result.hard_deleted) == [stem for stem in before if stem < boundary]
    assert result.hard_deleted, "a threshold inside the fixture has to remove something"
    left = sorted(path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME))
    assert left == [stem for stem in before if stem >= boundary]


def test_the_window_is_counted_in_months_and_not_in_thirty_day_steps() -> None:
    """A month file is kept or dropped whole, so the arithmetic is in months."""
    assert oldest_month_kept(date(2026, 8, 30), 13) == "2025-08"
    assert oldest_month_kept(date(2026, 8, 1), 13) == "2025-08"
    assert oldest_month_kept(date(2026, 1, 15), 13) == "2025-01"
    assert oldest_month_kept(date(2026, 1, 15), 1) == "2026-01"
    assert oldest_month_kept(date(2026, 12, 31), 24) == "2025-01"
    with pytest.raises(ValueError):
        oldest_month_kept(date(2026, 8, 30), 0)


#: Names of the right width and shape that are not a month. Every one was
#: accepted by at least one month reader and refused by another before
#: 2026-09-08, which is what made the same file survive in one store and get
#: deleted in the next.
NOT_MONTHS: Final = (
    "2025-00",
    "2025-13",
    "0000-01",
    #: `2025-01` in Arabic-Indic digits. `str.isdigit` and `int` both read this
    #: as January 2025, so a naive check finds two files claiming one month.
    "\u0662\u0660\u0662\u0665-\u0660\u0661",
)

#: The rest of what turns up beside a shard: the wrong width, no date at all,
#: and a file whose real suffix is not the one being read.
OTHER_STRAYS: Final = ("notes", "2025-1", "README", "2025-01.csv")


def test_the_month_readers_all_agree_on_what_a_month_is(tmp_path: Path) -> None:
    """One rule for four directories. They used to carry three.

    This is the defect the row is about, stated as one assertion. A directory a
    prune deletes from names what it recognises, so two directories that
    recognise different things dispose of the same file two different ways.
    """
    state = tmp_path / "state"
    readers: dict[str, tuple[Path, str, Callable[[], list[Path]]]] = {
        "retention.month_shards": (
            state / ledger.ITEM_HEALTH_DIRNAME,
            ".csv",
            lambda: month_shards(state / ledger.ITEM_HEALTH_DIRNAME),
        ),
        "evals.writer.ledger_shards": (
            state / score_writer.LEDGER_DIRNAME,
            ".csv",
            lambda: score_writer.ledger_shards(state),
        ),
        "evals.writer.index_shards": (
            state / score_writer.INDEX_DIRNAME,
            ".csv",
            lambda: score_writer.index_shards(state),
        ),
        "evals.archive.archive_files": (
            state / score_archive.ARCHIVE_DIRNAME,
            ".json",
            lambda: score_archive.archive_files(state),
        ),
    }
    for directory, suffix, _ in readers.values():
        directory.mkdir(parents=True)
        for stem in ("2025-01", "2025-12", *NOT_MONTHS, *OTHER_STRAYS):
            (directory / f"{stem}{suffix}").write_text("header\n", encoding="utf-8")

    found = {name: [path.stem for path in read()] for name, (_, _, read) in readers.items()}

    assert found == {name: ["2025-01", "2025-12"] for name in readers}


def test_a_file_that_is_not_a_month_shard_is_never_a_candidate(tmp_path: Path) -> None:
    """A directory this deletes from names what it recognises, never the rest."""
    directory = tmp_path / "state" / ledger.ITEM_HEALTH_DIRNAME
    directory.mkdir(parents=True)
    for stem in ("2025-01", *NOT_MONTHS, *OTHER_STRAYS):
        (directory / f"{stem}.csv").write_text("header\n", encoding="utf-8")

    assert [path.name for path in month_shards(directory)] == ["2025-01.csv"]


def test_an_empty_state_tree_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """A fresh clone has no history, and no history is not an error."""
    result = prune_telemetry(tmp_path / "state", ObservabilityConfig(), TODAY)
    assert result.changed is False
    assert result.rows_folded == 0


# --- The browser's copy of a folded month ------------------------------------


def a_published_tree(tmp_path: Path) -> tuple[Path, Path]:
    """A state tree and the browser's copy of every month in it.

    The copy is written by the publisher rather than by this file, so what the
    prune deletes is the file the pipeline really produces.
    """
    state = a_state_tree(tmp_path)
    public = tmp_path / "frontend" / "public" / "telemetry"
    publish_telemetry.publish(state_root=state, public_root=public)
    return state, public


def test_the_browser_copy_goes_with_the_month_it_copies(tmp_path: Path) -> None:
    """One boundary, two trees. A copy nobody can check is worse than no copy.

    `public_telemetry_keep_months` must equal `item_health_full_grain_months`,
    so the two sets are the same months and the assertion is that both trees end
    up holding exactly them.
    """
    state, public = a_published_tree(tmp_path)
    config = ObservabilityConfig()
    kept = oldest_month_kept(TODAY, config.item_health_full_grain_months)
    assert len(month_shards(public)) == HISTORY_MONTHS

    result = prune_telemetry(state, config, TODAY, public_root=public)

    assert sorted(result.public_deleted) == sorted(result.folded)
    assert [path.stem for path in month_shards(public)] == [
        stem for stem in months_back(TODAY, HISTORY_MONTHS) if stem >= kept
    ]
    for stem in result.public_deleted:
        assert not publish_telemetry.shard_path(public, stem).exists()


def test_a_copy_whose_source_is_already_gone_is_still_taken(tmp_path: Path) -> None:
    """The case the fold loop cannot see, because there is nothing left to fold.

    A run that unlinked the shard and then lost its push - or died between the
    two - leaves a published month with no ledger behind it. It is the one copy
    a reader can still fetch and nobody can check, so the pass that takes it
    walks the published tree rather than the shards being folded.
    """
    state = tmp_path / "state"
    public = tmp_path / "telemetry"
    public.mkdir(parents=True)
    orphan = publish_telemetry.shard_path(public, "2024-01")
    orphan.write_text(",".join(publish_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")
    live = publish_telemetry.shard_path(public, TODAY.strftime("%Y-%m"))
    live.write_text(",".join(publish_telemetry.PUBLIC_COLUMNS) + "\n", encoding="utf-8")

    result = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public)

    assert result.folded == (), "there was no shard to fold"
    assert result.public_deleted == ("2024-01",)
    assert result.changed is True, "a deletion is a change even with nothing folded"
    assert not orphan.exists()
    assert live.exists()


def test_a_dry_run_names_the_copy_it_would_take_and_leaves_it(tmp_path: Path) -> None:
    """The list a dry run prints is the list a live run removes, file for file.

    That equality is the deliverable: the workflow ships in dry run so a person
    can read the list before the deletion is switched on, and a list assembled
    from what the deletion happened to reach could not be read that way.
    """
    state, public = a_published_tree(tmp_path)
    before = {path.name: path.read_bytes() for path in month_shards(public)}

    planned = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public, dry_run=True)
    done = prune_telemetry(state, ObservabilityConfig(), TODAY, public_root=public)

    assert planned.public_deleted == done.public_deleted
    assert planned.folded == done.folded
    assert {path.name for path in month_shards(public)} == set(before) - {
        f"{stem}.csv" for stem in done.public_deleted
    }
    for name, content in before.items():
        copy = public / name
        if copy.exists():
            assert copy.read_bytes() == content, f"{name} was rewritten rather than left alone"


def test_a_state_tree_with_no_site_beside_it_deletes_no_copy(tmp_path: Path) -> None:
    """`public_root` is None by default on purpose.

    A caller that names its own state tree and forgets the published one must get
    nothing, never the committed tree. Deleting a published shard out of a test
    run is the failure the pairing exists to stop.
    """
    state, public = a_published_tree(tmp_path)
    held = {path.name: path.read_bytes() for path in month_shards(public)}

    result = prune_telemetry(state, ObservabilityConfig(), TODAY)

    assert result.public_deleted == ()
    assert {path.name: path.read_bytes() for path in month_shards(public)} == held


def test_a_fold_that_cannot_be_written_leaves_the_shard_and_its_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is deleted on the strength of a write nobody checked.

    The aggregate is written, read back and reconciled first. A read-back that
    disagrees raises, and BOTH files that month owns stay - the private record
    and the browser's copy of it. Half a deletion is the state nothing can
    recover from.
    """
    state, public = a_published_tree(tmp_path)
    config = ObservabilityConfig()
    doomed = [
        path
        for path in month_shards(state / ledger.ITEM_HEALTH_DIRNAME)
        if path.stem < oldest_month_kept(TODAY, config.item_health_full_grain_months)
    ]
    assert doomed, "the fixture has to reach past the window or this proves nothing"
    monkeypatch.setattr(ledger, "load_telemetry_aggregate", lambda _path: [])

    with pytest.raises(ValueError, match="did not read back"):
        prune_telemetry(state, config, TODAY, public_root=public)

    assert doomed[0].exists(), "the first shard was unlinked after an unverified write"
    assert publish_telemetry.shard_path(public, doomed[0].stem).exists()
    assert len(month_shards(public)) == HISTORY_MONTHS


# --- The feed-health shards --------------------------------------------------


def feed_health_history(state_dir: Path, months: list[str]) -> None:
    """A real feed-health shard per month, written through the real appender."""
    for index, month in enumerate(months):
        day = f"{month}-11"
        ledger.append_health(
            state_dir,
            day,
            [
                FeedHealthRow(
                    version=FeedHealthRow.schema_version(),
                    run_id=f"{day}-1",
                    date=day,
                    feed_id=f"example-{index:02d}",
                    checked_at=f"{day}T06:00:00Z",
                    outcome=FetchOutcome.OK,
                    status=200,
                    items=3,
                    detail=None,
                )
            ],
        )


def test_a_feed_health_month_past_its_own_age_is_deleted_rather_than_folded(
    tmp_path: Path,
) -> None:
    """Nothing reads a feed's result from fourteen months ago.

    The quarantine reads 31 days and the console reaches at most
    `console.max_window_days`, so a summary of an older month would be a shape
    with no consumer, written for ever. The knob is the store's own, and what
    survives is asserted against it rather than against a stem this test picked.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    months = months_back(TODAY, HISTORY_MONTHS)
    feed_health_history(state, months)
    boundary = oldest_month_kept(TODAY, config.feed_health_keep_months)

    result = prune_feed_health(state, config, TODAY)

    assert list(result.deleted) == [stem for stem in months if stem < boundary]
    assert list(result.kept) == [stem for stem in months if stem >= boundary]
    assert result.bytes_freed > 0
    assert [path.stem for path in month_shards(state / ledger.HEALTH_DIRNAME)] == list(result.kept)
    assert not (state / ledger.TELEMETRY_AGGREGATE_DIRNAME).exists(), (
        "feed health is deleted rather than folded; an aggregate here has no reader"
    )


def test_the_retirement_ledger_is_never_a_candidate(tmp_path: Path) -> None:
    """It carries no time window, so no age can expire it.

    One row is one address a server reported permanently gone. A run that forgot
    it would start asking a dead address again, and the evidence that retired it
    lives in shards this prune is entitled to delete - so the record has to
    outlive them.
    """
    state = tmp_path / "state"
    feed_health_history(state, months_back(TODAY, HISTORY_MONTHS))
    retirements = ledger.feed_retirements_path(state)
    retirements.write_text("header\n", encoding="utf-8")

    result = prune_feed_health(state, ObservabilityConfig(), TODAY)

    assert result.deleted, "the fixture has to reach past the window or this proves nothing"
    assert retirements.read_text(encoding="utf-8") == "header\n"


def test_a_feed_health_file_that_is_not_a_month_shard_is_left_alone(tmp_path: Path) -> None:
    """A directory this deletes from names what it recognises, never the rest."""
    directory = tmp_path / "state" / ledger.HEALTH_DIRNAME
    directory.mkdir(parents=True)
    strays = tuple(f"{stem}.csv" for stem in (*NOT_MONTHS, *OTHER_STRAYS))
    for name in (*strays, "2024-01.csv"):
        (directory / name).write_text("header\n", encoding="utf-8")

    result = prune_feed_health(tmp_path / "state", ObservabilityConfig(), TODAY)

    assert result.deleted == ("2024-01",)
    assert sorted(path.name for path in directory.iterdir()) == sorted(strays)


def test_a_feed_health_dry_run_names_the_shard_and_leaves_it(tmp_path: Path) -> None:
    state = tmp_path / "state"
    feed_health_history(state, ["2024-01", TODAY.strftime("%Y-%m")])

    result = prune_feed_health(state, ObservabilityConfig(), TODAY, dry_run=True)

    assert result.deleted == ("2024-01",)
    assert result.dry_run
    assert ledger.health_path(state, "2024-01-11").exists()


def test_a_feed_health_run_handed_an_older_date_keeps_the_live_shard(tmp_path: Path) -> None:
    """`--date` takes whatever it is given, so the boundary has to be a floor.

    `prune-state --date <last January>` computes a smaller window, and every
    shard since is outside it. The rule is "older than the oldest month kept",
    not "outside the window", so the live shard stays and only the genuinely
    older one goes. Deleting what is outside would take the shard the next
    quarantine reads.
    """
    state = tmp_path / "state"
    feed_health_history(state, ["2024-01", "2026-08"])

    result = prune_feed_health(state, ObservabilityConfig(), date(2026, 1, 5))

    assert result.deleted == ("2024-01",)
    assert result.kept == ("2026-08",)
    assert ledger.health_path(state, "2026-08-11").exists(), (
        "the live shard was deleted by a run given an older date"
    )
    assert not ledger.health_path(state, "2024-01-11").exists()


def test_an_empty_state_tree_deletes_no_feed_health_and_says_so(tmp_path: Path) -> None:
    result = prune_feed_health(tmp_path / "state", ObservabilityConfig(), TODAY)
    assert result.changed is False
    assert result.deleted == ()
    assert result.bytes_freed == 0


# --- The oracle, over fifteen months -----------------------------------------


def test_the_oracle_fifteen_months_leave_fourteen_of_each_and_one_verified_summary(
    tmp_path: Path,
) -> None:
    """One month expires and the three stores that hold it agree about it.

    Fifteen months against a fourteen-month age is the tightest fixture that can
    fail either way: one month expires, so an off-by-one shows up as an empty
    result or as an emptied tree rather than as a shard on the wrong side.

    What the run has to leave: fourteen full-grain item-health shards, fourteen
    matching browser copies, fourteen feed-health shards, the expired item month
    present only as one aggregate whose totals equal the shard it replaced, the
    expired feed month gone, and a second run that changes no byte.
    """
    config = ObservabilityConfig()
    keep = config.item_health_full_grain_months
    months = months_back(TODAY, keep + 1)
    expired, survivors = months[0], months[1:]
    assert len(survivors) == keep == 14

    state = tmp_path / "state"
    item_health_history(state, months)
    feed_health_history(state, months)
    public = tmp_path / "frontend" / "public" / "telemetry"
    publish_telemetry.publish(state_root=state, public_root=public)
    doomed_text = ledger.item_health_path(state, f"{expired}-01").read_text(encoding="utf-8")

    first = stage_prune_state(
        observability=config,
        collect=CollectConfig(),
        retention_config=RetentionConfig(),
        run_id=RUN_ID,
        today=TODAY,
        state_dir=state,
        public_root=public,
    )
    assert first == 0

    assert [path.stem for path in month_shards(state / ledger.ITEM_HEALTH_DIRNAME)] == survivors
    assert [path.stem for path in month_shards(public)] == survivors
    assert [path.stem for path in month_shards(state / ledger.HEALTH_DIRNAME)] == survivors
    assert len(survivors) == 14

    # The expired month survives as one summary, and the summary is checked
    # against the file it replaced rather than against the code that wrote it.
    aggregate = ledger.telemetry_aggregate_path(state, expired)
    assert [path.stem for path in month_shards(state / ledger.TELEMETRY_AGGREGATE_DIRNAME)] == [
        expired
    ]
    assert totals_from_aggregate(ledger.load_telemetry_aggregate(aggregate)) == totals_from_shard(
        doomed_text
    )
    assert not publish_telemetry.shard_path(public, expired).exists()
    assert not ledger.health_path(state, f"{expired}-01").exists()

    # Every window a 366-day console read can select still names a file that is
    # there. `shards_in_window` is the reader's own helper, so this is the read
    # itself rather than a restatement of it.
    for offset in range(31):
        anchor = (TODAY - timedelta(days=offset)).isoformat()
        for stem in ledger.shards_in_window(anchor, CONSOLE_MAX_WINDOW_DAYS):
            if stem < months[0] or stem > months[-1]:
                continue
            assert publish_telemetry.shard_path(public, stem).exists(), (
                f"a {CONSOLE_MAX_WINDOW_DAYS}-day read anchored on {anchor} names "
                f"{stem}, which this prune deleted"
            )

    everything = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*.csv"))
    }

    assert (
        stage_prune_state(
            observability=config,
            collect=CollectConfig(),
            retention_config=RetentionConfig(),
            run_id=RUN_ID,
            today=TODAY,
            state_dir=state,
            public_root=public,
        )
        == 0
    )

    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*.csv"))
    } == everything, "a second run over a settled tree must move no byte"


def test_the_stage_names_every_file_a_live_run_would_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The dry run's whole deliverable: the paths, not a count.

    This list is what a person reads before turning the deletion on, so it is
    the POSIX relative path of each file (`CLAUDE.md` section 2) and it says
    "would remove" rather than "removed" while nothing is being removed.
    """
    config = ObservabilityConfig()
    months = months_back(TODAY, config.item_health_full_grain_months + 1)
    state = tmp_path / "state"
    item_health_history(state, months)
    feed_health_history(state, months)
    public = tmp_path / "frontend" / "public" / "telemetry"
    publish_telemetry.publish(state_root=state, public_root=public)
    expired = months[0]

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=config,
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
                public_root=public,
                dry_run=True,
            )
            == 0
        )

    named = sorted(
        line.split("would remove ", 1)[1]
        for line in caplog.text.splitlines()
        if "prune-state would remove " in line and not line.endswith("files:")
    )
    assert named == sorted(
        [
            f"state/item-health/{expired}.csv",
            f"state/feed-health/{expired}.csv",
            f"frontend/public/telemetry/{expired}.csv",
        ]
    )
    assert "\\" not in caplog.text, "a path leaving the process is POSIX (section 2)"
    assert ledger.item_health_path(state, f"{expired}-01").exists()
    assert publish_telemetry.shard_path(public, expired).exists()
    assert ledger.health_path(state, f"{expired}-11").exists()


def test_the_stage_says_so_when_there_is_nothing_to_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Silence and "nothing expired" read the same, and only one of them is true."""
    state = tmp_path / "state"
    day = f"{TODAY:%Y-%m}-04"
    ledger.append_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)]
    )

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "prune-state removes no file today" in caplog.text


def test_the_stage_reports_what_it_folded(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """What a person reads off the run: which months went, and how many rows they held."""
    state = a_state_tree(tmp_path)
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )
    assert "telemetry fold:" in caplog.text
    assert "2025-06" in caplog.text, "the oldest month past the window has to be named"
    assert "2025-07" not in caplog.text, "the oldest month kept must not be folded"


def test_the_stage_says_so_when_every_month_is_still_at_full_grain(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    state = tmp_path / "state"
    day = f"{TODAY:%Y-%m}-04"
    ledger.append_item_health(
        state, day, [health_row(day=day, run=1, number=1, stage=ItemStage.PUBLISH)]
    )
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )
    assert "every month is still at full grain" in caplog.text
    assert ledger.item_health_path(state, day).exists()


# --- The seen shards ---------------------------------------------------------


def _seen_shard(state: Path, stem: str, rows: int = 1) -> Path:
    """One month of the seen ledger, written by the real appender."""
    day = f"{stem}-15"
    ledger.append_seen(
        state,
        day,
        [
            SeenRow(
                version=SeenRow.schema_version(),
                url_key=hashlib.sha256(f"{stem}-{n}".encode()).hexdigest(),
                first_seen_at=f"{day}T06:00:00Z",
                first_seen_run=f"{day}-1",
            )
            for n in range(rows)
        ],
    )
    return ledger.seen_path(state, day)


def test_a_seen_shard_the_planner_still_reads_is_never_deleted(tmp_path: Path) -> None:
    """The keep-set is the reader's own, so this is a property rather than a list.

    Every stem `load_seen` would open is asserted to survive, for the window the
    committed config actually sets - not for a window the test picked.
    """
    state = tmp_path / "state"
    window = CollectConfig().seen_window_days
    today = TODAY.isoformat()
    inside = ledger.shards_in_window(today, window)
    for stem in inside:
        _seen_shard(state, stem)

    result = prune_seen(state, today=today, within_days=window)

    assert result.deleted == ()
    assert sorted(result.kept) == sorted(inside)
    assert all(ledger.seen_path(state, f"{stem}-15").exists() for stem in inside)


def test_a_seen_shard_outside_the_window_goes_and_says_what_it_weighed(
    tmp_path: Path,
) -> None:
    """A shard no read can reach is bytes answering no question.

    `2024-01` is far outside any window this config can name, and the assertion
    is that `load_seen` cannot see it either - the two have to agree, or the
    prune is deleting something the planner wanted.
    """
    state = tmp_path / "state"
    window = CollectConfig().seen_window_days
    today = TODAY.isoformat()
    stale = _seen_shard(state, "2024-01", rows=3)
    weight = stale.stat().st_size
    kept = _seen_shard(state, TODAY.strftime("%Y-%m"))

    before = ledger.load_seen(state, today=today, within_days=window)
    result = prune_seen(state, today=today, within_days=window)
    after = ledger.load_seen(state, today=today, within_days=window)

    assert result.deleted == ("2024-01",)
    assert result.bytes_freed == weight
    assert not stale.exists()
    assert kept.exists()
    # What the prune removed was already invisible: the reader's answer is
    # unchanged, which is the whole safety claim stated as data.
    assert after == before


def test_a_dry_run_names_the_shard_and_leaves_it(tmp_path: Path) -> None:
    state = tmp_path / "state"
    stale = _seen_shard(state, "2024-01")

    result = prune_seen(
        state, today=TODAY.isoformat(), within_days=CollectConfig().seen_window_days, dry_run=True
    )

    assert result.deleted == ("2024-01",)
    assert result.dry_run
    assert stale.exists()


def test_the_stage_says_so_when_every_seen_shard_is_inside_the_window(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A prune that deleted nothing has to say which window it measured against.

    Without the number, "nothing was deleted" reads the same whether the window
    is 90 days or the config went missing.
    """
    state = tmp_path / "state"
    _seen_shard(state, TODAY.strftime("%Y-%m"))

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "seen prune: every shard is inside the" in caplog.text
    assert str(CollectConfig().seen_window_days) in caplog.text


def test_what_is_kept_reaches_further_back_than_the_planner_ever_reads() -> None:
    """The margin, in days, over every anchor date a year can offer.

    The prune keeps whole month files and the reader asks for a span of days, so
    the two are only comparable in days: what survives is every row on or after
    the first of the oldest month the reader opens. This walks a year of anchor
    dates and asserts that span is never shorter than `seen_window_days` - the
    property the whole design rests on, stated as arithmetic rather than as a
    claim about one date.

    Measured over the 366 dates from 2026-01-01, at the committed window of 90
    days: the retained span runs 90 to 120 days, so the margin is 0 to 30. It is
    zero on the dates where the window's oldest day is already the first of a
    month, and thirty where it is the last - the whole shard is kept either way.
    """
    window = CollectConfig().seen_window_days
    margins = []
    for offset in range(366):
        anchor = date(2026, 1, 1) + timedelta(days=offset)
        oldest_kept = min(ledger.shards_in_window(anchor.isoformat(), window))
        first_row_kept = date.fromisoformat(f"{oldest_kept}-01")
        retained_days = (anchor - first_row_kept).days
        assert retained_days >= window, (
            f"on {anchor} the prune keeps back to {first_row_kept}, which is "
            f"{retained_days} days - the planner reads {window}"
        )
        margins.append(retained_days - window)

    assert min(margins) >= 0
    # Never wider than one whole shard, or the prune is keeping a month the
    # reader cannot reach through any date.
    assert max(margins) < 31, f"margin ran to {max(margins)} days"


def test_a_shard_newer_than_the_date_it_was_handed_is_never_deleted(
    tmp_path: Path,
) -> None:
    """A back-dated invocation must not delete the shard every later plan opens.

    `--date` takes whatever it is handed, so `prune-state --date <last January>`
    computes a window around last January. Every shard since is outside it. The
    rule is "older than the oldest month the reader opens", not "outside the
    window", so those shards stay and only the genuinely older one goes.
    """
    state = tmp_path / "state"
    window = CollectConfig().seen_window_days
    live = _seen_shard(state, "2026-08")
    stale = _seen_shard(state, "2024-01")

    result = prune_seen(state, today="2026-01-05", within_days=window)

    assert result.deleted == ("2024-01",)
    assert live.exists(), "the live shard was deleted by a run given an older date"
    assert not stale.exists()
    # And the planner reading at its own date still finds the rows it wants.
    assert ledger.load_seen(state, today="2026-08-31", within_days=window)


# --- The trace tree ----------------------------------------------------------

#: A day inside the committed window's own month, so the fixtures below read as a
#: recent run rather than one the seen tests already use.
TRACE_TODAY: Final = date(2026, 8, 20)


def _write_trace(state: Path, run_id: str, shard: int = 0, *, spans: int = 45) -> Path:
    """One shard's committed trace at the real path, with real span records in it.

    The bytes are a `telemetry.Span` serialized the way `FileSink` writes it, so
    a per-run size the byte-bound test reads off the fixture is the size a run
    actually writes rather than a number this test invented.
    """
    path = telemetry.committed_trace_path(state, run_id, shard)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = telemetry.Span(
        trace_id="unattributed",
        span_id="item-000",
        parent_id=None,
        name=telemetry.SpanName.ITEM,
        kind=telemetry.SpanKind.SPAN,
        started_at=f"{run_id[:10]}T02:20:00Z",
        duration_ms=1234,
        attributes={"run_id": run_id, "shard": shard, "url_key": "a" * 64},
    ).as_record()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join([line] * spans) + "\n", encoding="utf-8")
    return path


def test_a_trace_past_the_window_is_gone_and_a_recent_one_stays(tmp_path: Path) -> None:
    """The oracle: the oldest trace is deleted, the newest is kept, on the real path.

    Four runs across the seven-day boundary. `2026-08-14` is six days back and
    inside the window; `2026-08-13` is seven days back and outside it - so the
    boundary itself is exercised, not just a run three weeks old.
    """
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    newest = _write_trace(state, "2026-08-20-1")
    edge_kept = _write_trace(state, "2026-08-14-1")
    edge_gone = _write_trace(state, "2026-08-13-1")
    oldest = _write_trace(state, "2026-07-30-1")

    result = prune_traces(state, today=TRACE_TODAY, within_days=window)

    assert newest.exists()
    assert edge_kept.exists()
    assert not edge_gone.exists(), "a trace seven days back was inside the window"
    assert not oldest.exists()
    assert result.kept == 2
    assert telemetry.committed_trace_relpath("2026-07-30-1", 0) in result.deleted
    assert telemetry.committed_trace_relpath("2026-08-20-1", 0) not in result.deleted


def test_the_window_bounds_the_tree_by_construction(tmp_path: Path) -> None:
    """The bound is a number, not an intent: surviving bytes <= window x per-run.

    Seeded with one run a day for a month at a real per-run size, the tree
    collapses to exactly the window's worth of files. Measured 2026-09-06 off a
    real traced run: about 0.47 MB for the 160-item work spans, so a seven-day
    window bounds state/traces/ well under the 1 GB Pages reference it is not
    even part of.
    """
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    per_run = 0
    for back in range(30):
        run_day = TRACE_TODAY - timedelta(days=back)
        per_run = max(per_run, _write_trace(state, f"{run_day.isoformat()}-1").stat().st_size)

    result = prune_traces(state, today=TRACE_TODAY, within_days=window)

    root = state / "traces"
    files = list(root.rglob("*.jsonl"))
    surviving = sum(path.stat().st_size for path in files)
    assert len(files) == window, "one run a day, so exactly the window's days survive"
    assert surviving <= window * per_run
    assert result.kept == window


def test_an_empty_trace_tree_is_a_no_op(tmp_path: Path) -> None:
    """state/traces/ does not exist until tracing is switched on (a later plan), so
    the prune walks nothing and changes nothing on every run until then."""
    state = tmp_path / "state"
    result = prune_traces(
        state, today=TRACE_TODAY, within_days=ObservabilityConfig().trace_window_days
    )
    assert result == TracePruneResult(deleted=(), bytes_freed=0, kept=0, dry_run=False)
    assert not result.changed


def test_a_dry_run_names_the_trace_and_leaves_it(tmp_path: Path) -> None:
    """The dry run's list is what a person reads before the deletion is switched on,
    so it names the file and removes nothing."""
    state = tmp_path / "state"
    stale = _write_trace(state, "2026-07-30-1")

    result = prune_traces(
        state,
        today=TRACE_TODAY,
        within_days=ObservabilityConfig().trace_window_days,
        dry_run=True,
    )

    assert telemetry.committed_trace_relpath("2026-07-30-1", 0) in result.deleted
    assert result.dry_run
    assert stale.exists()


def test_a_trace_newer_than_the_date_it_was_handed_is_never_deleted(tmp_path: Path) -> None:
    """A back-dated run keeps the traces since. `prune-state --date <last winter>`
    computes a window around then; every run since is newer and stays."""
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    live = _write_trace(state, "2026-08-20-1")
    stale = _write_trace(state, "2026-01-01-1")

    result = prune_traces(state, today=date(2026, 8, 5), within_days=window)

    assert live.exists(), "a trace ahead of the handed date was deleted"
    assert not stale.exists()
    assert telemetry.committed_trace_relpath("2026-01-01-1", 0) in result.deleted


def test_the_stage_reports_the_trace_window_it_measured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A prune that deleted nothing still names the window, or 'nothing deleted' reads
    the same whether the window is seven days or the config went missing."""
    state = tmp_path / "state"
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "trace prune: every committed trace is inside the" in caplog.text
    assert str(ObservabilityConfig().trace_window_days) in caplog.text


# --- The score ledger --------------------------------------------------------


def score_row(*, day: str, run: int, number: int) -> EvalRow:
    """One eval row, built off the committed fixture so every column is real-shaped.

    `hhem` walks the deciles and `band` follows it, so a fixture month exercises
    more than one bucket and more than one band - a summary that collapsed
    either would still pass a single-value fixture.
    """
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.05 + (number % 10) / 10, 4)
    seed = f"{day}-{run}-{number}"
    band = (
        ConfidenceBand.HIGH
        if faithfulness >= 0.80
        else ConfidenceBand.MEDIUM
        if faithfulness >= 0.50
        else ConfidenceBand.LOW
    )
    return EvalRow.model_validate(
        {
            **base,
            "date": day,
            "run_id": f"{day}-{run}",
            "item_id": f"ai-{number:04d}",
            "url_key": hashlib.sha256(seed.encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{seed}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": band.value,
            "unsupported_numbers": number % 3,
            "hedge_dropped": number % 4 == 0,
            "extraction_suspect": number % 5 == 0,
            "source_word_count": 1320,
            "source_seen_word_count": 1320 - (number % 2) * 40,
            "score_ms": 1000 + number,
            "scored_at": f"{day}T06:18:02Z",
        }
    )


def score_history(state_dir: Path, months: list[str]) -> None:
    """A real score shard per month, written through the real appender."""
    for index, month in enumerate(months):
        for day_of_month in (4, 17):
            day = f"{month}-{day_of_month:02d}"
            score_writer.append(
                state_dir,
                [score_row(day=day, run=1, number=index * 100 + offset) for offset in range(6)],
            )


def a_score_tree(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    return state


def test_a_score_month_past_the_window_is_summarised_and_then_deleted(tmp_path: Path) -> None:
    """The whole point: the shard goes, and everything it could still answer stays."""
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.scores_full_grain_months)
    doomed = [path.stem for path in score_writer.ledger_shards(state) if path.stem < boundary]
    assert doomed, "the fixture has to reach past the window or this proves nothing"

    result = prune_scores(state, config, TODAY)

    assert result.archived == tuple(doomed)
    assert result.dry_run is False
    assert [path.stem for path in score_writer.ledger_shards(state)] == [
        month for month in months_back(TODAY, HISTORY_MONTHS) if month >= boundary
    ]
    assert score_archive.archived_months(state) == doomed
    # Every archived month reads back through its contract and still adds up.
    for month in doomed:
        stored = score_archive.read(score_archive.archive_path(state, month))
        assert stored.month == month
        assert sum(cohort.rows for cohort in stored.cohorts) == stored.source_rows
        assert len(stored.observation_digests) == stored.source_rows
    assert result.rows_archived == sum(
        score_archive.read(score_archive.archive_path(state, month)).source_rows for month in doomed
    )


def test_a_score_month_inside_the_window_is_untouched(tmp_path: Path) -> None:
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, 3))
    held = {path.name: path.read_bytes() for path in score_writer.ledger_shards(state)}

    result = prune_scores(state, ObservabilityConfig(), TODAY)

    assert result.changed is False
    assert result.archived == ()
    assert {path.name: path.read_bytes() for path in score_writer.ledger_shards(state)} == held
    assert score_archive.archived_months(state) == []


def test_a_score_dry_run_writes_nothing_and_still_counts_both_sides(tmp_path: Path) -> None:
    """The dry run's own deliverable is the byte ratio, so it has to compute it.

    A dry run that reported only a file list would leave the person deciding
    whether to switch the deletion on with no idea what the archive costs
    (Guardrail #10). It summarises, measures both sides, and writes nothing.
    """
    state = a_score_tree(tmp_path)
    held = {path.name: path.read_bytes() for path in score_writer.ledger_shards(state)}

    result = prune_scores(state, ObservabilityConfig(), TODAY, dry_run=True)

    assert result.dry_run is True
    assert result.archived
    assert result.source_bytes > 0
    assert result.archive_bytes > 0
    assert {path.name: path.read_bytes() for path in score_writer.ledger_shards(state)} == held
    assert score_archive.archived_months(state) == []
    assert not (state / score_archive.ARCHIVE_DIRNAME).exists()


def test_a_month_with_real_volume_summarises_to_a_fraction_of_its_shard(tmp_path: Path) -> None:
    """The measurement the policy rests on, pinned as a direction rather than a figure.

    Two costs make up an archive: one digest per distinct measurement, which is
    64 hex characters against a whole CSV row of thirty-odd columns, and a fixed
    block of moments per cohort. The first is what saves the bytes and the
    second is what a thin month pays anyway - so a twelve-row month really does
    summarise LARGER than it held, and a month with a run's worth of rows in it
    does not. Fourteen-month-old months are the full ones, which is why this
    direction is the one that matters. The measured figure and its date are in
    `docs/reference/measurements.md`.
    """
    state = tmp_path / "state"
    day = "2025-01-09"
    score_writer.append(state, [score_row(day=day, run=1, number=n) for n in range(200)])
    shard = score_writer.ledger_shards(state)[0]
    source_bytes = shard.stat().st_size

    built = score_archive.summarise(shard, observation_key=score_writer.OBSERVATION_KEY)
    archive_bytes = len(built.to_json().encode("utf-8"))

    assert built.source_rows == 200
    assert len(built.cohorts) == 1
    assert archive_bytes * 2 < source_bytes, (
        f"{archive_bytes} bytes of archive against {source_bytes} of shard is not a saving"
    )


def test_a_second_score_run_over_a_settled_tree_moves_no_byte(tmp_path: Path) -> None:
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    prune_scores(state, config, TODAY)
    settled = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }

    again = prune_scores(state, config, TODAY)

    assert again.changed is False
    assert {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    } == settled


def test_a_score_file_that_is_not_a_month_shard_is_never_a_candidate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    stray = state / score_writer.LEDGER_DIRNAME / "notes.csv"
    stray.write_text("nothing the contract knows\n", encoding="utf-8")

    prune_scores(state, ObservabilityConfig(), TODAY)

    assert stray.exists(), "a directory this deletes from names what it recognises"


def test_a_score_stem_that_is_not_a_month_is_left_rather_than_archived_and_deleted(
    tmp_path: Path,
) -> None:
    """The defect this row exists for, on the one store where it deleted a file.

    `prune_scores` summarises a month past the window and then unlinks the
    shard. Its reader used to accept any seven characters of the right shape, so
    `2025-13.csv` was archived into `state/score-archive/` and then deleted here,
    while `prune_feed_health` - reading the strict rule - left the same name
    alone. Nothing in this repository writes `2025-13.csv`, so nothing could have
    said afterwards what was in it, and `prune.yml` force-pushes `main`.

    The archive directory is listed with `iterdir` rather than through
    `archived_months`, because that helper now shares the rule under test and
    would agree with the bug.
    """
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    boundary = oldest_month_kept(TODAY, ObservabilityConfig().scores_full_grain_months)
    real = [month for month in months_back(TODAY, HISTORY_MONTHS) if month < boundary]
    assert real, "the fixture has to reach past the window or this proves nothing"
    strays = {
        state / score_writer.LEDGER_DIRNAME / f"{stem}.csv": f"{stem} was never written\n"
        for stem in NOT_MONTHS
    }
    for path, text in strays.items():
        path.write_text(text, encoding="utf-8")

    prune_scores(state, ObservabilityConfig(), TODAY)

    assert {path: path.read_text(encoding="utf-8") for path in strays} == strays
    assert sorted(
        path.stem for path in (state / score_archive.ARCHIVE_DIRNAME).iterdir()
    ) == sorted(real), "only a real month is ever summarised"


def test_an_archive_that_does_not_reconcile_leaves_its_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is deleted on the strength of a summary nobody checked.

    The read-back is not enough on its own: a file that parses can still
    describe a different month. So the reconcile recomputes from the shard and
    compares, and a disagreement raises with the shard still on disk.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    doomed = [
        path
        for path in score_writer.ledger_shards(state)
        if path.stem < oldest_month_kept(TODAY, config.scores_full_grain_months)
    ]
    assert doomed
    honest = score_archive.read

    def one_row_short(path: Path) -> object:
        stored = honest(path)
        return stored.model_copy(update={"source_rows": stored.source_rows + 1})

    monkeypatch.setattr(score_archive, "read", one_row_short)

    with pytest.raises(ValueError, match="does not reconcile"):
        prune_scores(state, config, TODAY)

    assert doomed[0].exists(), "the shard was unlinked against a summary that disagreed"


def test_the_archive_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path,
) -> None:
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    assert config.score_archive_keep_months is None

    result = prune_scores(state, config, TODAY)

    assert result.hard_deleted == ()
    assert score_archive.archived_months(state)


def test_a_hard_delete_takes_the_archive_only_after_the_month_has_been_archived(
    tmp_path: Path,
) -> None:
    """A finite archive age must sit above the full-grain window, and does.

    Fifteen against fourteen, so the month that is deleted outright is one that
    was summarised on an earlier pass rather than one that never was.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig(scores_full_grain_months=14, score_archive_keep_months=15)
    prune_scores(state, ObservabilityConfig(), TODAY)
    before = score_archive.archived_months(state)
    assert len(before) > 1

    result = prune_scores(state, config, TODAY)

    assert result.hard_deleted == tuple(
        month for month in before if month < oldest_month_kept(TODAY, 15)
    )
    assert result.hard_deleted, "the fixture has to reach past both ages"
    assert score_archive.archived_months(state) == [
        month for month in before if month not in result.hard_deleted
    ]


def test_the_oracle_an_archived_month_reconciles_and_is_still_refused_as_a_repeat(
    tmp_path: Path,
) -> None:
    """The row's Oracle, both halves.

    First: the archive's source hash and row count match the shard, its
    observation digests are one-for-one with the shard's own observation keys,
    and its moments recompute exactly - checked against the raw CSV rather than
    by calling the summariser again, so the oracle cannot pass by agreeing with
    the code it is checking.

    Second, and the one that matters most: after the shard is gone, every
    measurement it held is still refused as a repeat. Without that, the day a
    month is deleted every row in it becomes scoreable again as if it were new.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.scores_full_grain_months)
    shard = next(path for path in score_writer.ledger_shards(state) if path.stem < boundary)
    raw = list(csv.DictReader(io.StringIO(shard.read_text(encoding="utf-8"))))
    fingerprint = hashlib.sha256(shard.read_bytes()).hexdigest()
    keys = {tuple(row[name] for name in score_writer.OBSERVATION_KEY) for row in raw}
    hhem_by_cohort: dict[tuple[str, ...], list[float]] = {}
    for row in raw:
        cohort = tuple(row[name] for name in score_archive.COHORT_KEY)
        hhem_by_cohort.setdefault(cohort, []).append(float(row["hhem"]))
    doomed = list(raw)

    prune_scores(state, config, TODAY)

    stored = score_archive.read(score_archive.archive_path(state, shard.stem))
    assert stored.source_sha256 == fingerprint
    assert stored.source_rows == len(raw)
    assert set(stored.observation_digests) == {score_archive.digest_of(key) for key in keys}
    assert len(stored.observation_digests) == len(keys)
    for group in stored.cohorts:
        values = hhem_by_cohort[group.key]
        moment = group.measurements["hhem"]
        assert moment.n == len(values)
        assert moment.sum == pytest.approx(sum(values))
        assert moment.sum_squares == pytest.approx(sum(value * value for value in values))
        assert moment.min == pytest.approx(min(values))
        assert moment.max == pytest.approx(max(values))

    # The second half. Every row of the deleted month, offered again.
    assert not shard.exists()
    replayed = [
        EvalRow.model_validate({key: value for key, value in row.items() if value != ""})
        for row in doomed
    ]
    assert score_writer.append(state, replayed) == 0, (
        "a deleted month made its measurements new again"
    )
    assert not shard.exists(), "the replay recreated the shard the archive replaced"


def test_the_stage_names_the_score_shard_a_live_run_would_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The dry run names the score shard too, in the POSIX form section 2 asks for."""
    state = tmp_path / "state"
    config = ObservabilityConfig()
    months = months_back(TODAY, config.scores_full_grain_months + 1)
    score_history(state, months)
    expired = months[0]

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=config,
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
                dry_run=True,
            )
            == 0
        )

    named = sorted(
        line.split("would remove ", 1)[1]
        for line in caplog.text.splitlines()
        if "prune-state would remove " in line and not line.endswith("files:")
    )
    assert named == [f"state/scores/{expired}.csv"]
    assert "\\" not in caplog.text, "a path leaving the process is POSIX (section 2)"
    assert score_writer.ledger_path(state, f"{expired}-01").exists()


def test_the_stage_says_so_when_every_score_month_is_at_full_grain(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Silence and "nothing aged out" read the same, and only one of them is true."""
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, 2))

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "score archive: every month is inside the 14-month window" in caplog.text
