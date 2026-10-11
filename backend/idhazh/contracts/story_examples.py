"""Which approved worked examples exercise the hierarchy without relabeling the old frame?"""

from pydantic import Field

from idhazh.contracts.base import Model, Sha256, Url
from idhazh.contracts.story_annotation import ArticleDecision, CatalogReview
from idhazh.contracts.story_candidates import PairDecision
from idhazh.contracts.story_source import ArticleEvidence, Nonempty


class NamedPath(Model):
    topic: Nonempty
    event: Nonempty
    story: Nonempty


class ExampleSourceCheck(Model):
    url: Url
    status: Nonempty
    finding: Nonempty | None = None
    location: Url | None = None


class ApprovedExample(Model):
    id: Nonempty
    source_pair_id: Nonempty
    topic: Nonempty | None = None
    event: Nonempty | None = None
    a_event: Nonempty | None = None
    b_event: Nonempty | None = None
    a_stories: list[Nonempty] = Field(default_factory=list)
    b_stories: list[Nonempty] = Field(default_factory=list)
    a_occurrences: list[Nonempty] = Field(default_factory=list)
    b_occurrences: list[Nonempty] = Field(default_factory=list)
    a_memberships: list[NamedPath] = Field(default_factory=list)
    b_memberships: list[NamedPath] = Field(default_factory=list)
    relation: Nonempty
    reason: Nonempty
    evidence: Nonempty
    source_checks: list[ExampleSourceCheck] = Field(default_factory=list)
    needs_targeted_review: bool = False
    granularity_question: Nonempty | None = None


class ApprovedExamples(Model):
    status: Nonempty
    frame_sha256: Sha256
    scope: Nonempty
    examples: list[ApprovedExample]
    limits: list[Nonempty]


class WorkedExampleFixture(Model):
    id: Nonempty
    source_pair_id: Nonempty
    a: ArticleEvidence
    b: ArticleEvidence
    a_decision: ArticleDecision
    b_decision: ArticleDecision
    pair_decision: PairDecision


class ApprovedFixtures(Model):
    approved_examples_sha256: Sha256
    approval_reference: Nonempty
    catalog: CatalogReview
    examples: list[WorkedExampleFixture]
