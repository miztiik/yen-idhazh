"""Label published pie and bubble charts, and report exact-type keep rates.

This operator tool reads one named review queue and writes only local,
gitignored label shards. It never renders a chart or fetches a published page.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import TypeAdapter

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from idhazh.atomic_write import write_atomic, write_atomic_bytes  # noqa: E402
from idhazh.contracts.base import Sha256, Slug  # noqa: E402
from idhazh.contracts.review_queue import ReviewQueue, ReviewRow  # noqa: E402
from idhazh.contracts.visual_label import (  # noqa: E402
    VISUAL_LABEL_TYPES,
    VisualLabel,
    VisualLabelDraw,
    VisualLabelRow,
    normalize_published_base_url,
    visual_label_draw_id,
)
from idhazh.evals.visual_labels import (  # noqa: E402
    VisualTypeEvidence,
    collapse_visual_label_rows,
    index_labelable_visuals,
    summarize_visual_labels,
)

DEFAULT_ROOT: Final = REPO_ROOT / "backend" / "var" / "visual-labels"
_SHA256: Final = TypeAdapter(Sha256)
_SLUG: Final = TypeAdapter(Slug)


class VisualLabelBundle(NamedTuple):
    """A draw manifest with the exact queue bytes it names."""

    draw: VisualLabelDraw
    queue: ReviewQueue


def _io_failure(path_hint: str, error: OSError) -> ValueError:
    detail = error.strerror or type(error).__name__
    return ValueError(f"cannot access {path_hint}: {detail}")


def create_visual_label_draw(
    queue_path: Path,
    *,
    published_base_url: str,
    root: Path = DEFAULT_ROOT,
) -> VisualLabelBundle:
    """Freeze one named queue and its published destination for later review."""
    try:
        queue_bytes = queue_path.read_bytes()
    except OSError as error:
        raise _io_failure(queue_path.name, error) from error
    queue = ReviewQueue.from_json(queue_bytes.decode("utf-8"))
    if not index_labelable_visuals(queue):
        raise ValueError("the queue has no published pie or bubble row with a visual_id")
    base_url = normalize_published_base_url(published_base_url)
    queue_sha256 = sha256(queue_bytes).hexdigest()
    draw = VisualLabelDraw(
        version=VisualLabelDraw.schema_version(),
        draw_id=visual_label_draw_id(
            queue_sha256=queue_sha256,
            queue_date=queue.date,
            published_base_url=base_url,
            visual_types=VISUAL_LABEL_TYPES,
        ),
        queue_sha256=queue_sha256,
        queue_date=queue.date,
        published_base_url=base_url,
        visual_types=VISUAL_LABEL_TYPES,
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    draw_dir = root / draw.draw_id
    manifest_path = draw_dir / "draw.json"
    queue_snapshot_path = draw_dir / "queue.json"
    existing_draw: VisualLabelDraw | None = None
    if manifest_path.exists():
        try:
            existing_draw = VisualLabelDraw.read(manifest_path)
        except OSError as error:
            raise _io_failure(f"{draw.draw_id}/draw.json", error) from error
        if (
            existing_draw.draw_id != draw.draw_id
            or existing_draw.queue_sha256 != draw.queue_sha256
            or existing_draw.queue_date != draw.queue_date
            or existing_draw.published_base_url != draw.published_base_url
            or existing_draw.visual_types != draw.visual_types
        ):
            raise ValueError("the draw directory already holds a different manifest")
    if queue_snapshot_path.exists():
        try:
            if queue_snapshot_path.read_bytes() != queue_bytes:
                raise ValueError("the draw directory already holds different queue bytes")
        except OSError as error:
            raise _io_failure(f"{draw.draw_id}/queue.json", error) from error
    if not queue_snapshot_path.exists():
        try:
            write_atomic_bytes(queue_snapshot_path, queue_bytes)
        except OSError as error:
            raise _io_failure(f"{draw.draw_id}/queue.json", error) from error
    if existing_draw is None:
        try:
            write_atomic(manifest_path, draw.to_json())
        except OSError as error:
            raise _io_failure(f"{draw.draw_id}/draw.json", error) from error
    return read_visual_label_draw(root, draw.draw_id)


def read_visual_label_draw(root: Path, draw_id: str) -> VisualLabelBundle:
    """Read one exact draw and refuse a missing or changed queue snapshot."""
    valid_id = _SHA256.validate_python(draw_id)
    draw_dir = root / valid_id
    try:
        draw = VisualLabelDraw.read(draw_dir / "draw.json")
        queue_bytes = (draw_dir / "queue.json").read_bytes()
    except OSError as error:
        raise _io_failure(f"{valid_id}/draw.json or queue.json", error) from error
    if draw.draw_id != valid_id:
        raise ValueError("the draw manifest does not match the requested draw")
    if sha256(queue_bytes).hexdigest() != draw.queue_sha256:
        raise ValueError("the saved queue bytes do not match the draw")
    queue = ReviewQueue.from_json(queue_bytes.decode("utf-8"))
    if queue.date != draw.queue_date:
        raise ValueError("the saved queue date does not match the draw")
    return VisualLabelBundle(draw=draw, queue=queue)


def published_item_url(bundle: VisualLabelBundle, visual_id: str) -> str:
    """Return the existing dated page and its exact item anchor."""
    indexed = index_labelable_visuals(bundle.queue)
    try:
        _, row = indexed[visual_id]
    except KeyError as error:
        raise ValueError("the visual is not in this draw's published chart queue") from error
    return f"{bundle.draw.published_base_url}/{bundle.draw.queue_date}/#{row.item_id}"


def next_unlabelled_visual(
    root: Path,
    bundle: VisualLabelBundle,
    *,
    reviewer_id: str,
    skipped_visual_ids: frozenset[str] = frozenset(),
) -> tuple[int, str, ReviewRow] | None:
    """Choose the first unanswered visual from this reviewer's exact draw."""
    valid_reviewer_id = _SLUG.validate_python(reviewer_id)
    indexed = index_labelable_visuals(bundle.queue)
    existing = collapse_visual_label_rows(
        read_visual_label_rows(
            root,
            draw_id=bundle.draw.draw_id,
            reviewer_id=valid_reviewer_id,
        )
    )
    answered: set[str] = set()
    for label in existing:
        if label.draw_id != bundle.draw.draw_id or label.reviewer_id != valid_reviewer_id:
            raise ValueError("a saved label belongs to another draw or reviewer")
        entry = indexed.get(label.visual_id)
        if entry is None:
            raise ValueError("a saved label does not join a visual in this draw")
        if label.queue_position != entry[0]:
            raise ValueError("a saved label has a different position in this draw")
        answered.add(label.visual_id)

    if not skipped_visual_ids.issubset(indexed):
        raise ValueError("a skipped visual does not belong to this draw")
    for visual_id, (queue_position, row) in indexed.items():
        if visual_id not in answered and visual_id not in skipped_visual_ids:
            return queue_position, visual_id, row
    return None


