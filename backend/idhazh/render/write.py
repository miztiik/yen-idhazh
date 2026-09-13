"""Write a compiled visual's data beside the day that names it.

The file lives next to the payload that references it, so a day is one
directory a reader, a retention pass or a human with a file browser can reason
about without an index.

**One published file per visual since 2026-09-13**, and it is data rather than a
picture: the reader's browser draws the chart and the pipeline never does
(`docs/architecture/publishing/visuals.md`). The SVG writer that stood here is
gone with the renderer.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from idhazh.contracts.app_config import VisualsConfig
from idhazh.contracts.base import ITEM_ID_PATTERN
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import VisualPlan
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    VisualDecision,
    VisualKind,
    VisualState,
)
from idhazh.render.chart import CompileError, compile_bar

PUBLIC_ROOT: Final = Path("frontend/public/digest")
#: What a visual's published data is filed as. It was `.svg` until 2026-09-13,
#: when the drawing moved into the reader's browser and the marks became the
#: only thing the pipeline publishes for a picture.
SUFFIX: Final = ".json"


def asset_relpath(date: str, item_id: str) -> str:
    """`digest/<YYYY>/<MM>/<DD>/<item_id>.json`, POSIX and digest-free.

    The name is the item's own id - the same `<vertical>-<id>` a reader already
    lands on as an anchor - so the path is a function of the item and of
    nothing else. A counter has to be seeded from somewhere, and the only thing
    available to seed it from was the day's directory: two runs of one day read
    that directory before either had pushed, both wrote `energy-03.svg` for
    different items, and the rebase lost the whole day. An identity cannot be
    read from a directory, so no two runs and no two shards can choose one path
    for two stories.

    `digest.json` and `run.json` are the day's own payloads and sit in the same
    directory. Neither can ever collide with one of these: an item id has to end
    in a hyphen and a run of digits or sixteen base32 symbols, so no item is
    called `digest` or `run`.

    Relative to `frontend/public/`, which is what the payload carries and what
    the page appends to its base path.
    """
    year, month, day = date.split("-")
    return f"digest/{year}/{month}/{day}/{item_id}{SUFFIX}"


def assets_in_day(public_root: Path, date: str) -> set[str]:
    """Every file this day's directory holds for its items, as the writer files them.

    The inverse of `asset_relpath`: that one asks what path an item should have,
    this one asks what is actually on disk. Reading the directory is no longer
    allowed to decide a *name* - that is what raced two runs onto one path - but
    a caller that needs to compare the directory against a payload has to read
    it. `idhazh validate-days` is that caller: a file no item names is weight the
    reader pays for and will never see.

    **What makes a file one of these is that it is named for an item**, which is
    also what tells it apart from the day's own payloads. `digest.json` and
    `run.json` sit in this directory and belong to the day rather than to any
    story, and naming them here to exclude them would be a list that rots: it
    was written when `digest.json` was the only one, and `run.json` walked
    straight through it. An item id ends in a hyphen and a run of digits or
    sixteen base32 symbols, so no day-level payload can ever look like one.

    Relative to `public_root`, matching the strings a payload carries.
    """
    year, month, day = date.split("-")
    folder = public_root / "digest" / year / month / day
    if not folder.is_dir():
        return set()
    return {
        f"digest/{year}/{month}/{day}/{path.name}"
        for path in folder.glob(f"*{SUFFIX}")
        if re.match(ITEM_ID_PATTERN, path.stem)
    }


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
    """Delete this run's copy of any published file the tip already holds.

    A run takes about three hours and the day is refreshed five times, so a
    second run compiles while the first is still summarizing and neither
    checkout can see what the other has not pushed yet. Git cannot rebase two
    adds of one path when the two blobs differ, and run `32869125768` lost a
    finished day right there.

    Since the path is the item's id, a path both sides hold is **one story
    compiled twice** - never two stories under one name. So there is nothing to
    choose between: the tip's copy is published and a reader may already hold
    that address, and `assemble.build_day` keeps the tip's item over ours in any
    case, which makes our file the one nothing will reference. Dropping it is
    what lets the rebase apply.

    The decision payload is left alone on purpose. It still names the right path,
    the tip's file is sitting at that path after the rebase, and rewriting it to
    point somewhere else is how an item ends up with a picture that is not
    filed under its own name.

    **The renderer going did not retire this** (Fowler, 2026-09-13). Vega's
    process-global clip-path counter made two renders of one item differ
    reliably, and that cause left with the renderer - so an item compiled twice
    from unchanged inputs now writes identical bytes, which git merges without
    a conflict. The race itself stays, because the compiled marks come from a
    plan and an element table derived from text re-fetched off the open web: a
    source page that moved between two runs' fetches puts two different blobs on
    one path. That is rarer than the counter was and exactly as expensive, which
    is an argument for keeping the control rather than against it.

    `published` names what the tip holds, relative to `public_root`. Returns the
    paths it dropped, so the run log can name them.
    """
    already = set(published)
    dropped: list[str] = []
    for decision_path in sorted(items_dir.glob(f"*{PAYLOAD_SUFFIX}")):
        decision = VisualDecision.read(decision_path)
        relpath = decision.data_path
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


def render_planned_visual(
    decision: VisualDecision,
    plan: VisualPlan,
    table: ElementTable,
    *,
    public_root: Path,
    relpath: str,
    visuals: VisualsConfig,
) -> VisualDecision:
    """A validated plan becomes a published data file, or the item stays decided to nothing.

    The whole path in one call: compile the plan over the article's elements,
    write the marks where the day payload will point, and hand back the decision
    carrying them. It exists so the one place a plan turns into a published
    picture is one place rather than three call sites that can each get the
    order wrong, and so no caller has to remember a `try` around the compile.

    **`decision` arrives as the `none` it is.** `VisualDecision` refuses a
    `chart` that carries no spec, and the spec is what this function makes - so
    the item is decided to nothing until a plan compiles, and it is promoted
    through the contract's own validation rather than around it.

    **A plan this build cannot compile stays `none`, and that is the contract's
    ruling rather than a shortcut.** `render_failed` means marks were compiled
    and the file did not land; a plan that never compiled has no spec to record,
    and the shape will not hold one. Which gate refused it is `none_reason`'s to
    say, and the caller sets it.

    **Nothing is drawn here and nothing is drawn anywhere in this repository.**
    The reader's browser draws the chart from 2026-09-13
    ([`docs/architecture/publishing/visuals.md`](../../../docs/architecture/publishing/visuals.md)),
    so the compiled marks are the last thing the pipeline writes for a picture
    and the first thing the drawing code reads.
    """
    if decision.kind is not VisualKind.NONE:
        raise ValueError("a planned visual starts as an item decided to nothing")
    try:
        compiled = compile_bar(plan, table, visuals=visuals)
    except CompileError:
        return decision
    planned = VisualDecision.model_validate(
        decision.model_dump(mode="json")
        | {
            "kind": VisualKind.CHART.value,
            "none_reason": None,
            "spec": compiled.data.to_json(),
            "alt_text": compiled.alt_text,
        }
    )
    try:
        write_bytes_atomic(public_root / relpath, compiled.data.to_json().encode("utf-8"))
    except OSError as error:
        return planned.model_copy(
            update={
                "visual_state": VisualState.RENDER_FAILED,
                "failure_detail": f"the data file could not be written: {type(error).__name__}",
            }
        )
    return planned.model_copy(
        update={"visual_state": VisualState.RENDERED, "data_path": relpath}
    )
