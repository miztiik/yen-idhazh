"""How big is the published site, how fast is it growing, and when does the alarm fire?"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.cli import main
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.retention import PAGES_HARD_CAP_MB, RetentionConfig
from idhazh.retention import (
    BYTES_PER_MB,
    SiteSize,
    budget_alarm,
    cap_breach,
    count_published_items,
    daily_growth_bytes,
    days_to_alarm,
    days_to_cap,
    headroom_mb,
    heaviest_directories,
    measure,
    over_budget,
    over_cap,
)
from idhazh.stages.site_weight import stage_site_weight

from ._trees import (
    FASTEST_MEASURED_KB_PER_DAY,
    WARNING_DAYS_REQUIRED,
    days_of_warning,
    site,
)


def test_an_absent_site_measures_as_nothing(tmp_path: Path) -> None:
    assert measure(tmp_path / "missing").bytes_used == 0


def test_the_site_is_measured_every_run(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a-0000000001.webp", "b-0000000002.webp"]})
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
        f"docs/reference/pipeline-cost.md before changing it here"
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
    root = site(tmp_path, {"2026-08-21": ["a-0000000001.webp"]})
    (root / "2026" / "08" / "21" / "big-0000000005.webp").write_bytes(b"x" * 2 * BYTES_PER_MB)
    before = measure(root)
    assert over_budget(before, RetentionConfig(site_budget_mb=1)) is True
    assert measure(root) == before


def test_a_small_site_is_not_over_budget(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a-0000000001.webp"]})
    assert not over_budget(measure(root), RetentionConfig())


def test_the_alarm_speaks_only_when_over_budget(tmp_path: Path) -> None:
    """The words the run logs: None below the budget, a headroom line above it."""
    root = site(tmp_path, {"2026-08-21": ["a-0000000001.webp"]})
    (root / "2026" / "08" / "21" / "big-0000000005.webp").write_bytes(b"x" * 2 * BYTES_PER_MB)
    over = measure(root)
    assert budget_alarm(over, RetentionConfig()) is None
    line = budget_alarm(over, RetentionConfig(site_budget_mb=1))
    assert line is not None
    assert "alarm point" in line
    assert "Pages cap" in line


def test_headroom_is_measured_against_the_hard_cap(tmp_path: Path) -> None:
    root = site(tmp_path, {"2026-08-21": ["a-0000000001.webp"]})
    assert headroom_mb(measure(root)) == pytest.approx(PAGES_HARD_CAP_MB, abs=1)


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
    root = site(tmp_path, {"2020-01-01": ["a-0000000001.webp", "b-0000000002.webp"], "2026-08-20": ["new-0000000004.webp"]})
    (root / "sitemap.xml").write_bytes(b"x" * 40)
    before = measure(root)

    doomed = [root / "2020" / "01" / "01" / "a-0000000001.webp", root / "sitemap.xml"]
    sizes = {path: path.stat().st_size for path in doomed}
    for path in doomed:
        path.unlink()

    assert before.minus(root, sizes) == measure(root)


def test_maintaining_the_total_does_not_read_more_as_the_tree_grows(tmp_path: Path) -> None:
    """Guardrail #12, counted. The walk grows with the archive and the retraction does not."""
    small = site(tmp_path / "small", {"2026-08-20": ["a-0000000001.webp", "b-0000000002.webp"]})
    large = site(
        tmp_path / "large",
        {f"2026-08-{day:02d}": [f"p-{n:010d}.webp" for n in range(6)] for day in range(1, 11)},
    )

    walked_small = reads_during(lambda: measure(small))
    walked_large = reads_during(lambda: measure(large))
    assert walked_large > walked_small, (
        "the independent walk is supposed to grow with the tree - it is the audit"
    )

    carried_small = measure(small)
    carried_large = measure(large)
    assert (
        reads_during(lambda: carried_small.minus(small, {small / "2026/08/20/a-0000000001.webp": 1000})) == 0
    )
    assert (
        reads_during(lambda: carried_large.minus(large, {large / "2026/08/01/p-0000000000.webp": 1000})) == 0
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

    This is also the permitted case of the bound. `contracts/test_app_config.py` holds
    refusal, and neither case alone is a bound: one shows the number can be lowered
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
