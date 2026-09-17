"""Write a person's labels onto `corpus/reference-dataset-1/dataset.jsonl`.

Plan 23 row #P3. An agent may prepare this tooling; the labels themselves are a
person's (`CLAUDE.md` section 0a, and the set's own datasheet).

Three verbs.

- `plan` prints the work: one line an unlabelled article, with its split and the
  path to its text. Batch it with `--offset` and `--size`.
- `apply` merges a labels file into `dataset.jsonl`. Every value is checked
  against the committed vocabulary before a byte is written, so a label nobody
  declared is RefusedError here rather than discovered in a measurement.
- `status` counts what is done.
`retire` is the fourth, and it is the only one that takes a row out. Labelling
all 641 rows surfaced defects no shape check can see - a file with no story in
it, a file whose title names a different story, a file holding several unrelated
stories, and a story that stops before it lands. It reads a verdict file a second
reader wrote against the text, drops the rows, deletes their article files, and
appends `removed.tsv` beside the set so the removal is a record rather than a
gap. It refuses to take either split under the floors it was built to.
`apply` reads JSON Lines, one object an article::

    {"url_key": "...", "labels": {...}, "second_labels": {...}}

`second_labels` is optional and may be null. It is a **second reading**, not a
correction: row #P3 compares the two with Cohen's kappa, so a row where it
merely repeats `labels` adds agreement that was never tested.

This is an operator surface, not a pipeline stage. pytest does not run
`backend/utilities/`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from idhazh.contracts.reference_dataset import (
    ReferenceDatasetRow,
    ReferenceLabels,
    ReferenceSplit,
)
from idhazh.contracts.taxonomy import Taxonomy

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DATASET_RELPATH: Final = "corpus/reference-dataset-1"
TAXONOMY_RELPATH: Final = "config/taxonomy.json"
WATCHLIST_RELPATH: Final = "config/watchlist.json"

#: The three labelling vocabularies `config/taxonomy.json` does not carry yet.
#: This block is deleted once the taxonomy declares all three.
ARTICLE_KINDS: Final = ("report", "analysis", "research", "announcement", "opinion")
SENTIMENTS: Final = ("positive", "negative", "neutral")
STANCES: Final[Mapping[str, tuple[str, ...]]] = {
    "stance-on-change": ("conservatism", "progressivism"),
    "stance-on-economic-power": ("socialism", "libertarianism"),
    "stance-on-state-power": ("statism", "constitutionalism"),
    "stance-on-borders": ("nationalism", "internationalism"),
    "stance-on-personal-sphere": ("civil-libertarianism", "communitarianism"),
}
DECLINE: Final = "not-applicable"

#: Which article kinds let the political gate open. A company announcement is
#: never one of them, and this file cannot tell a government announcement from a
#: company one - so `announcement` is admitted and the labeller carries that half.
GATE_OPENS_ON: Final = ("opinion", "analysis", "announcement")

#: Why a row leaves the set. Four defects a builder's shape checks cannot see,
#: because each is about meaning: the file carries no story, a different story
#: from the one its title names, several unrelated stories, or a story that
#: stops before it lands. `keep` is here because the verdict file carries the
#: rows that were cleared as well as the rows that go.
RETIRE_REASONS: Final = ("no-article", "title-mismatch", "many-articles", "truncated")
REMOVED_FILENAME: Final = "removed.tsv"


class RefusedError(Exception):
    """A label that may not be written, named so the operator can fix one line."""


def _dataset_dir(root: Path) -> Path:
    return root / DATASET_RELPATH


def read_rows(root: Path) -> list[ReferenceDatasetRow]:
    body = (_dataset_dir(root) / "dataset.jsonl").read_text(encoding="utf-8")
    return [ReferenceDatasetRow.model_validate_json(line) for line in body.splitlines() if line]


def read_splits(root: Path) -> dict[str, ReferenceSplit]:
    where: dict[str, ReferenceSplit] = {}
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        path = _dataset_dir(root) / "splits" / f"{side.value}.txt"
        for key in path.read_text(encoding="utf-8").split():
            where[key] = side
    return where


def active_vocabulary(root: Path) -> tuple[frozenset[str], frozenset[str], str]:
    """The desks and lenses a label may name, and the taxonomy version it is taken against.

    A **draft** entry counts. It is a word somebody committed and defined but has
    not let the pipeline publish - no feed declares it, or nobody has chosen its
    keywords - and a labeller reading an article needs it precisely then. What a
    draft may not do is reach a reader, and nothing here does.
    """
    taxonomy = Taxonomy.from_json((root / TAXONOMY_RELPATH).read_text(encoding="utf-8"))
    usable = {"active", "draft"}
    desks = frozenset(entry.id for entry in taxonomy.verticals if entry.status in usable)
    lenses = frozenset(entry.id for entry in taxonomy.lenses if entry.status in usable)
    return desks, lenses, taxonomy.version


def watchlist_ids(root: Path) -> frozenset[str]:
    payload = json.loads((root / WATCHLIST_RELPATH).read_text(encoding="utf-8"))
    return frozenset(
        entry["id"] for entry in payload["entities"] if entry.get("status") == "active"
    )


def check(
    labels: ReferenceLabels,
    *,
    desks: frozenset[str],
    lenses: frozenset[str],
    version: str,
    where: str,
) -> None:
    """Refuse anything the committed vocabulary does not name. Raises on the first fault."""

    def refuse(what: str) -> None:
        raise RefusedError(f"{where}: {what}")

    if labels.desk not in desks:
        refuse(f"desk {labels.desk!r} is not an active vertical")
    unknown = [lens for lens in labels.lenses if lens not in lenses]
    if unknown:
        refuse(f"lenses {unknown} are not active")
    if len(set(labels.lenses)) != len(labels.lenses):
        refuse("a lens is listed twice")
    if labels.article_kind not in ARTICLE_KINDS:
        refuse(f"article_kind {labels.article_kind!r} is not one of {list(ARTICLE_KINDS)}")
    if set(labels.stances) != set(STANCES):
        refuse(f"stances must carry exactly {sorted(STANCES)}")
    for axis, value in labels.stances.items():
        if value != DECLINE and value not in STANCES[axis]:
            refuse(f"{axis} may not be {value!r}")
    if labels.article_kind not in GATE_OPENS_ON:
        live = [axis for axis, value in labels.stances.items() if value != DECLINE]
        if live:
            refuse(f"the gate is shut on a {labels.article_kind}, so {live} may not carry a stance")
    if labels.sentiment is not None and labels.sentiment not in SENTIMENTS:
        refuse(f"sentiment {labels.sentiment!r} is not one of {list(SENTIMENTS)}")
    if labels.labelled_by != "human":
        refuse(f"labelled_by is {labels.labelled_by!r}, and a label is a person's")
    if labels.definition_version != version:
        refuse(f"definition_version {labels.definition_version!r} is not the committed {version!r}")


def _summary_faults(labels: ReferenceLabels, where: str) -> list[str]:
    text = labels.reference_summary
    if text is None:
        return [f"{where}: reference_summary is empty"]
    faults = []
    if not text.isascii():
        faults.append(f"{where}: reference_summary is not ASCII")
    if len(text.split()) < 25:
        faults.append(f"{where}: reference_summary is under 25 words")
    return faults


def apply(root: Path, source: Path) -> int:
    rows = read_rows(root)
    by_key = {row.url_key: index for index, row in enumerate(rows)}
    desks, lenses, version = active_vocabulary(root)

    incoming = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    touched = 0
    for entry in incoming:
        key = entry.get("url_key", "")
        if key not in by_key:
            raise RefusedError(f"{key[:12] or '<missing>'}: no such row")
        try:
            first = ReferenceLabels.model_validate(entry["labels"])
            second_payload = entry.get("second_labels")
            second = ReferenceLabels.model_validate(second_payload) if second_payload else None
        except ValidationError as error:
            raise RefusedError(f"{key[:12]}: {error}") from error

        check(first, desks=desks, lenses=lenses, version=version, where=f"{key[:12]} labels")
        for fault in _summary_faults(first, f"{key[:12]} labels"):
            raise RefusedError(fault)
        if second is not None:
            check(
                second, desks=desks, lenses=lenses, version=version, where=f"{key[:12]} second"
            )
            if second.model_dump() == first.model_dump():
                raise RefusedError(f"{key[:12]}: second_labels repeats labels, so it tests nothing")

        index = by_key[key]
        rows[index] = rows[index].model_copy(update={"labels": first, "second_labels": second})
        touched += 1

    write_rows(root, rows)
    return touched


def write_rows(root: Path, rows: Sequence[ReferenceDatasetRow]) -> None:
    """Same serialisation the builder uses, so a labelling pass changes only the label bytes."""
    body = "".join(json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n" for row in rows)
    path = _dataset_dir(root) / "dataset.jsonl"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(body, encoding="utf-8", newline="")
    temp.replace(path)


def plan(root: Path, offset: int, size: int, side: str | None) -> Iterable[str]:
    where = read_splits(root)
    rows = [row for row in read_rows(root) if row.labels.is_empty]
    if side:
        rows = [row for row in rows if where.get(row.url_key, "") == side]
    for row in rows[offset : offset + size]:
        yield "\t".join(
            (
                row.url_key,
                where.get(row.url_key, ReferenceSplit.DEV).value,
                str(row.article_words),
                row.source_domain,
                row.title,
            )
        )


def retire(root: Path, source: Path, today: str) -> tuple[int, int]:
    """Drop verified-unusable rows from the set, and record why beside it.

    A row leaves only on a verdict a second reader took against the text. The
    floors are re-checked after the removal rather than before it: a cleaning
    pass that quietly takes a split under the size the set was built to is the
    one way this verb could make the measurement worse instead of better.
    """
    dataset = _dataset_dir(root)
    rows = read_rows(root)
    where = read_splits(root)
    by_key = {row.url_key: row for row in rows}
    settings = json.loads((root / "config" / "idhazh.json").read_text(encoding="utf-8"))
    floors = settings["reference_dataset"]

    going: dict[str, tuple[str, str]] = {}
    cleared = 0
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise RefusedError(f"line {number}: expected key, verdict and evidence")
        key, verdict, evidence = (part.strip() for part in parts)
        if verdict == "keep":
            cleared += 1
            continue
        if verdict not in RETIRE_REASONS:
            raise RefusedError(f"line {number}: {verdict!r} is not one of {list(RETIRE_REASONS)}")
        if key not in by_key:
            raise RefusedError(f"line {number}: {key[:12]} is not in the set")
        if not evidence:
            raise RefusedError(f"line {number}: {key[:12]} has no evidence, so it is an opinion")
        going[key] = (verdict, evidence)

    kept = [row for row in rows if row.url_key not in going]
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        on_side = [row for row in kept if where.get(row.url_key) == side]
        domains = {row.source_domain for row in on_side}
        if len(on_side) < floors["rows_per_split_min"]:
            raise RefusedError(f"{side.value} would fall to {len(on_side)} rows, under its floor")
        if len(domains) < floors["domains_per_split_min"]:
            raise RefusedError(
                f"{side.value} would fall to {len(domains)} domains, under its floor"
            )

    write_rows(root, kept)
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        keys = [row.url_key for row in kept if where.get(row.url_key) == side]
        path = dataset / "splits" / f"{side.value}.txt"
        path.write_text("".join(key + "\n" for key in keys), encoding="utf-8", newline="")

    record = dataset / REMOVED_FILENAME
    header = "url_key\treason\tremoved_on\tsplit\tsource_domain\tevidence\n"
    body = header if not record.exists() else ""
    for key, (verdict, evidence) in going.items():
        row = by_key[key]
        (dataset / "articles" / f"{key}.txt").unlink(missing_ok=True)
        split_name = where.get(key, ReferenceSplit.DEV).value
        body += "\t".join((key, verdict, today, split_name, row.source_domain, evidence))
        body += "\n"
    with record.open("a", encoding="utf-8", newline="") as handle:
        handle.write(body)
    return len(going), cleared


def status(root: Path) -> None:
    where = read_splits(root)
    rows = read_rows(root)
    done = [row for row in rows if not row.labels.is_empty]
    second = [row for row in rows if row.second_labels is not None]
    print(f"rows            {len(rows)}")
    print(f"labelled        {len(done)}")
    print(f"second reading  {len(second)}")
    for side in (ReferenceSplit.DEV, ReferenceSplit.TEST):
        on_side = [row for row in rows if where.get(row.url_key) == side]
        ready = [row for row in on_side if not row.labels.is_empty]
        print(f"  {side.value:<12} {len(ready)} of {len(on_side)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    verbs = parser.add_subparsers(dest="verb", required=True)

    ask = verbs.add_parser("plan", help="print unlabelled articles, one a line")
    ask.add_argument("--offset", type=int, default=0)
    ask.add_argument("--size", type=int, default=25)
    ask.add_argument("--split", choices=[side.value for side in ReferenceSplit])

    put = verbs.add_parser("apply", help="merge a labels file into dataset.jsonl")
    put.add_argument("source", type=Path)

    drop = verbs.add_parser("retire", help="remove verified-unusable rows and record why")
    drop.add_argument("source", type=Path, help="key, verdict and evidence, tab separated")
    drop.add_argument("--on", default=date.today().isoformat(), help="the day it was decided")

    verbs.add_parser("status", help="count what is labelled")

    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        if args.verb == "plan":
            for line in plan(root, args.offset, args.size, args.split):
                print(line)
        elif args.verb == "apply":
            print(f"wrote {apply(root, args.source)} rows")
        elif args.verb == "retire":
            gone, cleared = retire(root, args.source, args.on)
            print(f"removed {gone} rows, cleared {cleared}")
        else:
            status(root)
    except RefusedError as refusal:
        print(f"RefusedError: {refusal}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
