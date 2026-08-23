"""Turn a routed spec into a file on disk, or degrade to nothing.

Both renderers are deterministic and neither runs a browser. A render failure is
recorded and the item publishes without a picture. Never the other way round.
"""

from __future__ import annotations

from idhazh.render.chart import render_chart
from idhazh.render.diagram import render_diagram
from idhazh.render.write import asset_relpath, render_route

__all__ = ["asset_relpath", "render_chart", "render_diagram", "render_route"]
