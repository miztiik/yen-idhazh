"""Render a planned spec to a file beside the day that names it.

The asset lives next to the payload that references it, so a day is one
directory a reader, a retention pass or a human with a file browser can reason
about without an index.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import VisualPlan
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.render.chart import RenderError as ChartError
from idhazh.render.chart import compile_bar, render_chart

PUBLIC_ROOT: Final = Path("frontend/public/digest")
SUFFIX: Final = ".svg"


def asset_relpath(date: str, item_id: str) -> str:
    """`digest/<YYYY>/<MM>/<DD>/<item_id>.svg`, POSIX and digest-free.

    The name is the item's own id - the same `<vertical>-<id>` a reader already
    lands on as an anchor - so the path is a function of the item and of
    nothing else. A counter has to be seeded from somewhere, and the only thing
    available to seed it from was the day's directory: two runs of one day read
    that directory before either had pushed, both wrote `energy-03.svg` for
    different items, and the rebase lost the whole day. An identity cannot be
    read from a directory, so no two runs and no two shards can choose one path
    for two stories.

    Relative to `frontend/public/`, which is what the payload carries and what
    the page appends to its base path.
    """
    year, month, day = date.split("-")
    return f"digest/{year}/{month}/{day}/{item_id}{SUFFIX}"


def assets_in_day(public_root: Path, date: str) -> set[str]:
    """Every asset sitting in this day's directory, as `asset_relpath` writes it.

    The inverse of `asset_relpath`: that one asks what a path an item should
    have, this one asks what is actually on disk. Reading the directory is no
    longer allowed to decide a *name* - that is what raced two runs onto one
    path - but a caller that needs to compare the directory against a payload
    has to read it. `idhazh validate-days` is that caller: a file no item names
    is a picture the reader paid for and will never see.

    Relative to `public_root`, matching the strings a payload carries.
    """
    year, month, day = date.split("-")
    folder = public_root / "digest" / year / month / day
    if not folder.is_dir():
        return set()
    return {f"digest/{year}/{month}/{day}/{path.name}" for path in folder.glob(f"*{SUFFIX}")}


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


def drop_raced_assets(
    *, public_root: Path, items_dir: Path, published: Iterable[str]
) -> list[str]:
    """Delete this run's copy of any asset the tip already publishes.

    A run takes about three hours and the day is refreshed five times, so a
    second run renders while the first is still summarizing and neither checkout
    can see what the other has not pushed yet. Git cannot rebase two adds of one
    path, and run `32869125768` lost a finished day right there.

    Since the path is the item's id, a path both sides hold is **one story
    rendered twice** - never two stories under one name. So there is nothing to
    choose between: the tip's copy is published and a reader may already hold
    that address, and `assemble.build_day` keeps the tip's item over ours in any
    case, which makes our file the one nothing will reference. Dropping it is
    what lets the rebase apply.

    The decision payload is left alone on purpose. It still names the right path,
    the tip's file is sitting at that path after the rebase, and rewriting it to
    point somewhere else is how an item ends up with a picture that is not
    filed under its own name.

    `published` names what the tip holds, relative to `public_root`. Returns the
    paths it dropped, so the run log can name them.
    """
    already = set(published)
    dropped: list[str] = []
    for decision_path in sorted(items_dir.glob(f"*{PAYLOAD_SUFFIX}")):
        decision = VisualDecision.read(decision_path)
        relpath = decision.asset_path
        if relpath is None or relpath not in already:
            continue
        source = public_root / relpath
        # A payload naming a file this checkout does not hold cannot collide
        # with anything: nothing here would commit that path.
        if not source.is_file():
            continue
        source.unlink()
        dropped.append(relpath)
    return dropped


def render_visual(
    decision: VisualDecision,
    *,
    public_root: Path,
    relpath: str,
) -> VisualDecision:
    """Render, write, and return the decision carrying its outcome.

    Every failure path returns a `render_failed` decision. None of them raises, so
    a picture can never be the reason an item does not reach a reader.

    No canvas size is passed in. A Vega-Lite spec carries its own width and
    height, set from `visuals.canvas_width` where the spec is built.
    """
    if decision.kind is VisualKind.NONE or not decision.spec:
        return decision

    try:
        payload = render_chart(decision.spec)
        write_bytes_atomic(public_root / relpath, payload)
    except ChartError as error:
        return decision.model_copy(
            update={
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": str(error)[:200],
            }
        )
    except OSError as error:
        return decision.model_copy(
            update={
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": f"the asset could not be written: {type(error).__name__}",
            }
        )

    return decision.model_copy(update={"visual_state": VisualState.RENDERED, "asset_path": relpath})


def render_planned_visual(
    decision: VisualDecision,
    plan: VisualPlan,
    table: ElementTable,
    *,
    public_root: Path,
    relpath: str,
    visuals: VisualsConfig,
) -> VisualDecision:
    """A validated plan becomes a drawing on disk, or the item stays decided to nothing.

    The whole path in one call: compile the plan over the article's elements,
    draw the spec, write the file, and hand back the decision carrying the spec,
    the alt text and where the picture landed. It exists so the one place a plan
    turns into a published picture is one place rather than three call sites
    that can each get the order wrong, and so no caller has to remember a `try`
    around the compile.

    **`decision` arrives as the `none` it is.** `VisualDecision` refuses a
    `chart` that carries no spec, and the spec is what this function makes - so
    the item is decided to nothing until a plan compiles into a picture, and it
    is promoted through the contract's own validation rather than around it.

    **A plan this build cannot draw stays `none`, and that is the contract's
    ruling rather than a shortcut.** `render_failed` means a spec was drawn and
    the drawing failed; a plan that never became a spec has no spec to record,
    and the shape will not hold one. Which gate refused it is `none_reason`'s to
    say, and the caller sets it.
    """
    if decision.kind is not VisualKind.NONE:
        raise ValueError("a planned visual starts as an item decided to nothing")
    try:
        drawn = compile_bar(plan, table, visuals=visuals)
    except ChartError:
        return decision
    planned = VisualDecision.model_validate(
        decision.model_dump(mode="json")
        | {
            "kind": VisualKind.CHART.value,
            "none_reason": None,
            "spec": json.dumps(drawn.spec, separators=(",", ":"), sort_keys=True),
            "alt_text": drawn.alt_text,
        }
    )
    return render_visual(planned, public_root=public_root, relpath=relpath)
