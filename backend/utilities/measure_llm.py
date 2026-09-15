"""Bench one candidate model and emit the dossier page body its numbers fill.

Three verbs. `bench` downloads exact GGUF files and runs one local llama-bench
build over them. `emit` folds that case together with the server case's runtime
sweep and writes the model dossier's body, numbers already in place. `compare`
reads two emitted reading sets and says whether the second reproduces the first
inside the spread each one declares.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
GGUF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$")
# A full commit. A branch is re-pointed on every upload, so a benchmark that
# names one cannot be repeated: the bytes move and nothing says they did.
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ModelRef:
    repo: str
    revision: str
    file: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/{self.revision}/{self.file}"

    @property
    def tree_url(self) -> str:
        return f"https://huggingface.co/api/models/{self.repo}/tree/{self.revision}"

    def __str__(self) -> str:
        return f"{self.repo}@{self.revision}:{self.file}"


@dataclass(frozen=True, slots=True)
class RemoteFile:
    bytes: int
    sha256: str


def parse_model_refs(value: str) -> list[ModelRef]:
    refs: list[ModelRef] = []
    filenames: set[str] = set()
    for raw in value.split(","):
        if raw.count(":") != 1:
            raise ValueError(f"model reference must be repo@revision:file: {raw}")
        source, file = raw.split(":", maxsplit=1)
        if source.count("@") != 1:
            raise ValueError(f"model reference must be repo@revision:file: {raw}")
        repo, revision = source.split("@", maxsplit=1)
        if not REPO_RE.fullmatch(repo):
            raise ValueError(f"invalid Hugging Face repository: {repo}")
        if not REVISION_RE.fullmatch(revision):
            raise ValueError(f"revision must be a 40-character commit: {revision}")
        if not GGUF_RE.fullmatch(file):
            raise ValueError(f"invalid GGUF filename: {file}")
        if file in filenames:
            raise ValueError(f"duplicate GGUF filename: {file}")
        filenames.add(file)
        refs.append(ModelRef(repo=repo, revision=revision, file=file))
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
    raise ValueError(f"Hugging Face returned no LFS identity for {ref}")


def resolve_remote_file(ref: ModelRef) -> RemoteFile:
    with urllib.request.urlopen(ref.tree_url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Hugging Face returned an invalid tree for {ref}")
    return remote_file_from_tree(ref, payload)


def download(ref: ModelRef, remote: RemoteFile, models_dir: Path) -> tuple[Path, float]:
    destination = models_dir / ref.file
    if destination.is_file():
        local_sha = sha256(destination)
        if destination.stat().st_size != remote.bytes or local_sha != remote.sha256:
            raise ValueError(
                f"existing file does not match {ref}; "
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
        raise ValueError(f"downloaded file failed identity check: {ref}")
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
) -> list[dict[str, Any]]:
    """Run the bench and hand back the rows it printed.

    The rows are returned as well as written. The emitter needs the numbers in
    the same process that produced them: re-reading the file would mean a second
    parser for a format this function already holds parsed.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    resources_report.parent.mkdir(parents=True, exist_ok=True)
    resources: list[dict[str, object]] = []
    rows: list[dict[str, Any]] = []
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
                rows.extend(bench_rows(result.stdout))
    return rows


def bench_rows(stdout: bytes) -> list[dict[str, Any]]:
    """The rows of one `llama-bench -o json` invocation."""
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError("llama-bench did not print a JSON array")
    return [row for row in cast(list[object], payload) if isinstance(row, dict)]


# --- the page the bench fills -----------------------------------------------