def _label_path(root: Path, draw_id: str, reviewer_id: str) -> Path:
    valid_draw_id = _SHA256.validate_python(draw_id)
    valid_reviewer_id = _SLUG.validate_python(reviewer_id)
    return root / valid_draw_id / f"{valid_reviewer_id}.csv"


def read_visual_label_rows(
    root: Path, *, draw_id: str, reviewer_id: str
) -> tuple[VisualLabelRow, ...]:
    """Read one named reviewer's file, without listing the draw directory."""
    path = _label_path(root, draw_id, reviewer_id)
    path_hint = f"{draw_id}/{reviewer_id}.csv"
    try:
        path.stat()
    except FileNotFoundError:
        return ()
    except OSError as error:
        raise _io_failure(path_hint, error) from error
    rows: list[VisualLabelRow] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(VisualLabelRow.csv_columns()):
                raise ValueError(f"{path_hint} has a different visual-label header")
            for raw in reader:
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError(f"{path_hint} has a malformed CSV row")
                row = VisualLabelRow.from_csv_row(
                    {name: value for name, value in raw.items() if value is not None}
                )
                if row.draw_id != draw_id or row.reviewer_id != reviewer_id:
                    raise ValueError(f"{path_hint} contains a row for another label file")
                rows.append(row)
    except OSError as error:
        raise _io_failure(path_hint, error) from error
    return tuple(rows)


