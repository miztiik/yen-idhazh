"""Download exact GGUF files and compare them with one local llama-bench build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
GGUF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$")


@dataclass(frozen=True, slots=True)
class ModelRef:
    repo: str
    file: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/main/{self.file}"


@dataclass(frozen=True, slots=True)
class RemoteFile:
    bytes: int
    sha256: str


def parse_model_refs(value: str) -> list[ModelRef]:
    refs: list[ModelRef] = []
    filenames: set[str] = set()
    for raw in value.split(","):
        if raw.count(":") != 1:
            raise ValueError(f"model reference must be repo:file: {raw}")
        repo, file = raw.split(":", maxsplit=1)
        if not REPO_RE.fullmatch(repo):
            raise ValueError(f"invalid Hugging Face repository: {repo}")
        if not GGUF_RE.fullmatch(file):
            raise ValueError(f"invalid GGUF filename: {file}")
        if file in filenames:
            raise ValueError(f"duplicate GGUF filename: {file}")
        filenames.add(file)
        refs.append(ModelRef(repo=repo, file=file))
    if not refs:
        raise ValueError("at least one model reference is required")
    return refs


def parse_positive_csv(value: str, *, name: str) -> list[int]:
    try:
        values = [int(part) for part in value.split(",")]
    except ValueError as error:
        raise ValueError(f"{name} must be comma-separated positive integers") from error
    if not values or any(number < 1 for number in values):
        raise ValueError(f"{name} must be comma-separated positive integers")
    return sorted(set(values))


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def find_llama_bench(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"llama-bench not found: {display_path(explicit)}")
        return explicit

    names = ("llama-bench.exe", "llama-bench") if os.name == "nt" else ("llama-bench",)
    candidates = [
        path for name in names for path in Path("backend/bin").rglob(name) if path.is_file()
    ]
    if len(candidates) != 1:
        found = ", ".join(path.as_posix() for path in candidates) or "none"
        raise FileNotFoundError(
            f"expected one llama-bench under backend/bin, found: {found}; use --binary"
        )
    return candidates[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def runtime_identity(binary: Path) -> str:
    # llama-bench has no version flag. Its JSON rows carry build_number and
    # build_commit; the executable hash ties those fields to the bytes invoked.
    return f"runtime={display_path(binary)} sha256={sha256(binary)}"


def remote_file_from_tree(ref: ModelRef, entries: list[dict[str, Any]]) -> RemoteFile:
    for entry in entries:
        if entry.get("path") != ref.file:
            continue
        lfs = entry.get("lfs")
        if not isinstance(lfs, dict):
            break
        oid = lfs.get("oid")
        size = lfs.get("size")
        if isinstance(oid, str) and re.fullmatch(r"[0-9a-f]{64}", oid) and isinstance(size, int):
            return RemoteFile(bytes=size, sha256=oid)
        break
    raise ValueError(f"Hugging Face returned no LFS identity for {ref.repo}:{ref.file}")


def resolve_remote_file(ref: ModelRef) -> RemoteFile:
    url = f"https://huggingface.co/api/models/{ref.repo}/tree/main"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Hugging Face returned an invalid tree for {ref.repo}")
    return remote_file_from_tree(ref, payload)


def download(ref: ModelRef, remote: RemoteFile, models_dir: Path) -> tuple[Path, float]:
    destination = models_dir / ref.file
    if destination.is_file():
        local_sha = sha256(destination)
        if destination.stat().st_size != remote.bytes or local_sha != remote.sha256:
            raise ValueError(
                f"existing file does not match {ref.repo}:{ref.file}; "
                f"delete {display_path(destination)} and retry"
            )
        return destination, 0.0

    curl = shutil.which("curl.exe" if os.name == "nt" else "curl")
    if curl is None:
        raise FileNotFoundError("curl is required to download GGUF files")

    models_dir.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(f"{destination.suffix}.part")
    started = time.monotonic()
    subprocess.run(
        [
            curl,
            "--fail",
            "--location",
            "--retry",
            "3",
            "--retry-all-errors",
            "--continue-at",
            "-",
            "--output",
            str(partial),
            ref.url,
        ],
        check=True,
    )
    partial.replace(destination)
    local_sha = sha256(destination)
    if destination.stat().st_size != remote.bytes or local_sha != remote.sha256:
        destination.unlink()
        raise ValueError(f"downloaded file failed identity check: {ref.repo}:{ref.file}")
    return destination, time.monotonic() - started


def _key_values(path: Path) -> dict[str, int | str]:
    if not path.is_file():
        return {}
    values: dict[str, int | str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, raw = line.partition(" ")
        values[key] = int(raw) if raw.isdigit() else raw
    return values


def resource_snapshot() -> dict[str, object]:
    root = Path("/sys/fs/cgroup")
    return {
        "cpu_stat": _key_values(root / "cpu.stat"),
        "cpu_pressure": _key_values(root / "cpu.pressure"),
        "memory_events": _key_values(root / "memory.events"),
        "memory_peak": (root / "memory.peak").read_text(encoding="utf-8").strip()
        if (root / "memory.peak").is_file()
        else None,
    }


def bench_command(
    *,
    binary: Path,
    model: Path,
    prompt_tokens: list[int],
    generation_tokens: int,
    threads: int,
    repeats: int,
) -> list[str]:
    return [
        str(binary),
        "-m",
        str(model),
        "-p",
        ",".join(str(value) for value in prompt_tokens),
        "-n",
        str(generation_tokens),
        "-t",
        str(threads),
        "-r",
        str(repeats),
        "-o",
        "json",
    ]


def run_benchmarks(
    *,
    binary: Path,
    models: list[Path],
    threads: list[int],
    prompt_tokens: list[int],
    generation_tokens: int,
    repeats: int,
    output: Path,
    resources_report: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    resources_report.parent.mkdir(parents=True, exist_ok=True)
    resources: list[dict[str, object]] = []
    with output.open("wb") as stream:
        for model in models:
            for thread_count in threads:
                print(
                    f"benchmark model={model.name} threads={thread_count}",
                    file=sys.stderr,
                    flush=True,
                )
                before = resource_snapshot()
                started = time.monotonic()
                result = subprocess.run(
                    bench_command(
                        binary=binary,
                        model=model,
                        prompt_tokens=prompt_tokens,
                        generation_tokens=generation_tokens,
                        threads=thread_count,
                        repeats=repeats,
                    ),
                    check=False,
                    stdout=subprocess.PIPE,
                )
                stream.write(result.stdout)
                stream.write(b"\n")
                resources.append(
                    {
                        "model": model.name,
                        "threads": thread_count,
                        "wall_seconds": time.monotonic() - started,
                        "returncode": result.returncode,
                        "before": before,
                        "after": resource_snapshot(),
                    }
                )
                resources_report.write_text(
                    json.dumps(resources, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode,
                        bench_command(
                            binary=binary,
                            model=model,
                            prompt_tokens=prompt_tokens,
                            generation_tokens=generation_tokens,
                            threads=thread_count,
                            repeats=repeats,
                        ),
                    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, help="Comma-separated repo:file references")
    parser.add_argument("--threads", default="4", help="Comma-separated worker counts")
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--models-dir", type=Path, default=Path("backend/models"))
    parser.add_argument("--output", type=Path, default=Path("backend/var/llm.json"))
    parser.add_argument("--weights-report", type=Path, default=Path("backend/var/weights.txt"))
    parser.add_argument("--resources-report", type=Path, default=Path("backend/var/resources.json"))
    parser.add_argument("--prompt-tokens", default="730,1800,4850")
    parser.add_argument("--generation-tokens", type=int, default=250)
    parser.add_argument("--repeats", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        refs = parse_model_refs(args.models)
        threads = parse_positive_csv(args.threads, name="threads")
        prompt_tokens = parse_positive_csv(args.prompt_tokens, name="prompt-tokens")
        if args.generation_tokens < 1:
            raise ValueError("generation-tokens must be positive")
        if args.repeats < 1:
            raise ValueError("repeats must be positive")
        binary = find_llama_bench(args.binary)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    models: list[Path] = []
    report = [runtime_identity(binary)]
    for ref in refs:
        remote = resolve_remote_file(ref)
        path, elapsed = download(ref, remote, args.models_dir)
        models.append(path)
        source = "local" if elapsed == 0.0 else f"download {elapsed:.1f}s"
        report.append(f"{ref.repo}:{ref.file} {source} bytes={remote.bytes} sha256={remote.sha256}")

    args.weights_report.parent.mkdir(parents=True, exist_ok=True)
    args.weights_report.write_text("\n".join(report) + "\n", encoding="utf-8")
    run_benchmarks(
        binary=binary,
        models=models,
        threads=threads,
        prompt_tokens=prompt_tokens,
        generation_tokens=args.generation_tokens,
        repeats=args.repeats,
        output=args.output,
        resources_report=args.resources_report,
    )
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("summarise_bench.py")), str(args.output)],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
