"""The appearance contract: the bounds are the reason the knobs are allowed to exist.

Contract tier (CLAUDE.md section 13). `config/appearance.json` carries the frame
width, the measure and the breakpoints, which a 2026-08-28 advisory ruling said
should not be knobs at all - the argument being that a frame set to 300px would
need a code change to still look right. That argument is true of an unvalidated
number and false of a validated one, so these tests are the argument: every
bound that makes the knob safe is asserted here, in both directions.

Nothing is mocked and nothing touches the network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig, ThemeChoice, UiConfig
from idhazh.contracts.appearance_config import (
    DARK_CONFIDENCE_RAMP,
    FRAME_CONSOLE_MIN_PX,
    FRAME_READING_MAX_PX,
    FRAME_READING_MIN_PX,
    LIGHT_CONFIDENCE_RAMP,
    MEASURE_CH_MAX,
    MEASURE_CH_MIN,
    AppearanceConfig,
    ChartConfig,
    FrameConfig,
    MotionConfig,
    ThemeConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
APPEARANCE_PATH = REPO_ROOT / "config" / "appearance.json"


def committed_app_config() -> AppConfig:
    """`AppConfig` has one block with no default, so `{}` is not a document.

    There is no honest default for "which weights", and a wrong guess would
    silently run the wrong model.
    """
    return AppConfig.model_validate(
        json.loads((REPO_ROOT / "config" / "idhazh.json").read_text(encoding="utf-8"))
    )


def test_the_committed_file_validates() -> None:
    """The file an operator edits is the shape the contract declares."""
    AppearanceConfig.model_validate(json.loads(APPEARANCE_PATH.read_text(encoding="utf-8")))


def test_the_committed_file_is_lf_and_ascii() -> None:
    """`.gitattributes` pins `config/*.json` to LF, and section 5 pins ASCII.

    A config file whose bytes shift with the checkout changes the hash the run
    manifest records for it.
    """
    raw = APPEARANCE_PATH.read_bytes()
    assert b"\r" not in raw, "config/appearance.json must be LF"
    assert all(byte < 128 for byte in raw), "config/appearance.json must be ASCII"


def test_defaults_alone_are_a_valid_document() -> None:
    """A fresh clone runs on the defaults (section 1a)."""
    resolved = AppearanceConfig.model_validate({})
    assert resolved.frame.reading_max_px >= FRAME_READING_MIN_PX
    assert resolved.version == AppearanceConfig.schema_version()


@pytest.mark.parametrize("width", [0, 320, FRAME_READING_MIN_PX - 1, FRAME_READING_MAX_PX + 1])
def test_a_frame_outside_the_bounds_is_refused(width: int) -> None:
    """The whole answer to "a frame set to 300px would break the design".

    It cannot be set to 300px. That is not a convention, it is the contract.
    """
    with pytest.raises(ValidationError):
        FrameConfig(reading_max_px=width)


@pytest.mark.parametrize("width", [FRAME_READING_MIN_PX, 1280, FRAME_READING_MAX_PX])
def test_a_frame_inside_the_bounds_is_accepted(width: int) -> None:
    """And the bound is a range, not a single blessed value - or it is a constant."""
    assert FrameConfig(reading_max_px=width, console_max_px=2000).reading_max_px == width


@pytest.mark.parametrize("measure", [0, MEASURE_CH_MIN - 1, MEASURE_CH_MAX + 1, 400])
def test_a_measure_outside_the_readable_range_is_refused(measure: int) -> None:
    """Below about 52 the eye returns too often; above about 80 it loses the line."""
    with pytest.raises(ValidationError):
        FrameConfig(measure_ch=measure)


def test_the_console_may_not_be_narrower_than_the_reading_frame() -> None:
    """An instrument that gets less room than a paragraph is the original defect."""
    with pytest.raises(ValidationError, match="console_max_px"):
        FrameConfig(reading_max_px=1400, console_max_px=FRAME_CONSOLE_MIN_PX)


def test_breakpoints_must_be_three_ascending_and_distinct() -> None:
    """Three is a decision: phone to tablet, side rail, third column."""
    with pytest.raises(ValidationError):
        FrameConfig(breakpoints_px=[640, 1024])
    with pytest.raises(ValidationError):
        FrameConfig(breakpoints_px=[1024, 640, 1400])
    with pytest.raises(ValidationError):
        FrameConfig(breakpoints_px=[640, 640, 1400])
    assert FrameConfig(breakpoints_px=[600, 900, 1300]).breakpoints_px == [600, 900, 1300]


def test_gutters_are_ordered() -> None:
    with pytest.raises(ValidationError, match="gutter"):
        FrameConfig(gutter_min_px=32, gutter_max_px=16)


def test_a_sparkline_can_never_be_taller_than_a_chart() -> None:
    """Held by the field bounds rather than by a cross-field validator.

    `sparkline_height_px` tops out at 96 and `height_px` starts at 120, so the
    two ranges cannot overlap. A validator here would never fire, and a
    validator that cannot fire reads like a guarantee nobody is holding.
    """
    with pytest.raises(ValidationError):
        ChartConfig(sparkline_height_px=97)
    with pytest.raises(ValidationError):
        ChartConfig(height_px=119)
    assert ChartConfig(sparkline_height_px=96, height_px=120).height_px == 120


def test_a_readout_may_not_be_wider_than_the_plot_or_zero_wide() -> None:
    """A readout at 0 is a strip nobody can read; one over 1 is not a share.

    The strip sits below the plot, so no value here can cover a mark. The bound
    is against the other failure: a readout as wide as the chart it explains,
    which is what the floating box it replaced was - 40 to 55 percent of a
    220px plot, measured 2026-08-29.
    """
    for refused in (0.0, -0.1, 1.01, 2.0):
        with pytest.raises(ValidationError):
            ChartConfig(readout_max_share=refused)
    assert ChartConfig(readout_max_share=1.0).readout_max_share == 1.0
    assert ChartConfig().readout_max_share == 0.33


def test_fast_motion_is_faster_than_base_motion() -> None:
    with pytest.raises(ValidationError, match="duration_fast_ms"):
        MotionConfig(duration_fast_ms=400, duration_base_ms=100)


def test_the_server_may_not_prerender_wider_than_the_frame() -> None:
    """A chart drawn wider than its container snaps on every first paint.

    It self-corrects once a script runs, which is the one moment a static site
    is supposed to be already finished.
    """
    with pytest.raises(ValidationError, match="width_px"):
        AppearanceConfig.model_validate(
            {"frame": {"console_max_px": 1200, "reading_max_px": 1100}, "chart": {"width_px": 1600}}
        )


def test_the_moved_blocks_keep_the_same_shape_on_both_sides() -> None:
    """The file moved; the contract did not fork.

    One definition, two exposure points. If these ever diverge, a knob means one
    thing to `config/idhazh.json` and another to `config/appearance.json`, and
    the frontend's fallback merge silently mixes them.

    `AppConfig` is loaded from the committed file rather than from `{}` because
    it has one block with no default on purpose - there is no honest default for
    "which weights", and a wrong guess would silently run the wrong model.
    """
    appearance = AppearanceConfig.model_validate({})
    app = AppConfig.model_validate(
        json.loads((REPO_ROOT / "config" / "idhazh.json").read_text(encoding="utf-8"))
    )
    assert type(appearance.digest) is type(app.ui)
    assert type(appearance.console) is type(app.console)
    assert type(appearance.assist) is type(app.assist)


def test_the_legacy_blocks_still_validate_so_an_unmigrated_config_still_reads() -> None:
    """The read-side migration's other half (section 11).

    `AppConfig` keeps `ui`, `console` and `assist`, so a `config/idhazh.json`
    written before 2026-08-29 is still a valid document and the frontend's
    fallback has something to fall back to.
    """
    legacy = json.loads((REPO_ROOT / "config" / "idhazh.json").read_text(encoding="utf-8"))
    resolved = AppConfig.model_validate(legacy)
    assert resolved.ui.archive_page_size >= 1
    assert resolved.console.chart_width >= 240


def test_the_archive_may_not_list_more_than_a_month_of_days_as_rows() -> None:
    """The bound is the whole reason this knob is allowed to exist.

    `archive_recent_days` is how many days the archive lists as rows of their
    own before the month disclosures take over. Set to 400 the block is the
    wall of dates it replaced, and the design decision the row settled is
    undone by an edit to one line of config. Set to 0 the page loses its only
    surface that works with no script at all.
    """
    for refused in (0, -1, 32, 400):
        with pytest.raises(ValidationError, match="archive_recent_days"):
            UiConfig(archive_recent_days=refused)
    assert UiConfig(archive_recent_days=1).archive_recent_days == 1
    assert UiConfig(archive_recent_days=31).archive_recent_days == 31
    assert UiConfig().archive_recent_days == 7


def test_the_default_theme_is_the_one_root_carries() -> None:
    """A fresh clone is served dark, because `:root` in tokens.css is dark.

    The knob and the first painted frame have to name the same theme. If this
    ever says `light` again, a page paints dark and the config says otherwise.
    """
    assert AppearanceConfig.model_validate({}).digest.theme_default is ThemeChoice.DARK
    assert committed_app_config().ui.theme_default is ThemeChoice.DARK


def test_system_is_no_longer_a_theme_anyone_can_choose() -> None:
    """It was the absence of a choice, and nothing asks the device any more."""
    assert [choice.value for choice in ThemeChoice] == ["light", "dark"]


def test_a_config_that_still_says_system_reads_as_dark() -> None:
    """The read-side migration (section 11).

    A file written before 2026-08-31 names a member the enum no longer has. It
    still has to load, and the only honest reading of "follow the device" once
    nothing asks the device is the base theme.
    """
    assert (
        AppearanceConfig.model_validate({"digest": {"theme_default": "system"}}).digest.theme_default
        is ThemeChoice.DARK
    )
    legacy = json.loads((REPO_ROOT / "config" / "idhazh.json").read_text(encoding="utf-8"))
    legacy["ui"]["theme_default"] = "system"
    assert AppConfig.model_validate(legacy).ui.theme_default is ThemeChoice.DARK


def test_a_theme_that_never_existed_is_still_refused() -> None:
    """The migration reads one legacy value, not any string that arrives."""
    with pytest.raises(ValidationError):
        AppearanceConfig.model_validate({"digest": {"theme_default": "sepia"}})


def test_the_schema_is_generated_and_stamped() -> None:
    schema = AppearanceConfig.json_schema()
    assert schema["$id"] == "appearance-config.schema.json"
    # The relation section 11 promises, not the stamp of the day this was
    # written. A literal date here is a line every later knob has to edit, and
    # two branches that both edit it to the same value merge clean and fail on
    # the full suite - which is a failure that says nothing about the change.
    assert schema["version"] == schema["changelog"][0]["version"]
    assert schema["version"] >= "2026-08-29", "the stamp went backwards"
    for block in ("digest", "console", "assist", "frame", "theme", "chart", "icons", "motion"):
        assert block in schema["properties"], f"{block} missing from the generated schema"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("movement_good_light", LIGHT_CONFIDENCE_RAMP["--band-high"]),
        ("movement_bad_light", LIGHT_CONFIDENCE_RAMP["--band-low"]),
        ("movement_good_light", LIGHT_CONFIDENCE_RAMP["--band-medium"]),
        ("movement_good_dark", DARK_CONFIDENCE_RAMP["--band-high"]),
        ("movement_bad_dark", DARK_CONFIDENCE_RAMP["--band-low"]),
    ],
)
def test_a_movement_colour_that_is_a_confidence_hue_is_refused(field: str, value: str) -> None:
    """`They are not the health ramp`, made mechanical.

    Green on the confidence ramp means "it worked". A summary that got 3 percent
    slower is not broken, and a movement pair that resolves to the same bytes as
    `--band-*` is the confidence ramp under a second name - which is exactly the
    alarm fatigue the pair was added to avoid.
    """
    with pytest.raises(ValidationError):
        ThemeConfig.model_validate({field: value})


def test_one_colour_cannot_say_both_directions() -> None:
    with pytest.raises(ValidationError):
        ThemeConfig(movement_good_light="#2f6f5e", movement_bad_light="#2f6f5e")


@pytest.mark.parametrize("value", ["2f6f5e", "#2F6F5E", "#2f6f5", "rebeccapurple", ""])
def test_a_movement_colour_that_is_not_a_lower_case_six_digit_hex_is_refused(value: str) -> None:
    """One form, because `tokens.css` writes one form and `tokens.spec.ts` reads it back."""
    with pytest.raises(ValidationError):
        ThemeConfig(movement_good_light=value)


def test_the_committed_movement_pair_is_what_tokens_css_declares() -> None:
    """The config file and the token file are two copies of one decision.

    `scripts/build-frame-css.mjs` emits the config values after `tokens.css`
    loads, so the two disagreeing means the committed default is dead and no
    diff shows it.
    """
    theme = AppearanceConfig.model_validate(
        json.loads(APPEARANCE_PATH.read_text(encoding="utf-8"))
    ).theme
    tokens = (REPO_ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
    # Dark is the base block and light is the override that follows it, so the
    # light selector is the boundary between the two.
    light_at = tokens.index("[data-theme='light']")
    for block, start, end in (("dark", 0, light_at), ("light", light_at, len(tokens))):
        for name in ("good", "bad"):
            declared = re.search(
                rf"--movement-{name}:\s*(#[0-9a-f]{{6}});", tokens[start:end]
            )
            assert declared is not None, f"--movement-{name} is not declared in the {block} theme"
            assert declared.group(1) == getattr(theme, f"movement_{name}_{block}"), (
                f"tokens.css and config/appearance.json disagree about "
                f"--movement-{name} on the {block} theme"
            )