#: The headings a bench reading may print under, in the order the model dossier
#: prints them. Closed-world: a reading that names anything else has no place on
#: the page, and a heading the committed dossier does not carry fails the test
#: that reads it. The rows INSIDE a section are open, because the prompt lengths
#: are a config value and a closed list of them would be a second spelling of
#: `--prompt-tokens` (Guardrail #6).
CACHE_SECTION: Final = "## On disk, and what it costs the cache"
THROUGHPUT_SECTION: Final = "## Prefill and decode"
MEMORY_SECTION: Final = "## Memory"
MODEL_LOAD_SECTION: Final = "### Model load time"
ITEM_SECTION: Final = "## Seconds an item"
DOSSIER_SECTIONS: Final = (
    CACHE_SECTION,
    THROUGHPUT_SECTION,
    MEMORY_SECTION,
    MODEL_LOAD_SECTION,
    ITEM_SECTION,
)

#: What the Identity table says, and the order it says it in. Every one of these
#: must arrive; the emitter refuses to render a page with a blank in it rather
#: than print a row a reader would have to go and fill in by hand.
IDENTITY_FIELDS: Final = (
    ("id", "Configuration id"),
    ("repo", "Repository"),
    ("revision", "Repository revision"),
    ("file", "File"),
    ("quantisation", "Quantisation"),
    ("sha256", "SHA-256"),
    ("bytes", "Bytes"),
)
#: What every number on the page was measured against. A reading with no
#: hardware and no date is not a measurement (Guardrail #10), so these are
#: required exactly as hard as the identity is.
CONTEXT_FIELDS: Final = (
    "measured_at",
    "runner",
    "cpu",
    "threads",
    "llama_build",
    "llama_commit",
    "bench_repeats",
    "server_repeats",
    "corpus",
)

GIB: Final = 1024.0**3


@dataclass(frozen=True, slots=True)
class Reading:
    """One measured quantity: what it read, how far it moved, and over how many runs.

    `repeats` of 1 means the spread is unavailable rather than zero, and the
    comparison refuses to judge such a reading instead of holding it to an
    exact match.
    """

    section: str
    label: str
    value: float
    spread: float
    unit: str
    repeats: int

    def as_json(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "label": self.label,
            "value": self.value,
            "spread": self.spread,
            "unit": self.unit,
            "repeats": self.repeats,
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> Reading:
        return cls(
            section=str(payload["section"]),
            label=str(payload["label"]),
            value=float(payload["value"]),
            spread=float(payload["spread"]),
            unit=str(payload["unit"]),
            repeats=int(payload["repeats"]),
        )


@dataclass(frozen=True, slots=True)
class BenchReadings:
    """Everything one dispatch of the bench learned about one candidate."""

    identity: dict[str, str]
    context: dict[str, str]
    readings: dict[str, Reading]

    def merge(self, other: BenchReadings) -> BenchReadings:
        clash = set(self.readings) & set(other.readings)
        if clash:
            raise ValueError(f"two cases read the same quantity: {', '.join(sorted(clash))}")
        return BenchReadings(
            identity={**self.identity, **other.identity},
            context={**self.context, **other.context},
            readings={**self.readings, **other.readings},
        )

    def as_json(self) -> dict[str, Any]:
        # Identity and context are a lookup and are sorted. The readings are not:
        # their order is the order the page prints them in, prefill before
        # decode and median before longest, and sorting by key would shuffle
        # that into alphabetical nonsense on the way through the artifact.
        return {
            "identity": dict(sorted(self.identity.items())),
            "context": dict(sorted(self.context.items())),
            "readings": {name: reading.as_json() for name, reading in self.readings.items()},
        }

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> BenchReadings:
        readings = payload.get("readings") or {}
        if not isinstance(readings, dict):
            raise ValueError("readings must be a mapping of name to reading")
        return cls(
            identity={str(k): str(v) for k, v in dict(payload.get("identity") or {}).items()},
            context={str(k): str(v) for k, v in dict(payload.get("context") or {}).items()},
            readings={
                str(name): Reading.from_json(value)
                for name, value in cast(dict[str, Any], readings).items()
            },
        )

    @classmethod
    def read(cls, path: Path) -> BenchReadings:
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.as_json(), indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def format_number(value: float) -> str:
    """Two decimals at most, thousands grouped, and no trailing zero to read past.

    A quantity smaller than the second decimal keeps two significant figures
    instead. Printing a spread of 0.002 as `0` would claim a run repeated
    exactly, which is a precision nobody measured (Guardrail #10).
    """
    if value and abs(value) < 0.01:
        return f"{value:.2g}"
    text = f"{value:,.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _one_row(
    rows: Sequence[Mapping[str, Any]], *, prompt: int, generation: int
) -> Mapping[str, Any]:
    matches = [
        row
        for row in rows
        if int(row.get("n_prompt", 0)) == prompt and int(row.get("n_gen", 0)) == generation
    ]
    if len(matches) != 1:
        raise ValueError(
            f"llama-bench printed {len(matches)} rows for n_prompt={prompt} "
            f"n_gen={generation}, and a reading needs exactly one"
        )
    return matches[0]


