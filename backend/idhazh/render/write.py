"""Render a routed spec to a file beside the day that names it.

The asset lives next to the payload that references it, so a day is one
directory a reader, a retention pass or a human with a file browser can reason
about without an index.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final

from idhazh.contracts.route import Route, VisualKind, VisualState
from idhazh.render.chart import RenderError as ChartError
from idhazh.render.chart import render_chart
from idhazh.render.diagram import RenderError as DiagramError
from idhazh.render.diagram import render_diagram

PUBLIC_ROOT: Final = Path("frontend/public/digest")
SUFFIX: Final = ".svg"


def asset_relpath(date: str, vertical: str, ordinal: int) -> str:
    """`digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.svg`, POSIX and digest-free.

    Relative to `frontend/public/`, which is what the payload carries and what
    the page appends to its base path.
    """
    year, month, day = date.split("-")
    return f"digest/{year}/{month}/{day}/{vertical}-{ordinal:02d}{SUFFIX}"


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False)
    try:
        with handle:
            handle.write(payload)
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def render_route(
    route: Route,
    *,
    public_root: Path,
    relpath: str,
    canvas_width: int = 800,
    canvas_height: int = 500,
) -> Route:
    """Render, write, and return the route carrying its outcome.

    Every failure path returns a `render_failed` route. None of them raises, so
    a picture can never be the reason an item does not reach a reader.
    """
    if route.kind is VisualKind.NONE or not route.spec:
        return route

    try:
        if route.kind is VisualKind.CHART:
            payload = render_chart(route.spec)
        elif route.kind is VisualKind.DIAGRAM:
            payload = render_diagram(route.spec, width=canvas_width, height=canvas_height)
        else:
            return route.model_copy(
                update={
                    "visual_state": VisualState.RENDER_FAILED,
                    "failure_detail": f"no renderer is built for {route.kind.value}",
                }
            )
        write_bytes_atomic(public_root / relpath, payload)
    except (ChartError, DiagramError) as error:
        return route.model_copy(
            update={
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": str(error)[:200],
            }
        )
    except OSError as error:
        return route.model_copy(
            update={
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": f"the asset could not be written: {type(error).__name__}",
            }
        )

    return route.model_copy(update={"visual_state": VisualState.RENDERED, "asset_path": relpath})