def append_visual_label(
    root: Path,
    *,
    draw_id: str,
    reviewer_id: str,
    visual_id: str,
    label: VisualLabel,
    labelled_at: str,
    page_is_live: bool,
) -> bool:
    """Atomically append one human answer after the exact page was confirmed live."""
    if not page_is_live:
        raise ValueError("a label requires confirmation that its exact published page is live")
    bundle = read_visual_label_draw(root, draw_id)
    valid_reviewer_id = _SLUG.validate_python(reviewer_id)
    try:
        queue_position, _ = index_labelable_visuals(bundle.queue)[visual_id]
    except KeyError as error:
        raise ValueError("the visual is not in this draw's published chart queue") from error
    row = VisualLabelRow(
        version=VisualLabelRow.schema_version(),
        draw_id=bundle.draw.draw_id,
        visual_id=visual_id,
        reviewer_id=valid_reviewer_id,
        queue_position=queue_position,
        label=label,
        labelled_at=labelled_at,
    )

    path = _label_path(root, bundle.draw.draw_id, valid_reviewer_id)
    existing = read_visual_label_rows(
        root, draw_id=bundle.draw.draw_id, reviewer_id=valid_reviewer_id
    )
    existing = collapse_visual_label_rows(existing)
    existing_by_key = {(old.draw_id, old.visual_id, old.reviewer_id): old for old in existing}
    key = (row.draw_id, row.visual_id, row.reviewer_id)
    previous = existing_by_key.get(key)
    if previous is not None:
        if previous.label is not row.label or previous.queue_position != row.queue_position:
            raise ValueError("a reviewer cannot change a label already recorded for this visual")
        return False

    rows = [*existing, row]
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=VisualLabelRow.csv_columns(),
        lineterminator="\n",
    )
    writer.writeheader()
    for saved in rows:
        writer.writerow(saved.csv_row())
    try:
        write_atomic(path, output.getvalue())
    except OSError as error:
        raise _io_failure(f"{bundle.draw.draw_id}/{valid_reviewer_id}.csv", error) from error
    return True


def load_named_visual_label_rows(
    root: Path, *, draw_id: str, reviewer_ids: Sequence[str]
) -> tuple[VisualLabelRow, ...]:
    """Read only the draw and reviewer files named for this report."""
    if not reviewer_ids:
        raise ValueError("at least one reviewer must be named")
    reviewers = tuple(_SLUG.validate_python(reviewer_id) for reviewer_id in reviewer_ids)
    if len(set(reviewers)) != len(reviewers):
        raise ValueError("reviewer names must be distinct")
    return tuple(
        row
        for reviewer_id in reviewers
        for row in read_visual_label_rows(
            root, draw_id=draw_id, reviewer_id=reviewer_id
        )
    )


