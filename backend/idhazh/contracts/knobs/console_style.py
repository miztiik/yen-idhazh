"""Which colors, type and spacing may the operator console draw with?"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from idhazh.contracts.base import Model

ConsoleFontFace = Literal["inter", "system-sans", "system-mono"]
ConsoleLinecap = Literal["butt", "round", "square"]
Color = Annotated[str, Field(pattern=r"^#[0-9a-f]{6}$")]
Size = Annotated[float, Field(strict=True, ge=0.75, le=4, allow_inf_nan=False)]
Leading = Annotated[float, Field(strict=True, ge=0.75, le=8, allow_inf_nan=False)]
Weight = Annotated[int, Field(strict=True, ge=100, le=900)]
Tracking = Annotated[float, Field(strict=True, ge=-0.1, le=0.2, allow_inf_nan=False)]
Space = Annotated[float, Field(strict=True, ge=0, le=4, allow_inf_nan=False)]
Radius = Annotated[float, Field(strict=True, ge=0, le=2, allow_inf_nan=False)]
Stroke = Annotated[float, Field(strict=True, ge=0.5, le=2, allow_inf_nan=False)]
Dash = Annotated[float, Field(strict=True, ge=0.5, le=16, allow_inf_nan=False)]
ShadowOffset = Annotated[float, Field(strict=True, ge=0, le=16, allow_inf_nan=False)]
ShadowBlur = Annotated[float, Field(strict=True, ge=0, le=32, allow_inf_nan=False)]
ShadowAlpha = Annotated[float, Field(strict=True, ge=0, le=0.2, allow_inf_nan=False)]


class ConsoleColors(Model):
    """Neutral light surfaces, teal actions and a separate categorical palette."""

    canvas: Color = "#f2f1ed"
    inset: Color = "#e9e7e1"
    surface: Color = "#fffefa"
    raised: Color = "#ffffff"
    text: Color = "#25251f"
    text_secondary: Color = "#625e55"
    text_tertiary: Color = "#746f64"
    rule: Color = "#dad6cb"
    rule_strong: Color = "#b6afa0"
    accent: Color = "#0b746e"
    accent_hover: Color = "#085d58"
    on_accent: Color = "#ffffff"
    focus: Color = "#0b746e"
    selected: Color = "#dcedea"
    chart_axis: Color = "#b6afa0"
    chart_grid: Color = "#dad6cb"
    categorical: list[Color] = Field(
        default_factory=lambda: [
            "#356a9a",
            "#7d53a0",
            "#167f99",
            "#a3427c",
            "#5968af",
            "#29739e",
            "#995aab",
            "#777268",
        ],
        min_length=8,
        max_length=8,
    )

    @model_validator(mode="after")
    def distinct_categories(self) -> Self:
        if len(set(self.categorical)) != len(self.categorical):
            raise ValueError("categorical must contain eight distinct colors")
        return self


class DarkConsoleColors(ConsoleColors):
    """The same roles on deliberately chosen dark surfaces."""

    canvas: Color = "#191917"
    inset: Color = "#151513"
    surface: Color = "#22221f"
    raised: Color = "#2b2b27"
    text: Color = "#f0ede5"
    text_secondary: Color = "#c1bcb1"
    text_tertiary: Color = "#a39c8f"
    rule: Color = "#393932"
    rule_strong: Color = "#565348"
    accent: Color = "#6bc7be"
    accent_hover: Color = "#94d9d0"
    on_accent: Color = "#122722"
    focus: Color = "#6bc7be"
    selected: Color = "#263d38"
    chart_axis: Color = "#565348"
    chart_grid: Color = "#393932"
    categorical: list[Color] = Field(
        default_factory=lambda: [
            "#8bbce5",
            "#bea2df",
            "#72c6d9",
            "#e6a1c9",
            "#a4b1e8",
            "#83bfdc",
            "#cea4e0",
            "#b0aa9e",
        ],
        min_length=8,
        max_length=8,
    )


class ConsoleColorModes(Model):
    """Each theme supplies the same color roles."""

    light: ConsoleColors = Field(default_factory=ConsoleColors)
    dark: DarkConsoleColors = Field(default_factory=DarkConsoleColors)


class ConsoleType(Model):
    """A size and its leading travel together."""

    size_rem: Size = 0.875
    leading_rem: Leading = 1.25
    weight: Weight = 400
    tracking_em: Tracking = 0

    @model_validator(mode="after")
    def leading_fits_size(self) -> Self:
        if not self.size_rem <= self.leading_rem <= 2 * self.size_rem:
            raise ValueError("leading_rem must be between size_rem and twice size_rem")
        return self


class ConsoleSmallType(ConsoleType):
    size_rem: Size = 0.75
    leading_rem: Leading = 1


class ConsoleControlType(ConsoleType):
    weight: Weight = 500


class ConsolePanelType(ConsoleType):
    size_rem: Size = 1
    leading_rem: Leading = 1.5
    weight: Weight = 600
    tracking_em: Tracking = -0.01


class ConsolePageType(ConsoleType):
    size_rem: Size = 1.5
    leading_rem: Leading = 2
    weight: Weight = 600
    tracking_em: Tracking = -0.02


class ConsoleValueType(ConsolePageType):
    size_rem: Size = 1.75


class ConsoleTypography(Model):
    """Existing font choices and six bounded type roles."""

    ui_face: ConsoleFontFace = "inter"
    heading_face: ConsoleFontFace = "inter"
    data_face: ConsoleFontFace = "inter"
    small: ConsoleSmallType = Field(default_factory=ConsoleSmallType)
    body: ConsoleType = Field(default_factory=ConsoleType)
    control: ConsoleControlType = Field(default_factory=ConsoleControlType)
    panel_title: ConsolePanelType = Field(default_factory=ConsolePanelType)
    page_title: ConsolePageType = Field(default_factory=ConsolePageType)
    value: ConsoleValueType = Field(default_factory=ConsoleValueType)


class ConsoleLayout(Model):
    """The rail, controls and panels keep bounded room."""

    rail_width_rem: float = Field(default=12, strict=True, ge=8, le=18, allow_inf_nan=False)
    header_min_height_rem: float = Field(default=3.5, strict=True, ge=3, le=5, allow_inf_nan=False)
    rail_padding_rem: Space = 1
    rail_gap_rem: Space = 0.5
    content_gap_rem: Space = 1.5
    control_min_height_rem: float = Field(
        default=2.75, strict=True, ge=2.75, le=4, allow_inf_nan=False
    )
    control_padding_inline_rem: Space = 0.75
    control_padding_block_rem: Space = 0.25
    control_gap_rem: Space = 0.5
    panel_padding_rem: Space = 1
    panel_gap_rem: Space = 1
    group_gap_rem: Space = 1.5
    columns_wide: int = Field(default=2, strict=True, ge=1, le=2)


class ConsoleRadii(Model):
    control_rem: Radius = 0.25
    panel_rem: Radius = 0.5


class ConsoleShadow(Model):
    y_px: ShadowOffset = 0
    blur_px: ShadowBlur = 0
    alpha: ShadowAlpha = 0


class ConsolePanelShadow(ConsoleShadow):
    y_px: ShadowOffset = 1
    blur_px: ShadowBlur = 2
    alpha: ShadowAlpha = 0.06


class ConsoleFloatingShadow(ConsoleShadow):
    y_px: ShadowOffset = 6
    blur_px: ShadowBlur = 16
    alpha: ShadowAlpha = 0.12


class ConsoleLightElevation(Model):
    panel: ConsolePanelShadow = Field(default_factory=ConsolePanelShadow)
    floating: ConsoleFloatingShadow = Field(default_factory=ConsoleFloatingShadow)


class ConsoleDarkElevation(Model):
    panel: ConsoleShadow = Field(default_factory=ConsoleShadow)
    floating: ConsoleShadow = Field(default_factory=ConsoleShadow)


class ConsoleElevation(Model):
    light: ConsoleLightElevation = Field(default_factory=ConsoleLightElevation)
    dark: ConsoleDarkElevation = Field(default_factory=ConsoleDarkElevation)


class ConsoleChartStyle(Model):
    """Chart furniture and series strokes never change a reading."""

    axis_width_px: Stroke = 1
    grid_width_px: Stroke = 1
    line_width_px: float = Field(default=2, strict=True, ge=0.5, le=4, allow_inf_nan=False)
    grid_opacity: float = Field(default=1, strict=True, gt=0, le=1, allow_inf_nan=False)
    grid_dash_px: list[Dash] | None = Field(default=None, min_length=2, max_length=2)
    linecap: ConsoleLinecap = "round"


class ConsoleStyleConfig(Model):
    """Default missing console-only style blocks and leaves; replace arrays whole."""

    model_config = ConfigDict(allow_inf_nan=False)

    colors: ConsoleColorModes = Field(default_factory=ConsoleColorModes)
    typography: ConsoleTypography = Field(default_factory=ConsoleTypography)
    layout: ConsoleLayout = Field(default_factory=ConsoleLayout)
    radii: ConsoleRadii = Field(default_factory=ConsoleRadii)
    elevation: ConsoleElevation = Field(default_factory=ConsoleElevation)
    chart: ConsoleChartStyle = Field(default_factory=ConsoleChartStyle)
