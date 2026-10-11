"""Route explicit new-candidate registration, bounded encoding and immutable unit import."""

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from idhazh.contracts.story_encoder_candidate import (
    CandidateVectorState,
    CandidateVectorUnit,
    PinnedEncoderCandidate,
)
from idhazh.contracts.story_source import SourceCheck
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.encoder_candidates import (
    register_candidate_unit,
    register_pinned_candidate,
)
from idhazh.story_dataset.pinned_encoding import encode_pinned_selected
from idhazh.story_dataset.source import load_policy, validate_freeze
from idhazh.story_dataset.storage import digest, read_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("corpus/story-dataset-1"))
    parser.add_argument("--root", type=Path, default=Path("corpus/story-dataset-1"))
    parser.add_argument("--repository", type=Path, default=Path())
    parser.add_argument("--policy", type=Path, default=Path("config/story-dataset.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    registration = commands.add_parser("register")
    registration.add_argument("--vectors", type=Path, required=True)
    registration.add_argument("--legacy-root", type=Path, required=True)
    registration.add_argument("--slug", required=True)
    registration.add_argument("--pin", required=True)
    registration.add_argument("--metadata", type=Path, required=True)
    registration.add_argument("--check", type=Path, required=True)
    encoding = commands.add_parser("encode")
    encoding.add_argument("--candidate", type=Path, required=True)
    encoding.add_argument("--ids", type=Path, required=True)
    encoding.add_argument("--output", type=Path, required=True)
    importing = commands.add_parser("import")
    importing.add_argument("--candidate", type=Path, required=True)
    importing.add_argument("--unit", type=Path, required=True)
    importing.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        manifest, articles = validate_freeze(args.source_root, args.repository, policy)
        if args.command == "register":
            vectors = read_model(args.vectors, VectorSnapshot)
            if vectors.source_sha256 != manifest.source_sha256:
                raise ValueError("legacy vectors belong to another frozen source")
            result = register_pinned_candidate(
                vectors,
                args.legacy_root,
                args.slug,
                args.pin,
                args.metadata,
                read_model(args.check, SourceCheck),
                args.root,
            )
            print(f"new candidate {digest(result)}; no historical vectors reused")
        else:
            candidate = read_model(args.candidate, PinnedEncoderCandidate)
            if candidate.source_sha256 != manifest.source_sha256:
                raise ValueError("candidate belongs to another frozen source")
            if args.command == "encode":
                unit = encode_pinned_selected(
                    candidate,
                    articles,
                    TypeAdapter(list[str]).validate_json(args.ids.read_bytes()),
                    policy,
                    args.root,
                    args.output,
                )
                print(f"encoded {len(unit.article_ids)} new candidate rows; unit {digest(unit)}")
            else:
                state = register_candidate_unit(
                    args.root,
                    candidate,
                    articles,
                    read_model(args.unit, CandidateVectorUnit),
                    read_model(args.previous, CandidateVectorState) if args.previous else None,
                )
                print(f"candidate-only vector state {digest(state)}")
    except (ValueError, OSError) as error:
        parser.exit(2, f"refused: {error}\n")


if __name__ == "__main__":
    main()
