"""Reproduce only the ten approved examples and their real saved-vector test slices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

import numpy as np

from idhazh.contracts.story_annotation import ArticleDecision, CatalogReview, Identity, Membership
from idhazh.contracts.story_candidates import PairDecision, VectorOrder
from idhazh.contracts.story_examples import ApprovedExamples, ApprovedFixtures, WorkedExampleFixture
from idhazh.contracts.story_source import SourceCheck
from idhazh.story_dataset.catalog import empty_catalog, identity_id
from idhazh.story_dataset.source import article_id, load_articles, load_policy
from idhazh.story_dataset.storage import canonical, digest, file_hash, write_model
from utilities.record_encoder_judgments import read_frame


def build(examples_path: Path, vector_root: Path, repository: Path) -> None:
    root = repository / "corpus" / "story-dataset-1"
    fixture = repository / "backend" / "tests" / "fixtures" / "story-dataset"
    fixture.mkdir(parents=True, exist_ok=True)
    approved = ApprovedExamples.model_validate_json(examples_path.read_bytes())
    original_hash = file_hash(examples_path)
    if (
        original_hash
        != json.loads((root / "manifest.json").read_bytes())["approved_examples_sha256"]
    ):
        raise ValueError("only the approved B1-B10 source artifact can generate these fixtures")
    (root / "approved-examples.json").write_bytes(examples_path.read_bytes())
    policy = load_policy(repository / "config" / "story-dataset.json")
    articles = load_articles(root / "articles.jsonl", policy.expected_articles)
    frame, _ = read_frame(
        repository / "corpus" / "encoder-comparison-1" / "judgments" / "pairs.json"
    )
    pairs = {p.id: p for p in frame.rows}
    entities: dict[str, Identity] = {}
    worked = []

    def add(
        kind: Literal["topic", "event", "story", "occurrence"],
        key: str,
        name: str,
        parents: list[str],
        identity: str,
    ) -> str:
        identifier = identity_id(kind, key)
        if identifier not in entities:
            entities[identifier] = Identity(
                id=identifier,
                kind=kind,
                identity_key=key,
                name=name,
                parent_ids=parents,
                definition=name + ". Approved example identity, not a closed archive ontology.",
                evidence_article_ids=[identity],
            )
        elif identity not in entities[identifier].evidence_article_ids:
            entities[identifier].evidence_article_ids.append(identity)
        return identifier

    for example in approved.examples:
        pair = pairs[example.source_pair_id]
        a, b = articles[article_id(pair.a.url)], articles[article_id(pair.b.url)]
        decisions = []
        for side, article in (("a", a), ("b", b)):
            named = example.a_memberships if side == "a" else example.b_memberships
            event_name = (example.a_event if side == "a" else example.b_event) or example.event
            stories = example.a_stories if side == "a" else example.b_stories
            triples = (
                [(m.topic, m.event, m.story) for m in named]
                if named
                else [(str(example.topic), str(event_name), story) for story in stories]
            )
            if example.id == "B10":
                triples = [(str(example.topic), str(example.event), "Three-day strike deferment")]
            paths = []
            for topic_name, event_name, story_name in triples:
                topic = add(
                    "topic", "approved-topic:" + topic_name, topic_name, [], article.article_id
                )
                event = add(
                    "event", "approved-event:" + event_name, event_name, [topic], article.article_id
                )
                story = add(
                    "story",
                    "approved-story:" + event_name + ":" + story_name,
                    story_name,
                    [event],
                    article.article_id,
                )
                names = example.a_occurrences if side == "a" else example.b_occurrences
                if example.id in ("B1", "B2", "B3", "B8", "B9", "B10"):
                    names = [story_name + " specific occurrence"]
                if example.id in ("B4", "B5"):
                    names = [story_name + " ruling/launch occurrence"]
                if example.id == "B7":
                    names = [names[0]] if story_name == "Victim identification" else [names[-1]]
                occurrences = [
                    add(
                        "occurrence",
                        "approved-occurrence:" + event_name + ":" + name,
                        name,
                        [story],
                        article.article_id,
                    )
                    for name in names
                ]
                paths.append(
                    Membership(
                        topic=topic,
                        event=event,
                        story=story,
                        occurrence_refs=occurrences,
                        evidence=example.reason,
                    )
                )
            checks = [
                SourceCheck(
                    url=check.url,
                    checked_at=None,
                    state="redirect" if check.status == "HTTP301" else "read",
                    finding=check.finding or "Recorded HTTP301 redirect to " + str(check.location),
                    evidence_sha256=original_hash,
                    final_url=check.location,
                    evidence_reference="approved-examples.json; check instant was not recorded",
                )
                for check in example.source_checks
            ]
            unresolved = (
                [
                    "Explanatory-demand sibling-Story boundary needs explicit review; "
                    "stored summary conflicts with original sources."
                ]
                if example.id == "B10"
                else []
            )
            decisions.append(
                ArticleDecision(
                    input_sha256=article.input_sha256,
                    state="unresolved" if unresolved else "annotated",
                    memberships=paths,
                    reason=example.reason,
                    unresolved_reasons=unresolved,
                    review_flags=["B10-source-conflict-and-story-boundary"] if unresolved else [],
                    source_checks=checks,
                )
            )
        # These are transcriptions of approved worked examples, NOT archive labeling rules.
        occurrence = {
            "B1": "same",
            "B2": "same",
            "B3": "same",
            "B4": "different",
            "B5": "different",
            "B6": "different",
            "B7": "different",
            "B8": "partial",
            "B9": "same",
            "B10": "same",
        }[example.id]
        coverage = {
            "B1": "duplicate",
            "B2": "duplicate",
            "B3": "duplicate",
            "B4": "different",
            "B5": "different",
            "B6": "different",
            "B7": "partial",
            "B8": "partial",
            "B9": "duplicate",
            "B10": "unresolved",
        }[example.id]
        pair_decision = PairDecision.model_validate(
            {
                "input_sha256": digest({"a": a, "b": b}),
                "topic": "shared",
                "event": "different" if example.id in ("B4", "B5") else "shared",
                "story": "unresolved"
                if example.id == "B10"
                else ("different" if example.id in ("B4", "B5") else "shared"),
                "occurrence": occurrence,
                "coverage": coverage,
                "reason": example.reason,
                "unresolved_reasons": decisions[0].unresolved_reasons,
                "review_flags": decisions[0].review_flags,
                "source_checks": [check.model_dump() for check in decisions[0].source_checks],
            }
        )
        worked.append(
            WorkedExampleFixture(
                id=example.id,
                source_pair_id=example.source_pair_id,
                a=a,
                b=b,
                a_decision=decisions[0],
                b_decision=decisions[1],
                pair_decision=pair_decision,
            )
        )
    review = CatalogReview(
        expected_revision=empty_catalog().revision,
        reviewer="gpt-6.1-sol approved B1-B10 fixture transcriber",
        reason="Owner approved B1-B10 meanings in parent task; original artifact status preserved. "
        "B10 disputed explanatory sibling is NOT seeded.",
        entities=list(entities.values()),
    )
    write_model(root / "seed-catalog-review.json", review)
    write_model(
        fixture / "approved.json",
        ApprovedFixtures(
            approved_examples_sha256=original_hash,
            approval_reference=(
                "Owner approved B1-B10 task, 2026-10-09; fixtures, not primary records."
            ),
            catalog=review,
            examples=worked,
        ),
    )
    fixture_ids = list(
        dict.fromkeys(
            identity
            for example in worked
            for identity in (example.a.article_id, example.b.article_id)
        )
    )
    (root / "approved-example-ids.json").write_bytes(canonical(fixture_ids))
    encoded = json.loads(
        (repository / "corpus" / "encoder-comparison-1" / "pairs.json").read_bytes()
    )
    indices = {article_id(url): i for i, url in enumerate(encoded["urls"])}
    hashes = {}
    original_hashes = {}
    for slug, relative in policy.vector_files.items():
        old = np.load(vector_root / relative, mmap_mode="r", allow_pickle=False)
        np.save(
            fixture / (slug + ".npy"), old[[indices[i] for i in fixture_ids]], allow_pickle=False
        )
        hashes[slug] = file_hash(fixture / (slug + ".npy"))
        original_hashes[slug] = file_hash(vector_root / relative)
    write_model(
        fixture / "vector-order.json",
        VectorOrder(
            article_ids=fixture_ids,
            source_input_sha256=file_hash(
                repository / "corpus" / "encoder-comparison-1" / "pairs.json"
            ),
            vectors_sha256=hashes,
            original_vector_sha256=original_hashes,
        ),
    )
    print(
        f"{len(worked)} approved examples; {len(fixture_ids)} real articles; "
        f"{len(entities)} explicit seed identities; no primary labels imported"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--vector-root", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    build(args.examples, args.vector_root, args.repository)


if __name__ == "__main__":
    main()