def _bench_repeats(row: Mapping[str, Any], *, requested: int) -> int:
    samples = row.get("samples_ts")
    if isinstance(samples, list) and samples:
        return len(cast(list[object], samples))
    return requested


def raw_readings(
    rows: Sequence[Mapping[str, Any]],
    *,
    prompt_tokens: Sequence[int],
    generation_tokens: int,
    threads: int,
    repeats: int,
) -> dict[str, Reading]:
    """Prefill and decode, straight off the bench rows.

    Prefill is read at every length asked for rather than at one, because
    attention is quadratic and a single tokens-per-second constant is wrong in
    both directions at once.
    """
    wanted = [row for row in rows if int(row.get("n_threads", 0)) == threads]
    if not wanted:
        raise ValueError(f"llama-bench printed no rows at {threads} threads")
    readings: dict[str, Reading] = {}
    for count in prompt_tokens:
        row = _one_row(wanted, prompt=count, generation=0)
        readings[f"prefill_{count}"] = Reading(
            section=THROUGHPUT_SECTION,
            label=f"Prefill, {count:,}-token prompt",
            value=float(row["avg_ts"]),
            spread=float(row.get("stddev_ts", 0.0)),
            unit="tok/s",
            repeats=_bench_repeats(row, requested=repeats),
        )
    decode = _one_row(wanted, prompt=0, generation=generation_tokens)
    readings[f"decode_{generation_tokens}"] = Reading(
        section=THROUGHPUT_SECTION,
        label=f"Decode, {generation_tokens:,} tokens",
        value=float(decode["avg_ts"]),
        spread=float(decode.get("stddev_ts", 0.0)),
        unit="tok/s",
        repeats=_bench_repeats(decode, requested=repeats),
    )
    return readings


def _kilobytes(value: object) -> float:
    """`/proc/<pid>/status` prints `14051836 kB`; take the number."""
    head = str(value).split()[0]
    return float(head)


def _spread_reading(
    section: str,
    label: str,
    values: Sequence[float],
    *,
    unit: str,
    scale: float = 1.0,
) -> Reading:
    scaled = [value * scale for value in values]
    return Reading(
        section=section,
        label=label,
        value=statistics.median(scaled),
        spread=max(scaled) - min(scaled),
        unit=unit,
        repeats=len(scaled),
    )


def _peak_server_rss_gib(run: Mapping[str, Any]) -> float:
    samples = run.get("server_rss_samples") or []
    peaks = [
        _kilobytes(sample["VmHWM"])
        for sample in cast(list[Any], samples)
        if isinstance(sample, dict) and "VmHWM" in sample
    ]
    if not peaks:
        raise ValueError(f"repeat {run.get('repeat')} sampled no resident set at all")
    return max(peaks) * 1024.0 / GIB


