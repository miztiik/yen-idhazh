"""Does the frontend style copy and its real CSS producer agree with the native contract?"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import get_args

import pytest

from idhazh.contracts.appearance_config import AppearanceConfig
from idhazh.contracts.knobs.console_style import (
    ConsoleChartStyle,
    ConsoleStyleConfig,
    ConsoleTypography,
)

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[3]
SCRIPT = """
import { readFileSync } from 'node:fs';
import { resolveConsoleStyle, CONSOLE_FONT_FACES, CONSOLE_LINECAPS } from './frontend/src/lib/console/console-style.ts';
import { renderFrameCss } from './frontend/scripts/build-frame-css.mjs';
const input = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify({
    style: resolveConsoleStyle(input),
    faces: CONSOLE_FONT_FACES,
    caps: CONSOLE_LINECAPS,
    css: renderFrameCss({console_style: input})
}));
"""


def frontend(style: object) -> dict[str, object]:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", SCRIPT],
        cwd=ROOT,
        input=json.dumps(style),
        text=True,
        capture_output=True,
        check=True,
    )
    decoded: dict[str, object] = json.loads(result.stdout)
    return decoded


def test_frontend_fields_defaults_and_partial_leaves_match_native_style() -> None:
    for given in (
        {},
        {
            "typography": {"small": {"weight": 500}},
            "colors": {"dark": {"accent": "#58bab0"}},
            "elevation": {"light": {"floating": {"y_px": 8}}},
            "chart": {"grid_dash_px": [2, 4]},
        },
    ):
        native = ConsoleStyleConfig.model_validate(given).model_dump(mode="json")
        assert frontend(given)["style"] == native


def test_frontend_font_and_linecap_vocabularies_match_native_style() -> None:
    copied = frontend({})
    assert copied["faces"] == list(get_args(ConsoleTypography.model_fields["ui_face"].annotation))
    assert copied["caps"] == list(get_args(ConsoleChartStyle.model_fields["linecap"].annotation))


def test_real_css_producer_substitutes_nondefault_style_without_changing_reader_tokens() -> None:
    fixture = (
        ROOT / "tests/fixtures/contracts/appearance-config/knobs-set-away-from-the-defaults.json"
    )
    style = AppearanceConfig.model_validate_json(fixture.read_text(encoding="utf-8")).console_style
    rendered = frontend(style.model_dump(mode="json"))
    assert rendered["style"] == style.model_dump(mode="json")
    css = rendered["css"]
    assert isinstance(css, str)
    reader, operator = css.split("/* The selector includes the outer canvas", 1)
    assert "--console-" not in reader
    assert "--color-bg:" not in reader
    assert "--color-bg: #1a1a18;" in operator
    assert "--color-bg: #f3f2ee;" in operator
    assert "--console-small-size: 0.875rem;" in operator
    assert "--console-small-leading: 1.125rem;" in operator
    assert "--console-rail-width: 13rem;" in operator
    assert "--console-chart-grid-dash: 2 4;" in operator
    assert "--series-1: var(--chart-1);" in operator
