"""Turn raw llama-bench output into the numbers the pipeline design actually needs:
seconds per article, per length bucket, and total wall-clock for a batch of URLs.

`--markdown` prints the rates as a table for a run page instead. Same file, same
parse, same grouping: a second formatter over the same JSON would be two things
to keep agreeing about what a prefill row means (CLAUDE.md Guardrail #5).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# English BPE runs ~1.33 tokens/word. Buckets are (words, +/- words, share of feed).
#
# Measured 2026-08-22 by the `corpus` job over 20 live articles, replacing the
# invented 400/1200/3500 at 25/55/20. The real corpus is bimodal: half of it is
# short, and the long tail is a quarter rather than a fifth. Blending against
# the old shares made every per-article figure a statement about a corpus this
# project does not have.
BUCKETS = {
    "short": (411, 200, 0.50),
    "medium": (1546, 500, 0.25),
    "long": (2769, 1500, 0.25),
}
TOKENS_PER_WORD = 1.33
OUTPUT_TOKENS = {"short": 150, "medium": 200, "long": 250}


@dataclass
class Throughput:
    model: str
    threads: int
    prefill: dict[int, tuple[float, float]]  # n_prompt -> (tok/s, stddev)
    decode: tuple[float, float] | None  # (tok/s, stddev)
    # How many times llama-bench actually timed each row. A spread over one draw
    # is not a spread, and a table that printed `+/- 0.00` for it would claim a
    # steadiness nobody measured (CLAUDE.md Guardrail #10).
    prefill_draws: dict[int, int] = field(default_factory=dict)
    decode_draws: int = 0


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
    by_model_and_threads: dict[tuple[str, int], Throughput] = {}
    for r in runs:
        name = Path(r.get("model_filename", r.get("model", "?"))).name
        threads = int(r.get("n_threads", 0))
        key = (name, threads)
        tp = by_model_and_threads.setdefault(key, Throughput(name, threads, {}, None))
        ts = float(r["avg_ts"])
        sd = float(r.get("stddev_ts", 0.0))
        if int(r.get("n_prompt", 0)) > 0:
            tp.prefill[int(r["n_prompt"])] = (ts, sd)
            tp.prefill_draws[int(r["n_prompt"])] = draws(r)
        elif int(r.get("n_gen", 0)) > 0:
            tp.decode = (ts, sd)
            tp.decode_draws = draws(r)
    return list(by_model_and_threads.values())


def draws(row: dict[str, Any]) -> int:
    """How many times llama-bench timed this row, 0 where it did not say."""
    samples = row.get("samples_ts")
    if isinstance(samples, list):
        return len(samples)
    return 0


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


def seconds(
    tp: Throughput,
    bucket: str,
    words: float,
    *,
    system_prompt_tokens: int,
    truncation_cap_tokens: int,
) -> float:
    article_tokens = min(int(words * TOKENS_PER_WORD), truncation_cap_tokens)
    tokens_in = article_tokens + system_prompt_tokens
    pf_ts, _ = interpolate(tp.prefill, tokens_in)
    dec_ts = tp.decode[0] if tp.decode else float("nan")
    return tokens_in / pf_ts + OUTPUT_TOKENS[bucket] / dec_ts


def report(
    tps: list[Throughput],
    n_urls: int,
    parallel: int,
    *,
    system_prompt_tokens: int | None,
    truncation_cap_tokens: int | None,
) -> None:
    for tp in sorted(tps, key=lambda t: (t.model, t.threads)):
        print(f"\n### {tp.model}  (threads={tp.threads})")
        pf = ", ".join(f"{n}tok={v[0]:.1f}+/-{v[1]:.1f}" for n, v in sorted(tp.prefill.items()))
        print(f"  prefill tok/s : {pf}")
        if tp.decode:
            print(f"  decode  tok/s : {tp.decode[0]:.2f} +/- {tp.decode[1]:.2f}")
        if system_prompt_tokens is None:
            print("  derived timings : skipped; pass the model-specific --system-prompt-tokens")
            continue
        if truncation_cap_tokens is None:
            raise ValueError("derived timings require the config-specific truncation cap")
        print(
            f"  {'bucket':<8} {'in_tok':>7} {'out_tok':>8} {'best':>8} {'typical':>9} {'worst':>8}"
        )

        blended = 0.0
        for bucket, (words, spread, share) in BUCKETS.items():
            lo = seconds(
                tp,
                bucket,
                max(50, words - spread),
                system_prompt_tokens=system_prompt_tokens,
                truncation_cap_tokens=truncation_cap_tokens,
            )
            mid = seconds(
                tp,
                bucket,
                words,
                system_prompt_tokens=system_prompt_tokens,
                truncation_cap_tokens=truncation_cap_tokens,
            )
            hi = seconds(
                tp,
                bucket,
                words + spread,
                system_prompt_tokens=system_prompt_tokens,
                truncation_cap_tokens=truncation_cap_tokens,
            )
            article_tokens = min(int(words * TOKENS_PER_WORD), truncation_cap_tokens)
            tokens_in = article_tokens + system_prompt_tokens
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


#: What the table says when the bench produced nothing to say. It is one
#: sentence and it names the file, because the next question a reader has is
#: whether the measurement failed or was never asked for.
NO_READINGS = (
    "## Model speed\n"
    "\n"
    "The llama-bench speed case produced no readings. `backend/var/llm.json` is\n"
    "missing or unreadable, so there are no rates to show here; this job's own\n"
    "log says what happened."
)


def _rate(value: float, spread: float, draws_taken: int) -> str:
    """One rate, with its spread where a spread was measured and not where it was not."""
    if draws_taken == 1:
        return f"{value:.2f}"
    return f"{value:.2f} +/- {spread:.2f}"


def _draws_cell(draws_taken: int) -> str:
    if draws_taken == 1:
        return "1 draw, no spread"
    if draws_taken == 0:
        return "not stated"
    return str(draws_taken)


def markdown(
    runs: list[dict[str, Any]] | None,
    *,
    candidate: str = "",
    quantisation: str = "",
) -> str:
    """The rates as a table a person reads on the run page.

    Every number carries its unit in the column heading and its meaning in the
    sentence above the table, and the machine is named because the same
    dispatch's other job runs on its own host and often draws a different one
    (`docs/reference/benchmarks/the-processor-lottery.md`).
    """
    if not runs:
        return NO_READINGS

    head = runs[0]
    cpu = str(head.get("cpu_info") or "an unrecorded processor")
    build = head.get("build_number")
    where = f"on {cpu}" + (f", llama.cpp build b{build}" if build else "")
    title = candidate or Path(str(head.get("model_filename", head.get("model", "?")))).name

    lines = [
        f"## Model speed: {title}",
        "",
        f"Measured by `llama-bench` {where}.",
        "",
        "Every rate below is **tokens a second, and more is faster**. Reading is how"
        " fast the model takes a prompt in; writing is how fast it puts an answer out."
        " A prompt is read once and an answer is written a token at a time, so the two"
        " rates differ by an order of magnitude and that is normal.",
        "",
        "| Weights | Threads | What was timed | Tokens a second | Draws |",
        "| --- | ---: | --- | ---: | --- |",
    ]

    for tp in sorted(collect(runs), key=lambda t: (t.model, t.threads)):
        for count in sorted(tp.prefill):
            value, spread = tp.prefill[count]
            taken = tp.prefill_draws.get(count, 0)
            lines.append(
                f"| `{tp.model}` | {tp.threads} | Reading a {count:,}-token prompt "
                f"| {_rate(value, spread, taken)} | {_draws_cell(taken)} |"
            )
        if tp.decode is not None:
            value, spread = tp.decode
            lines.append(
                f"| `{tp.model}` | {tp.threads} | Writing an answer "
                f"| {_rate(value, spread, tp.decode_draws)} "
                f"| {_draws_cell(tp.decode_draws)} |"
            )

    lines += [
        "",
        f"Candidate `{candidate or 'unstated'}`, quantisation `{quantisation or 'unstated'}`.",
        "",
        "This is the machine **this job** drew. The server case of the same dispatch"
        " runs on its own runner and has drawn a different processor in 3 of 4"
        " measured dispatches, so the wall clock it reports is about a different"
        " machine from these rates.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bench_json", type=Path)
    ap.add_argument("--urls", type=int, default=40)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument(
        "--markdown",
        action="store_true",
        help="Print the rates as a table for a run page instead of the derived timings.",
    )
    ap.add_argument(
        "--candidate-id",
        default="",
        help="The configuration id these weights serve as, for the table's heading.",
    )
    ap.add_argument(
        "--quantisation",
        default="",
        help="The quantisation these bytes carry, for the table's footer.",
    )
    ap.add_argument(
        "--system-prompt-tokens",
        type=int,
        help="Rendered prompt tokens for this model; omit to suppress derived timings.",
    )
    ap.add_argument(
        "--truncation-cap-tokens",
        type=int,
        help="Configured article-token cap; required with --system-prompt-tokens.",
    )
    args = ap.parse_args()
    if (args.system_prompt_tokens is None) != (args.truncation_cap_tokens is None):
        ap.error("--system-prompt-tokens and --truncation-cap-tokens must be supplied together")
    if args.system_prompt_tokens is not None and args.system_prompt_tokens < 1:
        ap.error("--system-prompt-tokens must be positive")
    if args.truncation_cap_tokens is not None and args.truncation_cap_tokens < 1:
        ap.error("--truncation-cap-tokens must be positive")
    if args.urls < 1 or args.parallel < 1:
        ap.error("--urls and --parallel must be positive")

    # The markdown path degrades and the text path does not, and the difference
    # is who is reading. A run summary is written by a step that must not fail
    # the job it is reporting on, so an absent or unreadable file becomes a
    # sentence saying so (CLAUDE.md section 1a). A person at a terminal asked
    # for a report and wants the error.
    if args.markdown:
        print(
            markdown(
                _runs_or_none(args.bench_json),
                candidate=args.candidate_id,
                quantisation=args.quantisation,
            )
        )
        return 0

    runs = load_runs(args.bench_json)
    if not runs:
        print("no runs parsed", file=sys.stderr)
        return 1
    report(
        collect(runs),
        args.urls,
        args.parallel,
        system_prompt_tokens=args.system_prompt_tokens,
        truncation_cap_tokens=args.truncation_cap_tokens,
    )
    return 0


def _runs_or_none(path: Path) -> list[dict[str, Any]] | None:
    """The rows, or `None` where there are none to be had and why does not matter."""
    try:
        runs = load_runs(path)
    except (OSError, ValueError):
        return None
    return runs or None


if __name__ == "__main__":
    raise SystemExit(main())
