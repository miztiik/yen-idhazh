"""Turn raw llama-bench output into the numbers the pipeline design actually needs:
seconds per article, per length bucket, and total wall-clock for a batch of URLs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# English BPE runs ~1.33 tokens/word. Buckets are (words, +/- words, share of feed).
BUCKETS = {
    "short": (400, 200, 0.25),
    "medium": (1200, 500, 0.55),
    "long": (3500, 1500, 0.20),
}
TOKENS_PER_WORD = 1.33
SYSTEM_PROMPT_TOKENS = 200
OUTPUT_TOKENS = {"short": 150, "medium": 200, "long": 250}


@dataclass
class Throughput:
    model: str
    threads: int
    prefill: dict[int, tuple[float, float]]  # n_prompt -> (tok/s, stddev)
    decode: tuple[float, float] | None       # (tok/s, stddev)


def load_runs(path: Path) -> list[dict[str, Any]]:
    """llama-bench emits one JSON array per invocation; a file may hold several."""
    raw = path.read_text(encoding="utf-8").strip()
    runs: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(raw):
        while idx < len(raw) and raw[idx] not in "[{":
            idx += 1
        if idx >= len(raw):
            break
        obj, end = decoder.raw_decode(raw, idx)
        runs.extend(obj if isinstance(obj, list) else [obj])
        idx = end
    return runs


def collect(runs: list[dict[str, Any]]) -> list[Throughput]:
    by_model: dict[str, Throughput] = {}
    for r in runs:
        name = Path(r.get("model_filename", r.get("model", "?"))).name
        tp = by_model.setdefault(name, Throughput(name, int(r.get("n_threads", 0)), {}, None))
        ts = float(r["avg_ts"])
        sd = float(r.get("stddev_ts", 0.0))
        if int(r.get("n_prompt", 0)) > 0:
            tp.prefill[int(r["n_prompt"])] = (ts, sd)
        elif int(r.get("n_gen", 0)) > 0:
            tp.decode = (ts, sd)
    return list(by_model.values())


def interpolate(prefill: dict[int, tuple[float, float]], n: int) -> tuple[float, float]:
    """Prefill tok/s drifts with context length; interpolate between measured points."""
    if not prefill:
        raise ValueError("no prefill measurements")
    pts = sorted(prefill)
    if n <= pts[0]:
        return prefill[pts[0]]
    if n >= pts[-1]:
        return prefill[pts[-1]]
    lo = max(p for p in pts if p <= n)
    hi = min(p for p in pts if p >= n)
    if lo == hi:
        return prefill[lo]
    w = (n - lo) / (hi - lo)
    return (
        prefill[lo][0] + w * (prefill[hi][0] - prefill[lo][0]),
        max(prefill[lo][1], prefill[hi][1]),
    )


def seconds(tp: Throughput, bucket: str, words: float) -> float:
    tokens_in = int(words * TOKENS_PER_WORD) + SYSTEM_PROMPT_TOKENS
    pf_ts, _ = interpolate(tp.prefill, tokens_in)
    dec_ts = tp.decode[0] if tp.decode else float("nan")
    return tokens_in / pf_ts + OUTPUT_TOKENS[bucket] / dec_ts


def report(tps: list[Throughput], n_urls: int, parallel: int) -> None:
    for tp in sorted(tps, key=lambda t: t.model):
        print(f"\n### {tp.model}  (threads={tp.threads})")
        pf = ", ".join(f"{n}tok={v[0]:.1f}+/-{v[1]:.1f}" for n, v in sorted(tp.prefill.items()))
        print(f"  prefill tok/s : {pf}")
        if tp.decode:
            print(f"  decode  tok/s : {tp.decode[0]:.2f} +/- {tp.decode[1]:.2f}")
        print(
            f"  {'bucket':<8} {'in_tok':>7} {'out_tok':>8} "
            f"{'best':>8} {'typical':>9} {'worst':>8}"
        )

        blended = 0.0
        for bucket, (words, spread, share) in BUCKETS.items():
            lo = seconds(tp, bucket, max(50, words - spread))
            mid = seconds(tp, bucket, words)
            hi = seconds(tp, bucket, words + spread)
            tokens_in = int(words * TOKENS_PER_WORD) + SYSTEM_PROMPT_TOKENS
            print(
                f"  {bucket:<8} {tokens_in:>7} {OUTPUT_TOKENS[bucket]:>8} "
                f"{lo:>7.0f}s {mid:>8.0f}s {hi:>7.0f}s"
            )
            blended += share * mid

        serial = blended * n_urls
        waves = -(-n_urls // parallel)
        fanout = blended * waves
        print(f"  blended/article : {blended:.0f}s")
        print(
            f"  {n_urls} URLs serial   : {serial / 60:.0f} min  "
            f"({serial / 3600:.2f}h of the 6h job cap)"
        )
        print(
            f"  {n_urls} URLs x{parallel} matrix: {fanout / 60:.0f} min wall-clock "
            f"({waves} wave(s))"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bench_json", type=Path)
    ap.add_argument("--urls", type=int, default=40)
    ap.add_argument("--parallel", type=int, default=20)
    args = ap.parse_args()

    runs = load_runs(args.bench_json)
    if not runs:
        print("no runs parsed", file=sys.stderr)
        return 1
    report(collect(runs), args.urls, args.parallel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
