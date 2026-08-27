"""The two pieces of text one scored item was judged on, kept so a person can read them.

The faithfulness question a human labeller answers is "does this summary assert
anything the article does not support?", and nothing in the committed ledger
carries either text. `state/scores.csv` names the words that came out
(`output_digest`) and the words that went in (`source_digest`) and holds
neither.

**The premise here is the text the scorer read** - the article after extraction,
sanitizing and the truncation cap - never the page as it stands today. Re-fetching
the address at label time would hand the person a different document from the one
the number came from, so their disagreement with the scorer would measure a
premise mismatch and not a scorer error.

**Never committed.** An article body is not ours to republish (`CLAUDE.md`
section 0a), so this payload is written under `backend/var/evidence/`, which is
gitignored, and travels to a labeller as a workflow artifact with a finite life.

**Why a contract at all**, when the file is gitignored and a re-run rebuilds it:
it crosses a process boundary and usually a machine boundary, which is what makes
a shape a payload rather than a local variable (section 1a). The label CLI has to
be able to refuse a file it cannot trust, and refusing needs a shape to check
against. `backend/var/run/<date>/plan.json` and `<item_id>.article.json` are
gitignored and regenerable in exactly the same way and are contracts for exactly
the same reason.

**It is a contract under Rule #3 and not a migration surface under section 11.**
Nothing this payload was ever written into survives: the oldest copy that can
exist is a workflow artifact 14 days old, and a re-run rebuilds it byte for byte.
So a shape change here never owes a read-side migration - it owes a re-run. The
`version` field is carried because every `Contract` carries one and because it
tells a labeller which build wrote the file in front of them, not because an
older payload has to keep validating.

`source_digest` is rebuilt from `premise` on read rather than trusted, so a file
whose text was edited after the run cannot load at all.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Sha256,
    Url,
    UrlKey,
    derive_text_digest,
)


class EvidenceItem(Contract):
    """One scored item's premise and summary, addressed by the measurement it belongs to."""

    __schema_stem__: ClassVar[str] = "evidence-item"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27",
            change="Initial shape: the measurement's identity, the premise, and the summary.",
            why=(
                "The faithfulness bands are a reader-facing promise with no measured human "
                "error rate, and the label queue could not produce one: it showed a "
                "labeller the headline and the link and never the article the verdict has "
                "to judge. This payload carries the exact text the scorer read, beside the "
                "exact summary it scored, so a human and the scorer answer the same "
                "question about the same document."
            ),
        ),
    )

    # The four fields that identify one measurement, spelled exactly as
    # `state/scores.csv` spells them. A file is named by their digest, so a
    # ledger row finds its evidence without a lookup table.
    url_key: UrlKey
    pipeline_fingerprint: Sha256
    output_digest: Sha256
    scorer_version: str = Field(min_length=1)

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    source_url: Url
    title: UntrustedLine | None = None

    source_digest: Sha256 = Field(
        description=(
            "sha256 of `premise`, the same value the eval row carries. Recomputed on read, "
            "so an edited premise fails to load rather than reaching a labeller."
        )
    )
    premise: str = Field(
        description=(
            "The article after extraction, sanitizing and the truncation cap - the text the "
            "scorer read, byte for byte. Untrusted (Rule #11): it prints as inert terminal "
            "text and never becomes a prompt, a path or a URL."
        )
    )
    summary: str = Field(
        description=(
            "The summary the scorer scored against `premise`. The published item also "
            "carries key points; they are left out because the scorer never read them, and "
            "showing a labeller words the number does not cover would put the two of them "
            "back on different questions."
        )
    )

    @model_validator(mode="after")
    def _digest_is_rebuilt_not_trusted(self) -> Self:
        if self.source_digest != derive_text_digest(self.premise):
            raise ValueError("source_digest must be sha256 of premise, recomputed on read")
        return self