def _print_visual_type_evidence(evidence: VisualTypeEvidence) -> None:
    print(evidence.visual_type.value)
    print(f"  machine planned: {evidence.machine_planned} queue rows")
    print(f"  machine rendered: {evidence.machine_rendered} published rows")
    print(
        f"  human labels: {evidence.human_labels} from "
        f"{evidence.reviewed_visuals} distinct visuals"
    )
    if evidence.keep_rate is None:
        print("  human keep rate: NOT QUOTABLE (no reviewer overlap)")
    else:
        print(
            f"  human keep rate: {evidence.keep_rate:.1%} "
            f"({evidence.kept_labels}/{evidence.human_labels} labels)"
        )
    print(
        f"  overlap: {evidence.overlap_visuals} visuals; raw agreement: "
        f"{evidence.agreeing_pairs}/{evidence.reviewer_pairs} reviewer pairs"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record human keep labels for published pie and bubble charts."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    draw = commands.add_parser("draw", help="freeze one review queue and published URL")
    draw.add_argument("--queue", required=True, type=Path)
    draw.add_argument("--published-base-url", required=True)

    label = commands.add_parser("label", help="label one visual from a named draw")
    label.add_argument("--draw-id", required=True)
    label.add_argument("--reviewer", required=True)
    target = label.add_mutually_exclusive_group(required=True)
    target.add_argument("--visual-id")
    target.add_argument("--next", action="store_true")

    report = commands.add_parser("report", help="report exact-type keep rates")
    report.add_argument("--draw-id", required=True)
    report.add_argument("--reviewer", action="append", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "draw":
            bundle = create_visual_label_draw(
                args.queue,
                published_base_url=args.published_base_url,
            )
            print(f"draw_id {bundle.draw.draw_id}")
            print(
                "published page pattern "
                f"{bundle.draw.published_base_url}/{bundle.draw.queue_date}/#<item_id>"
            )
            print(f"{len(index_labelable_visuals(bundle.queue))} published pie/bubble visuals")
            print(f"local labels backend/var/visual-labels/{bundle.draw.draw_id}/")
            print(
                "To resume in queue order: python backend/utilities/visual_labels.py label "
                f"--draw-id {bundle.draw.draw_id} --reviewer reviewer-id --next"
            )
            print("Replace reviewer-id with the same reviewer id on each run.")
            return 0

        if args.command == "label":
            bundle = read_visual_label_draw(DEFAULT_ROOT, args.draw_id)
            reviewer_id = _SLUG.validate_python(args.reviewer)
            skipped: set[str] = set()
            while True:
                visual_id = args.visual_id
                if args.next:
                    candidate = next_unlabelled_visual(
                        DEFAULT_ROOT,
                        bundle,
                        reviewer_id=reviewer_id,
                        skipped_visual_ids=frozenset(skipped),
                    )
                    if candidate is None:
                        if skipped:
                            print("No more visuals this pass; skipped visuals will return later.")
                        else:
                            print("This reviewer has labelled every visual in the draw.")
                        return 0
                    _, visual_id, _ = candidate
                if visual_id is None:
                    parser.error("choose --visual-id or --next")

                page_url = published_item_url(bundle, visual_id)
                print(f"Published page: {page_url}")
                confirmed = input(
                    "Open this exact page, confirm the chart is live, then type LIVE: "
                )
                if confirmed != "LIVE":
                    print("No label recorded.")
                    return 0
                answer = input(
                    "Keep this chart? [k] keep, [d] discard, [s] skip, [q] stop: "
                ).lower()
                if answer == "q":
                    print("No label recorded.")
                    return 0
                if answer == "s":
                    if args.next:
                        skipped.add(visual_id)
                        print("Skipped for this pass; it will be offered again later.")
                        continue
                    print("No label recorded.")
                    return 0
                if answer not in {"k", "d"}:
                    parser.error("answer must be k, d, s or q")
                label_value = VisualLabel.KEEP if answer == "k" else VisualLabel.DISCARD
                added = append_visual_label(
                    DEFAULT_ROOT,
                    draw_id=bundle.draw.draw_id,
                    reviewer_id=reviewer_id,
                    visual_id=visual_id,
                    label=label_value,
                    labelled_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    page_is_live=True,
                )
                print("Label recorded." if added else "This reviewer already gave the same label.")
                if not args.next:
                    return 0

        bundle = read_visual_label_draw(DEFAULT_ROOT, args.draw_id)
        reviewers = tuple(_SLUG.validate_python(reviewer_id) for reviewer_id in args.reviewer)
        labels = load_named_visual_label_rows(
            DEFAULT_ROOT, draw_id=bundle.draw.draw_id, reviewer_ids=reviewers
        )
        report = summarize_visual_labels(
            bundle.queue,
            labels,
            draw_id=bundle.draw.draw_id,
            reviewer_ids=reviewers,
        )
        for evidence in report:
            _print_visual_type_evidence(evidence)
        return 0
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
