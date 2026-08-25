"""Render a routed spec to a file beside the day that names it.

The asset lives next to the payload that references it, so a day is one
directory a reader, a retention pass or a human with a file browser can reason
about without an index.
"""

from __future__ import annotations

import tempfile
from collections.abc import Collection, Iterable
from pathlib import Path, PurePosixPath
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


def highest_ordinal(public_root: Path, date: str, vertical: str) -> int:
    """The largest `<vertical>-<NN>` already written for this day, or zero.

    A day runs several times. Numbering from one in each process made the second
    run overwrite the first run's `india-01.svg` while the digest still carried
    both items, so two different articles pointed at one file and one of them
    displayed a chart drawn from the other's numbers - with alt text describing
    figures that were not in the picture. Every value was true and the picture
    belonged to another story.

    Reading the directory keeps the `<vertical>-<NN>` shape the contract fixes
    (no hash in any published path) and needs no handshake between the router
    and the assembler, which run in different jobs.
    """
    year, month, day = date.split("-")
    folder = public_root / "digest" / year / month / day
    if not folder.is_dir():
        return 0
    highest = 0
    for path in folder.glob(f"{vertical}-*{SUFFIX}"):
        tail = path.stem[len(vertical) + 1 :]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return highest


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


def assets_in_day(public_root: Path, date: str) -> set[str]:
    """Every asset already sitting in this day's directory, as `asset_relpath` writes it."""
    year, month, day = date.split("-")
    folder = public_root / "digest" / year / month / day
    if not folder.is_dir():
        return set()
    return {f"digest/{year}/{month}/{day}/{path.name}" for path in folder.glob(f"*{SUFFIX}")}


def free_relpath(taken: Collection[str], date: str, vertical: str) -> str:
    """The lowest `<vertical>-<NN>` for this day that `taken` does not hold.

    Free by construction rather than by counting: the caller's `taken` is the
    union of two directories that cannot see each other, so "one past the
    highest" would be one past the highest of whichever side it read.
    """
    ordinal = 1
    while asset_relpath(date, vertical, ordinal) in taken:
        ordinal += 1
    return asset_relpath(date, vertical, ordinal)


def renumber_racing_assets(
    *, public_root: Path, items_dir: Path, date: str, published: Iterable[str]
) -> list[tuple[str, str]]:
    """Move this run's assets off any path another run of the day already holds.

    Two runs of one day both seed their counter from the day's directory
    (`highest_ordinal`), and neither can see what the other pushed while it
    worked. So both write `energy-03.svg`, for different items, with different
    bytes. Git cannot rebase two adds of one path, and run `32869125768` lost a
    finished day right there - eight workers and a router done, every summary
    thrown away at the push.

    The other run's copy is published and a reader may already hold that
    address, so this run's copy is the one that moves. The route payload moves
    with it, because that payload is the record of where the file went and
    `assemble` copies it into the day verbatim.

    `published` names what the other run holds, relative to `public_root`.
    Returns the moves it made, so the run log can name them.
    """
    already = set(published)
    taken = already | assets_in_day(public_root, date)
    moves: list[tuple[str, str]] = []
    for route_path in sorted(items_dir.glob("*.route.json")):
        route = Route.from_json(route_path.read_text(encoding="utf-8"))
        relpath = route.asset_path
        if relpath is None or relpath not in already:
            continue
        source = public_root / relpath
        # A payload naming a file this checkout does not hold cannot collide
        # with anything: nothing here would commit that path.
        if not source.is_file():
            continue
        vertical = PurePosixPath(relpath).stem.rsplit("-", 1)[0]
        moved = free_relpath(taken, date, vertical)
        source.replace(public_root / moved)
        taken.add(moved)
        renamed = route.model_copy(update={"asset_path": moved})
        write_bytes_atomic(route_path, renamed.to_json().encode("utf-8"))
        moves.append((relpath, moved))
    return moves


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
