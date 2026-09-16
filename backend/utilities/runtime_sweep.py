"""How long does one candidate take over a fixed five-article corpus?

Shells `python -m idhazh work`, so what it times is production's own path.
Which repeats may be compared is a separate question, in `sweep_verdict.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple

from idhazh import config
from idhazh.contracts.knobs.models import ModelsConfig
from idhazh.contracts.run_plan import RunPlan
from idhazh.llm.server import server_argv
from idhazh.telemetry import silicon
from utilities import sweep_verdict

ROOT = Path("backend/var/runtime-sweep")
CONFIG_ROOT = ROOT / "configs"
CANDIDATE_CONFIG = Path("backend/var/candidate-config")
RUN_ROOT = Path("backend/var/run")
SERVER_BINARY = Path("backend/bin/llama-server")
WEIGHTS_DIR = Path("backend/models")

#: Five, because the corpus is fixed and a repeat that wrote four measured
#: something else. It is asserted rather than assumed at both ends.
CORPUS_ITEMS = 5

#: What each named candidate changes about the server it starts. Every value is
#: an `inference` knob except `draft`, which is a sibling of `inference` and is
#: lifted one level up by `write_config`.
CANDIDATE_UPDATES: dict[str, tuple[dict[str, Any], int]] = {
    "baseline": ({}, 1),
    "np1": ({"n_parallel": 1}, 1),
    "batch2048": ({"n_batch": 2048}, 1),
    "no_startup_warmup": ({"startup_warmup": False}, 1),
    "flash_attention_on": ({"flash_attention": "on"}, 1),
    "load_mode_mmap_mlock": ({"load_mode": "mmap+mlock"}, 1),
    "kv_q8": ({"cache_type_k": "q8_0", "cache_type_v": "q8_0"}, 1),
    "prio_poll": ({"priority": 2, "poll": 100}, 1),
    "np2_inflight": ({"n_parallel": 2, "n_ctx": 16384}, 2),
    # The one candidate that reaches outside `inference`. A model file declaring
    # no draft head answers the question it exists for: what the head is worth,
    # measured on ONE machine instead of across two dispatches.
    "no_draft": ({"draft": None}, 1),
}

#: Two knobs whose value an operator types, so each is bounded where it is read.
SIZED_BY_DISPATCH = ("threads", "threads_batch")

#: The port every workflow that stands a llama-server up declares once at
#: workflow level. Read back rather than passed as an argument, because an
#: argument named `--port` is a second spelling of a llama-server flag and the
#: whole rule is that the flag list has one spelling.
PORT_ENV = "LLAMA_PORT"


def candidate_update(name: str, *, threads: int, threads_batch: int) -> tuple[dict[str, Any], int]:
    """What this candidate changes, and how many workers it runs."""
    if name == "threads":
        return {"n_threads": threads}, 1
    if name == "threads_batch":
        return {"n_threads_batch": threads_batch}, 1
    if name not in CANDIDATE_UPDATES:
        raise SystemExit(f"unknown runtime candidate: {name}")
    update, workers = CANDIDATE_UPDATES[name]
    return dict(update), workers


def write_config(label: str, update: dict[str, Any]) -> Path:
    """A scratch config for one case, from the candidate copy and never from `config/`.

    The committed config still names the incumbent, so a sweep that copied it
    would measure the wrong weights under the candidate's name.
    """
    dst = CONFIG_ROOT / label
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(CANDIDATE_CONFIG, dst)
    pointer = json.loads((dst / "idhazh.json").read_text(encoding="utf-8"))["models_file"]
    path = dst / pointer
    payload = json.loads(path.read_text(encoding="utf-8"))
    inference = dict(update)
    # Written through `update` rather than indexed, because an entry declaring
    # no draft head has no such key and this is the one line allowed to make one.
    if "draft" in inference:
        payload["summarize"].update({"draft": inference.pop("draft")})
    payload["summarize"]["inference"].update(inference)
    path.write_text(ModelsConfig.model_validate(payload).to_json(), encoding="utf-8")
    return dst


def read_status(pid: int) -> dict[str, str]:
    """The server's resident set, as the kernel reports it this second."""
    status = Path("/proc") / str(pid) / "status"
    values: dict[str, str] = {}
    if not status.exists():
        return values
    for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value = line.split(":", 1)
            values[key] = value.strip()
    return values