def server_readings(summary: Mapping[str, Any], *, label: str = "baseline") -> dict[str, Reading]:
    """Model load, resident set and seconds an item, from the runtime sweep.

    The cold and warm halves of the model load are the first repeat and the
    ones after it. Nothing in the job had read those weights before the first
    server start, so the first start faults every page in off disk and the
    later ones do not - which is exactly the shape of the first run after a
    model swap, on every shard at once.
    """
    results = summary.get("results") or []
    runs = sorted(
        (
            run
            for run in cast(list[Any], results)
            if isinstance(run, dict) and run.get("label") == label
        ),
        key=lambda run: int(run["repeat"]),
    )
    if len(runs) < 2:
        raise ValueError(
            f"the server case ran {len(runs)} repeat(s) of {label!r}; under two, "
            "a cold start cannot be told from a warm one"
        )

    readings: dict[str, Reading] = {
        "model_load_cold": Reading(
            section=MODEL_LOAD_SECTION,
            label="Cold, the first start of the job",
            value=float(runs[0]["startup_ms"]),
            spread=0.0,
            unit="ms",
            repeats=1,
        ),
        "model_load_warm": _spread_reading(
            MODEL_LOAD_SECTION,
            "Warm, every start after it",
            [float(run["startup_ms"]) for run in runs[1:]],
            unit="ms",
        ),
        "server_rss_peak": _spread_reading(
            MEMORY_SECTION,
            "Peak resident set, llama-server alone",
            [_peak_server_rss_gib(run) for run in runs],
            unit="GiB",
        ),
        "summarize_median": _spread_reading(
            ITEM_SECTION,
            "A summarize call, median",
            [
                statistics.median(float(item["summarize_ms"]) for item in run["per_item"])
                for run in runs
            ],
            unit="s",
            scale=1 / 1000,
        ),
        "summarize_longest": _spread_reading(
            ITEM_SECTION,
            "A summarize call, longest",
            [max(float(item["summarize_ms"]) for item in run["per_item"]) for run in runs],
            unit="s",
            scale=1 / 1000,
        ),
    }

    peaks = [run.get("cgroup_memory_peak_bytes") for run in runs]
    if all(peak is not None for peak in peaks):
        readings["tree_rss_peak"] = _spread_reading(
            MEMORY_SECTION,
            "Peak resident set, the whole job",
            [float(str(peak)) for peak in peaks],
            unit="GiB",
            scale=1 / GIB,
        )
    return readings


