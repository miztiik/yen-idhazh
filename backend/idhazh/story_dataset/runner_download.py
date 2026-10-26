"""Download one explicitly named repository artifact with GitHub's archive checksum."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from idhazh.story_dataset.runner_archive import extract_archive


def download_release_asset(
    repository: str, identity: str, checksum: str, output: Path
) -> str:
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        or not identity.isdecimal()
        or not re.fullmatch(r"[0-9a-f]{64}", checksum)
    ):
        raise ValueError("input requires an exact repository, numeric asset ID and archive hash")
    endpoint = f"repos/{repository}/releases/assets/{identity}"
    asset = json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))
    if (
        asset.get("state") != "uploaded"
        or not 0 < asset.get("size", 0) <= 64 * 1024 * 1024
    ):
        raise ValueError("input release asset is unavailable or too large")
    archive = output.with_suffix(".zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as target:
        subprocess.run(
            ["gh", "api", endpoint, "-H", "Accept: application/octet-stream"],
            stdout=target, check=True,
        )
    if archive.stat().st_size != asset["size"]:
        raise ValueError("downloaded input asset size differs")
    extract_archive(archive, checksum, output)
    return checksum


def download_artifact(
    repository: str,
    identity: str,
    expected_name: str,
    output: Path,
    expected_digest: str | None = None,
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("recipient must be an exact account/repository name")
    if not identity.isdecimal():
        raise ValueError("artifact identity must be numeric")
    endpoint = f"repos/{repository}/actions/artifacts/{identity}"
    artifact = json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))
    checksum = str(artifact.get("digest", "")).removeprefix("sha256:")
    if (
        artifact.get("name") != expected_name
        or artifact.get("expired") is not False
        or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        or (expected_digest is not None and checksum != expected_digest)
        or artifact.get("size_in_bytes", 0) > 64 * 1024 * 1024
    ):
        raise ValueError("artifact name, availability, archive hash or size differs")
    archive = output.with_suffix(".zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as target:
        subprocess.run(["gh", "api", endpoint + "/zip"], stdout=target, check=True)
    extract_archive(archive, checksum, output)
    return checksum


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", required=True)
    acquisition = parser.add_mutually_exclusive_group(required=True)
    acquisition.add_argument("--artifact-id")
    acquisition.add_argument("--asset-id")
    parser.add_argument("--name")
    parser.add_argument("--sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.asset_id:
        if not args.sha256:
            parser.error("release asset acquisition requires the approved archive SHA-256")
        print(download_release_asset(args.recipient, args.asset_id, args.sha256, args.output))
    else:
        if not args.name:
            parser.error("artifact acquisition requires the expected artifact name")
        print(download_artifact(args.recipient, args.artifact_id, args.name, args.output,
                                args.sha256))
