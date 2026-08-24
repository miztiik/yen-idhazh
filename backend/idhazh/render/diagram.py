"""Mermaid source to SVG, laid out here rather than by a browser.

The persisted spec is Mermaid, because Mermaid is the interchange format and
anyone can re-render it with the real toolchain. We do not run that toolchain:
mermaid-cli drives a headless Chromium, which is roughly 300 MB of install and
seconds per render, and the only shape we emit is a chain of labelled boxes.
That is a layout problem with an exact answer, so it is solved here in about a
hundred lines and no dependency (Rule #8 names the cost; the cost is not
worth paying for this).

The subset understood here is exactly the subset `route.diagram_spec` writes: a
`flowchart TD` of `nN["label"]` nodes joined by `-->`. Anything else raises, and
the item publishes with no picture.
"""

from __future__ import annotations

import re
from typing import Final
from xml.sax.saxutils import escape

SUFFIX: Final = ".svg"

_NODE = re.compile(r'^\s*n(\d+)\["(.*)"\]\s*$')
_CAPTION = re.compile(r"^\s*%%\s*(.*)$")

_PADDING: Final = 28
_GAP: Final = 26
_ARROW: Final = 14
_FONT: Final = 15
_CHAR_WIDTH: Final = 0.55
_MAX_BOX_WIDTH: Final = 560


class RenderError(RuntimeError):
    """The spec did not become a picture. The item still publishes."""


def parse_mermaid(spec: str) -> tuple[str, list[str]]:
    """Return the caption and the ordered node labels."""
    caption = ""
    labels: dict[int, str] = {}
    saw_header = False
    for line in spec.splitlines():
        if not line.strip():
            continue
        comment = _CAPTION.match(line)
        if comment:
            caption = comment.group(1).strip()
            continue
        if line.strip().startswith("flowchart"):
            saw_header = True
            continue
        node = _NODE.match(line)
        if node:
            labels[int(node.group(1))] = node.group(2)
            continue
        if "-->" in line:
            continue
        raise RenderError("the diagram spec used a Mermaid feature this renderer does not draw")
    if not saw_header:
        raise RenderError("the diagram spec has no flowchart header")
    if len(labels) < 2:
        raise RenderError("a diagram of fewer than two steps is a sentence")
    return caption, [labels[key] for key in sorted(labels)]


def wrap(label: str, width_px: int, *, max_lines: int = 3) -> list[str]:
    """Greedy wrap on an average-character-width estimate.

    An estimate is honest here: the exact answer needs font metrics, the box is
    generous, and the failure mode of being slightly wrong is a slightly short
    line rather than an overflow.
    """
    per_line = max(int(width_px / (_FONT * _CHAR_WIDTH)), 8)
    lines: list[str] = []
    current = ""
    for word in label.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= per_line:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        return [label[:per_line]]
    if len(lines) == max_lines:
        joined = " ".join(lines)
        if len(joined) < len(label):
            lines[-1] = lines[-1][: max(per_line - 3, 1)].rstrip() + "..."
    return lines


def render_diagram(spec: str, *, width: int = 800, height: int = 500) -> bytes:
    """Draw the chain top-down inside one fixed canvas."""
    caption, labels = parse_mermaid(spec)

    top = _PADDING + (30 if caption else 0)
    available = height - top - _PADDING
    count = len(labels)
    box_height = (available - (count - 1) * (_GAP + _ARROW)) / count
    if box_height < 34:
        raise RenderError("too many steps to draw legibly in one canvas")
    box_width = min(width - 2 * _PADDING, _MAX_BOX_WIDTH)
    left = (width - box_width) / 2

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" font-family="sans-serif">',
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" fill="#8a8f98"/></marker></defs>',
    ]
    if caption:
        parts.append(
            f'<text x="{_PADDING}" y="{_PADDING + 12}" font-size="16" font-weight="600" '
            f'fill="currentColor">{escape(caption)}</text>'
        )

    cursor = float(top)
    for index, label in enumerate(labels):
        parts.append(
            f'<rect x="{left:.1f}" y="{cursor:.1f}" width="{box_width:.1f}" '
            f'height="{box_height:.1f}" rx="8" fill="none" stroke="#8a8f98" stroke-width="1.5"/>'
        )
        lines = wrap(label, int(box_width) - 32)
        block = len(lines) * (_FONT + 4)
        text_y = cursor + box_height / 2 - block / 2 + _FONT
        for offset, line in enumerate(lines):
            parts.append(
                f'<text x="{width / 2:.1f}" y="{text_y + offset * (_FONT + 4):.1f}" '
                f'font-size="{_FONT}" text-anchor="middle" fill="currentColor">'
                f"{escape(line)}</text>"
            )
        cursor += box_height
        if index < count - 1:
            parts.append(
                f'<line x1="{width / 2:.1f}" y1="{cursor + 4:.1f}" x2="{width / 2:.1f}" '
                f'y2="{cursor + _GAP + _ARROW - 4:.1f}" stroke="#8a8f98" stroke-width="1.5" '
                'marker-end="url(#a)"/>'
            )
            cursor += _GAP + _ARROW

    parts.append("</svg>")
    return "".join(parts).encode("utf-8")