def _table(header: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _reading_row(reading: Reading) -> tuple[str, str, str]:
    value = f"**{format_number(reading.value)}"
    if reading.repeats > 1:
        value += f" +/- {format_number(reading.spread)}"
    value += f"** {reading.unit}"
    runs = f"n = {reading.repeats}" if reading.repeats > 1 else "n = 1, spread unavailable"
    return (reading.label, value, runs)


def render_dossier(readings: BenchReadings) -> str:
    """The dossier body, numbers already in it, ready to paste.

    Every value on the page came in through `readings`. Nothing here supplies a
    default for a missing one: a page that invented a number would be worse than
    a page that refused to render.
    """
    missing = [name for name, _ in IDENTITY_FIELDS if not readings.identity.get(name)]
    missing += [name for name in CONTEXT_FIELDS if not readings.context.get(name)]
    if missing:
        raise ValueError(f"the bench did not record: {', '.join(sorted(set(missing)))}")
    unplaceable = sorted(
        {
            reading.section
            for reading in readings.readings.values()
            if reading.section not in DOSSIER_SECTIONS
        }
    )
    if unplaceable:
        raise ValueError(f"no dossier heading holds: {', '.join(unplaceable)}")
    if not readings.readings:
        raise ValueError("the bench recorded no readings at all")

    context = readings.context
    day = context["measured_at"][:10]
    lines: list[str] = [
        f"# {readings.identity['id']}",
        "",
        f"**Last Updated**: {day}",
        "",
        "**Status: measured, not adopted.** Every number below was read by one "
        f"dispatch of the bench on {day}. Nothing here says the model is good enough "
        "to publish with - that is the qualification case, and it runs separately.",
        "",
        "## Identity",
        "",
    ]
    lines.extend(
        _table(
            ("Field", "Value"),
            ((title, readings.identity[name]) for name, title in IDENTITY_FIELDS),
        )
    )

    provenance = {
        CACHE_SECTION: (
            f"Read on {day} on {context['runner']}, {context['cpu']}. A cache miss is "
            "what the first run after a swap draws, on every shard at once."
        ),
        THROUGHPUT_SECTION: (
            f"Measured {day} on {context['cpu']}, {context['threads']} threads, "
            f"llama.cpp {context['llama_build']} ({context['llama_commit']}), "
            f"{context['bench_repeats']} repeats, `llama-bench`. Prefill falls as the "
            "prompt grows, so one tokens-per-second figure would be wrong at both ends."
        ),
        MEMORY_SECTION: (
            f"Sampled once a second across {context['server_repeats']} repeats on "
            f"{context['runner']}, against the 16 GB the runner has. What this does NOT "
            "split is anonymous from file-backed pages, so it cannot say how much of the "
            "peak a second process would have to compete for. `Rss_Anon` and `Rss_File` "
            "from `/proc/<pid>/smaps_rollup`, sampled by the same thread, would settle "
            "that; they are unmeasured today."
        ),
        MODEL_LOAD_SECTION: (
            "Cold is the first server start of the job, with the page cache holding none "
            "of the weights. Warm is every start after it."
        ),
        ITEM_SECTION: (
            f"{context['corpus']}, {context['server_repeats']} repeats, on "
            f"{context['runner']}. There is no 95th percentile here: five articles cannot "
            "carry one. The published ledger over a real day is what gives that number."
        ),
    }

    for section in DOSSIER_SECTIONS:
        placed = [reading for reading in readings.readings.values() if reading.section == section]
        if not placed:
            continue
        lines.extend(["", section, "", provenance[section], ""])
        lines.extend(_table(("Reading", "Value", "Runs"), (_reading_row(r) for r in placed)))

    lines.extend(
        [
            "",
            "## What this page still owes",
            "",
            "The bench reads throughput, memory and wall-clock. It does not grade a "
            "summary and it does not decide whether this model publishes. Paste the "
            "qualification verdict and the licence row in from the validation case "
            "before this page stands for an adopted model.",
            "",
        ]
    )
    return "\n".join(lines)


def within_spread(name: str, observed: Reading, declared: Reading) -> str | None:
    """Does one reading reproduce another? `None` when it does, the reason when not.

    The tolerance is the two spreads added rather than either one alone: a run
    that lands inside its own noise and inside the page's noise has not
    disagreed with the page.
    """
    if observed.unit != declared.unit:
        return (
            f"{name}: the bench read {format_number(observed.value)} {observed.unit} and "
            f"the page declares {format_number(declared.value)} {declared.unit}; "
            "two units are not one reading"
        )
    tolerance = observed.spread + declared.spread
    gap = abs(observed.value - declared.value)
    if gap <= tolerance:
        return None
    return (
        f"{name}: the bench read {format_number(observed.value)} +/- "
        f"{format_number(observed.spread)} {observed.unit} and the page declares "
        f"{format_number(declared.value)} +/- {format_number(declared.spread)} "
        f"{declared.unit}; they are {format_number(gap)} {observed.unit} apart and the "
        f"two spreads allow {format_number(tolerance)}"
    )


def compare_readings(
    observed: BenchReadings, declared: BenchReadings
) -> tuple[list[str], list[str]]:
    """Every quantity both sides read, judged. Returns the failures and the abstentions.

    A reading taken once carries no spread, so it is reported rather than
    judged. Holding it to an exact match would fail on noise nobody measured.
    """
    failures: list[str] = []
    abstained: list[str] = []
    for name in sorted(set(observed.readings) | set(declared.readings)):
        left = observed.readings.get(name)
        right = declared.readings.get(name)
        if left is None:
            failures.append(f"{name}: the page declares it and the bench did not read it")
            continue
        if right is None:
            failures.append(f"{name}: the bench read it and the page declares nothing")
            continue
        if left.repeats < 2 or right.repeats < 2:
            abstained.append(
                f"{name}: {format_number(left.value)} {left.unit} against "
                f"{format_number(right.value)} {right.unit}, not judged because a "
                "reading taken once has no spread"
            )
            continue
        problem = within_spread(name, left, right)
        if problem is not None:
            failures.append(problem)
    return failures, abstained


def check_declared_digest(ref: ModelRef, remote: RemoteFile, expected: str) -> str | None:
    """Do the bytes the Hub holds match the digest the dispatch declared?

    `download` already checks what arrived against what the Hub advertised. This
    checks what the Hub advertises against what the operator asked for, which is
    the half that catches a repinned reference: a benchmark filed under a model
    that never ran is worse than no benchmark (Guardrail #10).
    """
    if remote.sha256 == expected:
        return None
    return f"{ref} is {remote.sha256} on the Hub and the dispatch declares {expected}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)

    bench = verbs.add_parser("bench", help="Download one candidate and run llama-bench over it")
    bench.add_argument(
        "--models", required=True, help="Comma-separated repo@revision:file references"
    )
    bench.add_argument("--threads", default="4", help="Comma-separated worker counts")
    bench.add_argument("--binary", type=Path)
    bench.add_argument("--models-dir", type=Path, default=Path("backend/models"))
    bench.add_argument("--output", type=Path, default=Path("backend/var/llm.json"))
    bench.add_argument("--weights-report", type=Path, default=Path("backend/var/weights.txt"))
    bench.add_argument("--resources-report", type=Path, default=Path("backend/var/resources.json"))
    bench.add_argument("--prompt-tokens", default="730,1800,4850")
    bench.add_argument("--generation-tokens", type=int, default=250)
    bench.add_argument("--repeats", type=int, default=3)
    # Without this the harness downloads whatever the repository holds today and
    # says nothing. The digest is what makes the rest of the page about a
    # specific set of bytes (Guardrail #10).
    bench.add_argument(
        "--expect-sha256",
        default="",
        help="Refuse any bytes but these. Required with a single model reference.",
    )
    bench.add_argument("--candidate-id", default="", help="The config id these weights serve as")
    bench.add_argument("--quantisation", default="", help="The quantisation these bytes carry")
    bench.add_argument("--readings", type=Path, default=Path("backend/var/bench/raw-case.json"))

    emit = verbs.add_parser("emit", help="Write the dossier body the two cases fill")
    emit.add_argument("--raw", type=Path, required=True, help="The raw case's readings")
    emit.add_argument(
        "--server", type=Path, required=True, help="The server case's runtime summary"
    )
    emit.add_argument("--corpus", default="Five articles", help="What the server case replayed")
    emit.add_argument("--dossier", type=Path, default=Path("backend/var/bench/dossier.md"))
    emit.add_argument("--readings", type=Path, default=Path("backend/var/bench/readings.json"))

    compare = verbs.add_parser("compare", help="Judge one reading set against another")
    compare.add_argument("--observed", type=Path, required=True)
    compare.add_argument("--declared", type=Path, required=True)

    return parser.parse_args()


def run_bench(args: argparse.Namespace) -> int:
    try:
        refs = parse_model_refs(args.models)
        threads = parse_positive_csv(args.threads, name="threads")
        prompt_tokens = parse_positive_csv(args.prompt_tokens, name="prompt-tokens")
        if args.generation_tokens < 1:
            raise ValueError("generation-tokens must be positive")
        if args.repeats < 1:
            raise ValueError("repeats must be positive")
        expected = args.expect_sha256.strip().lower()
        if expected and not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"expect-sha256 must be a sha256 digest: {args.expect_sha256}")
        if len(refs) == 1 and not expected:
            raise ValueError("one candidate needs --expect-sha256; nothing else names its bytes")
        binary = find_llama_bench(args.binary)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    models: list[Path] = []
    fetch_seconds: float | None = None
    args.weights_report.parent.mkdir(parents=True, exist_ok=True)
    args.weights_report.write_text(runtime_identity(binary) + "\n", encoding="utf-8", newline="\n")
    remotes: list[RemoteFile] = []
    for ref in refs:
        remote = resolve_remote_file(ref)
        if expected and len(refs) == 1:
            problem = check_declared_digest(ref, remote, expected)
            if problem is not None:
                print(problem, file=sys.stderr)
                return 2
        path, elapsed = download(ref, remote, args.models_dir)
        models.append(path)
        remotes.append(remote)
        if len(refs) == 1 and elapsed > 0.0:
            fetch_seconds = elapsed
        source = "local" if elapsed == 0.0 else f"download {elapsed:.1f}s"
        with args.weights_report.open("a", encoding="utf-8", newline="\n") as report:
            report.write(f"{ref} {source} bytes={remote.bytes} sha256={remote.sha256}\n")

    rows = run_benchmarks(
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
    if len(refs) == 1:
        _write_raw_case(
            args,
            ref=refs[0],
            remote=remotes[0],
            rows=rows,
            threads=threads[0],
            prompt_tokens=prompt_tokens,
            fetch_seconds=fetch_seconds,
        )
    return 0


def _write_raw_case(
    args: argparse.Namespace,
    *,
    ref: ModelRef,
    remote: RemoteFile,
    rows: Sequence[Mapping[str, Any]],
    threads: int,
    prompt_tokens: Sequence[int],
    fetch_seconds: float | None,
) -> None:
    readings = raw_readings(
        rows,
        prompt_tokens=prompt_tokens,
        generation_tokens=args.generation_tokens,
        threads=threads,
        repeats=args.repeats,
    )
    if fetch_seconds is not None:
        readings["weights_fetch_cold"] = Reading(
            section=CACHE_SECTION,
            label=f"First download, cache miss, {format_number(remote.bytes / GIB)} GiB",
            value=fetch_seconds,
            spread=0.0,
            unit="s",
            repeats=1,
        )
    head = dict(rows[0]) if rows else {}
    BenchReadings(
        identity={
            "id": args.candidate_id or ref.file,
            "repo": ref.repo,
            "revision": ref.revision,
            "file": ref.file,
            "quantisation": args.quantisation or "unstated",
            "sha256": remote.sha256,
            "bytes": f"{remote.bytes:,}",
        },
        context={
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runner": "ubuntu-latest",
            "cpu": str(head.get("cpu_info") or "unrecorded"),
            "threads": str(threads),
            "llama_build": f"b{head.get('build_number')}",
            "llama_commit": str(head.get("build_commit") or "unrecorded"),
            "bench_repeats": str(args.repeats),
        },
        readings=readings,
    ).write(args.readings)


def run_emit(args: argparse.Namespace) -> int:
    raw = BenchReadings.read(args.raw)
    summary = json.loads(args.server.read_text(encoding="utf-8"))
    server = BenchReadings(
        identity={},
        # What the timing was taken over, which is not always what was asked
        # for. The bench refetches every repeat, and a repeat whose article a
        # publisher edited mid-job is dropped from the median rather than
        # failing the run - so the page says the number it was really given
        # (CLAUDE.md Guardrail #10).
        context={
            "server_repeats": str(summary.get("repeats_timed") or summary.get("repeats") or ""),
            "corpus": args.corpus,
        },
        readings=server_readings(summary),
    )
    merged = raw.merge(server)
    merged.write(args.readings)
    args.dossier.parent.mkdir(parents=True, exist_ok=True)
    args.dossier.write_text(render_dossier(merged), encoding="utf-8", newline="\n")
    print(f"wrote {display_path(args.dossier)} and {display_path(args.readings)}")
    return 0


def run_compare(args: argparse.Namespace) -> int:
    failures, abstained = compare_readings(
        BenchReadings.read(args.observed), BenchReadings.read(args.declared)
    )
    for line in abstained:
        print(line)
    for line in failures:
        print(line, file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    args = parse_args()
    if args.verb == "emit":
        return run_emit(args)
    if args.verb == "compare":
        return run_compare(args)
    return run_bench(args)


if __name__ == "__main__":
    raise SystemExit(main())
