"""The appearance contract: what the validators add, and what must stay in step.

Contract tier (CLAUDE.md section 12). A `Field` range is the contract's own
statement and Pydantic enforces it, so a test that feeds it a value just outside
the range restates the declaration. What is asserted here is what no declaration
says: the cross-field validators, the read-side migrations, the bindings between
this file's values and the files that copy them, and the frame-width and measure
ranges that `docs/concepts/config/appearance.md` gives as the answer to "a frame
set to 300px would need a code change to still look right".

Nothing is mocked and nothing touches the network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.appearance_config import (
    DARK_CONFIDENCE_RAMP,
    FRAME_CONSOLE_MIN_PX,
    FRAME_READING_MAX_PX,
    FRAME_READING_MIN_PX,
    LIGHT_CONFIDENCE_RAMP,
    MEASURE_CH_MAX,
    MEASURE_CH_MIN,
    AppearanceConfig,
    ChartPalette,
    FrameConfig,
    MotionConfig,
    StoryChartGeometryConfig,
    ThemeConfig,
)
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.ui import ThemeChoice, UiConfig

pytestmark = pytest.mark.contract


def test_retired_source_doubt_limit_does_not_restore_a_console_reader() -> None:
    old = {"version": "2026-11-12", "console": {"doubt_rows": 6, "source_rows": 8}}
    appearance = AppearanceConfig.model_validate(old)
    app = AppConfig.model_validate({**old, "models_file": "models/recorded-model.json"})
    for console in (appearance.console, app.console):
        assert console.source_rows == 8
        assert "doubt_rows" not in console.model_dump()
    with pytest.raises(ValidationError, match="doubt_row"):
        ConsoleConfig.model_validate({"doubt_row": 6})


REPO_ROOT = Path(__file__).resolve().parents[2]
APPEARANCE_PATH = REPO_ROOT / "config" / "appearance.json"


def test_machine_palette_matches_the_frontend_vocabulary() -> None:
    source = (REPO_ROOT / "frontend/src/lib/server/config.ts").read_text()
    copied = re.search(r"palette: ([^;]+);", source)
    assert copied is not None
    assert set(re.findall(r"'([^']+)'", copied[1])) == {value.value for value in ChartPalette}


def committed_app_config() -> AppConfig:
    """`AppConfig` has one block with no default, so `{}` is not a document.

    There is no honest default for "which weights", and a wrong guess would
    silently run the wrong model.
    """
    return AppConfig.model_validate(
        json.loads((REPO_ROOT / "config" / "idhazh.json").read_text(encoding="utf-8"))
    )


def test_the_committed_file_is_ascii() -> None:
    """Section 5 requires ASCII; checkout line endings belong to `.gitattributes`."""
    raw = APPEARANCE_PATH.read_bytes()
    assert all(byte < 128 for byte in raw), "config/appearance.json must be ASCII"


def test_story_chart_geometry_is_committed_and_refuses_unusable_dash_arrays() -> None:
    appearance = AppearanceConfig.model_validate_json(APPEARANCE_PATH.read_text(encoding="utf-8"))
    assert appearance.chart.story_geometry == StoryChartGeometryConfig()
    for invalid in (
        {"line_series_dash_arrays": ("none",) * 8},
        {
            "line_series_dash_arrays": (
                "none",
                "0 2",
                "2 3",
                "8 2 2 2",
                "1 3",
                "12 3",
                "4 2 1 2",
                "3 1 1 1",
            )
        },
    ):
        with pytest.raises(ValidationError):
            StoryChartGeometryConfig.model_validate(invalid)


@pytest.mark.parametrize(
    "style",
    [
        {"colors": {"light": {"accent": "#AABBCC"}}},
        {"colors": {"light": {"categorical": ["#112233"] * 8}}},
        {"typography": {"small": {"size_rem": True}}},
        {"typography": {"small": {"leading_rem": 1.51}}},
        {"typography": {"body": {"leading_rem": 0.8}}},
        {"chart": {"grid_opacity": None}},
    ],
)
def test_console_style_refuses_unsafe_or_ambiguous_values(style: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AppearanceConfig.model_validate({"console_style": style})


@pytest.mark.parametrize("color", ["#1a7f4b", "#2f6f5e"])
def test_console_categories_stay_separate_from_confidence_and_movement(color: str) -> None:
    palette = AppearanceConfig.model_validate({}).console_style.colors.light.categorical
    palette[0] = color
    with pytest.raises(ValidationError, match="separate from confidence and movement"):
        AppearanceConfig.model_validate(
            {"console_style": {"colors": {"light": {"categorical": palette}}}}
        )


@pytest.mark.parametrize("width", [0, 320, FRAME_READING_MIN_PX - 1, FRAME_READING_MAX_PX + 1])
def test_a_frame_outside_the_bounds_is_refused(width: int) -> None:
    """The whole answer to "a frame set to 300px would break the design".

    It cannot be set to 300px. That is not a convention, it is the contract.
    """
    with pytest.raises(ValidationError):
        FrameConfig(reading_max_px=width)


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


def test_the_days_aside_may_not_be_narrower_than_the_item_rail() -> None:
    """The aside replaces the rail at the wide breakpoint, so a narrower aside
    would give a wider screen less beside the prose than a smaller one gets."""
    with pytest.raises(ValidationError, match="zone_aside_rem"):
        FrameConfig(zone_rail_rem=20.0, zone_aside_rem=14.0)
    assert FrameConfig(zone_rail_rem=14.0, zone_aside_rem=14.0).zone_aside_rem == 14.0


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


def test_the_default_theme_is_the_one_root_carries() -> None:
    """Declared defaults agree with the CSS base and both first-paint scripts.

    The config field does not drive first paint. This checks agreement, not
    runtime configurability or the reader's stored choice.
    """
    tokens = (REPO_ROOT / "frontend" / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")
    base = re.search(r"^:root\s*,\s*\[data-theme=['\"](\w+)['\"]\]\s*\{", tokens, re.MULTILINE)
    assert base is not None, "tokens.css no longer names the theme sharing the :root group"
    theme = ThemeChoice(base.group(1))
    appearance = AppearanceConfig.model_validate_json(APPEARANCE_PATH.read_text(encoding="utf-8"))
    for name, declared in {
        "appearance default": AppearanceConfig.model_validate({}).digest.theme_default,
        "UI default": UiConfig().theme_default,
        "config/appearance.json": appearance.digest.theme_default,
        "config/idhazh.json": committed_app_config().ui.theme_default,
    }.items():
        assert declared is theme, f"{name} disagrees with the CSS base theme"

    app = (REPO_ROOT / "frontend" / "src" / "app.html").read_text(encoding="utf-8")
    reader = (REPO_ROOT / "frontend" / "src" / "lib" / "theme.ts").read_text(encoding="utf-8")
    for name, source, pattern in (
        ("app.html initial choice", app, r"var\s+choice\s*=\s*'(\w+)'"),
        ("app.html storage refusal", app, r"catch\s*\([^)]*\)\s*\{\s*choice\s*=\s*'(\w+)'"),
        ("theme.ts absent storage", reader, r"if\s*\(typeof localStorage[^;]+return\s*'(\w+)'"),
        ("theme.ts absent choice", reader, r"return localStorage\.getItem[^;]+:\s*'(\w+)'"),
        ("theme.ts storage refusal", reader, r"return typeof document[^;]+:\s*'(\w+)'"),
    ):
        fallback = re.search(pattern, source)
        assert fallback is not None, f"{name} no longer declares its fallback"
        assert fallback.group(1) == theme.value, f"{name} disagrees with the CSS base theme"


def test_a_config_that_still_says_system_reads_as_dark() -> None:
    """The read-side migration (section 11).

    A file written before 2026-08-31 names a member the enum no longer has. It
    still has to load, and the only honest reading of "follow the device" once
    nothing asks the device is the base theme.
    """
    assert (
        AppearanceConfig.model_validate(
            {"digest": {"theme_default": "system"}}
        ).digest.theme_default
        is ThemeChoice.DARK
    )


def test_a_theme_that_never_existed_is_still_refused() -> None:
    """The migration reads one legacy value, not any string that arrives."""
    with pytest.raises(ValidationError):
        AppearanceConfig.model_validate({"digest": {"theme_default": "sepia"}})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("movement_good_light", LIGHT_CONFIDENCE_RAMP["--band-high"]),
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


@pytest.mark.parametrize("value", ["2f6f5e", "#2F6F5E"])
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
            declared = re.search(rf"--movement-{name}:\s*(#[0-9a-f]{{6}});", tokens[start:end])
            assert declared is not None, f"--movement-{name} is not declared in the {block} theme"
            assert declared.group(1) == getattr(theme, f"movement_{name}_{block}"), (
                f"tokens.css and config/appearance.json disagree about "
                f"--movement-{name} on the {block} theme"
            )