def cgroup_peak() -> str | None:
    path = Path("/sys/fs/cgroup/memory.peak")
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def parse_server_facts(log_path: Path) -> dict[str, str]:
    """What the server said it was doing, read back out of its own log."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    facts = {}
    for key in ("n_slots", "n_ctx_slot", "n_ctx_per_seq", "kv_unified"):
        match = re.search(rf"{key}\s*=\s*'?([^,\s']+)'?", text)
        if match:
            facts[key] = match.group(1)
    return facts


def wait_for_health(port: int) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status < 500:
                    return
        except OSError:
            pass
        time.sleep(5)
    raise RuntimeError("llama-server never became healthy")


def assert_the_candidate_is_serving(port: int, candidate_id: str) -> None:
    """Healthy says a server replied. It does not say which weights replied.

    Every number this job reports is filed under the candidate's id, so a server
    answering under any other alias makes the whole run a measurement of
    something else with the candidate's name on it (Guardrail #10).
    """
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=5) as response:
        served = json.load(response)["data"][0]["id"]
    if served != candidate_id:
        raise RuntimeError(f"the server answers to {served}, not {candidate_id}")


class Collected(NamedTuple):
    """What one repeat read, what it wrote, and what each item cost."""

    sources: dict[str, str]
    digests: dict[str, str]
    per_item: list[dict[str, Any]]


def collect(date: str, label: str, repeat: int) -> Collected:
    """Read one repeat's output back off disk.

    `sources` is a digest of the article as extracted rather than of the page,
    so it moves when a publisher edits the text and not when they change an ad.
    """
    items_dir = RUN_ROOT / date / "items"
    articles = sorted(items_dir.glob("*.article.json"))
    summaries = sorted(items_dir.glob("*.summary.json"))
    for what, found in (("articles", articles), ("summaries", summaries)):
        if len(found) != CORPUS_ITEMS:
            raise RuntimeError(
                f"{label} repeat {repeat} wrote {len(found)} {what}, not {CORPUS_ITEMS}"
            )

    sources = {}
    for path in articles:
        data = json.loads(path.read_text(encoding="utf-8"))
        source = {
            key: data.get(key) for key in ("title", "text", "source_form", "truncated", "brief")
        }
        canonical = json.dumps(source, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        sources[data["item_id"]] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    digests = {}
    per_item = []
    for path in summaries:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "ok":
            raise RuntimeError(f"{path.name} did not summarize: {data.get('failure_detail')}")
        digests[data["item_id"]] = data["output_digest"]
        per_item.append(
            {
                "item_id": data["item_id"],
                "output_digest": data["output_digest"],
                **{
                    key: data[key]
                    for key in (
                        "duration_ms",
                        "fetch_ms",
                        "extract_ms",
                        "summarize_ms",
                        "input_tokens",
                        "output_tokens",
                    )
                },
            }
        )
    return Collected(sources, digests, per_item)


def run_once(
    label: str,
    update: dict[str, Any],
    repeat: int,
    worker_count: int,
    *,
    date: str,
    candidate: str,
    candidate_file: str,
    candidate_id: str,
    port: int,
) -> dict[str, Any]:
    """One server start, one pass over the five articles, one set of readings."""
    cfg = write_config(f"{label}-{repeat}", update)
    settings = config.load(cfg)
    log_path = ROOT / f"{label}-{repeat}.llama-server.log"
    items_dir = RUN_ROOT / date / "items"
    if items_dir.exists():
        shutil.rmtree(items_dir)
    items_dir.mkdir(parents=True, exist_ok=True)
    argv = server_argv(
        binary=SERVER_BINARY,
        weights=WEIGHTS_DIR / candidate_file,
        model=settings.models.summarize,
        inference=settings.models.summarize.inference,
        port=port,
    )
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "backend/bin"
    started = time.perf_counter()
    rss_samples: list[dict[str, str]] = []
    with log_path.open("w", encoding="utf-8") as log:
        server = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
        stop = threading.Event()

        def sample_rss() -> None:
            while not stop.is_set():
                rss_samples.append(read_status(server.pid))
                time.sleep(1)

        sampler = threading.Thread(target=sample_rss, daemon=True)
        sampler.start()
        try:
            wait_for_health(port)
            assert_the_candidate_is_serving(port, candidate_id)
            startup_ms = int((time.perf_counter() - started) * 1000)
            work_started = time.perf_counter()
            workers = [
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "idhazh",
                        "work",
                        "--config",
                        str(cfg),
                        "--date",
                        date,
                        "--shard",
                        str(shard),
                        "--shards",
                        str(worker_count),
                        "--no-faithfulness",
                    ]
                )
                for shard in range(worker_count)
            ]
            failures = [proc.wait() for proc in workers]
            if any(failures):
                raise RuntimeError(f"{label} repeat {repeat} worker failures: {failures}")
            work_ms = int((time.perf_counter() - work_started) * 1000)
            total_ms = int((time.perf_counter() - started) * 1000)
        finally:
            stop.set()
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=20)
            sampler.join(timeout=5)

    found = collect(date, label, repeat)
    return {
        "label": label,
        "candidate": candidate,
        "repeat": repeat,
        "argv": argv,
        "worker_count": worker_count,
        "startup_ms": startup_ms,
        "work_ms": work_ms,
        "total_ms": total_ms,
        "model_path_ms": startup_ms + sum(item["summarize_ms"] for item in found.per_item),
        "server_rss_samples": rss_samples,
        "cgroup_memory_peak_bytes": cgroup_peak(),
        "server_facts": parse_server_facts(log_path),
        "sources": found.sources,
        "digests": found.digests,
        "per_item": found.per_item,
    }


def freeze_corpus(date: str) -> None:
    """Cut the day's plan to five articles and keep a copy beside the readings.

    The plan is frozen so every repeat reads the same five ADDRESSES. Their text
    is refetched each time, which is what `sweep_verdict` exists to notice.
    """
    plan_path = RUN_ROOT / date / "plan.json"
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["items"] = payload["items"][:CORPUS_ITEMS]
    if len(payload["items"]) != CORPUS_ITEMS:
        raise SystemExit(f"the runtime sweep needs exactly {CORPUS_ITEMS} planned articles")
    counts = Counter(item["vertical"] for item in payload["items"])
    for vertical in payload["verticals"]:
        vertical["planned"] = counts.get(vertical["id"], 0)
    text = RunPlan.model_validate(payload).to_json()
    plan_path.write_text(text, encoding="utf-8")
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "plan.json").write_text(text, encoding="utf-8")


def _bounded(name: str, value: int) -> int:
    ceiling = 2 * (os.cpu_count() or 1)
    if not 1 <= value <= ceiling:
        raise SystemExit(f"runtime_{name} must be in 1..{ceiling}")
    return value


def server_port() -> int:
    """The port the workflow declared. Never a literal, and never an argument.

    A server on one port and a stage posting to another is every item failing,
    so the number is declared once at workflow level and read back everywhere.
    An argument named `--port` would also be a second spelling of a
    llama-server flag, and the flag list has exactly one spelling.
    """
    return int(os.environ[PORT_ENV])


def sweep(args: argparse.Namespace) -> int:
    candidate = args.candidate
    # Two, because a spread needs two readings and this stops a dispatch that
    # cannot produce one. The ceiling is the job timeout rather than taste: a
    # named candidate runs two cases, and one repeat of five articles has taken
    # over an hour on every machine measured so far (Guardrail #2).
    if args.repeats < sweep_verdict.MIN_AGREEING_REPEATS:
        raise SystemExit("runtime_repeats must be at least 2 - one reading has no spread")
    port = server_port()
    threads = _bounded("threads", args.threads)
    threads_batch = _bounded("threads_batch", args.threads_batch)

    ROOT.mkdir(parents=True, exist_ok=True)
    update, workers = candidate_update(candidate, threads=threads, threads_batch=threads_batch)
    labels = [sweep_verdict.BASELINE]
    if candidate != sweep_verdict.BASELINE:
        labels.append(candidate)
    updates = {sweep_verdict.BASELINE: ({}, 1), candidate: (update, workers)}

    results = []
    for repeat in range(1, args.repeats + 1):
        for label in labels:
            current, worker_count = updates[label]
            result = run_once(
                label,
                current,
                repeat,
                worker_count,
                date=args.date,
                candidate=candidate,
                candidate_file=args.candidate_file,
                candidate_id=args.candidate_id,
                port=port,
            )
            results.append(result)
            print(
                f"{label} repeat {repeat}: startup_ms={result['startup_ms']} "
                f"work_ms={result['work_ms']} total_ms={result['total_ms']}"
            )

    found = sweep_verdict.judge(results, labels=labels, candidate=candidate)
    summary = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidate": candidate,
        # The machine THIS job drew. `llama-bench` runs in a different job and the
        # platform places each separately, so the processor beside a prefill rate
        # is not the processor beside these wall-clock figures.
        "cpu": silicon.host_cpu_model() or "unrecorded",
        "repeats": args.repeats,
        # What the timing was actually taken over. It is not `repeats` whenever
        # a page moved mid-job, and a reader who assumed it was would be reading
        # a median over a denominator nobody told them about.
        "repeats_timed": len(found.comparable),
        "fixed_corpus": str(ROOT / "plan.json").replace("\\", "/"),
        "gguf_cache_hit": args.gguf_cache_hit,
        "verdict": found.verdict,
        "problems": found.problems,
        "timing": sweep_verdict.timings(found, labels=labels, candidate=candidate),
        "results": results,
    }
    (ROOT / "runtime-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if found.verdict != sweep_verdict.PASSED:
        raise SystemExit(found.verdict)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze-corpus", help="Cut the day's plan to five articles.")
    freeze.add_argument("--date", required=True)

    run = sub.add_parser("sweep", help="Time the candidate against the baseline.")
    run.add_argument("--date", required=True)
    run.add_argument("--candidate", required=True)
    run.add_argument("--candidate-file", required=True)
    run.add_argument("--candidate-id", required=True)
    run.add_argument("--repeats", type=int, required=True)
    run.add_argument("--threads", type=int, required=True)
    run.add_argument("--threads-batch", type=int, required=True)
    run.add_argument("--gguf-cache-hit", default="false")

    args = parser.parse_args(argv)
    if args.command == "freeze-corpus":
        freeze_corpus(args.date)
        return 0
    return sweep(args)


if __name__ == "__main__":
    raise SystemExit(main())
