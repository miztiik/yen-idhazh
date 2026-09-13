"""Turn a validated plan into the data a reader's browser draws, or degrade to nothing.

Nothing here renders. The reader's browser draws the chart and the pipeline
never does (owner, 2026-09-13). A compile failure is recorded and the item
publishes without a picture. Never the other way round.

The package kept its name. Renaming it moves 23 importers and a dozen doc
references for no behaviour, and the moment that is worth an hour is the one
where plans 15 to 18 add the second visual vocabulary and somebody has to name
a new module anyway (Fowler, 2026-09-13).
"""

from __future__ import annotations

from idhazh.render.chart import CompiledChart, CompileError, compile_bar
from idhazh.render.write import (
    asset_relpath,
    drop_raced_assets,
    render_planned_visual,
)

__all__ = [
    "CompileError",
    "CompiledChart",
    "asset_relpath",
    "compile_bar",
    "drop_raced_assets",
    "render_planned_visual",
]
