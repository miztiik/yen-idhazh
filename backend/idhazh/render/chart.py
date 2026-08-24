"""Vega-Lite spec to SVG, with no browser and no runtime JavaScript.

`vl-convert` bundles the Vega toolchain as a Rust extension, so the render is a
function call rather than a subprocess plus a headless Chromium. Measured on the
development machine (Windows 11, 8 vCPU, 2026-08-22): 2568 ms for the first
render in a process, 49 ms warm, 7 KB of SVG. The cold cost is engine boot and
is paid once per run, not once per item.

SVG rather than PNG: a bar chart is a dozen paths, so the vector is smaller than
any raster of it, stays sharp on a phone, and costs the retention budget less.
"""

from __future__ import annotations

import json
from typing import Any, Final

SUFFIX: Final = ".svg"


class RenderError(RuntimeError):
    """The spec did not become a picture. The item still publishes."""


def render_chart(spec: str | dict[str, Any]) -> bytes:
    """Render a Vega-Lite spec. Raises `RenderError` and never returns a broken file."""
    import vl_convert

    text = spec if isinstance(spec, str) else json.dumps(spec)
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        raise RenderError(f"the chart spec is not valid JSON: {error.msg}") from error
    try:
        svg = vl_convert.vegalite_to_svg(text)
    except Exception as error:  # vl_convert raises its own error types
        raise RenderError(f"vega-lite rejected the spec: {type(error).__name__}") from error
    if not svg.strip().startswith("<svg"):
        raise RenderError("the renderer returned something that is not an SVG")
    return svg.encode("utf-8")
