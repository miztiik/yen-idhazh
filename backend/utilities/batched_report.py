"""Does a second sequence buy anything on four cores, and by how much?

A verdict of "dead" is a successful measurement and exits zero; this fails only
when the instrument did.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path("backend/var/batched-bench")

#: A data row starts with a digit inside the first cell. A header does not.
DATA_ROW = re.compile(r"^\|\s*\d")

#: The table's columns, in the order llama-batched-bench prints them. The first
#: four are counts and the rest are seconds and rates.
COLUMNS: tuple[str, ...] = (
    "prompt_tokens",
    "generate_tokens",
    "parallel",
    "n_kv",
    "prefill_seconds",
    "prefill_tok_s",
    "decode_seconds",
    "decode_tok_s",
    "total_seconds",
    "total_tok_s",
)


def read_table(path: Path, levels: Sequence[int]) -> dict[int, dict[str, float]]:
    """One repeat's rows, keyed by parallel level."""
    found: dict[int, dict[str, float]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not DATA_ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(COLUMNS):
            continue
        values = [int(cell) for cell in cells[:4]] + [float(cell) for cell in cells[4:]]
        row = dict(zip(COLUMNS, values, strict=True))
        found[int(row["parallel"])] = row
    missing = [level for level in levels if level not in found]
    if missing:
        raise SystemExit(f"{path.name} has no row for parallel level(s) {missing}")
    return found


def spread(values: Sequence[float]) -> dict[str, Any]:
    return {
        "values": list(values),
        "median": statistics.median(values),
        "spread": max(values) - min(values),
    }


def summarise(
    repeats: Sequence[dict[int, dict[str, float]]], *, levels: Sequence[int], gate: float
) -> dict[str, Any]:
    """The readings, the paired ratios, and the verdict."""
    base = levels[0]
    by_level = {
        str(level): {
            "decode_tok_s": spread([table[level]["decode_tok_s"] for table in repeats]),
            "prefill_tok_s": spread([table[level]["prefill_tok_s"] for table in repeats]),
        }
        for level in levels
    }
    # Paired inside a repeat, then taken across repeats. A ratio of two medians
    # would mix repeats that ran minutes apart.
    ratios = {
        f"{level}_over_{base}": spread(
            [table[level]["decode_tok_s"] / table[base]["decode_tok_s"] for table in repeats]
        )
        for level in levels[1:]
    }
    gate_ratio = ratios[f"2_over_{base}"]
    return {
        "aggregate_by_parallel_level": by_level,
        "paired_decode_ratios": ratios,
        "verdict": "alive" if gate_ratio["median"] >= gate else "dead",
    }


def _report(found: dict[str, Any], *, levels: Sequence[int], gate: float, repeats: int) -> None:
    base = levels[0]
    print(f"aggregate decode (S_TG t/s), {repeats} repeats, one host:")
    for level in levels:
        stat = found["aggregate_by_parallel_level"][str(level)]["decode_tok_s"]
        values = ", ".join(f"{value:.2f}" for value in stat["values"])
        print(
            f"  B={level}: median {stat['median']:.2f} t/s, "
            f"spread {stat['spread']:.2f}, values {values}"
        )
    gate_ratio = found["paired_decode_ratios"][f"2_over_{base}"]
    paired = ", ".join(f"{value:.3f}" for value in gate_ratio["values"])
    print(
        f"gate: S_TG(B=2) / S_TG(B=1) = {gate_ratio['median']:.3f} "
        f"(spread {gate_ratio['spread']:.3f}, paired {paired}); "
        f"gate is {gate}x; parallel decode is {found['verdict']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", required=True, help="Comma-separated parallel levels.")
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--gate-ratio", type=float, required=True)
    parser.add_argument("--llama-build", required=True)
    parser.add_argument("--model-file", required=True)
    parser.add_argument("--prompt-tokens", type=int, required=True)
    parser.add_argument("--generate-tokens", type=int, required=True)
    parser.add_argument("--n-ctx", type=int, required=True)
    parser.add_argument("--n-batch", type=int, required=True)
    parser.add_argument("--n-ubatch", type=int, required=True)
    parser.add_argument("--n-threads", type=int, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    levels = [int(value) for value in args.levels.split(",")]
    tables = [read_table(args.root / f"repeat-{n}.txt", levels) for n in range(1, args.repeats + 1)]
    found = summarise(tables, levels=levels, gate=args.gate_ratio)

    summary = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "llama_cpp_build": args.llama_build,
        "model_file": args.model_file,
        "prompt_tokens": args.prompt_tokens,
        "generate_tokens": args.generate_tokens,
        "n_ctx": args.n_ctx,
        "n_batch": args.n_batch,
        "n_ubatch": args.n_ubatch,
        "n_threads": args.n_threads,
        "parallel_levels": levels,
        "repeats": args.repeats,
        "gate_ratio": args.gate_ratio,
        **found,
        "tables": [
            {"repeat": index, "rows": [table[level] for level in levels]}
            for index, table in enumerate(tables, start=1)
        ],
    }
    (args.root / "batched-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _report(found, levels=levels, gate=args.gate_ratio, repeats=args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
