"""The evidence one model qualification leaves behind.

A qualification runs one model. There is no incumbent arm and no paired replay:
the owner ruled on 2026-08-26 that the candidate is judged alone, and Andre
ruled that re-basing the dropped comparisons on the committed 8B history would
be confounded - those rows span two run-days, the articles differ every day, and
they were written while the stamp still digested placeholders.

So the gates are absolute rather than relative, every threshold is read from
something already committed, and the shape here is what makes that auditable: a
gate carries its measured value, its threshold, and where the threshold came
from, so a failure names the number rather than the opinion.

Two documents, because two jobs write them. A capture-and-replay shard writes a
`QualificationShard` - the frozen corpus it hashed, every call it made, and the
canaries it ran. The decide job merges those and writes one
`QualificationReport`. Neither carries article text: the corpus lives under
gitignored `backend/var/` and only its hashes travel (`CLAUDE.md` section 0a -
the pipeline never republishes an article body).
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    Sha256,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    canonical_json,
)


class GateName(StrEnum):
    """The eleven gates that block adoption. Closed set, never free text."""

    REASONING_LEAKAGE = "reasoning_leakage"
    SCHEMA_VALIDITY = "schema_validity"
    INJECTION_CANARIES = "injection_canaries"
    DETERMINISM = "determinism"
    PUBLISHABLE_LENGTH = "publishable_length"
    CONTEXT_FIT = "context_fit"
    IDENTITY = "identity"
    BUDGET = "budget"
    SCORED_DENOMINATOR = "scored_denominator"
    FAITHFULNESS_FLOOR = "faithfulness_floor"
    BRIEF_COPYING_CEILING = "brief_copying_ceiling"


class GateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class GateOutcome(Model):
    """One gate, and the arithmetic that decided it.

    `measured` and `threshold` are spelled rather than typed as floats because
    the gates do not share a unit - one counts calls, one counts minutes, one is
    a mean between zero and one - and a column that means a different thing on
    every row is a column nobody can read.
    """

    gate: GateName
    status: GateStatus
    measured: str = Field(min_length=1, description="What this run observed, in its own unit.")
    threshold: str = Field(min_length=1, description="The bar, in the same unit.")
    source: str = Field(
        min_length=1, description="Where the bar is read from. Never a number typed here."
    )
    detail: str = Field(
        min_length=1, description="The gate's own words, so a reader needs no code."
    )


class Diagnostic(Model):
    """A number recorded and never blocked on.

    Every one carries its denominator. A rate over four items is not a rate, and
    a diagnostic that hides its denominator is how an unmeasured number gets
    cited later as if it were evidence (Rule #10).
    """

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    denominator: int = Field(ge=0, description="How many observations produced the value.")


class CandidateIdentity(Model):
    """Which bytes ran. A model-card name identifies nothing."""

    model_id: Slug
    repo: str = Field(min_length=1)
    revision: str = Field(
        min_length=1, description="An immutable repository revision, not a branch."
    )
    file: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256_expected: Sha256 = Field(description="What the adoption target declares.")
    sha256_observed: Sha256 = Field(description="What the runtime actually opened.")
    bytes_expected: int = Field(ge=1)
    bytes_observed: int = Field(ge=1)
    runtime_build: str = Field(min_length=1)


class ScorerIdentity(Model):
    """Which instrument read the summaries.

    `pinned` is false when the revision is a branch name. The faithfulness gate
    refuses to run on an unpinned scorer: a floor measured with an instrument
    that can move overnight measures an unknown instrument.
    """

    scorer_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    pinned: bool
    weights_sha256: Sha256 = Field(
        description="Digest of the weights that loaded, never of the name they were asked for."
    )
    scorer_version: str = Field(min_length=1)


class CorpusItem(Model):
    """One frozen article: what it is, and the hashes that prove it did not move."""

    item_id: ItemId
    url_key: UrlKey
    canonical_url: Url
    source_id: Slug
    vertical: Slug
    band_index: int = Field(
        ge=0, description="Which `summarize.bands` tier the extracted length fell in."
    )
    brief: bool
    truncated: bool = Field(
        description="The extracted text passed `extract.truncation_cap_tokens` and was cut."
    )
    source_word_count: int = Field(ge=0)
    seen_word_count: int = Field(ge=0)
    seen_token_count: int = Field(ge=0)
    seen_text_sha256: Sha256 = Field(description="The exact bytes the model was shown.")
    full_text_sha256: Sha256 = Field(
        description=(
            "The sanitized article the scorer read. Extract does not keep the pre-cap "
            "text, so on a truncated item this equals seen_text_sha256 and says so."
        )
    )


class ItemObservation(Model):
    """One inference call: one corpus item at one repeat.

    Every call is recorded, including the ones that failed. A failure that
    vanishes from the record takes the denominator with it, and the success rate
    then describes the survivors rather than the run.
    """

    item_id: ItemId
    repeat: int = Field(ge=1)
    ok: bool
    failure_code: str | None = None
    finish_reason: str = Field(min_length=1)
    reasoning_channel_used: bool = Field(
        description="The runtime split a reasoning channel off the content."
    )
    think_block_words: int = Field(
        ge=0, description="Words inside inline `<think>` blocks. Any is a leak."
    )
    schema_valid: bool
    repaired: bool = Field(description="A second attempt was needed. The gate allows none.")
    output_digest: Sha256
    summary_word_count: int = Field(ge=0)
    prompt_tokens: int = Field(
        ge=0, description="The complete chat-templated request, as counted by the runtime."
    )
    completion_tokens: int = Field(ge=0)
    fits_context_predicted: bool = Field(
        description="What `summarize.fits_context` said before the call."
    )
    summarize_seconds: float = Field(ge=0.0)


class ItemScore(Model):
    """What the scorer and the counterweights read on one item.

    Scored once per item, on the first repeat. Two more repeats of identical
    words would add three identical rows and no information.
    """

    item_id: ItemId
    brief: bool
    hhem: float = Field(ge=0.0, le=1.0)
    hhem_full: float = Field(ge=0.0, le=1.0)
    verbatim_run: float = Field(ge=0.0, le=1.0)
    extractiveness: float = Field(ge=0.0, le=1.0)
    compression: float = Field(ge=0.0)
    lead_coverage: float = Field(ge=0.0, le=1.0)
    unsupported_numbers: int = Field(ge=0)
    hedge_dropped: bool
    evidential_density: float = Field(ge=0.0)
    speculative_density: float = Field(ge=0.0)
    title_fell_back: bool = Field(description="The drafted title missed its range and was dropped.")


class CanaryObservation(Model):
    """One planted attack, run live against the candidate.

    The unit suite proves the sanitizer and the schema against recorded
    completions. It cannot prove that a model nobody has served before follows
    this chat template, so the canaries run again here on live calls (Rule #11).

    `replied` is false for two very different reasons - the attack was never put
    to the model, or the model answered with nothing publishable - and neither
    is a marker that survived. The run on 2026-08-26 failed here with every
    marker list empty, and it was written up as a sanitizer breach, so the
    reason travels with the observation now rather than living in a log line
    the next reader no longer has.
    """

    name: Slug
    replied: bool = Field(description="A schema-valid, non-blank reply came back.")
    failure_code: str | None = Field(
        default=None, description="Why no reply came back. Null when the candidate replied."
    )
    failure_detail: UntrustedLine | None = Field(
        default=None, description="The summarizer's own words about that failure."
    )
    markers_present: list[str] = Field(
        default_factory=list, description="`must_not_survive` strings that reached the reply."
    )
    facts_missing: list[str] = Field(
        default_factory=list, description="`must_survive` facts the boundary ate."
    )
    forbidden_keys_present: list[str] = Field(
        default_factory=list, description="`forbidden_output` keys the raw reply carried."
    )


class QualificationShard(Contract):
    """What one capture-and-replay job uploads.

    The corpus is hashed and written before the first inference call, so the
    pre-registration is an ordering the code enforces rather than a promise in a
    document.
    """

    __schema_stem__: ClassVar[str] = "qualification-shard"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27",
            change="Added optional failure_code and failure_detail to CanaryObservation.",
            why=(
                "A canary that never replied and a canary whose reply carried the attack "
                "both landed as `replied: false` with nothing to tell them apart, so a "
                "blank reply was read as a sanitizer breach. Both fields are nullable, so "
                "a shard written before today still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Initial shape: the frozen corpus, every call, every score and the canaries.",
            why=(
                "Row #10 qualifies one model on absolute gates, so the evidence a shard "
                "hands the decider is a persisted contract rather than a log line."
            ),
        ),
    )

    date: DateStamp
    commit_sha: str = Field(min_length=7)
    runner: str = Field(min_length=1)
    shard: int = Field(ge=0)
    shards: int = Field(ge=1)
    repeats: int = Field(ge=1)
    candidate: CandidateIdentity
    scorer: ScorerIdentity
    pipeline_fingerprint: Sha256 = Field(
        description="The stamp the controls produced. One value across every shard."
    )
    corpus_registered_at: Timestamp = Field(
        description="When the hashes were written. Before any output was viewed."
    )
    planned: int = Field(ge=0, description="Addresses this shard was handed.")
    corpus: list[CorpusItem] = Field(default_factory=list)
    observations: list[ItemObservation] = Field(default_factory=list)
    scores: list[ItemScore] = Field(default_factory=list)
    canaries: list[CanaryObservation] = Field(default_factory=list)
    elapsed_seconds: float = Field(
        ge=0.0, description="Wall-clock this shard spent inside the stage."
    )

    @model_validator(mode="after")
    def _every_observation_names_a_frozen_item(self) -> Self:
        known = {item.item_id for item in self.corpus}
        unknown = sorted({o.item_id for o in self.observations} - known)
        if unknown:
            raise ValueError(f"observations for items that were never frozen: {unknown}")
        return self


class QualificationReport(Contract):
    """The merged verdict: every gate, every diagnostic, one answer."""

    __schema_stem__: ClassVar[str] = "qualification-report"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-26",
            change="Initial shape: eleven hard gates, the diagnostics, and the corpus digest.",
            why=(
                "An adoption gate that reports a pass without the number that produced it "
                "cannot be re-read six months later (Rule #10)."
            ),
        ),
    )

    date: DateStamp
    commit_sha: str = Field(min_length=7)
    runner: str = Field(min_length=1)
    candidate: CandidateIdentity
    scorer: ScorerIdentity
    pipeline_fingerprint: Sha256
    corpus_digest: Sha256 = Field(
        description="Digest over the frozen item hashes. Two runs on one corpus share it."
    )
    corpus_items: int = Field(ge=0)
    planned: int = Field(ge=0, description="The full attempted denominator, failures included.")
    repeats: int = Field(ge=1)
    scored: int = Field(ge=0)
    gates: list[GateOutcome]
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    qualified: bool
    detail: str = Field(min_length=1)

    @model_validator(mode="after")
    def _every_gate_is_reported_once(self) -> Self:
        seen = [outcome.gate for outcome in self.gates]
        if len(set(seen)) != len(seen):
            raise ValueError("a gate reported twice is two answers to one question")
        missing = sorted(set(GateName) - set(seen))
        if missing:
            raise ValueError(f"gates never evaluated: {[gate.value for gate in missing]}")
        return self

    @model_validator(mode="after")
    def _the_verdict_is_the_gates(self) -> Self:
        passed = all(outcome.status is GateStatus.PASSED for outcome in self.gates)
        if self.qualified != passed:
            raise ValueError("qualified must be exactly whether every gate passed")
        return self


def corpus_digest(items: list[CorpusItem]) -> str:
    """One digest over the frozen corpus, order-independent.

    Order-independent because the shards capture in parallel and the union is
    the corpus. Built from the two text hashes and the address, so a page that
    was rewritten between two runs produces a different corpus and says so.
    """
    payload = sorted([item.url_key, item.seen_text_sha256, item.full_text_sha256] for item in items)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
