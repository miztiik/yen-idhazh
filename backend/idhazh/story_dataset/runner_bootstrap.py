"""Check approved installer bytes before installing any dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def check_bootstrap(root: Path, expected: str, repository: Path) -> None:
    raw = (root / "package.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("input package manifest differs from the approved hash")
    package = json.loads(raw)
    if package["code_commit"] != os.environ["GITHUB_SHA"]:
        raise ValueError("workflow code commit differs from the approved package")
    for items, base in ((package["files"], root), (package["code_files"], repository)):
        for item in items:
            name = PurePosixPath(item["path"])
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in item["path"]
                or ":" in item["path"]
            ):
                raise ValueError("unsafe package path")
            path = base / item["path"]
            with path.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            if checksum != item["sha256"] or path.stat().st_size != item["bytes"]:
                raise ValueError("package or code file hash differs")
    if package["runtime_lock"] not in package["files"]:
        raise ValueError("installer is not part of the approved package")
    if package["runtime_lock"]["path"] != "runtime-requirements.txt":
        raise ValueError("unrecognized runtime installer input")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    check_bootstrap(args.root, args.sha256, Path.cwd())
