"""Write the text one scored item was judged on, and hand it back to a labeller.

The run has both texts in hand for a moment and then throws them away: the
premise lives in a shard checkout that is deleted when the job ends, and the
committed ledger keeps only digests. This module is the copy that survives long
enough for a person to read it.

**Written during the run, never re-fetched later.** The scorer read the article
after extraction, sanitizing and the truncation cap. Fetching the address again
at label time returns a different document - the page moves, the extractor
changes, the cap changes - so the human and the scorer would be answering
questions about two documents and their disagreement would measure that instead
of scorer error.

**Not committed and not served.** `backend/var/evidence/` is gitignored. An
article body is not ours to republish (`CLAUDE.md` section 0a), so it reaches a
labeller as a workflow artifact with a retention date, or not at all.

**One file per measurement, named by the measurement.** The name is a digest of
the four fields `state/scores.csv` identifies a row by, so a ledger row finds its
evidence with no index and no lookup table, and two shards writing the same
address cannot disagree about what is in it.

**Refusal is the point.** A labeller reading different text from the scorer
produces a measurement of nothing, so every way that can happen has its own
sentence: a row scored before the premise was recorded, a row the package does
not hold, a file whose text no longer matches its own digest, and a file whose
premise is not the one the ledger row names.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import ValidationError

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.evidence import EvidenceItem
from idhazh.evals.writer import observation

#: Relative and POSIX-separated, because it is quoted in logs, in the workflow
#: and in the operator how-to (`CLAUDE.md` section 2).
EVIDENCE_ROOT_RELPATH: Final = "backend/var/evidence"


def key_of(payload: Mapping[str, object]) -> str:
    """The content address of one measurement, from a ledger row or from a payload.

    Built from the same four fields `evals.writer` calls an observation, so a
    file written by the run and a row read from the CSV land on the same name.
    Recomputed from the value fields every time and never carried inside the
    payload, which is what keeps a renamed file from claiming to be another
    measurement.
    """
    return derive_text_digest("|".join(observation(payload)))


def of(row: EvalRow, *, premise: str, summary: str) -> EvidenceItem:
    """The evidence for one eval row, built from the row so the two cannot disagree."""
    return EvidenceItem(
        version=EvidenceItem.schema_version(),
        url_key=row.url_key,
        pipeline_fingerprint=row.pipeline_fingerprint,
        output_digest=row.output_digest,
        scorer_version=row.scorer_version,
        date=row.date,
        run_id=row.run_id,
        item_id=row.item_id,
        source_url=row.source_url,
        title=row.title,
        source_digest=derive_text_digest(premise),
        premise=premise,
        summary=summary,
    )


def path_for(directory: Path, item: EvidenceItem) -> Path:
    return directory / f"{key_of(item.model_dump(mode='json'))}.json"


def posix_relpath(path: Path, *, base: Path) -> str:
    """How a path is spelled when it leaves this process (`CLAUDE.md` section 2).

    Relative to whatever the caller is talking about - the repository for a file
    the run wrote, the package directory for a file an operator downloaded - and
    POSIX-separated either way. A path outside its base has no minimal form, so
    it keeps its own name only.
    """
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.name


def index(package: Path) -> dict[str, Path]:
    """Every evidence file in a package, keyed by the measurement it belongs to.

    Recursive, because a downloaded package arrives in whatever shape the
    workflow uploaded it - flat, or one directory per shard - and both are the
    same package. A missing directory is an empty package rather than an error:
    the tool's job is to say which rows it cannot show, and none of them is a
    louder answer than all of them.
    """
    if not package.is_dir():
        return {}
    return {path.stem: path for path in sorted(package.rglob("*.json"))}


class Evidence(NamedTuple):
    """What a package could offer for one ledger row, or the sentence saying why not."""

    item: EvidenceItem | None
    refusal: str | None


NO_DIGEST: Final = (
    "this row was scored before the run recorded which text it read, so nothing "
    "here can prove an article is that text"
)
NOT_HELD: Final = "this package holds no evidence for this measurement"
UNREADABLE: Final = "this evidence file does not match its own digest, so its text was changed"
DIFFERENT_TEXT: Final = (
    "this evidence names a different premise from the one the ledger row was scored on"
)


def look_up(package: Mapping[str, Path], record: Mapping[str, str]) -> Evidence:
    """The evidence for one ledger row, or the reason a labeller must not judge it."""
    digest = str(record.get("source_digest") or "").strip()
    if not digest:
        return Evidence(None, NO_DIGEST)
    path = package.get(key_of(record))
    if path is None:
        return Evidence(None, NOT_HELD)
    try:
        item = EvidenceItem.from_json(path.read_text(encoding="utf-8"))
    except (ValidationError, OSError, UnicodeDecodeError):
        return Evidence(None, UNREADABLE)
    if item.source_digest != digest:
        return Evidence(None, DIFFERENT_TEXT)
    return Evidence(item, None)
