"""The eval ledger's record of which measurements it already holds.

The ledger's promise is that it counts measurements rather than runs: the same
address, the same pipeline, the same words and the same scorer is one row
however many times the pipeline looks at it. Keeping that promise means the
writer has to answer "have we recorded this one?" before it appends, and until
2026-09-07 it answered by reading every score row it had ever written.

That is a bill that arrives every run for an answer the writer already had, and
it grows on a day nobody writes any code (Guardrail #12). An eval row is 819.6 bytes
wide on average because it carries eleven metrics, two model scores, a band and
a timestamp - none of which the question needs. The question needs one digest.

So the identity is written down a second time, on its own, at a fixed width.
`state/score-index/<YYYY-MM>.csv` holds one row per observation the matching
score shard holds, and the writer reads that instead of the rows.

**The declared cover is every observation identity, with nothing forgotten.**
That is deliberate, and it is why this is an index and not a clock. The identity
`("url_key", "output_digest", "scorer_version")` carries no date on purpose -
re-measuring an article a year later is the same measurement, and a window that
forgot it would let a duplicate row through and quietly overstate how much the
ledger had measured.

A row is a ten-character stamp, a comma, sixty-four hex characters and a
newline: 76 bytes, fixed by construction rather than by a corpus. Measured on
this repository on 2026-09-07 over its 7,636 measurements, that is 566.8 KB
against 6,111.8 KB of rows - 10.8 times smaller, and no spread, because both
figures are file sizes rather than timings.

CSV rather than one JSON document per month, because `.gitattributes` marks
`state/**/*.csv` `merge=union`: four to eight work shards append in parallel and
their results are merged by a machine that has never read this file. A union
merge collapses identical lines and concatenates the rest, and a digest set does
not care if a line survives twice. A JSON index would conflict instead.
"""

from __future__ import annotations

from typing import ClassVar, Self

from idhazh.contracts.base import ChangelogEntry, Contract, Sha256


class ObservationIndexRow(Contract):
    """One row of `state/score-index/<YYYY-MM>.csv`: one measurement already held."""

    __schema_stem__: ClassVar[str] = "observation-index-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-07",
            change="Initial shape: the observation digest, and the stamp every ledger row carries.",
            why=(
                "The writer's dedupe read every live score shard and every archived month "
                "before a single append. Measured on this repository on 2026-09-07: 7,636 rows, "
                "6,111.8 KB, 819.6 bytes a row, and about 173 MB once the ledger reaches steady "
                "state - a cost that rises on a day nobody writes any code, which is what "
                "Guardrail #12 refuses. The question is 64 hex characters wide, so the answer "
                "is a cheaper record of the same identities rather than a shorter memory: "
                "566.8 KB over those same measurements, 10.8 times smaller. Nothing is "
                "forgotten and no clock is involved."
            ),
        ),
    )

    observation_digest: Sha256

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: str(payload[name]) for name in self.csv_columns()}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        return cls.model_validate({name: row[name] for name in cls.model_fields})
