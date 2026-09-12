"""What a committed day was already checked against, so it is not read again.

A published day is frozen. The only thing that can happen to it is deletion, so
nothing about it can stop matching its contracts on its own - what can move is
the shape it is read through. `cli.stage_validate_days` opened every committed
day anyway, on every scheduled publication and on every CI run, parsed it and
put it through both contracts a reader holds. Measured on this repository on
2026-09-08, on an Intel Core i7-1265U: 18 committed days, 19,867,266 bytes,
0.45 s median over three runs (best 0.45 s, worst 0.96 s), and one more day
every day nobody writes any code. That is the cost Guardrail #12 refuses.

So the answer is a receipt rather than a clock. A frozen artefact does not
become suspect with age; it becomes suspect when the rules move. A row here
records that one day's payload passed one validator, and the next run reads the
row instead of the day.

**What a row claims.** That the payload for `date`, of exactly `payload_bytes`
and digesting to `payload_digest`, passed the validator identified by
`validator_version`. The digest is taken from the bytes that passed - the day is
open at that moment anyway - and is never guessed from anything else.

**What the skip consults, and why it is not the digest.** A digest cannot be
compared without reading the file, and reading every file is the cost this
record exists to remove. `os.stat` answers the length without opening anything,
so a skip is `date`, length and validator.

A day can carry more than one row, and only the rows at the length on disk say
anything about the payload that is there now. A closed day that `backfill.yml`
re-encoded leaves a truthful new row beside a row about the payload that used to
be there, and the old one is ignored rather than held against the day. Where two
rows claim the same length and different bytes, one of them is wrong and the day
is opened again rather than trusted. That is what the digest is for.

**What it therefore does not catch**, stated rather than hidden: a committed day
edited outside the pipeline to exactly its old length. Everything a producer
does either moves the length or is validated head-on - a run names the day it
wrote, and a named day is always opened.

CSV rather than one JSON document, because `.gitattributes` marks
`state/*.csv` `merge=union`. Two runs appending rows are merged by a machine
that has never read this file, and a union over independent rows is exactly
right here. It also makes the file append-only: a rewrite that dropped a
superseded row would be resolved by a union that puts it back. The file
therefore grows by one row a day, plus one a day for each time the validator
moves, at about 155 bytes a row. **Deleting it is always safe** - a missing
receipt costs one full sweep and never a wrong answer - so an operator who
wants it smaller truncates it and lets the next run rebuild it.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Sha256


class DayValidationReceipt(Contract):
    """One row of `state/day-validations.csv`: one frozen day, one validator."""

    __schema_stem__: ClassVar[str] = "day-validation-receipt"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-08",
            change=(
                "Initial shape: the day, the length and digest of the payload that "
                "passed, and the identity of the validator that passed it."
            ),
            why=(
                "`validate-days` re-read every committed day on every publication and "
                "every CI run - 18 days and 19,867,266 bytes on 2026-09-08, 0.45 s "
                "median, and one day more every day nobody writes any code (Guardrail #12). "
                "A published day is frozen, so re-reading it can only find a fault the "
                "day it was written already refused. What can change is the contract it "
                "is read through, so the receipt keys on the validator's identity as "
                "well as on the payload, and a validator that moves invalidates every "
                "row at once."
            ),
        ),
    )

    date: DateStamp = Field(description="The published day this row is about.")
    payload_bytes: int = Field(
        ge=1,
        description=(
            "The length of the day payload that passed. Compared against `os.stat` on a "
            "later run, which is what lets an unchanged day be skipped without opening "
            "it. A length of zero is not a day."
        ),
    )
    payload_digest: Sha256 = Field(
        description=(
            "sha256 over the payload bytes that passed. Taken from the bytes, never "
            "derived from anything else. It is what makes two rows about one day "
            "detectable as disagreeing after a union merge."
        )
    )
    validator_version: Sha256 = Field(
        description=(
            "The identity of what the day was checked against: both generated schemas "
            "plus the source of the functions that do the checking. It moves when any "
            "of them moves, so it cannot be left behind by hand."
        )
    )

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
