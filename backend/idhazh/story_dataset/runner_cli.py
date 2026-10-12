"""Route exact runner preparation, artifact download, validation, import and derivation."""

import argparse
import json
import subprocess
from pathlib import Path

from pydantic import TypeAdapter

from idhazh.contracts.story_encoder_candidate import CandidateVectorState, PinnedEncoderCandidate
from idhazh.contracts.story_runner import RunnerFile, RunnerPackage, RunnerResult, RunnerShard
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.runner_download import download_artifact
from idhazh.story_dataset.runner_inputs import (
    finish_package,
    prepare_shards,
    validate_package,
)
from idhazh.story_dataset.runner_results import import_result, recover_result, validate_result
from idhazh.story_dataset.source import load_policy, validate_freeze
from idhazh.story_dataset.storage import digest, read_model
from idhazh.story_dataset.vector_derivation import derive_gemma


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("--source-root", type=Path, required=True)
    preparation.add_argument("--vectors", type=Path, required=True)
    preparation.add_argument("--vector-root", type=Path, required=True)
    preparation.add_argument("--candidate", type=Path, required=True)
    preparation.add_argument("--state", type=Path, required=True)
    preparation.add_argument("--candidate-root", type=Path, required=True)
    preparation.add_argument("--requirements", type=Path, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    preparation.add_argument("--config", type=Path, default=Path("config/story-runner.json"))
    for command in ("validate", "matrix", "run", "import", "recover"):
        stage = commands.add_parser(command)
        stage.add_argument("--package-root", type=Path, required=True)
        stage.add_argument("--shard")
        if command in ("validate", "import", "recover"):
            stage.add_argument("--result", type=Path)
        if command == "run":
            stage.add_argument("--output", type=Path, required=True)
            stage.add_argument("--soft-stop-minutes", type=int, default=300)
        if command == "import":
            stage.add_argument("--source-root", type=Path, required=True)
            stage.add_argument("--root", type=Path, required=True)
            stage.add_argument("--state-pointer", type=Path)
    downloading = commands.add_parser("download")
    downloading.add_argument("--recipient", required=True)
    downloading.add_argument("--artifact-id", required=True)
    downloading.add_argument("--name", required=True)
    downloading.add_argument("--sha256")
    downloading.add_argument("--output", type=Path, required=True)
    derivation = commands.add_parser("derive")
    derivation.add_argument("--vectors", type=Path, required=True)
    derivation.add_argument("--root", type=Path, required=True)
    derivation.add_argument("--output-root", type=Path, required=True)
    derivation.add_argument("--dimensions", type=int, choices=(128, 256, 512), required=True)
    args = parser.parse_args()
    try:
        if args.command == "download":
            print(
                download_artifact(
                    args.recipient, args.artifact_id, args.name, args.output, args.sha256
                )
            )
        elif args.command == "derive":
            derived_result = derive_gemma(
                read_model(args.vectors, VectorSnapshot),
                args.root,
                args.output_root,
                "embeddinggemma-two",
                args.dimensions,
            )
            print(            f"derived {derived_result.derivation.slug}; "
            f"snapshot {digest(derived_result)}; no inference")
        elif args.command == "prepare":
            config = json.loads(args.config.read_bytes())
            policy = load_policy(args.repository / "config/story-dataset.json")
            source, articles = validate_freeze(args.source_root, args.repository, policy)
            shards = prepare_shards(
                source,
                articles,
                policy,
                read_model(args.vectors, VectorSnapshot),
                args.vector_root,
                read_model(args.candidate, PinnedEncoderCandidate),
                read_model(args.state, CandidateVectorState),
                args.candidate_root,
                args.output,
                config["shard_rows"],
                TypeAdapter(dict[str, list[RunnerFile]]).validate_python(config["model_files"]),
            )
            commit = subprocess.check_output(
                ["git", "-C", str(args.repository), "rev-parse", "HEAD"], text=True
            ).strip()
            package = finish_package(
                args.output,
                shards,
                args.repository,
                commit,
                config["code_files"],
                args.requirements,
            )
            print(
                f"prepared {len(shards)} shards; package {digest(package)}; no permission to send"
            )
        else:
            package = read_model(args.package_root / "package.json", RunnerPackage)
            validate_package(package, args.package_root, args.repository)
            if args.command == "matrix":
                names = [args.shard] if args.shard else list(package.shards)
                if any(name not in package.shards for name in names):
                    raise ValueError("selected shard is not part of this exact package")
                print(json.dumps(names))
            elif args.command == "validate" and not args.result:
                print(f"validated package {digest(package)}")
            else:
                if args.shard not in package.shards:
                    raise ValueError("select an exact package shard")
                shard = read_model(args.package_root / package.shards[args.shard], RunnerShard)
                if args.command == "run":
                    from idhazh.story_dataset.runner_execution import run_shard

                    result = run_shard(
                        package,
                        args.package_root,
                        args.repository,
                        shard,
                        args.output,
                        args.soft_stop_minutes,
                    )
                    print(f"{result.state}; {len(result.pending_article_ids)} inputs still missing")
                    if result.error:
                        parser.exit(1, result.error + "\n")
                else:
                    if args.result is None:
                        raise ValueError("select a downloaded result directory")
                    if args.command == "recover":
                        result = recover_result(shard, package, args.result)
                        print(f"recovered {len(result.units)} complete units without inference")
                        return
                    result = read_model(args.result / "result.json", RunnerResult)
                    if args.command == "validate":
                        validate_result(result, shard, package, args.result)
                        print("validated complete native units and exact pending inputs")
                    else:
                        if args.root.resolve() == args.source_root.resolve():
                            raise ValueError(
                                "runner import must use an integration-owned vector index"
                            )
                        policy = load_policy(args.repository / "config/story-dataset.json")
                        _, articles = validate_freeze(args.source_root, args.repository, policy)
                        registered = import_result(
                            result,
                            shard,
                            package,
                            args.result,
                            args.root,
                            articles,
                            args.state_pointer,
                        )
                        print(f"registered current vector head {digest(registered)}")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"refused: {error}\n")


if __name__ == "__main__":
    main()
