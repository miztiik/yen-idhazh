"""Draw the human-label queue from the committed eval ledger.

Pure and deterministic: the same ledger and the same draw id give the same 60
rows on any machine, so a draw is reproducible rather than remembered. No model
runs here and nothing in this module may import one - the whole point of the
instrument is that it measures the scorer against a human, and a judge that
shares the failure modes of the thing judged is not a measurement
(`CLAUDE.md` section 0a).

The draw is uniform across `hhem` deciles, not concentrated at the cuts. The
question these labels answer first is a level question - what does `high` mean at
all - and a boundary-weighted draw could not answer it: it would speak about
0.75 to 0.85 and stay silent about the majority of the ledger. Re-weighting a
uniform draw to the live distribution recovers an overall rate; the reverse is
not available.

The strata are how the rows are chosen and never how they are ordered. The queue
comes back in one global `label_id` order, so the sequence says nothing about
which decile a row came from.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Final

from idhazh.contracts.label_row import LabelRow
from idhazh.ledger import read_header as _read_header
from idhazh.ledger import require_matching_header

LEDGER_RELPATH: Final = "state/labels.csv"

#: Ten `hhem` deciles: [0.0,0.1), [0.1,0.2) ... [0.9,1.0]. A score of exactly
#: 1.0 belongs to the last one rather than to an eleventh bucket of its own.
DECILES: Final = 10


def decile_of(hhem: float) -> int:
    """Which decile a score falls in, with 1.0 in the top one."""
    return min(int(hhem * DECILES), DECILES - 1)


def label_id(record: Mapping[str, str], *, draw_id: str) -> str:
    """The draw key, and the shuffle key, in one value.

    Hashed over the full identity - the address, the inputs that produced the
    words, the instrument that read them, and the draw - so a re-draw under a new
    scorer is genuinely a new draw and can never silently reuse the old one's
    rows.
    """
    material = "|".join(
        (
            draw_id,
            record["url_key"],
            record["pipeline_fingerprint"],
            record["output_digest"],
            record["scorer_version"],
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()[:16]


def eligible(records: Iterable[Mapping[str, str]], *, scorer_version: str) -> list[dict[str, str]]:
    """Ledger rows the live instrument produced.

    Rows at an older `scorer_version` are excluded, because a stratum computed
    across two instruments is not a stratum. Short-source rows are deliberately
    KEPT: they are extraction failures rather than summary defects, and dropping
    them would bias the sample toward well-extracted items - the exact sampling
    error the labels exist to avoid. The `unjudgeable` tag carries them instead.
    """
    return [dict(record) for record in records if record.get("scorer_version") == scorer_version]


def draw(
    records: Iterable[Mapping[str, str]],
    *,
    draw_id: str,
    scorer_version: str,
    per_decile: int,
) -> list[dict[str, str]]:
    """`per_decile` rows from each `hhem` decile, deterministic by hash.

    A decile with fewer rows than asked for contributes all of them; the draw
    does not borrow from a neighbour to hit a round number, because a stratum
    that quietly includes another stratum's rows is not the stratum it is named
    after. The shortfall is visible in the result and belongs in the report.

    Rows come back in one global `label_id` order. Hiding the number while
    emitting decile after decile hid nothing: a labeller working down the queue
    still read the confidence gradient off the sequence, and the first twenty
    rows were the bottom three deciles entire. `label_id` is a hash over the
    address, the inputs, the words, the instrument and the draw, so sorting the
    whole picked set by it is a shuffle that needs no seed and stays
    reproducible - which matters the moment two labellers compare notes.
    """
    pool = eligible(records, scorer_version=scorer_version)
    buckets: dict[int, list[dict[str, str]]] = {index: [] for index in range(DECILES)}
    for record in pool:
        record["label_id"] = label_id(record, draw_id=draw_id)
        buckets[decile_of(float(record["hhem"]))].append(record)

    picked: list[dict[str, str]] = []
    for index in range(DECILES):
        bucket = sorted(buckets[index], key=lambda row: row["label_id"])
        picked.extend(bucket[:per_decile])
    return sorted(picked, key=lambda row: row["label_id"])


def shortfalls(picked: Sequence[Mapping[str, str]], *, per_decile: int) -> dict[int, int]:
    """Deciles the ledger could not fill, and by how many.

    Reported rather than hidden: a draw of 47 rows is a draw of 47 rows, and
    calling it 60 is how a denominator starts lying.
    """
    counted = dict.fromkeys(range(DECILES), 0)
    for record in picked:
        counted[decile_of(float(record["hhem"]))] += 1
    return {index: per_decile - count for index, count in counted.items() if count < per_decile}


def run_days(records: Iterable[Mapping[str, str]], *, scorer_version: str) -> set[str]:
    """Distinct run-days at one instrument. The collection requirement counts these."""
    return {record["date"] for record in eligible(records, scorer_version=scorer_version)}


def columns() -> tuple[str, ...]:
    return LabelRow.csv_columns()


def read_header(path: Path) -> tuple[str, ...]:
    return _read_header(path)


def recorded(path: Path) -> set[tuple[str, str]]:
    """Every (label_id, labeller) already in the file.

    Keyed on both, because a second labeller on the same row is the overlap that
    makes agreement measurable, while the same labeller twice is a duplicate.
    """
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {(row["label_id"], row["labeller"]) for row in csv.DictReader(handle)}


def append(path: Path, rows: Iterable[LabelRow]) -> int:
    """Append labels, writing the header only when the file is new.

    Refuses a row this labeller already gave for this draw key. A label is a
    considered human judgement, so a second one from the same person on the same
    words is a mis-click rather than new evidence.
    """
    pending = list(rows)
    if not pending:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, columns())

    already = recorded(path)
    fresh: list[LabelRow] = []
    for row in pending:
        key = (row.label_id, row.labeller)
        if key in already:
            continue
        already.add(key)
        fresh.append(row)
    if not fresh:
        return 0

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns(), lineterminator="\n")
        if not exists:
            writer.writeheader()
        for row in fresh:
            writer.writerow(row.csv_row())
    return len(fresh)
