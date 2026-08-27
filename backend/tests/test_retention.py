"""Unit-tier tests for the retention job and the site-budget alarm.

The prune is the most dangerous code in this repository - it is the only thing
that deletes a published byte - so the tests are written around the ways it goes
wrong rather than the way it goes right.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh.cli import main, stage_site_weight
from idhazh.contracts.app_config import RetentionConfig
from idhazh.retention import (
    BYTES_PER_MB,
    PAGES_HARD_CAP_MB,
    SiteSize,
    budget_alarm,
    cap_breach,
    cutoff,
    headroom_mb,
    measure,
    over_budget,
    over_cap,
    prune,
    visuals_older_than,
)


def site(root: Path, days: dict[str, list[str]]) -> Path:
    for day, files in days.items():
        year, month, number = day.split("-")
        folder = root / year / month / number
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "digest.json").write_text(f'{{"date": "{day}"}}', encoding="utf-8")
        for name in files:
            (folder / name).write_bytes(b"x" * 1000)
    return root


#: The fastest growth of the PUBLISHED SITE this project has measured: 16,641,956
#: bytes a published day, 2026-08-27, over the three mature committed days.
#: Rounded up to binary KB, the unit the code uses. It replaces 8,537, which was
#: unmeasured arithmetic over a hypothetical PNG on every item AND was taken over
#: the committed payload tree rather than the site - a different tree, eighteen
#: times smaller. Source and the rest of the table:
#: docs/reference/measurements.md, "Days to the 1 GB Pages ceiling".
FASTEST_MEASURED_KB_PER_DAY = 16_252
#: Days the alarm must buy at that rate. A judgement about one maintainer
#: reading one issue, not a measurement (Rule #10), and derived as one in
#: docs/reference/measurements.md, "Where the alarm fires, and what it buys".
WARNING_DAYS_REQUIRED = 14


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


def test_the_gate_fails_when_the_built_site_crosses_the_platform_cap(tmp_path: Path) -> None:
    """Past the cap the bytes cannot be published, so the build stops here.

    The alarm point stays at its shipped 800 MB, so this proves the cap is
    checked on its own rather than as a louder alarm.
    """
    tree = built_site(tmp_path / "build", 3)
    assert stage_site_weight(tree, RetentionConfig(), cap_mb=2) == 1


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


def test_a_directory_that_is_not_a_date_is_left_alone(tmp_path: Path) -> None:
    stray = tmp_path / "assets" / "brand"
    stray.mkdir(parents=True)
    (stray / "logo.svg").write_bytes(b"x" * 10)
    config = RetentionConfig(image_months=1, dry_run=False)
    assert prune(tmp_path, config, date(2026, 8, 21)).deleted == 0
    assert (stray / "logo.svg").exists()
