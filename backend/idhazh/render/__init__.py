"""Turn a validated plan into the data a reader's browser draws, or degrade to nothing.

Nothing here renders. The reader's browser draws the chart and the pipeline
never does (maintainer, 2026-09-13). A compile failure is recorded and the item
publishes without a picture. Never the other way round.

The package kept its name. Renaming it moves 23 importers and a dozen doc
references for no behaviour, and the moment that is worth an hour is the one
where plans 15 to 18 add the second visual vocabulary and somebody has to name
a new module anyway (Fowler, 2026-09-13).
"""

from __future__ import annotations

from idhazh.render.chart import CompiledChart, CompileError, can_compile, compile_bar
from idhazh.render.whowhat_grid import (
    compile_whowhat_grid,
    render_planned_whowhat,
    write_whowhat_from_decisions,
)
from idhazh.render.write import (
    asset_relpath,
    render_planned_visual,
    write_charts_from_decisions,
)

__all__ = [
    "CompileError",
    "CompiledChart",
    "asset_relpath",
    "can_compile",
    "compile_bar",
    "compile_whowhat_grid",
    "render_planned_visual",
    "render_planned_whowhat",
    "write_charts_from_decisions",
    "write_whowhat_from_decisions",
]
