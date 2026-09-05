"""Turn a planned spec into a file on disk, or degrade to nothing.

The renderer is deterministic and does not run a browser. A render failure is
recorded and the item publishes without a picture. Never the other way round.
"""

from __future__ import annotations

from idhazh.render.chart import render_chart
from idhazh.render.write import (
    asset_relpath,
    drop_raced_assets,
    render_visual,
)

__all__ = [
    "asset_relpath",
    "drop_raced_assets",
    "render_chart",
    "render_visual",
]
