"""Publish every injection canary as a real day, for the browser suite to attack.

The pipeline's controls sit behind this. By the time text is in a payload the
sanitizer has already run, so a canary day built from sanitized text would only
re-assert the control the backend suite already asserts.

This builds the day from the **raw** attack text instead. That is the honest
worst case for the browser boundary: suppose the sanitizer regressed, or a model
repeated an attack verbatim, and the markup reached a payload. The published
surface must still render it as words. If it does not, the page is one bad
summary away from being a click target a stranger chose.

Operator tooling. It never runs in the pipeline and never writes into the
published tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from idhazh.assemble import build_embeddings, day_dir, to_digest_visual, write_atomic
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.route import Route, SpecFormat, VisualKind
from idhazh.contracts.taxonomy import SourceKind
from idhazh.embed import Embedder
from idhazh.render import asset_relpath, render_route

CANARY_DIR = Path("tests/fixtures/canaries")
DATE = "2026-08-20"

# Two items carry a real visual, so the browser suite exercises the picture path
# rather than proving it safe by never serving one. The specs are ours, not a
# model's - this file tests the surface, not the router.
CHART_SPEC = json.dumps(
    {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "transparent",
        "data": {
            "values": [
                {"label": "2025", "value": 15400},
                {"label": "2024", "value": 11200},
                {"label": "2023", "value": 8600},
            ]
        },
        "encoding": {
            "x": {"axis": {"title": "megawatt"}, "field": "value", "type": "quantitative"},
            "y": {"axis": {"title": None}, "field": "label", "sort": None, "type": "nominal"},
        },
        "height": 410,
        "mark": {"color": "#4c6ef5", "type": "bar"},
        "width": 680,
    },
    separators=(",", ":"),
    sort_keys=True,
)

DIAGRAM_SPEC = (
    'flowchart TD\n    n0["Filed"]\n    n1["Reviewed"]\n    n2["Approved"]\n'
    "    n0 --> n1\n    n1 --> n2"
)


def canaries() -> list[dict[str, object]]:
    """Every canary, build-time and browser, in a stable order."""
    paths = sorted(CANARY_DIR.glob("*.json")) + sorted((CANARY_DIR / "browser").glob("*.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def to_item(index: int, canary: dict[str, object], run_n: int) -> DigestItem:
    raw_text = str(canary["raw_text"])
    return DigestItem(
        item_id=f"ai-{index + 1:02d}",
        vertical="ai",
        title=str(canary["raw_title"]),
        source_url=str(canary["source_url"]),
        source_id="canary",
        source_name="Canary fixture",
        source_kind=SourceKind.REPORTING,
        summary=raw_text,
        key_points=[line for line in raw_text.splitlines() if line.strip()][:3] or ["-"],
        band=ConfidenceBand.LOW,
        introduced_by_run=run_n,
    )


def visual_for(index: int, item_id: str, target: Path) -> Route | None:
    """A rendered chart on the first item, a rendered diagram on the second."""
    if index == 0:
        kind, spec, fmt = VisualKind.CHART, CHART_SPEC, SpecFormat.VEGA_LITE
        alt = "Bar chart. 2025 15,400 megawatt; 2024 11,200 megawatt; 2023 8,600 megawatt."
    elif index == 1:
        kind, spec, fmt = VisualKind.DIAGRAM, DIAGRAM_SPEC, SpecFormat.MERMAID
        alt = "Flow diagram. Filed then Reviewed then Approved."
    else:
        return None

    route = Route(
        version=Route.schema_version(),
        item_id=item_id,
        url_key="0" * 64,
        kind=kind,
        spec=spec,
        spec_format=fmt,
        alt_text=alt,
        model_id="canary",
        routed_at=f"{DATE}T06:00:00Z",
    )
    return render_route(
        route,
        # The payload stores `digest/<Y>/<M>/<D>/...`, so the root here is the
        # parent of the digest directory - exactly as the real pipeline does it.
        public_root=target.parent,
        relpath=asset_relpath(DATE, "ai", index + 1),
    )


def build(target: Path) -> DigestDay:
    items = [to_item(index, canary, 1) for index, canary in enumerate(canaries())]
    items = [
        item.model_copy(
            update={"visual": to_digest_visual(visual_for(index, item.item_id, target))}
        )
        for index, item in enumerate(items)
    ]
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        retention_window_months=-1,
        runs=[DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=len(items))],
        verticals=[DigestVerticalRef(id="ai", display_name="AI", count=len(items))],
        items=items,
        embeddings=build_embeddings(items, Embedder(Path.cwd())),
    )
    write_atomic(day_dir(target, DATE) / "digest.json", day.to_json())
    return day


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("backend/var/canary/digest"))
    args = parser.parse_args()
    day = build(args.out)
    digest = hashlib.sha256(day.to_json().encode("utf-8")).hexdigest()[:12]
    visuals = sum(1 for item in day.items if item.visual is not None)
    print(f"canary day {DATE}: {len(day.items)} items, {visuals} visuals, payload {digest}")
    print(f"wrote {(day_dir(args.out, DATE) / 'digest.json').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
